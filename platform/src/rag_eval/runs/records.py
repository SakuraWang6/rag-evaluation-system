"""Strict orchestration-only records for Native v2 Runs."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.runs.artifacts import ArtifactV2Reader
from rag_eval.runs.models import ARTIFACT_V2_DIRECTORY, ARTIFACT_V2_MANIFEST
from rag_eval.runs.plans import (
    ResolvedRunPlanReferenceV2,
    ResolvedRunPlanStore,
    ResolvedRunPlanV2,
)
from rag_eval.storage.atomic import atomic_write_json

RUN_RECORD_V2_SCHEMA_VERSION = "2.0"
RUN_RECORD_V2_FILENAME = "run-record.json"
ARTIFACT_V2_REFERENCE = f"{ARTIFACT_V2_DIRECTORY}/{ARTIFACT_V2_MANIFEST}"
_SAFE_ID_PATTERN = r"^[A-Za-z0-9_-]+$"


class RunRecordStateV2(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunRecordV2(BaseModel):
    """Mutable orchestration state with no evaluation payload.

    Gold, traces, metrics, provenance, judgments and leaderboard eligibility
    belong exclusively to Artifact 2.0.  ``extra='forbid'`` makes accidental
    duplication into this record a contract violation rather than a silent
    second source of truth.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2.0"] = RUN_RECORD_V2_SCHEMA_VERSION
    run_id: str = Field(pattern=_SAFE_ID_PATTERN)
    experiment_id: str = Field(pattern=_SAFE_ID_PATTERN)
    resolved_plan_path: str = Field(min_length=1)
    resolved_plan_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    state: RunRecordStateV2
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    execution_error: str | None = None
    artifact_path: Literal["artifact-v2/artifact.json"] | None = None
    artifact_digest: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def validate_state(self) -> RunRecordV2:
        reference = PurePosixPath(self.resolved_plan_path)
        if reference.is_absolute() or ".." in reference.parts:
            raise ValueError("resolved_plan_path must be a safe relative path")
        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("Run start precedes creation")
        if self.completed_at is not None:
            floor = self.started_at or self.created_at
            if self.completed_at < floor:
                raise ValueError("Run completion precedes its active lifetime")

        has_artifact = self.artifact_path is not None or self.artifact_digest is not None
        if self.state == RunRecordStateV2.COMPLETED:
            if (
                self.started_at is None
                or self.completed_at is None
                or self.artifact_path is None
                or self.artifact_digest is None
            ):
                raise ValueError(
                    "COMPLETED requires start/completion timestamps and a verified Artifact 2.0 reference"
                )
            if self.execution_error is not None:
                raise ValueError("COMPLETED cannot carry an execution error")
        elif has_artifact:
            raise ValueError("only COMPLETED may reference Artifact 2.0")

        if self.state == RunRecordStateV2.PENDING:
            if any(
                value is not None
                for value in (
                    self.started_at,
                    self.completed_at,
                    self.execution_error,
                )
            ):
                raise ValueError("PENDING cannot contain execution state")
        elif self.state == RunRecordStateV2.RUNNING:
            if self.started_at is None or any(
                value is not None
                for value in (self.completed_at, self.execution_error)
            ):
                raise ValueError("RUNNING requires only a start timestamp")
        elif self.state == RunRecordStateV2.FAILED:
            if self.completed_at is None or not (self.execution_error or "").strip():
                raise ValueError("FAILED requires a completion timestamp and execution error")
        elif self.state == RunRecordStateV2.CANCELLED:
            if self.completed_at is None:
                raise ValueError("CANCELLED requires a completion timestamp")
            if self.execution_error is not None:
                raise ValueError("CANCELLED cannot carry an execution error")
        return self


