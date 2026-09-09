"""Versioned, local LLM provider and stage-binding configuration.

This module belongs to the editable product layer.  It deliberately does not
change the Evaluation Core, LightRAG adapter, scorer, or metric contracts.
Provider configuration is server-owned; API keys are represented only by
secret references and are never serialized in a response or configuration
digest.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.ids import safe_id

if TYPE_CHECKING:
    from rag_eval.authoring.providers import StructuredProposalProvider


LLM_CONFIG_SCHEMA_VERSION = "1.0"


class LLMModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LLMProviderKind(StrEnum):
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"


class LLMHealthStatus(StrEnum):
    NOT_CHECKED = "not_checked"
    HEALTHY = "healthy"
    UNREACHABLE = "unreachable"
    MODEL_UNAVAILABLE = "model_unavailable"
    INVALID = "invalid"


class LLMLatencyStatus(StrEnum):
    """Operational result of the independent provider latency probe."""

    NOT_CHECKED = "not_checked"
    MEASURED = "measured"
    UNREACHABLE = "unreachable"
    INVALID = "invalid"


class LLMStage(StrEnum):
    TARGET_DISCOVERY = "target_discovery"
    QUESTION_GENERATION = "question_generation"
    ANSWER_EVIDENCE = "answer_evidence"
    REVIEW_ASSIST = "review_assist"
    CALIBRATION = "calibration"
    RUNTIME_GENERATION = "runtime_generation"
    RUNTIME_EMBEDDING = "runtime_embedding"


STAGE_ORDER: tuple[LLMStage, ...] = (
    LLMStage.TARGET_DISCOVERY,
    LLMStage.QUESTION_GENERATION,
    LLMStage.ANSWER_EVIDENCE,
    LLMStage.REVIEW_ASSIST,
    LLMStage.CALIBRATION,
    LLMStage.RUNTIME_GENERATION,
    LLMStage.RUNTIME_EMBEDDING,
)


class LLMProviderConfig(LLMModel):
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    display_name: str = Field(min_length=1, max_length=120)
    kind: LLMProviderKind
    endpoint: str = Field(min_length=1, max_length=500)
    # A provider may be saved before its model catalogue is detected.  Stage
    # bindings remain fail-closed and cannot use such a provider until a model
    # is selected from that catalogue.
    model: str = Field(default="", max_length=200)
    embedding_model: str | None = Field(default=None, max_length=200)
    enabled: bool = True
    # Internal-only reference. API projections omit this field entirely.
    api_key_ref: str | None = None
    health_status: LLMHealthStatus = LLMHealthStatus.NOT_CHECKED
    available_models: list[str] = Field(default_factory=list)
    available_chat_models: list[str] = Field(default_factory=list)
    available_embedding_models: list[str] = Field(default_factory=list)
    health_message: str | None = None
    last_checked_at: datetime | None = None
    # Latency is deliberately separate from model-catalogue health.  A
    # provider can respond quickly while its selected model is unavailable,
    # and a catalogue detection must not be mistaken for a timing result.
    latency_status: LLMLatencyStatus = LLMLatencyStatus.NOT_CHECKED
    latency_ms: int | None = Field(default=None, ge=0)
    last_latency_checked_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_endpoint(self) -> LLMProviderConfig:
        parsed = urlsplit(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("endpoint must be an absolute http(s) URL")
        if any(char.isspace() for char in self.endpoint):
            raise ValueError("endpoint cannot contain whitespace")
        return self


class LLMStageBinding(LLMModel):
    stage: LLMStage
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    model: str | None = Field(default=None, max_length=200)
    enabled: bool = True
    fallback_provider_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_-]{1,63}$")


class LLMConfigRevision(LLMModel):
    schema_version: str = LLM_CONFIG_SCHEMA_VERSION
    revision_id: str = Field(pattern=r"^llm-config-[a-z0-9-]+$")
    config_version: int = Field(ge=1)
    created_at: datetime
    actor: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=500)
    parent_revision_id: str | None = None
    config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    providers: list[LLMProviderConfig] = Field(default_factory=list)
    bindings: list[LLMStageBinding] = Field(default_factory=list)


class SecretStoreLike(Protocol):
    def get(self, reference: str) -> str: ...


def _base_endpoint(endpoint: str) -> str:
    value = endpoint.rstrip("/")
    for suffix in ("/api/generate", "/api/chat", "/api/tags", "/api/version"):
        if value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def _ollama_generate_endpoint(endpoint: str) -> str:
    value = endpoint.rstrip("/")
    if value.endswith("/api/generate"):
        return value
    return f"{value}/api/generate"


def _models_endpoint(provider: LLMProviderConfig) -> str:
    endpoint = provider.endpoint.rstrip("/")
    if provider.kind == LLMProviderKind.OLLAMA:
        return f"{_base_endpoint(endpoint)}/api/tags"
    if endpoint.endswith("/chat/completions"):
        return endpoint[: -len("/chat/completions")] + "/models"
    if endpoint.endswith("/completions"):
        return endpoint[: -len("/completions")] + "/models"
    if endpoint.endswith("/models"):
        return endpoint
    return endpoint + "/models"


def _latency_endpoint(provider: LLMProviderConfig) -> str:
    """Return the smallest portable request that proves the service responds.

    Ollama exposes a dedicated version endpoint, so measuring it never also
    downloads a model catalogue.  OpenAI-compatible providers have no common
    health endpoint; ``/models`` is the light authenticated endpoint that is
    broadly supported.  Its response is intentionally discarded here.
    """

    if provider.kind == LLMProviderKind.OLLAMA:
        return f"{_base_endpoint(provider.endpoint)}/api/version"
    return _models_endpoint(provider)


def _config_payload(providers: list[LLMProviderConfig], bindings: list[LLMStageBinding]) -> dict[str, Any]:
    # Operational health fields and secret references are intentionally absent:
    # a connection check must not change the identity of a configuration.
    return {
        "providers": [
            {
                "provider_id": item.provider_id,
                "display_name": item.display_name,
                "kind": item.kind.value,
                "endpoint": item.endpoint,
                "model": item.model,
                "embedding_model": item.embedding_model,
                "enabled": item.enabled,
                "api_key_configured": bool(item.api_key_ref),
            }
            for item in sorted(providers, key=lambda value: value.provider_id)
        ],
        "bindings": [
            {
                "stage": item.stage.value,
                "provider_id": item.provider_id,
                "model": item.model,
                "enabled": item.enabled,
                "fallback_provider_id": item.fallback_provider_id,
            }
            for item in sorted(bindings, key=lambda value: value.stage.value)
        ],
    }


def configuration_digest(providers: list[LLMProviderConfig], bindings: list[LLMStageBinding]) -> str:
    encoded = json.dumps(_config_payload(providers, bindings), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_default_endpoint(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "http://127.0.0.1:11434"
    return _base_endpoint(urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")))


class LLMConfigurationService:
    """Append-only configuration revisions plus mutable health observations."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.revisions_root = root / "revisions"
        self.current_path = root / "current.json"
        self.revisions_root.mkdir(parents=True, exist_ok=True)
        if not self.current_path.is_file():
            self._bootstrap()

    def _bootstrap(self) -> None:
        endpoint = _normalize_default_endpoint(os.environ.get("RAG_EVAL_AUTHORING_OLLAMA_URL", "http://127.0.0.1:11434"))
        model = os.environ.get("RAG_EVAL_AUTHORING_OLLAMA_MODEL", "qwen3:4b-instruct")
        embedding_model = os.environ.get("RAG_EVAL_AUTHORING_OLLAMA_EMBEDDING_MODEL", "bge-m3:latest")
        providers = [
            LLMProviderConfig(
                provider_id="ollama-local",
                display_name="Ollama（本机）",
                kind=LLMProviderKind.OLLAMA,
                endpoint=endpoint,
                model=model,
                embedding_model=embedding_model,
            )
        ]
        remote_url = os.environ.get("RAG_EVAL_AUTHORING_REMOTE_URL", "").strip()
        remote_model = os.environ.get("RAG_EVAL_AUTHORING_REMOTE_MODEL", "").strip()
        if remote_url and remote_model:
            providers.append(
                LLMProviderConfig(
                    provider_id="remote-configured",
                    display_name="远程 OpenAI 兼容接口",
                    kind=LLMProviderKind.OPENAI_COMPATIBLE,
                    endpoint=remote_url,
                    model=remote_model,
                )
            )
        bindings = [
            LLMStageBinding(
                stage=stage,
                provider_id="ollama-local",
                model=embedding_model if stage == LLMStage.RUNTIME_EMBEDDING else model,
            )
            for stage in STAGE_ORDER
        ]
        self._write_revision(providers, bindings, actor="system", reason="initial local model configuration")

    def _load_current(self) -> LLMConfigRevision:
        return LLMConfigRevision.model_validate_json(self.current_path.read_text(encoding="utf-8"))

    def current(self) -> LLMConfigRevision:
        return self._load_current()

    def revisions(self) -> list[LLMConfigRevision]:
        return [
            LLMConfigRevision.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.revisions_root.glob("*.json"), reverse=True)
        ]

    def _validate_graph(self, providers: list[LLMProviderConfig], bindings: list[LLMStageBinding]) -> None:
        provider_ids = [item.provider_id for item in providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("provider_id values must be unique")
        provider_map = {item.provider_id: item for item in providers}
        stages = [item.stage for item in bindings]
        if len(stages) != len(set(stages)):
            raise ValueError("each LLM stage may have only one binding")
        unknown_stages = set(stages).difference(STAGE_ORDER)
        if unknown_stages:
            raise ValueError("unknown LLM stage")
        for binding in bindings:
            provider = provider_map.get(binding.provider_id)
            if provider is None:
                raise ValueError(f"stage {binding.stage.value} references unknown provider {binding.provider_id!r}")
            if binding.enabled and not provider.enabled:
                raise ValueError(f"stage {binding.stage.value} references a disabled provider")
            if binding.enabled and not (binding.model or provider.model).strip():
                raise ValueError(f"stage {binding.stage.value} requires a selected model")
            if binding.fallback_provider_id is not None and binding.fallback_provider_id not in provider_map:
                raise ValueError(f"stage {binding.stage.value} references unknown fallback provider")
        missing = set(STAGE_ORDER).difference(stages)
        if missing:
            raise ValueError("all LLM stages require an explicit binding")

    def _write_revision(self, providers: list[LLMProviderConfig], bindings: list[LLMStageBinding], *, actor: str, reason: str) -> LLMConfigRevision:
        self._validate_graph(providers, bindings)
        previous = self._load_current() if self.current_path.is_file() else None
        now = datetime.now(UTC)
        version = (previous.config_version + 1) if previous else 1
        revision_id = f"llm-config-{version:04d}"
        digest = configuration_digest(providers, bindings)
        revision = LLMConfigRevision(
            revision_id=revision_id,
            config_version=version,
            created_at=now,
            actor=actor.strip() or "local-user",
            reason=reason.strip() or "updated model configuration",
            parent_revision_id=previous.revision_id if previous else None,
            config_digest=digest,
            providers=providers,
            bindings=bindings,
        )
        atomic_write_json(self.revisions_root / f"{safe_id(revision_id)}.json", revision.model_dump(mode="json"))
        atomic_write_json(self.current_path, revision.model_dump(mode="json"))
        return revision

    def save(self, providers: list[LLMProviderConfig], bindings: list[LLMStageBinding], *, actor: str, reason: str) -> LLMConfigRevision:
        # Health is an observation, not part of config identity.  An endpoint
        # change invalidates the catalogue; choosing a detected model does not.
        # This keeps the model dropdown usable after a normal save.
        previous = self._load_current() if self.current_path.is_file() else None
        previous_by_id = {item.provider_id: item for item in previous.providers} if previous else {}
        now = datetime.now(UTC)
        normalized: list[LLMProviderConfig] = []
        for item in providers:
            prior = previous_by_id.get(item.provider_id)
            same_catalogue = prior is not None and prior.kind == item.kind and prior.endpoint == item.endpoint
            normalized.append(item.model_copy(update={
                "health_status": LLMHealthStatus.NOT_CHECKED,
                "available_models": prior.available_models if same_catalogue else [],
                "available_chat_models": prior.available_chat_models if same_catalogue else [],
                "available_embedding_models": prior.available_embedding_models if same_catalogue else [],
                "health_message": None,
                "last_checked_at": None,
                "latency_status": prior.latency_status if same_catalogue else LLMLatencyStatus.NOT_CHECKED,
                "latency_ms": prior.latency_ms if same_catalogue else None,
                "last_latency_checked_at": prior.last_latency_checked_at if same_catalogue else None,
                "updated_at": now,
            }))
        return self._write_revision(normalized, bindings, actor=actor, reason=reason)

    def update_health(
        self,
        provider_id: str,
        *,
        status: LLMHealthStatus,
        models: list[str],
        chat_models: list[str] | None = None,
        embedding_models: list[str] | None = None,
        message: str | None,
    ) -> LLMProviderConfig:
        current = self._load_current()
        found = False
        updated: list[LLMProviderConfig] = []
        now = datetime.now(UTC)
        for provider in current.providers:
            if provider.provider_id == provider_id:
                found = True
                updated.append(provider.model_copy(update={
                    "health_status": status,
                    "available_models": sorted(set(models)),
                    "available_chat_models": sorted(set(chat_models if chat_models is not None else models)),
                    "available_embedding_models": sorted(set(embedding_models if embedding_models is not None else models)),
                    "health_message": message,
                    "last_checked_at": now,
                    "updated_at": now,
                }))
            else:
                updated.append(provider)
        if not found:
            raise FileNotFoundError(provider_id)
        # Do not create a config revision for an operational health observation.
        updated_revision = current.model_copy(update={"providers": updated})
        atomic_write_json(self.current_path, updated_revision.model_dump(mode="json"))
        return next(item for item in updated if item.provider_id == provider_id)

    def update_latency(
        self,
        provider_id: str,
        *,
        status: LLMLatencyStatus,
        latency_ms: int | None,
    ) -> LLMProviderConfig:
        """Persist a timing observation without changing catalogue health."""

        current = self._load_current()
        found = False
        updated: list[LLMProviderConfig] = []
        now = datetime.now(UTC)
        for provider in current.providers:
            if provider.provider_id == provider_id:
                found = True
                updated.append(provider.model_copy(update={
                    "latency_status": status,
                    "latency_ms": latency_ms,
                    "last_latency_checked_at": now,
                    "updated_at": now,
                }))
            else:
                updated.append(provider)
        if not found:
            raise FileNotFoundError(provider_id)
        updated_revision = current.model_copy(update={"providers": updated})
        atomic_write_json(self.current_path, updated_revision.model_dump(mode="json"))
        return next(item for item in updated if item.provider_id == provider_id)

    def provider_for_stage(self, stage: LLMStage) -> tuple[LLMProviderConfig, LLMStageBinding]:
        current = self._load_current()
        binding = next(item for item in current.bindings if item.stage == stage)
        return next(item for item in current.providers if item.provider_id == binding.provider_id), binding

    def build_provider(self, stage: LLMStage, *, requested: str, remote_consent: bool, secret_store: SecretStoreLike | None = None) -> tuple["StructuredProposalProvider | None", str]:
        """Build an authoring proposal provider from the stage binding.

        Explicit ``rule``/``manual`` requests remain untouched.  A remote
        binding is never used without the existing explicit consent gate.
        """

        try:
            provider, binding = self.provider_for_stage(stage)
        except (FileNotFoundError, StopIteration):
            return None, requested
        if not provider.enabled or not binding.enabled:
            return None, requested
        from rag_eval.authoring.providers import ConfiguredRemoteProvider, LocalOllamaProvider

        if provider.kind == LLMProviderKind.OLLAMA and requested == "ollama":
            model = binding.model or provider.model
            return LocalOllamaProvider(endpoint=_ollama_generate_endpoint(provider.endpoint), model=model), "ollama"
        if provider.kind == LLMProviderKind.OPENAI_COMPATIBLE and requested == "remote" and remote_consent:
            authorization = None
            if provider.api_key_ref and secret_store is not None:
                authorization = secret_store.get(provider.api_key_ref)
            return ConfiguredRemoteProvider(endpoint=provider.endpoint, model=binding.model or provider.model, authorization=authorization), "remote"
        return None, requested

    def check_provider(self, provider_id: str, *, secret_store: SecretStoreLike | None = None) -> LLMProviderConfig:
        current = self._load_current()
        try:
            provider = next(item for item in current.providers if item.provider_id == provider_id)
        except StopIteration as exc:
            raise FileNotFoundError(provider_id) from exc
        if not provider.enabled:
            return self.update_health(provider_id, status=LLMHealthStatus.INVALID, models=[], message="provider is disabled")
        if provider.kind == LLMProviderKind.OPENAI_COMPATIBLE and not provider.api_key_ref:
            return self.update_health(provider_id, status=LLMHealthStatus.INVALID, models=[], message="external provider requires an API key")
        headers: dict[str, str] = {}
        if provider.api_key_ref and secret_store is not None:
            try:
                headers["Authorization"] = f"Bearer {secret_store.get(provider.api_key_ref)}"
            except Exception:
                return self.update_health(provider_id, status=LLMHealthStatus.INVALID, models=[], message="configured API key is unavailable")
        try:
            # Health checks target an explicit local/remote endpoint.  Do not
            # silently route them through a shell proxy configuration.
            response = httpx.get(_models_endpoint(provider), headers=headers, timeout=8, trust_env=False)
            response.raise_for_status()
            payload = response.json()
            if provider.kind == LLMProviderKind.OLLAMA:
                raw_models = payload.get("models", []) if isinstance(payload, dict) else []
                models = [str(item.get("name")) for item in raw_models if isinstance(item, dict) and item.get("name")]
                chat_models = [
                    str(item.get("name"))
                    for item in raw_models
                    if isinstance(item, dict)
                    and item.get("name")
                    and any(capability in {"completion", "chat", "tools"} for capability in item.get("capabilities", []) if isinstance(capability, str))
                ]
                embedding_models = [
                    str(item.get("name"))
                    for item in raw_models
                    if isinstance(item, dict)
                    and item.get("name")
                    and any(capability in {"embedding", "embed"} for capability in item.get("capabilities", []) if isinstance(capability, str))
                ]
                # Older Ollama versions do not advertise capabilities.  Keep
                # their usable catalogue selectable rather than hiding it.
                chat_models = chat_models or models
                embedding_models = embedding_models or models
            else:
                raw_models = payload.get("data", []) if isinstance(payload, dict) else []
                models = [str(item.get("id")) for item in raw_models if isinstance(item, dict) and item.get("id")]
                chat_models = models
                embedding_models = models
            # The selected models belong to typed stage bindings, not to the
            # provider transport card.  Provider-level model fields are kept
            # solely as a backwards-compatible default for older revisions.
            selected_models = [
                binding.model or provider.model
                for binding in current.bindings
                if binding.provider_id == provider.provider_id and binding.enabled and (binding.model or provider.model)
            ]
            missing_models = [value for value in selected_models if models and value not in models]
            selected = not missing_models
            status = LLMHealthStatus.HEALTHY if selected else LLMHealthStatus.MODEL_UNAVAILABLE
            message = None if selected else f"selected model(s) not advertised by the endpoint: {', '.join(missing_models)}"
            return self.update_health(
                provider_id,
                status=status,
                models=models,
                chat_models=chat_models,
                embedding_models=embedding_models,
                message=message,
            )
        # The health endpoint is a diagnostic surface.  Any unexpected
        # transport or platform error must be represented as a typed status,
        # never converted into an opaque HTTP 500 for the WebUI.
        except Exception as exc:
            return self.update_health(provider_id, status=LLMHealthStatus.UNREACHABLE, models=[], message=str(exc)[:240])

    def check_latency(self, provider_id: str, *, secret_store: SecretStoreLike | None = None) -> LLMProviderConfig:
        """Measure one lightweight request without detecting or changing models."""

        current = self._load_current()
        try:
            provider = next(item for item in current.providers if item.provider_id == provider_id)
        except StopIteration as exc:
            raise FileNotFoundError(provider_id) from exc
        if not provider.enabled:
            return self.update_latency(provider_id, status=LLMLatencyStatus.INVALID, latency_ms=None)
        if provider.kind == LLMProviderKind.OPENAI_COMPATIBLE and not provider.api_key_ref:
            return self.update_latency(provider_id, status=LLMLatencyStatus.INVALID, latency_ms=None)
        headers: dict[str, str] = {}
        if provider.api_key_ref and secret_store is not None:
            try:
                headers["Authorization"] = f"Bearer {secret_store.get(provider.api_key_ref)}"
            except Exception:
                return self.update_latency(provider_id, status=LLMLatencyStatus.INVALID, latency_ms=None)
        try:
            started_at = time.perf_counter()
            response = httpx.get(_latency_endpoint(provider), headers=headers, timeout=8, trust_env=False)
            response.raise_for_status()
            latency_ms = max(0, round((time.perf_counter() - started_at) * 1000))
            return self.update_latency(provider_id, status=LLMLatencyStatus.MEASURED, latency_ms=latency_ms)
        except Exception:
            # A timing probe is operational feedback, not a request failure
            # for the page.  Preserve the independently detected catalogue.
            return self.update_latency(provider_id, status=LLMLatencyStatus.UNREACHABLE, latency_ms=None)


def provider_api_view(provider: LLMProviderConfig) -> dict[str, Any]:
    return {
        "provider_id": provider.provider_id,
        "display_name": provider.display_name,
        "kind": provider.kind.value,
        "endpoint": provider.endpoint,
        "model": provider.model,
        "embedding_model": provider.embedding_model,
        "enabled": provider.enabled,
        "api_key_configured": bool(provider.api_key_ref),
        "health_status": provider.health_status.value,
        "available_models": provider.available_models,
        "available_chat_models": provider.available_chat_models,
        "available_embedding_models": provider.available_embedding_models,
        "health_message": provider.health_message,
        "last_checked_at": provider.last_checked_at,
        "latency_status": provider.latency_status.value,
        "latency_ms": provider.latency_ms,
        "last_latency_checked_at": provider.last_latency_checked_at,
    }


def binding_api_view(binding: LLMStageBinding) -> dict[str, Any]:
    return {
        "stage": binding.stage.value,
        "provider_id": binding.provider_id,
        "model": binding.model,
        "enabled": binding.enabled,
        "fallback_provider_id": binding.fallback_provider_id,
    }


def revision_api_view(revision: LLMConfigRevision) -> dict[str, Any]:
    return {
        "schema_version": revision.schema_version,
        "revision_id": revision.revision_id,
        "config_version": revision.config_version,
        "created_at": revision.created_at,
        "actor": revision.actor,
        "reason": revision.reason,
        "parent_revision_id": revision.parent_revision_id,
        "config_digest": revision.config_digest,
        "providers": [provider_api_view(item) for item in revision.providers],
        "bindings": [binding_api_view(item) for item in revision.bindings],
    }
