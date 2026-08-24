"""Deterministic, multi-label failure assessment for completed and failed cases."""

from __future__ import annotations

from rag_eval.contracts.adapter import RAGResult
from rag_eval.contracts.dataset import GoldEvidenceSet
from rag_eval.contracts.research import FailureAssessment, FailureLabel
from rag_eval.contracts.run import MetricResult, MetricStatus
from rag_eval.evaluation.evidence import CorpusEvidenceIndex, match_all


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
        raw_matches = match_all(result.raw_retrieval, evidence_set.evidence, corpus)
        if not _complete(raw_matches, evidence_set):
            labels.append(FailureLabel.RETRIEVAL_MISSING)
            reasons.append("a required evidence group is absent from raw retrieval")

    if result.raw_retrieval is not None and result.ranked_retrieval is not None:
        raw_matches = match_all(result.raw_retrieval, evidence_set.evidence, corpus)
        ranked_matches = match_all(result.ranked_retrieval, evidence_set.evidence, corpus)
        if _complete(raw_matches, evidence_set) and not _complete(ranked_matches, evidence_set):
            labels.append(FailureLabel.RANKING_FAILURE)
            reasons.append("raw evidence was present but ranked retrieval lost a required group")
    elif result.ranked_retrieval is None:
        review_required = True
        reasons.append("ranked retrieval is not observable")

    if result.ranked_retrieval is not None and result.final_context is not None:
        ranked_matches = match_all(result.ranked_retrieval, evidence_set.evidence, corpus)
        context_matches = match_all(result.final_context, evidence_set.evidence, corpus)
        if _complete(ranked_matches, evidence_set) and not _complete(context_matches, evidence_set):
            labels.append(FailureLabel.CONTEXT_SELECTION_LOSS)
            reasons.append("ranked evidence was present but final context lost a required group")
    elif result.final_context is None:
        review_required = True
        reasons.append("final context is not observable")

    by_id = {metric.metric_id: metric for metric in metrics}
    accuracy = by_id.get("answer_accuracy")
    context_complete = result.final_context is not None and _complete(
        match_all(result.final_context, evidence_set.evidence, corpus), evidence_set
    )
    if context_complete and accuracy is not None and accuracy.status == MetricStatus.OBSERVED and accuracy.value == 0:
        labels.append(FailureLabel.GENERATION_FAILURE)
        reasons.append("final context covered Gold Evidence but answer scorer failed")
    grounded = by_id.get("answer_groundedness")
    if grounded is not None and grounded.status == MetricStatus.OBSERVED and grounded.value == 0:
        labels.append(FailureLabel.UNSUPPORTED_ANSWER)
        reasons.append("completed answer is not deterministically grounded")
    if review_required:
        labels.append(FailureLabel.NEEDS_REVIEW)
    return FailureAssessment(
        labels=list(dict.fromkeys(labels)),
        certainty="deterministic" if not review_required else "unknown",
        reasons=list(dict.fromkeys(reasons)),
        review_required=review_required,
    )


def _complete(matches: set[str], evidence_set: GoldEvidenceSet) -> bool:
    return all(any(evidence_id in matches for evidence_id in group) for group in evidence_set.required_groups)
