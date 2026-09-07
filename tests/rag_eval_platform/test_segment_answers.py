"""P1 answer scoring must remain separate from segment retrieval outcomes."""

from __future__ import annotations

from rag_eval.contracts.adapter import RAGResult, SegmentTraceStatus
from rag_eval.contracts.benchmark import (
    BenchmarkGold,
    SegmentEvaluationOutcome,
    SegmentEvaluationStage,
    SegmentEvaluationTrace,
)
from rag_eval.contracts.dataset import GoldAnswer, GoldAnswerKind
from rag_eval.contracts.run import MetricStatus
from rag_eval.evaluation.segment_answers import evaluate_segment_answer


def _gold() -> BenchmarkGold:
    return BenchmarkGold(
        gold_id="gold",
        case_id="case",
        answer=GoldAnswer(
            gold_answer_id="answer",
            kind=GoldAnswerKind.TEXT,
            canonical="正确答案",
        ),
        evidence_paths=((('segment-a',),),),
    )


def _trace(context: SegmentEvaluationOutcome) -> SegmentEvaluationTrace:
    def stage(name: str, outcome: SegmentEvaluationOutcome) -> SegmentEvaluationStage:
        return SegmentEvaluationStage(
            stage=name,  # type: ignore[arg-type]
            status=(
                SegmentTraceStatus.RUNTIME_ERROR
                if outcome == SegmentEvaluationOutcome.RUNTIME_ERROR
                else SegmentTraceStatus.OBSERVED
            ),
            outcome=outcome,
            strict_rankable=outcome != SegmentEvaluationOutcome.RUNTIME_ERROR,
            reason="adapter timed out" if outcome == SegmentEvaluationOutcome.RUNTIME_ERROR else None,
        )

    return SegmentEvaluationTrace(
        benchmark_contract_digest="a" * 64,
        raw=stage("raw", SegmentEvaluationOutcome.COMPLETE),
        ranked=stage("ranked", SegmentEvaluationOutcome.COMPLETE),
        context=stage("context", context),
    )


def _by_id(metrics):
    return {metric.metric_id: metric for metric in metrics}


def test_correct_answer_and_complete_segment_context_are_independently_observed() -> None:
    metrics = _by_id(
        evaluate_segment_answer(
            RAGResult(answer="正确答案"),
            _gold(),
            _trace(SegmentEvaluationOutcome.COMPLETE),
            evaluate_answer=True,
        )
    )

    assert metrics["answer_accuracy"].value == 1.0
    assert metrics["answer_groundedness"].value == 1.0
    assert metrics["answer_hallucination"].value == 0.0


def test_retrieval_miss_does_not_become_a_hallucination_verdict() -> None:
    metrics = _by_id(
        evaluate_segment_answer(
            RAGResult(answer="正确答案"),
            _gold(),
            _trace(SegmentEvaluationOutcome.RETRIEVAL_MISSING),
            evaluate_answer=True,
        )
    )

    assert metrics["answer_accuracy"].status == MetricStatus.OBSERVED
    assert metrics["answer_accuracy"].value == 1.0
    assert metrics["answer_groundedness"].value == 0.0
    assert metrics["answer_hallucination"].status == MetricStatus.NEEDS_REVIEW


def test_disabled_answer_generation_and_runtime_errors_never_become_zero_scores() -> None:
    disabled = _by_id(
        evaluate_segment_answer(
            RAGResult(), _gold(), _trace(SegmentEvaluationOutcome.COMPLETE), evaluate_answer=False
        )
    )
    assert all(metric.status == MetricStatus.NOT_APPLICABLE for metric in disabled.values())

    runtime = _by_id(
        evaluate_segment_answer(
            RAGResult(answer="正确答案"),
            _gold(),
            _trace(SegmentEvaluationOutcome.RUNTIME_ERROR),
            evaluate_answer=True,
        )
    )
    assert runtime["answer_groundedness"].status == MetricStatus.ERROR
    assert runtime["answer_hallucination"].status == MetricStatus.ERROR
