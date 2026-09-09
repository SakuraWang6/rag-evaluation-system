"""Deterministic Wire 2 observation fixtures for the shared Adapter TCK."""

from __future__ import annotations

import hashlib

from rag_eval.contracts.canonical import SourceSpan
from rag_eval.contracts.observation import (
    AdapterCapabilitiesV2,
    AdapterRunResultV2,
    CanonicalExtent,
    CanonicalMappingRecord,
    ContentObservation,
    ExtentUnit,
    IngestionCatalogObservation,
    MappingTier,
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

SOURCE_SHA256 = "1" * 64
CATALOG_SHA256 = "2" * 64
CONFIG_SHA256 = "3" * 64
ADAPTER_ID = "tck-fixture-adapter"
ADAPTER_VERSION = "2.0"
SYSTEM_ID = "tck-fixture-rag"
SYSTEM_VERSION = "2.0"
CASE_ID = "tck-fixture-case"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source() -> SourceIdentity:
    return SourceIdentity(
        document_id="tck-document",
        source_sha256=SOURCE_SHA256,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        source_coordinate_schema="ooxml-structural-v1",
        canonical_catalog_sha256=CATALOG_SHA256,
    )


def _runtime_profile() -> RuntimeProfileIdentity:
    return RuntimeProfileIdentity(
        profile_id="tck-runtime-profile",
        system_id=SYSTEM_ID,
        system_version=SYSTEM_VERSION,
        configuration_digest=CONFIG_SHA256,
    )


def _profile(capabilities: AdapterCapabilitiesV2) -> ObservationProfileIdentity:
    return ObservationProfileIdentity.build(
        profile_id="tck-observation-profile",
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        capabilities=capabilities,
    )


def _chunk(native_chunk_id: str, content: str) -> RuntimeChunkRecord:
    lineage = NativeLineage.build(
        schema_version="tck-native-lineage/1",
        source_sha256=SOURCE_SHA256,
        payload={"native_chunk_id": native_chunk_id},
    )
    return RuntimeChunkRecord(
        native_document_id="tck-native-document",
        native_chunk_id=native_chunk_id,
        content_sha256=_sha256(content),
        content=content,
        native_lineage=lineage,
        parser_identity="tck-parser/1",
        chunker_identity="tck-chunker/1",
        persisted_metadata_digest=_sha256(f"metadata:{native_chunk_id}"),
    )


def _item(
    chunk: RuntimeChunkRecord,
    rank: int,
    *,
    provenance_edge_ids: tuple[str, ...] = (),
) -> ObservedStageItem:
    return ObservedStageItem(
        native_chunk_id=chunk.native_chunk_id,
        native_rank=rank,
        content_sha256=chunk.content_sha256,
        content=chunk.content,
        provenance_edge_ids=provenance_edge_ids,
    )


def _stage(
    stage: StageName,
    items: tuple[ObservedStageItem, ...],
    *,
    completeness: ObservationCompleteness,
    configured_cutoff: int,
) -> StageObservation:
    return StageObservation(
        stage=stage,
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


def _unsupported_prompt() -> ContentObservation:
    return ContentObservation(
        observation_status=ObservationStatus.UNSUPPORTED,
        completeness=ObservationCompleteness.UNKNOWN,
        reason="fixture Adapter does not expose prompts",
    )


def _unobserved_stage(stage: StageName, reason: str) -> StageObservation:
    return StageObservation(
        stage=stage,
        observation_status=ObservationStatus.UNOBSERVED,
        completeness=ObservationCompleteness.UNKNOWN,
        items=(),
        reason=reason,
    )


def _result(trace: UnifiedTrace) -> AdapterRunResultV2:
    return AdapterRunResultV2(
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        system_id=SYSTEM_ID,
        system_version=SYSTEM_VERSION,
        trace=trace,
        telemetry={"native_query_executions": 1},
    )


def derived_context_result(
    *,
    include_output_coverage_proof: bool = True,
) -> AdapterRunResultV2:
    """A valid merge derivation whose output identity is not in the catalog."""

    chunk_a = _chunk("runtime-a", "alpha")
    chunk_b = _chunk("runtime-b", "beta")
    derived = _chunk("context-merged", "alpha\nbeta")
    ranked_items = (_item(chunk_a, 1), _item(chunk_b, 2))
    transformation = TransformationRecord.build(
        source_stage=StageName.RANKED,
        target_stage=StageName.CONTEXT,
        source_item_references=tuple(
            StageItemReference(
                stage=StageName.RANKED,
                native_chunk_id=item.native_chunk_id,
                content_sha256=item.content_sha256,
            )
            for item in ranked_items
        ),
        transformation_kind="merge",
        output_native_chunk_id=derived.native_chunk_id,
        output_content_sha256=derived.content_sha256,
        lineage_integrity_status="verified",
    )
    extent = CanonicalExtent.build(
        extent_kind="text_span",
        units=(
            ExtentUnit(
                unit_id="paragraph-1",
                coordinate_system="canonical-text-offset-v1",
                start=0,
                end=10,
            ),
        ),
    )
    edge = ProvenanceEdge.build(
        native_chunk_id=derived.native_chunk_id,
        canonical_object_id="paragraph-1",
        canonical_locator=SourceSpan(
            part="word/document.xml",
            coordinates={"body_ordinal": 1},
            text_start=0,
            text_end=10,
        ),
        mapping_tier=MappingTier.NATIVE_LINEAGE,
        coverage_status=ProvenanceCoverageStatus.COMPLETE,
        expected_extent=extent,
        covered_extent=extent,
        source_sha256=SOURCE_SHA256,
        native_content_sha256=derived.content_sha256,
        native_lineage_sha256=transformation.transformation_receipt_sha256,
        canonical_value_sha256=_sha256("alpha\nbeta"),
        reason_code="verified_derived_output",
    )
    edges = (edge,) if include_output_coverage_proof else ()
    mappings = (
        CanonicalMappingRecord.build(
            canonical_object_id="paragraph-1",
            expected_extent=extent,
            reverse_mapping_status=ReverseMappingStatus.COMPLETE,
            native_chunk_ids=(derived.native_chunk_id,),
        ),
    ) if include_output_coverage_proof else ()
    context_item = _item(
        derived,
        1,
        provenance_edge_ids=(edge.edge_id,) if include_output_coverage_proof else (),
    )
    capabilities = AdapterCapabilitiesV2(
        ingestion_catalog=True,
        candidate_retrieval=True,
        ranked_retrieval=True,
        final_context=True,
        prompt_trace=False,
        answer=True,
        provenance=True,
        transformation_lineage=True,
        transitions=(
            StageTransitionDeclaration(
                source_stage=StageName.CANDIDATE,
                target_stage=StageName.RANKED,
                mode=StageTransitionMode.IDENTITY_SUBSET,
            ),
            StageTransitionDeclaration(
                source_stage=StageName.RANKED,
                target_stage=StageName.CONTEXT,
                mode=StageTransitionMode.VERIFIED_DERIVATION,
            ),
        ),
    )
    trace = UnifiedTrace.build(
        case_id=CASE_ID,
        source_identity=_source(),
        runtime_profile=_runtime_profile(),
        observation_profile=_profile(capabilities),
        ingestion_catalog=IngestionCatalogObservation(
            observation_status=ObservationStatus.OBSERVED,
            completeness=ObservationCompleteness.COMPLETE,
            items=(chunk_a, chunk_b),
        ),
        provenance_edges=edges,
        canonical_mapping_records=mappings,
        mapping_diagnostics=(),
        raw_retrieval=_stage(
            StageName.CANDIDATE,
            ranked_items,
            completeness=ObservationCompleteness.COMPLETE,
            configured_cutoff=5,
        ),
        ranked_retrieval=_stage(
            StageName.RANKED,
            ranked_items,
            completeness=ObservationCompleteness.TRUNCATED,
            configured_cutoff=5,
        ),
        final_context=_stage(
            StageName.CONTEXT,
            (context_item,),
            completeness=ObservationCompleteness.COMPLETE,
            configured_cutoff=1,
        ),
        transformations=(transformation,),
        prompt_trace=_unsupported_prompt(),
        answer=ContentObservation.observed("fixture answer"),
        validation_receipts=(),
    )
    return _result(trace)


def partial_stage_result() -> AdapterRunResultV2:
    """A valid observation with known non-prefix omissions and rank gaps."""

    chunk_a = _chunk("runtime-a", "alpha")
    chunk_b = _chunk("runtime-b", "beta")
    capabilities = AdapterCapabilitiesV2(
        ingestion_catalog=True,
        candidate_retrieval=True,
        ranked_retrieval=True,
        final_context=True,
        prompt_trace=False,
        answer=True,
        provenance=False,
        transformation_lineage=False,
        transitions=(
            StageTransitionDeclaration(
                source_stage=StageName.CANDIDATE,
                target_stage=StageName.RANKED,
                mode=StageTransitionMode.IDENTITY_SUBSET,
            ),
            StageTransitionDeclaration(
                source_stage=StageName.RANKED,
                target_stage=StageName.CONTEXT,
                mode=StageTransitionMode.IDENTITY_SUBSET,
            ),
        ),
    )
    trace = UnifiedTrace.build(
        case_id=CASE_ID,
        source_identity=_source(),
        runtime_profile=_runtime_profile(),
        observation_profile=_profile(capabilities),
        ingestion_catalog=IngestionCatalogObservation(
            observation_status=ObservationStatus.OBSERVED,
            completeness=ObservationCompleteness.COMPLETE,
            items=(chunk_a, chunk_b),
        ),
        provenance_edges=(),
        canonical_mapping_records=(),
        mapping_diagnostics=(),
        raw_retrieval=_stage(
            StageName.CANDIDATE,
            (_item(chunk_a, 1), _item(chunk_b, 3)),
            completeness=ObservationCompleteness.PARTIAL,
            configured_cutoff=5,
        ),
        ranked_retrieval=_stage(
            StageName.RANKED,
            (_item(chunk_b, 2),),
            completeness=ObservationCompleteness.PARTIAL,
            configured_cutoff=5,
        ),
        final_context=_stage(
            StageName.CONTEXT,
            (_item(chunk_b, 4),),
            completeness=ObservationCompleteness.PARTIAL,
            configured_cutoff=5,
        ),
        transformations=(),
        prompt_trace=_unsupported_prompt(),
        answer=ContentObservation.observed("fixture answer"),
        validation_receipts=(),
    )
    return _result(trace)


def unobservable_transition_result() -> AdapterRunResultV2:
    """A supported runtime whose downstream stages were not observed."""

    chunk = _chunk("runtime-a", "alpha")
    capabilities = AdapterCapabilitiesV2(
        ingestion_catalog=True,
        candidate_retrieval=True,
        ranked_retrieval=True,
        final_context=True,
        prompt_trace=False,
        answer=True,
        provenance=False,
        transformation_lineage=False,
        transitions=(
            StageTransitionDeclaration(
                source_stage=StageName.CANDIDATE,
                target_stage=StageName.RANKED,
                mode=StageTransitionMode.UNOBSERVABLE,
            ),
            StageTransitionDeclaration(
                source_stage=StageName.RANKED,
                target_stage=StageName.CONTEXT,
                mode=StageTransitionMode.UNOBSERVABLE,
            ),
        ),
    )
    trace = UnifiedTrace.build(
        case_id=CASE_ID,
        source_identity=_source(),
        runtime_profile=_runtime_profile(),
        observation_profile=_profile(capabilities),
        ingestion_catalog=IngestionCatalogObservation(
            observation_status=ObservationStatus.OBSERVED,
            completeness=ObservationCompleteness.COMPLETE,
            items=(chunk,),
        ),
        provenance_edges=(),
        canonical_mapping_records=(),
        mapping_diagnostics=(),
        raw_retrieval=_stage(
            StageName.CANDIDATE,
            (_item(chunk, 1),),
            completeness=ObservationCompleteness.COMPLETE,
            configured_cutoff=5,
        ),
        ranked_retrieval=_unobserved_stage(
            StageName.RANKED,
            "ranking hook was not enabled for this query",
        ),
        final_context=_unobserved_stage(
            StageName.CONTEXT,
            "context hook was not enabled for this query",
        ),
        transformations=(),
        prompt_trace=_unsupported_prompt(),
        answer=ContentObservation.observed("fixture answer"),
        validation_receipts=(),
    )
    return _result(trace)


__all__ = [
    "ADAPTER_ID",
    "CASE_ID",
    "SYSTEM_ID",
    "derived_context_result",
    "partial_stage_result",
    "unobservable_transition_result",
]
