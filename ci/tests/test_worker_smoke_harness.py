from __future__ import annotations

import importlib.util
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

import pytest
import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "run_worker_smoke.py"
SPEC = importlib.util.spec_from_file_location("run_worker_smoke", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeDocker:
    def __init__(self, logs: str = "") -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.log_output = logs

    def pull(self, image: str) -> None:
        self.calls.append(("pull", image))

    def start(self, spec: Any, image: str, token: str, run_id: str) -> str:
        self.calls.append(("start", spec.name, image, token, run_id))
        return "container-id"

    def published_port(self, container_id: str) -> int:
        self.calls.append(("port", container_id))
        return 45123

    def logs(self, container_id: str) -> str:
        self.calls.append(("logs", container_id))
        return self.log_output

    def remove(self, container_id: str) -> None:
        self.calls.append(("remove", container_id))


class FakeClient:
    capabilities: ClassVar[dict[str, bool]] = {"answer": True}

    def __init__(
        self,
        spec: Any,
        *,
        prepared_capabilities: Mapping[str, Any] | None = None,
    ) -> None:
        self.spec = spec
        self.prepared_capabilities = prepared_capabilities or self.capabilities
        self.calls: list[str] = []

    def wait_for_handshake(self, timeout: float) -> Mapping[str, Any]:
        self.calls.append("handshake")
        return {
            "protocol_version": "1.0",
            "adapter_id": self.spec.adapter_id,
            "adapter_version": "0.1.0",
            "system_id": self.spec.system_id,
            "system_version": self.spec.system_version,
            "capabilities": dict(self.capabilities),
        }

    def prepare(self, config: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
        self.calls.append("prepare")
        return {
            "effective_config": dict(config),
            "capabilities": dict(self.prepared_capabilities),
            "system_version": self.spec.system_version,
        }

    def health(self, timeout: float = 5.0) -> Mapping[str, Any]:
        self.calls.append("health")
        return {"status": "ready", "ready": True, "details": {"prepared": True}}

    def close(self, timeout: float = 10.0) -> Mapping[str, Any]:
        self.calls.append("close")
        return {"closed": True}


@pytest.fixture
def lock_path() -> Path:
    return Path(__file__).resolve().parents[1] / "worker-runtime-lock.yaml"


@pytest.mark.parametrize("worker", ["lightrag", "rag-anything"])
def test_runtime_lock_uses_full_source_and_image_pins(
    lock_path: Path, worker: str
) -> None:
    spec = MODULE.load_worker_spec(lock_path, worker)
    assert len(spec.source_revision) == 40
    assert spec.locked_image == f"{spec.image_repository}@{spec.image_digest}"
    assert spec.image_platform == "linux/arm64"
    assert spec.source_repository.startswith("https://github.com/")
    assert spec.source_tag


def test_mutable_image_reference_is_rejected(tmp_path: Path, lock_path: Path) -> None:
    value = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    value["workers"]["lightrag"]["image"]["repository"] += ":latest"
    candidate = tmp_path / "worker-lock.yaml"
    candidate.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    with pytest.raises(MODULE.SmokeError, match="mutable tag"):
        MODULE.load_worker_spec(candidate, "lightrag")


def test_docker_command_has_ephemeral_loopback_and_tmpfs(lock_path: Path) -> None:
    spec = MODULE.load_worker_spec(lock_path, "lightrag")
    arguments = MODULE.docker_run_arguments(
        spec, "candidate:local", "secret-token", "run-id", "safe-name"
    )
    assert f"127.0.0.1::{MODULE.CONTAINER_PORT}" in arguments
    assert arguments.count("--tmpfs") == 2
    assert "RAG_EVAL_WORKER_ALLOW_CONTAINER_BIND=1" in arguments
    assert "RAG_EVAL_WORKER_TOKEN=secret-token" in arguments
    assert "--adapter-factory" in arguments
    assert "OLLAMA_HOST" not in " ".join(arguments)


def test_lifecycle_passes_and_always_removes_container(lock_path: Path) -> None:
    spec = MODULE.load_worker_spec(lock_path, "lightrag")
    docker = FakeDocker()
    client = FakeClient(spec)
    result = MODULE.run_smoke(
        spec,
        image="candidate:local",
        pull=False,
        startup_timeout=1,
        docker=docker,
        client_factory=lambda *_: client,
    )
    assert result["result"] == "PASS"
    assert client.calls == ["handshake", "prepare", "health", "close"]
    assert docker.calls[-1] == ("remove", "container-id")


def test_capability_mismatch_fails_with_stage_and_cleanup(lock_path: Path) -> None:
    spec = MODULE.load_worker_spec(lock_path, "lightrag")
    docker = FakeDocker()
    client = FakeClient(spec, prepared_capabilities={"answer": False})
    with pytest.raises(MODULE.SmokeError, match="during prepare"):
        MODULE.run_smoke(
            spec,
            image="candidate:local",
            pull=False,
            startup_timeout=1,
            docker=docker,
            client_factory=lambda *_: client,
        )
    assert docker.calls[-1] == ("remove", "container-id")


def test_failure_log_redacts_token(lock_path: Path) -> None:
    spec = MODULE.load_worker_spec(lock_path, "lightrag")
    docker = FakeDocker()

    class FailingClient(FakeClient):
        def wait_for_handshake(self, timeout: float) -> Mapping[str, Any]:
            token = next(call[3] for call in docker.calls if call[0] == "start")
            docker.log_output = f"Authorization: Bearer {token}"
            raise MODULE.SmokeError("unavailable")

    with pytest.raises(MODULE.SmokeError) as captured:
        MODULE.run_smoke(
            spec,
            image="candidate:local",
            pull=False,
            startup_timeout=1,
            docker=docker,
            client_factory=lambda *_: FailingClient(spec),
        )
    assert "<redacted>" in str(captured.value)
    token = next(call[3] for call in docker.calls if call[0] == "start")
    assert token not in str(captured.value)


def test_pull_is_explicit_and_precedes_start(lock_path: Path) -> None:
    spec = MODULE.load_worker_spec(lock_path, "rag-anything")
    docker = FakeDocker()
    client = FakeClient(spec)
    MODULE.run_smoke(
        spec,
        image=spec.locked_image,
        pull=True,
        startup_timeout=1,
        docker=docker,
        client_factory=lambda *_: client,
    )
    assert docker.calls[0] == ("pull", spec.locked_image)
    assert docker.calls[1][0] == "start"


def test_print_locked_image_does_not_invoke_docker(
    lock_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = MODULE.main(
        [
            "--worker",
            "lightrag",
            "--lock",
            str(lock_path),
            "--print-locked-image",
            "--docker",
            "definitely-not-a-real-docker-command",
        ]
    )
    assert result == 0
    assert (
        capsys.readouterr()
        .out.strip()
        .endswith(
            "@sha256:c1b5391b0a113a54a9c9773b70fcab466ae295da97f3866a74b4e66de5c93a94"
        )
    )
