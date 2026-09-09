from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

import pytest

from rag_eval.contracts.run import RunStatus
from rag_eval.evaluation.unified import EvaluationMetricStatus
from rag_eval.execution import RunExecutor
from rag_eval.runs import ArtifactV2Reader, RunRecordStateV2
from rag_eval.systems import SystemRegistration
from rag_eval.worker.client import WorkerProtocolError
from tests.rag_eval_platform.test_resolved_run_plan_v2 import _native_experiment


def require_loopback_bind() -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
    except PermissionError:
        pytest.skip("sandbox does not permit binding a loopback port")


def test_standalone_fake_adapter_run_is_reproducible_and_source_only(
    tmp_path: Path,
) -> None:
    """The retained CI node now exercises the complete Direct Wire 2 path."""

    require_loopback_bind()
    service, source_experiment, bundle = _native_experiment(tmp_path)
    platform_src = Path(__file__).resolve().parents[2] / "src"
    pythonpath = str(platform_src)
    if inherited := os.environ.get("PYTHONPATH"):
        pythonpath = os.pathsep.join([pythonpath, inherited])
    service.systems.register(
        SystemRegistration(
            system_id="fake-rag",
            adapter_id="fake",
            adapter_factory="rag_eval.adapters.fake:create_worker_definition",
            python_executable=sys.executable,
            environment={"PYTHONPATH": pythonpath},
        )
    )
    experiment = source_experiment.model_copy(
        update={
            "experiment_id": "standalone-fake",
            "display_name": "Direct Wire 2 fake integration",
            "system_id": "fake-rag",
            "adapter_id": "fake",
            "repetitions": 2,
        }
    )
    reference = service.admit_new_public_experiment(experiment, bundle)
    plan = service.resolved_run_plans.get(reference)
    command = service.system_resolver.resolve(
        experiment.system_id,
        provider=plan.system.execution_provider,
    ).command
    executor = RunExecutor(
        service.datasets,
        service.runs,
        dataset_release_store=service.formal_datasets.releases,
        run_record_store=service.run_records,
    )

    manifest = executor.execute(
        experiment,
        command,
        run_id="fake-run",
        resolved_plan=plan,
        resolved_plan_reference=reference,
    )

    assert manifest.status == RunStatus.COMPLETED
    assert manifest.effective_config["query"]["final_context_k"] == 5
    assert len(manifest.index_fingerprints) == 2
    assert manifest.repetition_seeds == [0, 1]
    assert manifest.reproducibility is not None
    assert len(manifest.reproducibility.dependency_lock_digest) == 64

    record = service.run_records.get("fake-run")
    reader = ArtifactV2Reader(service.paths.runs / "fake-run" / "artifact-v2")
    assert record.state == RunRecordStateV2.COMPLETED
    assert reader.verify().valid
    assert record.artifact_digest == reader.manifest().artifact_digest
    cases = reader.cases()
    assert [case.repetition for case in cases] == [1, 2]
    assert all(case.adapter_result is not None for case in cases)
    assert all(
        case.adapter_result.telemetry["native_query_executions"] == 1
        for case in cases
        if case.adapter_result is not None
    )
    assert all(
        metric.status == EvaluationMetricStatus.UNAVAILABLE
        for case in cases
        for metric in case.evaluation.metrics
    )

    source_files = sorted(
        path.name for path in (service.paths.runs / "fake-run" / "source").iterdir()
    )
    assert len(source_files) == 2
    assert any(name.endswith(".docx") for name in source_files)
    assert any("canonical" in name for name in source_files)
    assert not any(
        token in name
        for name in source_files
        for token in ("gold", "answer", "question")
    )

    case_path = (
        service.paths.runs
        / "fake-run"
        / "artifact-v2"
        / reader.manifest().cases[0].path
    )
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    payload["question"] = "tampered"
    case_path.write_text(json.dumps(payload), encoding="utf-8")
    assert not reader.verify().valid


def test_query_protocol_error_is_persisted_as_unavailable_artifact_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    require_loopback_bind()
    service, source_experiment, bundle = _native_experiment(tmp_path)
    platform_src = Path(__file__).resolve().parents[2] / "src"
    pythonpath = str(platform_src)
    if inherited := os.environ.get("PYTHONPATH"):
        pythonpath = os.pathsep.join([pythonpath, inherited])
    service.systems.register(
        SystemRegistration(
            system_id="fake-rag",
            adapter_id="fake",
            adapter_factory="rag_eval.adapters.fake:create_worker_definition",
            python_executable=sys.executable,
            environment={"PYTHONPATH": pythonpath},
        )
    )
    experiment = source_experiment.model_copy(
        update={
            "experiment_id": "protocol-error",
            "system_id": "fake-rag",
            "adapter_id": "fake",
            "repetitions": 1,
        }
    )
    reference = service.admit_new_public_experiment(experiment, bundle)
    plan = service.resolved_run_plans.get(reference)
    command = service.system_resolver.resolve(
        experiment.system_id,
        provider=plan.system.execution_provider,
    ).command

    def fail_query(*_args, **_kwargs):
        raise WorkerProtocolError("malformed Direct Wire 2 query payload")

    monkeypatch.setattr("rag_eval.worker.client.WorkerClient.query", fail_query)
    manifest = RunExecutor(
        service.datasets,
        service.runs,
        dataset_release_store=service.formal_datasets.releases,
        run_record_store=service.run_records,
    ).execute(
        experiment,
        command,
        run_id="protocol-error-run",
        resolved_plan=plan,
        resolved_plan_reference=reference,
    )

    assert manifest.status == RunStatus.COMPLETED
    record = service.run_records.get("protocol-error-run")
    assert record.state == RunRecordStateV2.COMPLETED
    reader = ArtifactV2Reader(
        service.paths.runs / "protocol-error-run" / "artifact-v2"
    )
    assert reader.verify().valid
    case = reader.cases()[0]
    assert case.status == "system_error"
    assert case.error is not None
    assert case.error.code == "worker_protocol_error"
    assert all(
        metric.status == EvaluationMetricStatus.UNAVAILABLE
        for metric in case.evaluation.metrics
    )
