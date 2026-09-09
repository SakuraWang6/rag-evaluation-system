from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_eval.api import create_app
from rag_eval.contracts.schema import PUBLIC_MODELS
from rag_eval.runs import ArtifactV2Reader, ArtifactWriter
from rag_eval.runs.plans import (
    BenchmarkReleaseIdentityV2,
    NativeMetricConfigV2,
    NativeQueryConfigV2,
    OriginalDocumentIdentityV2,
    ResolvedResourceLimitsV2,
    ResolvedRunPlanV2,
    ResolvedSystemIdentityV2,
    formal_metric_descriptors,
)
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths
from tests.rag_eval_platform.test_run_artifact_v2 import (
    _benchmark_identity,
    _evaluated_case,
)
from tests.rag_eval_platform.test_unified_evaluation_v2 import SHA_A, SHA_C, _profile


def _write_v2_run(
    service: PlatformService,
    run_id: str = "run-1",
    *,
    context_budget: int = 4096,
) -> Path:
    resolved, case = _evaluated_case(context_budget=context_budget)
    experiment_id = f"experiment-{run_id}"
    profile = _profile(1).model_copy(
        update={"context_budget": context_budget}
    )
    plan = ResolvedRunPlanV2(
        experiment_id=experiment_id,
        experiment_digest="sha256:" + "d" * 64,
        benchmark_release=BenchmarkReleaseIdentityV2(
            release_id="dataset-release-1",
            release_digest=SHA_C,
            validation_report_digest=SHA_A,
            runtime_bundle_id=SHA_A,
        ),
        original_document=OriginalDocumentIdentityV2(
            document_id="doc-1",
            source_sha256=SHA_A,
            runtime_path="documents/source.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        system=ResolvedSystemIdentityV2(
            system_id="system-under-test",
            adapter_id="adapter-under-test",
            adapter_factory="fixture.worker:create",
            worker_profile_kind="registered_system",
            worker_profile_id="fixture-profile",
            worker_profile_version="1",
            worker_profile_digest="sha256:" + "e" * 64,
            system_config_digest="sha256:" + "f" * 64,
            execution_provider="fixture",
            worker_request_timeout_seconds=30,
        ),
        adapter_config_digest="sha256:" + "1" * 64,
        query_config=NativeQueryConfigV2(
            generate_answer=True,
            retrieval_candidate_k=1,
            final_context_k=1,
            max_context_tokens=context_budget,
            generation_options={},
        ),
        metric_config=NativeMetricConfigV2(k_values=(1, 3, 5)),
        evaluation_profile=profile,
        metric_descriptors=formal_metric_descriptors(profile),
        case_ids=("case-1",),
        case_selection_id="selection-1",
        seed=7,
        repetitions=1,
        resource_limits=ResolvedResourceLimitsV2(
            worker_request_timeout_seconds=30,
            max_context_tokens=context_budget,
        ),
    )
    reference = service.resolved_run_plans.create(plan)
    run_dir = service.paths.runs / run_id
    started = datetime(2026, 9, 8, tzinfo=UTC)
    service.run_records.create(
        run_id=run_id,
        experiment_id=experiment_id,
        resolved_plan=reference,
        created_at=started,
    )
    service.run_records.mark_running(run_id, started_at=started)
    ArtifactWriter(run_dir).publish(
        run_id=run_id,
        experiment_id=experiment_id,
        benchmark_identity=_benchmark_identity(resolved),
        cases=(case,),
        started_at=started,
        completed_at=started + timedelta(seconds=2),
    )
    service.run_records.mark_completed(run_id)
    return run_dir


def _write_retired_run(root: Path) -> None:
    run_dir = root / "runs" / "archive-run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text("{}\n", encoding="utf-8")


def _forbid_runtime_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Artifact presentation must not score or map provenance")

    monkeypatch.setattr(
        "rag_eval.runs.orchestration.evaluate_unified_trace", forbidden
    )
    monkeypatch.setattr("rag_eval.runs.orchestration.score_answer", forbidden)


