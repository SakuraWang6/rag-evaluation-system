"""RAG-neutral result models for proof-driven Unified Evaluation v2.

The models live with the evaluation owner instead of the Run contracts.  Phase
6 may persist them verbatim, but orchestration is not an authority for their
meaning.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.contracts.observation import StageName

UNIFIED_EVALUATION_SCHEMA_VERSION = "2.0"
UNIFIED_SCORER_ID = "canonical-unified-evidence"
UNIFIED_SCORER_VERSION = "2.0"
FORMAL_CORE_METRIC_IDS = (
    "ranked_evidence_coverage@1",
    "ranked_complete_evidence_recall@1",
    "ranked_evidence_coverage@3",
    "ranked_complete_evidence_recall@3",
    "ranked_evidence_coverage@5",
    "ranked_complete_evidence_recall@5",
    "ranked_complete_evidence_mrr@5",
)


class EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvaluationMetricStatus(StrEnum):
    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"


class FailureKind(StrEnum):
    PARSER_INDEX_LOSS = "PARSER_INDEX_LOSS"
    RETRIEVAL_LOSS = "RETRIEVAL_LOSS"
    RANKING_LOSS = "RANKING_LOSS"
    CONTEXT_LOSS = "CONTEXT_LOSS"
    GENERATION_FAILURE = "GENERATION_FAILURE"
    UNOBSERVABLE = "UNOBSERVABLE"


class ShadowDifferenceKind(StrEnum):
    EQUIVALENT = "equivalent"
    EXPECTED_SEMANTIC_CHANGE = "expected_semantic_change"
    NOT_COMPARABLE = "not_comparable"


class EvaluationProfile(EvaluationModel):
    """Versioned scoring window, independent of any Adapter profile."""

    candidate_cutoff: int = Field(ge=1)
    ranked_cutoffs: tuple[int, ...] = (1, 3, 5)
    ranked_mrr_cutoff: int = Field(default=5, ge=1)
    context_budget: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_formal_windows(self) -> EvaluationProfile:
        if self.ranked_cutoffs != (1, 3, 5):
            raise ValueError("formal ranked cutoffs must be exactly (1, 3, 5)")
        if self.ranked_mrr_cutoff != 5:
            raise ValueError("formal complete-evidence MRR cutoff must be 5")
        return self


class MetricDescriptor(EvaluationModel):
    metric_id: str = Field(min_length=1)
    scorer_id: Literal[UNIFIED_SCORER_ID] = UNIFIED_SCORER_ID
    scorer_version: Literal[UNIFIED_SCORER_VERSION] = UNIFIED_SCORER_VERSION
    scorer_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    aggregation: Literal["mses_clause_equal_weight", "canonical_extent_union"]
    stage: StageName | None = None
    cutoff: int | None = Field(default=None, ge=1)
    candidate_cutoff: int = Field(ge=1)
    ranked_cutoff: int = Field(ge=1)
    context_budget: int = Field(ge=1)


class EvaluationMetric(EvaluationModel):
    metric_id: str = Field(min_length=1)
    status: EvaluationMetricStatus
    value: float | None = Field(default=None, ge=0)
    lower_bound: float = Field(ge=0, le=1)
    upper_bound: float = Field(ge=0, le=1)
    descriptor: MetricDescriptor
    reason: str | None = None

    @model_validator(mode="after")
    def validate_availability(self) -> EvaluationMetric:
        if self.lower_bound > self.upper_bound:
            raise ValueError("metric lower bound cannot exceed upper bound")
        if self.metric_id != self.descriptor.metric_id:
            raise ValueError("metric ID must agree with its descriptor")
        if self.status == EvaluationMetricStatus.OBSERVED:
            if self.value is None:
                raise ValueError("observed metric requires a value")
            if abs(self.lower_bound - self.upper_bound) > 1e-12:
                raise ValueError("observed metric requires a proved exact bound")
        elif self.value is not None:
            raise ValueError("unavailable metric cannot carry a value")
        return self


class EvidenceLocalization(EvaluationModel):
    evidence_id: str = Field(min_length=1)
    canonical_object_id: str | None = None
    lower_coverage: float = Field(ge=0, le=1)
    upper_coverage: float = Field(ge=0, le=1)
    exact: bool
    reason: str | None = None


class StageLocalization(EvaluationModel):
    stage: StageName | Literal["ingestion"]
    cutoff: int | None = Field(default=None, ge=1)
    status: EvaluationMetricStatus
    evidence: tuple[EvidenceLocalization, ...]
    coverage_lower: float = Field(ge=0, le=1)
    coverage_upper: float = Field(ge=0, le=1)
    complete_recall_lower: float = Field(ge=0, le=1)
    complete_recall_upper: float = Field(ge=0, le=1)
    reason: str | None = None


class ObjectExtentDelta(EvaluationModel):
    canonical_object_id: str = Field(min_length=1)
    lost_fraction: float = Field(ge=0, le=1)
    gained_fraction: float = Field(ge=0, le=1)


class PipelineDelta(EvaluationModel):
    transition: Literal["candidate_to_ranked", "ranked_to_context"]
    status: EvaluationMetricStatus
    loss_fraction: float | None = Field(default=None, ge=0, le=1)
    gain_fraction: float | None = Field(default=None, ge=0, le=1)
    object_deltas: tuple[ObjectExtentDelta, ...] = ()
    candidate_cutoff: int = Field(ge=1)
    ranked_cutoff: int = Field(ge=1)
    context_budget: int = Field(ge=1)
    reason: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> PipelineDelta:
        if self.status == EvaluationMetricStatus.OBSERVED:
            if self.loss_fraction is None or self.gain_fraction is None:
                raise ValueError("observed pipeline delta requires loss and gain")
        elif self.loss_fraction is not None or self.gain_fraction is not None:
            raise ValueError("unavailable pipeline delta cannot carry values")
        return self


class ProofGatedFailure(EvaluationModel):
    kind: FailureKind
    cutoff: int | None = Field(default=None, ge=1)
    reason: str = Field(min_length=1)
    proof_subjects: tuple[str, ...] = ()


class UnifiedEvaluationResult(EvaluationModel):
    schema_version: Literal[UNIFIED_EVALUATION_SCHEMA_VERSION] = (
        UNIFIED_EVALUATION_SCHEMA_VERSION
    )
    scorer_id: Literal[UNIFIED_SCORER_ID] = UNIFIED_SCORER_ID
    scorer_version: Literal[UNIFIED_SCORER_VERSION] = UNIFIED_SCORER_VERSION
    scorer_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    gold_evidence_set_id: str = Field(min_length=1)
    trace_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    metrics: tuple[EvaluationMetric, ...]
    localizations: tuple[StageLocalization, ...]
    pipeline_deltas: tuple[PipelineDelta, ...]
    failure: ProofGatedFailure | None = None

    def metric(self, metric_id: str) -> EvaluationMetric:
        for metric in self.metrics:
            if metric.metric_id == metric_id:
                return metric
        raise KeyError(metric_id)

    def pipeline_delta(self, transition: str) -> PipelineDelta:
        for delta in self.pipeline_deltas:
            if delta.transition == transition:
                return delta
        raise KeyError(transition)

    @property
    def core_metrics_available(self) -> bool:
        by_id = {metric.metric_id: metric for metric in self.metrics}
        return all(
            metric_id in by_id
            and by_id[metric_id].status == EvaluationMetricStatus.OBSERVED
            for metric_id in FORMAL_CORE_METRIC_IDS
        )


class ShadowDifference(EvaluationModel):
    legacy_metric_id: str = Field(min_length=1)
    unified_metric_id: str = Field(min_length=1)
    kind: ShadowDifferenceKind
    reason: str = Field(min_length=1)


class UnifiedShadowComparison(EvaluationModel):
    legacy_scorer_version: str = Field(min_length=1)
    unified_scorer_version: str = Field(min_length=1)
    differences: tuple[ShadowDifference, ...]
