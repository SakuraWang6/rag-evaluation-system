"""Explicit, non-authoritative comparison against the legacy scorer."""

from __future__ import annotations

from rag_eval.contracts.run import MetricResult, MetricStatus
from rag_eval.evaluation.unified.models import (
    EvaluationMetricStatus,
    ShadowDifference,
    ShadowDifferenceKind,
    UnifiedEvaluationResult,
    UnifiedShadowComparison,
)


def compare_legacy_shadow(
    legacy_metrics: list[MetricResult],
    unified: UnifiedEvaluationResult,
) -> UnifiedShadowComparison:
    """Classify overlap; this never promotes legacy output to v2 authority."""

    legacy_by_id = {item.metric_id: item for item in legacy_metrics}
    differences: list[ShadowDifference] = []
    for cutoff in (1, 3, 5):
        legacy_id = f"ranked_recall@{cutoff}"
        unified_id = f"ranked_complete_evidence_recall@{cutoff}"
        old = legacy_by_id.get(legacy_id)
        try:
            new = unified.metric(unified_id)
        except KeyError:
            continue
        if old is None:
            continue
        if (
            old.status == MetricStatus.OBSERVED
            and new.status == EvaluationMetricStatus.OBSERVED
            and old.value is not None
            and new.value is not None
            and abs(old.value - new.value) <= 1e-12
        ):
            kind = ShadowDifferenceKind.EQUIVALENT
            reason = "legacy complete-hit recall equals v2 clause-complete recall"
        elif (
            old.status != MetricStatus.OBSERVED
            or new.status != EvaluationMetricStatus.OBSERVED
        ):
            kind = ShadowDifferenceKind.NOT_COMPARABLE
            reason = "one scorer lacks a proved observed value"
        else:
            kind = ShadowDifferenceKind.EXPECTED_SEMANTIC_CHANGE
            reason = (
                "v2 uses verified extent union and MSES clause weighting; "
                "the versioned difference is not silently reconciled"
            )
        differences.append(
            ShadowDifference(
                legacy_metric_id=legacy_id,
                unified_metric_id=unified_id,
                kind=kind,
                reason=reason,
            )
        )
    versions = sorted({item.scorer_version for item in legacy_metrics})
    return UnifiedShadowComparison(
        legacy_scorer_version=",".join(versions) or "unknown",
        unified_scorer_version=unified.scorer_version,
        differences=tuple(differences),
    )
