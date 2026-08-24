from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from rag_eval.api import create_app
from rag_eval.contracts.run import ExperimentSpec
from rag_eval.datasets.bundle import case_selection_id
from rag_eval.jobs import JobStatus, JobStore
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths
from rag_eval.systems import SystemRegistration
from tests.rag_eval_platform.test_bundle_store import write_bundle


def experiment(bundle_id: str) -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id="experiment-1",
        bundle_id=bundle_id,
        system_id="fake-rag",
        adapter_id="fake",
        case_selection_id=case_selection_id(["case-1"], policy="all", seed=0),
    )


def test_job_state_machine_cancel_and_restart_recovery(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    queued = store.create(experiment("bundle"))
    assert store.request_cancel(queued.job_id).status == JobStatus.CANCELLED

    active = store.create(
        experiment("bundle").model_copy(update={"experiment_id": "experiment-2"})
    )
    claimed = store.claim_next()
    assert claimed is not None and claimed.job_id == active.job_id
    assert claimed.status == JobStatus.RUNNING
    recovered = store.recover()
    assert recovered[0].status == JobStatus.INTERRUPTED
    assert "restarted" in (recovered[0].error or "")


def test_api_keeps_system_registration_local_and_legacy_out(tmp_path: Path) -> None:
    source = tmp_path / "bundle"
    source.mkdir()
    write_bundle(source)
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    bundle = service.datasets.register(source)
    service.systems.register(
        SystemRegistration(
            system_id="fake-rag",
            adapter_id="fake",
            adapter_factory="rag_eval.adapters.fake:create_worker_definition",
            python_executable=sys.executable,
            environment={"SECRET_TOKEN": "must-not-be-returned"},
        )
    )
    client = TestClient(create_app(service, start_supervisor=False))

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

    spec = experiment(bundle.bundle_id)
    created = client.post(
        "/api/v1/experiments", json=spec.model_dump(mode="json")
    )
    assert created.status_code == 200
    queued = client.post("/api/v1/experiments/experiment-1/runs")
    assert queued.status_code == 200
    job_id = queued.json()["job_id"]
    cancelled = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancelled.json()["status"] == "cancelled"

    legacy = service.paths.runs / "old-legacy"
    legacy.mkdir()
    (legacy / "run.json").write_text('{"schema":"legacy"}', encoding="utf-8")
    assert client.get("/api/v1/runs").json() == []
