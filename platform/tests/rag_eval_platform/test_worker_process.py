from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from rag_eval.worker.process import (
    WorkerCommand,
    WorkerProcess,
    process_group_has_live_members,
    terminate_process_group,
)

from .native_worker_fixtures import native_query, stage_native_worker_input


def _capture_opened_files(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    opened_files: list[object] = []
    original_open = Path.open

    def tracked_open(path: Path, *args: object, **kwargs: object):
        opened_file = original_open(path, *args, **kwargs)
        opened_files.append(opened_file)
        return opened_file

    monkeypatch.setattr(Path, "open", tracked_open)
    return opened_files


def _assert_worker_resources_cleared(worker: WorkerProcess) -> None:
    assert worker.process is None
    assert worker.client is None
    assert worker._log_file is None


def test_fake_adapter_runs_over_real_loopback_process(tmp_path: Path) -> None:
    platform_src = Path(__file__).resolve().parents[2] / "src"
    inherited_pythonpath = os.environ.get("PYTHONPATH", "")
    pythonpath = str(platform_src)
    if inherited_pythonpath:
        pythonpath = os.pathsep.join([pythonpath, inherited_pythonpath])
    command = WorkerCommand(
        adapter_id="fake",
        adapter_factory="rag_eval.adapters.fake:create_worker_definition",
        python_executable=sys.executable,
        environment={"PYTHONPATH": pythonpath},
    )
    try:
        process = WorkerProcess(
            command, run_id="process-run", log_path=tmp_path / "worker.log"
        )
    except PermissionError:
        pytest.skip("sandbox does not permit binding a loopback port")

    try:
        client = process.start()
        health = client.health()
        assert health.identity.adapter_id == "fake"
        original, resolved = stage_native_worker_input(
            tmp_path,
            run_id="process-run",
        )
        prepared = client.prepare(original, resolved)
        assert prepared.effective_config["final_context_k"] == 1
        result = client.query(prepared, native_query())
        assert result.trace.final_context.items
        assert result.trace.final_context.items[0].content == (
            "The controlled value is 42."
        )
        assert result.telemetry["native_query_executions"] == 1
    finally:
        process.stop()

    assert process.process is None


def test_worker_prepends_selected_python_bin_to_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    class ProcessStub:
        pid = 1000

        def poll(self):
            return None

    class ClientStub:
        def wait_until_ready(self, _timeout):
            return None

        def close_adapter(self) -> None:
            return None

        def close(self) -> None:
            return None

    def popen(argv, **kwargs):
        captured["argv"] = argv
        captured["env"] = kwargs["env"]
        return ProcessStub()

    monkeypatch.setattr("rag_eval.worker.process.reserve_loopback_port", lambda: 9876)
    monkeypatch.setattr("rag_eval.worker.process.subprocess.Popen", popen)
    monkeypatch.setattr(
        "rag_eval.worker.process.WorkerClient", lambda *args, **kwargs: ClientStub()
    )
    monkeypatch.setattr(
        "rag_eval.worker.process.terminate_process_group", lambda *_args, **_kwargs: True
    )
    executable = tmp_path / "venv" / "bin" / "python"
    executable.parent.mkdir(parents=True)
    executable.write_text("")
    process = WorkerProcess(
        WorkerCommand(
            adapter_id="fake",
            adapter_factory="rag_eval.adapters.fake:create_worker_definition",
            python_executable=str(executable),
        ),
        run_id="run-path",
        log_path=tmp_path / "worker.log",
    )

    process.start()

    environment = captured["env"]
    assert isinstance(environment, dict)
    assert environment["PATH"].split(os.pathsep)[0] == str(executable.parent)
    assert process.cancel()
    _assert_worker_resources_cleared(process)


def test_worker_start_closes_log_when_popen_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("rag_eval.worker.process.reserve_loopback_port", lambda: 9876)
    opened_files = _capture_opened_files(monkeypatch)

    def fail_to_spawn(*_args: object, **_kwargs: object) -> None:
        raise OSError("spawn failed")

    monkeypatch.setattr("rag_eval.worker.process.subprocess.Popen", fail_to_spawn)
    worker = WorkerProcess(
        WorkerCommand(adapter_id="fake", adapter_factory="example:create"),
        run_id="spawn-failure",
        log_path=tmp_path / "worker.log",
    )

    with pytest.raises(OSError, match="spawn failed"):
        worker.start()

    assert len(opened_files) == 1
    assert opened_files[0].closed  # type: ignore[attr-defined]
    _assert_worker_resources_cleared(worker)
    worker.stop()
    assert worker.cancel()
    _assert_worker_resources_cleared(worker)


def test_worker_start_terminates_process_when_client_construction_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("rag_eval.worker.process.reserve_loopback_port", lambda: 9876)
    opened_files = _capture_opened_files(monkeypatch)

    class ProcessStub:
        pid = 2301

    process_stub = ProcessStub()
    monkeypatch.setattr(
        "rag_eval.worker.process.subprocess.Popen",
        lambda *_args, **_kwargs: process_stub,
    )

    def fail_client_construction(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("client construction failed")

    monkeypatch.setattr(
        "rag_eval.worker.process.WorkerClient", fail_client_construction
    )
    terminated: list[tuple[int, object]] = []

    def terminate(pid: int, *, process: object, **_kwargs: object) -> bool:
        terminated.append((pid, process))
        return True

    monkeypatch.setattr("rag_eval.worker.process.terminate_process_group", terminate)
    worker = WorkerProcess(
        WorkerCommand(adapter_id="fake", adapter_factory="example:create"),
        run_id="client-construction-failure",
        log_path=tmp_path / "worker.log",
    )

    with pytest.raises(RuntimeError, match="client construction failed"):
        worker.start()

    assert terminated == [(2301, process_stub)]
    assert len(opened_files) == 1
    assert opened_files[0].closed  # type: ignore[attr-defined]
    _assert_worker_resources_cleared(worker)
    assert worker.cancel()
    assert terminated == [(2301, process_stub)]


def test_worker_start_cleans_process_client_and_log_when_readiness_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("rag_eval.worker.process.reserve_loopback_port", lambda: 9876)
    opened_files = _capture_opened_files(monkeypatch)

    class ProcessStub:
        pid = 2302

    class ClientStub:
        def __init__(self) -> None:
            self.close_calls = 0
            self.close_adapter_calls = 0

        def wait_until_ready(self, _timeout: float) -> None:
            raise TimeoutError("readiness failed")

        def close(self) -> None:
            self.close_calls += 1

        def close_adapter(self) -> None:
            self.close_adapter_calls += 1

    process_stub = ProcessStub()
    client_stub = ClientStub()
    monkeypatch.setattr(
        "rag_eval.worker.process.subprocess.Popen",
        lambda *_args, **_kwargs: process_stub,
    )
    monkeypatch.setattr(
        "rag_eval.worker.process.WorkerClient", lambda *_args, **_kwargs: client_stub
    )
    terminated: list[int] = []

    def terminate(pid: int, **_kwargs: object) -> bool:
        terminated.append(pid)
        return True

    monkeypatch.setattr("rag_eval.worker.process.terminate_process_group", terminate)
    worker = WorkerProcess(
        WorkerCommand(adapter_id="fake", adapter_factory="example:create"),
        run_id="readiness-failure",
        log_path=tmp_path / "worker.log",
    )

    with pytest.raises(TimeoutError, match="readiness failed"):
        worker.start()

    assert terminated == [2302]
    assert client_stub.close_calls == 1
    assert client_stub.close_adapter_calls == 0
    assert len(opened_files) == 1
    assert opened_files[0].closed  # type: ignore[attr-defined]
    _assert_worker_resources_cleared(worker)


@pytest.mark.parametrize("cleanup_method", ["stop", "cancel"])
def test_worker_cleanup_releases_partial_resources_without_a_process(
    cleanup_method: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("rag_eval.worker.process.reserve_loopback_port", lambda: 9876)

    class ClientStub:
        def __init__(self) -> None:
            self.close_calls = 0
            self.close_adapter_calls = 0

        def close(self) -> None:
            self.close_calls += 1

        def close_adapter(self) -> None:
            self.close_adapter_calls += 1

    client_stub = ClientStub()
    worker = WorkerProcess(
        WorkerCommand(adapter_id="fake", adapter_factory="example:create"),
        run_id=f"partial-{cleanup_method}",
        log_path=tmp_path / "worker.log",
    )
    log_file = worker.log_path.open("a", encoding="utf-8")
    worker.client = client_stub  # type: ignore[assignment]
    worker._log_file = log_file

    first_result = getattr(worker, cleanup_method)()

    if cleanup_method == "cancel":
        assert first_result is True
    else:
        assert first_result is None
    assert client_stub.close_calls == 1
    assert client_stub.close_adapter_calls == 0
    assert log_file.closed
    _assert_worker_resources_cleared(worker)

    second_result = getattr(worker, cleanup_method)()
    if cleanup_method == "cancel":
        assert second_result is True
    assert client_stub.close_calls == 1
    assert client_stub.close_adapter_calls == 0
    _assert_worker_resources_cleared(worker)


def test_process_group_cancellation_ends_parser_descendants(tmp_path: Path) -> None:
    try:
        subprocess.run(
            ["ps", "-axo", "pgid=,stat="],
            check=False,
            capture_output=True,
        )
    except PermissionError:
        pytest.skip("sandbox does not permit process-table inspection")
    marker = tmp_path / "child-started"
    script = (
        "import pathlib,subprocess,sys,time;"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],"
        "start_new_session=True);"
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid));"
        "time.sleep(60)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(marker)],
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 2.0
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists()
        child_pid = int(marker.read_text())
        assert process_group_has_live_members(process.pid)
        assert process_group_has_live_members(child_pid)

        assert terminate_process_group(process.pid, process=process, grace_seconds=1.0)
        assert not process_group_has_live_members(process.pid)
        assert not process_group_has_live_members(child_pid)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, 9)
            process.wait(timeout=1)
        if marker.exists():
            child_pid = int(marker.read_text())
            if process_group_has_live_members(child_pid):
                os.killpg(child_pid, 9)


def test_worker_cancel_does_not_wait_for_adapter_close(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("rag_eval.worker.process.reserve_loopback_port", lambda: 9876)

    class ProcessStub:
        pid = 4242

    class ClientStub:
        close_calls = 0
        close_adapter_calls = 0

        def close(self) -> None:
            self.close_calls += 1

        def close_adapter(self) -> None:
            self.close_adapter_calls += 1

    client = ClientStub()
    worker = WorkerProcess(
        WorkerCommand(adapter_id="fake", adapter_factory="example:create"),
        run_id="cancel-run",
        log_path=tmp_path / "worker.log",
    )
    worker.process = ProcessStub()  # type: ignore[assignment]
    worker.client = client  # type: ignore[assignment]
    worker._log_file = worker.log_path.open("a", encoding="utf-8")
    calls: list[int] = []

    def terminate(pid: int, **_kwargs) -> bool:
        calls.append(pid)
        return True

    monkeypatch.setattr("rag_eval.worker.process.terminate_process_group", terminate)

    assert worker.cancel()
    assert calls == [4242]
    assert client.close_calls == 1
    assert client.close_adapter_calls == 0
    assert worker.process is None
