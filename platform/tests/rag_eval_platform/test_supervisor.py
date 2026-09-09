from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from rag_eval.artifact_contract import artifact_digest
from rag_eval.contracts.run import ExperimentSpec, RunStatus
from rag_eval.evaluation.unified.models import EvaluationProfile
from rag_eval.execution import RunExecutor
from rag_eval.jobs import JobStatus, JobStore
from rag_eval.runs.plans import (
    BenchmarkReleaseIdentityV2,
    NativeMetricConfigV2,
    NativeQueryConfigV2,
    OriginalDocumentIdentityV2,
    ResolvedResourceLimitsV2,
    ResolvedRunPlanStore,
    ResolvedRunPlanV2,
    ResolvedSystemIdentityV2,
    digest_json,
    formal_metric_descriptors,
)
from rag_eval.runs.records import RunRecordStateV2, RunRecordStoreV2
from rag_eval.supervisor import JobSupervisor


def _idle_supervisor(tmp_path) -> JobSupervisor:
    plans = ResolvedRunPlanStore(tmp_path / "idle-resolved-run-plans")
    return JobSupervisor(
        JobStore(tmp_path / "idle-jobs"),
        plans,
        RunRecordStoreV2(tmp_path / "idle-runs", plans),
        SimpleNamespace(),
        RunExecutor(SimpleNamespace(), SimpleNamespace()),  # type: ignore[arg-type]
        SimpleNamespace(),
    )


def test_supervisor_can_start_stop_and_start_again(tmp_path) -> None:
    supervisor = _idle_supervisor(tmp_path)

    supervisor.start()
    first_thread = supervisor._thread
    assert first_thread is not None and first_thread.is_alive()
    supervisor.stop()
    assert not first_thread.is_alive()
    assert supervisor._thread is None

    supervisor.start()
    second_thread = supervisor._thread
    assert second_thread is not None and second_thread.is_alive()
    assert second_thread is not first_thread
    supervisor.stop()
    supervisor.stop()
    assert not second_thread.is_alive()
    assert supervisor._thread is None


def test_supervisor_rejects_overlapping_start(tmp_path) -> None:
    supervisor = _idle_supervisor(tmp_path)
    supervisor.start()
    try:
        with pytest.raises(RuntimeError, match="already running"):
            supervisor.start()
    finally:
        supervisor.stop()


def test_supervisor_retains_a_timed_out_thread_as_the_single_writer(
    tmp_path, monkeypatch
) -> None:
    supervisor = _idle_supervisor(tmp_path)
    entered = threading.Event()
    release = threading.Event()

    def blocked_loop() -> None:
        entered.set()
        release.wait(timeout=1)

    monkeypatch.setattr(supervisor, "_loop", blocked_loop)
    monkeypatch.setattr("rag_eval.supervisor._STOP_TIMEOUT_SECONDS", 0.01)
    supervisor.start()
    assert entered.wait(timeout=1)
    thread = supervisor._thread
    assert thread is not None

    with pytest.raises(RuntimeError, match="did not stop"):
        supervisor.stop()
    assert supervisor._thread is thread
    with pytest.raises(RuntimeError, match="already running"):
        supervisor.start()

    release.set()
    supervisor.stop()
    assert supervisor._thread is None


def test_supervisor_keeps_the_formal_release_store_for_queued_runs(tmp_path, monkeypatch) -> None:
    """A formal release validated in preview must remain available at execution."""

    formal_store = object()
    jobs = JobStore(tmp_path / "jobs")
    plans = ResolvedRunPlanStore(tmp_path / "resolved-run-plans")
    experiment = ExperimentSpec(
        experiment_id="formal-supervisor-test",
        bundle_id="a" * 64,
        dataset_release_id="dataset-release-formal-test",
        system_id="fixture-system",
        adapter_id="fixture-adapter",
        adapter_config={},
        query_config={
            "generate_answer": True,
            "retrieval_candidate_k": 3,
            "final_context_k": 1,
            "max_context_tokens": 2000,
            "generation_options": {},
        },
        metric_config={"k_values": [1, 3, 5]},
        case_selection_id="selection-test",
        seed=0,
        repetitions=1,
    )
    system_identity = ResolvedSystemIdentityV2(
        system_id="fixture-system",
        adapter_id="fixture-adapter",
        adapter_factory="fixture.worker:create",
        worker_profile_kind="registered_system",
        worker_profile_id="fixture-profile",
        worker_profile_version="1",
        worker_profile_digest="sha256:" + "b" * 64,
        system_config_digest="sha256:" + "c" * 64,
        execution_provider="fixture",
        worker_request_timeout_seconds=10,
    )
    query_config = NativeQueryConfigV2.model_validate(experiment.query_config)
    profile = EvaluationProfile(
        candidate_cutoff=3,
        ranked_cutoffs=(1, 3, 5),
        ranked_mrr_cutoff=5,
        context_budget=2000,
    )
    plan = ResolvedRunPlanV2(
        experiment_id=experiment.experiment_id,
        experiment_digest=artifact_digest(experiment),
        benchmark_release=BenchmarkReleaseIdentityV2(
            release_id="dataset-release-formal-test",
            release_digest="d" * 64,
            validation_report_digest="e" * 64,
            runtime_bundle_id="a" * 64,
        ),
        original_document=OriginalDocumentIdentityV2(
            document_id="fixture-document",
            source_sha256="f" * 64,
            runtime_path="documents/fixture.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        system=system_identity,
        adapter_config_digest=digest_json(experiment.adapter_config),
        query_config=query_config,
        metric_config=NativeMetricConfigV2.model_validate(experiment.metric_config),
        evaluation_profile=profile,
        metric_descriptors=formal_metric_descriptors(profile),
        case_ids=("case-1",),
        case_selection_id=experiment.case_selection_id,
        seed=0,
        repetitions=1,
        resource_limits=ResolvedResourceLimitsV2(
            worker_request_timeout_seconds=10,
            max_context_tokens=2000,
        ),
    )
    job = jobs.create(
        experiment,
        resolved_plan=plans.create(plan),
        execution_provider="fixture",
    )
    outer_executor = RunExecutor(
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        dataset_release_store=formal_store,  # type: ignore[arg-type]
    )
    observed: list[tuple[object, object]] = []
    run_records = SimpleNamespace(
        get=lambda _run_id: SimpleNamespace(state=RunRecordStateV2.COMPLETED)
    )

    def execute(self, *_args, **_kwargs):
        observed.append(
            (self.dataset_release_store, _kwargs.get("resolved_plan"))
        )
        return SimpleNamespace(status=RunStatus.COMPLETED, run_id="formal-run")

    monkeypatch.setattr(RunExecutor, "execute", execute)
    supervisor = JobSupervisor(
        jobs,
        plans,
        run_records,
        SimpleNamespace(
            plan_identity=lambda *_args, **_kwargs: system_identity,
            resolve=lambda *_args, **_kwargs: SimpleNamespace(
                command=SimpleNamespace(), provider="fixture", execution_metadata={}
            )
        ),
        outer_executor,
        SimpleNamespace(get=lambda _provider: SimpleNamespace()),
    )

    assert supervisor.run_once() is True
    assert observed == [(formal_store, plan)]
    assert jobs.get(job.job_id).status == JobStatus.COMPLETED
