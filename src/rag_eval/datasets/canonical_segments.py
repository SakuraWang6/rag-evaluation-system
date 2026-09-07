"""Deterministic primary evaluation corpus built from canonical records.

The source DOCX remains the presentation/audit artifact.  Retrieval evaluation
uses this module's immutable projection instead: every source object is placed
in a named logical segment *before* it reaches a RAG implementation.  The
LightRAG adapter is then required to prove its persisted chunks came from the
named input batches; it is never allowed to guess an OOXML location from a
returned string.

The intentionally small transport contract is shared with adapters through a
JSON manifest staged in the run's source sandbox.  It is not a new authoring
format: it is a deterministic runtime view of the already-pinned canonical
JSONL in a Bundle 2.0 document.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.contracts.adapter import DocumentInput
from rag_eval.contracts.dataset import (
    GoldEvidence,
    ObjectLocator,
    PageRegionLocator,
    TableCellLocator,
    TextSpanLocator,
)
from rag_eval.storage.atomic import atomic_write_json


CANONICAL_SEGMENT_SCHEMA_VERSION = "canonical-segment-corpus/1"
CANONICAL_SEGMENT_MANIFEST_NAME = "canonical-segment-corpus.json"
# This is deliberately a conservative packing target, not an asserted token
# conversion.  The adapter independently rejects a batch if LightRAG splits
# it or changes its bytes, which is the actual acceptance boundary.
DEFAULT_MAX_BATCH_CHARACTERS = 3_000


class CanonicalSegmentError(ValueError):
    """A canonical source cannot be made into an auditable retrieval corpus."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class CanonicalSegmentSource(_Model):
    document_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_sidecar_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CanonicalSegmentObject(_Model):
    """One source object in the segment corpus's immutable object catalog."""

    object_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    locator: dict[str, Any] | None = None
    expected_extent: dict[str, Any]
    mapping_status: Literal["mapped", "unmapped"]
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    witness_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class CanonicalSegmentEdge(_Model):
    object_id: str = Field(min_length=1)
    coverage: Literal["full", "partial"]


