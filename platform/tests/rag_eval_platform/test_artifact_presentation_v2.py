from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_eval.api import create_app
from rag_eval.contracts.schema import PUBLIC_MODELS
from rag_eval.runs import ArtifactV2Reader, ArtifactWriter
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths
from tests.rag_eval_platform.test_run_artifact_v2 import (
    _benchmark_identity,
    _evaluated_case,
)
from tests.rag_eval_platform.test_run_history import _manifest, _write_archive


def _write_v2_run(service: PlatformService, run_id: str = "run-1") -> Path:
    resolved, case = _evaluated_case()
    manifest = _manifest().model_copy(
        update={
            "run_id": run_id,
            "experiment_id": "experiment-1",
            "dataset_release_id": "dataset-release-1",
        }
    )
    run_dir = service.paths.runs / run_id
    run_dir.mkdir(parents=True)
    service.runs.write_manifest(manifest)
    started = datetime(2026, 9, 8, tzinfo=UTC)
    ArtifactWriter(run_dir).publish(
        run_id=run_id,
        experiment_id="experiment-1",
        benchmark_identity=_benchmark_identity(resolved),
        cases=(case,),
        started_at=started,
        completed_at=started + timedelta(seconds=2),
    )
    return run_dir


def _forbid_runtime_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Artifact presentation must not score or map provenance")

    monkeypatch.setattr("rag_eval.run_history.aggregate_metrics", forbidden)
    monkeypatch.setattr("rag_eval.run_history.evidence_observability", forbidden)
    monkeypatch.setattr("rag_eval.storage.runs.case_judgments", forbidden)
    monkeypatch.setattr("rag_eval.storage.runs.score_answer", forbidden)


