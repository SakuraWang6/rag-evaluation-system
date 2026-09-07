"""Stage-aware retrieval metrics over required evidence groups.

Metrics consume the independent localization layer from
``rag_eval.evaluation.evidence``.  In particular, partial source spans are
only promoted after a verified, gap-free union at the requested cutoff, and
MRR is the earliest rank at which one complete alternative path is covered.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from rag_eval.contracts.adapter import RAGEvidenceItem, RAGResult
from rag_eval.contracts.dataset import GoldEvidenceSet
from rag_eval.contracts.run import MetricResult, MetricStatus
from rag_eval.evaluation.evidence import (
    EVIDENCE_SCORER_DIGEST,
    EVIDENCE_SCORER_ID,
    EVIDENCE_SCORER_VERSION,
    CorpusEvidenceIndex,
    GoldLocalization,
    LocalizationStatus,
    StageLocalization,
    evidence_observability,
    localize_stage,
)


def evaluate_retrieval_stages(
    result: RAGResult,
    evidence_set: GoldEvidenceSet,
    corpus: CorpusEvidenceIndex,
    *,
    k_values: tuple[int, ...] = (1, 3, 5),
) -> list[MetricResult]:
    """Evaluate Raw, Ranked, and Final Context independently."""

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
        metrics.append(difference_metric(f"retrieval_stage_delta@{cutoff}", ranked, raw))
        metrics.append(
            difference_metric(f"context_selection_loss@{cutoff}", ranked, context)
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
    """Evaluate one stage while preserving ``None`` versus ``[]`` semantics."""

    if items is None:
        metric_ids = [f"{stage}_recall@{cutoff}" for cutoff in k_values]
        if stage in {"raw", "ranked"}:
            metric_ids.append(f"{stage}_mrr")
        return [
            unavailable(metric_id, f"{stage} stage is not observable")
            for metric_id in metric_ids
        ]

    ordered = sorted(items, key=lambda item: (item.rank, item.item_id))
    metrics: list[MetricResult] = []
    for cutoff in k_values:
        selected_items = [item for item in ordered if item.rank <= cutoff]
        localized = localize_stage(
            selected_items,
            evidence_set,
            corpus,
            stage=stage,
            cutoff=cutoff,
        )
        observability_reason = _observability_for_localization(localized, evidence_set)
        if observability_reason is not None:
            metrics.append(
                unavailable(
                    f"{stage}_recall@{cutoff}", observability_reason
                )
            )
            continue
        path, clause_ranks = _best_path(localized, evidence_set)
        if path is None:
            metrics.append(
                unavailable(
                    f"{stage}_recall@{cutoff}",
                    "Gold Evidence set has no valid MSES path",
                )
            )
            continue
        hits = sum(rank is not None for rank in clause_ranks)
        denominator = len(clause_ranks)
        metrics.append(
            observed(
                f"{stage}_recall@{cutoff}",
                hits / denominator if denominator else 0.0,
                numerator=hits,
                denominator=denominator,
            )
        )

    if stage in {"raw", "ranked"}:
        localized = localize_stage(ordered, evidence_set, corpus, stage=stage)
        observability_reason = _observability_for_localization(localized, evidence_set)
        if observability_reason is not None:
            metrics.append(unavailable(f"{stage}_mrr", observability_reason))
        else:
            _path, clause_ranks = _best_path(localized, evidence_set)
            complete_ranks = [
                max(ranks)
                for path in _paths(evidence_set)
                if (ranks := _path_clause_ranks(localized, path))
                and all(rank is not None for rank in ranks)
            ]
            first_rank = min(complete_ranks, default=None)
            reciprocal = 1 / first_rank if first_rank else 0.0
            metrics.append(
                observed(
                    f"{stage}_mrr",
                    reciprocal,
                    numerator=reciprocal,
                    denominator=1,
                )
            )

    # These diagnostics are intentionally separate from recall denominators.
    # They describe the selected path's clauses and do not make an unused
    # alternative or a near-miss a required hit.  Downstream product readers
    # may also call ``localization_statistics`` for the per-Gold matrix.
    metrics.extend(_localization_metrics(stage, ordered, evidence_set, corpus))
    return metrics


def localization_statistics(
    stage_localization: StageLocalization,
    evidence_set: GoldEvidenceSet,
) -> dict[str, Any]:
    """Summarize selected-path localization without changing recall semantics.

    The ``counts`` values are clause counts.  An OR clause contributes exactly
    once, using its best alternative.  ``gold`` retains the full per-Gold
    matrix, including evidence IDs that are not part of the selected path for
    diagnostic display.
    """

    if not stage_localization.observable:
        return {
            "stage": stage_localization.stage,
            "observable": False,
            "counts": {},
            "denominator": 0,
            "gold": {},
        }
    path, _ = _best_path(stage_localization, evidence_set)
    counts: Counter[str] = Counter()
    if path is not None:
        for clause in path:
            statuses = [
                stage_localization.gold.get(evidence_id)
                for evidence_id in clause
            ]
            counts[_best_clause_status(statuses).value] += 1
    return {
        "stage": stage_localization.stage,
        "observable": True,
        "counts": dict(counts),
        # One OR clause is one required decision, regardless of how many
        # evidence IDs are listed as alternatives inside it.
        "denominator": len(path) if path is not None else 0,
        "selected_path": path,
        "gold": {
            evidence_id: localization.as_dict()
            for evidence_id, localization in stage_localization.gold.items()
        },
    }


# Readable aliases for report code.
stage_localization_statistics = localization_statistics


def _localization_metrics(
    stage: str,
    items: Sequence[RAGEvidenceItem],
    evidence_set: GoldEvidenceSet,
    corpus: CorpusEvidenceIndex,
) -> list[MetricResult]:
    localized = localize_stage(items, evidence_set, corpus, stage=stage)
    stats = localization_statistics(localized, evidence_set)
    denominator = int(stats.get("denominator") or 0)
    if not denominator:
        return []
    counts = stats.get("counts") or {}
    result: list[MetricResult] = []
    for status in LocalizationStatus:
        count = int(counts.get(status.value, 0))
        result.append(
            observed(
                f"{stage}_localization_{status.value}",
                count / denominator,
                numerator=count,
                denominator=denominator,
            )
        )
    return result


def _observability_for_localization(
    localized: StageLocalization,
    evidence_set: GoldEvidenceSet,
) -> str | None:
    if not localized.observable:
        return f"{localized.stage} stage is not observable"
    if localized.complete_path(evidence_set):
        return None
    for path in _paths(evidence_set):
        for clause in path:
            statuses = [
                localized.gold.get(evidence_id)
                for evidence_id in clause
            ]
            if any(
                value is not None and value.status == LocalizationStatus.MATCHED
                for value in statuses
            ):
                continue
            if any(
                value is not None
                and value.status == LocalizationStatus.PROVENANCE_MISSING
                for value in statuses
            ):
                return "runtime provenance mapping is unavailable for required Gold Evidence"
    return None


def _paths(evidence_set: GoldEvidenceSet) -> list[list[list[str]]]:
    return evidence_set.mses_paths or [evidence_set.required_groups]


def _path_clause_ranks(
    localized: StageLocalization,
    path: list[list[str]],
) -> list[int | None]:
    return [
        min(
            (
                localization.rank
                for evidence_id in clause
                if (localization := localized.gold.get(evidence_id)) is not None
                and localization.status == LocalizationStatus.MATCHED
                and localization.rank is not None
            ),
            default=None,
        )
        for clause in path
    ]


def _best_path(
    localized: StageLocalization,
    evidence_set: GoldEvidenceSet,
) -> tuple[list[list[str]] | None, list[int | None]]:
    candidates: list[tuple[tuple[Any, ...], int, list[list[str]], list[int | None]]] = []
    for index, path in enumerate(_paths(evidence_set)):
        ranks = _path_clause_ranks(localized, path)
        hits = sum(rank is not None for rank in ranks)
        complete = hits == len(ranks) and bool(ranks)
        max_rank = max((rank for rank in ranks if rank is not None), default=10**12)
        # Complete paths win; then clause coverage; then earliest completion;
        # then shorter paths; finally declaration order for reproducibility.
        key = (
            1 if complete else 0,
            hits / len(ranks) if ranks else 0.0,
            -max_rank,
            -len(ranks),
            -index,
        )
        candidates.append((key, index, path, ranks))
    if not candidates:
        return None, []
    _key, _index, path, ranks = max(candidates, key=lambda value: value[0])
    return path, ranks


def _best_clause_status(values: Sequence[GoldLocalization | None]) -> LocalizationStatus:
    statuses = {
        value.status for value in values if value is not None
    }
    if LocalizationStatus.MATCHED in statuses:
        return LocalizationStatus.MATCHED
    if LocalizationStatus.PARTIAL in statuses:
        return LocalizationStatus.PARTIAL
    if LocalizationStatus.PROVENANCE_MISSING in statuses:
        return LocalizationStatus.PROVENANCE_MISSING
    return LocalizationStatus.RETRIEVAL_MISSED


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
