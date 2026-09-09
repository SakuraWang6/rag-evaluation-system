from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_eval.api import create_app
from rag_eval.cli import main as cli_main
from rag_eval.contracts.run import ExperimentSpec
from rag_eval.datasets.bundle import case_selection_id
from rag_eval.execution import (
    RunExecutor,
    execution_view_identity,
    stage_original_document,
)
from rag_eval.products import SystemConnection
from rag_eval.runtime_admission import NewRunAdmissionError
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths
from rag_eval.systems import SystemRegistration
from tests.rag_eval_platform.test_bundle_store import write_bundle
from tests.rag_eval_platform.test_bundle_v3 import _release_context


def _registered_legacy_api(
    tmp_path: Path,
    *,
    primary_corpus: object | None = None,
    formal_projection: dict[str, object] | None = None,
) -> tuple[PlatformService, TestClient, str]:
    source = tmp_path / "bundle"
    source.mkdir()
    write_bundle(source)
    if primary_corpus is not None or formal_projection is not None:
        manifest_path = source / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if primary_corpus is not None:
            manifest.setdefault("metadata", {})[
                "primary_evaluation_corpus"
            ] = primary_corpus
        if formal_projection is not None:
            manifest.setdefault("metadata", {})[
                "formal_runtime_projection"
            ] = formal_projection
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    service = PlatformService(
        PlatformPaths(tmp_path / "platform"), product_enabled=False
    )
    bundle = service.datasets.register(source)
    service.systems.register(
        SystemRegistration(
            system_id="fake-rag",
            adapter_id="fake",
            adapter_factory="rag_eval.adapters.fake:create_worker_definition",
            python_executable=sys.executable,
        )
    )
    return service, TestClient(create_app(service, start_supervisor=False)), bundle.bundle_id


def _experiment(bundle_id: str, *, experiment_id: str = "experiment-1") -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id=experiment_id,
        bundle_id=bundle_id,
        system_id="fake-rag",
        adapter_id="fake",
        case_selection_id=case_selection_id(["case-1"], policy="all", seed=0),
    )


def _native_product_service(
    tmp_path: Path,
) -> tuple[PlatformService, TestClient, str]:
    _authoring, formal, release, _store, _target = _release_context(
        tmp_path / "formal-fixture"
    )
    service = PlatformService(
        PlatformPaths(tmp_path / "platform"), product_enabled=True
    )
    service.formal_datasets = formal
    assert service.products is not None
    profile = service.products.profiles.get("lightrag", "1.0.1")
    service.products.save_connection(
        SystemConnection(
            system_id=profile.system_id,
            display_name="Native system",
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            python_executable=sys.executable,
        )
    )
    return (
        service,
        TestClient(create_app(service, start_supervisor=False)),
        release.release_id,
    )


def _native_draft(release_id: str) -> dict[str, object]:
    return {
        "mode": "basic",
        "dataset_release_id": release_id,
        "system_id": "lightrag",
        "profile_id": "lightrag",
        "profile_version": "1.0.1",
        "display_name": "native formal run",
        "adapter_overrides": {},
        "query_overrides": {},
        "metric_overrides": {},
        "case_ids": None,
        "seed": 0,
        "repetitions": 1,
    }


