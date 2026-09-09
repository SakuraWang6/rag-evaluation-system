from __future__ import annotations

import subprocess
from pathlib import Path

from rag_eval.execution_provider import (
    DockerProvider,
    ExecutionRequest,
    record_cancelled_liveness,
)
from rag_eval.worker.process import WorkerCommand


def test_docker_provider_launches_the_resolved_immutable_image_id(
    monkeypatch, tmp_path: Path
) -> None:
    import rag_eval.execution_provider as module

    image_id = "sha256:" + "a" * 64
    calls: list[list[str]] = []

    class Client:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def wait_until_ready(self) -> None:
            return None

        def close(self) -> None:
            return None

    def docker(arguments: list[str], *, check: bool = True):
        calls.append(arguments)
        if arguments[:2] == ["image", "inspect"]:
            return image_id
        if arguments[:1] == ["run"]:
            return "container-id\\n"
        if arguments[:1] == ["inspect"]:
            return '{"Pid": 1234}'
        raise AssertionError(arguments)

    monkeypatch.setattr(module.shutil, "which", lambda _name: "/usr/bin/docker")
    monkeypatch.setattr(module.os, "getuid", lambda: 501)
    monkeypatch.setattr(module.os, "getgid", lambda: 20)
    monkeypatch.setattr(module, "reserve_loopback_port", lambda: 32123)
    monkeypatch.setattr(module, "WorkerClient", Client)
    monkeypatch.setattr(module, "_docker", docker)

    handle = DockerProvider().start(
        ExecutionRequest(
            command=WorkerCommand(
                adapter_id="lightrag",
                adapter_factory="example:create",
            ),
            run_id="immutable-image",
            log_path=tmp_path / "worker.log",
            source_dir=tmp_path / "source",
            work_dir=tmp_path / "work",
        )
    )

    run_arguments = next(arguments for arguments in calls if arguments[:1] == ["run"])
    assert image_id in run_arguments
    assert "rag-eval-adapter-lightrag:0.1.0" not in run_arguments
    assert handle.launch_metadata["image"] == image_id
    assert handle.launch_metadata["image_reference"] == "rag-eval-adapter-lightrag:0.1.0"


def test_docker_provider_retries_after_removing_matching_managed_conflict(
    monkeypatch, tmp_path: Path
) -> None:
    import rag_eval.execution_provider as module

    image_id = "sha256:" + "b" * 64
    calls: list[list[str]] = []
    conflict = True

    class Client:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def wait_until_ready(self) -> None:
            return None

        def close(self) -> None:
            return None

    def docker(arguments: list[str], *, check: bool = True):
        nonlocal conflict
        calls.append(arguments)
        if arguments[:2] == ["image", "inspect"]:
            return image_id
        if arguments[:1] == ["run"]:
            if conflict:
                conflict = False
                raise RuntimeError("docker run failed: name is already in use")
            return "container-id\n"
        if arguments[:1] == ["inspect"] and any("Config.Labels" in item for item in arguments):
            return subprocess.CompletedProcess(
                ["docker", *arguments],
                0,
                '{"rag-eval.managed":"true","rag-eval.run_id":"retry-conflict"}',
                "",
            )
        if arguments[:1] == ["inspect"]:
            return '{"Pid": 1234}'
        if arguments[:2] == ["rm", "--force"]:
            return subprocess.CompletedProcess(["docker", *arguments], 0, "", "")
        raise AssertionError(arguments)

    monkeypatch.setattr(module.shutil, "which", lambda _name: "/usr/bin/docker")
    monkeypatch.setattr(module.os, "getuid", lambda: 501)
    monkeypatch.setattr(module.os, "getgid", lambda: 20)
    monkeypatch.setattr(module, "reserve_loopback_port", lambda: 32124)
    monkeypatch.setattr(module, "WorkerClient", Client)
    monkeypatch.setattr(module, "_docker", docker)

    handle = DockerProvider().start(
        ExecutionRequest(
            command=WorkerCommand(adapter_id="lightrag", adapter_factory="example:create"),
            run_id="retry-conflict",
            log_path=tmp_path / "worker.log",
            source_dir=tmp_path / "source",
            work_dir=tmp_path / "work",
        )
    )

    assert handle.container_id == "container-id"
    assert any(arguments[:2] == ["rm", "--force"] for arguments in calls)
    assert sum(arguments[:1] == ["run"] for arguments in calls) == 2


def test_docker_handle_closes_adapter_and_redacts_runtime_logs(
    monkeypatch, tmp_path: Path
) -> None:
    import rag_eval.execution_provider as module

    endpoint = "http://host.docker.internal:11434"
    log = tmp_path / "lightrag-server.log"
    log.write_text(f"Host: {endpoint}\\n", encoding="utf-8")
    calls: list[list[str]] = []

    class Client:
        closed_adapter = False
        closed = False

        def close_adapter(self) -> None:
            self.closed_adapter = True

        def close(self) -> None:
            self.closed = True

    client = Client()
    monkeypatch.setattr(
        module,
        "_docker",
        lambda arguments, **_kwargs: calls.append(arguments),
    )
    from rag_eval.execution_provider import DockerWorkerHandle

    handle = DockerWorkerHandle(
        container_id="container-id",
        client=client,  # type: ignore[arg-type]
        worker_pid=1,
        launch_metadata={},
        host_source=tmp_path / "source",
        host_work=tmp_path,
        runtime_endpoints=(endpoint,),
    )
    handle.stop()

    assert client.closed_adapter and client.closed
    assert calls == [["rm", "--force", "container-id"]]
    assert endpoint not in log.read_text(encoding="utf-8")


def test_confirmed_cancellation_is_persisted_for_native_liveness(tmp_path: Path) -> None:
    status = tmp_path / "ingestion-liveness.json"
    status.write_text(
        '{"schema_version":1,"stage":"parsing","active_stage":"parsing"}',
        encoding="utf-8",
    )

    record_cancelled_liveness(tmp_path, confirmed=True)

    import json

    payload = json.loads(status.read_text(encoding="utf-8"))
    assert payload["stage"] == "cancelled"
    assert payload["terminal"] is True
    assert payload["cancellation_confirmed"] is True
    assert payload["details"]["event"] == "worker_process_group_terminated"
