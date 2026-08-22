"""Stage-aware retrieval metrics over required evidence groups."""

from __future__ import annotations

from rag_eval.contracts.adapter import RAGEvidenceItem, RAGResult
from rag_eval.contracts.dataset import GoldEvidenceSet
from rag_eval.contracts.run import MetricResult, MetricStatus
from rag_eval.evaluation.evidence import (
    EVIDENCE_SCORER_DIGEST,
    EVIDENCE_SCORER_ID,
    EVIDENCE_SCORER_VERSION,
    CorpusEvidenceIndex,
    match_all,
)


def evaluate_retrieval_stages(
    result: RAGResult,
    evidence_set: GoldEvidenceSet,
    corpus: CorpusEvidenceIndex,
    *,
    k_values: tuple[int, ...] = (1, 3, 5),
) -> list[MetricResult]:
    metrics: list[MetricResult] = []
    stage_results: dict[str, dict[str, MetricResult]] = {}
    for stage, items in (
        ("raw", result.raw_retrieval),
        ("ranked", result.ranked_retrieval),
        ("context", result.final_context),
    ):
        stage_metrics = evaluate_stage(
            stage, items, evidence_set, corpus, k_values=k_values
        )
        stage_results[stage] = {metric.metric_id: metric for metric in stage_metrics}
        metrics.extend(stage_metrics)

    for cutoff in k_values:
        raw = stage_results["raw"][f"raw_recall@{cutoff}"]
        ranked = stage_results["ranked"][f"ranked_recall@{cutoff}"]
        context = stage_results["context"][f"context_recall@{cutoff}"]
        metrics.append(
            difference_metric(
                f"retrieval_stage_delta@{cutoff}", ranked, raw
            )
        )
        metrics.append(
            difference_metric(
                f"context_selection_loss@{cutoff}", ranked, context
            )
        )
    return metrics


def evaluate_stage(
    stage: str,
    items: list[RAGEvidenceItem] | None,
    evidence_set: GoldEvidenceSet,
    corpus: CorpusEvidenceIndex,
    *,
    k_values: tuple[int, ...],
) -> list[MetricResult]:
    if items is None:
        metric_ids = [f"{stage}_recall@{cutoff}" for cutoff in k_values]
        if stage in {"raw", "ranked"}:
            metric_ids.append(f"{stage}_mrr")
        return [unavailable(metric_id, f"{stage} stage is not observable") for metric_id in metric_ids]

    ordered = sorted(items, key=lambda item: item.rank)
    matches = match_all(ordered, evidence_set.evidence, corpus)
    group_ranks = [
        min(
            (matches[evidence_id].rank for evidence_id in group if evidence_id in matches),
            default=None,
        )
        for group in evidence_set.required_groups
    ]
    denominator = len(group_ranks)
    metrics: list[MetricResult] = []
    for cutoff in k_values:
        hits = sum(rank is not None and rank <= cutoff for rank in group_ranks)
        metrics.append(
            observed(
                f"{stage}_recall@{cutoff}",
                hits / denominator,
                numerator=hits,
                denominator=denominator,
            )
        )
    if stage in {"raw", "ranked"}:
        first_rank = min((rank for rank in group_ranks if rank is not None), default=None)
        reciprocal = 1 / first_rank if first_rank else 0.0
        metrics.append(
            observed(
                f"{stage}_mrr",
                reciprocal,
                numerator=reciprocal,
                denominator=1,
            )
        )
    return metrics


def difference_metric(
    metric_id: str, left: MetricResult, right: MetricResult
) -> MetricResult:
    if left.status != MetricStatus.OBSERVED or right.status != MetricStatus.OBSERVED:
        return unavailable(metric_id, "both source stages must be observable")
    assert left.value is not None and right.value is not None
    return observed(metric_id, left.value - right.value, numerator=None, denominator=None)


def observed(
    metric_id: str,
    value: float,
    *,
    numerator: float | None,
    denominator: float | None,
) -> MetricResult:
    return MetricResult(
        metric_id=metric_id,
        status=MetricStatus.OBSERVED,
        value=float(value),
        numerator=numerator,
        denominator=denominator,
        scorer_id=EVIDENCE_SCORER_ID,
        scorer_version=EVIDENCE_SCORER_VERSION,
        scorer_digest=EVIDENCE_SCORER_DIGEST,
    )


def unavailable(metric_id: str, reason: str) -> MetricResult:
    return MetricResult(
        metric_id=metric_id,
        status=MetricStatus.UNAVAILABLE,
        scorer_id=EVIDENCE_SCORER_ID,
        scorer_version=EVIDENCE_SCORER_VERSION,
        scorer_digest=EVIDENCE_SCORER_DIGEST,
        reason=reason,
    )
