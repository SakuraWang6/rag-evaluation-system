from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_eval.api import create_app
from rag_eval.contracts.run import ExperimentSpec
from rag_eval.datasets.bundle import DatasetBundle, case_selection_id
from rag_eval.execution import RunExecutor
from rag_eval.jobs import JobStatus
from rag_eval.products import SystemConnection
from rag_eval.runtime_admission import NewRunAdmissionError
from rag_eval.service import PlatformService
from rag_eval.systems import SystemRegistration
from rag_eval.worker.process import WorkerCommand
from tests.rag_eval_platform.test_native_formal_cutover import (
    _native_draft,
    _native_product_service,
)

pytestmark = pytest.mark.native_v2_characterization


def _native_experiment(
    tmp_path: Path,
) -> tuple[PlatformService, ExperimentSpec, DatasetBundle]:
    service, client, release_id = _native_product_service(tmp_path)
    created = client.post(
        "/api/v1/product/evaluation-drafts", json=_native_draft(release_id)
    )
    assert created.status_code == 200
    preview = client.get(
        f"/api/v1/product/evaluation-drafts/{created.json()['draft_id']}/preview"
    )
    assert preview.status_code == 200
    experiment = ExperimentSpec.model_validate(preview.json())
    return service, experiment, service.datasets.get(experiment.bundle_id)


def test_admission_freezes_a_complete_immutable_resolved_plan(tmp_path: Path) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)

    reference = service.admit_new_public_experiment(experiment, bundle)
    plan = service.resolved_run_plans.get(reference)

    assert plan.schema_version == "2.0"
    assert plan.experiment_id == experiment.experiment_id
    assert plan.benchmark_release.release_id == experiment.dataset_release_id
    assert plan.benchmark_release.runtime_bundle_id == experiment.bundle_id
    assert plan.original_document.runtime_path.endswith(".docx")
    assert plan.system.system_id == experiment.system_id
    assert plan.system.adapter_id == experiment.adapter_id
    assert plan.system.worker_profile_id == "lightrag"
    assert plan.system.worker_profile_version == "1.0.1"
    assert plan.query_config.retrieval_candidate_k == 20
    assert plan.query_config.final_context_k == 5
    assert plan.evaluation_profile.candidate_cutoff == 20
    assert plan.evaluation_profile.ranked_cutoffs == (1, 3, 5)
    assert plan.evaluation_profile.ranked_mrr_cutoff == 5
    assert {item.metric_id for item in plan.metric_descriptors} == {
        "ranked_evidence_coverage@1",
        "ranked_complete_evidence_recall@1",
        "ranked_evidence_coverage@3",
        "ranked_complete_evidence_recall@3",
        "ranked_evidence_coverage@5",
        "ranked_complete_evidence_recall@5",
        "ranked_complete_evidence_mrr@5",
    }
    assert plan.case_ids
    assert reference == service.admit_new_public_experiment(experiment, bundle)


def test_plan_binding_checks_normalized_query_content_not_only_experiment_digest(
    tmp_path: Path,
) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    reference = service.admit_new_public_experiment(experiment, bundle)
    plan = service.resolved_run_plans.get(reference)
    inconsistent = plan.model_copy(
        update={
            "query_config": plan.query_config.model_copy(
                update={"retrieval_candidate_k": 3, "final_context_k": 1}
            )
        }
    )

    assert inconsistent.experiment_digest == plan.experiment_digest
    assert not inconsistent.matches_experiment(experiment)


@pytest.mark.parametrize(
    ("query_update", "message"),
    [
        ({"retrieval_candidate_k": None}, "retrieval_candidate_k"),
        ({"max_context_tokens": None}, "max_context_tokens"),
        ({"retrieval_candidate_k": 0}, "retrieval_candidate_k"),
        ({"retrieval_candidate_k": True}, "retrieval_candidate_k"),
        ({"final_context_k": 21}, "cannot exceed"),
        ({"generation_options": None}, "generation_options"),
        ({"unknown_cutoff": 5}, "unknown_cutoff"),
    ],
)
def test_admission_rejects_invalid_query_values_before_freezing(
    tmp_path: Path, query_update: dict[str, object], message: str
) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    query = {**experiment.query_config, **query_update}
    invalid = experiment.model_copy(
        update={"experiment_id": "invalid-query", "query_config": query}
    )

    with pytest.raises(NewRunAdmissionError, match=message):
        service.admit_new_public_experiment(invalid, bundle)

    assert service.resolved_run_plans.list() == []


