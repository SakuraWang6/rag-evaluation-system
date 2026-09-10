from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_eval.api import create_app
from rag_eval.contracts.run import ExperimentSpec
from rag_eval.datasets.formal import (
    DatasetRelease,
    RuleResult,
    RuleSeverity,
    ValidationFinding,
    ValidationReport,
)
from rag_eval.execution import RunExecutor, stage_original_document
from rag_eval.products import SystemConnection
from rag_eval.runtime_admission import NewRunAdmissionError
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths
from tests.rag_eval_platform.test_bundle_v3 import _release_context


def _native_product_service(
    tmp_path: Path,
) -> tuple[PlatformService, TestClient, str]:
    _authoring, formal, release, _store, _target = _release_context(
        tmp_path / "formal-fixture"
    )
    service = PlatformService(
        PlatformPaths(tmp_path / "platform"), product_enabled=True
    )
    # The fixture owns a complete immutable Release store. Bind that store to
    # both admission and execution so the test exercises the same authority.
    service.formal_datasets = formal
    service.executor.benchmark_service = formal
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


def _preview_native_experiment(
    client: TestClient, release_id: str
) -> ExperimentSpec:
    created = client.post(
        "/api/v1/product/evaluation-drafts", json=_native_draft(release_id)
    )
    assert created.status_code == 200
    preview = client.get(
        f"/api/v1/product/evaluation-drafts/{created.json()['draft_id']}/preview"
    )
    assert preview.status_code == 200
    return ExperimentSpec.model_validate(preview.json())


def test_formal_release_preview_and_staging_use_only_the_original_docx(
    tmp_path: Path,
) -> None:
    service, client, release_id = _native_product_service(tmp_path)
    experiment = _preview_native_experiment(client, release_id)

    assert experiment.dataset_release_id == release_id
    assert "evaluation_corpus" not in experiment.adapter_config
    assert "bundle_id" not in ExperimentSpec.model_fields

    assert service.formal_datasets is not None
    benchmark = service.formal_datasets.resolve_native_benchmark(
        release_id,
        case_ids=(None if experiment.case_ids is None else tuple(experiment.case_ids)),
        seed=experiment.seed,
        expected_case_selection_id=experiment.case_selection_id,
    )
    staged = stage_original_document(benchmark, tmp_path / "run-source")
    assert staged.source_path.endswith(".docx")
    assert (tmp_path / "run-source" / staged.source_path).read_bytes() == (
        benchmark.original_docx_path.read_bytes()
    )
    canonical_records = [
        json.loads(line)
        for line in (
            tmp_path / "run-source" / str(staged.canonical_catalog_path)
        ).read_text(encoding="utf-8").splitlines()
    ]
    physical_cell = next(
        item for item in canonical_records if item["object_type"] == "cell"
    )
    assert physical_cell["attributes"]["logical_cell_id"] in {
        item["object_id"]
        for item in canonical_records
        if item["object_type"] == "logical_cell"
    }
    assert "merged_cell_origin_physical_id" in physical_cell["attributes"]
    executor = RunExecutor(service.formal_datasets, service.run_records)
    assert executor.benchmark_service is service.formal_datasets


def test_staging_rejects_source_changed_after_benchmark_resolution(
    tmp_path: Path,
) -> None:
    service, _client, release_id = _native_product_service(tmp_path)
    assert service.formal_datasets is not None
    benchmark = service.formal_datasets.resolve_native_benchmark(release_id)
    benchmark.original_docx_path.write_bytes(b"tampered-after-resolution")

    with pytest.raises(ValueError, match="immutable Benchmark identity"):
        stage_original_document(benchmark, tmp_path / "run-source")

    assert list((tmp_path / "run-source").glob("*.docx")) == []


def test_product_evaluation_write_contract_rejects_retired_fields(
    tmp_path: Path,
) -> None:
    _service, client, release_id = _native_product_service(tmp_path)
    payload = _native_draft(release_id)
    payload["bundle_id"] = "a" * 64
    payload["formal"] = False

    response = client.post("/api/v1/product/evaluation-drafts", json=payload)

    assert response.status_code == 422