@pytest.mark.native_v2_characterization
def test_formal_release_preview_materializes_only_the_original_docx_for_ingestion(
    tmp_path: Path,
) -> None:
    service, client, release_id = _native_product_service(tmp_path)

    created = client.post(
        "/api/v1/product/evaluation-drafts", json=_native_draft(release_id)
    )
    assert created.status_code == 200
    preview = client.get(
        f"/api/v1/product/evaluation-drafts/{created.json()['draft_id']}/preview"
    )
    assert preview.status_code == 200
    spec = ExperimentSpec.model_validate(preview.json())
    assert spec.dataset_release_id == release_id
    assert "evaluation_corpus" not in spec.adapter_config
    assert "benchmark_contract_digest" not in ExperimentSpec.model_fields

    bundle = service.datasets.get(spec.bundle_id)
    assert "primary_evaluation_corpus" not in bundle.manifest.metadata
    projection = bundle.manifest.metadata["formal_runtime_projection"]
    assert projection["projection_version"] == "4"
    assert projection["execution_contract"] == "native-document/v2"
    assert len(bundle.manifest.documents) == 1
    source = bundle.manifest.documents[0]
    assert source.path.endswith(".docx")
    assert (
        source.mime_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert source.metadata["execution_view"] == "native-document/v2"
    assert execution_view_identity(spec, bundle) == ("native-document/v2", False)
    executor = RunExecutor(
        service.datasets,
        service.run_records,
        dataset_release_store=service.formal_datasets.releases,
    )
    executor._validate_dataset_release_reference(spec, bundle)

    source_dir = tmp_path / "run-source"
    document = stage_original_document(bundle, source_dir)
    assert Path(document.source_path).suffix == ".docx"
    assert (source_dir / document.source_path).read_bytes() == (
        bundle.root / source.path
    ).read_bytes()


def test_native_projection_has_no_presegmented_shadow_materialization(
    tmp_path: Path,
) -> None:
    service, client, release_id = _native_product_service(tmp_path)
    created = client.post(
        "/api/v1/product/evaluation-drafts", json=_native_draft(release_id)
    )
    preview = client.get(
        f"/api/v1/product/evaluation-drafts/{created.json()['draft_id']}/preview"
    )
    bundle = service.datasets.get(preview.json()["bundle_id"])
    benchmark_before = {
        "questions": [item.model_dump(mode="json") for item in bundle.questions],
        "answers": {
            key: value.model_dump(mode="json")
            for key, value in bundle.gold_answers.items()
        },
        "evidence": {
            key: value.model_dump(mode="json")
            for key, value in bundle.gold_evidence_sets.items()
        },
    }

    native = stage_original_document(bundle, tmp_path / "native")
    assert native.source_path.endswith(".docx")
    # The execution boundary no longer accepts any corpus selector. Canonical
    # Gold remains unchanged and adjacent to the one native DOCX input.
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        stage_original_document(
            bundle,
            tmp_path / "oracle",
            primary_corpus="canonical_segments",
        )
    assert benchmark_before == {
        "questions": [item.model_dump(mode="json") for item in bundle.questions],
        "answers": {
            key: value.model_dump(mode="json")
            for key, value in bundle.gold_answers.items()
        },
        "evidence": {
            key: value.model_dump(mode="json")
            for key, value in bundle.gold_evidence_sets.items()
        },
    }


@pytest.mark.native_v2_characterization
def test_product_evaluation_write_contract_accepts_only_a_benchmark_release(
    tmp_path: Path,
) -> None:
    _service, client, release_id = _native_product_service(tmp_path)
    legacy = _native_draft(release_id)
    legacy["bundle_id"] = "a" * 64
    legacy["formal"] = False

    response = client.post("/api/v1/product/evaluation-drafts", json=legacy)

    assert response.status_code == 422


def test_product_evaluation_rejects_a_corpus_selector(
    tmp_path: Path,
) -> None:
    _service, client, release_id = _native_product_service(tmp_path)
    payload = _native_draft(release_id)
    payload["adapter_overrides"] = {"evaluation_corpus": "canonical_segments"}

    response = client.post("/api/v1/product/evaluation-drafts", json=payload)

    assert response.status_code == 422
    assert "reserved" in response.text


def test_product_system_configuration_rejects_a_corpus_selector(
    tmp_path: Path,
) -> None:
    service = PlatformService(
        PlatformPaths(tmp_path / "platform"), product_enabled=True
    )
    client = TestClient(create_app(service, start_supervisor=False))

    response = client.post(
        "/api/v1/product/systems",
        json={
            "connection": {
                "system_id": "lightrag",
                "display_name": "Invalid route override",
                "profile_id": "lightrag",
                "profile_version": "1.0.1",
                "adapter_overrides": {"evaluation_corpus": "source_document"},
            }
        },
    )

    assert response.status_code == 422
    assert "reserved" in response.text
    assert service.products is not None
    assert service.products.connections.list() == []


@pytest.mark.native_v2_characterization
def test_public_experiment_create_and_queue_reject_presegmented_routes(
    tmp_path: Path,
) -> None:
    service, client, bundle_id = _registered_legacy_api(tmp_path)
    presegmented = _experiment(bundle_id).model_copy(
        update={"adapter_config": {"evaluation_corpus": "canonical_segments"}}
    )

    created = client.post(
        "/api/v1/experiments", json=presegmented.model_dump(mode="json")
    )
    assert created.status_code == 400
    assert "reserved" in created.text
    assert service.experiments.list() == []
    assert service.jobs.list() == []


def test_public_experiment_create_rejects_the_benchmark_segment_contract(
    tmp_path: Path,
) -> None:
    service, client, bundle_id = _registered_legacy_api(tmp_path)
    presegmented = _experiment(
        bundle_id, experiment_id="benchmark-contract"
    ).model_dump(mode="json")
    presegmented.update(
        {
            "dataset_release_id": "release-1",
            "benchmark_contract_version": "rag-benchmark-contract/1",
            "benchmark_contract_digest": "a" * 64,
        }
    )

    response = client.post("/api/v1/experiments", json=presegmented)

    assert response.status_code == 422
    assert "Extra inputs are not permitted" in response.text
    assert service.experiments.list() == []


def test_public_experiment_rejects_a_presegmented_bundle_default(
    tmp_path: Path,
) -> None:
    service, client, bundle_id = _registered_legacy_api(
        tmp_path, primary_corpus="canonical_segments"
    )

    response = client.post(
        "/api/v1/experiments",
        json=_experiment(bundle_id).model_dump(mode="json"),
    )

    assert response.status_code == 400
    assert "pre-segmented" in response.text
    assert service.experiments.list() == []


def test_release_bound_public_experiment_rejects_a_modified_projection(
    tmp_path: Path,
) -> None:
    service, client, release_id = _native_product_service(tmp_path)
    draft = client.post(
        "/api/v1/product/evaluation-drafts", json=_native_draft(release_id)
    )
    preview = client.get(
        f"/api/v1/product/evaluation-drafts/{draft.json()['draft_id']}/preview"
    )
    experiment = ExperimentSpec.model_validate(preview.json())
    native_bundle = service.datasets.get(experiment.bundle_id)

    staging = tmp_path / "non-docx-projection"
    shutil.copytree(native_bundle.root, staging)
    manifest_path = staging / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_relative = manifest["documents"][0]["path"]
    new_relative = "documents/not-a-docx.txt"
    (staging / old_relative).rename(staging / new_relative)
    manifest["documents"][0]["path"] = new_relative
    manifest["documents"][0]["mime_type"] = "text/plain"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (staging / "checksums.json").unlink()
    invalid_bundle = service.datasets.register(staging)
    experiment = experiment.model_copy(
        update={
            "experiment_id": "non-docx-projection",
            "bundle_id": invalid_bundle.bundle_id,
        }
    )

    response = client.post(
        "/api/v1/experiments", json=experiment.model_dump(mode="json")
    )

    assert response.status_code == 400
    assert "exact runtime projection" in response.text
    assert service.experiments.list() == []


@pytest.mark.native_v2_characterization
def test_release_bound_public_experiment_rejects_modified_benchmark_content(
    tmp_path: Path,
) -> None:
    service, client, release_id = _native_product_service(tmp_path)
    draft = client.post(
        "/api/v1/product/evaluation-drafts", json=_native_draft(release_id)
    )
    preview = client.get(
        f"/api/v1/product/evaluation-drafts/{draft.json()['draft_id']}/preview"
    )
    experiment = ExperimentSpec.model_validate(preview.json())
    native_bundle = service.datasets.get(experiment.bundle_id)

    staging = tmp_path / "modified-benchmark-projection"
    shutil.copytree(native_bundle.root, staging)
    questions_path = staging / "questions.jsonl"
    questions = [
        json.loads(line)
        for line in questions_path.read_text(encoding="utf-8").splitlines()
    ]
    questions[0]["question"] = "A modified question must not inherit the Release pin."
    questions_path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in questions),
        encoding="utf-8",
    )
    (staging / "checksums.json").unlink()
    invalid_bundle = service.datasets.register(staging)
    experiment = experiment.model_copy(
        update={
            "experiment_id": "modified-benchmark-content",
            "bundle_id": invalid_bundle.bundle_id,
        }
    )

    response = client.post(
        "/api/v1/experiments", json=experiment.model_dump(mode="json")
    )

    assert response.status_code == 400
    assert "exact runtime projection" in response.text
    assert service.experiments.list() == []


