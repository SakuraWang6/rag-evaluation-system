"""Public Unified Evaluation v2 boundary."""

from rag_eval.evaluation.unified.models import (
    FORMAL_CORE_METRIC_IDS,
    EvaluationMetric,
    EvaluationMetricStatus,
    EvaluationProfile,
    FailureKind,
    PipelineDelta,
    ProofGatedFailure,
    ShadowDifferenceKind,
    UnifiedEvaluationResult,
    UnifiedShadowComparison,
)
from rag_eval.evaluation.unified.scorer import evaluate_unified_trace
from rag_eval.evaluation.unified.shadow import compare_legacy_shadow

__all__ = [
    "FORMAL_CORE_METRIC_IDS",
    "EvaluationMetric",
    "EvaluationMetricStatus",
    "EvaluationProfile",
    "FailureKind",
    "PipelineDelta",
    "ProofGatedFailure",
    "ShadowDifferenceKind",
    "UnifiedEvaluationResult",
    "UnifiedShadowComparison",
    "compare_legacy_shadow",
    "evaluate_unified_trace",
]