def artifact_plan_binding_errors(
    reader: ArtifactV2Reader,
    plan: ResolvedRunPlanV2,
) -> tuple[str, ...]:
    """Return exact authority mismatches between one Artifact and frozen Plan."""

    manifest = reader.manifest()
    benchmark = manifest.benchmark_identity
    errors: list[str] = []
    expected_benchmark = (
        plan.benchmark_release.release_id,
        plan.benchmark_release.release_digest,
        plan.benchmark_release.runtime_bundle_id,
        plan.case_selection_id,
    )
    observed_benchmark = (
        benchmark.dataset_release_id,
        benchmark.dataset_release_digest,
        benchmark.bundle_id,
        benchmark.case_selection_id,
    )
    if observed_benchmark != expected_benchmark:
        errors.append("resolved-plan:benchmark-identity")

    source_pins = {
        (item.document_id, item.source_sha256)
        for item in benchmark.source_identities
    }
    expected_source = {
        (
            plan.original_document.document_id,
            plan.original_document.source_sha256,
        )
    }
    if source_pins != expected_source:
        errors.append("resolved-plan:original-document")

    expected_case_keys = {
        (case_id, repetition)
        for case_id in plan.case_ids
        for repetition in range(1, plan.repetitions + 1)
    }
    observed_case_keys = {
        (item.case_id, item.repetition) for item in manifest.cases
    }
    if observed_case_keys != expected_case_keys:
        errors.append("resolved-plan:case-executions")

    expected_descriptors = {
        item.metric_id: item for item in plan.metric_descriptors
    }
    for case in reader.cases():
        case_label = f"case:{case.repetition}:{case.case_id}"
        if case.seed != plan.seed + case.repetition - 1:
            errors.append(f"{case_label}:seed")
        observed_descriptors = {
            item.metric_id: item.descriptor for item in case.evaluation.metrics
        }
        if any(
            observed_descriptors.get(metric_id) != descriptor
            for metric_id, descriptor in expected_descriptors.items()
        ):
            errors.append(f"{case_label}:metric-descriptors")
        if case.adapter_result is None:
            continue
        result = case.adapter_result
        trace = result.trace
        if (
            result.adapter_id != plan.system.adapter_id
            or trace.observation_profile.adapter_id != plan.system.adapter_id
        ):
            errors.append(f"{case_label}:adapter-identity")
        if (
            result.system_id != plan.system.system_id
            or trace.runtime_profile.system_id != plan.system.system_id
        ):
            errors.append(f"{case_label}:system-identity")
        if (
            trace.source_identity.document_id
            != plan.original_document.document_id
            or trace.source_identity.source_sha256
            != plan.original_document.source_sha256
        ):
            errors.append(f"{case_label}:source-identity")
    return tuple(sorted(set(errors)))


