"""Single-writer persistent job dispatcher."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Self

from rag_eval.contracts.run import RunStatus
from rag_eval.execution import RunExecutor
from rag_eval.execution_provider import ExecutionProviderRegistry
from rag_eval.jobs import JobStatus, JobStore
from rag_eval.runs.plans import (
    ResolvedRunPlanReferenceV2,
    ResolvedRunPlanStore,
)
from rag_eval.systems import SystemResolver

logger = logging.getLogger(__name__)
_STOP_TIMEOUT_SECONDS = 5.0


class JobSupervisor:
    def __init__(
        self,
        jobs: JobStore,
        resolved_run_plans: ResolvedRunPlanStore,
        systems: SystemResolver,
        executor: RunExecutor,
        providers: ExecutionProviderRegistry,
        on_run_completed: Callable[[str], object] | None = None,
    ) -> None:
        self.jobs = jobs
        self.resolved_run_plans = resolved_run_plans
        self.systems = systems
        self.executor = executor
        self.providers = providers
        self.on_run_completed = on_run_completed
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._lifecycle_lock = threading.Lock()

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._thread is not None:
                raise RuntimeError("supervisor is already running")
            self._stop.clear()
            self._wake.clear()
            self.jobs.recover()
            thread = threading.Thread(
                target=self._loop, name="rag-eval-supervisor", daemon=True
            )
            self._thread = thread
            thread.start()

    def stop(self) -> None:
        with self._lifecycle_lock:
            thread = self._thread
            if thread is None:
                return
            self._stop.set()
            self._wake.set()
        thread.join(timeout=_STOP_TIMEOUT_SECONDS)
        with self._lifecycle_lock:
            if thread.is_alive():
                # Retain the thread reference so start() cannot create a
                # second single-writer dispatcher while this one still runs.
                raise RuntimeError("supervisor did not stop within the timeout")
            if self._thread is thread:
                self._thread = None

    def notify(self) -> None:
        self._wake.set()

    def run_once(self) -> bool:
        job = self.jobs.claim_next()
        if job is None:
            return False
        try:
            plan = self.resolved_run_plans.get(
                ResolvedRunPlanReferenceV2(
                    path=job.resolved_plan_path,
                    digest=job.resolved_plan_digest,
                )
            )
            if not plan.matches_experiment(job.experiment):
                raise ValueError(
                    "queued Experiment does not match its immutable resolved plan"
                )
            if job.execution_provider != plan.system.execution_provider:
                raise ValueError(
                    "queued execution provider does not match the resolved plan"
                )
            resolved = self.systems.resolve(
                job.experiment.system_id,
                provider=job.execution_provider,
            )
            current_system_identity = self.systems.plan_identity(
                job.experiment.system_id,
                expected_adapter_id=job.experiment.adapter_id,
                provider=job.execution_provider,
            )
            if current_system_identity != plan.system:
                raise ValueError(
                    "queued system/worker profile drifted from the resolved plan"
                )

            def cancelled() -> bool:
                return self.jobs.get(job.job_id).status == JobStatus.CANCELLING

            def worker_started(run_id: str, pid: int) -> None:
                self.jobs.update_worker(job.job_id, run_id=run_id, worker_pid=pid)

            executor = RunExecutor(
                self.executor.dataset_store,
                self.executor.run_store,
                self.providers.get(resolved.provider),
                # A queued run must retain the formal-release authority used
                # by its preview; otherwise formal releases look unavailable
                # only after the supervisor claims the job.
                dataset_release_store=self.executor.dataset_release_store,
            )
            manifest = executor.execute(
                job.experiment,
                resolved.command,
                cancelled=cancelled,
                worker_started=worker_started,
                execution_metadata=resolved.execution_metadata,
                resolved_plan=plan,
            )
            current = self.jobs.get(job.job_id)
            if manifest.status == RunStatus.CANCELLED or current.status == JobStatus.CANCELLING:
                self.jobs.transition(
                    job.job_id, JobStatus.CANCELLED, run_id=manifest.run_id
                )
            else:
                self.jobs.transition(
                    job.job_id, JobStatus.COMPLETED, run_id=manifest.run_id
                )
                if self.on_run_completed is not None:
                    # Semantic review is scheduled only after the immutable
                    # Run and its job are complete. The callback must return
                    # quickly (it owns any background model work), so a slow
                    # local LLM cannot block the single-writer supervisor.
                    try:
                        self.on_run_completed(manifest.run_id)
                    except Exception:  # pragma: no cover - defensive callback boundary
                        logger.exception(
                            "could not schedule post-run review for %s",
                            manifest.run_id,
                        )
        except Exception as exc:
            current = self.jobs.get(job.job_id)
            target = (
                JobStatus.CANCELLED
                if current.status == JobStatus.CANCELLING
                else JobStatus.FAILED
            )
            self.jobs.transition(job.job_id, target, error=str(exc) or type(exc).__name__)
            logger.exception("RAG evaluation job %s failed", job.job_id)
        return True

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self.run_once():
                continue
            self._wake.wait(1)
            self._wake.clear()

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()
