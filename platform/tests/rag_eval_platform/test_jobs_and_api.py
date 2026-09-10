from __future__ import annotations

import json
import sys
from pathlib import Path

from rag_eval.contracts.run import ExperimentSpec
from rag_eval.jobs import JobStatus, JobStore
from rag_eval.runs.plans import ResolvedRunPlanReferenceV2
from rag_eval.systems import SystemRegistration
from tests.rag_eval_platform.test_native_formal_cutover import (
    _native_product_service,
    _preview_native_experiment,
)


def experiment(release_id: str) -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id="experiment-1",
        dataset_release_id=release_id,
        system_id="fake-rag",
        adapter_id="fake",
        case_selection_id="selection",
    )


def test_job_state_machine_cancel_and_restart_recovery(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    reference = ResolvedRunPlanReferenceV2(
        path="resolved-run-plans/experiment-1.json",
        digest="sha256:" + "a" * 64,
    )
    queued = store.create(
        experiment("release"),
        resolved_plan=reference,
        execution_provider="local",
    )
    assert store.request_cancel(queued.job_id).status == JobStatus.CANCELLED

    active = store.create(
        experiment("release").model_copy(update={"experiment_id": "experiment-2"}),
        resolved_plan=reference.model_copy(
            update={"path": "resolved-run-plans/experiment-2.json"}
        ),
        execution_provider="local",
    )
    claimed = store.claim_next()
    assert claimed is not None and claimed.job_id == active.job_id
    assert claimed.status == JobStatus.RUNNING
    recovered = store.recover()
    assert recovered[0].status == JobStatus.INTERRUPTED
    assert "restarted" in (recovered[0].error or "")


def test_api_keeps_system_registration_local_and_retired_routes_out(
    tmp_path: Path,
) -> None:
    service, client, release_id = _native_product_service(tmp_path)
    service.systems.register(
        SystemRegistration(
            system_id="fake-rag",
            adapter_id="fake",
            adapter_factory="rag_eval.adapters.fake:create_worker_definition",
            python_executable=sys.executable,
            environment={"SECRET_TOKEN": "must-not-be-returned"},
        )
    )
    preflight = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://127.0.0.1:4178",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.headers["access-control-allow-origin"] == (
        "http://127.0.0.1:4178"
    )

    systems = client.get("/api/v1/systems").json()
    assert systems[0]["environment_keys"] == ["SECRET_TOKEN"]
    assert "must-not-be-returned" not in str(systems)
    assert client.post("/api/v1/systems", json={}).status_code == 405

    spec = _preview_native_experiment(client, release_id).model_copy(
        update={
            "experiment_id": "missing-release",
            "dataset_release_id": release_id + "-missing",
        }
    )
    created = client.post(
        "/api/v1/experiments", json=spec.model_dump(mode="json")
    )
    assert created.status_code == 400
    assert "Benchmark Release" in created.text
    assert service.experiments.list() == []
    assert service.jobs.list() == []
    assert client.get("/api/v1/datasets").status_code == 404

    liveness_dir = service.paths.runs / "native-active" / "work" / "rep-0001"
    liveness_dir.mkdir(parents=True)
    (liveness_dir / "ingestion-liveness.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "stage": "parsing",
                "active_stage": "parsing",
                "progress_seq": 2,
                "details": {"child_processes": 1},
            }
        ),
        encoding="utf-8",
    )
    liveness = client.get("/api/v1/runs/native-active/liveness")
    assert liveness.status_code == 404

    legacy = service.paths.runs / "old-legacy"
    legacy.mkdir()
    (legacy / "run.json").write_text('{"schema":"legacy"}', encoding="utf-8")
    assert client.get("/api/v1/runs").json() == []
