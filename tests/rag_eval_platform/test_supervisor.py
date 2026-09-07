from __future__ import annotations

from types import SimpleNamespace

from rag_eval.contracts.run import ExperimentSpec, RunStatus
from rag_eval.execution import RunExecutor
from rag_eval.jobs import JobStore, JobStatus
from rag_eval.supervisor import JobSupervisor


def test_supervisor_keeps_the_formal_release_store_for_queued_runs(tmp_path, monkeypatch) -> None:
    """A formal release validated in preview must remain available at execution."""

    formal_store = object()
    jobs = JobStore(tmp_path / "jobs")
    job = jobs.create(
        ExperimentSpec(
            experiment_id="formal-supervisor-test",
            bundle_id="bundle-runtime-test",
            dataset_release_id="dataset-release-formal-test",
            system_id="fixture-system",
            adapter_id="fixture-adapter",
            adapter_config={},
            query_config={},
            metric_config={},
            case_selection_id="selection-test",
            seed=0,
            repetitions=1,
        ),
        execution_provider="fixture",
    )
    outer_executor = RunExecutor(
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        dataset_release_store=formal_store,  # type: ignore[arg-type]
    )
    observed: list[object] = []

    def execute(self, *_args, **_kwargs):
        observed.append(self.dataset_release_store)
        return SimpleNamespace(status=RunStatus.COMPLETED, run_id="formal-run")

    monkeypatch.setattr(RunExecutor, "execute", execute)
    supervisor = JobSupervisor(
        jobs,
        SimpleNamespace(
            resolve=lambda *_args, **_kwargs: SimpleNamespace(
                command=SimpleNamespace(), provider="fixture", execution_metadata={}
            )
        ),
        outer_executor,
        SimpleNamespace(get=lambda _provider: SimpleNamespace()),
    )

    assert supervisor.run_once() is True
    assert observed == [formal_store]
    assert jobs.get(job.job_id).status == JobStatus.COMPLETED
