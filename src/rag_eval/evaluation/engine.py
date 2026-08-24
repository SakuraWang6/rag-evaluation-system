"""Case-level deterministic evaluation."""

from __future__ import annotations

from rag_eval.contracts.adapter import RAGResult
from rag_eval.contracts.dataset import GoldAnswer, GoldEvidenceSet
from rag_eval.contracts.run import MetricResult, MetricStatus
from rag_eval.evaluation.answers import (
    ANSWER_SCORER_DIGEST,
    ANSWER_SCORER_ID,
    ANSWER_SCORER_VERSION,
    AnswerVerdict,
    score_answer,
)
from rag_eval.evaluation.evidence import CorpusEvidenceIndex, match_all
from rag_eval.evaluation.metrics import evaluate_retrieval_stages

GROUNDING_MODE = "deterministic_gold_evidence"


def evaluate_case(
    result: RAGResult,
    gold_answer: GoldAnswer,
    evidence_set: GoldEvidenceSet,
    corpus: CorpusEvidenceIndex,
    *,
    k_values: tuple[int, ...] = (1, 3, 5),
    evaluate_answer: bool = True,
) -> list[MetricResult]:
    metrics = evaluate_retrieval_stages(
        result, evidence_set, corpus, k_values=k_values
    )
    if not evaluate_answer:
        metrics.extend(
            [
                answer_not_applicable("answer_accuracy"),
                answer_not_applicable("answer_groundedness", grounding=True),
                answer_not_applicable("unsupported_answer_rate", grounding=True),
            ]
        )
        return metrics

    answer_score = score_answer(result.answer, gold_answer)
    if answer_score.verdict == AnswerVerdict.NEEDS_REVIEW:
        metrics.append(answer_needs_review("answer_accuracy", answer_score.reason))
    else:
        metrics.append(
            answer_observed("answer_accuracy", 1.0 if answer_score.passed else 0.0)
        )

    if result.final_context is None:
        metrics.extend(
            [
                answer_unavailable(
                    "answer_groundedness", "final context is not observable", grounding=True
                ),
                answer_unavailable(
                    "unsupported_answer_rate",
                    "final context is not observable",
                    grounding=True,
                ),
            ]
        )
        return metrics

    matches = match_all(result.final_context, evidence_set.evidence, corpus)
    evidence_complete = all(
        any(evidence_id in matches for evidence_id in group)
        for group in evidence_set.required_groups
    )
    if answer_score.verdict == AnswerVerdict.NEEDS_REVIEW:
        metrics.extend(
            [
                answer_needs_review(
                    "answer_groundedness", answer_score.reason, grounding=True
                ),
                answer_needs_review(
                    "unsupported_answer_rate", answer_score.reason, grounding=True
                ),
            ]
        )
        return metrics

    supported = answer_score.passed and evidence_complete
    metrics.extend(
        [
            answer_observed(
                "answer_groundedness", 1.0 if supported else 0.0, grounding=True
            ),
            answer_observed(
                "unsupported_answer_rate", 0.0 if supported else 1.0, grounding=True
            ),
        ]
    )
    return metrics


def answer_observed(
    metric_id: str, value: float, *, grounding: bool = False
) -> MetricResult:
    return MetricResult(
        metric_id=metric_id,
        status=MetricStatus.OBSERVED,
        value=value,
        numerator=value,
        denominator=1,
        scorer_id=ANSWER_SCORER_ID,
        scorer_version=ANSWER_SCORER_VERSION,
        scorer_digest=ANSWER_SCORER_DIGEST,
        evaluator_mode=GROUNDING_MODE if grounding else None,
    )


def answer_unavailable(
    metric_id: str, reason: str, *, grounding: bool = False
) -> MetricResult:
    return MetricResult(
        metric_id=metric_id,
        status=MetricStatus.UNAVAILABLE,
        scorer_id=ANSWER_SCORER_ID,
        scorer_version=ANSWER_SCORER_VERSION,
        scorer_digest=ANSWER_SCORER_DIGEST,
        evaluator_mode=GROUNDING_MODE if grounding else None,
        reason=reason,
    )


def answer_needs_review(
    metric_id: str, reason: str, *, grounding: bool = False
) -> MetricResult:
    return MetricResult(
        metric_id=metric_id,
        status=MetricStatus.NEEDS_REVIEW,
        scorer_id=ANSWER_SCORER_ID,
        scorer_version=ANSWER_SCORER_VERSION,
        scorer_digest=ANSWER_SCORER_DIGEST,
        evaluator_mode=GROUNDING_MODE if grounding else None,
        reason=reason,
    )


def answer_not_applicable(
    metric_id: str, *, grounding: bool = False
) -> MetricResult:
    return MetricResult(
        metric_id=metric_id,
        status=MetricStatus.NOT_APPLICABLE,
        scorer_id=ANSWER_SCORER_ID,
        scorer_version=ANSWER_SCORER_VERSION,
        scorer_digest=ANSWER_SCORER_DIGEST,
        evaluator_mode=GROUNDING_MODE if grounding else None,
        reason="answer generation is disabled for this experiment",
    )