def test_cli_create_and_run_apply_the_same_native_admission(
    tmp_path: Path,
) -> None:
    service, _client, bundle_id = _registered_legacy_api(tmp_path)
    presegmented = _experiment(bundle_id).model_copy(
        update={"adapter_config": {"evaluation_corpus": "canonical_segments"}}
    )
    spec_path = tmp_path / "presegmented-experiment.json"
    spec_path.write_text(presegmented.model_dump_json(), encoding="utf-8")

    with pytest.raises(NewRunAdmissionError, match="reserved"):
        cli_main(
            [
                "--home",
                str(service.paths.home),
                "create-experiment",
                str(spec_path),
            ]
        )
    service.experiments.create(presegmented)
    with pytest.raises(NewRunAdmissionError, match="reserved"):
        cli_main(
            ["--home", str(service.paths.home), "run", presegmented.experiment_id]
        )
    assert service.jobs.list() == []


def test_presegmented_execution_and_materialization_symbols_are_absent() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src" / "rag_eval"
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in source_root.rglob("*.py")
    )

    for retired in (
        "materialize_canonical_segment_documents",
        "materialize_benchmark_segment_documents",
        "execute_benchmark_case",
        "validate_canonical_segment_provenance_contract",
    ):
        assert retired not in production


def test_leaderboard_eligibility_has_no_adapter_or_route_policy() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "rag_eval"
        / "runs"
        / "eligibility.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "adapter_id",
        "system_id",
        "execution_view",
        "diagnostic_only",
    ):
        assert forbidden not in source


