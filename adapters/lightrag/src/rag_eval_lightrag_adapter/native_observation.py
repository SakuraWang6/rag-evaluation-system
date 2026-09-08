"""Translate one native LightRAG run into the RAG-neutral Wire 2.0 trace.

The translator is deliberately downstream of LightRAG.  It consumes the
authoritative persisted chunk store, the native DOCX lineage map, and the
single response returned by LightRAG's evaluation trace.  It never reads Gold,
changes a query, creates a second retrieval request, or rewrites stage items.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from rag_eval.contracts.adapter import RAGEvidenceItem
from rag_eval.contracts.canonical import SourceSpan, canonical_json
from rag_eval.contracts.observation import (
    AdapterCapabilitiesV2,
    AdapterRunResultV2,
    CanonicalExtent,
    CanonicalMappingRecord,
    ContentObservation,
    ExtentUnit,
    IngestionCatalogObservation,
    MappingDiagnostic,
    MappingDiagnosticStatus,
    MappingTier,
    NativeLineage,
    NativeSpan,
    ObservationCompleteness,
    ObservationProfileIdentity,
    ObservationStatus,
    ObservedStageItem,
    PhysicalCellFootprint,
    ProvenanceCoverageStatus,
    ProvenanceEdge,
    ReceiptStatus,
    ReverseMappingStatus,
    RuntimeChunkRecord,
    RuntimeProfileIdentity,
    SourceIdentity,
    StageName,
    StageObservation,
    StageTransitionDeclaration,
    StageTransitionMode,
    UnifiedTrace,
    ValidationReceipt,
)

from rag_eval_lightrag_adapter.canonical_provenance import (
    NativeDocxCanonicalObject,
    NativeDocxDocumentMap,
    normalize_source_span,
    sha256_text,
)

ADAPTER_ID = "lightrag"
SOURCE_COORDINATE_SYSTEM = "ooxml-structural-v1"
RUNTIME_COORDINATE_SYSTEM = "lightrag-rendered-stream-v1"


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _normalized_witness_digest(value: Any) -> str:
    text = " ".join(unicodedata.normalize("NFKC", str(value or "")).split())
    return sha256_text(text)


def _scalar_coordinates(
    value: Mapping[str, Any],
) -> dict[str, str | int | float | bool]:
    result: dict[str, str | int | float | bool] = {}
    for key, item in value.items():
        if key in {"part", "coordinate_system"} or item is None:
            continue
        if isinstance(item, (str, int, float, bool)):
            result[str(key)] = item
        else:
            # Nested table paths are not Gold-eligible in the current
            # Canonical Conformance policy, but retain their exact shape as a
            # deterministic diagnostic coordinate rather than dropping it.
            result[f"{key}_json"] = canonical_json(item)
    return result


def _record_value(item: NativeDocxCanonicalObject, key: str) -> Any:
    if key in item.raw_record:
        return item.raw_record[key]
    attributes = item.raw_record.get("attributes")
    if isinstance(attributes, dict):
        return attributes.get(key)
    return None


def _source_span(item: NativeDocxCanonicalObject) -> SourceSpan:
    locator = dict(item.locator)
    provenance = item.raw_record.get("provenance")
    raw_span: Mapping[str, Any] | None = None
    if isinstance(provenance, dict):
        spans = provenance.get("source_spans")
        if isinstance(spans, list) and spans and isinstance(spans[0], dict):
            raw_span = spans[0]
    part = str(
        locator.pop("part", None) or (raw_span or {}).get("part") or "word/document.xml"
    )
    coordinates = _scalar_coordinates(locator)
    if not coordinates:
        coordinates = {"object_id": item.object_id}
    text_start = (raw_span or {}).get("text_start")
    text_end = (raw_span or {}).get("text_end")
    if not (
        isinstance(text_start, int)
        and not isinstance(text_start, bool)
        and isinstance(text_end, int)
        and not isinstance(text_end, bool)
        and 0 <= text_start < text_end
    ):
        text_start = None
        text_end = None
    return SourceSpan(
        part=part,
        coordinates=coordinates,
        text_start=text_start,
        text_end=text_end,
    )


def _physical_objects_by_table(
    document: NativeDocxDocumentMap,
) -> dict[str, tuple[NativeDocxCanonicalObject, ...]]:
    values: dict[str, list[NativeDocxCanonicalObject]] = {}
    for item in document.objects:
        if item.object_type not in {"cell", "table_cell"}:
            continue
        table_id = _record_value(item, "table_id") or item.locator.get("table_id")
        if isinstance(table_id, str) and table_id:
            values.setdefault(table_id, []).append(item)
    return {
        key: tuple(sorted(items, key=lambda item: item.object_id))
        for key, items in values.items()
    }


def _physical_ids_for_object(
    item: NativeDocxCanonicalObject,
    physical_by_table: Mapping[str, tuple[NativeDocxCanonicalObject, ...]],
) -> tuple[str, ...]:
    if item.object_type in {"cell", "table_cell"}:
        return (item.object_id,)
    if item.object_type == "logical_cell":
        raw = _record_value(item, "derived_from_object_ids")
        if isinstance(raw, (list, tuple)) and all(
            isinstance(value, str) and value for value in raw
        ):
            return tuple(sorted(set(raw)))
        return tuple(
            child.object_id
            for children in physical_by_table.values()
            for child in children
            if _record_value(child, "logical_cell_id") == item.object_id
        )
    if item.object_type == "table":
        table_id = _record_value(item, "table_id") or item.object_id
        return tuple(
            child.object_id for child in physical_by_table.get(str(table_id), ())
        )
    return ()


def _physical_unit(item: NativeDocxCanonicalObject) -> ExtentUnit:
    coordinates = _scalar_coordinates(item.locator)
    coordinates.setdefault("object_id", item.object_id)
    return ExtentUnit(
        unit_id=item.object_id,
        coordinate_system="ooxml-physical-cell-v1",
        coordinates=coordinates,
    )


def _object_extent(
    item: NativeDocxCanonicalObject,
    *,
    objects_by_id: Mapping[str, NativeDocxCanonicalObject],
    physical_by_table: Mapping[str, tuple[NativeDocxCanonicalObject, ...]],
) -> CanonicalExtent:
    physical_ids = _physical_ids_for_object(item, physical_by_table)
    physical = tuple(
        _physical_unit(objects_by_id[object_id])
        for object_id in physical_ids
        if object_id in objects_by_id
    )
    if physical:
        return CanonicalExtent.build(extent_kind="physical_cell_union", units=physical)
    locator = _source_span(item)
    unit = ExtentUnit(
        unit_id=item.object_id,
        coordinate_system=locator.coordinate_system,
        start=locator.text_start,
        end=locator.text_end,
        coordinates={
            "part": locator.part,
            **locator.coordinates,
        },
    )
    return CanonicalExtent.build(extent_kind="canonical_object", units=(unit,))


def _physical_footprint(item: NativeDocxCanonicalObject) -> PhysicalCellFootprint:
    table_id = _record_value(item, "table_id") or item.locator.get("table_id")
    row = _record_value(item, "row")
    column = _record_value(item, "column")
    grid_span = _record_value(item, "grid_span") or 1
    v_merge = str(_record_value(item, "v_merge") or "none")
    origin = _record_value(item, "merged_cell_origin_physical_id")
    merge_origin = (
        str(origin)
        if v_merge in {"restart", "continue"} and isinstance(origin, str) and origin
        else None
    )
    return PhysicalCellFootprint(
        physical_cell_id=item.object_id,
        table_id=str(table_id),
        row=int(row),
        column=int(column),
        grid_span=int(grid_span),
        v_merge=v_merge,  # type: ignore[arg-type]
        merge_origin_physical_cell_id=merge_origin,
    )


def _native_lineage(record: Mapping[str, Any]) -> NativeLineage | None:
    raw = record.get("lineage")
    if not isinstance(raw, dict):
        return None
    schema_version = raw.get("schema_version")
    source_sha256 = raw.get("source_sha256")
    if not (
        isinstance(schema_version, str)
        and schema_version
        and isinstance(source_sha256, str)
        and len(source_sha256) == 64
    ):
        return None
    payload = {
        key: value
        for key, value in raw.items()
        if key not in {"schema_version", "source_sha256"}
    }
    return NativeLineage.build(
        schema_version=schema_version,
        source_sha256=source_sha256,
        payload=payload,
    )


def _runtime_span(record: Mapping[str, Any]) -> NativeSpan | None:
    span = normalize_source_span(record.get("source_span"))
    if span is None:
        lineage = record.get("lineage")
        span = normalize_source_span(
            lineage.get("source_span") if isinstance(lineage, dict) else None
        )
    if span is None:
        return None
    return NativeSpan(
        schema_version="lightrag-source-span/1",
        coordinate_system=RUNTIME_COORDINATE_SYSTEM,
        coordinates={"start": span[0], "end": span[1]},
    )


def _runtime_capabilities(runtime_config: Mapping[str, Any]) -> AdapterCapabilitiesV2:
    candidate_transition = StageTransitionMode.IDENTITY_SUBSET
    if (
        runtime_config.get("ranking_strategy") != "none"
        or runtime_config.get("exact_id_types")
        or runtime_config.get("enable_rerank")
    ):
        # Structured explicit-ID injection and third-party rerankers are
        # valid LightRAG behavior, but the current raw hook cannot prove their
        # complete derivation.  The stages remain observed while this
        # transition is explicitly unobservable.
        candidate_transition = StageTransitionMode.UNOBSERVABLE
    return AdapterCapabilitiesV2(
        ingestion_catalog=True,
        candidate_retrieval=True,
        ranked_retrieval=True,
        final_context=True,
        prompt_trace=True,
        answer=True,
        provenance=True,
        transformation_lineage=False,
        latency_breakdown=True,
        token_usage=False,
        transitions=(
            StageTransitionDeclaration(
                source_stage=StageName.CANDIDATE,
                target_stage=StageName.RANKED,
                mode=candidate_transition,
            ),
            StageTransitionDeclaration(
                source_stage=StageName.RANKED,
                target_stage=StageName.CONTEXT,
                mode=StageTransitionMode.IDENTITY_SUBSET,
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class NativeObservationSnapshot:
    source_identity: SourceIdentity
    runtime_profile: RuntimeProfileIdentity
    observation_profile: ObservationProfileIdentity
    ingestion_catalog: IngestionCatalogObservation
    provenance_edges: tuple[ProvenanceEdge, ...]
    canonical_mapping_records: tuple[CanonicalMappingRecord, ...]
    mapping_diagnostics: tuple[MappingDiagnostic, ...]
    validation_receipts: tuple[ValidationReceipt, ...]
    runtime_chunks: dict[str, RuntimeChunkRecord]
    legacy_mappings: dict[str, dict[str, Any]]
    provenance_edge_ids_by_chunk: dict[str, tuple[str, ...]]
    candidate_completeness: ObservationCompleteness


def _validation_receipt(
    *, receipt_kind: str, subject_id: str, details: dict[str, Any]
) -> ValidationReceipt:
    payload = {
        "receipt_kind": receipt_kind,
        "status": ReceiptStatus.VERIFIED.value,
        "subject_id": subject_id,
        "details": details,
    }
    return ValidationReceipt(
        receipt_kind=receipt_kind,
        status=ReceiptStatus.VERIFIED,
        subject_id=subject_id,
        receipt_sha256=_digest(payload),
        details=details,
    )


def _mapping_status(reason: str) -> MappingDiagnosticStatus:
    if any(
        marker in reason
        for marker in (
            "mismatch",
            "malformed",
            "ambiguous",
            "out_of_bounds",
            "duplicate",
            "digest",
        )
    ):
        return MappingDiagnosticStatus.CORRUPTED
    if "unsupported" in reason:
        return MappingDiagnosticStatus.UNSUPPORTED
    return MappingDiagnosticStatus.MISSING


def _edge(
    *,
    chunk_id: str,
    item: NativeDocxCanonicalObject,
    expected_extent: CanonicalExtent,
    covered_extent: CanonicalExtent,
    mapping_tier: MappingTier,
    runtime_chunk: RuntimeChunkRecord,
    coverage_status: ProvenanceCoverageStatus,
    reason_code: str,
    physical_footprint: tuple[PhysicalCellFootprint, ...] = (),
) -> ProvenanceEdge:
    canonical_value_sha256 = item.witness_sha256 or _normalized_witness_digest(
        item.canonical_value
    )
    return ProvenanceEdge.build(
        native_chunk_id=chunk_id,
        canonical_object_id=item.object_id,
        canonical_locator=_source_span(item),
        mapping_tier=mapping_tier,
        coverage_status=coverage_status,
        expected_extent=expected_extent,
        covered_extent=covered_extent,
        source_sha256=item.source_sha256,
        native_content_sha256=runtime_chunk.content_sha256,
        native_lineage_sha256=(
            runtime_chunk.native_lineage.lineage_sha256
            if runtime_chunk.native_lineage is not None
            else None
        ),
        canonical_value_sha256=canonical_value_sha256,
        reason_code=reason_code,
        physical_cell_footprint=physical_footprint,
    )


def build_native_observation_snapshot(
    *,
    document: NativeDocxDocumentMap,
    stored_chunks: Mapping[str, Mapping[str, Any]],
    provenance_manifest: Mapping[str, Any],
    runtime_config: Mapping[str, Any],
    system_version: str,
    adapter_version: str,
) -> NativeObservationSnapshot:
    """Freeze run-level native catalog/provenance independently of a query."""

    if provenance_manifest.get("map_kind") != "native-docx-runtime-provenance":
        raise ValueError("Wire 2.0 native observation requires a native DOCX map")
    if not document.source_sha256 or len(document.source_sha256) != 64:
        raise ValueError("native DOCX source identity is missing")
    if not stored_chunks:
        raise ValueError("native DOCX ingestion catalog is empty")

    raw_mappings = provenance_manifest.get("runtime_chunks")
    if not isinstance(raw_mappings, dict):
        raise TypeError("native DOCX provenance manifest lacks runtime chunks")
    mappings = {
        chunk_id: dict(mapping)
        for chunk_id, mapping in raw_mappings.items()
        if isinstance(chunk_id, str)
        and isinstance(mapping, dict)
        and mapping.get("document_id") == document.document_id
    }
    if set(mappings) != set(stored_chunks):
        raise ValueError("native DOCX runtime catalog is not document-complete")

    runtime_chunks: dict[str, RuntimeChunkRecord] = {}
    for chunk_id in sorted(stored_chunks):
        raw = stored_chunks[chunk_id]
        content = raw.get("content")
        if not isinstance(content, str):
            raise TypeError(f"runtime chunk {chunk_id!r} lacks exact content")
        mapping = mappings[chunk_id]
        content_sha256 = sha256_text(content)
        if mapping.get("content_sha256") != content_sha256:
            raise ValueError(
                f"runtime chunk {chunk_id!r} content identity differs from provenance map"
            )
        raw_lineage = raw.get("lineage")
        expected_legacy_lineage = mapping.get("lineage_sha256")
        if expected_legacy_lineage is not None:
            if not isinstance(raw_lineage, dict):
                raise ValueError(
                    f"runtime chunk {chunk_id!r} lost its persisted native lineage"
                )
            observed_legacy_lineage = hashlib.sha256(
                json.dumps(
                    raw_lineage,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            if observed_legacy_lineage != expected_legacy_lineage:
                raise ValueError(
                    f"runtime chunk {chunk_id!r} lineage identity differs from provenance map"
                )
        native_document_id = raw.get("full_doc_id") or mapping.get("native_document_id")
        if not isinstance(native_document_id, str) or not native_document_id:
            raise ValueError(
                f"runtime chunk {chunk_id!r} lacks LightRAG document identity"
            )
        lineage = _native_lineage(raw)
        runtime_chunks[chunk_id] = RuntimeChunkRecord(
            native_document_id=native_document_id,
            native_chunk_id=chunk_id,
            content_sha256=content_sha256,
            content=content,
            native_span=_runtime_span(raw),
            native_lineage=lineage,
            parser_identity=(
                f"lightrag-native-docx-parser/{lineage.schema_version}"
                if lineage is not None
                else "lightrag-native-parser/unobserved"
            ),
            chunker_identity=(
                "lightrag-native-chunker/"
                f"{canonical_json(runtime_config.get('chunking') or {})}"
            ),
            persisted_metadata_digest=_digest(
                {key: value for key, value in raw.items() if key != "content"}
            ),
        )

    source_identity = SourceIdentity(
        document_id=document.document_id,
        source_sha256=document.source_sha256,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        source_coordinate_schema=SOURCE_COORDINATE_SYSTEM,
        canonical_catalog_sha256=document.canonical_sidecar_sha256,
    )
    config_digest = _digest(
        {"runtime_config": dict(runtime_config), "system_version": system_version}
    )
    runtime_profile = RuntimeProfileIdentity(
        profile_id=(
            f"lightrag:{runtime_config.get('query_mode', 'naive')}:"
            f"{runtime_config.get('profile', 'legacy')}:native-docx"
        ),
        system_id=ADAPTER_ID,
        system_version=system_version,
        configuration_digest=config_digest,
    )
    capabilities = _runtime_capabilities(runtime_config)
    candidate_completeness = (
        ObservationCompleteness.PARTIAL
        if capabilities.transition(StageName.CANDIDATE, StageName.RANKED).mode
        == StageTransitionMode.UNOBSERVABLE
        and (
            runtime_config.get("ranking_strategy") != "none"
            or runtime_config.get("exact_id_types")
        )
        else ObservationCompleteness.COMPLETE
    )
    observation_profile = ObservationProfileIdentity.build(
        profile_id="lightrag-native-docx-observation/2.0",
        adapter_id=ADAPTER_ID,
        adapter_version=adapter_version,
        capabilities=capabilities,
    )

    objects_by_id = {item.object_id: item for item in document.objects}
    physical_by_table = _physical_objects_by_table(document)
    extents = {
        item.object_id: _object_extent(
            item,
            objects_by_id=objects_by_id,
            physical_by_table=physical_by_table,
        )
        for item in document.objects
    }
    edges: dict[tuple[str, str], ProvenanceEdge] = {}
    diagnostics: list[MappingDiagnostic] = []

    # Direct native-lineage edges are already verified by the ingestion map's
    # source/content/locator/witness checks.  Table and logical-cell coverage
    # is reconstructed below from verified physical-cell atoms so row splits
    # can be represented as positive partial extents.
    for chunk_id, mapping in sorted(mappings.items()):
        runtime_chunk = runtime_chunks[chunk_id]
        for raw_edge in mapping.get("canonical_objects") or []:
            if not isinstance(raw_edge, dict):
                continue
            object_id = raw_edge.get("object_id")
            item = objects_by_id.get(str(object_id))
            if item is None or item.object_type in {"table", "logical_cell"}:
                continue
            if runtime_chunk.native_lineage is None:
                diagnostics.append(
                    MappingDiagnostic(
                        native_chunk_id=chunk_id,
                        canonical_object_id=item.object_id,
                        status=MappingDiagnosticStatus.MISSING,
                        mapping_tier_attempted=MappingTier.NATIVE_LINEAGE,
                        reason_code="native_lineage_receipt_unavailable",
                    )
                )
                continue
            footprint: tuple[PhysicalCellFootprint, ...] = ()
            if item.object_type in {"cell", "table_cell"}:
                footprint = (_physical_footprint(item),)
            edge = _edge(
                chunk_id=chunk_id,
                item=item,
                expected_extent=extents[item.object_id],
                covered_extent=extents[item.object_id],
                mapping_tier=MappingTier.NATIVE_LINEAGE,
                runtime_chunk=runtime_chunk,
                coverage_status=ProvenanceCoverageStatus.COMPLETE,
                reason_code="lightrag_native_lineage_verified",
                physical_footprint=footprint,
            )
            edges[(chunk_id, item.object_id)] = edge

        mapping_reason = str(mapping.get("reason") or "")
        diagnostic_edges = [
            item
            for item in mapping.get("diagnostic_edges") or []
            if isinstance(item, dict)
        ]
        for diagnostic_edge in diagnostic_edges:
            reason = str(
                diagnostic_edge.get("reason")
                or mapping_reason
                or "native_lineage_extent_is_partial"
            )
            diagnostics.append(
                MappingDiagnostic(
                    native_chunk_id=chunk_id,
                    canonical_object_id=(
                        str(diagnostic_edge["object_id"])
                        if diagnostic_edge.get("object_id")
                        else None
                    ),
                    status=_mapping_status(reason),
                    mapping_tier_attempted=MappingTier.NATIVE_LINEAGE,
                    reason_code=reason,
                    diagnostics={
                        "provenance_status": mapping.get("provenance_status"),
                        "coverage": diagnostic_edge.get("coverage"),
                        "mapping_status": diagnostic_edge.get("mapping_status"),
                    },
                )
            )
        for field, reason, status in (
            (
                "witness_failures",
                "native_source_value_witness_mismatch",
                MappingDiagnosticStatus.CORRUPTED,
            ),
            (
                "ambiguous_objects",
                "ambiguous_native_structural_locator",
                MappingDiagnosticStatus.CORRUPTED,
            ),
            (
                "unmatched_objects",
                "native_lineage_object_not_in_canonical_catalog",
                MappingDiagnosticStatus.MISSING,
            ),
        ):
            for failure in mapping.get(field) or []:
                if not isinstance(failure, dict):
                    continue
                diagnostics.append(
                    MappingDiagnostic(
                        native_chunk_id=chunk_id,
                        canonical_object_id=(
                            str(failure["object_id"])
                            if failure.get("object_id")
                            else None
                        ),
                        status=status,
                        mapping_tier_attempted=MappingTier.NATIVE_LINEAGE,
                        reason_code=reason,
                        diagnostics=dict(failure),
                    )
                )
        if (
            mapping_reason
            and not mapping.get("canonical_objects")
            and not diagnostic_edges
        ):
            diagnostics.append(
                MappingDiagnostic(
                    native_chunk_id=chunk_id,
                    status=_mapping_status(mapping_reason),
                    mapping_tier_attempted=MappingTier.NATIVE_LINEAGE,
                    reason_code=mapping_reason,
                    diagnostics={"provenance_status": mapping.get("provenance_status")},
                )
            )

    # A verified authored paragraph also proves its deterministic canonical
    # text-span child.  This is structural crosswalk, never text search.
    direct_edges = tuple(edges.values())
    for item in document.objects:
        if item.object_type != "text_span" or item.representation_status != "complete":
            continue
        block_id = _record_value(item, "block_id")
        if not isinstance(block_id, str) or not block_id:
            continue
        for parent_edge in direct_edges:
            if parent_edge.canonical_object_id != block_id:
                continue
            chunk = runtime_chunks[parent_edge.native_chunk_id]
            edges[(parent_edge.native_chunk_id, item.object_id)] = _edge(
                chunk_id=parent_edge.native_chunk_id,
                item=item,
                expected_extent=extents[item.object_id],
                covered_extent=extents[item.object_id],
                mapping_tier=MappingTier.DETERMINISTIC_CROSSWALK,
                runtime_chunk=chunk,
                coverage_status=ProvenanceCoverageStatus.COMPLETE,
                reason_code="canonical_text_span_from_verified_parent",
            )

    # Project verified physical cells onto logical cells and whole tables.
    # The output edge contains only the cells present in this runtime chunk;
    # the reverse record below unions them across chunks.
    for item in document.objects:
        if (
            item.object_type not in {"logical_cell", "table"}
            or item.representation_status != "complete"
        ):
            continue
        expected_ids = set(_physical_ids_for_object(item, physical_by_table))
        if not expected_ids:
            continue
        expected_extent = extents[item.object_id]
        for chunk_id, runtime_chunk in runtime_chunks.items():
            covered_ids = sorted(
                object_id
                for native_id, object_id in edges
                if native_id == chunk_id and object_id in expected_ids
            )
            if not covered_ids:
                continue
            covered_units = tuple(
                _physical_unit(objects_by_id[object_id]) for object_id in covered_ids
            )
            covered_extent = CanonicalExtent.build(
                extent_kind="physical_cell_union", units=covered_units
            )
            complete = set(covered_ids) == expected_ids
            footprint = tuple(
                _physical_footprint(objects_by_id[object_id])
                for object_id in covered_ids
            )
            edges[(chunk_id, item.object_id)] = _edge(
                chunk_id=chunk_id,
                item=item,
                expected_extent=expected_extent,
                covered_extent=covered_extent,
                mapping_tier=MappingTier.DETERMINISTIC_CROSSWALK,
                runtime_chunk=runtime_chunk,
                coverage_status=(
                    ProvenanceCoverageStatus.COMPLETE
                    if complete
                    else ProvenanceCoverageStatus.PARTIAL
                ),
                reason_code="canonical_structure_from_verified_physical_cells",
                physical_footprint=footprint,
            )

    ordered_edges = tuple(
        sorted(
            edges.values(),
            key=lambda edge: (edge.native_chunk_id, edge.canonical_object_id),
        )
    )
    reverse_records: list[CanonicalMappingRecord] = []
    for item in sorted(document.objects, key=lambda value: value.object_id):
        item_edges = [
            edge for edge in ordered_edges if edge.canonical_object_id == item.object_id
        ]
        expected = extents[item.object_id]
        physical_ids = set(_physical_ids_for_object(item, physical_by_table))
        covered_ids = {
            unit.unit_id for edge in item_edges for unit in edge.covered_extent.units
        }
        proof_supported = not (
            item.object_type in {"table", "logical_cell", "cell", "table_cell"}
            and not physical_ids
        )
        if item.representation_status != "complete" or not proof_supported:
            status = ReverseMappingStatus.UNSUPPORTED
            native_ids: tuple[str, ...] = ()
        elif not item_edges:
            status = ReverseMappingStatus.MISSING
            native_ids = ()
        elif physical_ids and not physical_ids.issubset(covered_ids):
            status = ReverseMappingStatus.PARTIAL
            native_ids = tuple(sorted({edge.native_chunk_id for edge in item_edges}))
        else:
            status = ReverseMappingStatus.COMPLETE
            native_ids = tuple(sorted({edge.native_chunk_id for edge in item_edges}))
        reverse_records.append(
            CanonicalMappingRecord.build(
                canonical_object_id=item.object_id,
                expected_extent=expected,
                reverse_mapping_status=status,
                native_chunk_ids=native_ids,
            )
        )
        if status in {ReverseMappingStatus.MISSING, ReverseMappingStatus.UNSUPPORTED}:
            diagnostics.append(
                MappingDiagnostic(
                    canonical_object_id=item.object_id,
                    status=(
                        MappingDiagnosticStatus.UNSUPPORTED
                        if status == ReverseMappingStatus.UNSUPPORTED
                        else MappingDiagnosticStatus.MISSING
                    ),
                    reason_code=(
                        "canonical_extent_not_supported_by_native_profile"
                        if status == ReverseMappingStatus.UNSUPPORTED
                        else "canonical_extent_not_observed_in_runtime_catalog"
                    ),
                )
            )

    edge_ids_by_chunk = {
        chunk_id: tuple(
            edge.edge_id for edge in ordered_edges if edge.native_chunk_id == chunk_id
        )
        for chunk_id in runtime_chunks
    }
    ingestion_catalog = IngestionCatalogObservation(
        observation_status=ObservationStatus.OBSERVED,
        completeness=ObservationCompleteness.COMPLETE,
        items=tuple(runtime_chunks[key] for key in sorted(runtime_chunks)),
        diagnostics={
            "authoritative_store": "kv_store_text_chunks.json",
            "native_document_count": 1,
        },
    )
    receipts = (
        _validation_receipt(
            receipt_kind="source_catalog_pin",
            subject_id=document.document_id,
            details={
                "source_sha256": document.source_sha256,
                "canonical_catalog_sha256": document.canonical_sidecar_sha256,
            },
        ),
        _validation_receipt(
            receipt_kind="runtime_catalog_content_identity",
            subject_id=document.document_id,
            details={
                "runtime_chunk_count": len(runtime_chunks),
                "runtime_chunk_ids": sorted(runtime_chunks),
            },
        ),
        _validation_receipt(
            receipt_kind="native_provenance_round_trip",
            subject_id=document.document_id,
            details={
                "edge_count": len(ordered_edges),
                "canonical_record_count": len(reverse_records),
            },
        ),
    )
    return NativeObservationSnapshot(
        source_identity=source_identity,
        runtime_profile=runtime_profile,
        observation_profile=observation_profile,
        ingestion_catalog=ingestion_catalog,
        provenance_edges=ordered_edges,
        canonical_mapping_records=tuple(reverse_records),
        mapping_diagnostics=tuple(
            sorted(
                diagnostics,
                key=lambda item: (
                    item.native_chunk_id or "",
                    item.canonical_object_id or "",
                    item.reason_code,
                ),
            )
        ),
        validation_receipts=receipts,
        runtime_chunks=runtime_chunks,
        legacy_mappings=mappings,
        provenance_edge_ids_by_chunk=edge_ids_by_chunk,
        candidate_completeness=candidate_completeness,
    )


def _corrupted_stage(
    stage: StageName, *, reason: str, configured_cutoff: int
) -> StageObservation:
    return StageObservation(
        stage=stage,
        observation_status=ObservationStatus.CORRUPTED,
        completeness=ObservationCompleteness.UNKNOWN,
        configured_cutoff=configured_cutoff,
        items=(),
        reason=reason,
    )


def _stage_observation(
    *,
    snapshot: NativeObservationSnapshot,
    stage: StageName,
    raw_items: Any,
    configured_cutoff: int,
    completeness: ObservationCompleteness = ObservationCompleteness.COMPLETE,
) -> StageObservation:
    if not isinstance(raw_items, list):
        return _corrupted_stage(
            stage,
            reason=f"lightrag_{stage.value}_stage_is_not_a_list",
            configured_cutoff=configured_cutoff,
        )
    items: list[ObservedStageItem] = []
    seen: set[str] = set()
    for expected_rank, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            return _corrupted_stage(
                stage,
                reason=f"lightrag_{stage.value}_item_is_not_an_object",
                configured_cutoff=configured_cutoff,
            )
        native_id = raw.get("native_id")
        content = raw.get("content")
        rank = raw.get("rank")
        if not isinstance(native_id, str) or not native_id or native_id in seen:
            return _corrupted_stage(
                stage,
                reason=f"lightrag_{stage.value}_native_identity_invalid",
                configured_cutoff=configured_cutoff,
            )
        if rank != expected_rank:
            return _corrupted_stage(
                stage,
                reason=f"lightrag_{stage.value}_rank_prefix_invalid",
                configured_cutoff=configured_cutoff,
            )
        if not isinstance(content, str):
            return _corrupted_stage(
                stage,
                reason=f"lightrag_{stage.value}_content_missing",
                configured_cutoff=configured_cutoff,
            )
        runtime = snapshot.runtime_chunks.get(native_id)
        mapping = snapshot.legacy_mappings.get(native_id)
        if runtime is None or mapping is None:
            return _corrupted_stage(
                stage,
                reason=f"lightrag_{stage.value}_item_not_in_runtime_catalog",
                configured_cutoff=configured_cutoff,
            )
        if runtime.content_sha256 != sha256_text(content):
            return _corrupted_stage(
                stage,
                reason=f"lightrag_{stage.value}_content_hash_mismatch",
                configured_cutoff=configured_cutoff,
            )
        trace_span = normalize_source_span(raw.get("source_span"))
        mapping_span = normalize_source_span(mapping.get("source_span"))
        if trace_span != mapping_span:
            return _corrupted_stage(
                stage,
                reason=f"lightrag_{stage.value}_source_span_mismatch",
                configured_cutoff=configured_cutoff,
            )
        expected_lineage = mapping.get("lineage_sha256")
        if (
            expected_lineage is not None
            and raw.get("lineage_sha256") != expected_lineage
        ):
            return _corrupted_stage(
                stage,
                reason=f"lightrag_{stage.value}_lineage_digest_mismatch",
                configured_cutoff=configured_cutoff,
            )
        trace_source = raw.get("source_sha256")
        if (
            trace_source is not None
            and trace_source != snapshot.source_identity.source_sha256
        ):
            return _corrupted_stage(
                stage,
                reason=f"lightrag_{stage.value}_source_identity_mismatch",
                configured_cutoff=configured_cutoff,
            )
        trace_document = raw.get("document_id")
        accepted_documents = {
            runtime.native_document_id,
            snapshot.source_identity.document_id,
        }
        if trace_document is not None and trace_document not in accepted_documents:
            return _corrupted_stage(
                stage,
                reason=f"lightrag_{stage.value}_document_identity_mismatch",
                configured_cutoff=configured_cutoff,
            )
        score = raw.get("score")
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
        ):
            score = None
        items.append(
            ObservedStageItem(
                native_chunk_id=native_id,
                native_rank=expected_rank,
                runtime_score=float(score) if score is not None else None,
                content_sha256=runtime.content_sha256,
                content=content,
                provenance_edge_ids=snapshot.provenance_edge_ids_by_chunk.get(
                    native_id, ()
                ),
                metadata={
                    "native_item_id": raw.get("item_id"),
                    "file_path": raw.get("file_path"),
                    "source_type": raw.get("source_type"),
                    "lineage_sha256": raw.get("lineage_sha256"),
                    "output_coverage_proof": "provenance_edge_receipts",
                },
            )
        )
        seen.add(native_id)
    return StageObservation(
        stage=stage,
        observation_status=ObservationStatus.OBSERVED,
        completeness=completeness,
        configured_cutoff=configured_cutoff,
        items=tuple(items),
        diagnostics={
            "stage_boundary": (
                "configured_complete_output"
                if completeness == ObservationCompleteness.COMPLETE
                else "known_partial_output"
            ),
            "reported_item_count": len(items),
            "known_non_prefix_omission": (
                completeness == ObservationCompleteness.PARTIAL
            ),
        },
    )


def build_native_run_result_v2(
    *,
    snapshot: NativeObservationSnapshot,
    case_id: str,
    retrieval_stages: Mapping[str, Any],
    final_prompt: Any,
    answer: Any,
    candidate_cutoff: int,
    ranked_cutoff: int,
    context_cutoff: int,
    generate_answer: bool,
) -> AdapterRunResultV2:
    """Build Wire 2.0 from the already-returned LightRAG response."""

    raw = _stage_observation(
        snapshot=snapshot,
        stage=StageName.CANDIDATE,
        raw_items=retrieval_stages.get("raw_retrieval"),
        configured_cutoff=candidate_cutoff,
        completeness=snapshot.candidate_completeness,
    )
    ranked = _stage_observation(
        snapshot=snapshot,
        stage=StageName.RANKED,
        raw_items=retrieval_stages.get("ranked_retrieval"),
        configured_cutoff=ranked_cutoff,
    )
    context = _stage_observation(
        snapshot=snapshot,
        stage=StageName.CONTEXT,
        raw_items=retrieval_stages.get("final_context"),
        configured_cutoff=context_cutoff,
    )
    prompt = (
        ContentObservation.observed(final_prompt)
        if isinstance(final_prompt, str) and final_prompt.strip()
        else ContentObservation(
            observation_status=ObservationStatus.UNOBSERVED,
            completeness=ObservationCompleteness.UNKNOWN,
            reason="lightrag_trace_has_no_rendered_prompt",
        )
    )
    if generate_answer and isinstance(answer, str):
        answer_observation = ContentObservation.observed(answer)
    elif generate_answer:
        answer_observation = ContentObservation(
            observation_status=ObservationStatus.FAILED,
            completeness=ObservationCompleteness.UNKNOWN,
            reason="lightrag_answer_is_not_text",
        )
    else:
        answer_observation = ContentObservation(
            observation_status=ObservationStatus.UNOBSERVED,
            completeness=ObservationCompleteness.UNKNOWN,
            reason="answer_generation_was_disabled",
        )
    trace = UnifiedTrace.build(
        case_id=case_id,
        source_identity=snapshot.source_identity,
        runtime_profile=snapshot.runtime_profile,
        observation_profile=snapshot.observation_profile,
        ingestion_catalog=snapshot.ingestion_catalog,
        provenance_edges=snapshot.provenance_edges,
        canonical_mapping_records=snapshot.canonical_mapping_records,
        mapping_diagnostics=snapshot.mapping_diagnostics,
        raw_retrieval=raw,
        ranked_retrieval=ranked,
        final_context=context,
        transformations=(),
        prompt_trace=prompt,
        answer=answer_observation,
        validation_receipts=snapshot.validation_receipts,
    )
    return AdapterRunResultV2(
        adapter_id=snapshot.observation_profile.adapter_id,
        adapter_version=snapshot.observation_profile.adapter_version,
        system_id=snapshot.runtime_profile.system_id,
        system_version=snapshot.runtime_profile.system_version,
        trace=trace,
    )


def verify_wire_v1_shadow(
    result: AdapterRunResultV2,
    *,
    raw_retrieval: Iterable[RAGEvidenceItem] | None,
    ranked_retrieval: Iterable[RAGEvidenceItem] | None,
    final_context: Iterable[RAGEvidenceItem] | None,
) -> dict[str, Any]:
    """Prove that the additive v2 observer did not alter Wire 1.0 outputs."""

    pairs = (
        ("raw_retrieval", raw_retrieval, result.trace.raw_retrieval),
        ("ranked_retrieval", ranked_retrieval, result.trace.ranked_retrieval),
        ("final_context", final_context, result.trace.final_context),
    )
    compared: dict[str, int] = {}
    for name, legacy, observed in pairs:
        if observed.observation_status != ObservationStatus.OBSERVED:
            compared[name] = 0
            continue
        legacy_items = list(legacy or ())
        left = [
            (item.native_id, item.rank, item.content, item.score)
            for item in legacy_items
        ]
        right = [
            (
                item.native_chunk_id,
                item.native_rank,
                item.content,
                item.runtime_score,
            )
            for item in observed.items
        ]
        if left != right:
            raise ValueError(f"Wire 1.0/v2 shadow mismatch at {name}")
        compared[name] = len(right)
    return {
        "status": "verified",
        "comparison": "native_id+rank+content+score",
        "stage_item_counts": compared,
    }


__all__ = [
    "NativeObservationSnapshot",
    "build_native_observation_snapshot",
    "build_native_run_result_v2",
    "verify_wire_v1_shadow",
]