def test_product_evaluation_and_system_configuration_reject_corpus_selectors(
    tmp_path: Path,
) -> None:
    service, client, release_id = _native_product_service(tmp_path)
    payload = _native_draft(release_id)
    payload["adapter_overrides"] = {"evaluation_corpus": "canonical_segments"}

    response = client.post("/api/v1/product/evaluation-drafts", json=payload)
    assert response.status_code == 422
    assert "reserved" in response.text

    response = client.post(
        "/api/v1/product/systems",
        json={
            "connection": {
                "system_id": "invalid-route",
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
    assert all(
        item.system_id != "invalid-route"
        for item in service.products.connections.list()
    )


def test_public_experiment_admission_is_directly_release_bound(
    tmp_path: Path,
) -> None:
    service, client, release_id = _native_product_service(tmp_path)
    experiment = _preview_native_experiment(client, release_id)

    created = client.post(
        "/api/v1/experiments", json=experiment.model_dump(mode="json")
    )

    assert created.status_code == 200
    assert service.experiments.get(experiment.experiment_id) == experiment
    plan = service.resolved_run_plans.list()[0]
    assert plan.benchmark_release.release_id == release_id
    assert not hasattr(plan.benchmark_release, "runtime_bundle_id")
    assert not hasattr(plan.original_document, "runtime_path")


def test_public_experiment_rejects_presegmented_configuration_without_persisting(
    tmp_path: Path,
) -> None:
    service, client, release_id = _native_product_service(tmp_path)
    experiment = _preview_native_experiment(client, release_id).model_copy(
        update={"adapter_config": {"evaluation_corpus": "benchmark_segments"}}
    )

    response = client.post(
        "/api/v1/experiments", json=experiment.model_dump(mode="json")
    )

    assert response.status_code == 400
    assert "reserved" in response.text
    assert service.experiments.list() == []
    assert service.jobs.list() == []


def test_retired_dataset_api_and_cli_are_absent(tmp_path: Path) -> None:
    _service, client, _release_id = _native_product_service(tmp_path)

    assert client.get("/api/v1/datasets").status_code == 404
    assert client.post("/api/v1/datasets", json={}).status_code == 404

    cli_source = (
        Path(__file__).resolve().parents[2] / "src" / "rag_eval" / "cli.py"
    ).read_text(encoding="utf-8")
    assert "register-dataset" not in cli_source


def test_invalid_release_is_rejected_before_experiment_or_job_persistence(
    tmp_path: Path,
) -> None:
    service, _client, release_id = _native_product_service(tmp_path)
    experiment = ExperimentSpec(
        experiment_id="missing-release",
        dataset_release_id=release_id + "-missing",
        system_id="lightrag",
        adapter_id="lightrag",
        query_config={
            "generate_answer": True,
            "retrieval_candidate_k": 20,
            "final_context_k": 5,
            "max_context_tokens": 4096,
            "generation_options": {},
        },
        metric_config={"k_values": [1, 3, 5]},
        case_selection_id="0" * 64,
    )

    with pytest.raises(NewRunAdmissionError, match="verified native snapshot"):
        service.queue_new_public_experiment(experiment)

    assert service.experiments.list() == []
    assert service.jobs.list() == []
    assert service.resolved_run_plans.list() == []


@pytest.mark.parametrize(
    "failure_mode",
    ("missing_payload", "payload_digest_mismatch", "removed", "validation_error"),
)
def test_invalid_release_state_cannot_create_a_job(
    tmp_path: Path,
    failure_mode: str,
) -> None:
    service, client, release_id = _native_product_service(tmp_path)
    experiment = _preview_native_experiment(client, release_id)
    assert service.formal_datasets is not None
    formal = service.formal_datasets
    release = formal.releases.get(release_id)

    if failure_mode == "missing_payload":
        (
            formal.releases.root
            / "payload-snapshots"
            / f"{release_id}.json"
        ).unlink()
    elif failure_mode == "payload_digest_mismatch":
        path = (
            formal.releases.root
            / "payload-snapshots"
            / f"{release_id}.json"
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["cases"][0]["draft"]["question"] = "tampered after preview"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
    elif failure_mode == "removed":
        formal.remove_from_catalog(release_id, actor="fixture-user")
    else:
        report = formal.releases.reports.get(release.validation_report_digest)
        invalid_report = ValidationReport.build(
            dataset_id=report.dataset_id,
            document_revision_id=report.document_revision_id,
            case_revision_ids=report.case_revision_ids,
            gold_revision_ids=report.gold_revision_ids,
            input_digests=report.input_digests,
            findings=report.findings
            + (
                ValidationFinding(
                    rule_id="fixture.injected_validation_error",
                    severity=RuleSeverity.ERROR,
                    result=RuleResult.FAIL,
                    message="fixture release must fail admission",
                ),
            ),
        )
        formal.releases.reports.put(invalid_report)
        release_values = {
            field: getattr(release, field)
            for field in DatasetRelease.model_fields
            if field not in {"release_id", "release_digest"}
        }
        release_values.update(
            release_version="invalid-validation-report",
            validation_report_digest=invalid_report.report_digest,
        )
        invalid_release = DatasetRelease.build(**release_values)
        formal.releases.put(invalid_release)
        experiment = experiment.model_copy(
            update={"dataset_release_id": invalid_release.release_id}
        )

    with pytest.raises(NewRunAdmissionError, match="verified native snapshot"):
        service.queue_new_public_experiment(experiment)

    assert service.experiments.list() == []
    assert service.jobs.list() == []
    assert service.resolved_run_plans.list() == []


def test_presegmented_execution_and_materialization_symbols_are_absent() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src" / "rag_eval"
    production = "\n".join(
        path.read_text(encoding="utf-8") for path in source_root.rglob("*.py")
    )

    for retired in (
        "materialize_runtime_bundle",
        "materialize_canonical_segment_documents",
        "materialize_benchmark_segment_documents",
        "execute_benchmark_case",
        "validate_canonical_segment_provenance_contract",
        "DatasetBundleStore",
    ):
        assert retired not in production


def test_leaderboard_and_admission_have_no_adapter_specific_policy() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src" / "rag_eval"
    eligibility = (source_root / "runs" / "eligibility.py").read_text(
        encoding="utf-8"
    )
    admission = (source_root / "runtime_admission.py").read_text(
        encoding="utf-8"
    ).lower()

    for forbidden in ("adapter_id", "system_id", "execution_view", "diagnostic_only"):
        assert forbidden not in eligibility
    for forbidden in (
        "lightrag",
        "rag-anything",
        "gold_evidence",
        "gold_eligibility",
        "adaptercapabilities",
    ):
        assert forbidden not in admission


def test_webui_exposes_only_release_based_evaluation_creation() -> None:
    root = Path(__file__).resolve().parents[3] / "webui" / "src"
    api_source = (root / "api.ts").read_text(encoding="utf-8")
    product_source = (root / "components" / "ProductPages.tsx").read_text(
        encoding="utf-8"
    )
    wizard_source = product_source.split("export function NewEvaluationPage", 1)[1]

    assert "registerDataset" not in api_source
    assert "uploadDataset" not in api_source
    assert "selectedLegacyBundle" not in wizard_source
    assert "dataset_release_id: selectedRelease!.release_id" in wizard_source
    assert "bundle_id:" not in wizard_source
