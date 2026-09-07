"""Artifact Contract 1.2 models for controlled research evaluation.

These contracts are transport-neutral.  In particular, they deliberately do
not import an adapter implementation or a RAG core package.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelArtifactIdentity(ContractModel):
    """An immutable model identity; names and tags are display-only metadata."""

    display_name: str = Field(min_length=1)
    requested_ref: str = Field(min_length=1)
    resolved_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    revision: str | None = Field(default=None, min_length=1)
    resolver: str = Field(min_length=1)
    resolved_at: datetime
    verified: bool = False

    @model_validator(mode="after")
    def validate_immutable_identity(self) -> ModelArtifactIdentity:
        if self.verified and not (self.resolved_digest or self.revision):
            raise ValueError("a verified model requires a digest or immutable revision")
        return self

    @property
    def identity(self) -> str | None:
        return self.resolved_digest or self.revision


class ModelLock(ContractModel):
    """Frozen model identities referenced by a formal ExperimentSpec."""

    schema_version: Literal[1] = 1
    models: dict[str, ModelArtifactIdentity] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_verified_models(self) -> ModelLock:
        unverified = [name for name, value in self.models.items() if not value.verified]
        if unverified:
            raise ValueError(f"model lock contains unverified models: {sorted(unverified)}")
        return self


class SourceIdentity(ContractModel):
    package_version: str | None = None
    git_commit: str | None = None
    dirty_patch_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    direct_url: str | None = None


class FailureLabel(StrEnum):
    PROVENANCE_UNAVAILABLE = "provenance_unavailable"
    RETRIEVAL_MISSING = "retrieval_missing"
    RANKING_FAILURE = "ranking_failure"
    CONTEXT_SELECTION_LOSS = "context_selection_loss"
    GENERATION_FAILURE = "generation_failure"
    UNSUPPORTED_ANSWER = "unsupported_answer"
    TIMEOUT = "timeout"
    ADAPTER_ERROR = "adapter_error"
    DATASET_ISSUE = "dataset_issue"
    PARTIAL_COVERAGE = "partial_coverage"
    UNSUPPORTED_STAGE = "unsupported_stage"
    RUNTIME_ERROR = "runtime_error"
    MAPPING_CORRUPTED = "mapping_corrupted"
    NEEDS_REVIEW = "needs_review"


class FailureAssessment(ContractModel):
    labels: list[FailureLabel] = Field(default_factory=list)
    certainty: Literal["deterministic", "reviewed", "unknown"] = "unknown"
    reasons: list[str] = Field(default_factory=list)
    review_required: bool = False


class LatencyMeasurement(ContractModel):
    """Monotonic timing values expressed in seconds.

    Only ``end_to_end_query_latency`` is a cross-system candidate metric.  The
    native breakdown is adapter diagnostics and must remain optional.
    """

    end_to_end_query_latency: float = Field(ge=0)
    native_query_latency: float | None = Field(default=None, ge=0)
    retrieval_latency: float | None = Field(default=None, ge=0)
    generation_latency: float | None = Field(default=None, ge=0)


class LatencyProtocol(ContractModel):
    """Frozen lifecycle conditions for Task-Comparable wall-clock latency."""

    schema_version: Literal[1] = 1
    fresh_worker_per_repetition: bool = True
    fresh_run_scoped_index: bool = True
    warmup_queries: int = Field(default=1, ge=0)
    warmup_question: str = Field(default="RAG evaluation warmup.", min_length=1)
    answer_cache_enabled: bool = False
    query_cache_enabled: bool = False
    llm_cache_enabled: bool = False
    worker_ready_before_measurement: bool = True
    ingestion_before_measurement: bool = True
    concurrency: Literal[1] = 1
    preserve_model_and_index_warmth_between_cases: bool = True
    identical_case_order_across_treatments: bool = True
    measurement_scope: Literal["query_dispatch_to_validated_response"] = (
        "query_dispatch_to_validated_response"
    )

    @model_validator(mode="after")
    def validate_formal_policy(self) -> LatencyProtocol:
        if self.answer_cache_enabled or self.query_cache_enabled or self.llm_cache_enabled:
            raise ValueError("formal latency protocol requires all answer/query/LLM caches disabled")
        if not self.worker_ready_before_measurement or not self.ingestion_before_measurement:
            raise ValueError("formal latency protocol starts after worker preparation and ingestion")
        if not self.fresh_worker_per_repetition or not self.fresh_run_scoped_index:
            raise ValueError("formal latency protocol requires fresh worker and index per repetition")
        if self.warmup_queries != 1:
            raise ValueError("formal latency protocol requires exactly one warmup query")
        return self


class ComparisonSpec(ContractModel):
    """Pre-registered controls and interpretation scope for a comparison."""

    comparison_id: str = Field(min_length=1)
    experiment_ids: list[str] = Field(min_length=2)
    tier: Literal["task_comparable", "strict_controlled", "exploratory"]
    controlled_factors: list[str] = Field(default_factory=list)
    treatment_factors: list[str] = Field(default_factory=list)
    primary_metrics: list[str] = Field(default_factory=list)
    secondary_metrics: list[str] = Field(default_factory=list)
    minimum_metric_coverage: float = Field(default=1.0, ge=0, le=1)
    model_lock_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    latency_protocol_digest: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    analysis_contract_digest: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def validate_factor_partition(self) -> ComparisonSpec:
        overlap = set(self.controlled_factors).intersection(self.treatment_factors)
        if overlap:
            raise ValueError(f"factor cannot be both controlled and treatment: {sorted(overlap)}")
        metric_overlap = set(self.primary_metrics).intersection(self.secondary_metrics)
        if metric_overlap:
            raise ValueError(
                f"metric cannot be both primary and secondary: {sorted(metric_overlap)}"
            )
        if len(self.experiment_ids) != len(set(self.experiment_ids)):
            raise ValueError("ComparisonSpec experiment_ids must be unique")
        if self.tier == "strict_controlled" and not self.controlled_factors:
            raise ValueError("strict controlled comparison requires controlled_factors")
        if self.tier == "strict_controlled" and not self.primary_metrics:
            raise ValueError("strict controlled comparison requires primary_metrics")
        if self.tier == "strict_controlled":
            missing = [
                name
                for name, value in (
                    ("model_lock_digest", self.model_lock_digest),
                    ("latency_protocol_digest", self.latency_protocol_digest),
                    ("analysis_contract_digest", self.analysis_contract_digest),
                )
                if value is None
            ]
            if missing:
                raise ValueError(
                    "strict controlled comparison requires frozen artifacts: "
                    f"{', '.join(missing)}"
                )
        return self


class AnalysisContract(ContractModel):
    """Pre-registered case-clustered analysis policy for formal benchmarks."""

    schema_version: Literal[1] = 1
    independent_unit: Literal["case"] = "case"
    seed_role: Literal["within_case_repeated_measurement"] = (
        "within_case_repeated_measurement"
    )
    paired_seed_policy: Literal["mean_matched_seeds"] = "mean_matched_seeds"
    bootstrap_method: Literal["stratified_case_clustered_paired"] = (
        "stratified_case_clustered_paired"
    )
    bootstrap_iterations: int = Field(default=10000, ge=1000)
    confidence_level: float = Field(default=0.95, gt=0, lt=1)
    analysis_seed: int

    @model_validator(mode="after")
    def reject_case_seed_pseudoreplication(self) -> AnalysisContract:
        if self.independent_unit != "case":
            raise ValueError("formal analysis must use case as the independent unit")
        return self


class BlindProtocol(ContractModel):
    """Final append-only record for a sealed, formal blind benchmark."""

    schema_version: Literal[1] = 1
    sealed_at: datetime
    sealed_bundle_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    curator_id: str = Field(min_length=1)
    config_frozen_at: datetime
    code_commit: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    model_lock_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    comparison_spec_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    analysis_contract_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    formal_runs_started_at: datetime
    formal_runs_completed_at: datetime
    gold_revealed_at: datetime
    evaluator_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_timeline(self) -> BlindProtocol:
        if not (
            self.sealed_at
            < self.config_frozen_at
            < self.formal_runs_started_at
            <= self.formal_runs_completed_at
            < self.gold_revealed_at
        ):
            raise ValueError(
                "blind timeline must satisfy seal < config freeze < run start "
                "<= run completion < Gold reveal"
            )
        return self
