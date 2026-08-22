"""Single-writer persistent job dispatcher."""

from __future__ import annotations

import logging
import threading
from typing import Self

from rag_eval.contracts.run import RunStatus
from rag_eval.execution import RunExecutor
from rag_eval.jobs import JobStatus, JobStore
from rag_eval.systems import SystemRegistry

logger = logging.getLogger(__name__)


class JobSupervisor:
    def __init__(
        self,
        jobs: JobStore,
        systems: SystemRegistry,
        executor: RunExecutor,
    ) -> None:
        self.jobs = jobs
        self.systems = systems
        self.executor = executor
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("supervisor is already running")
        self.jobs.recover()
        self._thread = threading.Thread(
            target=self._loop, name="rag-eval-supervisor", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None

    def notify(self) -> None:
        self._wake.set()

    def run_once(self) -> bool:
        job = self.jobs.claim_next()
        if job is None:
            return False
        try:
            registration = self.systems.get(job.experiment.system_id)

            def cancelled() -> bool:
                return self.jobs.get(job.job_id).status == JobStatus.CANCELLING

            def worker_started(run_id: str, pid: int) -> None:
                self.jobs.update_worker(job.job_id, run_id=run_id, worker_pid=pid)

            manifest = self.executor.execute(
                job.experiment,
                registration.worker_command(),
                cancelled=cancelled,
                worker_started=worker_started,
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
