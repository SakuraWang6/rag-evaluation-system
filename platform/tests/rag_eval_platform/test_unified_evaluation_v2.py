from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_eval.contracts.canonical import SourceSpan
from rag_eval.contracts.dataset import (
    GoldAnswer,
    GoldAnswerKind,
    GoldEvidence,
    GoldEvidenceSet,
    GoldSourceIdentity,
    ObjectLocator,
    TableCellLocator,
)
from rag_eval.contracts.observation import (
    AdapterCapabilitiesV2,
    CanonicalExtent,
    CanonicalMappingRecord,
    ContentObservation,
    ExtentUnit,
    IngestionCatalogObservation,
    LineageIntegrityStatus,
    MappingDiagnostic,
    MappingDiagnosticStatus,
    ObservationCompleteness,
    ObservationProfileIdentity,
    ObservationStatus,
    ObservedStageItem,
    PhysicalCellFootprint,
    ProvenanceCoverageStatus,
    ProvenanceEdge,
    ReverseMappingStatus,
    RuntimeChunkRecord,
    RuntimeProfileIdentity,
    SourceIdentity,
    StageItemReference,
    StageName,
    StageObservation,
    StageTransitionDeclaration,
    StageTransitionMode,
    TransformationRecord,
    UnifiedTrace,
)
from rag_eval.contracts.run import MetricResult, MetricStatus
from rag_eval.evaluation.unified import (
    EvaluationMetricStatus,
    EvaluationProfile,
    FailureKind,
    ShadowDifferenceKind,
    compare_legacy_shadow,
    evaluate_unified_trace,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _gold(
    *clauses: tuple[str, ...],
    evidence_to_object: dict[str, str] | None = None,
) -> GoldEvidenceSet:
    mapping = evidence_to_object or {
        evidence_id: evidence_id for clause in clauses for evidence_id in clause
    }
    evidence = [
        GoldEvidence(
            evidence_id=evidence_id,
            document_id="doc-1",
            locator=ObjectLocator(
                object_type="paragraph", object_id=canonical_object_id
            ),
            canonical_object_id=canonical_object_id,
            canonical_value=evidence_id,
        )
        for evidence_id, canonical_object_id in mapping.items()
    ]
    return GoldEvidenceSet(
        gold_evidence_set_id="gold-1",
        evidence=evidence,
        required_groups=[list(clause) for clause in clauses],
        source_identities=(
            GoldSourceIdentity(
                document_id="doc-1",
                source_sha256=SHA_A,
                source_coordinate_schema="ooxml-structural-v1",
                canonical_catalog_sha256=SHA_B,
            ),
        ),
        mses_paths=[[list(clause) for clause in clauses]],
    )


def _text_extent(
    object_id: str, start: int = 0, end: int = 10
) -> CanonicalExtent:
    return CanonicalExtent.build(
        extent_kind="canonical_object",
        units=(
            ExtentUnit(
                unit_id=object_id,
                coordinate_system="canonical-text-offset-v1",
                start=start,
                end=end,
                coordinates={"part": "word/document.xml"},
            ),
        ),
    )


def _cell_extent(*cell_ids: str) -> CanonicalExtent:
    return CanonicalExtent.build(
        extent_kind="physical_cell_union",
        units=tuple(
            ExtentUnit(
                unit_id=cell_id,
                coordinate_system="ooxml-physical-cell-v1",
                coordinates={"table_id": "table-1"},
            )
            for cell_id in cell_ids
        ),
    )


def _covered_text(
    object_id: str, start: int, end: int
) -> CanonicalExtent:
    return _text_extent(object_id, start, end)


def _chunk(chunk_id: str) -> RuntimeChunkRecord:
    content = f"content:{chunk_id}"
    return RuntimeChunkRecord(
        native_document_id="runtime-doc-1",
        native_chunk_id=chunk_id,
        content_sha256=_sha(content),
        content=content,
        parser_identity="parser/1",
        chunker_identity="chunker/1",
        persisted_metadata_digest=SHA_A,
    )


def _edge(
    chunk: RuntimeChunkRecord,
    object_id: str,
    expected: CanonicalExtent,
    covered: CanonicalExtent,
    *,
    footprint: tuple[PhysicalCellFootprint, ...] = (),
) -> ProvenanceEdge:
    return ProvenanceEdge.build(
        native_chunk_id=chunk.native_chunk_id,
        canonical_object_id=object_id,
        canonical_locator=SourceSpan(
            part="word/document.xml",
            coordinates={"object_id": object_id},
        ),
        mapping_tier="deterministic_crosswalk",
        coverage_status=(
            ProvenanceCoverageStatus.COMPLETE
            if expected.extent_digest == covered.extent_digest
            else ProvenanceCoverageStatus.PARTIAL
        ),
        expected_extent=expected,
        covered_extent=covered,
        physical_cell_footprint=footprint,
        source_sha256=SHA_A,
        native_content_sha256=chunk.content_sha256,
        canonical_value_sha256=_sha(object_id),
        reason_code="verified_fixture_crosswalk",
    )


def _item(
    chunk: RuntimeChunkRecord,
    rank: int,
    edges: tuple[ProvenanceEdge, ...],
) -> ObservedStageItem:
    return ObservedStageItem(
        native_chunk_id=chunk.native_chunk_id,
        native_rank=rank,
        content_sha256=chunk.content_sha256,
        content=chunk.content,
        provenance_edge_ids=tuple(edge.edge_id for edge in edges),
    )


def _stage(
    name: StageName,
    items: tuple[ObservedStageItem, ...],
    *,
    completeness: ObservationCompleteness = ObservationCompleteness.COMPLETE,
    configured_cutoff: int | None = None,
) -> StageObservation:
    return StageObservation(
        stage=name,
        observation_status=ObservationStatus.OBSERVED,
        completeness=completeness,
        configured_cutoff=configured_cutoff,
        proven_prefix_depth=(
            len(items)
            if completeness == ObservationCompleteness.TRUNCATED
            else None
        ),
        items=items,
    )


def _trace(
    *,
    chunks: tuple[RuntimeChunkRecord, ...],
    edges: tuple[ProvenanceEdge, ...],
    mapping_statuses: dict[str, ReverseMappingStatus],
    candidate: tuple[ObservedStageItem, ...],
    ranked: tuple[ObservedStageItem, ...],
    context: tuple[ObservedStageItem, ...],
    ranked_completeness: ObservationCompleteness = ObservationCompleteness.COMPLETE,
    mapping_diagnostics: tuple[MappingDiagnostic, ...] = (),
    candidate_to_ranked: StageTransitionMode = StageTransitionMode.IDENTITY_SUBSET,
    ranked_to_context: StageTransitionMode = StageTransitionMode.IDENTITY_SUBSET,
    answer: str = "correct",
    transformations: tuple[TransformationRecord, ...] = (),
    expected_extents: dict[str, CanonicalExtent] | None = None,
) -> UnifiedTrace:
    capabilities = AdapterCapabilitiesV2(
        ingestion_catalog=True,
        candidate_retrieval=True,
        ranked_retrieval=True,
        final_context=True,
        prompt_trace=True,
        answer=True,
        provenance=True,
        transformation_lineage=any(
            mode == StageTransitionMode.VERIFIED_DERIVATION
            for mode in (candidate_to_ranked, ranked_to_context)
        ),
        transitions=(
            StageTransitionDeclaration(
                source_stage=StageName.CANDIDATE,
                target_stage=StageName.RANKED,
                mode=candidate_to_ranked,
            ),
            StageTransitionDeclaration(
                source_stage=StageName.RANKED,
                target_stage=StageName.CONTEXT,
                mode=ranked_to_context,
            ),
        ),
    )
    edge_by_object: dict[str, list[ProvenanceEdge]] = {}
    for edge in edges:
        edge_by_object.setdefault(edge.canonical_object_id, []).append(edge)
    expected_extents = expected_extents or {}
    records = []
    for object_id, mapping_status in sorted(mapping_statuses.items()):
        object_edges = edge_by_object.get(object_id, [])
        if object_edges:
            expected = object_edges[0].expected_extent
            native_ids = tuple(
                sorted({edge.native_chunk_id for edge in object_edges})
            )
        else:
            expected = expected_extents[object_id]
            native_ids = ()
        records.append(
            CanonicalMappingRecord.build(
                canonical_object_id=object_id,
                expected_extent=expected,
                reverse_mapping_status=mapping_status,
                native_chunk_ids=native_ids,
            )
        )
    return UnifiedTrace.build(
        case_id="case-1",
        source_identity=SourceIdentity(
            document_id="doc-1",
            source_sha256=SHA_A,
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            source_coordinate_schema="ooxml-structural-v1",
            canonical_catalog_sha256=SHA_B,
        ),
        runtime_profile=RuntimeProfileIdentity(
            profile_id="runtime-profile",
            system_id="system-under-test",
            system_version="1",
            configuration_digest=SHA_C,
        ),
        observation_profile=ObservationProfileIdentity.build(
            profile_id="observation-profile",
            adapter_id="adapter-under-test",
            adapter_version="1",
            capabilities=capabilities,
        ),
        ingestion_catalog=IngestionCatalogObservation(
            observation_status=ObservationStatus.OBSERVED,
            completeness=ObservationCompleteness.COMPLETE,
            items=chunks,
        ),
        provenance_edges=edges,
        canonical_mapping_records=tuple(records),
        mapping_diagnostics=mapping_diagnostics,
        raw_retrieval=_stage(StageName.CANDIDATE, candidate),
        ranked_retrieval=_stage(
            StageName.RANKED,
            ranked,
            completeness=ranked_completeness,
            configured_cutoff=(20 if ranked_completeness == "truncated" else None),
        ),
        final_context=_stage(StageName.CONTEXT, context),
        transformations=transformations,
        prompt_trace=ContentObservation.observed("prompt"),
        answer=ContentObservation.observed(answer),
        validation_receipts=(),
    )


def _profile(candidate_cutoff: int = 5) -> EvaluationProfile:
    return EvaluationProfile(
        candidate_cutoff=candidate_cutoff,
        ranked_cutoffs=(1, 3, 5),
        ranked_mrr_cutoff=5,
        context_budget=4096,
    )


def _metric(result: object, metric_id: str):
    return result.metric(metric_id)  # type: ignore[attr-defined]


def test_gold_carries_a_stable_canonical_identity_without_adapter_input() -> None:
    cell = GoldEvidence(
        evidence_id="cell",
        document_id="doc-1",
        locator=TableCellLocator(table_id="table-1", row=2, column=3),
        canonical_object_id="logical-cell-2-3",
        canonical_value="42",
    )

    assert cell.canonical_object_id == "logical-cell-2-3"
    with pytest.raises(ValidationError, match="canonical object identity"):
        GoldEvidence(
            evidence_id="paragraph",
            document_id="doc-1",
            locator=ObjectLocator(object_type="paragraph", object_id="p-1"),
            canonical_object_id="p-2",
            canonical_value="text",
        )


def test_gold_snapshot_identity_must_match_the_trace_before_scoring() -> None:
    chunk = _chunk("gold")
    extent = _text_extent("gold-a")
    edge = _edge(chunk, "gold-a", extent, extent)
    item = _item(chunk, 1, (edge,))
    trace = _trace(
        chunks=(chunk,),
        edges=(edge,),
        mapping_statuses={"gold-a": ReverseMappingStatus.COMPLETE},
        candidate=(item,),
        ranked=(item,),
        context=(item,),
    )
    gold = _gold(("gold-a",)).model_copy(
        update={
            "source_identities": (
                GoldSourceIdentity(
                    document_id="doc-1",
                    source_sha256=SHA_A,
                    source_coordinate_schema="ooxml-structural-v1",
                    canonical_catalog_sha256=SHA_C,
                ),
            )
        }
    )

    result = evaluate_unified_trace(gold, trace, profile=_profile(1))

    metric = _metric(result, "ranked_evidence_coverage@1")
    assert metric.status == EvaluationMetricStatus.UNAVAILABLE
    assert "catalog identity differs" in (metric.reason or "")
    assert result.failure is not None
    assert result.failure.kind == FailureKind.UNOBSERVABLE


def test_legacy_gold_without_snapshot_pin_remains_readable_but_not_v2_scorable() -> None:
    chunk = _chunk("gold")
    extent = _text_extent("gold-a")
    edge = _edge(chunk, "gold-a", extent, extent)
    item = _item(chunk, 1, (edge,))
    trace = _trace(
        chunks=(chunk,),
        edges=(edge,),
        mapping_statuses={"gold-a": ReverseMappingStatus.COMPLETE},
        candidate=(item,),
        ranked=(item,),
        context=(item,),
    )
    legacy_gold = _gold(("gold-a",)).model_copy(update={"source_identities": ()})

    result = evaluate_unified_trace(legacy_gold, trace, profile=_profile(1))

    assert (
        _metric(result, "ranked_complete_evidence_recall@1").status
        == EvaluationMetricStatus.UNAVAILABLE
    )
    assert "no pinned source identity" in (
        _metric(result, "ranked_complete_evidence_recall@1").reason or ""
    )


def test_verified_top_five_computes_all_core_metrics_without_full_ranking() -> None:
    chunks = tuple(_chunk(f"chunk-{rank}") for rank in range(1, 6))
    extent_a = _text_extent("gold-a")
    extent_b = _text_extent("gold-b")
    edge_a = _edge(chunks[1], "gold-a", extent_a, extent_a)
    edge_b = _edge(chunks[3], "gold-b", extent_b, extent_b)
    edges_by_chunk = {
        chunks[1].native_chunk_id: (edge_a,),
        chunks[3].native_chunk_id: (edge_b,),
    }
    items = tuple(
        _item(chunk, rank, edges_by_chunk.get(chunk.native_chunk_id, ()))
        for rank, chunk in enumerate(chunks, start=1)
    )
    trace = _trace(
        chunks=chunks,
        edges=(edge_a, edge_b),
        mapping_statuses={
            "gold-a": ReverseMappingStatus.COMPLETE,
            "gold-b": ReverseMappingStatus.COMPLETE,
        },
        candidate=items,
        ranked=items,
        context=(
            _item(chunks[1], 1, (edge_a,)),
            _item(chunks[3], 2, (edge_b,)),
        ),
        ranked_completeness=ObservationCompleteness.TRUNCATED,
    )

    result = evaluate_unified_trace(
        _gold(("gold-a",), ("gold-b",)),
        trace,
        profile=_profile(),
        gold_answer=GoldAnswer(
            gold_answer_id="answer-1",
            kind=GoldAnswerKind.TEXT,
            canonical="correct",
        ),
    )

    assert _metric(result, "ranked_evidence_coverage@1").value == 0
    assert _metric(result, "ranked_evidence_coverage@3").value == 0.5
    assert _metric(result, "ranked_evidence_coverage@5").value == 1
    assert _metric(result, "ranked_complete_evidence_recall@5").value == 1
    assert _metric(result, "ranked_complete_evidence_mrr@5").value == 0.25
    assert all(
        _metric(result, metric_id).status == EvaluationMetricStatus.OBSERVED
        for metric_id in (
            "ranked_evidence_coverage@1",
            "ranked_evidence_coverage@3",
            "ranked_evidence_coverage@5",
            "ranked_complete_evidence_recall@1",
            "ranked_complete_evidence_recall@3",
            "ranked_complete_evidence_recall@5",
            "ranked_complete_evidence_mrr@5",
        )
    )
    assert _metric(
        result, "ranked_complete_evidence_mrr@5"
    ).descriptor.ranked_cutoff == 5
    assert _metric(
        result, "ranked_complete_evidence_mrr@5"
    ).descriptor.context_budget == 4096
    assert result.core_metrics_available
    assert type(result).model_validate_json(result.model_dump_json()) == result


def test_truncated_top_three_does_not_claim_top_five_or_mrr_at_five() -> None:
    chunks = tuple(_chunk(f"chunk-{rank}") for rank in range(1, 4))
    extent = _text_extent("gold-a")
    edge = _edge(chunks[1], "gold-a", extent, extent)
    items = (
        _item(chunks[0], 1, ()),
        _item(chunks[1], 2, (edge,)),
        _item(chunks[2], 3, ()),
    )
    trace = _trace(
        chunks=chunks,
        edges=(edge,),
        mapping_statuses={"gold-a": ReverseMappingStatus.COMPLETE},
        candidate=items,
        ranked=items,
        context=(_item(chunks[1], 1, (edge,)),),
        ranked_completeness=ObservationCompleteness.TRUNCATED,
    )

    result = evaluate_unified_trace(
        _gold(("gold-a",)), trace, profile=_profile(3)
    )

    assert _metric(result, "ranked_complete_evidence_recall@3").value == 1
    assert (
        _metric(result, "ranked_complete_evidence_recall@5").status
        == EvaluationMetricStatus.UNAVAILABLE
    )
    assert (
        _metric(result, "ranked_complete_evidence_mrr@5").status
        == EvaluationMetricStatus.UNAVAILABLE
    )
    assert not result.core_metrics_available


def test_text_span_union_and_equal_weight_clauses_are_not_chunk_hit_counts() -> None:
    chunks = (_chunk("first-half"), _chunk("second-half"), _chunk("other"))
    expected = _text_extent("gold-a")
    first = _edge(chunks[0], "gold-a", expected, _covered_text("gold-a", 0, 5))
    second = _edge(chunks[1], "gold-a", expected, _covered_text("gold-a", 5, 10))
    other_extent = _text_extent("gold-b")
    other = _edge(chunks[2], "gold-b", other_extent, other_extent)
    items = (
        _item(chunks[0], 1, (first,)),
        _item(chunks[1], 2, (second,)),
        _item(chunks[2], 3, (other,)),
    )
    trace = _trace(
        chunks=chunks,
        edges=(first, second, other),
        mapping_statuses={
            "gold-a": ReverseMappingStatus.COMPLETE,
            "gold-b": ReverseMappingStatus.COMPLETE,
        },
        candidate=items,
        ranked=items,
        context=items,
    )

    result = evaluate_unified_trace(
        _gold(("gold-a",), ("gold-b",)), trace, profile=_profile(3)
    )

    assert _metric(result, "ranked_evidence_coverage@1").value == 0.25
    assert _metric(result, "ranked_complete_evidence_recall@1").value == 0
    assert _metric(result, "ranked_evidence_coverage@3").value == 1
    assert _metric(result, "ranked_complete_evidence_mrr@5").value == pytest.approx(
        1 / 3
    )


def test_logical_table_cell_is_one_atom_proved_by_multiple_physical_cells() -> None:
    chunks = (_chunk("top"), _chunk("bottom"))
    expected = _cell_extent("physical-1", "physical-2")
    top_extent = _cell_extent("physical-1")
    bottom_extent = _cell_extent("physical-2")
    top_footprint = PhysicalCellFootprint(
        physical_cell_id="physical-1",
        table_id="table-1",
        row=1,
        column=1,
        v_merge="restart",
        merge_origin_physical_cell_id="physical-1",
    )
    bottom_footprint = PhysicalCellFootprint(
        physical_cell_id="physical-2",
        table_id="table-1",
        row=2,
        column=1,
        v_merge="continue",
        merge_origin_physical_cell_id="physical-1",
    )
    top = _edge(
        chunks[0], "logical-cell", expected, top_extent, footprint=(top_footprint,)
    )
    bottom = _edge(
        chunks[1],
        "logical-cell",
        expected,
        bottom_extent,
        footprint=(bottom_footprint,),
    )
    items = (
        _item(chunks[0], 1, (top,)),
        _item(chunks[1], 2, (bottom,)),
    )
    trace = _trace(
        chunks=chunks,
        edges=(top, bottom),
        mapping_statuses={"logical-cell": ReverseMappingStatus.COMPLETE},
        candidate=items,
        ranked=items,
        context=items,
    )

    result = evaluate_unified_trace(
        _gold(("cell",), evidence_to_object={"cell": "logical-cell"}),
        trace,
        profile=_profile(2),
    )

    assert _metric(result, "ranked_evidence_coverage@1").value == 0
    assert _metric(result, "ranked_evidence_coverage@3").value == 1
    assert _metric(result, "ranked_complete_evidence_mrr@5").value == 0.5


def test_unknown_mapping_is_unavailable_unless_the_metric_is_already_one() -> None:
    chunks = (_chunk("unknown"), _chunk("known"))
    expected = _text_extent("gold-a")
    half = _edge(chunks[1], "gold-a", expected, _covered_text("gold-a", 0, 5))
    items = (
        _item(chunks[0], 1, ()),
        _item(chunks[1], 2, (half,)),
    )
    trace = _trace(
        chunks=chunks,
        edges=(half,),
        mapping_statuses={"gold-a": ReverseMappingStatus.PARTIAL},
        candidate=items,
        ranked=items,
        context=items,
    )

    result = evaluate_unified_trace(
        _gold(("gold-a",)), trace, profile=_profile(2)
    )

    assert (
        _metric(result, "ranked_evidence_coverage@3").status
        == EvaluationMetricStatus.UNAVAILABLE
    )
    assert (
        _metric(result, "ranked_complete_evidence_mrr@5").status
        == EvaluationMetricStatus.UNAVAILABLE
    )

    full = _edge(chunks[0], "gold-a", expected, expected)
    complete_items = (
        _item(chunks[0], 1, (full,)),
        _item(chunks[1], 2, (half,)),
    )
    complete_trace = _trace(
        chunks=chunks,
        edges=(full, half),
        mapping_statuses={"gold-a": ReverseMappingStatus.PARTIAL},
        candidate=complete_items,
        ranked=complete_items,
        context=complete_items,
    )
    complete_result = evaluate_unified_trace(
        _gold(("gold-a",)), complete_trace, profile=_profile(2)
    )

    assert _metric(complete_result, "ranked_evidence_coverage@1").value == 1
    assert _metric(complete_result, "ranked_complete_evidence_mrr@5").value == 1


def test_corrupted_gold_mapping_fails_closed_even_with_a_positive_edge() -> None:
    chunk = _chunk("chunk")
    extent = _text_extent("gold-a")
    edge = _edge(chunk, "gold-a", extent, extent)
    item = _item(chunk, 1, (edge,))
    trace = _trace(
        chunks=(chunk,),
        edges=(edge,),
        mapping_statuses={"gold-a": ReverseMappingStatus.COMPLETE},
        candidate=(item,),
        ranked=(item,),
        context=(item,),
        mapping_diagnostics=(
            MappingDiagnostic(
                canonical_object_id="gold-a",
                status=MappingDiagnosticStatus.CORRUPTED,
                reason_code="ambiguous_duplicate",
            ),
        ),
    )

    result = evaluate_unified_trace(
        _gold(("gold-a",)), trace, profile=_profile(1)
    )

    assert (
        _metric(result, "ranked_evidence_coverage@1").status
        == EvaluationMetricStatus.UNAVAILABLE
    )
    assert result.failure is not None
    assert result.failure.kind == FailureKind.UNOBSERVABLE


def test_pipeline_loss_requires_a_proved_transition() -> None:
    chunks = (_chunk("lost"), _chunk("retained"))
    extent_a = _text_extent("gold-a")
    extent_b = _text_extent("gold-b")
    edge_a = _edge(chunks[0], "gold-a", extent_a, extent_a)
    edge_b = _edge(chunks[1], "gold-b", extent_b, extent_b)
    candidate = (
        _item(chunks[0], 1, (edge_a,)),
        _item(chunks[1], 2, (edge_b,)),
    )
    ranked = (_item(chunks[1], 1, (edge_b,)),)
    trace = _trace(
        chunks=chunks,
        edges=(edge_a, edge_b),
        mapping_statuses={
            "gold-a": ReverseMappingStatus.COMPLETE,
            "gold-b": ReverseMappingStatus.COMPLETE,
        },
        candidate=candidate,
        ranked=ranked,
        context=ranked,
    )
    gold = _gold(("gold-a",), ("gold-b",))

    result = evaluate_unified_trace(gold, trace, profile=_profile(2))
    ranking_delta = result.pipeline_delta("candidate_to_ranked")

    assert ranking_delta.status == EvaluationMetricStatus.OBSERVED
    assert ranking_delta.loss_fraction == 0.5
    assert ranking_delta.gain_fraction == 0
    assert ranking_delta.object_deltas[0].canonical_object_id == "gold-a"
    assert ranking_delta.object_deltas[0].lost_fraction == 1

    unobservable_trace = _trace(
        chunks=chunks,
        edges=(edge_a, edge_b),
        mapping_statuses={
            "gold-a": ReverseMappingStatus.COMPLETE,
            "gold-b": ReverseMappingStatus.COMPLETE,
        },
        candidate=candidate,
        ranked=ranked,
        context=ranked,
        candidate_to_ranked=StageTransitionMode.UNOBSERVABLE,
        transformations=(),
    )
    unobservable = evaluate_unified_trace(
        gold, unobservable_trace, profile=_profile(2)
    ).pipeline_delta("candidate_to_ranked")

    assert unobservable.status == EvaluationMetricStatus.UNAVAILABLE


def test_verified_stage_gain_is_recorded_separately_from_loss() -> None:
    source_chunk = _chunk("source")
    derived_chunk = _chunk("expanded")
    extent = _text_extent("gold-b")
    edge = _edge(derived_chunk, "gold-b", extent, extent)
    candidate = (_item(source_chunk, 1, ()),)
    ranked = (_item(derived_chunk, 1, (edge,)),)
    transformation = TransformationRecord.build(
        source_stage=StageName.CANDIDATE,
        target_stage=StageName.RANKED,
        source_item_references=(
            StageItemReference(
                stage=StageName.CANDIDATE,
                native_chunk_id=source_chunk.native_chunk_id,
                content_sha256=source_chunk.content_sha256,
            ),
        ),
        transformation_kind="parent_expansion",
        output_native_chunk_id=derived_chunk.native_chunk_id,
        output_content_sha256=derived_chunk.content_sha256,
        lineage_integrity_status=LineageIntegrityStatus.VERIFIED,
    )
    trace = _trace(
        chunks=(source_chunk,),
        edges=(edge,),
        mapping_statuses={"gold-b": ReverseMappingStatus.COMPLETE},
        candidate=candidate,
        ranked=ranked,
        context=ranked,
        candidate_to_ranked=StageTransitionMode.VERIFIED_DERIVATION,
        transformations=(transformation,),
    )

    result = evaluate_unified_trace(
        _gold(("gold-b",)), trace, profile=_profile(1)
    )
    delta = result.pipeline_delta("candidate_to_ranked")

    assert delta.status == EvaluationMetricStatus.OBSERVED
    assert delta.loss_fraction == 0
    assert delta.gain_fraction == 1
    assert _metric(result, "ranking_loss").value == 0
    assert _metric(result, "candidate_to_ranked_stage_gain").value == 1


def test_derived_context_without_output_coverage_proof_is_unavailable() -> None:
    source_chunk = _chunk("source")
    derived_chunk = _chunk("compressed-context")
    extent = _text_extent("gold-a")
    edge = _edge(source_chunk, "gold-a", extent, extent)
    source_item = _item(source_chunk, 1, (edge,))
    derived_item = _item(derived_chunk, 1, ())
    transformation = TransformationRecord.build(
        source_stage=StageName.RANKED,
        target_stage=StageName.CONTEXT,
        source_item_references=(
            StageItemReference(
                stage=StageName.RANKED,
                native_chunk_id=source_chunk.native_chunk_id,
                content_sha256=source_chunk.content_sha256,
            ),
        ),
        transformation_kind="compression",
        output_native_chunk_id=derived_chunk.native_chunk_id,
        output_content_sha256=derived_chunk.content_sha256,
        lineage_integrity_status=LineageIntegrityStatus.VERIFIED,
    )
    trace = _trace(
        chunks=(source_chunk,),
        edges=(edge,),
        mapping_statuses={"gold-a": ReverseMappingStatus.COMPLETE},
        candidate=(source_item,),
        ranked=(source_item,),
        context=(derived_item,),
        ranked_to_context=StageTransitionMode.VERIFIED_DERIVATION,
        transformations=(transformation,),
    )

    result = evaluate_unified_trace(
        _gold(("gold-a",)), trace, profile=_profile(1)
    )

    context = next(
        item for item in result.localizations if item.stage == StageName.CONTEXT
    )
    assert context.status == EvaluationMetricStatus.UNAVAILABLE
    assert result.pipeline_delta("ranked_to_context").status == (
        EvaluationMetricStatus.UNAVAILABLE
    )
    assert result.failure is not None
    assert result.failure.kind == FailureKind.UNOBSERVABLE


def test_failure_attribution_is_proof_gated_through_generation() -> None:
    chunks = (_chunk("gold"), _chunk("noise"))
    extent = _text_extent("gold-a")
    edge = _edge(chunks[0], "gold-a", extent, extent)
    gold_item = _item(chunks[0], 1, (edge,))
    noise_item = _item(chunks[1], 1, ())
    gold = _gold(("gold-a",))
    answer = GoldAnswer(
        gold_answer_id="answer-1",
        kind=GoldAnswerKind.NUMERIC,
        canonical="42",
    )

    retrieval_loss = evaluate_unified_trace(
        gold,
        _trace(
            chunks=chunks,
            edges=(edge,),
            mapping_statuses={"gold-a": ReverseMappingStatus.COMPLETE},
            candidate=(noise_item,),
            ranked=(noise_item,),
            context=(noise_item,),
            answer="999",
        ),
        profile=_profile(1),
        gold_answer=answer,
    )
    assert retrieval_loss.failure is not None
    assert retrieval_loss.failure.kind == FailureKind.RETRIEVAL_LOSS
    assert retrieval_loss.failure.cutoff == 1

    generation_failure = evaluate_unified_trace(
        gold,
        _trace(
            chunks=chunks,
            edges=(edge,),
            mapping_statuses={"gold-a": ReverseMappingStatus.COMPLETE},
            candidate=(gold_item,),
            ranked=(gold_item,),
            context=(gold_item,),
            answer="999",
        ),
        profile=_profile(1),
        gold_answer=answer,
    )
    assert generation_failure.failure is not None
    assert generation_failure.failure.kind == FailureKind.GENERATION_FAILURE


def test_parser_ranking_and_context_failures_require_complete_prior_proof() -> None:
    gold_chunk = _chunk("gold")
    noise_chunk = _chunk("noise")
    extent = _text_extent("gold-a")
    edge = _edge(gold_chunk, "gold-a", extent, extent)
    gold_item_candidate = _item(gold_chunk, 1, (edge,))
    noise_item_candidate = _item(noise_chunk, 2, ())
    noise_item_ranked = _item(noise_chunk, 1, ())
    gold = _gold(("gold-a",))

    parser_loss = evaluate_unified_trace(
        gold,
        _trace(
            chunks=(noise_chunk,),
            edges=(),
            mapping_statuses={"gold-a": ReverseMappingStatus.MISSING},
            expected_extents={"gold-a": extent},
            candidate=(_item(noise_chunk, 1, ()),),
            ranked=(_item(noise_chunk, 1, ()),),
            context=(_item(noise_chunk, 1, ()),),
        ),
        profile=_profile(1),
    )
    assert parser_loss.failure is not None
    assert parser_loss.failure.kind == FailureKind.PARSER_INDEX_LOSS

    ranking_loss = evaluate_unified_trace(
        gold,
        _trace(
            chunks=(gold_chunk, noise_chunk),
            edges=(edge,),
            mapping_statuses={"gold-a": ReverseMappingStatus.COMPLETE},
            candidate=(gold_item_candidate, noise_item_candidate),
            ranked=(noise_item_ranked,),
            context=(noise_item_ranked,),
        ),
        profile=_profile(2),
    )
    assert ranking_loss.failure is not None
    assert ranking_loss.failure.kind == FailureKind.RANKING_LOSS
    assert ranking_loss.failure.cutoff == 5

    context_loss = evaluate_unified_trace(
        gold,
        _trace(
            chunks=(gold_chunk,),
            edges=(edge,),
            mapping_statuses={"gold-a": ReverseMappingStatus.COMPLETE},
            candidate=(gold_item_candidate,),
            ranked=(gold_item_candidate,),
            context=(),
        ),
        profile=_profile(1),
    )
    assert context_loss.failure is not None
    assert context_loss.failure.kind == FailureKind.CONTEXT_LOSS


def test_unknown_earlier_rank_makes_mrr_unavailable_but_not_complete_coverage() -> None:
    chunks = (_chunk("unknown"), _chunk("complete"))
    expected = _text_extent("gold-a")
    full = _edge(chunks[1], "gold-a", expected, expected)
    items = (
        _item(chunks[0], 1, ()),
        _item(chunks[1], 2, (full,)),
    )
    trace = _trace(
        chunks=chunks,
        edges=(full,),
        mapping_statuses={"gold-a": ReverseMappingStatus.PARTIAL},
        candidate=items,
        ranked=items,
        context=items,
    )

    result = evaluate_unified_trace(
        _gold(("gold-a",)), trace, profile=_profile(2)
    )

    assert _metric(result, "ranked_evidence_coverage@3").value == 1
    assert _metric(result, "ranked_complete_evidence_recall@3").value == 1
    assert (
        _metric(result, "ranked_complete_evidence_mrr@5").status
        == EvaluationMetricStatus.UNAVAILABLE
    )
    assert _metric(result, "ranked_complete_evidence_mrr@5").lower_bound == 0.5
    assert _metric(result, "ranked_complete_evidence_mrr@5").upper_bound == 1


def test_or_alternative_and_path_aggregation_use_best_verified_choice() -> None:
    chunk = _chunk("alternative")
    extent = _text_extent("gold-b")
    edge = _edge(chunk, "gold-b", extent, extent)
    item = _item(chunk, 1, (edge,))
    gold = _gold(
        ("evidence-a", "evidence-b"),
        evidence_to_object={
            "evidence-a": "gold-a",
            "evidence-b": "gold-b",
        },
    )
    trace = _trace(
        chunks=(chunk,),
        edges=(edge,),
        mapping_statuses={
            "gold-a": ReverseMappingStatus.MISSING,
            "gold-b": ReverseMappingStatus.COMPLETE,
        },
        expected_extents={"gold-a": _text_extent("gold-a")},
        candidate=(item,),
        ranked=(item,),
        context=(item,),
    )

    result = evaluate_unified_trace(gold, trace, profile=_profile(1))

    assert _metric(result, "ranked_evidence_coverage@1").value == 1
    assert _metric(result, "ranked_complete_evidence_recall@1").value == 1


def test_unified_scorer_has_no_rag_or_corpus_mode_branches() -> None:
    root = Path(__file__).resolve().parents[2] / "src/rag_eval/evaluation/unified"
    forbidden = {"lightrag", "rag_anything", "rag-anything", "evaluation_corpus"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        strings = {
            node.value.casefold()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert not any(
            token in value for token in forbidden for value in strings
        ), path


def test_legacy_shadow_comparison_is_explicitly_versioned() -> None:
    chunk = _chunk("gold")
    extent = _text_extent("gold-a")
    edge = _edge(chunk, "gold-a", extent, extent)
    item = _item(chunk, 1, (edge,))
    result = evaluate_unified_trace(
        _gold(("gold-a",)),
        _trace(
            chunks=(chunk,),
            edges=(edge,),
            mapping_statuses={"gold-a": ReverseMappingStatus.COMPLETE},
            candidate=(item,),
            ranked=(item,),
            context=(item,),
        ),
        profile=_profile(1),
    )
    legacy = [
        MetricResult(
            metric_id="ranked_recall@1",
            status=MetricStatus.OBSERVED,
            value=1,
            numerator=1,
            denominator=1,
            scorer_id="legacy",
            scorer_version="1",
            scorer_digest=SHA_A,
        )
    ]

    shadow = compare_legacy_shadow(legacy, result)

    assert shadow.legacy_scorer_version == "1"
    assert shadow.unified_scorer_version == result.scorer_version
    assert shadow.differences[0].kind == ShadowDifferenceKind.EQUIVALENT
    assert shadow.differences[0].unified_metric_id == (
        "ranked_complete_evidence_recall@1"
    )
