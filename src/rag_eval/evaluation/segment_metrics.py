"""Segment-native retrieval scoring for ``rag-benchmark-contract/1``.

This evaluator never consults Word locations, canonical-object locators, or a
post-hoc text matcher.  It only accepts the dataset's immutable leaf IDs and
the adapter's typed mapping receipts.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Sequence

from rag_eval.contracts.adapter import (
    RAGResult,
    SegmentTraceItem,
    SegmentTraceStage,
    SegmentTraceStatus,
)
from rag_eval.contracts.benchmark import (
    BenchmarkGold,
    SegmentClauseMatrix,
    SegmentEvaluationOutcome,
    SegmentEvaluationStage,
    SegmentEvaluationTrace,
    segment_mapping_receipt,
)
from rag_eval.contracts.run import MetricResult, MetricStatus


SEGMENT_SCORER_ID = "segment-native-retrieval"
SEGMENT_SCORER_VERSION = "1.0"


def scorer_digest() -> str:
    try:
        payload = Path(__file__).read_bytes()
    except OSError:
        payload = b"<source-unavailable>"
    return "sha256:" + hashlib.sha256(payload).hexdigest()


SEGMENT_SCORER_DIGEST = scorer_digest()


def _metric(
    metric_id: str,
    *,
    value: float | None = None,
    numerator: float | None = None,
    denominator: float | None = None,
    status: MetricStatus = MetricStatus.OBSERVED,
    reason: str | None = None,
) -> MetricResult:
    return MetricResult(
        metric_id=metric_id,
        status=status,
        value=value,
        numerator=numerator,
        denominator=denominator,
        scorer_id=SEGMENT_SCORER_ID,
        scorer_version=SEGMENT_SCORER_VERSION,
        scorer_digest=SEGMENT_SCORER_DIGEST,
        reason=reason,
    )


def _metric_ids(stage: str, k_values: Sequence[int]) -> list[str]:
    values = [
        f"segment_{stage}_recall@{cutoff}" for cutoff in k_values
    ] + [
        f"segment_{stage}_gold_evidence_coverage@{cutoff}" for cutoff in k_values
    ] + [
        f"segment_{stage}_complete_evidence_coverage@{cutoff}"
        for cutoff in k_values
    ]
    if stage in {"raw", "ranked"}:
        values.append(f"segment_{stage}_mrr")
    return values


def _non_observed_metrics(
    stage: str,
    k_values: Sequence[int],
    *,
    status: MetricStatus,
    reason: str,
) -> list[MetricResult]:
    return [_metric(metric_id, status=status, reason=reason) for metric_id in _metric_ids(stage, k_values)]


def _rank_map(items: Sequence[SegmentTraceItem]) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for item in items:
        # Strict scoring calls this only after confirming there is exactly one
        # segment per native ranked item.
        segment_id = item.source_segment_ids[0]
        ranks[segment_id] = min(ranks.get(segment_id, item.rank), item.rank)
    return ranks


def _matrix(
    gold: BenchmarkGold,
    ranks: dict[str, int],
) -> tuple[tuple[SegmentClauseMatrix, ...], tuple[int, ...]]:
    clauses: list[SegmentClauseMatrix] = []
    complete_paths: list[int] = []
    for path_index, path in enumerate(gold.evidence_paths):
        complete = True
        for clause_index, alternatives in enumerate(path):
            matched = tuple(
                segment_id for segment_id in alternatives if segment_id in ranks
            )
            earliest = min((ranks[item] for item in matched), default=None)
            clauses.append(
                SegmentClauseMatrix(
                    path_index=path_index,
                    clause_index=clause_index,
                    alternatives=alternatives,
                    matched_segment_ids=matched,
                    earliest_rank=earliest,
                )
            )
            if not matched:
                complete = False
        if complete:
            complete_paths.append(path_index)
    return tuple(clauses), tuple(complete_paths)


def _best_path_coverage(
    gold: BenchmarkGold,
    ranks: dict[str, int],
) -> tuple[int, int, int | None]:
    """Return best MSES clause coverage and earliest complete-path rank."""

    candidates: list[tuple[int, int, int | None, int]] = []
    for path_index, path in enumerate(gold.evidence_paths):
        hit_ranks = [
            min((ranks[item] for item in clause if item in ranks), default=None)
            for clause in path
        ]
        hits = sum(rank is not None for rank in hit_ranks)
        completion = max((rank for rank in hit_ranks if rank is not None), default=None)
        complete_rank = completion if hits == len(path) and path else None
        candidates.append((hits, len(path), complete_rank, -path_index))
    if not candidates:
        return 0, 0, None
    # Prefer complete paths, then most clause hits, then early completion,
    # then a shorter denominator, then declaration order.
    hits, denominator, complete_rank, _ = max(
        candidates,
        key=lambda item: (
            int(item[2] is not None),
            item[0] / item[1] if item[1] else 0,
            -(item[2] or 10**12),
            -item[1],
            item[3],
        ),
    )
    return hits, denominator, complete_rank


def _validate_observed_stage(
    stage: SegmentTraceStage,
    *,
    benchmark_contract_digest: str,
    known_segment_ids: set[str],
) -> str | None:
    if stage.mapping_manifest_digest != benchmark_contract_digest:
        return "stage mapping manifest digest does not match the benchmark contract"
    native_ids: set[str] = set()
    for item in stage.items:
        if item.native_chunk_id in native_ids:
            return "stage repeats a native chunk ID"
        native_ids.add(item.native_chunk_id)
        unknown = set(item.source_segment_ids).difference(known_segment_ids)
        if unknown:
            return f"stage maps to unknown segment IDs: {sorted(unknown)}"
        expected = segment_mapping_receipt(
            benchmark_contract_digest,
            item.native_chunk_id,
            item.source_segment_ids,
        )
        if item.mapping_receipt_digest != expected:
            return "stage mapping receipt does not match its native chunk and segment IDs"
    return None


def evaluate_segment_stage(
    stage: SegmentTraceStage,
    gold: BenchmarkGold,
    *,
    benchmark_contract_digest: str,
    known_segment_ids: set[str],
    k_values: Sequence[int],
) -> tuple[list[MetricResult], SegmentEvaluationStage]:
    """Score one trace boundary without fabricating an unavailable metric."""

    if gold.answer.kind.value == "abstain":
        reason = "abstain Gold has no positive retrieval evidence path"
        return (
            _non_observed_metrics(stage.stage, k_values, status=MetricStatus.NOT_APPLICABLE, reason=reason),
            SegmentEvaluationStage(
                stage=stage.stage,
                status=stage.status,
                outcome=SegmentEvaluationOutcome.NOT_APPLICABLE,
                strict_rankable=False,
                reason=reason,
            ),
        )
    if stage.status == SegmentTraceStatus.UNSUPPORTED_STAGE:
        reason = stage.reason or "adapter does not expose this retrieval stage"
        return (
            _non_observed_metrics(stage.stage, k_values, status=MetricStatus.NOT_APPLICABLE, reason=reason),
            SegmentEvaluationStage(
                stage=stage.stage,
                status=stage.status,
                outcome=SegmentEvaluationOutcome.UNSUPPORTED_STAGE,
                strict_rankable=False,
                reason=reason,
            ),
        )
    if stage.status == SegmentTraceStatus.RUNTIME_ERROR:
        reason = stage.reason or "adapter failed while collecting this retrieval stage"
        return (
            _non_observed_metrics(stage.stage, k_values, status=MetricStatus.ERROR, reason=reason),
            SegmentEvaluationStage(
                stage=stage.stage,
                status=stage.status,
                outcome=SegmentEvaluationOutcome.RUNTIME_ERROR,
                strict_rankable=False,
                reason=reason,
            ),
        )
    if stage.status == SegmentTraceStatus.MAPPING_CORRUPTED:
        reason = stage.reason or "adapter reported a corrupted segment mapping"
        return (
            _non_observed_metrics(stage.stage, k_values, status=MetricStatus.ERROR, reason=reason),
            SegmentEvaluationStage(
                stage=stage.stage,
                status=stage.status,
                outcome=SegmentEvaluationOutcome.MAPPING_CORRUPTED,
                strict_rankable=False,
                reason=reason,
            ),
        )

    corruption = _validate_observed_stage(
        stage,
        benchmark_contract_digest=benchmark_contract_digest,
        known_segment_ids=known_segment_ids,
    )
    if corruption is not None:
        return (
            _non_observed_metrics(stage.stage, k_values, status=MetricStatus.ERROR, reason=corruption),
            SegmentEvaluationStage(
                stage=stage.stage,
                status=SegmentTraceStatus.MAPPING_CORRUPTED,
                outcome=SegmentEvaluationOutcome.MAPPING_CORRUPTED,
                strict_rankable=False,
                reason=corruption,
            ),
        )
    if any(len(item.source_segment_ids) != 1 for item in stage.items):
        reason = "native chunk covers multiple source segments; strict segment ranking is unavailable"
        ranks = _rank_map([item for item in stage.items if len(item.source_segment_ids) == 1])
        matrix, paths = _matrix(gold, ranks)
        return (
            _non_observed_metrics(stage.stage, k_values, status=MetricStatus.NOT_APPLICABLE, reason=reason),
            SegmentEvaluationStage(
                stage=stage.stage,
                status=stage.status,
                outcome=SegmentEvaluationOutcome.UNSUPPORTED_STAGE,
                strict_rankable=False,
                clause_matrix=matrix,
                complete_path_indices=paths,
                reason=reason,
            ),
        )

    ordered = tuple(sorted(stage.items, key=lambda item: (item.rank, item.native_chunk_id)))
    ranks = _rank_map(ordered)
    matrix, complete_paths = _matrix(gold, ranks)
    hits, denominator, complete_rank = _best_path_coverage(gold, ranks)
    if complete_paths:
        outcome = SegmentEvaluationOutcome.COMPLETE
    elif hits:
        outcome = SegmentEvaluationOutcome.PARTIAL_COVERAGE
    else:
        outcome = SegmentEvaluationOutcome.RETRIEVAL_MISSING
    metrics: list[MetricResult] = []
    for cutoff in k_values:
        cutoff_ranks = {segment_id: rank for segment_id, rank in ranks.items() if rank <= cutoff}
        cutoff_hits, cutoff_denominator, cutoff_complete_rank = _best_path_coverage(gold, cutoff_ranks)
        coverage = cutoff_hits / cutoff_denominator if cutoff_denominator else 0.0
        complete = 1.0 if cutoff_complete_rank is not None else 0.0
        metrics.extend(
            (
                _metric(
                    f"segment_{stage.stage}_recall@{cutoff}",
                    value=coverage,
                    numerator=cutoff_hits,
                    denominator=cutoff_denominator,
                ),
                _metric(
                    f"segment_{stage.stage}_gold_evidence_coverage@{cutoff}",
                    value=coverage,
                    numerator=cutoff_hits,
                    denominator=cutoff_denominator,
                ),
                _metric(
                    f"segment_{stage.stage}_complete_evidence_coverage@{cutoff}",
                    value=complete,
                    numerator=complete,
                    denominator=1,
                ),
            )
        )
    if stage.stage in {"raw", "ranked"}:
        metrics.append(
            _metric(
                f"segment_{stage.stage}_mrr",
                value=1 / complete_rank if complete_rank else 0.0,
                numerator=1 / complete_rank if complete_rank else 0.0,
                denominator=1,
            )
        )
    return (
        metrics,
        SegmentEvaluationStage(
            stage=stage.stage,
            status=stage.status,
            outcome=outcome,
            strict_rankable=True,
            clause_matrix=matrix,
            complete_path_indices=complete_paths,
            reason=None,
        ),
    )


def _stage_loss(
    *,
    metric_id: str,
    left: Sequence[MetricResult],
    right: Sequence[MetricResult],
    cutoff: int,
) -> MetricResult:
    left_id = next(
        (item for item in left if item.metric_id.endswith(f"recall@{cutoff}")),
        None,
    )
    right_id = next(
        (item for item in right if item.metric_id.endswith(f"recall@{cutoff}")),
        None,
    )
    if (
        left_id is None
        or right_id is None
        or left_id.status != MetricStatus.OBSERVED
        or right_id.status != MetricStatus.OBSERVED
        or left_id.value is None
        or right_id.value is None
    ):
        return _metric(
            metric_id,
            status=MetricStatus.NOT_APPLICABLE,
            reason="both strict source stages must be observed",
        )
    loss = max(left_id.value - right_id.value, 0.0)
    return _metric(metric_id, value=loss, numerator=loss, denominator=1)


def evaluate_segment_retrieval(
    result: RAGResult,
    gold: BenchmarkGold,
    *,
    benchmark_contract_digest: str,
    known_segment_ids: set[str],
    k_values: Sequence[int] = (1, 3, 5, 10),
) -> tuple[list[MetricResult], SegmentEvaluationTrace]:
    """Return strict metrics and the persisted stage-by-Gold evidence matrix."""

    if result.segment_traces is None:
        missing = SegmentTraceStage(
            stage="raw",
            status=SegmentTraceStatus.UNSUPPORTED_STAGE,
            reason="adapter did not return segment-native retrieval traces",
        )
        traces = {"raw": missing, "ranked": missing.model_copy(update={"stage": "ranked"}), "context": missing.model_copy(update={"stage": "context"})}
    else:
        traces = {
            "raw": result.segment_traces.raw,
            "ranked": result.segment_traces.ranked,
            "context": result.segment_traces.context,
        }
    by_stage: dict[str, list[MetricResult]] = {}
    evaluations: dict[str, SegmentEvaluationStage] = {}
    metrics: list[MetricResult] = []
    for name in ("raw", "ranked", "context"):
        stage_metrics, stage_trace = evaluate_segment_stage(
            traces[name],
            gold,
            benchmark_contract_digest=benchmark_contract_digest,
            known_segment_ids=known_segment_ids,
            k_values=k_values,
        )
        by_stage[name] = stage_metrics
        evaluations[name] = stage_trace
        metrics.extend(stage_metrics)
    for cutoff in k_values:
        metrics.append(
            _stage_loss(
                metric_id=f"segment_raw_to_ranked_evidence_loss@{cutoff}",
                left=by_stage["raw"],
                right=by_stage["ranked"],
                cutoff=cutoff,
            )
        )
        metrics.append(
            _stage_loss(
                metric_id=f"segment_ranked_to_context_evidence_loss@{cutoff}",
                left=by_stage["ranked"],
                right=by_stage["context"],
                cutoff=cutoff,
            )
        )
    return (
        metrics,
        SegmentEvaluationTrace(
            benchmark_contract_digest=benchmark_contract_digest,
            raw=evaluations["raw"],
            ranked=evaluations["ranked"],
            context=evaluations["context"],
        ),
    )
