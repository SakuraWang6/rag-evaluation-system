"""Provider boundary for isolated Adapter Workers.

The executor owns Wire Protocol calls and evaluation semantics. Providers own
only physical process/container lifecycle and path/endpoint resolution.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import secrets
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from rag_eval.contracts.adapter import PrepareContext
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.worker.client import WorkerClient
from rag_eval.worker.process import WorkerCommand, WorkerProcess, reserve_loopback_port


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    command: WorkerCommand
    run_id: str
    log_path: Path
    source_dir: Path
    work_dir: Path


class WorkerHandle(Protocol):
    client: WorkerClient
    worker_pid: int | None
    handle_id: str | None
    launch_metadata: dict[str, object]

    def prepare_context(self, context: PrepareContext) -> PrepareContext: ...
    def stop(self) -> None: ...
    def cancel(self) -> bool: ...


class ExecutionProvider(Protocol):
    name: str

    def start(self, request: ExecutionRequest) -> WorkerHandle: ...
    def terminate(self, handle_id: str) -> bool: ...


@dataclass(slots=True)
class LocalWorkerHandle:
    process: WorkerProcess
    client: WorkerClient
    worker_pid: int | None
    work_dir: Path | None = None
    handle_id: str | None = None
    launch_metadata: dict[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.launch_metadata is None:
            self.launch_metadata = {"provider": "local", "resolver_strategy": "loopback_process"}

    def prepare_context(self, context: PrepareContext) -> PrepareContext:
        return context

    def stop(self) -> None:
        self.process.stop()

    def cancel(self) -> bool:
        confirmed = self.process.cancel()
        if self.work_dir is not None:
            record_cancelled_liveness(self.work_dir, confirmed=confirmed)
        return confirmed


class LocalProcessProvider:
    name = "local"

    def start(self, request: ExecutionRequest) -> LocalWorkerHandle:
        process = WorkerProcess(request.command, run_id=request.run_id, log_path=request.log_path)
        client = process.start()
        return LocalWorkerHandle(
            process=process,
            client=client,
            worker_pid=process.process.pid if process.process is not None else None,
            work_dir=request.work_dir,
        )

    def terminate(self, handle_id: str) -> bool:
        return False


def runtime_endpoint(logical_ref: str, provider_name: str) -> tuple[str, dict[str, object]]:
    """Resolve only at launch; ExperimentSpec retains no physical endpoint."""
    if logical_ref == "ollama.local":
        endpoint = "http://host.docker.internal:11434" if provider_name == "docker" else "http://127.0.0.1:11434"
        strategy = "docker-host-bridge" if provider_name == "docker" else "local-loopback"
    else:
        key = "RAG_EVAL_LOGICAL_ENDPOINT_" + "".join(char if char.isalnum() else "_" for char in logical_ref.upper())
        endpoint = os.environ.get(key)
        if not endpoint:
            raise ValueError(f"logical endpoint {logical_ref!r} is not configured")
        strategy = "explicit-logical-endpoint"
    return endpoint, {
        "logical_endpoint_ref": logical_ref,
        "resolver_strategy": strategy,
        "effective_endpoint_identity_digest": "sha256:" + hashlib.sha256(endpoint.encode("utf-8")).hexdigest(),
    }


@dataclass(slots=True)
class DockerWorkerHandle:
    container_id: str
    client: WorkerClient
    worker_pid: int | None
    launch_metadata: dict[str, object]
    host_source: Path
    host_work: Path
    runtime_endpoints: tuple[str, ...] = ()

    @property
    def handle_id(self) -> str:
        return self.container_id

    def prepare_context(self, context: PrepareContext) -> PrepareContext:
        return context.model_copy(
            update={
                "source_dir": "/rag-eval/source",
                "work_dir": "/rag-eval/work",
            }
        )

    def stop(self) -> None:
        try:
            # Give the Worker a chance to close its adapter before the
            # container is removed.  Besides graceful child shutdown this
            # lets adapters finalize and sanitize their run-scoped logs.
            self.client.close_adapter()
        except Exception:  # noqa: BLE001 - force-removal is the safe fallback
            pass
        finally:
            _docker(["rm", "--force", self.container_id], check=False)
            _redact_runtime_endpoint_logs(self.host_work, self.runtime_endpoints)
            self.client.close()

    def cancel(self) -> bool:
        result = _docker(["rm", "--force", self.container_id], check=False)
        confirmed = isinstance(result, subprocess.CompletedProcess) and result.returncode == 0
        record_cancelled_liveness(self.host_work, confirmed=confirmed)
        self.client.close()
        return confirmed


class DockerProvider:
    """Wire-compatible fresh-container provider; Docker is never imported by the executor."""

    name = "docker"

    def __init__(self, *, image_by_adapter: dict[str, str] | None = None) -> None:
        self.image_by_adapter = image_by_adapter or {
            "lightrag": "rag-eval-adapter-lightrag:0.1.0",
            "rag-anything": "rag-eval-adapter-rag-anything:0.1.0",
        }

    def start(self, request: ExecutionRequest) -> DockerWorkerHandle:
        if shutil.which("docker") is None:
            raise RuntimeError("DockerProvider requires the docker CLI")
        uid = getattr(os, "getuid", lambda: 10001)()
        gid = getattr(os, "getgid", lambda: 10001)()
        if uid == 0:
            raise RuntimeError("DockerProvider refuses to run an Adapter Worker as root")
        image = self.image_by_adapter.get(request.command.adapter_id)
        if not image:
            raise ValueError(f"no standard Docker image is configured for {request.command.adapter_id!r}")
        # A tag is a convenient product-level reference but may be retargeted
        # between preview and launch. Resolve it once, then launch the exact
        # local content-addressed image and record both identities.
        image_id = _docker(["image", "inspect", image, "--format", "{{.Id}}"]).strip()
        if not image_id.startswith("sha256:"):
            raise RuntimeError(f"DockerProvider could not resolve an immutable image ID for {image!r}")
        request.source_dir.mkdir(parents=True, exist_ok=True)
        request.work_dir.mkdir(parents=True, exist_ok=True)
        host_port = reserve_loopback_port()
        container_port = host_port
        token = secrets.token_urlsafe(32)
        name = f"rag-eval-{request.run_id}".replace("_", "-")[:63]
        argv = [
            "run", "--detach", "--rm", "--name", name,
            "--label", "rag-eval.managed=true",
            "--label", f"rag-eval.run_id={request.run_id}",
            "--user", f"{uid}:{gid}",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m",
            "--mount", f"type=bind,src={request.source_dir.resolve()},dst=/rag-eval/source,readonly",
            "--mount", f"type=bind,src={request.work_dir.resolve()},dst=/rag-eval/work",
            "-p", f"127.0.0.1:{host_port}:{container_port}",
            "-e", f"RAG_EVAL_WORKER_TOKEN={token}",
            "-e", "RAG_EVAL_WORKER_ALLOW_CONTAINER_BIND=1",
        ]
        if platform.system() != "Darwin":
            argv.extend(["--add-host", "host.docker.internal:host-gateway"])
        for key, value in sorted(request.command.environment.items()):
            argv.extend(["-e", f"{key}={value}"])
        argv.extend(
            [
                image_id,
                "--adapter-factory", request.command.adapter_factory,
                "--run-id", request.run_id,
                "--host", "0.0.0.0",
                "--port", str(container_port),
            ]
        )
        container_id = _docker(argv).strip()
        client = WorkerClient(
            f"http://127.0.0.1:{host_port}",
            token=token,
            run_id=request.run_id,
            timeout=request.command.request_timeout_seconds,
        )
        try:
            client.wait_for_handshake()
            inspect = json.loads(_docker(["inspect", container_id, "--format", "{{json .State}}"])).get("Pid")
            return DockerWorkerHandle(
                container_id=container_id,
                client=client,
                worker_pid=int(inspect) if isinstance(inspect, int) and inspect > 0 else None,
                host_source=request.source_dir,
                host_work=request.work_dir,
                runtime_endpoints=tuple(
                    value
                    for key, value in request.command.environment.items()
                    if key.endswith("_HOST") and value
                ),
                launch_metadata={
                    "provider": "docker",
                    "image": image_id,
                    "image_reference": image,
                    "image_identity": image_id,
                    "container_id_digest": "sha256:" + hashlib.sha256(container_id.encode()).hexdigest(),
                },
            )
        except Exception:
            client.close()
            _docker(["rm", "--force", container_id], check=False)
            raise

    def terminate(self, handle_id: str) -> bool:
        return _docker(["rm", "--force", handle_id], check=False).returncode == 0


class ExecutionProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ExecutionProvider] = {
            "local": LocalProcessProvider(),
            "docker": DockerProvider(),
        }

    def get(self, name: str) -> ExecutionProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise ValueError(f"unknown execution provider {name!r}") from exc


def _docker(arguments: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str] | str:
    result = subprocess.run(["docker", *arguments], check=False, capture_output=True, text=True, timeout=60)
    if check and result.returncode != 0:
        raise RuntimeError(f"docker {' '.join(arguments[:2])} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout if check else result


def _redact_runtime_endpoint_logs(directory: Path, values: tuple[str, ...]) -> None:
    """Ensure provider-owned work logs cannot retain launch-only endpoints."""
    if not directory.exists():
        return
    for path in directory.rglob("*.log"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for value in sorted(set(values), key=len, reverse=True):
            digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
            text = text.replace(value, f"[redacted endpoint sha256:{digest}]")
        path.write_text(text, encoding="utf-8")


def record_cancelled_liveness(work_dir: Path, *, confirmed: bool) -> None:
    """Finalize an adapter liveness record after its worker group has ended."""

    path = work_dir / "ingestion-liveness.json"
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return
    if not isinstance(payload, dict):
        return
    now = datetime.now(UTC).isoformat()
    payload.update(
        {
            "stage": "cancelled",
            "updated_at": now,
            "terminal": True,
            "cancellation_confirmed": confirmed,
            "details": {
                "event": "worker_process_group_terminated",
                "termination_confirmed": confirmed,
            },
        }
    )
    atomic_write_json(path, payload)
