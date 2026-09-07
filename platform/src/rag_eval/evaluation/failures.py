"""Deterministic, multi-label failure assessment for completed and failed cases."""

from __future__ import annotations

from rag_eval.contracts.adapter import RAGResult
from rag_eval.contracts.dataset import GoldEvidenceSet
from rag_eval.contracts.research import FailureAssessment, FailureLabel
from rag_eval.contracts.run import MetricResult, MetricStatus
from rag_eval.evaluation.evidence import (
    CorpusEvidenceIndex,
    StageLocalization,
    evidence_observability,
    localize_stage,
)


def assess_failure(
    *,
    status: str,
    result: RAGResult | None,
    evidence_set: GoldEvidenceSet,
    corpus: CorpusEvidenceIndex,
    metrics: list[MetricResult],
) -> FailureAssessment:
    if status == "timeout":
        return FailureAssessment(
            labels=[FailureLabel.TIMEOUT],
            certainty="deterministic",
            reasons=["adapter query timed out"],
        )
    if status == "system_error":
        return FailureAssessment(
            labels=[FailureLabel.ADAPTER_ERROR],
            certainty="deterministic",
            reasons=["adapter query returned a system error"],
        )
    if status != "completed" or result is None:
        return FailureAssessment(
            labels=[FailureLabel.NEEDS_REVIEW],
            certainty="unknown",
            reasons=[f"case status is {status}"],
            review_required=True,
        )

    labels: list[FailureLabel] = []
    reasons: list[str] = []
    review_required = any(metric.status == MetricStatus.NEEDS_REVIEW for metric in metrics)
    if result.raw_retrieval is None:
        review_required = True
        reasons.append("raw retrieval is not observable")
    else:
        raw_localization = localize_stage(
            result.raw_retrieval, evidence_set, corpus, stage="raw"
        )
        raw_observability = evidence_observability(
            result.raw_retrieval, evidence_set, corpus
        )
        if raw_observability is not None:
            labels.append(FailureLabel.PROVENANCE_UNAVAILABLE)
            reasons.append(raw_observability)
            review_required = True
        elif not raw_localization.complete_path(evidence_set):
            labels.append(FailureLabel.RETRIEVAL_MISSING)
            reasons.append("a required evidence group is absent from raw retrieval")

    if result.raw_retrieval is not None and result.ranked_retrieval is not None:
        raw_localization = localize_stage(
            result.raw_retrieval, evidence_set, corpus, stage="raw"
        )
        ranked_localization = localize_stage(
            result.ranked_retrieval, evidence_set, corpus, stage="ranked"
        )
        ranked_observability = evidence_observability(
            result.ranked_retrieval, evidence_set, corpus
        )
        if ranked_observability is not None:
            labels.append(FailureLabel.PROVENANCE_UNAVAILABLE)
            reasons.append(ranked_observability)
            review_required = True
        elif raw_localization.complete_path(evidence_set) and not ranked_localization.complete_path(evidence_set):
            labels.append(FailureLabel.RANKING_FAILURE)
            reasons.append("raw evidence was present but ranked retrieval lost a required group")
    elif result.ranked_retrieval is None:
        review_required = True
        reasons.append("ranked retrieval is not observable")

    if result.ranked_retrieval is not None and result.final_context is not None:
        ranked_localization = localize_stage(
            result.ranked_retrieval, evidence_set, corpus, stage="ranked"
        )
        context_localization = localize_stage(
            result.final_context, evidence_set, corpus, stage="context"
        )
        context_observability = evidence_observability(
            result.final_context, evidence_set, corpus
        )
        if context_observability is not None:
            labels.append(FailureLabel.PROVENANCE_UNAVAILABLE)
            reasons.append(context_observability)
            review_required = True
        elif ranked_localization.complete_path(evidence_set) and not context_localization.complete_path(evidence_set):
            labels.append(FailureLabel.CONTEXT_SELECTION_LOSS)
            reasons.append("ranked evidence was present but final context lost a required group")
    elif result.final_context is None:
        review_required = True
        reasons.append("final context is not observable")

    by_id = {metric.metric_id: metric for metric in metrics}
    accuracy = by_id.get("answer_accuracy")
    context_localization = (
        localize_stage(result.final_context, evidence_set, corpus, stage="context")
        if result.final_context is not None
        else None
    )
    context_complete = bool(
        context_localization is not None
        and context_localization.complete_path(evidence_set)
    )
    if context_complete and accuracy is not None and accuracy.status == MetricStatus.OBSERVED and accuracy.value == 0:
        labels.append(FailureLabel.GENERATION_FAILURE)
        reasons.append("final context covered Gold Evidence but answer scorer failed")
    # ``answer_groundedness=0`` is the strict Gold-localization result.  It is
    # not proof that the answer lacks semantic support (a duplicate source
    # position may contain the same fact), so do not label it unsupported until
    # a semantic adjudicator supplies that evidence.
    # An actually empty, observable context is retained as the historical
    # deterministic unsupported-answer signal for compatibility.  A non-empty
    # context with a strict Gold miss never takes this branch: its semantic
    # support remains unknown and is represented by needs-review instead.
    if (
        result.final_context == []
        and groundedness_zero(by_id)
    ):
        labels.append(FailureLabel.UNSUPPORTED_ANSWER)
        reasons.append("final context was empty; no returned evidence can support the answer")
    if review_required:
        labels.append(FailureLabel.NEEDS_REVIEW)
    return FailureAssessment(
        labels=list(dict.fromkeys(labels)),
        certainty="deterministic" if not review_required else "unknown",
        reasons=list(dict.fromkeys(reasons)),
        review_required=review_required,
    )


def _complete(
    matches: set[str] | StageLocalization, evidence_set: GoldEvidenceSet
) -> bool:
    """Compatibility helper for callers that still pass a match-ID set."""

    if isinstance(matches, StageLocalization):
        return matches.complete_path(evidence_set)
    return any(
        all(any(evidence_id in matches for evidence_id in group) for group in path)
        for path in (evidence_set.mses_paths or [evidence_set.required_groups])
    )


def groundedness_zero(by_id: dict[str, MetricResult]) -> bool:
    metric = by_id.get("answer_groundedness")
    return (
        metric is not None
        and metric.status == MetricStatus.OBSERVED
        and metric.value == 0
    )
