"""Public Unified Evaluation v2 boundary."""

from rag_eval.evaluation.unified.models import (
    FORMAL_CORE_METRIC_IDS,
    EvaluationMetric,
    EvaluationMetricStatus,
    EvaluationProfile,
    FailureKind,
    PipelineDelta,
    ProofGatedFailure,
    UnifiedEvaluationResult,
)
from rag_eval.evaluation.unified.scorer import evaluate_unified_trace

__all__ = [
    "FORMAL_CORE_METRIC_IDS",
    "EvaluationMetric",
    "EvaluationMetricStatus",
    "EvaluationProfile",
    "FailureKind",
    "PipelineDelta",
    "ProofGatedFailure",
    "UnifiedEvaluationResult",
    "evaluate_unified_trace",
]
