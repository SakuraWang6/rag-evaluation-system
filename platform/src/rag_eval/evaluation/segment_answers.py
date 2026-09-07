"""P1 answer scoring that is independent from legacy locator provenance.

The vNext benchmark has no need to re-enter the Word/OOXML evidence
localizer for answer evaluation.  Accuracy, Gold-context grounding, and
hallucination are deliberately separate outputs:

* accuracy is the deterministic typed-answer rule;
* grounding is a statement about whether the *returned segment context*
  completes a Gold path;
* hallucination is intentionally conservative.  A retrieval miss never proves
  a generated claim is hallucinated, so non-trivial cases stay available for
  the existing LLM/human review flow.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from rag_eval.contracts.adapter import RAGResult
from rag_eval.contracts.benchmark import (
    BenchmarkGold,
    SegmentEvaluationOutcome,
    SegmentEvaluationTrace,
)
from rag_eval.contracts.dataset import GoldAnswerKind
from rag_eval.contracts.run import MetricResult, MetricStatus
from rag_eval.evaluation import answers as answers_module
from rag_eval.evaluation.answers import (
    ANSWER_SCORER_DIGEST,
    ANSWER_SCORER_ID,
    ANSWER_SCORER_VERSION,
    AnswerVerdict,
    score_answer,
)


SEGMENT_ANSWER_SCORER_ID = "segment-native-answer-evidence"
SEGMENT_ANSWER_SCORER_VERSION = "1.0"


def scorer_digest() -> str:
    """Fingerprint the P1 reducer, not a manually maintained label."""

    digest = hashlib.sha256()
    for path in (Path(__file__), Path(answers_module.__file__)):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<source-unavailable>")
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


SEGMENT_ANSWER_SCORER_DIGEST = scorer_digest()

BENCHMARK_ANSWER_METRIC_IDS = (
    "answer_accuracy",
    "answer_groundedness",
    "answer_hallucination",
)


def _metric(
    metric_id: str,
    *,
    status: MetricStatus,
    value: float | None = None,
    reason: str | None = None,
    evaluator_mode: str | None = None,
    typed_answer: bool = False,
) -> MetricResult:
    return MetricResult(
        metric_id=metric_id,
        status=status,
        value=value,
        numerator=value if status == MetricStatus.OBSERVED else None,
        denominator=1 if status == MetricStatus.OBSERVED else None,
        scorer_id=ANSWER_SCORER_ID if typed_answer else SEGMENT_ANSWER_SCORER_ID,
        scorer_version=ANSWER_SCORER_VERSION if typed_answer else SEGMENT_ANSWER_SCORER_VERSION,
        scorer_digest=ANSWER_SCORER_DIGEST if typed_answer else SEGMENT_ANSWER_SCORER_DIGEST,
        evaluator_mode=evaluator_mode,
        reason=reason,
    )


def answer_not_applicable_metrics(reason: str) -> list[MetricResult]:
    """Return all P1 metrics as explicitly unscored, never as zeros."""

    return [
        _metric(
            "answer_accuracy",
            status=MetricStatus.NOT_APPLICABLE,
            reason=reason,
            evaluator_mode="answer_generation_disabled",
            typed_answer=True,
        ),
        _metric(
            "answer_groundedness",
            status=MetricStatus.NOT_APPLICABLE,
            reason=reason,
            evaluator_mode="answer_generation_disabled",
        ),
        _metric(
            "answer_hallucination",
            status=MetricStatus.NOT_APPLICABLE,
            reason=reason,
            evaluator_mode="answer_generation_disabled",
        ),
    ]


def answer_error_metrics(reason: str) -> list[MetricResult]:
    """Represent a query/adapter failure without inventing answer scores."""

    return [
        _metric(
            "answer_accuracy",
            status=MetricStatus.ERROR,
            reason=reason,
            evaluator_mode="answer_generation_runtime_error",
            typed_answer=True,
        ),
        _metric(
            "answer_groundedness",
            status=MetricStatus.ERROR,
            reason=reason,
            evaluator_mode="segment_gold_context",
        ),
        _metric(
            "answer_hallucination",
            status=MetricStatus.ERROR,
            reason=reason,
            evaluator_mode="semantic_support_review",
        ),
    ]


def evaluate_segment_answer(
    result: RAGResult,
    gold: BenchmarkGold,
    retrieval: SegmentEvaluationTrace,
    *,
    evaluate_answer: bool,
) -> list[MetricResult]:
    """Score the three independent P1 answer outcomes for one benchmark case."""

    if not evaluate_answer:
        return answer_not_applicable_metrics("answer generation is disabled for this experiment")

    answer = result.answer or ""
    rule = score_answer(answer, gold.answer)
    accuracy = _accuracy_metric(rule)
    grounding = _grounding_metric(gold, retrieval)
    hallucination = _hallucination_metric(
        answer=answer,
        gold=gold,
        rule=rule,
        grounding=grounding,
        retrieval=retrieval,
    )
    return [accuracy, grounding, hallucination]


def _accuracy_metric(rule) -> MetricResult:
    if rule.verdict == AnswerVerdict.NEEDS_REVIEW:
        return _metric(
            "answer_accuracy",
            status=MetricStatus.NEEDS_REVIEW,
            reason=rule.reason,
            evaluator_mode="typed_answer_rule_then_semantic_review",
            typed_answer=True,
        )
    return _metric(
        "answer_accuracy",
        status=MetricStatus.OBSERVED,
        value=1.0 if rule.verdict == AnswerVerdict.PASS else 0.0,
        reason=rule.reason,
        evaluator_mode="typed_answer_rule",
        typed_answer=True,
    )


def _grounding_metric(
    gold: BenchmarkGold,
    retrieval: SegmentEvaluationTrace,
) -> MetricResult:
    if gold.answer.kind == GoldAnswerKind.ABSTAIN:
        return _metric(
            "answer_groundedness",
            status=MetricStatus.NOT_APPLICABLE,
            reason="abstain Gold has no positive segment evidence path",
            evaluator_mode="segment_gold_context",
        )
    context = retrieval.context
    if context.outcome == SegmentEvaluationOutcome.COMPLETE:
        return _metric(
            "answer_groundedness",
            status=MetricStatus.OBSERVED,
            value=1.0,
            evaluator_mode="segment_gold_context",
        )
    if context.outcome in {
        SegmentEvaluationOutcome.PARTIAL_COVERAGE,
        SegmentEvaluationOutcome.RETRIEVAL_MISSING,
    }:
        return _metric(
            "answer_groundedness",
            status=MetricStatus.OBSERVED,
            value=0.0,
            reason=(
                "final segment context did not complete a Gold evidence path; "
                "this does not determine hallucination"
            ),
            evaluator_mode="segment_gold_context",
        )
    if context.outcome in {
        SegmentEvaluationOutcome.UNSUPPORTED_STAGE,
        SegmentEvaluationOutcome.NOT_APPLICABLE,
    }:
        return _metric(
            "answer_groundedness",
            status=MetricStatus.NOT_APPLICABLE,
            reason=context.reason or "final context stage is not exposed by this adapter",
            evaluator_mode="segment_gold_context",
        )
    return _metric(
        "answer_groundedness",
        status=MetricStatus.ERROR,
        reason=context.reason or f"final context stage is {context.outcome.value}",
        evaluator_mode="segment_gold_context",
    )


def _hallucination_metric(
    *,
    answer: str,
    gold: BenchmarkGold,
    rule,
    grounding: MetricResult,
    retrieval: SegmentEvaluationTrace,
) -> MetricResult:
    """Avoid treating retrieval evidence state as a hallucination verdict."""

    if retrieval.context.outcome in {
        SegmentEvaluationOutcome.RUNTIME_ERROR,
        SegmentEvaluationOutcome.MAPPING_CORRUPTED,
    }:
        return _metric(
            "answer_hallucination",
            status=MetricStatus.ERROR,
            reason=retrieval.context.reason or "final context trace is invalid",
            evaluator_mode="semantic_support_review",
        )
    if not answer.strip():
        return _metric(
            "answer_hallucination",
            status=MetricStatus.OBSERVED,
            value=0.0,
            reason="empty answer contains no affirmative unsupported claim",
            evaluator_mode="rule_no_claim",
        )
    if rule.verdict == AnswerVerdict.PASS and (
        gold.answer.kind == GoldAnswerKind.ABSTAIN
        or (
            grounding.status == MetricStatus.OBSERVED
            and grounding.value == 1.0
        )
    ):
        return _metric(
            "answer_hallucination",
            status=MetricStatus.OBSERVED,
            value=0.0,
            reason="deterministic answer rule passed and required support is complete",
            evaluator_mode="rule_plus_segment_gold_context",
        )
    return _metric(
        "answer_hallucination",
        status=MetricStatus.NEEDS_REVIEW,
        reason=(
            "retrieval coverage alone cannot establish whether the generated "
            "answer is semantically supported; route to LLM judge then human review"
        ),
        evaluator_mode="semantic_support_review",
    )
