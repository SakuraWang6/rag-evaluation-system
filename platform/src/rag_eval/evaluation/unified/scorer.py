"""Unified Evaluation v2 orchestration over generic proof components."""

from __future__ import annotations

import hashlib
from pathlib import Path

from rag_eval.contracts.dataset import GoldAnswer, GoldEvidenceSet
from rag_eval.contracts.observation import StageName, UnifiedTrace
from rag_eval.evaluation.unified.failures import failure_attribution
from rag_eval.evaluation.unified.models import (
    UNIFIED_SCORER_ID,
    UNIFIED_SCORER_VERSION,
    EvaluationMetric,
    EvaluationMetricStatus,
    EvaluationProfile,
    MetricDescriptor,
    PipelineDelta,
    UnifiedEvaluationResult,
)
from rag_eval.evaluation.unified.pipeline import pipeline_delta
from rag_eval.evaluation.unified.proofs import ingestion_proof, same, stage_proof
from rag_eval.evaluation.unified.ranking import (
    complete_mrr_bounds,
    first_fragment_mrr_bounds,
)


def scorer_source_digest() -> str:
    digest = hashlib.sha256()
    root = Path(__file__).parent
    for path in sorted(root.glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def evaluate_unified_trace(
    gold: GoldEvidenceSet,
    trace: UnifiedTrace,
    *,
    profile: EvaluationProfile,
    gold_answer: GoldAnswer | None = None,
) -> UnifiedEvaluationResult:
    """Score one validated Wire 2.0 trace without runtime-specific semantics."""

    digest = scorer_source_digest()
    ranked = {
        cutoff: stage_proof(
            gold, trace, trace.ranked_retrieval, cutoff=cutoff
        )
        for cutoff in profile.ranked_cutoffs
    }
    ranked_prefixes = {
        rank: stage_proof(gold, trace, trace.ranked_retrieval, cutoff=rank)
        for rank in range(1, profile.ranked_mrr_cutoff + 1)
    }
    candidate = stage_proof(
        gold, trace, trace.raw_retrieval, cutoff=profile.candidate_cutoff
    )
    context = stage_proof(gold, trace, trace.final_context, cutoff=None)
    ingestion = ingestion_proof(gold, trace)

    metrics: list[EvaluationMetric] = []
    for cutoff in profile.ranked_cutoffs:
        proof = ranked[cutoff]
        metrics.extend(
            (
                _metric_from_bounds(
                    f"ranked_evidence_coverage@{cutoff}",
                    proof.public.coverage_lower,
                    proof.public.coverage_upper,
                    profile=profile,
                    scorer_digest=digest,
                    stage=StageName.RANKED,
                    cutoff=cutoff,
                    reason=proof.public.reason,
                ),
                _metric_from_bounds(
                    f"ranked_complete_evidence_recall@{cutoff}",
                    proof.public.complete_recall_lower,
                    proof.public.complete_recall_upper,
                    profile=profile,
                    scorer_digest=digest,
                    stage=StageName.RANKED,
                    cutoff=cutoff,
                    reason=proof.public.reason,
                ),
            )
        )

    boundary_proved = trace.ranked_retrieval.proves_prefix(
        profile.ranked_mrr_cutoff
    )
    if boundary_proved:
        mrr_lower, mrr_upper, mrr_reason = complete_mrr_bounds(
            ranked_prefixes, profile.ranked_mrr_cutoff
        )
        fragment_lower, fragment_upper, fragment_reason = (
            first_fragment_mrr_bounds(
                gold, ranked_prefixes, profile.ranked_mrr_cutoff
            )
        )
    else:
        boundary_reason = (
            f"ranked does not prove ordered Top-{profile.ranked_mrr_cutoff}"
        )
        mrr_lower, mrr_upper, mrr_reason = 0.0, 1.0, boundary_reason
        fragment_lower, fragment_upper, fragment_reason = (
            0.0,
            1.0,
            boundary_reason,
        )
    metrics.extend(
        (
            _metric_from_bounds(
                f"ranked_complete_evidence_mrr@{profile.ranked_mrr_cutoff}",
                mrr_lower,
                mrr_upper,
                profile=profile,
                scorer_digest=digest,
                stage=StageName.RANKED,
                cutoff=profile.ranked_mrr_cutoff,
                reason=mrr_reason,
            ),
            _metric_from_bounds(
                f"ranked_first_fragment_mrr@{profile.ranked_mrr_cutoff}",
                fragment_lower,
                fragment_upper,
                profile=profile,
                scorer_digest=digest,
                stage=StageName.RANKED,
                cutoff=profile.ranked_mrr_cutoff,
                reason=fragment_reason,
            ),
            _metric_from_bounds(
                f"candidate_evidence_coverage@{profile.candidate_cutoff}",
                candidate.public.coverage_lower,
                candidate.public.coverage_upper,
                profile=profile,
                scorer_digest=digest,
                stage=StageName.CANDIDATE,
                cutoff=profile.candidate_cutoff,
                reason=candidate.public.reason,
            ),
        )
    )

    ranked_window = ranked[profile.ranked_mrr_cutoff]
    ranking_delta = pipeline_delta(
        gold,
        trace,
        source=candidate,
        target=ranked_window,
        source_stage=StageName.CANDIDATE,
        target_stage=StageName.RANKED,
        transition="candidate_to_ranked",
        profile=profile,
    )
    context_delta = pipeline_delta(
        gold,
        trace,
        source=ranked_window,
        target=context,
        source_stage=StageName.RANKED,
        target_stage=StageName.CONTEXT,
        transition="ranked_to_context",
        profile=profile,
    )
    metrics.extend(
        (
            _delta_metric("ranking_loss", ranking_delta, "loss", profile, digest),
            _delta_metric("context_loss", context_delta, "loss", profile, digest),
            _delta_metric(
                "candidate_to_ranked_stage_gain",
                ranking_delta,
                "gain",
                profile,
                digest,
            ),
            _delta_metric(
                "ranked_to_context_stage_gain",
                context_delta,
                "gain",
                profile,
                digest,
            ),
        )
    )

    failure = failure_attribution(
        gold=gold,
        trace=trace,
        profile=profile,
        ingestion=ingestion,
        candidate=candidate,
        ranked=ranked_window,
        context=context,
        ranking_delta=ranking_delta,
        context_delta=context_delta,
        gold_answer=gold_answer,
    )
    return UnifiedEvaluationResult(
        scorer_id=UNIFIED_SCORER_ID,
        scorer_version=UNIFIED_SCORER_VERSION,
        scorer_digest=digest,
        gold_evidence_set_id=gold.gold_evidence_set_id,
        trace_digest=trace.trace_digest,
        metrics=tuple(metrics),
        localizations=(
            ingestion.public,
            candidate.public,
            *(ranked[cutoff].public for cutoff in profile.ranked_cutoffs),
            context.public,
        ),
        pipeline_deltas=(ranking_delta, context_delta),
        failure=failure,
    )


def _metric_from_bounds(
    metric_id: str,
    lower: float,
    upper: float,
    *,
    profile: EvaluationProfile,
    scorer_digest: str,
    stage: StageName,
    cutoff: int,
    reason: str | None,
) -> EvaluationMetric:
    exact = same(lower, upper)
    descriptor = MetricDescriptor(
        metric_id=metric_id,
        scorer_digest=scorer_digest,
        aggregation="mses_clause_equal_weight",
        stage=stage,
        cutoff=cutoff,
        candidate_cutoff=profile.candidate_cutoff,
        ranked_cutoff=(
            cutoff
            if stage == StageName.RANKED
            else profile.ranked_mrr_cutoff
        ),
        context_budget=profile.context_budget,
    )
    return EvaluationMetric(
        metric_id=metric_id,
        status=(
            EvaluationMetricStatus.OBSERVED
            if exact
            else EvaluationMetricStatus.UNAVAILABLE
        ),
        value=lower if exact else None,
        lower_bound=lower,
        upper_bound=upper,
        descriptor=descriptor,
        reason=None if exact else (reason or "metric value is not provable"),
    )


def _delta_metric(
    metric_id: str,
    delta: PipelineDelta,
    field: str,
    profile: EvaluationProfile,
    scorer_digest: str,
) -> EvaluationMetric:
    value = delta.loss_fraction if field == "loss" else delta.gain_fraction
    observed = delta.status == EvaluationMetricStatus.OBSERVED and value is not None
    return EvaluationMetric(
        metric_id=metric_id,
        status=(
            EvaluationMetricStatus.OBSERVED
            if observed
            else EvaluationMetricStatus.UNAVAILABLE
        ),
        value=value if observed else None,
        lower_bound=value if observed and value is not None else 0,
        upper_bound=value if observed and value is not None else 1,
        descriptor=MetricDescriptor(
            metric_id=metric_id,
            scorer_digest=scorer_digest,
            aggregation="canonical_extent_union",
            candidate_cutoff=profile.candidate_cutoff,
            ranked_cutoff=profile.ranked_mrr_cutoff,
            context_budget=profile.context_budget,
        ),
        reason=None if observed else delta.reason,
    )
