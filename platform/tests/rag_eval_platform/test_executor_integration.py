from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

import pytest

from rag_eval.cli import main as cli_main
from rag_eval.contracts.run import ExperimentSpec, RunStatus
from rag_eval.datasets.bundle import DatasetBundleStore, case_selection_id
from rag_eval.execution import RunExecutor
from rag_eval.storage.runs import RunStore
from rag_eval.systems import SystemRegistration, SystemRegistry
from rag_eval.worker.process import WorkerCommand
from tests.rag_eval_platform.test_bundle_store import write_bundle


def require_loopback_bind() -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
    except PermissionError:
        pytest.skip("sandbox does not permit binding a loopback port")


def test_standalone_fake_adapter_run_is_reproducible_and_source_only(
    tmp_path: Path,
) -> None:
    require_loopback_bind()
    source = tmp_path / "bundle"
    source.mkdir()
    write_bundle(source)
    dataset_store = DatasetBundleStore(tmp_path / "platform" / "datasets")
    bundle = dataset_store.register(source)
    run_store = RunStore(tmp_path / "platform" / "runs")
    executor = RunExecutor(dataset_store, run_store)

    platform_src = Path(__file__).resolve().parents[2] / "src"
    pythonpath = str(platform_src)
    if inherited := os.environ.get("PYTHONPATH"):
        pythonpath = os.pathsep.join([pythonpath, inherited])
    command = WorkerCommand(
        adapter_id="fake",
        adapter_factory="rag_eval.adapters.fake:create_worker_definition",
        python_executable=sys.executable,
        environment={"PYTHONPATH": pythonpath},
    )
    spec = ExperimentSpec(
        experiment_id="standalone-fake",
        bundle_id=bundle.bundle_id,
        system_id="fake-rag",
        adapter_id="fake",
        query_config={"final_context_k": 1},
        metric_config={"k_values": [1]},
        case_selection_id=case_selection_id(
            ["case-1"], policy="all", seed=0
        ),
        repetitions=2,
    )
    manifest = executor.execute(spec, command, run_id="fake-run")

    assert manifest.status == RunStatus.COMPLETED
    assert manifest.schema_version == 2
    assert manifest.producer == "rag_eval_platform"
    assert manifest.effective_config["query"]["final_context_k"] == 1
    assert manifest.index_fingerprint
    assert len(manifest.index_fingerprints) == 2
    assert manifest.repetition_seeds == [0, 1]
    assert manifest.reproducibility is not None
    assert len(manifest.reproducibility.dependency_lock_digest) == 64
    assert manifest.artifact_checksums
    cases = run_store.cases("fake-run")
    assert [case.repetition for case in cases] == [1, 2]
    case = cases[0]
    groundedness = next(
        metric for metric in case.metrics if metric.metric_id == "answer_groundedness"
    )
    assert groundedness.value == 1.0

    source_files = sorted(
        path.name for path in (run_store.root / "fake-run" / "source").iterdir()
    )
    assert len(source_files) == 1
    assert source_files[0].startswith("source-00000-")
    assert source_files[0].endswith(".txt")
    assert not any("gold" in name or "answer" in name for name in source_files)

    summary_path = run_store.root / "fake-run" / "summary.json"
    summary = json.loads(summary_path.read_text())
    assert summary["metrics"]["answer_groundedness"]["repetition_values"] == [
        1.0,
        1.0,
    ]
    assert summary["metrics"]["answer_groundedness"][
        "standard_deviation"
    ] == 0.0
    assert summary["execution"]["execution_failure_rate"] == 0.0
    assert run_store.verify_artifacts("fake-run").valid

    SystemRegistry(tmp_path / "platform" / "systems").register(
        SystemRegistration(
            system_id="fake-rag",
            adapter_id="fake",
            adapter_factory="rag_eval.adapters.fake:create_worker_definition",
            python_executable=sys.executable,
            environment={"PYTHONPATH": pythonpath},
        )
    )
    with pytest.raises(
        ValueError, match="new public Runs require an immutable Benchmark Release"
    ):
        cli_main(
            [
                "--home",
                str(tmp_path / "platform"),
                "replay",
                "fake-run",
                "--new-run-id",
                "fake-replay",
            ]
        )
    assert not (run_store.root / "fake-replay").exists()

    summary_path.write_text("{}", encoding="utf-8")
    verification = run_store.verify_artifacts("fake-run")
    assert not verification.valid
    assert verification.mismatched == ("summary.json",)
    assert (
        cli_main(
            [
                "--home",
                str(tmp_path / "platform"),
                "replay",
                "fake-run",
                "--new-run-id",
                "must-not-exist",
            ]
        )
        == 2
    )
    assert not (run_store.root / "must-not-exist").exists()
