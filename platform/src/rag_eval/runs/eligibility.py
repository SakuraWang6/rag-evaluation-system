"""Persisted-only aggregation and leaderboard admission for Artifact 2.0."""

from __future__ import annotations

from statistics import fmean

from rag_eval.evaluation.unified.models import (
    FORMAL_CORE_METRIC_IDS,
    EvaluationMetricStatus,
)
from rag_eval.runs.models import (
    AggregateMetricV2,
    ArtifactCaseIndexEntryV2,
    ArtifactCaseIndexV2,
    LeaderboardEligibilityV2,
    RunArtifactCaseV2,
    RunArtifactSummaryV2,
    case_artifact_path,
    descriptor_digest,
)


def derive_leaderboard_eligibility(
    cases: tuple[RunArtifactCaseV2, ...],
) -> LeaderboardEligibilityV2:
    """Decide admission from persisted core metric states and descriptors only."""

    if not cases:
        raise ValueError("leaderboard eligibility requires at least one case")
    reasons: set[str] = set()
    descriptor_digests: dict[str, str] = {}
    for metric_id in FORMAL_CORE_METRIC_IDS:
        values = []
        for case in cases:
            try:
                metric = case.evaluation.metric(metric_id)
            except KeyError:
                reasons.add(
                    f"case {case.case_id} repetition {case.repetition} "
                    f"has no persisted {metric_id}"
                )
                continue
            values.append(metric)
            if metric.status != EvaluationMetricStatus.OBSERVED:
                reasons.add(
                    f"case {case.case_id} repetition {case.repetition} "
                    f"has unavailable {metric_id}"
                )
        digests = {descriptor_digest(item) for item in values}
        if len(values) != len(cases):
            continue
        if len(digests) != 1:
            reasons.add(f"core metric {metric_id} has inconsistent descriptors")
            continue
        descriptor_digests[metric_id] = next(iter(digests))
    eligible = not reasons and len(descriptor_digests) == len(
        FORMAL_CORE_METRIC_IDS
    )
    return LeaderboardEligibilityV2(
        eligible=eligible,
        case_count=len(cases),
        descriptor_digests=descriptor_digests,
        reasons=tuple(sorted(reasons)),
    )


def build_artifact_summary(
    cases: tuple[RunArtifactCaseV2, ...],
) -> RunArtifactSummaryV2:
    if not cases:
        raise ValueError("Artifact 2.0 summary requires at least one case")
    metric_ids = sorted(
        {
            metric.metric_id
            for case in cases
            for metric in case.evaluation.metrics
        }
    )
    aggregates: list[AggregateMetricV2] = []
    for metric_id in metric_ids:
        values = []
        missing = 0
        for case in cases:
            try:
                values.append(case.evaluation.metric(metric_id))
            except KeyError:
                missing += 1
        observed = [
            item
            for item in values
            if item.status == EvaluationMetricStatus.OBSERVED
            and item.value is not None
        ]
        descriptor_digests = tuple(
            sorted({descriptor_digest(item) for item in values})
        )
        all_observed = (
            len(observed) == len(cases)
            and not missing
            and len(descriptor_digests) == 1
        )
        reasons: list[str] = []
        if missing:
            reasons.append(f"missing in {missing} case executions")
        if len(observed) != len(values):
            reasons.append(
                f"unavailable in {len(values) - len(observed)} case executions"
            )
        if len(descriptor_digests) > 1:
            reasons.append("metric descriptors differ across case executions")
        aggregates.append(
            AggregateMetricV2(
                metric_id=metric_id,
                status=(
                    EvaluationMetricStatus.OBSERVED
                    if all_observed
                    else EvaluationMetricStatus.UNAVAILABLE
                ),
                value=(
                    fmean(float(item.value) for item in observed)
                    if all_observed
                    else None
                ),
                case_count=len(cases),
                observed_case_count=len(observed),
                unavailable_case_count=len(cases) - len(observed),
                descriptor_digests=descriptor_digests,
                reason="; ".join(reasons) or None,
            )
        )
    status_counts: dict[str, int] = {}
    for case in cases:
        status_counts[case.status] = status_counts.get(case.status, 0) + 1
    return RunArtifactSummaryV2(
        case_count=len(cases),
        execution_status_counts=status_counts,
        metrics=tuple(aggregates),
        leaderboard_eligibility=derive_leaderboard_eligibility(cases),
    )


def build_case_index(
    cases: tuple[RunArtifactCaseV2, ...],
) -> ArtifactCaseIndexV2:
    entries = tuple(
        ArtifactCaseIndexEntryV2(
            case_id=case.case_id,
            repetition=case.repetition,
            seed=case.seed,
            status=case.status,
            question=case.question,
            answer_judgment=case.answer_judgment,
            evidence_judgment=case.evidence_judgment,
            core_metrics_available=case.evaluation.core_metrics_available,
            failure_kind=(
                case.evaluation.failure.kind if case.evaluation.failure else None
            ),
            artifact_path=case_artifact_path(case.case_id, case.repetition),
        )
        for case in sorted(cases, key=lambda item: (item.repetition, item.case_id))
    )
    return ArtifactCaseIndexV2(cases=entries)


__all__ = [
    "build_artifact_summary",
    "build_case_index",
    "derive_leaderboard_eligibility",
]
