"""Persistent single-supervisor job state machine."""

from __future__ import annotations

import subprocess
import threading
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from rag_eval.contracts.run import ExperimentSpec
from rag_eval.runs.plans import ResolvedRunPlanReferenceV2
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.runs import safe_id
from rag_eval.worker.process import terminate_process_group


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


TERMINAL_JOB_STATUSES = {
    JobStatus.CANCELLED,
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.INTERRUPTED,
}


class JobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: JobStatus
    experiment: ExperimentSpec
    resolved_plan_path: str = Field(min_length=1)
    resolved_plan_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    created_at: datetime
    updated_at: datetime
    run_id: str | None = None
    worker_pid: int | None = Field(default=None, ge=1)
    execution_provider: str = Field(min_length=1)
    error: str | None = None


_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.RUNNING: {
        JobStatus.CANCELLING,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.INTERRUPTED,
    },
    JobStatus.CANCELLING: {
        JobStatus.CANCELLED,
        JobStatus.FAILED,
        JobStatus.INTERRUPTED,
    },
    JobStatus.CANCELLED: set(),
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
    JobStatus.INTERRUPTED: set(),
}


class JobStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def create(
        self,
        experiment: ExperimentSpec,
        *,
        resolved_plan: ResolvedRunPlanReferenceV2,
        execution_provider: str,
    ) -> JobRecord:
        now = datetime.now(UTC)
        record = JobRecord(
            job_id=uuid.uuid4().hex,
            status=JobStatus.QUEUED,
            experiment=experiment,
            resolved_plan_path=resolved_plan.path,
            resolved_plan_digest=resolved_plan.digest,
            created_at=now,
            updated_at=now,
            execution_provider=execution_provider,
        )
        with self._lock:
            self._write(record)
        return record

    def get(self, job_id: str) -> JobRecord:
        path = self.root / f"{safe_id(job_id)}.json"
        return JobRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[JobRecord]:
        return [
            JobRecord.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.root.glob("*.json"))
        ]

    def transition(
        self,
        job_id: str,
        status: JobStatus,
        *,
        run_id: str | None = None,
        worker_pid: int | None = None,
        error: str | None = None,
    ) -> JobRecord:
        with self._lock:
            current = self.get(job_id)
            if status not in _TRANSITIONS[current.status]:
                raise ValueError(f"invalid job transition: {current.status} -> {status}")
            updated = current.model_copy(
                update={
                    "status": status,
                    "updated_at": datetime.now(UTC),
                    "run_id": run_id if run_id is not None else current.run_id,
                    "worker_pid": worker_pid
                    if worker_pid is not None
                    else current.worker_pid,
                    "error": error,
                }
            )
            self._write(updated)
            return updated

    def update_worker(self, job_id: str, *, run_id: str, worker_pid: int) -> JobRecord:
        with self._lock:
            current = self.get(job_id)
            if current.status not in {JobStatus.RUNNING, JobStatus.CANCELLING}:
                raise ValueError("worker metadata can be attached only to an active job")
            updated = current.model_copy(
                update={
                    "run_id": run_id,
                    "worker_pid": worker_pid,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._write(updated)
            return updated

    def claim_next(self) -> JobRecord | None:
        with self._lock:
            queued = [job for job in self.list() if job.status == JobStatus.QUEUED]
            if not queued:
                return None
            selected = min(queued, key=lambda job: (job.created_at, job.job_id))
            return self.transition(selected.job_id, JobStatus.RUNNING)

    def request_cancel(self, job_id: str) -> JobRecord:
        with self._lock:
            job = self.get(job_id)
            if job.status == JobStatus.QUEUED:
                return self.transition(job_id, JobStatus.CANCELLED)
            if job.status == JobStatus.RUNNING:
                return self.transition(job_id, JobStatus.CANCELLING)
            return job

    def recover(self) -> list[JobRecord]:
        recovered: list[JobRecord] = []
        for job in self.list():
            if job.status not in {JobStatus.RUNNING, JobStatus.CANCELLING}:
                continue
            if job.worker_pid is not None:
                terminate_verified_worker(job.worker_pid, job.run_id)
            recovered.append(
                self.transition(
                    job.job_id,
                    JobStatus.INTERRUPTED,
                    error="supervisor restarted while job was active",
                )
            )
        return recovered

    def _write(self, record: JobRecord) -> None:
        atomic_write_json(
            self.root / f"{safe_id(record.job_id)}.json",
            record.model_dump(mode="json"),
        )


def terminate_verified_worker(pid: int, run_id: str | None) -> bool:
    """Terminate only a PID whose command still identifies this worker/run."""
    if not run_id:
        return False
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        check=False,
        capture_output=True,
        text=True,
    )
    command = result.stdout.strip()
    if "rag_eval.worker.main" not in command or run_id not in command:
        return False
    return terminate_process_group(pid)
