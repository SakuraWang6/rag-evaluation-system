"""Experiment, run, case, metric, and comparison contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.contracts.adapter import AdapterCapabilities, RAGResult
from rag_eval.contracts.dataset import GoldAnswer, GoldEvidenceSet


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MetricStatus(StrEnum):
    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"


class RunStatus(StrEnum):
    QUEUED = "queued"
    PREPARING = "preparing"
    INGESTING = "ingesting"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class ComparisonTier(StrEnum):
    TASK_COMPARABLE = "task_comparable"
    STRICT_CONTROLLED = "strict_controlled"
    EXPLORATORY = "exploratory"


class MetricResult(ContractModel):
    metric_id: str = Field(min_length=1)
    status: MetricStatus
    value: float | None = None
    numerator: float | None = None
    denominator: float | None = None
    scorer_id: str = Field(min_length=1)
    scorer_version: str = Field(min_length=1)
    scorer_digest: str = Field(min_length=1)
    evaluator_mode: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_status_value(self) -> MetricResult:
        if self.status == MetricStatus.OBSERVED and self.value is None:
            raise ValueError("observed metric requires a value")
        if self.status != MetricStatus.OBSERVED and self.value is not None:
            raise ValueError("non-observed metric must not carry a value")
        return self


class ExperimentSpec(ContractModel):
    experiment_id: str = Field(min_length=1)
    bundle_id: str = Field(min_length=1)
    system_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    adapter_config: dict[str, Any] = Field(default_factory=dict)
    query_config: dict[str, Any] = Field(default_factory=dict)
    metric_config: dict[str, Any] = Field(default_factory=dict)
    case_ids: list[str] | None = None
    case_selection_id: str = Field(min_length=1)
    seed: int = 0
    repetitions: int = Field(default=1, ge=1)


class CaseError(ContractModel):
    code: str
    message: str
    retryable: bool = False


class CaseResult(ContractModel):
    case_id: str = Field(min_length=1)
    status: Literal["completed", "timeout", "system_error", "cancelled"]
    question: str
    gold_answer: GoldAnswer | None = None
    gold_evidence_set: GoldEvidenceSet | None = None
    rag_result: RAGResult | None = None
    metrics: list[MetricResult] = Field(default_factory=list)
    error: CaseError | None = None
    started_at: datetime
    completed_at: datetime
    repetition: int = Field(default=1, ge=1)
    seed: int = 0


class ReproducibilityRecord(ContractModel):
    platform_git_commit: str | None = None
    platform_dirty: bool
    dirty_patch_digest: str | None = None
    dependency_lock_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    environment_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_digests: dict[str, str] = Field(default_factory=dict)
    prompt_digests: dict[str, str] = Field(default_factory=dict)
    dependency_lock_artifact: str
    environment_artifact: str


class RunManifest(ContractModel):
    schema_version: Literal[2] = 2
    producer: Literal["rag_eval_platform"] = "rag_eval_platform"
    run_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    status: RunStatus
    bundle_id: str = Field(min_length=1)
    case_selection_id: str = Field(min_length=1)
    platform_version: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    system_id: str = Field(min_length=1)
    system_version: str = Field(min_length=1)
    declared_config: dict[str, Any]
    effective_config: dict[str, Any]
    scorer_id: str = Field(min_length=1)
    scorer_version: str = Field(min_length=1)
    scorer_digest: str = Field(min_length=1)
    declared_capabilities: AdapterCapabilities
    observed_capabilities: AdapterCapabilities
    seed: int
    repetitions: int = Field(ge=1)
    started_at: datetime
    completed_at: datetime | None = None
    execution_counts: dict[str, int] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    artifact_checksums: dict[str, str] = Field(default_factory=dict)
    index_fingerprint: str | None = None
    index_fingerprints: list[str] = Field(default_factory=list)
    repetition_seeds: list[int] = Field(default_factory=list)
    reproducibility: ReproducibilityRecord | None = None
    replay_of_run_id: str | None = None
    failure_reason: str | None = None

    @classmethod
    def now(cls) -> datetime:
        return datetime.now(UTC)
