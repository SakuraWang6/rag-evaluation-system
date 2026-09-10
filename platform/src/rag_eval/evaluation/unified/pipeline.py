"""Proof-gated canonical set differences across observed stages."""

from __future__ import annotations

from typing import Literal

from rag_eval.contracts.benchmark import BenchmarkGoldV2
from rag_eval.contracts.observation import (
    StageName,
    StageTransitionMode,
    UnifiedTrace,
)
from rag_eval.evaluation.unified.models import (
    EvaluationMetricStatus,
    EvaluationProfile,
    ObjectExtentDelta,
    PipelineDelta,
)
from rag_eval.evaluation.unified.proofs import (
    StageProof,
    canonical_object_id,
    required_object_ids,
)


def pipeline_delta(
    gold: BenchmarkGoldV2,
    trace: UnifiedTrace,
    *,
    source: StageProof,
    target: StageProof,
    source_stage: StageName,
    target_stage: StageName,
    transition: Literal["candidate_to_ranked", "ranked_to_context"],
    profile: EvaluationProfile,
) -> PipelineDelta:
    reason = _transition_unavailability(
        trace,
        source=source,
        target=target,
        source_stage=source_stage,
        target_stage=target_stage,
    )
    object_ids = required_object_ids(gold)
    evidence_by_object: dict[str, list[str]] = {}
    for evidence in gold.evidence:
        object_id = canonical_object_id(evidence)
        if object_id in object_ids:
            evidence_by_object.setdefault(object_id, []).append(evidence.evidence_id)
    if reason is None:
        for object_id, evidence_ids in evidence_by_object.items():
            source_values = [source.evidence[item] for item in evidence_ids]
            target_values = [target.evidence[item] for item in evidence_ids]
            if not all(
                item.exact and item.coverage is not None
                for item in (*source_values, *target_values)
            ):
                reason = f"canonical extent for {object_id} is not exactly observable"
                break
    if reason is not None:
        return PipelineDelta(
            transition=transition,
            status=EvaluationMetricStatus.UNAVAILABLE,
            candidate_cutoff=profile.candidate_cutoff,
            ranked_cutoff=profile.ranked_mrr_cutoff,
            context_budget=profile.context_budget,
            reason=reason,
        )

    deltas: list[ObjectExtentDelta] = []
    for object_id, evidence_ids in sorted(evidence_by_object.items()):
        source_value = source.evidence[evidence_ids[0]]
        target_value = target.evidence[evidence_ids[0]]
        assert source_value.coverage is not None and target_value.coverage is not None
        deltas.append(
            ObjectExtentDelta(
                canonical_object_id=object_id,
                lost_fraction=source_value.coverage.difference_fraction(
                    target_value.coverage
                ),
                gained_fraction=target_value.coverage.difference_fraction(
                    source_value.coverage
                ),
            )
        )
    denominator = len(deltas)
    return PipelineDelta(
        transition=transition,
        status=EvaluationMetricStatus.OBSERVED,
        loss_fraction=(
            sum(item.lost_fraction for item in deltas) / denominator
            if denominator
            else 0
        ),
        gain_fraction=(
            sum(item.gained_fraction for item in deltas) / denominator
            if denominator
            else 0
        ),
        object_deltas=tuple(deltas),
        candidate_cutoff=profile.candidate_cutoff,
        ranked_cutoff=profile.ranked_mrr_cutoff,
        context_budget=profile.context_budget,
    )


def _transition_unavailability(
    trace: UnifiedTrace,
    *,
    source: StageProof,
    target: StageProof,
    source_stage: StageName,
    target_stage: StageName,
) -> str | None:
    declaration = trace.observation_profile.capabilities.transition(
        source_stage, target_stage
    )
    if declaration.mode == StageTransitionMode.UNOBSERVABLE:
        return "stage transformation lineage is unobservable"
    source_ids = {item.native_chunk_id for item in source.items}
    target_ids = {item.native_chunk_id for item in target.items}
    if declaration.mode == StageTransitionMode.IDENTITY_SUBSET:
        if not target_ids.issubset(source_ids):
            return "target evaluation window is not a proved source identity subset"
        return None
    records = {
        (item.source_stage, item.target_stage, item.output_native_chunk_id): item
        for item in trace.transformations
    }
    for item in target.items:
        record = records.get((source_stage, target_stage, item.native_chunk_id))
        if record is None:
            return "derived target item has no verified transformation receipt"
        if any(
            reference.native_chunk_id not in source_ids
            for reference in record.source_item_references
        ):
            return "transformation source falls outside the proved source window"
    return None
