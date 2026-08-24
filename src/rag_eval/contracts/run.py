"""Experiment, run, case, metric, and comparison contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.artifact_contract import artifact_digest
from rag_eval.contracts.adapter import AdapterCapabilities, RAGResult
from rag_eval.contracts.dataset import GoldAnswer, GoldEvidenceSet
from rag_eval.contracts.research import (
    AnalysisContract,
    ComparisonSpec,
    FailureAssessment,
    LatencyProtocol,
    ModelArtifactIdentity,
    ModelLock,
    SourceIdentity,
)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MetricStatus(StrEnum):
    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"
    NEEDS_REVIEW = "needs_review"


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
    # Formal experiments must be frozen against immutable, verified artifacts.
    formal: bool = False
    model_lock_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    model_artifacts: dict[str, ModelArtifactIdentity] = Field(default_factory=dict)
    comparison_spec_digest: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    analysis_contract_digest: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    latency_protocol_digest: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    # Full frozen content is retained with a formal ExperimentSpec so the
    # runner can enforce its warmup/cache lifecycle instead of trusting a hash
    # label alone.
    analysis_contract: AnalysisContract | None = None
    latency_protocol: LatencyProtocol | None = None
    comparison_spec: ComparisonSpec | None = None

    @model_validator(mode="after")
    def validate_formal_model_lock(self) -> ExperimentSpec:
        if not self.formal:
            return self
        if not self.model_lock_digest:
            raise ValueError("formal experiment requires model_lock_digest")
        if not self.comparison_spec_digest:
            raise ValueError("formal experiment requires comparison_spec_digest")
        if not self.analysis_contract_digest:
            raise ValueError("formal experiment requires analysis_contract_digest")
        if not self.latency_protocol_digest:
            raise ValueError("formal experiment requires latency_protocol_digest")
        if not self.model_artifacts:
            raise ValueError("formal experiment requires model_artifacts")
        unverified = [
            name for name, model in self.model_artifacts.items() if not model.verified
        ]
        if unverified:
            raise ValueError(
                f"formal experiment has unverified models: {sorted(unverified)}"
            )
        expected_lock_digest = artifact_digest(ModelLock(models=self.model_artifacts))
        if self.model_lock_digest != expected_lock_digest:
            raise ValueError("model_lock_digest does not match model_artifacts")
        if self.analysis_contract is None:
            raise ValueError("formal experiment requires analysis_contract content")
        if self.analysis_contract_digest != artifact_digest(self.analysis_contract):
            raise ValueError("analysis_contract_digest does not match analysis_contract")
        if self.latency_protocol is None:
            raise ValueError("formal experiment requires latency_protocol content")
        if self.latency_protocol_digest != artifact_digest(self.latency_protocol):
            raise ValueError("latency_protocol_digest does not match latency_protocol")
        if self.comparison_spec is None:
            raise ValueError("formal experiment requires comparison_spec content")
        if self.comparison_spec_digest != artifact_digest(self.comparison_spec):
            raise ValueError("comparison_spec_digest does not match comparison_spec")
        return self


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
    failure_assessment: FailureAssessment | None = None
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
    model_artifacts: dict[str, ModelArtifactIdentity] = Field(default_factory=dict)
    source_identities: dict[str, SourceIdentity] = Field(default_factory=dict)
    hardware_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    dependency_lock_artifact: str
    environment_artifact: str


class RunManifest(ContractModel):
    schema_version: Literal[2] = 2
    producer: Literal["rag_eval_platform"] = "rag_eval_platform"
    artifact_contract_version: Literal["1.2"] = "1.2"
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
    # Namespace -> immutable scorer identity.  The legacy top-level answer
    # scorer fields remain for schema-v2 compatibility.
    metric_scorers: dict[str, dict[str, str]] = Field(default_factory=dict)
    model_artifacts: dict[str, ModelArtifactIdentity] = Field(default_factory=dict)
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
    index_input_fingerprint: str | None = None
    index_artifact_digest: str | None = None
    index_artifact_digests: list[str] = Field(default_factory=list)
    latency_protocol_digest: str | None = None
    repetition_seeds: list[int] = Field(default_factory=list)
    reproducibility: ReproducibilityRecord | None = None
    replay_of_run_id: str | None = None
    failure_reason: str | None = None

    @classmethod
    def now(cls) -> datetime:
        return datetime.now(UTC)
