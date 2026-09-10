"""Proof-driven stage attribution independent of any runtime implementation."""

from __future__ import annotations

from rag_eval.contracts.benchmark import BenchmarkAnswerV2, BenchmarkGoldV2
from rag_eval.contracts.observation import (
    ObservationCompleteness,
    ObservationStatus,
    UnifiedTrace,
)
from rag_eval.evaluation.answers import AnswerVerdict, score_answer
from rag_eval.evaluation.unified.models import (
    EvaluationMetricStatus,
    EvaluationProfile,
    FailureKind,
    PipelineDelta,
    ProofGatedFailure,
    StageLocalization,
)
from rag_eval.evaluation.unified.proofs import (
    EPSILON,
    StageProof,
    required_object_ids,
    same,
)


def failure_attribution(
    *,
    gold: BenchmarkGoldV2,
    trace: UnifiedTrace,
    profile: EvaluationProfile,
    ingestion: StageProof,
    candidate: StageProof,
    ranked: StageProof,
    context: StageProof,
    ranking_delta: PipelineDelta,
    context_delta: PipelineDelta,
    gold_answer: BenchmarkAnswerV2 | None,
) -> ProofGatedFailure | None:
    proofs = tuple(sorted(required_object_ids(gold)))
    if not same(
        ingestion.public.complete_recall_lower,
        ingestion.public.complete_recall_upper,
    ):
        return _unobservable("ingestion coverage cannot be proved", proofs)
    if ingestion.public.complete_recall_lower < 1 - EPSILON:
        return ProofGatedFailure(
            kind=FailureKind.PARSER_INDEX_LOSS,
            reason="complete ingestion catalog proves no complete Gold path",
            proof_subjects=proofs,
        )
    if not _exact_complete_recall(candidate.public):
        if _bounds_unknown(candidate.public):
            return _unobservable("candidate coverage cannot be proved", proofs)
        return ProofGatedFailure(
            kind=FailureKind.RETRIEVAL_LOSS,
            cutoff=profile.candidate_cutoff,
            reason="index contains a complete Gold path but candidate prefix does not",
            proof_subjects=proofs,
        )
    if not _exact_complete_recall(ranked.public):
        if (
            _bounds_unknown(ranked.public)
            or ranking_delta.status != EvaluationMetricStatus.OBSERVED
        ):
            return _unobservable("ranking loss cannot be proved", proofs)
        return ProofGatedFailure(
            kind=FailureKind.RANKING_LOSS,
            cutoff=profile.ranked_mrr_cutoff,
            reason="candidate covers Gold but ranked prefix loses canonical extent",
            proof_subjects=proofs,
        )
    if not _exact_complete_recall(context.public):
        if (
            _bounds_unknown(context.public)
            or context_delta.status != EvaluationMetricStatus.OBSERVED
        ):
            return _unobservable("context loss cannot be proved", proofs)
        return ProofGatedFailure(
            kind=FailureKind.CONTEXT_LOSS,
            reason="ranked prefix covers Gold but final context loses canonical extent",
            proof_subjects=proofs,
        )
    if gold_answer is None:
        return None
    if (
        trace.answer.observation_status != ObservationStatus.OBSERVED
        or trace.answer.completeness != ObservationCompleteness.COMPLETE
    ):
        return _unobservable("answer is not completely observed", proofs)
    answer = score_answer(trace.answer.content, gold_answer)
    if answer.verdict == AnswerVerdict.FAIL:
        return ProofGatedFailure(
            kind=FailureKind.GENERATION_FAILURE,
            reason=(
                "final context completely covers Gold but deterministic "
                "answer scoring failed"
            ),
            proof_subjects=proofs,
        )
    if answer.verdict == AnswerVerdict.NEEDS_REVIEW:
        return _unobservable(answer.reason, proofs)
    return None


def _exact_complete_recall(value: StageLocalization) -> bool:
    return (
        same(value.complete_recall_lower, value.complete_recall_upper)
        and value.complete_recall_lower >= 1 - EPSILON
    )


def _bounds_unknown(value: StageLocalization) -> bool:
    return not same(value.complete_recall_lower, value.complete_recall_upper)


def _unobservable(reason: str, proofs: tuple[str, ...]) -> ProofGatedFailure:
    return ProofGatedFailure(
        kind=FailureKind.UNOBSERVABLE,
        reason=reason,
        proof_subjects=proofs,
    )