@pytest.mark.native_v2_characterization
def test_new_run_admission_does_not_depend_on_adapter_or_gold_policy() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "rag_eval"
        / "runtime_admission.py"
    ).read_text(encoding="utf-8").lower()

    for forbidden in (
        "lightrag",
        "rag-anything",
        "gold_evidence",
        "gold_eligibility",
        "adaptercapabilities",
    ):
        assert forbidden not in source


def test_webui_exposes_only_release_based_evaluation_creation() -> None:
    root = Path(__file__).resolve().parents[3] / "webui" / "src"
    app_source = (root / "App.tsx").read_text(encoding="utf-8")
    api_source = (root / "api.ts").read_text(encoding="utf-8")
    product_source = (root / "components" / "ProductPages.tsx").read_text(
        encoding="utf-8"
    )
    wizard_source = product_source.split("export function NewEvaluationPage", 1)[1]

    assert "createExperiment" not in app_source
    assert "queueRun" not in app_source
    assert "createExperiment:" not in api_source
    assert "queueRun:" not in api_source
    assert "selectedLegacyBundle" not in wizard_source
    assert "bundle:" not in wizard_source
    assert "dataset_release_id: selectedRelease!.release_id" in wizard_source
    assert 'bundle_id:' not in wizard_source
    assert 'formal:' not in wizard_source