@pytest.mark.native_v2_characterization
def test_artifact_v2_api_reads_only_persisted_views(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    run_dir = _write_v2_run(service)
    _write_v2_run(service, "run-2")
    persisted = ArtifactV2Reader(run_dir / "artifact-v2")
    _forbid_runtime_projection(monkeypatch)
    client = TestClient(create_app(service, start_supervisor=False))

    run = client.get("/api/v1/runs/run-1")
    assert run.status_code == 200
    assert run.json()["schema_version"] == "2.0"
    assert run.json()["state"] == "completed"
    assert "metrics" not in run.json()
    assert "leaderboard_eligibility" not in run.json()

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
    assert "legacy_case" not in detail.json()

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

    report = client.get("/api/v1/runs/run-1/report")
    assert report.status_code == 200
    assert "Artifact contract: `2.0`" in report.text
    assert persisted.manifest().artifact_digest in report.text


@pytest.mark.native_v2_characterization
def test_comparison_marks_descriptor_drifted_metrics_noncomparable(
    tmp_path: Path,
) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    _write_v2_run(service, "run-1", context_budget=4096)
    _write_v2_run(service, "run-2", context_budget=8192)
    client = TestClient(create_app(service, start_supervisor=False))

    response = client.post(
        "/api/v1/comparisons/validate",
        json={"run_ids": ["run-1", "run-2"], "tier": "task_comparable"},
    )

    assert response.status_code == 200
    assert all(
        decision["comparable"] is False
        for decision in response.json()["metric_decisions"]
    )
    assert any(
        "metric descriptor differs" in reason
        for decision in response.json()["metric_decisions"]
        for reason in decision["reasons"]
    )


def test_legacy_artifact_api_is_not_a_supported_read_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "archive"
    _write_retired_run(archive)
    monkeypatch.setenv("RAG_EVAL_RUN_ARCHIVES", str(archive))
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    _forbid_runtime_projection(monkeypatch)
    client = TestClient(create_app(service, start_supervisor=False))

    assert client.get("/api/v1/runs").json() == []
    assert client.get("/api/v1/runs/archive-run-1").status_code == 404
    assert client.get("/api/v1/runs/archive-run-1/summary").status_code == 404
    assert client.get("/api/v1/runs/archive-run-1/cases").status_code == 404
    assert client.get("/api/v1/runs/archive-run-1/cases/index").status_code == 404
    assert client.get("/api/v1/runs/archive-run-1/cases/case-1").status_code == 404
    assert client.get("/api/v1/runs/archive-run-1/report").status_code == 404
    assert (
        client.get("/api/v1/runs/archive-run-1/artifacts/verify").status_code
        == 404
    )
    assert client.get("/api/v1/runs/archive-run-1/liveness").status_code == 404
    assert (
        client.put(
            "/api/v1/runs/archive-run-1/presentation",
            json={"display_name": "legacy"},
        ).status_code
        == 404
    )


@pytest.mark.native_v2_characterization
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
    assert "legacy_case" not in detail


@pytest.mark.native_v2_characterization
def test_missing_artifact_v2_is_reported_as_corruption_not_legacy_or_zero(
    tmp_path: Path,
) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    run_dir = _write_v2_run(service)
    artifact_root = run_dir / "artifact-v2"
    artifact_root.rename(run_dir / "artifact-v2.removed")
    client = TestClient(create_app(service, start_supervisor=False))

    summary = client.get("/api/v1/runs/run-1/summary")
    verification = client.get("/api/v1/runs/run-1/artifacts/verify")

    assert summary.status_code == 200
    assert summary.json()["availability"] == "corrupted"
    assert summary.json()["summary"] is None
    assert summary.json()["verification"]["valid"] is False
    assert summary.json()["verification"]["missing"] == ["artifact.json"]
    assert verification.status_code == 200
    assert verification.json()["valid"] is False


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
    schema_root = Path(__file__).resolve().parents[2] / "schemas" / "2.0"
    for name in (
        "run-artifact-overview-view-v2",
        "run-artifact-case-index-view-v2",
        "run-artifact-case-view-v2",
        "run-artifact-case-collection-view-v2",
    ):
        observed = json.loads(
            (schema_root / f"{name}.schema.json").read_text(encoding="utf-8")
        )
        assert observed == PUBLIC_MODELS[name].model_json_schema()


@pytest.mark.native_v2_characterization
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
