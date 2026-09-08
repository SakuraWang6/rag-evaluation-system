"""RAG-Anything native runtime observations translated to Wire 2.0.

The observer is deliberately downstream of the native parser, chunker, index,
and query.  It consumes a complete run-scoped storage snapshot plus facts
captured from the *same* query execution.  It never reads Gold, never submits a
second query, and never uses fuzzy or semantic text matching.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag_eval.contracts.adapter import DocumentInput
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

ADAPTER_ID = "rag-anything"
SOURCE_COORDINATE_SYSTEM = "ooxml-structural-v1"
PARSER_STREAM_COORDINATE_SYSTEM = "rag-anything-parser-stream-v1"
CANONICAL_WITNESS_COORDINATE_SYSTEM = "canonical-witness-text-v1"
SUPPORTED_EXACT_TEXT_OBJECT_TYPES = frozenset({"paragraph", "heading", "text_span"})


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _json_ready(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _json_ready(value.model_dump(mode="json", exclude_none=True))
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _digest(value: Any) -> str:
    return _sha256_text(canonical_json(_json_ready(value)))


@dataclass(frozen=True, slots=True)
class RuntimeIngestionCapture:
    """Exact run-scoped rows observed after native ingestion completes."""

    chunks: Mapping[str, Mapping[str, Any]]
    full_documents: Mapping[str, str]
    storage_identity: str


@dataclass(frozen=True, slots=True)
class RuntimeQueryCapture:
    """Facts captured while the normal RAG-Anything query executes once."""

    answer: str | None
    observation_status: ObservationStatus
    reason: str | None
    candidate_items: tuple[Mapping[str, Any], ...]
    query_result: Mapping[str, Any] | None
    candidate_cutoff: int | None
    query_parameters: Mapping[str, Any]

    @classmethod
    def observed(
        cls,
        *,
        answer: str | None,
        candidate_items: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        query_result: Mapping[str, Any],
        candidate_cutoff: int,
        query_parameters: Mapping[str, Any],
    ) -> RuntimeQueryCapture:
        return cls(
            answer=answer,
            observation_status=ObservationStatus.OBSERVED,
            reason=None,
            candidate_items=tuple(dict(item) for item in candidate_items),
            query_result=dict(query_result),
            candidate_cutoff=candidate_cutoff,
            query_parameters=dict(query_parameters),
        )

    @classmethod
    def unavailable(
        cls,
        *,
        answer: str | None,
        reason: str,
        status: ObservationStatus = ObservationStatus.UNOBSERVED,
        query_parameters: Mapping[str, Any] | None = None,
    ) -> RuntimeQueryCapture:
        if status == ObservationStatus.OBSERVED:
            raise ValueError("an unavailable runtime capture cannot be observed")
        return cls(
            answer=answer,
            observation_status=status,
            reason=reason,
            candidate_items=(),
            query_result=None,
            candidate_cutoff=None,
            query_parameters=dict(query_parameters or {}),
        )


@dataclass(frozen=True, slots=True)
class _CanonicalTextObject:
    object_id: str
    object_type: str
    representation_status: str
    witness: str | None
    locator: SourceSpan
    expected_extent: CanonicalExtent
    supported: bool


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
    runtime_chunks: Mapping[str, RuntimeChunkRecord]
    provenance_edge_ids_by_chunk: Mapping[str, tuple[str, ...]]


def _occurrences(value: str, needle: str) -> tuple[int, ...]:
    if not needle:
        return ()
    found: list[int] = []
    offset = 0
    while True:
        index = value.find(needle, offset)
        if index < 0:
            return tuple(found)
        found.append(index)
        offset = index + 1


def _source_span(record: Mapping[str, Any]) -> SourceSpan | None:
    provenance = record.get("provenance")
    if not isinstance(provenance, Mapping):
        return None
    spans = provenance.get("source_spans")
    if not isinstance(spans, list) or len(spans) != 1:
        return None
    try:
        return SourceSpan.model_validate(spans[0])
    except (TypeError, ValueError):
        return None


def _canonical_extent(
    object_id: str, locator: SourceSpan, witness: str | None
) -> CanonicalExtent:
    coordinates: dict[str, str | int | float | bool] = {
        "part": locator.part,
        **locator.coordinates,
    }
    unit = ExtentUnit(
        unit_id=object_id,
        coordinate_system=(
            CANONICAL_WITNESS_COORDINATE_SYSTEM
            if witness
            else locator.coordinate_system
        ),
        start=0 if witness else None,
        end=len(witness) if witness else None,
        coordinates=coordinates,
    )
    return CanonicalExtent.build(extent_kind="canonical_object", units=(unit,))


def _load_canonical_objects(
    *,
    document: DocumentInput,
    source_dir: Path,
) -> tuple[tuple[_CanonicalTextObject, ...], str, tuple[MappingDiagnostic, ...]]:
    raw_path = document.metadata.get("canonical_provenance_path")
    expected_digest = document.metadata.get("canonical_provenance_sha256")
    if not isinstance(raw_path, str) or Path(raw_path).name != raw_path:
        raise ValueError("canonical provenance path is not a safe staged filename")
    if not isinstance(expected_digest, str) or len(expected_digest) != 64:
        raise ValueError("canonical provenance digest is missing or malformed")
    path = source_dir / raw_path
    payload = path.read_bytes()
    if _sha256_bytes(payload) != expected_digest:
        raise ValueError("canonical provenance sidecar digest mismatch")

    records: list[Mapping[str, Any]] = []
    for line_number, line in enumerate(payload.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"canonical provenance line {line_number} is not valid JSON"
            ) from exc
        if not isinstance(record, Mapping):
            raise TypeError("canonical provenance records must be objects")
        records.append(record)
    if not records:
        raise ValueError("canonical provenance sidecar is empty")

    objects: list[_CanonicalTextObject] = []
    diagnostics: list[MappingDiagnostic] = []
    seen: set[str] = set()
    for record in records:
        object_id = record.get("object_id")
        if not isinstance(object_id, str) or not object_id:
            continue
        if object_id in seen:
            raise ValueError("canonical provenance repeats an object identity")
        seen.add(object_id)
        if record.get("document_id") != document.document_id:
            raise ValueError("canonical object uses a different document identity")
        provenance = record.get("provenance")
        source_sha256 = (
            provenance.get("source_sha256")
            if isinstance(provenance, Mapping)
            else None
        )
        if source_sha256 != document.sha256:
            raise ValueError("canonical object uses a different source identity")
        locator = _source_span(record)
        if locator is None:
            diagnostics.append(
                MappingDiagnostic(
                    canonical_object_id=object_id,
                    status=MappingDiagnosticStatus.CORRUPTED,
                    reason_code="canonical_object_has_no_unique_valid_source_span",
                )
            )
            continue
        witness_value = record.get("canonical_value")
        witness = witness_value if isinstance(witness_value, str) else None
        object_type = str(record.get("object_type") or record.get("record_type") or "")
        representation_status = str(
            record.get("representation_status") or record.get("status") or "missing"
        )
        supported = bool(
            representation_status == "complete"
            and witness
            and object_type in SUPPORTED_EXACT_TEXT_OBJECT_TYPES
        )
        expected_extent = _canonical_extent(object_id, locator, witness)
        objects.append(
            _CanonicalTextObject(
                object_id=object_id,
                object_type=object_type,
                representation_status=representation_status,
                witness=witness,
                locator=locator,
                expected_extent=expected_extent,
                supported=supported,
            )
        )
        if not supported:
            diagnostics.append(
                MappingDiagnostic(
                    canonical_object_id=object_id,
                    status=MappingDiagnosticStatus.UNSUPPORTED,
                    reason_code=(
                        "canonical_type_requires_structural_provenance"
                        if object_type not in SUPPORTED_EXACT_TEXT_OBJECT_TYPES
                        else "canonical_text_witness_is_not_complete"
                    ),
                    diagnostics={
                        "object_type": object_type,
                        "representation_status": representation_status,
                    },
                )
            )
    return tuple(objects), expected_digest, tuple(diagnostics)


def _native_lineage(
    *,
    document: DocumentInput,
    chunk_id: str,
    row: Mapping[str, Any],
    full_text: str | None,
) -> tuple[NativeLineage, NativeSpan | None, tuple[int, int] | None]:
    content = str(row["content"])
    positions = _occurrences(full_text, content) if full_text is not None else ()
    interval = (
        (positions[0], positions[0] + len(content)) if len(positions) == 1 else None
    )
    payload: dict[str, Any] = {
        "native_document_id": str(row["full_doc_id"]),
        "native_chunk_id": chunk_id,
        "chunk_order_index": row.get("chunk_order_index"),
        "file_path": row.get("file_path"),
        "content_sha256": _sha256_text(content),
        "parser_stream_sha256": _sha256_text(full_text) if full_text is not None else None,
        "parser_stream_interval": (
            {"start": interval[0], "end": interval[1]} if interval else None
        ),
        "parser_stream_match_count": len(positions),
    }
    lineage = NativeLineage.build(
        schema_version="rag-anything-runtime-chunk-lineage/1",
        source_sha256=str(document.sha256),
        payload=payload,
    )
    span = (
        NativeSpan(
            schema_version=PARSER_STREAM_COORDINATE_SYSTEM,
            coordinate_system=PARSER_STREAM_COORDINATE_SYSTEM,
            coordinates={"start": interval[0], "end": interval[1]},
        )
        if interval
        else None
    )
    return lineage, span, interval


def _runtime_chunks(
    *,
    document: DocumentInput,
    capture: RuntimeIngestionCapture,
    runtime_config: Mapping[str, Any],
    core_version: str,
) -> tuple[
    dict[str, RuntimeChunkRecord],
    dict[str, tuple[int, int] | None],
    tuple[MappingDiagnostic, ...],
]:
    if not capture.chunks:
        raise ValueError("RAG-Anything runtime ingestion catalog is empty")
    full_text = capture.full_documents.get(document.document_id)
    chunks: dict[str, RuntimeChunkRecord] = {}
    intervals: dict[str, tuple[int, int] | None] = {}
    diagnostics: list[MappingDiagnostic] = []
    for chunk_id in sorted(capture.chunks):
        row = capture.chunks[chunk_id]
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError("runtime catalog contains an invalid chunk identity")
        content = row.get("content")
        native_document_id = row.get("full_doc_id")
        if not isinstance(content, str):
            raise TypeError(f"runtime chunk {chunk_id!r} lacks exact content")
        if native_document_id != document.document_id:
            raise ValueError(
                f"runtime chunk {chunk_id!r} uses a different document identity"
            )
        lineage, span, interval = _native_lineage(
            document=document,
            chunk_id=chunk_id,
            row=row,
            full_text=full_text,
        )
        intervals[chunk_id] = interval
        if full_text is None:
            diagnostics.append(
                MappingDiagnostic(
                    native_chunk_id=chunk_id,
                    status=MappingDiagnosticStatus.MISSING,
                    mapping_tier_attempted=MappingTier.TEXT_UNIQUE_EXACT,
                    reason_code="native_parser_stream_is_unavailable",
                )
            )
        elif interval is None:
            diagnostics.append(
                MappingDiagnostic(
                    native_chunk_id=chunk_id,
                    status=MappingDiagnosticStatus.CORRUPTED,
                    mapping_tier_attempted=MappingTier.TEXT_UNIQUE_EXACT,
                    reason_code="runtime_chunk_is_not_unique_in_parser_stream",
                )
            )
        chunks[chunk_id] = RuntimeChunkRecord(
            native_document_id=native_document_id,
            native_chunk_id=chunk_id,
            content_sha256=_sha256_text(content),
            content=content,
            native_span=span,
            native_lineage=lineage,
            parser_identity=(
                "rag-anything-native-parser/"
                f"{runtime_config.get('parser', 'unknown')}:"
                f"{runtime_config.get('parse_method', 'unknown')}"
            ),
            chunker_identity=(
                f"lightrag-native-chunker/{core_version}:"
                f"{canonical_json(_json_ready(runtime_config.get('chunking') or {}))}"
            ),
            persisted_metadata_digest=_digest(
                {key: value for key, value in row.items() if key != "content"}
            ),
        )
    return chunks, intervals, tuple(diagnostics)


def _covered_extent(
    expected: CanonicalExtent, *, start: int, end: int
) -> CanonicalExtent:
    unit = expected.units[0]
    return CanonicalExtent.build(
        extent_kind=expected.extent_kind,
        units=(
            ExtentUnit(
                unit_id=unit.unit_id,
                coordinate_system=unit.coordinate_system,
                start=start,
                end=end,
                coordinates=unit.coordinates,
            ),
        ),
    )


def _intervals_cover(length: int, intervals: list[tuple[int, int]]) -> bool:
    cursor = 0
    for start, end in sorted(intervals):
        if start > cursor:
            return False
        cursor = max(cursor, end)
        if cursor >= length:
            return True
    return cursor >= length


def _validation_receipt(
    *, receipt_kind: str, subject_id: str, details: Mapping[str, Any]
) -> ValidationReceipt:
    normalized = dict(details)
    payload = {
        "receipt_kind": receipt_kind,
        "status": ReceiptStatus.VERIFIED.value,
        "subject_id": subject_id,
        "details": normalized,
    }
    return ValidationReceipt(
        receipt_kind=receipt_kind,
        status=ReceiptStatus.VERIFIED,
        subject_id=subject_id,
        receipt_sha256=_digest(payload),
        details=normalized,
    )


def _capabilities() -> AdapterCapabilitiesV2:
    return AdapterCapabilitiesV2(
        ingestion_catalog=True,
        candidate_retrieval=True,
        ranked_retrieval=True,
        final_context=True,
        prompt_trace=False,
        answer=True,
        provenance=True,
        transformation_lineage=False,
        latency_breakdown=True,
        token_usage=False,
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


def build_native_observation_snapshot(
    *,
    document: DocumentInput,
    source_dir: Path,
    capture: RuntimeIngestionCapture,
    runtime_config: Mapping[str, Any],
    system_version: str,
    core_version: str,
    adapter_version: str,
) -> NativeObservationSnapshot:
    """Build the immutable catalog/crosswalk without consulting Benchmark Gold."""

    if document.sha256 is None or len(document.sha256) != 64:
        raise ValueError("native DOCX source identity is missing")
    objects, catalog_sha256, catalog_diagnostics = _load_canonical_objects(
        document=document,
        source_dir=source_dir,
    )
    runtime_chunks, chunk_intervals, runtime_diagnostics = _runtime_chunks(
        document=document,
        capture=capture,
        runtime_config=runtime_config,
        core_version=core_version,
    )
    full_text = capture.full_documents.get(document.document_id)
    edges: list[ProvenanceEdge] = []
    mappings: list[CanonicalMappingRecord] = []
    diagnostics = [*catalog_diagnostics, *runtime_diagnostics]

    for item in sorted(objects, key=lambda value: value.object_id):
        item_edges: list[ProvenanceEdge] = []
        if item.supported and item.witness is not None and full_text is not None:
            positions = _occurrences(full_text, item.witness)
            if len(positions) > 1:
                diagnostics.append(
                    MappingDiagnostic(
                        canonical_object_id=item.object_id,
                        status=MappingDiagnosticStatus.CORRUPTED,
                        mapping_tier_attempted=MappingTier.TEXT_UNIQUE_EXACT,
                        reason_code="ambiguous_exact_witness_in_parser_stream",
                        diagnostics={"match_count": len(positions)},
                    )
                )
            elif len(positions) == 1:
                object_start = positions[0]
                object_end = object_start + len(item.witness)
                for chunk_id, chunk_interval in sorted(chunk_intervals.items()):
                    if chunk_interval is None:
                        continue
                    intersection_start = max(object_start, chunk_interval[0])
                    intersection_end = min(object_end, chunk_interval[1])
                    if intersection_end <= intersection_start:
                        continue
                    relative_start = intersection_start - object_start
                    relative_end = intersection_end - object_start
                    runtime = runtime_chunks[chunk_id]
                    covered = _covered_extent(
                        item.expected_extent,
                        start=relative_start,
                        end=relative_end,
                    )
                    complete = relative_start == 0 and relative_end == len(item.witness)
                    edge = ProvenanceEdge.build(
                        native_chunk_id=chunk_id,
                        canonical_object_id=item.object_id,
                        canonical_locator=item.locator,
                        mapping_tier=MappingTier.TEXT_UNIQUE_EXACT,
                        coverage_status=(
                            ProvenanceCoverageStatus.COMPLETE
                            if complete
                            else ProvenanceCoverageStatus.PARTIAL
                        ),
                        expected_extent=item.expected_extent,
                        covered_extent=covered,
                        source_sha256=document.sha256,
                        native_content_sha256=runtime.content_sha256,
                        native_lineage_sha256=(
                            runtime.native_lineage.lineage_sha256
                            if runtime.native_lineage is not None
                            else None
                        ),
                        canonical_value_sha256=_sha256_text(item.witness),
                        reason_code=(
                            "rag_anything_exact_unique_parser_stream_crosswalk"
                        ),
                    )
                    item_edges.append(edge)
                    edges.append(edge)
            else:
                diagnostics.append(
                    MappingDiagnostic(
                        canonical_object_id=item.object_id,
                        status=MappingDiagnosticStatus.MISSING,
                        mapping_tier_attempted=MappingTier.TEXT_UNIQUE_EXACT,
                        reason_code="canonical_witness_missing_from_parser_stream",
                    )
                )

        if not item.supported:
            reverse_status = ReverseMappingStatus.UNSUPPORTED
            native_ids: tuple[str, ...] = ()
        elif not item_edges:
            reverse_status = ReverseMappingStatus.MISSING
            native_ids = ()
        else:
            intervals = [
                (
                    int(edge.covered_extent.units[0].start),
                    int(edge.covered_extent.units[0].end),
                )
                for edge in item_edges
            ]
            complete = _intervals_cover(len(item.witness or ""), intervals)
            reverse_status = (
                ReverseMappingStatus.COMPLETE
                if complete
                else ReverseMappingStatus.PARTIAL
            )
            native_ids = tuple(sorted({edge.native_chunk_id for edge in item_edges}))
            if not complete:
                diagnostics.append(
                    MappingDiagnostic(
                        canonical_object_id=item.object_id,
                        status=MappingDiagnosticStatus.MISSING,
                        mapping_tier_attempted=MappingTier.TEXT_UNIQUE_EXACT,
                        reason_code="canonical_witness_only_partially_covered_by_runtime_chunks",
                    )
                )
        mappings.append(
            CanonicalMappingRecord.build(
                canonical_object_id=item.object_id,
                expected_extent=item.expected_extent,
                reverse_mapping_status=reverse_status,
                native_chunk_ids=native_ids,
            )
        )

    ordered_edges = tuple(
        sorted(edges, key=lambda edge: (edge.native_chunk_id, edge.canonical_object_id))
    )
    edge_ids_by_chunk = {
        chunk_id: tuple(
            edge.edge_id for edge in ordered_edges if edge.native_chunk_id == chunk_id
        )
        for chunk_id in runtime_chunks
    }
    source_identity = SourceIdentity(
        document_id=document.document_id,
        source_sha256=document.sha256,
        media_type=(
            document.mime_type
            or "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        source_coordinate_schema=SOURCE_COORDINATE_SYSTEM,
        canonical_catalog_sha256=catalog_sha256,
    )
    runtime_profile = RuntimeProfileIdentity(
        profile_id=(
            f"rag-anything:{runtime_config.get('query_mode', 'unknown')}:native-docx"
        ),
        system_id=ADAPTER_ID,
        system_version=system_version,
        configuration_digest=_digest(
            {
                "runtime_config": dict(runtime_config),
                "system_version": system_version,
                "core_version": core_version,
            }
        ),
    )
    observation_profile = ObservationProfileIdentity.build(
        profile_id="rag-anything-native-docx-observation/2.0",
        adapter_id=ADAPTER_ID,
        adapter_version=adapter_version,
        capabilities=_capabilities(),
    )
    ingestion_catalog = IngestionCatalogObservation(
        observation_status=ObservationStatus.OBSERVED,
        completeness=ObservationCompleteness.COMPLETE,
        items=tuple(runtime_chunks[key] for key in sorted(runtime_chunks)),
        diagnostics={
            "authoritative_store": capture.storage_identity,
            "native_document_count": 1,
            "runtime_chunk_count": len(runtime_chunks),
        },
    )
    receipts = (
        _validation_receipt(
            receipt_kind="source_catalog_pin",
            subject_id=document.document_id,
            details={
                "source_sha256": document.sha256,
                "canonical_catalog_sha256": catalog_sha256,
            },
        ),
        _validation_receipt(
            receipt_kind="runtime_catalog_content_identity",
            subject_id=document.document_id,
            details={
                "storage_identity": capture.storage_identity,
                "runtime_chunk_ids": sorted(runtime_chunks),
            },
        ),
        _validation_receipt(
            receipt_kind="exact_mapping_round_trip",
            subject_id=document.document_id,
            details={
                "edge_count": len(ordered_edges),
                "canonical_record_count": len(mappings),
            },
        ),
    )
    return NativeObservationSnapshot(
        source_identity=source_identity,
        runtime_profile=runtime_profile,
        observation_profile=observation_profile,
        ingestion_catalog=ingestion_catalog,
        provenance_edges=ordered_edges,
        canonical_mapping_records=tuple(
            sorted(mappings, key=lambda item: item.canonical_object_id)
        ),
        mapping_diagnostics=tuple(
            sorted(
                diagnostics,
                key=lambda item: (
                    item.canonical_object_id or "",
                    item.native_chunk_id or "",
                    item.reason_code,
                ),
            )
        ),
        validation_receipts=receipts,
        runtime_chunks=runtime_chunks,
        provenance_edge_ids_by_chunk=edge_ids_by_chunk,
    )


def _unavailable_stage(
    stage: StageName, *, capture: RuntimeQueryCapture, configured_cutoff: int | None
) -> StageObservation:
    status = capture.observation_status
    if status == ObservationStatus.OBSERVED:
        status = ObservationStatus.CORRUPTED
    return StageObservation(
        stage=stage,
        observation_status=status,
        completeness=ObservationCompleteness.UNKNOWN,
        configured_cutoff=configured_cutoff,
        items=(),
        reason=capture.reason or "native query stage observation is unavailable",
        diagnostics={"query_parameters": dict(capture.query_parameters)},
    )


def _corrupted_stage(
    stage: StageName, *, reason: str, configured_cutoff: int | None
) -> StageObservation:
    return StageObservation(
        stage=stage,
        observation_status=ObservationStatus.CORRUPTED,
        completeness=ObservationCompleteness.UNKNOWN,
        configured_cutoff=configured_cutoff,
        items=(),
        reason=reason,
    )


def _observed_items(
    *,
    snapshot: NativeObservationSnapshot,
    stage: StageName,
    values: list[Mapping[str, Any]],
    id_field: str,
    configured_cutoff: int | None,
    completeness: ObservationCompleteness,
) -> StageObservation:
    if configured_cutoff is not None and len(values) > configured_cutoff:
        return _corrupted_stage(
            stage,
            reason="native stage returned more items than its configured cutoff",
            configured_cutoff=configured_cutoff,
        )
    items: list[ObservedStageItem] = []
    seen: set[str] = set()
    for rank, raw in enumerate(values, start=1):
        native_id = raw.get(id_field)
        content = raw.get("content")
        if not isinstance(native_id, str) or not native_id or native_id in seen:
            return _corrupted_stage(
                stage,
                reason="native stage item identity is missing or duplicated",
                configured_cutoff=configured_cutoff,
            )
        runtime = snapshot.runtime_chunks.get(native_id)
        if runtime is None:
            return _corrupted_stage(
                stage,
                reason="native stage item is absent from the complete runtime catalog",
                configured_cutoff=configured_cutoff,
            )
        if not isinstance(content, str) or _sha256_text(content) != runtime.content_sha256:
            return _corrupted_stage(
                stage,
                reason="native stage content differs from the persisted runtime chunk",
                configured_cutoff=configured_cutoff,
            )
        score = raw.get("rerank_score", raw.get("distance"))
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
        ):
            score = None
        items.append(
            ObservedStageItem(
                native_chunk_id=native_id,
                native_rank=rank,
                runtime_score=float(score) if score is not None else None,
                content_sha256=runtime.content_sha256,
                content=content,
                provenance_edge_ids=snapshot.provenance_edge_ids_by_chunk.get(
                    native_id, ()
                ),
                metadata={
                    "file_path": raw.get("file_path"),
                    "reference_id": raw.get("reference_id"),
                    "output_coverage_proof": (
                        "catalog_content_sha256+provenance_receipts"
                    ),
                },
            )
        )
        seen.add(native_id)
    kwargs: dict[str, Any] = {}
    if completeness == ObservationCompleteness.TRUNCATED:
        kwargs["proven_prefix_depth"] = len(items)
    return StageObservation(
        stage=stage,
        observation_status=ObservationStatus.OBSERVED,
        completeness=completeness,
        configured_cutoff=configured_cutoff,
        items=tuple(items),
        diagnostics={
            "same_execution": True,
            "reported_item_count": len(items),
        },
        **kwargs,
    )


def _query_stages(
    *, snapshot: NativeObservationSnapshot, capture: RuntimeQueryCapture
) -> tuple[StageObservation, StageObservation, StageObservation, tuple[ValidationReceipt, ...]]:
    cutoff = capture.candidate_cutoff
    if capture.observation_status != ObservationStatus.OBSERVED:
        return (
            _unavailable_stage(StageName.CANDIDATE, capture=capture, configured_cutoff=cutoff),
            _unavailable_stage(StageName.RANKED, capture=capture, configured_cutoff=cutoff),
            _unavailable_stage(StageName.CONTEXT, capture=capture, configured_cutoff=None),
            (),
        )
    if cutoff is None or cutoff < 1 or capture.query_result is None:
        corrupted = RuntimeQueryCapture.unavailable(
            answer=capture.answer,
            status=ObservationStatus.CORRUPTED,
            reason="native query capture lacks its cutoff or structured result",
            query_parameters=capture.query_parameters,
        )
        return (
            _unavailable_stage(StageName.CANDIDATE, capture=corrupted, configured_cutoff=cutoff),
            _unavailable_stage(StageName.RANKED, capture=corrupted, configured_cutoff=cutoff),
            _unavailable_stage(StageName.CONTEXT, capture=corrupted, configured_cutoff=None),
            (),
        )

    candidates = [dict(item) for item in capture.candidate_items]
    candidate_completeness = (
        ObservationCompleteness.TRUNCATED
        if len(candidates) == cutoff and candidates
        else ObservationCompleteness.COMPLETE
    )
    candidate = _observed_items(
        snapshot=snapshot,
        stage=StageName.CANDIDATE,
        values=candidates,
        id_field="id",
        configured_cutoff=cutoff,
        completeness=candidate_completeness,
    )
    ranked = _observed_items(
        snapshot=snapshot,
        stage=StageName.RANKED,
        values=candidates,
        id_field="id",
        configured_cutoff=cutoff,
        completeness=candidate_completeness,
    )

    data = capture.query_result.get("data")
    raw_context = data.get("chunks") if isinstance(data, Mapping) else None
    if raw_context is None and not candidates:
        context_values: list[Mapping[str, Any]] = []
    elif not isinstance(raw_context, list) or not all(
        isinstance(item, Mapping) for item in raw_context
    ):
        context = _corrupted_stage(
            StageName.CONTEXT,
            reason="native structured result lacks final context chunks",
            configured_cutoff=None,
        )
        return candidate, ranked, context, ()
    else:
        context_values = [dict(item) for item in raw_context]
    context = _observed_items(
        snapshot=snapshot,
        stage=StageName.CONTEXT,
        values=context_values,
        id_field="chunk_id",
        configured_cutoff=None,
        completeness=ObservationCompleteness.COMPLETE,
    )
    if any(
        stage.observation_status != ObservationStatus.OBSERVED
        for stage in (candidate, ranked, context)
    ):
        return candidate, ranked, context, ()
    if (
        not {item.native_chunk_id for item in context.items}.issubset(
            {item.native_chunk_id for item in ranked.items}
        )
    ):
        context = _corrupted_stage(
            StageName.CONTEXT,
            reason="final context violates the declared identity-subset lineage",
            configured_cutoff=None,
        )
        return candidate, ranked, context, ()
    receipt = _validation_receipt(
        receipt_kind="same_execution_stage_lineage",
        subject_id="candidate->ranked->context",
        details={
            "candidate_ids": [item.native_chunk_id for item in candidate.items],
            "ranked_ids": [item.native_chunk_id for item in ranked.items],
            "context_ids": [item.native_chunk_id for item in context.items],
            "transition_mode": "identity_subset",
        },
    )
    return candidate, ranked, context, (receipt,)


def build_native_run_result_v2(
    *,
    snapshot: NativeObservationSnapshot,
    case_id: str,
    capture: RuntimeQueryCapture,
    generate_answer: bool,
    adapter_version: str,
) -> AdapterRunResultV2:
    candidate, ranked, context, query_receipts = _query_stages(
        snapshot=snapshot,
        capture=capture,
    )
    if generate_answer and isinstance(capture.answer, str):
        answer = ContentObservation.observed(capture.answer)
    elif generate_answer:
        answer = ContentObservation(
            observation_status=ObservationStatus.FAILED,
            completeness=ObservationCompleteness.UNKNOWN,
            reason="RAG-Anything answer is not text",
        )
    else:
        answer = ContentObservation(
            observation_status=ObservationStatus.UNOBSERVED,
            completeness=ObservationCompleteness.UNKNOWN,
            reason="answer generation was disabled",
        )
    prompt = ContentObservation(
        observation_status=ObservationStatus.UNSUPPORTED,
        completeness=ObservationCompleteness.UNKNOWN,
        reason="RAG-Anything does not expose the rendered final prompt",
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
        raw_retrieval=candidate,
        ranked_retrieval=ranked,
        final_context=context,
        transformations=(),
        prompt_trace=prompt,
        answer=answer,
        validation_receipts=(
            *snapshot.validation_receipts,
            *query_receipts,
        ),
    )
    return AdapterRunResultV2(
        adapter_id=ADAPTER_ID,
        adapter_version=adapter_version,
        system_id=ADAPTER_ID,
        system_version=snapshot.runtime_profile.system_version,
        trace=trace,
    )


__all__ = [
    "NativeObservationSnapshot",
    "RuntimeIngestionCapture",
    "RuntimeQueryCapture",
    "build_native_observation_snapshot",
    "build_native_run_result_v2",
]
