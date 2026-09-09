"""Trusted local system/adapter registry."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from rag_eval.execution_provider import runtime_endpoint
from rag_eval.products import ProductResources, SystemConnection
from rag_eval.runs.plans import ResolvedSystemIdentityV2, digest_json
from rag_eval.secrets import SecretStore
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.ids import safe_id
from rag_eval.worker.process import WorkerCommand


class SystemRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    adapter_factory: str = Field(pattern=r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")
    python_executable: str = Field(min_length=1)
    environment: dict[str, str] = Field(default_factory=dict)
    request_timeout_seconds: float = Field(default=180.0, gt=0)
    description: str = ""

    def worker_command(self) -> WorkerCommand:
        return WorkerCommand(
            adapter_id=self.adapter_id,
            adapter_factory=self.adapter_factory,
            python_executable=self.python_executable,
            environment=self.environment,
            request_timeout_seconds=self.request_timeout_seconds,
        )


class SystemRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def register(self, registration: SystemRegistration) -> Path:
        executable = Path(registration.python_executable)
        if not executable.is_absolute() or not executable.is_file():
            raise ValueError("python_executable must be an existing absolute file")
        path = self.root / f"{safe_id(registration.system_id)}.json"
        atomic_write_json(path, registration.model_dump(mode="json"))
        return path

    def get(self, system_id: str) -> SystemRegistration:
        path = self.root / f"{safe_id(system_id)}.json"
        return SystemRegistration.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[SystemRegistration]:
        return [
            SystemRegistration.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.root.glob("*.json"))
        ]


class ResolvedSystem:
    """Ephemeral launch data. It is never persisted with secret values."""

    def __init__(
        self,
        command: WorkerCommand,
        *,
        provider: str,
        execution_metadata: dict[str, object],
    ) -> None:
        self.command = command
        self.provider = provider
        self.execution_metadata = execution_metadata


class SystemResolver:
    """Resolves product connections first, then retains every legacy registration."""

    def __init__(
        self,
        legacy: SystemRegistry,
        products: ProductResources | None = None,
        secrets: SecretStore | None = None,
    ) -> None:
        self.legacy = legacy
        self.products = products
        self.secrets = secrets

    def resolve(self, system_id: str, *, provider: str | None = None) -> ResolvedSystem:
        if self.products is not None:
            try:
                connection = self.products.get_connection(system_id)
            except FileNotFoundError:
                connection = None
            if connection is not None:
                return self._resolve_connection(connection, provider=provider)
        registration = self.legacy.get(system_id)
        return ResolvedSystem(
            registration.worker_command(),
            provider="local",
            execution_metadata={"provider": "local", "system_source": "legacy_registration"},
        )

    def exists(self, system_id: str) -> bool:
        if self.products is not None:
            try:
                self.products.get_connection(system_id)
                return True
            except FileNotFoundError:
                pass
        try:
            self.legacy.get(system_id)
            return True
        except FileNotFoundError:
            return False

    def plan_identity(
        self,
        system_id: str,
        *,
        expected_adapter_id: str,
        provider: str | None = None,
    ) -> ResolvedSystemIdentityV2:
        """Resolve a secret-free, reproducible identity before queue admission."""

        if self.products is not None:
            try:
                connection = self.products.get_connection(system_id)
            except FileNotFoundError:
                connection = None
            if connection is not None:
                profile = self.products.profiles.get(
                    connection.profile_id, connection.profile_version
                )
                if connection.system_id != profile.system_id:
                    raise ValueError(
                        "system connection does not match its worker profile"
                    )
                selected_provider = provider or connection.execution_provider
                if selected_provider != connection.execution_provider:
                    raise ValueError(
                        "execution provider must match the selected system connection"
                    )
                if profile.adapter_id != expected_adapter_id:
                    raise ValueError(
                        "Experiment adapter_id does not match the selected worker profile"
                    )
                secret_digests: dict[str, str] = {}
                if connection.secret_bindings:
                    if self.secrets is None:
                        raise ValueError("secret storage is unavailable")
                    for environment_key, reference in sorted(
                        connection.secret_bindings.items()
                    ):
                        secret = self.secrets.get(reference)
                        secret_digests[environment_key] = _private_value_digest(
                            reference, secret
                        )
                config_identity = {
                    "system_id": connection.system_id,
                    "profile_id": connection.profile_id,
                    "profile_version": connection.profile_version,
                    "execution_provider": selected_provider,
                    "logical_endpoint_ref": connection.logical_endpoint_ref,
                    "python_executable": connection.python_executable,
                    "non_secret_environment": connection.non_secret_environment,
                    "secret_binding_digests": secret_digests,
                    "adapter_overrides": connection.adapter_overrides,
                    "query_overrides": connection.query_overrides,
                    "metric_overrides": connection.metric_overrides,
                    "request_timeout_seconds": connection.request_timeout_seconds,
                }
                return ResolvedSystemIdentityV2(
                    system_id=connection.system_id,
                    adapter_id=profile.adapter_id,
                    adapter_factory=profile.adapter_factory,
                    worker_profile_kind="product_profile",
                    worker_profile_id=profile.profile_id,
                    worker_profile_version=profile.profile_version,
                    worker_profile_digest=digest_json(
                        profile.model_dump(mode="json")
                    ),
                    system_config_digest=digest_json(config_identity),
                    execution_provider=selected_provider,
                    worker_request_timeout_seconds=connection.request_timeout_seconds,
                )

        registration = self.legacy.get(system_id)
        selected_provider = provider or "local"
        if selected_provider != "local":
            raise ValueError("registered systems support only the local provider")
        if registration.adapter_id != expected_adapter_id:
            raise ValueError(
                "Experiment adapter_id does not match the registered worker profile"
            )
        environment_digests = {
            key: _private_value_digest(key, value)
            for key, value in sorted(registration.environment.items())
        }
        profile_identity = {
            "system_id": registration.system_id,
            "adapter_id": registration.adapter_id,
            "adapter_factory": registration.adapter_factory,
        }
        config_identity = {
            **profile_identity,
            "python_executable": registration.python_executable,
            "environment_digests": environment_digests,
            "request_timeout_seconds": registration.request_timeout_seconds,
            "execution_provider": selected_provider,
        }
        return ResolvedSystemIdentityV2(
            system_id=registration.system_id,
            adapter_id=registration.adapter_id,
            adapter_factory=registration.adapter_factory,
            worker_profile_kind="registered_system",
            worker_profile_id=f"registered-{registration.system_id}",
            worker_profile_version="unversioned",
            worker_profile_digest=digest_json(profile_identity),
            system_config_digest=digest_json(config_identity),
            execution_provider=selected_provider,
            worker_request_timeout_seconds=registration.request_timeout_seconds,
        )

    def _resolve_connection(
        self, connection: SystemConnection, *, provider: str | None
    ) -> ResolvedSystem:
        if self.products is None:
            raise RuntimeError("product resources are disabled")
        profile = self.products.profiles.get(connection.profile_id, connection.profile_version)
        selected_provider = provider or connection.execution_provider
        endpoint, endpoint_metadata = runtime_endpoint(
            connection.logical_endpoint_ref, selected_provider
        )
        environment = dict(connection.non_secret_environment)
        if selected_provider == "local":
            runtime_sources = _local_standard_runtime_sources(profile.profile_id)
            if runtime_sources:
                existing = environment.get("PYTHONPATH", "")
                environment.setdefault(
                    "PYTHONPATH",
                    os.pathsep.join([*runtime_sources, *( [existing] if existing else [])]),
                )
        environment.setdefault("OLLAMA_HOST", endpoint)
        # Standard Adapter profiles may delegate to an upstream server whose
        # binding-specific host variables are distinct from OLLAMA_HOST.
        # These are launch-only values resolved by the Provider, never Spec
        # fields or persisted raw endpoint artifacts.
        environment.setdefault("LLM_BINDING_HOST", endpoint)
        environment.setdefault("QUERY_LLM_BINDING_HOST", endpoint)
        environment.setdefault("EMBEDDING_BINDING_HOST", endpoint)
        if connection.secret_bindings:
            if self.secrets is None:
                raise RuntimeError("secret storage is unavailable")
            for environment_key, reference in connection.secret_bindings.items():
                environment[environment_key] = self.secrets.get(reference)
        return ResolvedSystem(
            WorkerCommand(
                adapter_id=profile.adapter_id,
                adapter_factory=profile.adapter_factory,
                python_executable=connection.python_executable,
                environment=environment,
                request_timeout_seconds=connection.request_timeout_seconds,
            ),
            provider=selected_provider,
            execution_metadata={
                "provider": selected_provider,
                "system_source": "product_connection",
                "profile_id": profile.profile_id,
                "profile_version": profile.profile_version,
                **endpoint_metadata,
            },
        )


def _local_standard_runtime_sources(profile_id: str) -> tuple[str, ...]:
    """Prefer checked-out standard adapter sources for isolated local Workers.

    Dedicated virtual environments may retain a historical editable checkout.
    Product connections stay provider-neutral, but a local Standard Profile must
    execute the current Platform/Adapter sources.  Docker images contain their
    own sources and intentionally never receive host paths.
    """
    monorepo = Path(__file__).resolve().parents[3]
    adapter_directory = {
        "lightrag": "lightrag",
        "rag-anything": "rag-anything",
    }.get(profile_id)
    if adapter_directory is None:
        return ()
    adapter_source = monorepo / "adapters" / adapter_directory / "src"
    platform_source = monorepo / "platform" / "src"
    if adapter_source.is_dir() and platform_source.is_dir():
        return (str(platform_source), str(adapter_source))
    return ()


def _private_value_digest(label: str, value: str) -> str:
    """Bind mutable secret/environment values without persisting their content."""

    return "sha256:" + hashlib.sha256(f"{label}\0{value}".encode()).hexdigest()