def test_admission_rejects_missing_query_value_even_when_adapter_has_a_default(
    tmp_path: Path,
) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    query = dict(experiment.query_config)
    query.pop("retrieval_candidate_k")
    invalid = experiment.model_copy(
        update={
            "experiment_id": "adapter-fallback-is-forbidden",
            "query_config": query,
            "adapter_config": {
                **experiment.adapter_config,
                "retrieval_candidate_k": 100,
            },
        }
    )

    with pytest.raises(NewRunAdmissionError, match="retrieval_candidate_k"):
        service.admit_new_public_experiment(invalid, bundle)


@pytest.mark.parametrize(
    "metric_config",
    [
        {},
        {"k_values": None},
        {"k_values": [1, 3]},
        {"k_values": [1, 3, 5], "scorer_id": "unknown"},
    ],
)
def test_admission_rejects_an_incomplete_or_unknown_metric_descriptor(
    tmp_path: Path, metric_config: dict[str, object]
) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    invalid = experiment.model_copy(
        update={"experiment_id": "invalid-metrics", "metric_config": metric_config}
    )

    with pytest.raises(NewRunAdmissionError, match="metric_config"):
        service.admit_new_public_experiment(invalid, bundle)


def test_low_native_depth_is_admitted_with_top_five_descriptors(tmp_path: Path) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    low_depth = experiment.model_copy(
        update={
            "experiment_id": "low-depth",
            "query_config": {
                **experiment.query_config,
                "retrieval_candidate_k": 3,
                "final_context_k": 1,
            },
        }
    )

    reference = service.admit_new_public_experiment(low_depth, bundle)
    plan = service.resolved_run_plans.get(reference)

    assert plan.evaluation_profile.candidate_cutoff == 3
    assert plan.evaluation_profile.ranked_mrr_cutoff == 5
    assert any(item.cutoff == 5 for item in plan.metric_descriptors)


def test_builtin_rag_anything_low_depth_profile_is_a_valid_plan(
    tmp_path: Path,
) -> None:
    service, client, release_id = _native_product_service(tmp_path)
    assert service.products is not None
    profile = service.products.profiles.get("rag-anything", "1.0.1")
    service.products.save_connection(
        SystemConnection(
            system_id=profile.system_id,
            display_name="RAG-Anything",
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            python_executable=sys.executable,
        )
    )
    payload = _native_draft(release_id)
    payload.update(
        {
            "system_id": profile.system_id,
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
        }
    )

    created = client.post("/api/v1/product/evaluation-drafts", json=payload)
    preview = client.get(
        f"/api/v1/product/evaluation-drafts/{created.json()['draft_id']}/preview"
    )

    assert created.status_code == 200
    assert preview.status_code == 200
    experiment = ExperimentSpec.model_validate(preview.json())
    reference = service.admit_new_public_experiment(
        experiment, service.datasets.get(experiment.bundle_id)
    )
    plan = service.resolved_run_plans.get(reference)
    assert plan.system.worker_profile_id == "rag-anything"
    assert plan.evaluation_profile.candidate_cutoff == 3
    assert plan.evaluation_profile.ranked_mrr_cutoff == 5


def test_public_admission_rejects_a_run_without_a_benchmark_release(
    tmp_path: Path,
) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    unpinned = experiment.model_copy(
        update={"experiment_id": "unpinned", "dataset_release_id": None}
    )

    with pytest.raises(NewRunAdmissionError, match="Benchmark Release"):
        service.admit_new_public_experiment(unpinned, bundle)


def test_admission_rejects_an_explicit_empty_case_selection(tmp_path: Path) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    empty = experiment.model_copy(
        update={
            "experiment_id": "empty-selection",
            "case_ids": [],
            "case_selection_id": case_selection_id([], policy="explicit", seed=0),
        }
    )

    with pytest.raises(NewRunAdmissionError, match="at least one case"):
        service.admit_new_public_experiment(empty, bundle)


def test_public_api_rejects_an_incomplete_plan_before_persisting(
    tmp_path: Path,
) -> None:
    service, experiment, _bundle = _native_experiment(tmp_path)
    invalid = experiment.model_copy(
        update={
            "experiment_id": "api-invalid-plan",
            "query_config": {
                **experiment.query_config,
                "retrieval_candidate_k": None,
            },
        }
    )
    client = TestClient(create_app(service, start_supervisor=False))

    response = client.post(
        "/api/v1/experiments", json=invalid.model_dump(mode="json")
    )

    assert response.status_code == 400
    assert "retrieval_candidate_k" in response.text
    assert service.experiments.list() == []
    assert service.resolved_run_plans.list() == []


