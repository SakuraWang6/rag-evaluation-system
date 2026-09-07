#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""Run a model-free lifecycle smoke test against an actual Adapter Worker image."""

from __future__ import annotations

import argparse
import json
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PROTOCOL_VERSION = "1.0"
CONTAINER_PORT = 8765


class SmokeError(RuntimeError):
    """A lifecycle stage did not satisfy the required Worker contract."""


def _mapping(value: Any, subject: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SmokeError(f"{subject} must be a mapping")
    return value


def _text(value: Any, subject: str) -> str:
    if not isinstance(value, str) or not value:
        raise SmokeError(f"{subject} must be a non-empty string")
    return value


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    adapter_factory: str
    adapter_id: str
    system_id: str
    system_version: str
    source_repository: str
    source_tag: str
    source_revision: str
    image_repository: str
    image_digest: str
    image_platform: str
    prepare_timeout_seconds: float
    prepare_config: dict[str, Any]

    @property
    def locked_image(self) -> str:
        return f"{self.image_repository}@{self.image_digest}"


def load_worker_spec(lock_path: Path, worker: str) -> WorkerSpec:
    try:
        loaded = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SmokeError(f"cannot load Worker runtime lock {lock_path}: {exc}") from exc
    root = _mapping(loaded, "Worker runtime lock")
    if root.get("schema_version") != 1:
        raise SmokeError("unsupported Worker runtime lock schema")
    if root.get("protocol_version") != PROTOCOL_VERSION:
        raise SmokeError("Worker runtime lock protocol does not match the harness")
    workers = _mapping(root.get("workers"), "workers")
    if worker not in workers:
        raise SmokeError(
            f"unknown Worker {worker!r}; choose one of {sorted(workers)!r}"
        )
    value = _mapping(workers[worker], f"workers.{worker}")
    identity = _mapping(
        value.get("expected_identity"), f"workers.{worker}.expected_identity"
    )
    source = _mapping(value.get("source"), f"workers.{worker}.source")
    image = _mapping(value.get("image"), f"workers.{worker}.image")
    prepare = _mapping(value.get("prepare"), f"workers.{worker}.prepare")

    source_revision = _text(source.get("revision"), "source.revision")
    if not FULL_SHA_RE.fullmatch(source_revision):
        raise SmokeError("source.revision must be a full lowercase 40-character SHA")
    image_digest = _text(image.get("digest"), "image.digest")
    if not DIGEST_RE.fullmatch(image_digest):
        raise SmokeError("image.digest must be an immutable sha256 digest")
    image_repository = _text(image.get("repository"), "image.repository")
    if "@" in image_repository or image_repository.rsplit("/", 1)[-1].count(":"):
        raise SmokeError("image.repository must not contain a mutable tag or digest")
    config = prepare.get("config")
    if not isinstance(config, dict):
        raise SmokeError("prepare.config must be a mapping")
    timeout = prepare.get("timeout_seconds")
    if (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or timeout <= 0
    ):
        raise SmokeError("prepare.timeout_seconds must be positive")
    return WorkerSpec(
        name=worker,
        adapter_factory=_text(value.get("adapter_factory"), "adapter_factory"),
        adapter_id=_text(identity.get("adapter_id"), "expected_identity.adapter_id"),
        system_id=_text(identity.get("system_id"), "expected_identity.system_id"),
        system_version=_text(
            identity.get("system_version"), "expected_identity.system_version"
        ),
        source_repository=_text(source.get("repository"), "source.repository"),
        source_tag=_text(source.get("tag"), "source.tag"),
        source_revision=source_revision,
        image_repository=image_repository,
        image_digest=image_digest,
        image_platform=_text(image.get("platform"), "image.platform"),
        prepare_timeout_seconds=float(timeout),
        prepare_config=dict(config),
    )


def redact(text: str, secrets_to_hide: Sequence[str]) -> str:
    result = text
    for secret in sorted(
        (item for item in secrets_to_hide if item), key=len, reverse=True
    ):
        result = result.replace(secret, "<redacted>")
    return result


class DockerRuntime(Protocol):
    def pull(self, image: str) -> None: ...

    def start(self, spec: WorkerSpec, image: str, token: str, run_id: str) -> str: ...

    def published_port(self, container_id: str) -> int: ...

    def logs(self, container_id: str) -> str: ...

    def remove(self, container_id: str) -> None: ...


def docker_run_arguments(
    spec: WorkerSpec,
    image: str,
    token: str,
    run_id: str,
    container_name: str,
) -> list[str]:
    return [
        "run",
        "--detach",
        "--rm",
        "--name",
        container_name,
        "--publish",
        f"127.0.0.1::{CONTAINER_PORT}",
        "--env",
        f"RAG_EVAL_WORKER_TOKEN={token}",
        "--env",
        "RAG_EVAL_WORKER_ALLOW_CONTAINER_BIND=1",
        "--tmpfs",
        "/run/rag-eval-work:rw,uid=10001,gid=10001,mode=0700",
        "--tmpfs",
        "/run/rag-eval-source:rw,uid=10001,gid=10001,mode=0700",
        image,
        "--adapter-factory",
        spec.adapter_factory,
        "--run-id",
        run_id,
        "--host",
        "0.0.0.0",
        "--port",
        str(CONTAINER_PORT),
    ]


class DockerCli:
    def __init__(
        self,
        executable: str = "docker",
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.executable = executable
        self._runner = runner

    def _run(
        self, *arguments: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = self._runner(
                [self.executable, *arguments],
                check=False,
                text=True,
                capture_output=True,
            )
        except OSError as exc:
            raise SmokeError(f"cannot execute Docker: {exc}") from exc
        if check and result.returncode != 0:
            detail = (
                result.stderr.strip() or result.stdout.strip() or "unknown Docker error"
            )
            raise SmokeError(f"Docker {' '.join(arguments[:2])} failed: {detail}")
        return result

    def pull(self, image: str) -> None:
        self._run("pull", image)

    def image_exists(self, image: str) -> bool:
        return self._run("image", "inspect", image, check=False).returncode == 0

    def start(self, spec: WorkerSpec, image: str, token: str, run_id: str) -> str:
        suffix = secrets.token_hex(4)
        name = f"rag-eval-smoke-{spec.name}-{suffix}"
        if not SAFE_NAME_RE.fullmatch(name):
            raise SmokeError(f"unsafe generated container name: {name}")
        result = self._run(*docker_run_arguments(spec, image, token, run_id, name))
        container_id = result.stdout.strip()
        if not container_id:
            raise SmokeError("Docker did not return a container ID")
        return container_id

    def published_port(self, container_id: str) -> int:
        result = self._run("port", container_id, f"{CONTAINER_PORT}/tcp")
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if len(lines) != 1:
            raise SmokeError(f"unexpected Docker port output: {lines!r}")
        _, separator, port_text = lines[0].rpartition(":")
        if not separator or not port_text.isdecimal():
            raise SmokeError(f"cannot parse Docker port output: {lines[0]!r}")
        port = int(port_text)
        if not 1 <= port <= 65535:
            raise SmokeError(f"published Docker port is invalid: {port}")
        return port

    def logs(self, container_id: str) -> str:
        result = self._run("logs", container_id, check=False)
        return result.stdout + result.stderr

    def remove(self, container_id: str) -> None:
        self._run("rm", "--force", container_id, check=False)


class WorkerHttpClient:
    def __init__(self, base_url: str, token: str, run_id: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.run_id = run_id

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        timeout: float,
    ) -> Mapping[str, Any]:
        body = None
        headers = {"Authorization": f"Bearer {self.token}"}
        if payload is not None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SmokeError(f"HTTP {exc.code} from {path}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SmokeError(f"request to {path} failed: {exc}") from exc
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise SmokeError(f"non-JSON response from {path}") from exc
        return _mapping(parsed, f"response from {path}")

    def wait_for_handshake(self, timeout: float) -> Mapping[str, Any]:
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                return self._request("GET", "/handshake", timeout=2.0)
            except SmokeError as exc:
                last_error = exc
                time.sleep(0.1)
        raise SmokeError(f"handshake timed out after {timeout:g}s: {last_error}")

    def _wire_request(
        self,
        path: str,
        payload: Mapping[str, Any],
        timeout: float,
    ) -> Mapping[str, Any]:
        request_id = secrets.token_hex(16)
        envelope = self._request(
            "POST",
            path,
            payload={
                "protocol_version": PROTOCOL_VERSION,
                "request_id": request_id,
                "run_id": self.run_id,
                "payload": dict(payload),
            },
            timeout=timeout,
        )
        if envelope.get("protocol_version") != PROTOCOL_VERSION:
            raise SmokeError(f"{path} returned an incompatible protocol version")
        if (
            envelope.get("request_id") != request_id
            or envelope.get("run_id") != self.run_id
        ):
            raise SmokeError(f"{path} returned mismatched request identity")
        if envelope.get("status") != "ok":
            raise SmokeError(f"{path} returned Worker error: {envelope.get('error')!r}")
        return _mapping(envelope.get("payload"), f"{path} payload")

    def prepare(self, config: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
        return self._wire_request(
            "/prepare",
            {
                "context": {
                    "run_id": self.run_id,
                    "work_dir": "/run/rag-eval-work",
                    "source_dir": "/run/rag-eval-source",
                    "platform_version": "0.1.0",
                    "seed": 0,
                    "repetition": 1,
                },
                "config": dict(config),
            },
            timeout,
        )

    def health(self, timeout: float = 5.0) -> Mapping[str, Any]:
        request_id = secrets.token_hex(16)
        query = urllib.parse.urlencode(
            {
                "protocol_version": PROTOCOL_VERSION,
                "request_id": request_id,
                "run_id": self.run_id,
            }
        )
        envelope = self._request("GET", f"/health?{query}", timeout=timeout)
        if envelope.get("protocol_version") != PROTOCOL_VERSION:
            raise SmokeError("/health returned an incompatible protocol version")
        if (
            envelope.get("request_id") != request_id
            or envelope.get("run_id") != self.run_id
        ):
            raise SmokeError("/health returned mismatched request identity")
        if envelope.get("status") != "ok":
            raise SmokeError(
                f"/health returned Worker error: {envelope.get('error')!r}"
            )
        return _mapping(envelope.get("payload"), "/health payload")

    def close(self, timeout: float = 10.0) -> Mapping[str, Any]:
        return self._wire_request("/close", {}, timeout)


class LifecycleClient(Protocol):
    def wait_for_handshake(self, timeout: float) -> Mapping[str, Any]: ...

    def prepare(
        self, config: Mapping[str, Any], timeout: float
    ) -> Mapping[str, Any]: ...

    def health(self, timeout: float = 5.0) -> Mapping[str, Any]: ...

    def close(self, timeout: float = 10.0) -> Mapping[str, Any]: ...


def _validate_handshake(spec: WorkerSpec, handshake: Mapping[str, Any]) -> None:
    expected = {
        "protocol_version": PROTOCOL_VERSION,
        "adapter_id": spec.adapter_id,
        "system_id": spec.system_id,
        "system_version": spec.system_version,
    }
    for field, wanted in expected.items():
        if handshake.get(field) != wanted:
            raise SmokeError(
                f"handshake {field} mismatch: expected {wanted!r}, found {handshake.get(field)!r}"
            )
    _mapping(handshake.get("capabilities"), "handshake capabilities")


def run_smoke(
    spec: WorkerSpec,
    *,
    image: str,
    pull: bool,
    startup_timeout: float,
    docker: DockerRuntime,
    client_factory: Callable[[str, str, str], LifecycleClient] = WorkerHttpClient,
) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    run_id = f"worker-smoke-{spec.name}-{secrets.token_hex(4)}"
    container_id: str | None = None
    stage = "pull"
    try:
        if pull:
            docker.pull(image)
        stage = "start"
        container_id = docker.start(spec, image, token, run_id)
        port = docker.published_port(container_id)
        client = client_factory(f"http://127.0.0.1:{port}", token, run_id)

        stage = "handshake"
        handshake = client.wait_for_handshake(startup_timeout)
        _validate_handshake(spec, handshake)

        stage = "prepare"
        prepared = client.prepare(spec.prepare_config, spec.prepare_timeout_seconds)
        prepared_capabilities = _mapping(
            prepared.get("capabilities"), "prepared capabilities"
        )
        if prepared_capabilities != handshake.get("capabilities"):
            raise SmokeError("prepare capabilities differ from handshake capabilities")
        if prepared.get("system_version") != spec.system_version:
            raise SmokeError(
                "prepared system_version differs from the immutable runtime lock"
            )

        stage = "health"
        health = client.health()
        if health.get("ready") is not True:
            raise SmokeError(f"Worker is not ready after prepare: {health!r}")
        details = _mapping(health.get("details", {}), "health details")
        if details.get("prepared") is not True:
            raise SmokeError(
                f"Worker health does not report prepared state: {health!r}"
            )
        if health.get("status") in {None, "closed", "failed"}:
            raise SmokeError(f"Worker health status is not usable: {health!r}")

        stage = "close"
        closed = client.close()
        if closed.get("closed") is not True:
            raise SmokeError(f"Worker did not acknowledge close: {closed!r}")
        return {
            "worker": spec.name,
            "image": image,
            "protocol_version": handshake["protocol_version"],
            "adapter_id": handshake["adapter_id"],
            "system_id": handshake["system_id"],
            "system_version": handshake["system_version"],
            "health_status": health["status"],
            "result": "PASS",
        }
    except Exception as exc:
        logs = docker.logs(container_id) if container_id else ""
        safe_logs = redact(logs, [token])
        detail = redact(f"Worker smoke failed during {stage}: {exc}", [token])
        if safe_logs.strip():
            detail += f"\n--- redacted container log ---\n{safe_logs.strip()}"
        raise SmokeError(detail) from exc
    finally:
        if container_id:
            docker.remove(container_id)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", required=True, choices=("lightrag", "rag-anything"))
    parser.add_argument(
        "--lock",
        type=Path,
        default=Path(__file__).resolve().with_name("worker-runtime-lock.yaml"),
    )
    parser.add_argument(
        "--image", help="candidate image override; default is locked digest"
    )
    parser.add_argument(
        "--pull",
        choices=("always", "missing", "never"),
        default="missing",
        help="pull policy for the selected image",
    )
    parser.add_argument("--startup-timeout", type=float, default=60.0)
    parser.add_argument("--docker", default="docker")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.startup_timeout <= 0:
            raise SmokeError("--startup-timeout must be positive")
        spec = load_worker_spec(args.lock.resolve(), args.worker)
        image = args.image or spec.locked_image
        docker = DockerCli(args.docker)
        if args.pull == "always":
            should_pull = True
        elif args.pull == "never":
            should_pull = False
        else:
            should_pull = not docker.image_exists(image)
        result = run_smoke(
            spec,
            image=image,
            pull=should_pull,
            startup_timeout=args.startup_timeout,
            docker=docker,
        )
    except SmokeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
