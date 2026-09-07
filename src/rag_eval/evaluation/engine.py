"""Case-level deterministic evaluation."""

from __future__ import annotations

import hashlib
from pathlib import Path

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
from rag_eval.evaluation import evidence as evidence_module
from rag_eval.evaluation import metrics as metrics_module
from rag_eval.evaluation.evidence import (
    CorpusEvidenceIndex,
    evidence_observability,
    localize_stage,
)
from rag_eval.evaluation.metrics import evaluate_retrieval_stages

GROUNDING_MODE = "deterministic_gold_evidence"
GROUNDING_SCORER_ID = "gold-evidence-grounding"
GROUNDING_SCORER_VERSION = "1.0"


def grounding_source_digest() -> str:
    """Digest the actual source for the Gold-localization projection.

    Grounding is a separate product metric from typed answer correctness and
    must therefore carry a scorer identity that changes when its source,
    evidence localizer, or metric reducer changes.
    """

    digest = hashlib.sha256()
    for path in (
        Path(__file__),
        Path(evidence_module.__file__),
        Path(metrics_module.__file__),
    ):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<source-unavailable>")
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


GROUNDING_SCORER_DIGEST = grounding_source_digest()


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
                answer_needs_review(
                    "unsupported_answer_rate",
                    "unsupported-proof-unavailable: final context is not observable",
                    grounding=True,
                ),
            ]
        )
        return metrics

    # Grounding is a source-localization projection, not answer correctness.
    # A semantically correct answer with a strict Gold locator miss therefore
    # remains answer-correct while its unsupported-proof metric is left for
    # semantic adjudication instead of being forced to one.
    localization = localize_stage(
        result.final_context, evidence_set, corpus, stage="context"
    )
    observability_reason = evidence_observability(
        result.final_context, evidence_set, corpus
    )
    evidence_complete = localization.complete_path(evidence_set)
    if observability_reason is not None:
        metrics.append(
            answer_unavailable(
                "answer_groundedness", observability_reason, grounding=True
            )
        )
        metrics.append(
            answer_needs_review(
                "unsupported_answer_rate",
                "unsupported-proof-unavailable: " + observability_reason,
                grounding=True,
            )
        )
        return metrics

    metrics.extend(
        [
            answer_observed(
                "answer_groundedness", 1.0 if evidence_complete else 0.0, grounding=True
            ),
            answer_needs_review(
                "unsupported_answer_rate",
                "unsupported-proof-unavailable: strict Gold coverage is incomplete; semantic support was not adjudicated"
                if not evidence_complete
                else "",
                grounding=True,
            ),
        ]
    )
    # A complete deterministic path plus a deterministic answer pass is the
    # narrow compatibility case where unsupportedness can be observed as zero.
    # Gold coverage alone cannot establish that an incorrect answer was
    # supported: a complete context containing ``42 ms`` does not support a
    # generated ``999 ms`` answer.  Such cases stay explicitly undecided for
    # semantic adjudication while answer_accuracy remains independently 0.
    if evidence_complete and answer_score.verdict == AnswerVerdict.PASS:
        metrics[-1] = answer_observed(
            "unsupported_answer_rate", 0.0, grounding=True
        )
    return metrics


def answer_observed(
    metric_id: str, value: float, *, grounding: bool = False
) -> MetricResult:
    scorer_id, scorer_version, scorer_digest = _answer_scorer(grounding)
    return MetricResult(
        metric_id=metric_id,
        status=MetricStatus.OBSERVED,
        value=value,
        numerator=value,
        denominator=1,
        scorer_id=scorer_id,
        scorer_version=scorer_version,
        scorer_digest=scorer_digest,
        evaluator_mode=GROUNDING_MODE if grounding else None,
    )


def answer_unavailable(
    metric_id: str, reason: str, *, grounding: bool = False
) -> MetricResult:
    scorer_id, scorer_version, scorer_digest = _answer_scorer(grounding)
    return MetricResult(
        metric_id=metric_id,
        status=MetricStatus.UNAVAILABLE,
        scorer_id=scorer_id,
        scorer_version=scorer_version,
        scorer_digest=scorer_digest,
        evaluator_mode=GROUNDING_MODE if grounding else None,
        reason=reason,
    )


def answer_needs_review(
    metric_id: str, reason: str, *, grounding: bool = False
) -> MetricResult:
    scorer_id, scorer_version, scorer_digest = _answer_scorer(grounding)
    return MetricResult(
        metric_id=metric_id,
        status=MetricStatus.NEEDS_REVIEW,
        scorer_id=scorer_id,
        scorer_version=scorer_version,
        scorer_digest=scorer_digest,
        evaluator_mode=GROUNDING_MODE if grounding else None,
        reason=reason,
    )


def answer_not_applicable(
    metric_id: str, *, grounding: bool = False
) -> MetricResult:
    scorer_id, scorer_version, scorer_digest = _answer_scorer(grounding)
    return MetricResult(
        metric_id=metric_id,
        status=MetricStatus.NOT_APPLICABLE,
        scorer_id=scorer_id,
        scorer_version=scorer_version,
        scorer_digest=scorer_digest,
        evaluator_mode=GROUNDING_MODE if grounding else None,
        reason="answer generation is disabled for this experiment",
    )


def _answer_scorer(grounding: bool) -> tuple[str, str, str]:
    if grounding:
        return GROUNDING_SCORER_ID, GROUNDING_SCORER_VERSION, GROUNDING_SCORER_DIGEST
    return ANSWER_SCORER_ID, ANSWER_SCORER_VERSION, ANSWER_SCORER_DIGEST
