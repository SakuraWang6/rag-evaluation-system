from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from rag_eval.api import create_app
from rag_eval.contracts.adapter import AdapterCapabilities
from rag_eval.contracts.run import RunManifest, RunStatus
from rag_eval.run_history import RunHistory
from rag_eval.run_presentations import RunPresentationStore
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths
from rag_eval.storage.runs import RunStore


def _manifest() -> RunManifest:
    now = datetime.now(UTC)
    return RunManifest(
        run_id="archive-run-1",
        experiment_id="archive-experiment-1",
        status=RunStatus.COMPLETED,
        bundle_id="bundle-v3",
        dataset_release_id="dataset-release-1",
        case_selection_id="selection-1",
        platform_version="test",
        adapter_id="lightrag",
        adapter_version="0.1.0",
        system_id="lightrag",
        system_version="1.5.5",
        declared_config={},
        effective_config={},
        scorer_id="test",
        scorer_version="1",
        scorer_digest="test",
        declared_capabilities=AdapterCapabilities(),
        observed_capabilities=AdapterCapabilities(),
        seed=0,
        repetitions=1,
        started_at=now,
        completed_at=now,
        execution_counts={"completed": 1},
    )


def _write_archive(root: Path) -> None:
    run = root / "runs" / "archive-run-1"
    private = run / "private-evaluation"
    private.mkdir(parents=True)
    (run / "run.json").write_text(_manifest().model_dump_json(), encoding="utf-8")
    execution = {
        "case_id": "case-1",
        "case_revision_id": "case-revision-1",
        "ordinal": 1,
        "question": "Which value is recorded?",
        "status": "completed",
        "started_at": "2026-08-30T00:00:00+00:00",
        "completed_at": "2026-08-30T00:00:01+00:00",
        "rag_result": {
            "answer": "42",
            "raw_retrieval": [],
            "ranked_retrieval": [],
            "final_context": [],
        },
    }
    evaluation = {
        "case_id": "case-1",
        "answer_evaluation": {
            "answer_scorer": {"id": "typed-answer", "version": "1", "digest": "digest"},
            "answer_accuracy": {"status": "observed", "value": 1.0, "reason": "ok"},
        },
        "failure_assessment": {
            "labels": [], "certainty": "deterministic", "reasons": [], "review_required": False,
        },
    }
    (private / "case-execution.jsonl").write_text(json.dumps(execution) + "\n", encoding="utf-8")
    (private / "case-evaluation.jsonl").write_text(json.dumps(evaluation) + "\n", encoding="utf-8")
    (private / "summary.json").write_text(
        json.dumps({"completed_case_count": 1, "mean_metrics": {"answer_accuracy": 1.0}, "evaluator": {"id": "test"}}),
        encoding="utf-8",
    )


def test_archive_run_is_available_through_normal_run_contract(tmp_path: Path, monkeypatch) -> None:
    archive = tmp_path / "archive"
    _write_archive(archive)
    primary = RunStore(tmp_path / "primary-runs")
    monkeypatch.setenv("RAG_EVAL_RUN_ARCHIVES", str(archive))
    history = RunHistory(primary)

    assert [item.run_id for item in history.list()] == ["archive-run-1"]
    cases = history.cases("archive-run-1")
    assert cases[0].question == "Which value is recorded?"
    assert cases[0].gold_answer is None
    assert history.summary("archive-run-1")["metrics"]["answer_accuracy"]["value"] == 1.0
    assert "Gold values" in history.report("archive-run-1")


