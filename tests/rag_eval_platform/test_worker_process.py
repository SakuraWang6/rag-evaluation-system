from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from rag_eval.contracts.adapter import DocumentInput, PrepareContext, RAGQuery
from rag_eval.worker.process import WorkerCommand, WorkerProcess


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
        handshake = client.handshake()
        assert handshake.adapter_id == "fake"
        prepared = client.prepare(
            PrepareContext(
                run_id="process-run",
                work_dir=str(tmp_path / "work"),
                source_dir=str(tmp_path / "source"),
                platform_version="0.1.0",
            ),
            {"final_context_k": 1},
        )
        assert prepared.effective_config["final_context_k"] == 1
        client.ingest(
            [
                DocumentInput(
                    document_id="doc-1", content="The controlled value is 42."
                )
            ]
        )
        result = client.query(
            RAGQuery(case_id="case-1", question="controlled value")
        )
        assert result.final_context is not None
        assert result.final_context[0].document_id == "doc-1"
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
        def wait_for_handshake(self, _timeout):
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
    if process._log_file is not None:
        process._log_file.close()
