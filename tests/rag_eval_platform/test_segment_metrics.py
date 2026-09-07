"""Strict segment-native retrieval evaluation regressions."""

from __future__ import annotations

from rag_eval.contracts.adapter import (
    RAGResult,
    SegmentTraceItem,
    SegmentTraceSet,
    SegmentTraceStage,
    SegmentTraceStatus,
)
from rag_eval.contracts.benchmark import BenchmarkGold, segment_mapping_receipt
from rag_eval.contracts.dataset import GoldAnswer, GoldAnswerKind
from rag_eval.contracts.run import MetricStatus
from rag_eval.evaluation.segment_metrics import evaluate_segment_retrieval


CONTRACT_DIGEST = "a" * 64
SEGMENTS = {"segment-a", "segment-b", "segment-c"}


def _gold() -> BenchmarkGold:
    return BenchmarkGold(
        gold_id="gold-case",
        case_id="case",
        answer=GoldAnswer(gold_answer_id="answer", kind=GoldAnswerKind.TEXT, canonical="answer"),
        # One complete path requires A and B; C is an alternative for B.
        evidence_paths=((("segment-a",), ("segment-b", "segment-c")),),
    )


def _item(native_id: str, rank: int, segment_ids: tuple[str, ...]) -> SegmentTraceItem:
    return SegmentTraceItem(
        native_chunk_id=native_id,
        rank=rank,
        content=native_id,
        source_segment_ids=segment_ids,
        mapping_receipt_digest=segment_mapping_receipt(CONTRACT_DIGEST, native_id, segment_ids),
    )


def _observed(stage: str, *items: SegmentTraceItem) -> SegmentTraceStage:
    return SegmentTraceStage(
        stage=stage,  # type: ignore[arg-type]
        status=SegmentTraceStatus.OBSERVED,
        items=items,
        mapping_manifest_digest=CONTRACT_DIGEST,
    )


def _result(*items: SegmentTraceItem) -> RAGResult:
    return RAGResult(
        segment_traces=SegmentTraceSet(
            raw=_observed("raw", *items),
            ranked=_observed("ranked", *items),
            context=_observed("context", *items),
        )
    )


def _metrics_by_id(result: RAGResult) -> tuple[dict[str, object], object]:
    metrics, trace = evaluate_segment_retrieval(
        result,
        _gold(),
        benchmark_contract_digest=CONTRACT_DIGEST,
        known_segment_ids=SEGMENTS,
    )
    return {item.metric_id: item for item in metrics}, trace


def test_complete_path_is_scored_and_persists_stage_by_gold_matrix() -> None:
    metrics, trace = _metrics_by_id(
        _result(_item("native-a", 1, ("segment-a",)), _item("native-b", 2, ("segment-b",)))
    )

    recall = metrics["segment_ranked_recall@3"]
    mrr = metrics["segment_ranked_mrr"]
    assert recall.status == MetricStatus.OBSERVED and recall.value == 1.0
    assert mrr.status == MetricStatus.OBSERVED and mrr.value == 0.5
    assert trace.ranked.outcome.value == "complete"
    assert len(trace.ranked.clause_matrix) == 2


def test_partial_and_empty_observed_results_are_not_unverifiable() -> None:
    partial_metrics, partial_trace = _metrics_by_id(_result(_item("native-a", 1, ("segment-a",))))
    missing_metrics, missing_trace = _metrics_by_id(_result())

    assert partial_trace.raw.outcome.value == "partial_coverage"
    assert partial_metrics["segment_raw_recall@1"].value == 0.5
    assert missing_trace.raw.outcome.value == "retrieval_missing"
    assert missing_metrics["segment_raw_recall@1"].status == MetricStatus.OBSERVED
    assert missing_metrics["segment_raw_recall@1"].value == 0.0


def test_unsupported_runtime_error_and_mapping_corruption_keep_distinct_statuses() -> None:
    unsupported = RAGResult(
        segment_traces=SegmentTraceSet(
            raw=SegmentTraceStage(stage="raw", status=SegmentTraceStatus.UNSUPPORTED_STAGE, reason="not exposed"),
            ranked=SegmentTraceStage(stage="ranked", status=SegmentTraceStatus.UNSUPPORTED_STAGE, reason="not exposed"),
            context=SegmentTraceStage(stage="context", status=SegmentTraceStatus.UNSUPPORTED_STAGE, reason="not exposed"),
        )
    )
    unsupported_metrics, unsupported_trace = _metrics_by_id(unsupported)
    assert unsupported_trace.raw.outcome.value == "unsupported_stage"
    assert unsupported_metrics["segment_raw_recall@1"].status == MetricStatus.NOT_APPLICABLE

    runtime = RAGResult(
        segment_traces=SegmentTraceSet(
            raw=SegmentTraceStage(stage="raw", status=SegmentTraceStatus.RUNTIME_ERROR, reason="ReadTimeout"),
            ranked=SegmentTraceStage(stage="ranked", status=SegmentTraceStatus.RUNTIME_ERROR, reason="ReadTimeout"),
            context=SegmentTraceStage(stage="context", status=SegmentTraceStatus.RUNTIME_ERROR, reason="ReadTimeout"),
        )
    )
    runtime_metrics, runtime_trace = _metrics_by_id(runtime)
    assert runtime_trace.raw.outcome.value == "runtime_error"
    assert runtime_metrics["segment_raw_recall@1"].status == MetricStatus.ERROR

    corrupt_item = _item("native-a", 1, ("segment-a",)).model_copy(
        update={"mapping_receipt_digest": "0" * 64}
    )
    corrupt_metrics, corrupt_trace = _metrics_by_id(_result(corrupt_item))
    assert corrupt_trace.raw.outcome.value == "mapping_corrupted"
    assert corrupt_metrics["segment_raw_recall@1"].status == MetricStatus.ERROR


def test_multi_segment_native_chunk_is_diagnostic_not_a_fake_zero() -> None:
    metrics, trace = _metrics_by_id(
        _result(_item("native-many", 1, ("segment-a", "segment-b")))
    )

    assert trace.raw.strict_rankable is False
    assert trace.raw.outcome.value == "unsupported_stage"
    assert metrics["segment_raw_recall@1"].status == MetricStatus.NOT_APPLICABLE