def test_launcher_bootstrap_registers_system_without_starting_worker(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RAG_EVAL_BOOTSTRAP_LOCAL_SYSTEM", "1")
    monkeypatch.setenv("RAG_EVAL_LIGHTRAG_WORKER_PYTHON", str(Path(__file__).resolve()))
    service = PlatformService(PlatformPaths(tmp_path / "platform"))

    connections = service.products.connections.list() if service.products is not None else []
    assert len(connections) == 1
    assert connections[0].system_id == "lightrag"
    assert not service.runs.list()


def test_archive_run_is_visible_from_api_runs_and_cases(tmp_path: Path, monkeypatch) -> None:
    archive = tmp_path / "archive"
    _write_archive(archive)
    monkeypatch.setenv("RAG_EVAL_RUN_ARCHIVES", str(archive))
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    client = TestClient(create_app(service, start_supervisor=False))

    runs = client.get("/api/v1/runs")
    assert runs.status_code == 200
    assert runs.json()[0]["run_id"] == "archive-run-1"
    cases = client.get("/api/v1/runs/archive-run-1/cases")
    assert cases.status_code == 200
    assert cases.json()[0]["case_id"] == "case-1"
    index = client.get("/api/v1/runs/archive-run-1/cases/index")
    assert index.status_code == 200
    assert index.json() == [
        {
            "case_id": "case-1",
            "question": "Which value is recorded?",
            "status": "completed",
            "repetition": 1,
            "seed": 20260830,
            "answer_judgment": "correct",
            "evidence_judgment": "unavailable",
        }
    ]
    detail = client.get("/api/v1/runs/archive-run-1/cases/case-1")
    assert detail.status_code == 200
    assert detail.json()["case_id"] == "case-1"


def test_run_presentation_is_an_append_only_overlay_not_a_run_mutation(
    tmp_path: Path, monkeypatch
) -> None:
    archive = tmp_path / "archive"
    _write_archive(archive)
    primary = RunStore(tmp_path / "primary-runs")
    monkeypatch.setenv("RAG_EVAL_RUN_ARCHIVES", str(archive))
    presentations = RunPresentationStore(tmp_path / "product" / "run-presentations")
    history = RunHistory(primary, presentations=presentations)

    generated = history.run_view("archive-run-1")
    started = history.get("archive-run-1").started_at.strftime("%Y-%m-%d %H:%M UTC")
    assert generated["display_name"] == f"lightrag · {started} · archive-"
    assert generated["display_name_source"] == "generated"
    original_bytes = (archive / "runs" / "archive-run-1" / "run.json").read_bytes()

    first = presentations.append(
        run_id="archive-run-1",
        display_name="首次人工命名",
        actor="reviewer-a",
    )
    second = presentations.append(
        run_id="archive-run-1",
        display_name="最终运行名称",
        actor="reviewer-b",
        note="rename after review",
    )

    assert [item.revision for item in first.history] == [1]
    assert [item.revision for item in second.history] == [1, 2]
    assert history.run_view("archive-run-1")["display_name"] == "最终运行名称"
    assert history.run_view("archive-run-1")["display_name_source"] == "override"
    assert (archive / "runs" / "archive-run-1" / "run.json").read_bytes() == original_bytes


def test_run_presentation_api_keeps_the_original_manifest_unchanged(
    tmp_path: Path, monkeypatch
) -> None:
    archive = tmp_path / "archive"
    _write_archive(archive)
    monkeypatch.setenv("RAG_EVAL_RUN_ARCHIVES", str(archive))
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    client = TestClient(create_app(service, start_supervisor=False))
    source = archive / "runs" / "archive-run-1" / "run.json"
    original_bytes = source.read_bytes()

    response = client.put(
        "/api/v1/runs/archive-run-1/presentation",
        json={"display_name": "人工确认后的历史运行", "actor": "reviewer"},
    )

    assert response.status_code == 200
    assert response.json()["run"]["display_name"] == "人工确认后的历史运行"
    assert response.json()["run"]["display_name_source"] == "override"
    assert response.json()["presentation"]["history"][-1]["revision"] == 1
    assert source.read_bytes() == original_bytes


def test_formal_dataset_catalog_endpoint_is_separate_from_bundle2_catalog(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    client = TestClient(create_app(service, start_supervisor=False))

    response = client.get("/api/v1/product/formal-datasets")

    assert response.status_code == 200
    assert response.json() == {"releases": [], "bundles_v3": []}


def test_formal_dataset_content_endpoint_joins_pinned_case_gold_and_canonical_evidence(tmp_path: Path) -> None:
    # Reuse the existing release fixture so this API test exercises the same
    # immutable Release pins used by production, without hard-coding document
    # content into a generic unit test.
    from tests.rag_eval_platform.test_bundle_v3 import _release_context

    _authoring, formal, release, _store, _target = _release_context(tmp_path)
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    service.formal_datasets = formal
    client = TestClient(create_app(service, start_supervisor=False))

    response = client.get(f"/api/v1/product/formal-datasets/{release.release_id}/content")

    assert response.status_code == 200
    payload = response.json()
    assert payload["release"]["release_id"] == release.release_id
    assert len(payload["cases"]) == 1
    case = payload["cases"][0]
    assert case["question"] == "延迟指标对应的数值是多少？"
    assert case["gold"]["answer"]["canonical"] == "42 ms"
    assert case["gold"]["evidence"][0]["reachable"] is True
    assert case["gold"]["evidence"][0]["canonical"]["provenance"]["source_spans"]
    assert case["gold"]["mses_paths"]


def test_formal_dataset_reader_uses_persisted_case_and_document_read_models(tmp_path: Path) -> None:
    """Product reads stay available without the heavyweight Canonical snapshot."""

    from rag_eval.datasets.formal import FormalDatasetReleaseService
    from tests.rag_eval_platform.test_bundle_v3 import _release_context

    authoring, formal, release, _store, _target = _release_context(tmp_path)
    read_root = formal.releases.root / "read-models" / release.release_id
    assert (read_root / "index.json").is_file()
    assert (read_root / "cases" / f"{release.cases[0].case_id}.json").is_file()
    assert (read_root / "document.json").is_file()

    # A new service has no process memory cache.  Removing the snapshot in the
    # temporary fixture proves that the product endpoints use only the derived
    # read models after publication.
    (formal.releases.root / "canonical-snapshots" / f"{release.release_id}.json").unlink()
    fresh_formal = FormalDatasetReleaseService(
        authoring_store=authoring.store,
        release_root=formal.releases.root,
    )
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    service.formal_datasets = fresh_formal
    client = TestClient(create_app(service, start_supervisor=False))

    index = client.get(f"/api/v1/product/formal-datasets/{release.release_id}/cases")
    assert index.status_code == 200
    assert index.json()["cases"] == [
        {
            "case_id": release.cases[0].case_id,
            "question": "延迟指标对应的数值是多少？",
            "language": "zh-CN",
            "lifecycle": "frozen",
        }
    ]
    case = client.get(
        f"/api/v1/product/formal-datasets/{release.release_id}/cases/{release.cases[0].case_id}"
    )
    assert case.status_code == 200
    assert case.json()["gold"]["answer"]["canonical"] == "42 ms"
    document = client.get(f"/api/v1/product/formal-datasets/{release.release_id}/document")
    assert document.status_code == 200
    assert document.json()["blocks"]


def test_formal_dataset_document_endpoint_returns_source_ordered_highlightable_view(tmp_path: Path) -> None:
    from tests.rag_eval_platform.test_bundle_v3 import _release_context

    _authoring, formal, release, _store, _target = _release_context(tmp_path)
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    service.formal_datasets = formal
    client = TestClient(create_app(service, start_supervisor=False))

    response = client.get(f"/api/v1/product/formal-datasets/{release.release_id}/document")

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "private.docx"
    assert payload["blocks"]
    table = next(item for item in payload["blocks"] if item["kind"] == "table")
    assert table["cells"]
    assert table["object_ids"]
    assert formal.document_view(release.release_id) is formal.document_view(release.release_id)


def test_formal_dataset_content_endpoint_is_not_found_for_unknown_release(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    client = TestClient(create_app(service, start_supervisor=False))

    response = client.get("/api/v1/product/formal-datasets/unknown-release/content")

    assert response.status_code == 404