class RunRecordStoreV2:
    """Single-writer state store whose completion gate verifies Artifact 2.0."""

    def __init__(
        self,
        runs_root: Path,
        resolved_plans: ResolvedRunPlanStore,
    ) -> None:
        self.root = runs_root
        self.resolved_plans = resolved_plans
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def create(
        self,
        *,
        run_id: str,
        experiment_id: str,
        resolved_plan: ResolvedRunPlanReferenceV2,
        created_at: datetime | None = None,
    ) -> RunRecordV2:
        plan = self.resolved_plans.get(resolved_plan)
        if plan.experiment_id != experiment_id:
            raise ValueError("ResolvedRunPlanV2 belongs to another Experiment")
        record = RunRecordV2(
            run_id=run_id,
            experiment_id=experiment_id,
            resolved_plan_path=resolved_plan.path,
            resolved_plan_digest=resolved_plan.digest,
            state=RunRecordStateV2.PENDING,
            created_at=created_at or datetime.now(UTC),
        )
        with self._lock:
            path = self._path(record.run_id)
            if path.exists():
                existing = self.get(record.run_id)
                if existing != record:
                    raise FileExistsError(
                        f"RunRecordV2 already exists with different content: {run_id}"
                    )
                return existing
            run_directory = self._run_directory(record.run_id)
            if run_directory.is_dir() and any(run_directory.iterdir()):
                raise FileExistsError(
                    f"Run directory already contains another format: {run_id}"
                )
            self._write(record)
        return record

    def get(self, run_id: str) -> RunRecordV2:
        return RunRecordV2.model_validate_json(
            self._path(run_id).read_text(encoding="utf-8")
        )

    def list(self) -> list[RunRecordV2]:
        with self._lock:
            records = [
                RunRecordV2.model_validate_json(path.read_text(encoding="utf-8"))
                for path in sorted(self.root.glob(f"*/{RUN_RECORD_V2_FILENAME}"))
            ]
        return sorted(
            records,
            key=lambda item: (item.created_at, item.run_id),
            reverse=True,
        )

    def prepare_execution_layout(self, run_id: str) -> Path:
        """Create only the operational directories used by a Native v2 Run.

        Evaluation facts never live in these directories; Artifact 2.0 owns
        them exclusively.  Requiring an existing RunRecordV2 prevents this
        workspace helper from reviving the retired mixed RunStore format.
        """

        with self._lock:
            self.get(run_id)
            run_directory = self._run_directory(run_id)
            for name in ("worker", "source", "work"):
                (run_directory / name).mkdir(exist_ok=True)
            return run_directory

    def run_directory(self, run_id: str) -> Path:
        """Return a validated Native v2 Run directory."""

        self.get(run_id)
        return self._run_directory(run_id)

    def mark_running(
        self, run_id: str, *, started_at: datetime | None = None
    ) -> RunRecordV2:
        with self._lock:
            current = self.get(run_id)
            self._require_state(current, RunRecordStateV2.PENDING)
            updated = current.model_copy(
                update={
                    "state": RunRecordStateV2.RUNNING,
                    "started_at": started_at or datetime.now(UTC),
                }
            )
            updated = RunRecordV2.model_validate(updated.model_dump())
            self._write(updated)
            return updated

    def mark_completed(self, run_id: str) -> RunRecordV2:
        """Verify the published Artifact before exposing a completed Run."""

        with self._lock:
            current = self.get(run_id)
            self._require_state(current, RunRecordStateV2.RUNNING)
            reader = ArtifactV2Reader(self._run_directory(run_id) / ARTIFACT_V2_DIRECTORY)
            verification = reader.verify()
            if not verification.valid:
                raise ValueError(
                    "Artifact 2.0 verification failed before Run completion: "
                    f"{verification}"
                )
            manifest = reader.manifest()
            if manifest.run_id != current.run_id:
                raise ValueError("Artifact 2.0 belongs to another Run")
            if manifest.experiment_id != current.experiment_id:
                raise ValueError("Artifact 2.0 belongs to another Experiment")
            plan = self.resolved_plans.get(
                ResolvedRunPlanReferenceV2(
                    path=current.resolved_plan_path,
                    digest=current.resolved_plan_digest,
                )
            )
            binding_errors = artifact_plan_binding_errors(reader, plan)
            if binding_errors:
                raise ValueError(
                    "Artifact 2.0 does not match ResolvedRunPlanV2: "
                    + ", ".join(binding_errors)
                )
            if current.started_at is None:
                raise ValueError("RUNNING Run is missing its start timestamp")
            if manifest.started_at != current.started_at:
                raise ValueError("Artifact 2.0 start time differs from RunRecordV2")
            updated = current.model_copy(
                update={
                    "state": RunRecordStateV2.COMPLETED,
                    "completed_at": manifest.completed_at,
                    "artifact_path": ARTIFACT_V2_REFERENCE,
                    "artifact_digest": manifest.artifact_digest,
                }
            )
            updated = RunRecordV2.model_validate(updated.model_dump())
            self._write(updated)
            return updated

    def mark_failed(
        self,
        run_id: str,
        *,
        error: str,
        completed_at: datetime | None = None,
    ) -> RunRecordV2:
        with self._lock:
            current = self.get(run_id)
            if current.state in {
                RunRecordStateV2.COMPLETED,
                RunRecordStateV2.CANCELLED,
            }:
                raise ValueError(f"cannot fail a {current.state.value} Run")
            if current.state == RunRecordStateV2.FAILED:
                return current
            updated = current.model_copy(
                update={
                    "state": RunRecordStateV2.FAILED,
                    "completed_at": completed_at or datetime.now(UTC),
                    "execution_error": error.strip() or "Run execution failed",
                }
            )
            updated = RunRecordV2.model_validate(updated.model_dump())
            self._write(updated)
            return updated

    def mark_cancelled(
        self, run_id: str, *, completed_at: datetime | None = None
    ) -> RunRecordV2:
        with self._lock:
            current = self.get(run_id)
            if current.state not in {
                RunRecordStateV2.PENDING,
                RunRecordStateV2.RUNNING,
            }:
                raise ValueError(f"cannot cancel a {current.state.value} Run")
            updated = current.model_copy(
                update={
                    "state": RunRecordStateV2.CANCELLED,
                    "completed_at": completed_at or datetime.now(UTC),
                }
            )
            updated = RunRecordV2.model_validate(updated.model_dump())
            self._write(updated)
            return updated

    def _write(self, record: RunRecordV2) -> None:
        atomic_write_json(self._path(record.run_id), record.model_dump(mode="json"))

    def _path(self, run_id: str) -> Path:
        return self._run_directory(run_id) / RUN_RECORD_V2_FILENAME

    def _run_directory(self, run_id: str) -> Path:
        if not run_id or any(
            character
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for character in run_id
        ):
            raise ValueError("unsafe Run ID")
        return self.root / run_id

    @staticmethod
    def _require_state(record: RunRecordV2, expected: RunRecordStateV2) -> None:
        if record.state != expected:
            raise ValueError(
                f"Run {record.run_id} is {record.state.value}; expected {expected.value}"
            )


__all__ = [
    "ARTIFACT_V2_REFERENCE",
    "RUN_RECORD_V2_FILENAME",
    "RUN_RECORD_V2_SCHEMA_VERSION",
    "RunRecordStateV2",
    "RunRecordStoreV2",
    "RunRecordV2",
    "artifact_plan_binding_errors",
]
