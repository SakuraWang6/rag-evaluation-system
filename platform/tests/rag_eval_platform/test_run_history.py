from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from rag_eval.api import create_app
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths


def test_launcher_bootstrap_registers_system_without_starting_worker(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("RAG_EVAL_BOOTSTRAP_LOCAL_SYSTEM", "1")
    monkeypatch.setenv(
        "RAG_EVAL_LIGHTRAG_WORKER_PYTHON",
        str(Path(__file__).resolve()),
    )
    service = PlatformService(PlatformPaths(tmp_path / "platform"))

    connections = (
        service.products.connections.list()
        if service.products is not None
        else []
    )
    assert len(connections) == 1
    assert connections[0].system_id == "lightrag"
    assert not service.run_records.list()


def test_formal_dataset_catalog_exposes_only_immutable_releases(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"))
    client = TestClient(create_app(service, start_supervisor=False))

    response = client.get("/api/v1/product/formal-datasets")

    assert response.status_code == 200
    assert response.json() == {"releases": []}


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