def test_queue_requires_and_persists_the_exact_resolved_plan_reference(
    tmp_path: Path,
) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    reference = service.admit_new_public_experiment(experiment, bundle)

    job = service.queue_new_public_experiment(experiment, bundle)

    assert job.resolved_plan_path == reference.path
    assert job.resolved_plan_digest == reference.digest
    assert service.resolved_run_plans.get(reference).evaluation_profile is not None


def test_resolved_plan_digest_fails_closed_after_file_tampering(tmp_path: Path) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    reference = service.admit_new_public_experiment(experiment, bundle)
    path = service.paths.home / reference.path
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["system"]["system_config_digest"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="digest mismatch"):
        service.resolved_run_plans.get(reference)


def test_executor_rejects_a_worker_command_that_does_not_match_the_plan(
    tmp_path: Path,
) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    reference = service.admit_new_public_experiment(experiment, bundle)
    plan = service.resolved_run_plans.get(reference)
    mismatched = WorkerCommand(
        adapter_id=plan.system.adapter_id,
        adapter_factory="rag_eval.adapters.fake:create_worker_definition",
        python_executable=sys.executable,
        environment={},
        request_timeout_seconds=plan.system.worker_request_timeout_seconds,
    )

    with pytest.raises(ValueError, match="Worker command does not match"):
        service.executor.execute(
            experiment,
            mismatched,
            run_id="must-not-start",
            resolved_plan=plan,
            resolved_plan_reference=reference,
        )

    assert not (service.paths.runs / "must-not-start").exists()


def test_one_experiment_id_cannot_be_rebound_to_a_different_plan(
    tmp_path: Path,
) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    service.admit_new_public_experiment(experiment, bundle)
    changed = experiment.model_copy(
        update={
            "query_config": {
                **experiment.query_config,
                "retrieval_candidate_k": 3,
                "final_context_k": 1,
            }
        }
    )

    with pytest.raises(ValueError, match="different immutable resolved plan"):
        service.admit_new_public_experiment(changed, bundle)


def test_resolved_plan_persists_system_identity_without_secret_values(
    tmp_path: Path,
) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    service.systems.register(
        SystemRegistration(
            system_id="secret-system",
            adapter_id="fake",
            adapter_factory="rag_eval.adapters.fake:create_worker_definition",
            python_executable=sys.executable,
            environment={"SECRET_TOKEN": "must-not-enter-the-plan"},
        )
    )
    registered = experiment.model_copy(
        update={
            "experiment_id": "secret-free-plan",
            "system_id": "secret-system",
            "adapter_id": "fake",
        }
    )

    reference = service.admit_new_public_experiment(registered, bundle)
    plan_bytes = (service.paths.home / reference.path).read_text(encoding="utf-8")

    assert "must-not-enter-the-plan" not in plan_bytes
    assert "SECRET_TOKEN" not in plan_bytes
    assert service.resolved_run_plans.get(reference).system.worker_profile_kind == (
        "registered_system"
    )


def test_queue_fails_when_the_worker_profile_drifted_after_admission(
    tmp_path: Path,
) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    service.admit_new_public_experiment(experiment, bundle)
    assert service.products is not None
    connection = service.products.get_connection(experiment.system_id)
    service.products.save_connection(
        connection.model_copy(
            update={
                "request_timeout_seconds": connection.request_timeout_seconds + 1
            }
        )
    )

    with pytest.raises(ValueError, match="different immutable resolved plan"):
        service.queue_new_public_experiment(experiment, bundle)

    assert service.jobs.list() == []


def test_supervisor_rejects_worker_profile_drift_after_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, experiment, bundle = _native_experiment(tmp_path)
    job = service.queue_new_public_experiment(experiment, bundle)
    assert service.products is not None
    connection = service.products.get_connection(experiment.system_id)
    service.products.save_connection(
        connection.model_copy(
            update={
                "request_timeout_seconds": connection.request_timeout_seconds + 1
            }
        )
    )
    executed = False

    def forbidden_execute(*_args: object, **_kwargs: object) -> object:
        nonlocal executed
        executed = True
        raise AssertionError("executor must not start after plan drift")

    monkeypatch.setattr(RunExecutor, "execute", forbidden_execute)

    assert service.supervisor.run_once() is True
    failed = service.jobs.get(job.job_id)
    assert failed.status == JobStatus.FAILED
    assert "drifted" in (failed.error or "")
    assert executed is False