def test_artifact_v2_api_reads_only_persisted_views(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    run_dir = _write_v2_run(service)
    _write_v2_run(service, "run-2")
    persisted = ArtifactV2Reader(run_dir / "artifact-v2")
    _forbid_runtime_projection(monkeypatch)
    client = TestClient(create_app(service, start_supervisor=False))

    summary = client.get("/api/v1/runs/run-1/summary")
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["availability"] == "available"
    assert payload["artifact_contract_version"] == "2.0"
    assert payload["verification"]["valid"] is True
    assert payload["summary"]["leaderboard_eligibility"]["eligible"] is True
    assert payload["manifest"] == persisted.manifest().model_dump(mode="json")
    assert payload["summary"] == persisted.summary().model_dump(mode="json")
    assert payload["metric_descriptors"]
    assert {
        item["descriptor"]["metric_id"] for item in payload["metric_descriptors"]
    } >= set(payload["summary"]["leaderboard_eligibility"]["required_metric_ids"])

    index = client.get("/api/v1/runs/run-1/cases/index")
    assert index.status_code == 200
    assert index.json()["availability"] == "available"
    answer_judgment = index.json()["cases"][0]["answer_judgment"]
    assert answer_judgment["status"] == "observed"
    assert answer_judgment["value"] == "correct"

    detail = client.get("/api/v1/runs/run-1/cases/case-1")
    assert detail.status_code == 200
    assert detail.json()["availability"] == "available"
    artifact_case = detail.json()["artifact_case"]
    assert artifact_case == persisted.case("case-1").model_dump(mode="json")
    assert artifact_case["adapter_result"]["trace"]["ranked_retrieval"][
        "observation_status"
    ] == "observed"
    assert artifact_case["evaluation"]["metrics"][0]["descriptor"]
    assert detail.json()["legacy_case"] is None

    cases = client.get("/api/v1/runs/run-1/cases")
    assert cases.status_code == 200
    assert cases.json()["availability"] == "available"
    assert len(cases.json()["cases"]) == 1

    comparison = client.post(
        "/api/v1/comparisons/validate",
        json={"run_ids": ["run-1", "run-2"], "tier": "task_comparable"},
    )
    assert comparison.status_code == 200
    assert all(
        item["summary"]["availability"] == "available"
        for item in comparison.json()["runs"]
    )


def test_legacy_artifact_api_fails_closed_without_read_time_rescoring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "archive"
    _write_archive(archive)
    monkeypatch.setenv("RAG_EVAL_RUN_ARCHIVES", str(archive))
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    legacy_shadow = service.run_history.summary("archive-run-1")
    assert legacy_shadow["metrics"]["answer_accuracy"]["value"] == 1.0
    _forbid_runtime_projection(monkeypatch)
    client = TestClient(create_app(service, start_supervisor=False))

    summary = client.get("/api/v1/runs/archive-run-1/summary").json()
    assert summary["availability"] == "legacy_unavailable"
    assert summary["artifact_contract_version"] == "1.2"
    assert summary["summary"] is None
    assert summary["metric_descriptors"] == []
    assert "metrics" not in summary
    assert "not persisted" in summary["reason"]

    index = client.get("/api/v1/runs/archive-run-1/cases/index").json()
    assert index["availability"] == "legacy_unavailable"
    assert index["cases"][0]["answer_judgment"]["status"] == "unavailable"
    assert index["cases"][0]["evidence_judgment"]["status"] == "unavailable"

    detail = client.get("/api/v1/runs/archive-run-1/cases/case-1").json()
    assert detail["availability"] == "legacy_unavailable"
    assert detail["artifact_case"] is None
    assert detail["legacy_case"]["answer"] == "42"
    assert detail["legacy_case"]["question"] == "Which value is recorded?"


def test_corrupted_artifact_v2_is_diagnostic_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    run_dir = _write_v2_run(service)
    case_path = run_dir / "artifact-v2" / "cases" / "rep-0001-case-1.json"
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    payload["question"] = "tampered"
    case_path.write_text(json.dumps(payload), encoding="utf-8")
    _forbid_runtime_projection(monkeypatch)
    client = TestClient(create_app(service, start_supervisor=False))

    summary = client.get("/api/v1/runs/run-1/summary").json()
    assert summary["availability"] == "corrupted"
    assert summary["summary"] is None
    assert summary["manifest"] is None
    assert summary["verification"]["valid"] is False
    assert summary["verification"]["mismatched"] == [
        "cases/rep-0001-case-1.json"
    ]

    detail = client.get("/api/v1/runs/run-1/cases/case-1").json()
    assert detail["availability"] == "corrupted"
    assert detail["artifact_case"] is None
    assert detail["legacy_case"] is None


def test_product_profiles_declare_ui_capabilities_without_rag_name_logic(
    tmp_path: Path,
) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    client = TestClient(create_app(service, start_supervisor=False))

    profiles = client.get("/api/v1/product/profiles").json()
    assert profiles
    assert all(isinstance(item["query_modes"], list) for item in profiles)
    assert all("query_timeout_min_seconds" in item for item in profiles)


def test_artifact_presentation_schemas_are_exported() -> None:
    schema_root = Path(__file__).resolve().parents[2] / "schemas" / "1.2"
    for name in (
        "run-artifact-overview-view-v1",
        "run-artifact-case-index-view-v1",
        "run-artifact-case-view-v1",
        "run-artifact-case-collection-view-v1",
    ):
        observed = json.loads(
            (schema_root / f"{name}.schema.json").read_text(encoding="utf-8")
        )
        assert observed == PUBLIC_MODELS[name].model_json_schema()


def test_webui_has_no_rag_name_corpus_mode_or_segment_metric_branch() -> None:
    source_root = Path(__file__).resolve().parents[3] / "webui" / "src"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(source_root.rglob("*"))
        if path.suffix in {".ts", ".tsx", ".json"}
    ).lower()
    for forbidden in (
        "lightrag",
        "rag-anything",
        "rag_anything",
        "evaluation_corpus",
        "canonical_segments",
        "benchmark_segments",
        "source_document",
        "segment_ranked_",
        "segment_context_",
    ):
        assert forbidden not in source