class CanonicalSegment(_Model):
    segment_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    root_object_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    content: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    edges: tuple[CanonicalSegmentEdge, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_content(self) -> "CanonicalSegment":
        if _sha256_text(self.content) != self.content_sha256:
            raise ValueError("segment content digest does not match content")
        object_ids = [item.object_id for item in self.edges]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("a segment cannot repeat one canonical object edge")
        return self


class CanonicalSegmentBatch(_Model):
    """One physical LightRAG input containing complete logical segments."""

    batch_id: str = Field(min_length=1)
    input_document_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    segment_ids: tuple[str, ...] = Field(min_length=1)
    content: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_content(self) -> "CanonicalSegmentBatch":
        if _sha256_text(self.content) != self.content_sha256:
            raise ValueError("batch content digest does not match content")
        if len(self.segment_ids) != len(set(self.segment_ids)):
            raise ValueError("a batch cannot repeat one segment ID")
        return self


class CanonicalSegmentManifest(_Model):
    """Pinned bridge from canonical objects to deterministic input batches."""

    schema_version: Literal[CANONICAL_SEGMENT_SCHEMA_VERSION] = (
        CANONICAL_SEGMENT_SCHEMA_VERSION
    )
    sources: tuple[CanonicalSegmentSource, ...] = Field(min_length=1)
    object_catalog: tuple[CanonicalSegmentObject, ...] = Field(min_length=1)
    segments: tuple[CanonicalSegment, ...] = Field(min_length=1)
    batches: tuple[CanonicalSegmentBatch, ...] = Field(min_length=1)
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_manifest(self) -> "CanonicalSegmentManifest":
        source_ids = [item.document_id for item in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("canonical segment sources must be unique")
        catalog_ids = [item.object_id for item in self.object_catalog]
        if len(catalog_ids) != len(set(catalog_ids)):
            raise ValueError("canonical segment object IDs must be unique")
        segment_ids = [item.segment_id for item in self.segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError("canonical segment IDs must be unique")
        batch_ids = [item.batch_id for item in self.batches]
        if len(batch_ids) != len(set(batch_ids)):
            raise ValueError("canonical segment batch IDs must be unique")
        input_ids = [item.input_document_id for item in self.batches]
        if len(input_ids) != len(set(input_ids)):
            raise ValueError("canonical segment batch input IDs must be unique")
        known_sources = set(source_ids)
        if any(item.document_id not in known_sources for item in self.object_catalog):
            raise ValueError("object catalog references an unknown source document")
        if any(item.document_id not in known_sources for item in self.segments):
            raise ValueError("segment references an unknown source document")
        if any(item.document_id not in known_sources for item in self.batches):
            raise ValueError("batch references an unknown source document")
        known_objects = set(catalog_ids)
        if any(
            edge.object_id not in known_objects
            for segment in self.segments
            for edge in segment.edges
        ):
            raise ValueError("segment edge references an unknown canonical object")
        known_segments = set(segment_ids)
        packed_ids = [
            segment_id
            for batch in self.batches
            for segment_id in batch.segment_ids
        ]
        if set(packed_ids) != known_segments or len(packed_ids) != len(known_segments):
            raise ValueError("batches must contain every canonical segment exactly once")
        by_id = {item.segment_id: item for item in self.segments}
        for batch in self.batches:
            if any(by_id[item].document_id != batch.document_id for item in batch.segment_ids):
                raise ValueError("a physical batch cannot cross source documents")
            expected_content = render_batch([by_id[item] for item in batch.segment_ids])
            if expected_content != batch.content:
                raise ValueError("batch content does not match its ordered segment envelope")
        if self.manifest_digest != _manifest_digest_payload(self._digest_payload()):
            raise ValueError("canonical segment manifest digest does not match content")
        return self

    def _digest_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "sources": [item.model_dump(mode="json") for item in self.sources],
            "object_catalog": [item.model_dump(mode="json") for item in self.object_catalog],
            "segments": [item.model_dump(mode="json") for item in self.segments],
            "batches": [item.model_dump(mode="json") for item in self.batches],
        }

    @classmethod
    def build(
        cls,
        *,
        sources: Iterable[CanonicalSegmentSource],
        object_catalog: Iterable[CanonicalSegmentObject],
        segments: Iterable[CanonicalSegment],
        batches: Iterable[CanonicalSegmentBatch],
    ) -> "CanonicalSegmentManifest":
        values = {
            "sources": tuple(sorted(sources, key=lambda item: item.document_id)),
            "object_catalog": tuple(
                sorted(object_catalog, key=lambda item: (item.document_id, item.object_id))
            ),
            "segments": tuple(
                sorted(segments, key=lambda item: (item.document_id, item.ordinal, item.segment_id))
            ),
            "batches": tuple(
                sorted(batches, key=lambda item: (item.document_id, item.ordinal, item.batch_id))
            ),
        }
        digest = _manifest_digest_payload(
            {
                "schema_version": CANONICAL_SEGMENT_SCHEMA_VERSION,
                **{
                    key: [item.model_dump(mode="json") for item in value]
                    for key, value in values.items()
                },
            }
        )
        return cls(**values, manifest_digest=digest)

    def source_for(self, document_id: str) -> CanonicalSegmentSource:
        for item in self.sources:
            if item.document_id == document_id:
                return item
        raise KeyError(document_id)

    def batch_for_input(self, input_document_id: str) -> CanonicalSegmentBatch:
        for item in self.batches:
            if item.input_document_id == input_document_id:
                return item
        raise KeyError(input_document_id)


def _manifest_digest_payload(value: object) -> str:
    return _sha256_text(_canonical_json(value))


def render_segment_envelope(segment: CanonicalSegment) -> str:
    """Render a visible, deterministic envelope around one logical segment."""

    return (
        f"[[CANONICAL_SEGMENT id={segment.segment_id} document={segment.document_id}]]\n"
        f"{segment.content}\n"
        "[[/CANONICAL_SEGMENT]]"
    )


def render_batch(segments: Iterable[CanonicalSegment]) -> str:
    return "\n\n".join(render_segment_envelope(item) for item in segments)


def build_canonical_segment_manifest(
    bundle: Any,
    *,
    max_batch_characters: int = DEFAULT_MAX_BATCH_CHARACTERS,
) -> CanonicalSegmentManifest:
    """Create an immutable canonical-segment runtime view for a Bundle.

    ``bundle`` is intentionally duck-typed to avoid a circular import with
    :mod:`rag_eval.datasets.bundle`.  It must expose ``root`` and a manifest
    containing Bundle 2.0 document entries.
    """

    if max_batch_characters < 256:
        raise CanonicalSegmentError("max_batch_characters must be at least 256")
    sources: list[CanonicalSegmentSource] = []
    objects: list[CanonicalSegmentObject] = []
    segments: list[CanonicalSegment] = []
    batches: list[CanonicalSegmentBatch] = []
    for document in bundle.manifest.documents:
        if document.canonical_path is None:
            raise CanonicalSegmentError(
                f"document {document.document_id!r} has no canonical JSONL source"
            )
        canonical_path = bundle.root / document.canonical_path
        if not canonical_path.is_file():
            raise CanonicalSegmentError(
                f"canonical source is missing for document {document.document_id!r}"
            )
        raw = canonical_path.read_bytes()
        sidecar_sha = hashlib.sha256(raw).hexdigest()
        records = _canonical_records(raw, document.document_id)
        source, catalog, document_segments = _document_projection(
            document_id=document.document_id,
            source_sha256=document.sha256,
            canonical_sidecar_sha256=sidecar_sha,
            records=records,
        )
        sources.append(source)
        objects.extend(catalog)
        segments.extend(document_segments)
        batches.extend(
            _pack_document_segments(
                document_id=document.document_id,
                segments=document_segments,
                max_batch_characters=max_batch_characters,
            )
        )
    manifest = CanonicalSegmentManifest.build(
        sources=sources,
        object_catalog=objects,
        segments=segments,
        batches=batches,
    )
    _validate_gold_evidence_segmentability(bundle, manifest)
    return manifest


def materialize_canonical_segment_documents(
    bundle: Any,
    source_dir: Path,
    *,
    max_batch_characters: int = DEFAULT_MAX_BATCH_CHARACTERS,
) -> list[DocumentInput]:
    """Stage a primary canonical corpus and return its LightRAG inputs.

    Original documents and canonical sidecars are copied into the source
    sandbox for presentation/audit only.  They are not passed to ``ingest``.
    Each actual ingestion input is a digest-pinned canonical batch.
    """

    source_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_canonical_segment_manifest(
        bundle, max_batch_characters=max_batch_characters
    )
    manifest_path = source_dir / CANONICAL_SEGMENT_MANIFEST_NAME
    atomic_write_json(manifest_path, manifest.model_dump(mode="json"))

    # Retain source artifacts inside the run sandbox without putting them into
    # the primary ingestion list.  This supports later Word/canonical evidence
    # presentation while making the execution boundary explicit.
    for ordinal, document in enumerate(bundle.manifest.documents):
        original = bundle.root / document.path
        suffix = original.suffix.lower() or ".bin"
        source_name = f"presentation-{ordinal:05d}-{hashlib.sha256(document.document_id.encode()).hexdigest()[:12]}{suffix}"
        shutil.copyfile(original, source_dir / source_name)
        if document.canonical_path is not None:
            canonical = bundle.root / document.canonical_path
            sidecar_name = f"canonical-source-{ordinal:05d}-{hashlib.sha256(document.document_id.encode()).hexdigest()[:12]}.jsonl"
            shutil.copyfile(canonical, source_dir / sidecar_name)

    result: list[DocumentInput] = []
    for batch in manifest.batches:
        source = manifest.source_for(batch.document_id)
        result.append(
            DocumentInput(
                document_id=batch.input_document_id,
                content=batch.content,
                sha256=batch.content_sha256,
                mime_type="text/plain",
                metadata={
                    "primary_evaluation_corpus": "canonical_segments",
                    "canonical_segment_manifest_path": CANONICAL_SEGMENT_MANIFEST_NAME,
                    "canonical_segment_manifest_digest": manifest.manifest_digest,
                    "canonical_segment_batch_id": batch.batch_id,
                    "canonical_segment_source_document_id": source.document_id,
                    "canonical_segment_source_sha256": source.source_sha256,
                    "canonical_segment_sidecar_sha256": source.canonical_sidecar_sha256,
                },
            )
        )
    return result


def load_staged_canonical_segment_manifest(
    source_dir: Path, documents: Iterable[DocumentInput]
) -> CanonicalSegmentManifest | None:
    """Load the one staged manifest referenced by canonical batch inputs."""

    values = [
        item
        for item in documents
        if item.metadata.get("primary_evaluation_corpus") == "canonical_segments"
    ]
    if not values:
        return None
    paths = {item.metadata.get("canonical_segment_manifest_path") for item in values}
    digests = {item.metadata.get("canonical_segment_manifest_digest") for item in values}
    if len(paths) != 1 or len(digests) != 1:
        raise CanonicalSegmentError("canonical batch inputs disagree about their manifest")
    path_name = next(iter(paths))
    expected = next(iter(digests))
    if not isinstance(path_name, str) or Path(path_name).name != path_name:
        raise CanonicalSegmentError("canonical segment manifest path is unsafe")
    if not isinstance(expected, str) or len(expected) != 64:
        raise CanonicalSegmentError("canonical segment manifest digest is malformed")
    path = source_dir / path_name
    if not path.is_file():
        raise CanonicalSegmentError("canonical segment manifest is missing from source sandbox")
    try:
        manifest = CanonicalSegmentManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise CanonicalSegmentError("canonical segment manifest is malformed") from exc
    if manifest.manifest_digest != expected:
        raise CanonicalSegmentError("canonical segment manifest logical digest does not match input metadata")
    expected_inputs = {item.document_id for item in values}
    observed_inputs = {item.input_document_id for item in manifest.batches}
    if expected_inputs != observed_inputs:
        raise CanonicalSegmentError("canonical batch inputs do not match the staged manifest")
    for item in values:
        batch = manifest.batch_for_input(item.document_id)
        if item.content != batch.content or item.sha256 != batch.content_sha256:
            raise CanonicalSegmentError(
                f"canonical batch input {item.document_id!r} does not match its manifest"
            )
    return manifest


def _canonical_records(raw: bytes, document_id: str) -> list[dict[str, Any]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CanonicalSegmentError("canonical source is not UTF-8 JSONL") from exc
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CanonicalSegmentError(
                f"canonical source {document_id!r} has malformed JSON at line {line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise CanonicalSegmentError(
                f"canonical source {document_id!r} has a non-object record at line {line_number}"
            )
        if value.get("document_id") != document_id:
            raise CanonicalSegmentError(
                f"canonical source record at line {line_number} has a different document ID"
            )
        if not isinstance(value.get("object_id"), str) or not value["object_id"]:
            raise CanonicalSegmentError(
                f"canonical source record at line {line_number} has no object ID"
            )
        if not isinstance(value.get("object_type"), str) or not value["object_type"]:
            raise CanonicalSegmentError(
                f"canonical source record at line {line_number} has no object type"
            )
        records.append(value)
    if not records:
        raise CanonicalSegmentError(f"canonical source {document_id!r} is empty")
    ids = [str(item["object_id"]) for item in records]
    if len(ids) != len(set(ids)):
        raise CanonicalSegmentError(f"canonical source {document_id!r} repeats an object ID")
    return records


def _document_projection(
    *,
    document_id: str,
    source_sha256: str,
    canonical_sidecar_sha256: str,
    records: list[dict[str, Any]],
) -> tuple[
    CanonicalSegmentSource,
    list[CanonicalSegmentObject],
    list[CanonicalSegment],
]:
    by_id = {str(item["object_id"]): item for item in records}
    order = {
        object_id: _document_order(record, fallback=index)
        for index, (object_id, record) in enumerate(by_id.items())
    }
    segment_edges: dict[str, dict[str, Literal["full", "partial"]]] = {}
    raw_segments: list[tuple[str, str, int, str, dict[str, Literal["full", "partial"]]]] = []

    tables = sorted(
        (item for item in records if item.get("object_type") == "table" and _usable(item)),
        key=lambda item: (order[str(item["object_id"])], str(item["object_id"])),
    )
    table_ids = {str(item["object_id"]) for item in tables}
    rows_by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cells_by_table_row: dict[tuple[str, int | str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        table_id = record.get("table_id")
        if not isinstance(table_id, str) or table_id not in table_ids:
            continue
        if record.get("object_type") == "row":
            rows_by_table[table_id].append(record)
        elif record.get("object_type") == "cell":
            row = record.get("row")
            if isinstance(row, (int, str)) and not isinstance(row, bool):
                cells_by_table_row[(table_id, row)].append(record)

    consumed: set[str] = set()
    for table in tables:
        table_id = str(table["object_id"])
        rows = sorted(
            rows_by_table.get(table_id, ()),
            key=lambda item: (_sortable_row(item.get("row")), order[str(item["object_id"])]),
        )
        if not rows:
            table_content = _text_value(table)
            if table_content:
                edges = {table_id: "full"}
                raw_segments.append(
                    (table_id, table_id, order[table_id], _render_table_fallback(table_id, table_content), edges)
                )
                segment_edges[table_id] = edges
                consumed.add(table_id)
            continue
        header = _text_value(rows[0])
        for row_record in rows:
            row_id = str(row_record["object_id"])
            row_number = row_record.get("row")
            row_content = _text_value(row_record)
            cells = sorted(
                cells_by_table_row.get((table_id, row_number), ()),
                key=lambda item: _sortable_column(item.get("column")),
            )
            if not row_content:
                row_content = " | ".join(_text_value(item) for item in cells)
            if not row_content:
                # An entirely empty row cannot provide a non-empty retrieval
                # segment.  It stays catalogued as unmapped and therefore can
                # never make a Gold fact look retrievable.
                continue
            edges: dict[str, Literal["full", "partial"]] = {}
            if _usable(table):
                edges[table_id] = "partial"
            if _usable(row_record):
                edges[row_id] = "full"
            for cell in cells:
                if _usable(cell):
                    edges[str(cell["object_id"])] = "full"
            if not edges:
                continue
            content = _render_table_row(
                table_id=table_id,
                row=row_number,
                header=header if row_record is not rows[0] else None,
                value=row_content,
            )
            raw_segments.append((row_id, row_id, order[row_id], content, edges))
            segment_edges[row_id] = edges
            consumed.update(edges)

    root_types = {
        "paragraph",
        "block",
        "heading",
        "caption",
        "equation",
        "figure",
        "reference",
        "footnote",
        "endnote",
    }
    for record in sorted(records, key=lambda item: (order[str(item["object_id"])], str(item["object_id"]))):
        object_id = str(record["object_id"])
        if object_id in consumed or record.get("object_type") not in root_types or not _usable(record):
            continue
        value = _text_value(record)
        if not value:
            continue
        object_type = _normalized_object_type(record)
        content = f"【{_display_object_type(object_type)}】\n{value}"
        edges = {object_id: "full"}
        raw_segments.append((object_id, object_id, order[object_id], content, edges))
        segment_edges[object_id] = edges
        consumed.add(object_id)

    if not raw_segments:
        raise CanonicalSegmentError(
            f"canonical source {document_id!r} has no complete textual/table segment"
        )
    segments: list[CanonicalSegment] = []
    for ordinal, (root_object_id, _stable_root, record_order, content, edges) in enumerate(
        sorted(raw_segments, key=lambda item: (item[2], item[0]))
    ):
        edge_values = tuple(
            CanonicalSegmentEdge(object_id=object_id, coverage=coverage)
            for object_id, coverage in sorted(edges.items())
        )
        segment_id = "segment-" + _sha256_text(
            f"{CANONICAL_SEGMENT_SCHEMA_VERSION}\0{document_id}\0{canonical_sidecar_sha256}\0{root_object_id}"
        )
        segments.append(
            CanonicalSegment(
                segment_id=segment_id,
                document_id=document_id,
                root_object_id=root_object_id,
                ordinal=ordinal,
                content=content,
                content_sha256=_sha256_text(content),
                edges=edge_values,
            )
        )

    mapped_ids = {
        edge.object_id for segment in segments for edge in segment.edges
    }
    table_cells: dict[str, list[str]] = defaultdict(list)
    for record in records:
        if record.get("object_type") == "cell" and isinstance(record.get("table_id"), str):
            table_cells[str(record["table_id"])].append(str(record["object_id"]))
    catalog = [
        _catalog_object(
            record=record,
            source_sha256=source_sha256,
            mapped=str(record["object_id"]) in mapped_ids,
            table_cell_ids=tuple(sorted(table_cells.get(str(record["object_id"]), ()))),
        )
        for record in sorted(records, key=lambda item: (order[str(item["object_id"])], str(item["object_id"])))
    ]
    return (
        CanonicalSegmentSource(
            document_id=document_id,
            source_sha256=source_sha256,
            canonical_sidecar_sha256=canonical_sidecar_sha256,
        ),
        catalog,
        segments,
    )


def _pack_document_segments(
    *,
    document_id: str,
    segments: list[CanonicalSegment],
    max_batch_characters: int,
) -> list[CanonicalSegmentBatch]:
    values: list[CanonicalSegmentBatch] = []
    pending: list[CanonicalSegment] = []
    for segment in segments:
        single = render_batch([segment])
        if len(single) > max_batch_characters:
            raise CanonicalSegmentError(
                f"canonical segment {segment.segment_id!r} is {len(single)} characters, "
                f"above the configured deterministic batch boundary {max_batch_characters}"
            )
        candidate = [*pending, segment]
        if pending and len(render_batch(candidate)) > max_batch_characters:
            values.append(_make_batch(document_id, len(values), pending))
            pending = [segment]
        else:
            pending = candidate
    if pending:
        values.append(_make_batch(document_id, len(values), pending))
    return values


def _make_batch(
    document_id: str, ordinal: int, segments: list[CanonicalSegment]
) -> CanonicalSegmentBatch:
    content = render_batch(segments)
    stable = _sha256_text(
        f"{CANONICAL_SEGMENT_SCHEMA_VERSION}\0{document_id}\0"
        + "\0".join(item.segment_id for item in segments)
        + f"\0{_sha256_text(content)}"
    )
    return CanonicalSegmentBatch(
        batch_id="segment-batch-" + stable,
        input_document_id="canonical-batch-" + stable,
        document_id=document_id,
        ordinal=ordinal,
        segment_ids=tuple(item.segment_id for item in segments),
        content=content,
        content_sha256=_sha256_text(content),
    )


def _catalog_object(
    *,
    record: dict[str, Any],
    source_sha256: str,
    mapped: bool,
    table_cell_ids: tuple[str, ...],
) -> CanonicalSegmentObject:
    object_id = str(record["object_id"])
    object_type = _normalized_object_type(record)
    locator = _locator_for_record(record)
    status: Literal["mapped", "unmapped"] = "mapped" if mapped else "unmapped"
    extent: dict[str, Any] = {"status": status, "object_id": object_id}
    if object_type == "cell":
        table_id, row, column = record.get("table_id"), record.get("row"), record.get("column")
        if isinstance(table_id, str):
            extent.update({"table_id": table_id, "row": row, "column": column})
    elif object_type == "table":
        extent.update({"table_id": object_id, "physical_cell_ids": list(table_cell_ids)})
    else:
        body_ordinal = _body_ordinal(record)
        if body_ordinal is not None:
            extent["body_ordinal"] = body_ordinal
    value = _text_value(record)
    return CanonicalSegmentObject(
        object_id=object_id,
        document_id=str(record["document_id"]),
        object_type=object_type,
        locator=locator,
        expected_extent=extent,
        mapping_status=status,
        source_sha256=source_sha256,
        witness_sha256=_sha256_text(value) if value else None,
    )


def _validate_gold_evidence_segmentability(bundle: Any, manifest: CanonicalSegmentManifest) -> None:
    catalog = {item.object_id: item for item in manifest.object_catalog}
    cells_by_locator: dict[tuple[str, str, int | str, int | str], CanonicalSegmentObject] = {}
    for item in manifest.object_catalog:
        locator = item.locator or {}
        if locator.get("type") == "table_cell":
            cells_by_locator[
                (
                    item.document_id,
                    str(locator["table_id"]),
                    locator["row"],
                    locator["column"],
                )
            ] = item
    unsupported: list[str] = []
    for evidence_set in bundle.gold_evidence_sets.values():
        for evidence in evidence_set.evidence:
            item = _catalog_evidence_item(evidence, catalog, cells_by_locator)
            if item is None or item.mapping_status != "mapped":
                unsupported.append(evidence.evidence_id)
    if unsupported:
        preview = ", ".join(sorted(unsupported)[:8])
        suffix = " …" if len(unsupported) > 8 else ""
        raise CanonicalSegmentError(
            "primary canonical corpus has no deterministic segment for Gold Evidence: "
            f"{preview}{suffix}"
        )


def _catalog_evidence_item(
    evidence: GoldEvidence,
    catalog: dict[str, CanonicalSegmentObject],
    cells: dict[tuple[str, str, int | str, int | str], CanonicalSegmentObject],
) -> CanonicalSegmentObject | None:
    locator = evidence.locator
    if isinstance(locator, ObjectLocator):
        item = catalog.get(locator.object_id)
        return item if item is not None and item.document_id == evidence.document_id else None
    if isinstance(locator, TableCellLocator):
        return cells.get((evidence.document_id, locator.table_id, locator.row, locator.column))
    # The primary canonical segment corpus intentionally does not create a
    # rendered-page coordinate.  A source dataset with a text/page-only Gold
    # must publish an explicit canonical object before it can be evaluated.
    if isinstance(locator, (TextSpanLocator, PageRegionLocator)):
        return None
    return None


def _usable(record: dict[str, Any]) -> bool:
    status = record.get("representation_status", record.get("status"))
    return status in {"complete", "supported"}


def _text_value(record: dict[str, Any]) -> str:
    value = record.get("canonical_value")
    return value.strip() if isinstance(value, str) else ""


def _normalized_object_type(record: dict[str, Any]) -> str:
    value = str(record.get("object_type") or "")
    if value == "block":
        kind = str(record.get("block_kind") or "paragraph")
        return "heading" if kind == "heading" else kind
    return value


def _locator_for_record(record: dict[str, Any]) -> dict[str, Any] | None:
    object_type = _normalized_object_type(record)
    if object_type == "cell":
        table_id, row, column = record.get("table_id"), record.get("row"), record.get("column")
        if (
            isinstance(table_id, str)
            and isinstance(row, (int, str))
            and not isinstance(row, bool)
            and isinstance(column, (int, str))
            and not isinstance(column, bool)
        ):
            return {
                "type": "table_cell",
                "table_id": table_id,
                "row": row,
                "column": column,
            }
    return {"type": "object", "object_type": object_type, "object_id": str(record["object_id"])}


def _document_order(record: dict[str, Any], *, fallback: int) -> int:
    value = record.get("document_order")
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else fallback


def _body_ordinal(record: dict[str, Any]) -> int | None:
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        return None
    spans = provenance.get("source_spans")
    if not isinstance(spans, list):
        return None
    for span in spans:
        if not isinstance(span, dict):
            continue
        coordinates = span.get("coordinates")
        value = coordinates.get("body_ordinal") if isinstance(coordinates, dict) else None
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _sortable_row(value: object) -> tuple[int, str]:
    if isinstance(value, int) and not isinstance(value, bool):
        return 0, f"{value:012d}"
    return 1, str(value)


def _sortable_column(value: object) -> tuple[int, str]:
    if isinstance(value, int) and not isinstance(value, bool):
        return 0, f"{value:012d}"
    return 1, str(value)


def _render_table_row(
    *, table_id: str, row: object, header: str | None, value: str
) -> str:
    pieces = [f"【表格】{table_id}"]
    if header:
        pieces.extend(("【表头】", header))
    pieces.extend((f"【第 {row} 行】", value))
    return "\n".join(pieces)


def _render_table_fallback(table_id: str, value: str) -> str:
    return f"【表格】{table_id}\n{value}"


def _display_object_type(value: str) -> str:
    return {
        "paragraph": "段落",
        "heading": "标题",
        "caption": "题注",
        "equation": "公式",
        "figure": "图形说明",
        "reference": "引用",
        "footnote": "脚注",
        "endnote": "尾注",
    }.get(value, value)
