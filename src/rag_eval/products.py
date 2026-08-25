"""Editable product-layer resources that compile into frozen research contracts.

Nothing in this module changes Bundle, ExperimentSpec, Worker Wire, scoring, or
replay semantics.  It deliberately stores drafts outside immutable artifact
directories so the product layer can be switched off without affecting CLI use.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.contracts.run import ExperimentSpec
from rag_eval.datasets.bundle import case_selection_id
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.runs import safe_id


class ProductModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductMode(StrEnum):
    BASIC = "basic"
    ADVANCED = "advanced"


class SystemProfile(ProductModel):
    """An immutable, versioned set of fully declarative product defaults."""

    profile_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    profile_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    display_name: str = Field(min_length=1)
    system_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    adapter_factory: str = Field(pattern=r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")
    defaults: dict[str, dict[str, Any]]
    default_logical_endpoint: str = "ollama.local"
    docker_image: str | None = None

    @model_validator(mode="after")
    def validate_defaults(self) -> SystemProfile:
        if set(self.defaults) != {"adapter_config", "query_config", "metric_config"}:
            raise ValueError("profile defaults must contain adapter_config, query_config, metric_config")
        return self


def builtin_profiles() -> tuple[SystemProfile, ...]:
    """Stable profile versions. Changing defaults requires a new version entry."""
    common_metrics = {"k_values": [1, 3, 5]}
    return (
        SystemProfile(
            profile_id="lightrag",
            profile_version="1.0.0",
            display_name="LightRAG",
            system_id="lightrag",
            adapter_id="lightrag",
            adapter_factory="rag_eval_lightrag_adapter.adapter:create_worker_definition",
            defaults={
                "adapter_config": {
                    "profile": "legacy",
                    "query_mode": "naive",
                    "retrieval_candidate_k": 20,
                    "final_context_k": 5,
                    "max_context_tokens": 12000,
                    "model": {"llm_binding": "ollama", "embedding_binding": "ollama"},
                    "generation": {},
                },
                "query_config": {
                    "generate_answer": True,
                    "retrieval_candidate_k": 20,
                    "final_context_k": 5,
                    "max_context_tokens": 12000,
                    "generation_options": {},
                },
                "metric_config": common_metrics,
            },
            docker_image="rag-eval-adapter-lightrag:0.1.0",
        ),
        # Retain 1.0.0 for already-saved connections and drafts.  New Basic
        # configurations bind model identities through this immutable profile
        # rather than allowing an upstream LightRAG default to leak in.
        SystemProfile(
            profile_id="lightrag",
            profile_version="1.0.1",
            display_name="LightRAG",
            system_id="lightrag",
            adapter_id="lightrag",
            adapter_factory="rag_eval_lightrag_adapter.adapter:create_worker_definition",
            defaults={
                "adapter_config": {
                    "profile": "legacy",
                    "query_mode": "naive",
                    "retrieval_candidate_k": 20,
                    "final_context_k": 5,
                    "max_context_tokens": 12000,
                    "model": {
                        "llm_binding": "ollama",
                        "embedding_binding": "ollama",
                        "llm_model": "qwen3:4b-instruct",
                        "embedding_model": "bge-m3:latest",
                    },
                    "generation": {},
                },
                "query_config": {
                    "generate_answer": True,
                    "retrieval_candidate_k": 20,
                    "final_context_k": 5,
                    "max_context_tokens": 12000,
                    "generation_options": {},
                },
                "metric_config": common_metrics,
            },
            docker_image="rag-eval-adapter-lightrag:0.1.0",
        ),
        SystemProfile(
            profile_id="rag-anything",
            profile_version="1.0.0",
            display_name="RAG-Anything",
            system_id="rag-anything",
            adapter_id="rag-anything",
            adapter_factory="rag_eval_rag_anything_adapter.adapter:create_worker_definition",
            defaults={
                "adapter_config": {
                    "parser": "mineru",
                    "parse_method": "txt",
                    "query_mode": "mix",
                    "chunk_top_k": 20,
                    "max_context_tokens": 12000,
                    "model": {
                        "binding": "ollama",
                        "llm_model": "qwen3:4b-instruct",
                        "embedding_model": "bge-m3:latest",
                    },
                    "generation": {},
                },
                "query_config": {
                    "generate_answer": True,
                    "retrieval_candidate_k": 20,
                    "final_context_k": 5,
                    "max_context_tokens": 12000,
                    "generation_options": {},
                },
                "metric_config": common_metrics,
            },
            docker_image="rag-eval-adapter-rag-anything:0.1.0",
        ),
        # The product dataset authoring path is UTF-8 text/Markdown only in
        # this release.  Keep the historical multimedia-capable profile, and
        # add a separate text-safe version instead of silently changing it.
        SystemProfile(
            profile_id="rag-anything",
            profile_version="1.0.1",
            display_name="RAG-Anything",
            system_id="rag-anything",
            adapter_id="rag-anything",
            adapter_factory="rag_eval_rag_anything_adapter.adapter:create_worker_definition",
            defaults={
                "adapter_config": {
                    "parser": "mineru",
                    "parse_method": "txt",
                    "query_mode": "naive",
                    "chunking": {
                        "chunk_token_size": 120,
                        "chunk_overlap_token_size": 20,
                    },
                    "top_k": 3,
                    "chunk_top_k": 1,
                    "max_context_tokens": 2000,
                    "enable_image_processing": False,
                    "enable_table_processing": False,
                    "enable_equation_processing": False,
                    "model": {
                        "binding": "ollama",
                        "llm_model": "qwen3:4b-instruct",
                        "embedding_model": "bge-m3:latest",
                    },
                    "generation": {},
                },
                "query_config": {
                    "generate_answer": True,
                    "retrieval_candidate_k": 3,
                    "final_context_k": 1,
                    "max_context_tokens": 2000,
                    "generation_options": {},
                },
                "metric_config": common_metrics,
            },
            docker_image="rag-eval-adapter-rag-anything:0.1.0",
        ),
    )


class SystemProfileRegistry:
    def __init__(self) -> None:
        self._profiles = {(item.profile_id, item.profile_version): item for item in builtin_profiles()}

    def list(self) -> list[SystemProfile]:
        return list(sorted(self._profiles.values(), key=lambda item: (item.display_name, item.profile_version)))

    def get(self, profile_id: str, profile_version: str) -> SystemProfile:
        try:
            return self._profiles[(profile_id, profile_version)]
        except KeyError as exc:
            raise FileNotFoundError(f"unknown system profile {profile_id}@{profile_version}") from exc


class SystemConnection(ProductModel):
    system_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    profile_id: str
    profile_version: str
    execution_provider: Literal["local", "docker"] = "local"
    logical_endpoint_ref: str = "ollama.local"
    python_executable: str = Field(default_factory=lambda: sys.executable)
    non_secret_environment: dict[str, str] = Field(default_factory=dict)
    secret_bindings: dict[str, str] = Field(default_factory=dict)
    adapter_overrides: dict[str, Any] = Field(default_factory=dict)
    query_overrides: dict[str, Any] = Field(default_factory=dict)
    metric_overrides: dict[str, Any] = Field(default_factory=dict)
    # Fresh Docker indexes for real models can legitimately take longer than
    # the per-case request timeout.  Existing saved connections retain their
    # value; this is the conservative default for newly created product ones.
    request_timeout_seconds: float = Field(default=600.0, gt=0)
    connection_test_status: Literal["not_tested", "passed", "failed"] = "not_tested"
    last_connection_tested_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvaluationDraft(ProductModel):
    draft_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    mode: ProductMode = ProductMode.BASIC
    bundle_id: str | None = None
    system_id: str | None = None
    profile_id: str | None = None
    profile_version: str | None = None
    display_name: str = ""
    adapter_overrides: dict[str, Any] = Field(default_factory=dict)
    query_overrides: dict[str, Any] = Field(default_factory=dict)
    metric_overrides: dict[str, Any] = Field(default_factory=dict)
    case_ids: list[str] | None = None
    seed: int = 0
    repetitions: int = Field(default=1, ge=1)
    formal: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(base))
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def canonical_experiment(
    draft: EvaluationDraft,
    connection: SystemConnection,
    profile: SystemProfile,
    *,
    case_ids: list[str],
) -> ExperimentSpec:
    if draft.profile_id != connection.profile_id or draft.profile_version != connection.profile_version:
        raise ValueError("evaluation draft and system connection profile versions differ")
    if connection.system_id != profile.system_id or connection.profile_id != profile.profile_id:
        raise ValueError("system connection does not match selected profile")
    if draft.formal:
        raise ValueError("formal experiments must be created in Advanced with frozen research artifacts")
    adapter = deep_merge(profile.defaults["adapter_config"], connection.adapter_overrides)
    adapter = deep_merge(adapter, draft.adapter_overrides)
    query = deep_merge(profile.defaults["query_config"], connection.query_overrides)
    query = deep_merge(query, draft.query_overrides)
    metrics = deep_merge(profile.defaults["metric_config"], connection.metric_overrides)
    metrics = deep_merge(metrics, draft.metric_overrides)
    _require_explicit_model_identities(adapter)
    selected = sorted(case_ids if draft.case_ids is None else draft.case_ids)
    policy = "all" if draft.case_ids is None else "explicit"
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "profile_id": profile.profile_id,
                "profile_version": profile.profile_version,
                "bundle_id": draft.bundle_id,
                "system_id": connection.system_id,
                "seed": draft.seed,
                "selected": selected,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", draft.display_name.strip()).strip("-") or "evaluation"
    return ExperimentSpec(
        experiment_id=f"{name}-{fingerprint}",
        bundle_id=draft.bundle_id or "",
        system_id=connection.system_id,
        adapter_id=profile.adapter_id,
        adapter_config=adapter,
        query_config=query,
        metric_config=metrics,
        case_ids=draft.case_ids,
        case_selection_id=case_selection_id(selected, policy=policy, seed=draft.seed),
        seed=draft.seed,
        repetitions=draft.repetitions,
    )


def _require_explicit_model_identities(adapter_config: dict[str, Any]) -> None:
    """Reject product drafts that would otherwise use an upstream model default."""
    model = adapter_config.get("model")
    if not isinstance(model, dict):
        raise ValueError("generation model and embedding model are required")
    missing = [
        label
        for key, label in (("llm_model", "generation model"), ("embedding_model", "embedding model"))
        if not isinstance(model.get(key), str) or not model[key].strip()
    ]
    if missing:
        raise ValueError(f"missing required {', '.join(missing)}")


class JsonProductStore:
    def __init__(self, root: Path, model: type[ProductModel]) -> None:
        self.root = root
        self.model = model
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, item: ProductModel, identifier: str) -> ProductModel:
        atomic_write_json(self.root / f"{safe_id(identifier)}.json", item.model_dump(mode="json"))
        return item

    def get(self, identifier: str) -> ProductModel:
        return self.model.model_validate_json((self.root / f"{safe_id(identifier)}.json").read_text(encoding="utf-8"))

    def list(self) -> list[ProductModel]:
        return [self.model.model_validate_json(item.read_text(encoding="utf-8")) for item in sorted(self.root.glob("*.json"))]


class ProductResources:
    def __init__(self, *, drafts: Path, connections: Path) -> None:
        self.drafts = JsonProductStore(drafts, EvaluationDraft)
        self.connections = JsonProductStore(connections, SystemConnection)
        self.profiles = SystemProfileRegistry()

    def save_draft(self, draft: EvaluationDraft) -> EvaluationDraft:
        return self.drafts.save(draft.model_copy(update={"updated_at": datetime.now(UTC)}), draft.draft_id)  # type: ignore[return-value]

    def get_draft(self, draft_id: str) -> EvaluationDraft:
        return self.drafts.get(draft_id)  # type: ignore[return-value]

    def save_connection(self, connection: SystemConnection) -> SystemConnection:
        return self.connections.save(connection.model_copy(update={"updated_at": datetime.now(UTC)}), connection.system_id)  # type: ignore[return-value]

    def get_connection(self, system_id: str) -> SystemConnection:
        return self.connections.get(system_id)  # type: ignore[return-value]
