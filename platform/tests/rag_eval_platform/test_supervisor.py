from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from rag_eval.contracts.run import ExperimentSpec, RunStatus
from rag_eval.execution import RunExecutor
from rag_eval.jobs import JobStore, JobStatus
from rag_eval.supervisor import JobSupervisor


def _idle_supervisor(tmp_path) -> JobSupervisor:
    return JobSupervisor(
        JobStore(tmp_path / "idle-jobs"),
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
