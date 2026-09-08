from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_eval.contracts.adapter import (
    AdapterCapabilities,
    RAGEvidenceItem,
    RAGResult,
)
from rag_eval.contracts.canonical import SourceSpan
from rag_eval.contracts.observation import (
    AdapterCapabilitiesV2,
    AdapterRunResultV2,
    CanonicalExtent,
    CanonicalMappingRecord,
    ContentObservation,
    ExtentUnit,
    IngestionCatalogObservation,
    NativeLineage,
    ObservationCompleteness,
    ObservationProfileIdentity,
    ObservationStatus,
    ObservedStageItem,
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
from rag_eval.contracts.observation_compat import normalize_rag_result_v1
from rag_eval.contracts.schema import PUBLIC_MODELS

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _source() -> SourceIdentity:
    return SourceIdentity(
        document_id="doc-1",
        source_sha256=SHA_A,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        source_coordinate_schema="ooxml-structural-v1",
        canonical_catalog_sha256=SHA_B,
    )


def _runtime_profile() -> RuntimeProfileIdentity:
    return RuntimeProfileIdentity(
        profile_id="runtime-fixture",
        system_id="system-fixture",
        system_version="1.0",
        configuration_digest=SHA_C,
    )


def _capabilities(
    *,
    ranked_to_context: StageTransitionMode = StageTransitionMode.IDENTITY_SUBSET,
) -> AdapterCapabilitiesV2:
    return AdapterCapabilitiesV2(
        ingestion_catalog=True,
        candidate_retrieval=True,
        ranked_retrieval=True,
        final_context=True,
        prompt_trace=True,
        answer=True,
        provenance=True,
        transformation_lineage=(
            ranked_to_context == StageTransitionMode.VERIFIED_DERIVATION
        ),
        transitions=(
            StageTransitionDeclaration(
                source_stage=StageName.CANDIDATE,
                target_stage=StageName.RANKED,
                mode=StageTransitionMode.IDENTITY_SUBSET,
            ),
            StageTransitionDeclaration(
                source_stage=StageName.RANKED,
                target_stage=StageName.CONTEXT,
                mode=ranked_to_context,
            ),
        ),
    )


def _observation_profile(
    capabilities: AdapterCapabilitiesV2,
) -> ObservationProfileIdentity:
    return ObservationProfileIdentity.build(
        profile_id="observer-fixture",
        adapter_id="adapter-fixture",
        adapter_version="1.0",
        capabilities=capabilities,
    )


def _chunk(native_chunk_id: str, content: str) -> RuntimeChunkRecord:
    lineage = NativeLineage.build(
        schema_version="native-lineage/1",
        source_sha256=SHA_A,
        payload={"chunk": native_chunk_id},
    )
    return RuntimeChunkRecord(
        native_document_id="native-doc-1",
        native_chunk_id=native_chunk_id,
        content=content,
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        native_lineage=lineage,
        parser_identity="native-parser/1",
        chunker_identity="native-chunker/1",
        persisted_metadata_digest=SHA_A,
    )


def _item(
    native_chunk_id: str,
    rank: int,
    content: str,
    *,
    edge_ids: tuple[str, ...] = (),
) -> ObservedStageItem:
    return ObservedStageItem(
        native_chunk_id=native_chunk_id,
        native_rank=rank,
        content=content,
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        provenance_edge_ids=edge_ids,
    )


def _stage(
    stage: StageName,
    items: tuple[ObservedStageItem, ...],
    *,
    completeness: ObservationCompleteness = ObservationCompleteness.COMPLETE,
    configured_cutoff: int | None = None,
    proven_prefix_depth: int | None = None,
) -> StageObservation:
    return StageObservation(
        stage=stage,
        observation_status=ObservationStatus.OBSERVED,
        completeness=completeness,
        configured_cutoff=configured_cutoff,
        proven_prefix_depth=proven_prefix_depth,
        items=items,
    )


def _content(value: str) -> ContentObservation:
    return ContentObservation.observed(value)


def _unsupported_content(reason: str) -> ContentObservation:
    return ContentObservation(
        observation_status=ObservationStatus.UNSUPPORTED,
        completeness=ObservationCompleteness.UNKNOWN,
        content=None,
        content_sha256=None,
        reason=reason,
    )


def _extent() -> CanonicalExtent:
    return CanonicalExtent.build(
        extent_kind="text_span",
        units=(
            ExtentUnit(
                unit_id="paragraph-1:0-7",
                coordinate_system="canonical-text-offset-v1",
                start=0,
                end=7,
            ),
        ),
    )


def _edge(chunk: RuntimeChunkRecord) -> ProvenanceEdge:
    extent = _extent()
    assert chunk.native_lineage is not None
    return ProvenanceEdge.build(
        native_chunk_id=chunk.native_chunk_id,
        canonical_object_id="paragraph-1",
        canonical_locator=SourceSpan(
            part="word/document.xml",
            coordinates={"body_ordinal": 1},
            text_start=0,
            text_end=7,
        ),
        mapping_tier="native_lineage",
        coverage_status=ProvenanceCoverageStatus.COMPLETE,
        expected_extent=extent,
        covered_extent=extent,
        source_sha256=SHA_A,
        native_content_sha256=chunk.content_sha256,
        native_lineage_sha256=chunk.native_lineage.lineage_sha256,
        canonical_value_sha256=hashlib.sha256(b"gold-42").hexdigest(),
        reason_code="verified_native_lineage",
    )


def _mapping(edge: ProvenanceEdge) -> CanonicalMappingRecord:
    return CanonicalMappingRecord.build(
        canonical_object_id=edge.canonical_object_id,
        expected_extent=edge.expected_extent,
        reverse_mapping_status=ReverseMappingStatus.COMPLETE,
        native_chunk_ids=(edge.native_chunk_id,),
    )


def _trace(
    *,
    chunks: tuple[RuntimeChunkRecord, ...],
    candidate: StageObservation,
    ranked: StageObservation,
    context: StageObservation,
    capabilities: AdapterCapabilitiesV2,
    provenance_edges: tuple[ProvenanceEdge, ...] = (),
    mappings: tuple[CanonicalMappingRecord, ...] = (),
    transformations: tuple[TransformationRecord, ...] = (),
) -> UnifiedTrace:
    return UnifiedTrace.build(
        case_id="case-1",
        source_identity=_source(),
        runtime_profile=_runtime_profile(),
        observation_profile=_observation_profile(capabilities),
        ingestion_catalog=IngestionCatalogObservation(
            observation_status=ObservationStatus.OBSERVED,
            completeness=ObservationCompleteness.COMPLETE,
            items=chunks,
        ),
        provenance_edges=provenance_edges,
        canonical_mapping_records=mappings,
        mapping_diagnostics=(),
        raw_retrieval=candidate,
        ranked_retrieval=ranked,
        final_context=context,
        transformations=transformations,
        prompt_trace=_content("prompt"),
        answer=_content("answer"),
        validation_receipts=(),
    )


def test_observation_status_and_completeness_are_orthogonal() -> None:
    empty = _stage(StageName.CANDIDATE, ())
    items = tuple(_item(f"chunk-{rank}", rank, str(rank)) for rank in range(1, 6))
    truncated = _stage(
        StageName.RANKED,
        items,
        completeness=ObservationCompleteness.TRUNCATED,
        configured_cutoff=20,
        proven_prefix_depth=5,
    )

    assert empty.items == ()
    assert empty.completeness == ObservationCompleteness.COMPLETE
    assert truncated.proven_prefix_depth == 5
    assert truncated.proves_prefix(5)
    assert not truncated.proves_prefix(6)


@pytest.mark.parametrize(
    "payload, message",
    [
        (
            {
                "stage": "candidate",
                "observation_status": "unsupported",
                "completeness": "complete",
                "items": (),
                "reason": "not exposed",
            },
            "non-observed",
        ),
        (
            {
                "stage": "ranked",
                "observation_status": "observed",
                "completeness": "truncated",
                "items": (),
            },
            "truncated",
        ),
        (
            {
                "stage": "ranked",
                "observation_status": "observed",
                "completeness": "truncated",
                "configured_cutoff": 3,
                "proven_prefix_depth": 4,
                "items": tuple(_item(f"chunk-{i}", i, str(i)) for i in range(1, 5)),
            },
            "configured cutoff",
        ),
        (
            {
                "stage": "ranked",
                "observation_status": "observed",
                "completeness": "complete",
                "items": (_item("chunk-2", 2, "two"),),
            },
            "contiguous",
        ),
    ],
)
def test_illegal_stage_observation_combinations_fail_closed(
    payload: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        StageObservation.model_validate(payload)


@pytest.mark.parametrize("status", list(ObservationStatus))
@pytest.mark.parametrize("completeness", list(ObservationCompleteness))
def test_status_completeness_matrix_is_explicit(
    status: ObservationStatus, completeness: ObservationCompleteness
) -> None:
    payload: dict[str, object] = {
        "stage": StageName.CANDIDATE,
        "observation_status": status,
        "completeness": completeness,
        "items": (),
    }
    if status != ObservationStatus.OBSERVED:
        payload["reason"] = "not observed"
    if (
        status == ObservationStatus.OBSERVED
        and completeness == ObservationCompleteness.TRUNCATED
    ):
        payload |= {
            "items": (_item("chunk-1", 1, "one"),),
            "configured_cutoff": 1,
            "proven_prefix_depth": 1,
        }

    valid = status == ObservationStatus.OBSERVED or (
        completeness == ObservationCompleteness.UNKNOWN
    )
    if valid:
        StageObservation.model_validate(payload)
    else:
        with pytest.raises(ValidationError, match="non-observed"):
            StageObservation.model_validate(payload)


def test_runtime_catalog_provenance_and_reverse_map_round_trip() -> None:
    chunk = _chunk("chunk-a", "gold-42")
    edge = _edge(chunk)
    item = _item("chunk-a", 1, "gold-42", edge_ids=(edge.edge_id,))
    capabilities = _capabilities()

    trace = _trace(
        chunks=(chunk,),
        candidate=_stage(StageName.CANDIDATE, (item,)),
        ranked=_stage(StageName.RANKED, (item,)),
        context=_stage(StageName.CONTEXT, (item,)),
        capabilities=capabilities,
        provenance_edges=(edge,),
        mappings=(_mapping(edge),),
    )
    result = AdapterRunResultV2(
        adapter_id="adapter-fixture",
        adapter_version="1.0",
        system_id="system-fixture",
        system_version="1.0",
        trace=trace,
    )

    assert UnifiedTrace.model_validate_json(trace.model_dump_json()) == trace
    assert AdapterRunResultV2.model_validate_json(result.model_dump_json()) == result
    assert trace.provenance_map_digest
    assert trace.trace_digest


def test_exact_unique_mapping_can_prove_ranked_coverage_without_a_catalog() -> None:
    content = "unique runtime evidence"
    item_without_edge = _item("stage-only", 1, content)
    expected = _extent()
    edge = ProvenanceEdge.build(
        native_chunk_id="stage-only",
        canonical_object_id="paragraph-1",
        canonical_locator=SourceSpan(
            part="word/document.xml",
            coordinates={"body_ordinal": 1},
            text_start=0,
            text_end=7,
        ),
        mapping_tier="text_unique_exact",
        coverage_status=ProvenanceCoverageStatus.COMPLETE,
        expected_extent=expected,
        covered_extent=expected,
        source_sha256=SHA_A,
        native_content_sha256=item_without_edge.content_sha256,
        canonical_value_sha256=hashlib.sha256(b"gold-42").hexdigest(),
        reason_code="exact_unique_in_verified_source_scope",
    )
    item = _item("stage-only", 1, content, edge_ids=(edge.edge_id,))
    capabilities = _capabilities().model_copy(update={"ingestion_catalog": False})

    trace = UnifiedTrace.build(
        case_id="case-stage-only",
        source_identity=_source(),
        runtime_profile=_runtime_profile(),
        observation_profile=_observation_profile(capabilities),
        ingestion_catalog=IngestionCatalogObservation(
            observation_status=ObservationStatus.UNSUPPORTED,
            completeness=ObservationCompleteness.UNKNOWN,
            items=(),
            reason="runtime does not expose ingestion catalog",
        ),
        provenance_edges=(edge,),
        canonical_mapping_records=(_mapping(edge),),
        mapping_diagnostics=(),
        raw_retrieval=_stage(StageName.CANDIDATE, (item,)),
        ranked_retrieval=_stage(StageName.RANKED, (item,)),
        final_context=_stage(StageName.CONTEXT, (item,)),
        transformations=(),
        prompt_trace=_content("prompt"),
        answer=_content("answer"),
        validation_receipts=(),
    )

    assert trace.ingestion_catalog.observation_status == "unsupported"
    assert trace.ranked_retrieval.items[0].provenance_edge_ids == (edge.edge_id,)


def test_unknown_runtime_item_is_corruption_not_an_empty_mapping() -> None:
    chunk = _chunk("chunk-a", "a")
    unknown = _item("chunk-unknown", 1, "unknown")
    capabilities = _capabilities()

    with pytest.raises(ValidationError, match="unknown runtime or derived item"):
        _trace(
            chunks=(chunk,),
            candidate=_stage(StageName.CANDIDATE, (unknown,)),
            ranked=_stage(StageName.RANKED, (unknown,)),
            context=_stage(StageName.CONTEXT, (unknown,)),
            capabilities=capabilities,
        )


def test_identity_subset_transition_rejects_a_new_native_identity() -> None:
    chunk = _chunk("chunk-a", "a")
    candidate = _item("chunk-a", 1, "a")
    context = _item("chunk-derived", 1, "derived")
    capabilities = _capabilities()

    with pytest.raises(ValidationError, match="identity_subset"):
        _trace(
            chunks=(chunk,),
            candidate=_stage(StageName.CANDIDATE, (candidate,)),
            ranked=_stage(StageName.RANKED, (candidate,)),
            context=_stage(StageName.CONTEXT, (context,)),
            capabilities=capabilities,
        )


def test_verified_derivation_accepts_merge_with_a_verified_receipt() -> None:
    chunk_a = _chunk("chunk-a", "a")
    chunk_b = _chunk("chunk-b", "b")
    candidate_items = (
        _item("chunk-a", 1, "a"),
        _item("chunk-b", 2, "b"),
    )
    merged = _item("context-merged", 1, "a\nb")
    transformation = TransformationRecord.build(
        source_stage=StageName.RANKED,
        target_stage=StageName.CONTEXT,
        source_item_references=(
            StageItemReference(
                stage=StageName.RANKED,
                native_chunk_id="chunk-a",
                content_sha256=candidate_items[0].content_sha256,
            ),
            StageItemReference(
                stage=StageName.RANKED,
                native_chunk_id="chunk-b",
                content_sha256=candidate_items[1].content_sha256,
            ),
        ),
        transformation_kind="merge",
        output_native_chunk_id="context-merged",
        output_content_sha256=merged.content_sha256,
        lineage_integrity_status="verified",
    )
    capabilities = _capabilities(
        ranked_to_context=StageTransitionMode.VERIFIED_DERIVATION
    )

    trace = _trace(
        chunks=(chunk_a, chunk_b),
        candidate=_stage(StageName.CANDIDATE, candidate_items),
        ranked=_stage(StageName.RANKED, candidate_items),
        context=_stage(StageName.CONTEXT, (merged,)),
        capabilities=capabilities,
        transformations=(transformation,),
    )

    assert trace.transformations[0].lineage_integrity_status == "verified"
    assert trace.final_context.items[0].native_chunk_id == "context-merged"
    assert trace.final_context.items[0].provenance_edge_ids == ()


def test_tampered_provenance_receipt_and_reverse_map_fail_closed() -> None:
    chunk = _chunk("chunk-a", "gold-42")
    edge = _edge(chunk)

    with pytest.raises(ValidationError, match="provenance receipt"):
        ProvenanceEdge.model_validate(
            edge.model_dump(mode="json") | {"receipt_sha256": SHA_A}
        )

    item = _item("chunk-a", 1, "gold-42", edge_ids=(edge.edge_id,))
    capabilities = _capabilities()
    bad_mapping = CanonicalMappingRecord.build(
        canonical_object_id=edge.canonical_object_id,
        expected_extent=edge.expected_extent,
        reverse_mapping_status=ReverseMappingStatus.MISSING,
        native_chunk_ids=(),
    )
    with pytest.raises(ValidationError, match="forward/reverse provenance"):
        _trace(
            chunks=(chunk,),
            candidate=_stage(StageName.CANDIDATE, (item,)),
            ranked=_stage(StageName.RANKED, (item,)),
            context=_stage(StageName.CONTEXT, (item,)),
            capabilities=capabilities,
            provenance_edges=(edge,),
            mappings=(bad_mapping,),
        )


def test_partial_provenance_must_stay_within_the_expected_extent() -> None:
    chunk = _chunk("chunk-a", "gold-42")
    expected = _extent()
    covered = CanonicalExtent.build(
        extent_kind="text_span",
        units=(
            ExtentUnit(
                unit_id="paragraph-1:0-7",
                coordinate_system="canonical-text-offset-v1",
                start=2,
                end=5,
            ),
        ),
    )
    partial = ProvenanceEdge.build(
        native_chunk_id=chunk.native_chunk_id,
        canonical_object_id="paragraph-1",
        canonical_locator=SourceSpan(
            part="word/document.xml",
            coordinates={"body_ordinal": 1},
            text_start=0,
            text_end=7,
        ),
        mapping_tier="deterministic_crosswalk",
        coverage_status=ProvenanceCoverageStatus.PARTIAL,
        expected_extent=expected,
        covered_extent=covered,
        source_sha256=SHA_A,
        native_content_sha256=chunk.content_sha256,
        canonical_value_sha256=hashlib.sha256(b"gold-42").hexdigest(),
        reason_code="verified_partial_crosswalk",
    )
    assert partial.coverage_status == ProvenanceCoverageStatus.PARTIAL

    outside = CanonicalExtent.build(
        extent_kind="text_span",
        units=(
            ExtentUnit(
                unit_id="paragraph-1:0-7",
                coordinate_system="canonical-text-offset-v1",
                start=6,
                end=9,
            ),
        ),
    )
    with pytest.raises(ValidationError, match="outside the expected extent"):
        ProvenanceEdge.build(
            native_chunk_id=chunk.native_chunk_id,
            canonical_object_id="paragraph-1",
            canonical_locator=partial.canonical_locator,
            mapping_tier="deterministic_crosswalk",
            coverage_status=ProvenanceCoverageStatus.PARTIAL,
            expected_extent=expected,
            covered_extent=outside,
            source_sha256=SHA_A,
            native_content_sha256=chunk.content_sha256,
            canonical_value_sha256=partial.canonical_value_sha256,
            reason_code="invalid_partial_crosswalk",
        )


def test_corrupted_observation_is_persistable_but_never_proves_a_prefix() -> None:
    corrupted = StageObservation(
        stage=StageName.RANKED,
        observation_status=ObservationStatus.CORRUPTED,
        completeness=ObservationCompleteness.UNKNOWN,
        items=(),
        reason="rank receipt mismatch",
        diagnostics={"raw_rank": 1},
    )

    assert (
        StageObservation.model_validate_json(corrupted.model_dump_json()) == corrupted
    )
    assert not corrupted.proves_prefix(1)


def test_wire_v1_normalizer_preserves_unknown_and_empty_without_inventing_proof() -> (
    None
):
    legacy = RAGResult(
        answer="answer",
        raw_retrieval=None,
        ranked_retrieval=[],
        final_context=None,
    )
    before = legacy.model_dump_json()

    normalized = normalize_rag_result_v1(
        legacy,
        case_id="case-legacy",
        source_identity=_source(),
        runtime_profile=_runtime_profile(),
        legacy_capabilities=AdapterCapabilities(
            answer=True,
            raw_retrieval=True,
            ranked_retrieval=True,
            final_context=False,
        ),
        adapter_id="legacy-adapter",
        adapter_version="1.0",
    )

    assert legacy.model_dump_json() == before
    assert normalized.normalization is not None
    assert normalized.normalization.source_protocol_version == "1.0"
    assert normalized.trace.raw_retrieval.observation_status == "unobserved"
    assert normalized.trace.ranked_retrieval.observation_status == "observed"
    assert normalized.trace.ranked_retrieval.items == ()
    assert normalized.trace.ranked_retrieval.completeness == "unknown"
    assert normalized.trace.final_context.observation_status == "unsupported"
    assert normalized.trace.answer.content == "answer"
    assert normalized.trace.provenance_edges == ()


def test_wire_v1_items_are_content_pinned_but_mapping_remains_unsupported() -> None:
    legacy = RAGResult(
        ranked_retrieval=[
            RAGEvidenceItem(
                item_id="legacy-1",
                native_id="native-1",
                rank=1,
                content="legacy content",
            )
        ]
    )
    normalized = normalize_rag_result_v1(
        legacy,
        case_id="case-legacy",
        source_identity=_source(),
        runtime_profile=_runtime_profile(),
        legacy_capabilities=AdapterCapabilities(ranked_retrieval=True),
        adapter_id="legacy-adapter",
        adapter_version="1.0",
    )

    item = normalized.trace.ranked_retrieval.items[0]
    assert item.native_chunk_id == "native-1"
    assert item.content_sha256 == hashlib.sha256(b"legacy content").hexdigest()
    assert item.provenance_edge_ids == ()
    assert normalized.trace.mapping_diagnostics
    assert all(
        diagnostic.status == "unsupported"
        for diagnostic in normalized.trace.mapping_diagnostics
    )


def test_wire_v1_shadow_normalization_preserves_observed_native_values() -> None:
    def legacy_item(stage: str, rank: int) -> RAGEvidenceItem:
        return RAGEvidenceItem(
            item_id=f"{stage}-item-{rank}",
            native_id=f"{stage}-native-{rank}",
            rank=rank,
            score=1.0 / rank,
            content=f"{stage}-content-{rank}",
        )

    legacy = RAGResult(
        answer="shadow answer",
        raw_retrieval=[legacy_item("candidate", 1), legacy_item("candidate", 2)],
        ranked_retrieval=[legacy_item("ranked", 1)],
        final_context=[legacy_item("context", 1)],
    )
    normalized = normalize_rag_result_v1(
        legacy,
        case_id="case-shadow",
        source_identity=_source(),
        runtime_profile=_runtime_profile(),
        legacy_capabilities=AdapterCapabilities(
            answer=True,
            raw_retrieval=True,
            ranked_retrieval=True,
            final_context=True,
        ),
        adapter_id="legacy-adapter",
        adapter_version="1.0",
    )

    for legacy_items, observed in (
        (legacy.raw_retrieval, normalized.trace.raw_retrieval),
        (legacy.ranked_retrieval, normalized.trace.ranked_retrieval),
        (legacy.final_context, normalized.trace.final_context),
    ):
        assert legacy_items is not None
        assert [item.native_chunk_id for item in observed.items] == [
            item.native_id for item in legacy_items
        ]
        assert [item.native_rank for item in observed.items] == [
            item.rank for item in legacy_items
        ]
        assert [item.runtime_score for item in observed.items] == [
            item.score for item in legacy_items
        ]
        assert [item.content for item in observed.items] == [
            item.content for item in legacy_items
        ]
    assert normalized.trace.answer.content == legacy.answer
    assert not normalized.trace.raw_retrieval.proves_prefix(1)


def test_wire_v1_capability_contradiction_is_preserved_as_corruption() -> None:
    normalized = normalize_rag_result_v1(
        RAGResult(answer="unexpected", ranked_retrieval=[]),
        case_id="case-legacy",
        source_identity=_source(),
        runtime_profile=_runtime_profile(),
        legacy_capabilities=AdapterCapabilities(),
        adapter_id="legacy-adapter",
        adapter_version="1.0",
    )

    assert normalized.trace.answer.observation_status == "corrupted"
    assert normalized.trace.answer.content == "unexpected"
    assert normalized.trace.ranked_retrieval.observation_status == "corrupted"
    assert normalized.trace.ranked_retrieval.diagnostics["returned_item_count"] == 0


def test_v2_observation_contract_is_gold_and_rag_implementation_neutral() -> None:
    contracts_root = Path(__file__).resolve().parents[2] / "src/rag_eval/contracts"
    for filename in ("observation.py", "observation_compat.py"):
        path = contracts_root / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        assert not any(
            value.startswith(
                (
                    "rag_eval.contracts.benchmark",
                    "rag_eval_lightrag_adapter",
                    "rag_eval_rag_anything_adapter",
                )
            )
            for value in imported
        )
        assert "GoldEvidence" not in path.read_text(encoding="utf-8")


def test_wire_v2_public_schemas_are_exported_without_redefining_wire_v1() -> None:
    assert PUBLIC_MODELS["unified-trace-v2"] is UnifiedTrace
    assert PUBLIC_MODELS["adapter-run-result-v2"] is AdapterRunResultV2
    assert RAGResult.model_fields["segment_traces"]

    schema_root = Path(__file__).resolve().parents[2] / "schemas" / "1.2"
    for name in (
        "adapter-capabilities-v2",
        "unified-trace-v2",
        "adapter-run-result-v2",
    ):
        expected = PUBLIC_MODELS[name].model_json_schema()
        observed = json.loads(
            (schema_root / f"{name}.schema.json").read_text(encoding="utf-8")
        )
        assert observed == expected
