"""Deterministic canonical-object to LightRAG runtime-chunk provenance.

The bridge aligns canonicalizer-v1 records to their exact execution-Markdown
rendering, then intersects those source intervals with LightRAG's persisted
runtime chunk intervals. It never reads Gold and never searches with an answer.
Ambiguous, missing, malformed, or content-mismatched provenance fails closed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAP_SCHEMA_VERSION = 2
SUPPORTED_CANONICALIZER = "rag-eval-authoring-canonicalizer/1"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


@dataclass(frozen=True, slots=True)
class CanonicalObjectSpan:
    object_id: str
    object_type: str
    status: str
    start: int
    end: int
    locator: dict[str, Any]
    witness_sha256: str
    alignment_method: str
    structure: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "status": self.status,
            "source_span": {"start": self.start, "end": self.end},
            "locator": self.locator,
            "witness_sha256": self.witness_sha256,
            "alignment_method": self.alignment_method,
            "structure": self.structure,
        }


@dataclass(frozen=True, slots=True)
class CanonicalDocumentMap:
    document_id: str
    source_sha256: str
    canonical_sidecar_sha256: str
    canonical_digest: str | None
    canonicalizer: str | None
    objects: tuple[CanonicalObjectSpan, ...]
    sections: tuple[dict[str, Any], ...]
    diagnostics: tuple[dict[str, str], ...]

    def intersect(self, start: int, end: int) -> list[dict[str, Any]]:
        mappings: list[dict[str, Any]] = []
        for item in self.objects:
            overlap_start = max(start, item.start)
            overlap_end = min(end, item.end)
            if overlap_start >= overlap_end:
                continue
            coverage = "full" if start <= item.start and end >= item.end else "partial"
            mappings.append(
                {
                    **item.as_dict(),
                    "overlap_span": {
                        "start": overlap_start,
                        "end": overlap_end,
                    },
                    "coverage": coverage,
                }
            )
        return mappings

    def as_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_sha256": self.source_sha256,
            "canonical_sidecar_sha256": self.canonical_sidecar_sha256,
            "canonical_digest": self.canonical_digest,
            "canonicalizer": self.canonicalizer,
            "objects": [item.as_dict() for item in self.objects],
            "sections": list(self.sections),
            "diagnostics": list(self.diagnostics),
        }

    def structure_for_span(
        self, start: int, end: int, mappings: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Project canonical-only structure onto one verified runtime chunk.

        Section assignment is derived from the execution source intervals of
        canonical headings.  A chunk crossing a heading boundary is marked
        partial rather than silently attributed to an arbitrary section.
        """

        overlaps: list[tuple[int, dict[str, Any]]] = []
        for section in self.sections:
            interval = section.get("active_source_span")
            if not isinstance(interval, dict):
                continue
            section_start = interval.get("start")
            section_end = interval.get("end")
            if not isinstance(section_start, int) or not isinstance(section_end, int):
                continue
            overlap = min(end, section_end) - max(start, section_start)
            if overlap > 0:
                overlaps.append((overlap, section))
        if not overlaps:
            return {
                "metadata_status": "missing",
                "missing_fields": ["section_mapping"],
                "section_ids": [],
                "canonical_object_count": len(mappings),
            }

        overlaps.sort(
            key=lambda item: (
                -item[0],
                int(item[1].get("document_order") or -1),
                str(item[1].get("section_id") or ""),
            )
        )
        primary = overlaps[0][1]
        section_ids = [str(section.get("section_id")) for _, section in overlaps]
        object_structures = [
            item.get("structure")
            for item in mappings
            if isinstance(item, dict) and isinstance(item.get("structure"), dict)
        ]
        object_types = sorted(
            {
                str(item.get("object_type"))
                for item in mappings
                if isinstance(item, dict) and item.get("object_type")
            }
        )
        orders = [
            value.get("document_order")
            for value in object_structures
            if isinstance(value.get("document_order"), int)
        ]
        statuses = {
            str(value.get("metadata_status"))
            for value in object_structures
            if value.get("metadata_status")
        }
        status = "complete"
        missing_fields: list[str] = []
        if len(overlaps) != 1 or statuses - {"complete"}:
            status = "partial"
        if len(overlaps) != 1:
            missing_fields.append("single_section_mapping")
        if not object_structures:
            status = "partial"
            missing_fields.append("canonical_object_structure")
        if statuses - {"complete"}:
            missing_fields.append("complete_canonical_object_structure")
        return {
            "metadata_status": status,
            "missing_fields": missing_fields,
            "section_id": primary.get("section_id"),
            "heading_path": primary.get("heading_path"),
            "parent_section_id": primary.get("parent_section_id"),
            "section_role": primary.get("section_role"),
            "document_order": min(orders) if orders else None,
            "document_order_range": (
                {"start": min(orders), "end": max(orders)} if orders else None
            ),
            "section_ids": section_ids,
            "section_overlap_chars": {
                str(section.get("section_id")): overlap for overlap, section in overlaps
            },
            "canonical_object_count": len(mappings),
            "canonical_object_types": object_types,
            "table_ids": sorted(
                {
                    str(value.get("table_id"))
                    for value in object_structures
                    if value.get("table_id")
                }
            ),
            "row_ids": sorted(
                {
                    str(value.get("row_id"))
                    for value in object_structures
                    if value.get("row_id")
                }
            ),
        }


def load_canonical_document_map(
    *,
    document_id: str,
    source: str,
    sidecar_path: Path,
    expected_sidecar_sha256: str,
) -> CanonicalDocumentMap:
    payload = sidecar_path.read_bytes()
    actual_digest = sha256_bytes(payload)
    if actual_digest != expected_sidecar_sha256:
        raise ValueError("canonical provenance sidecar digest mismatch")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(payload.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(
                f"canonical provenance line {line_number} is not an object"
            )
        if value.get("document_id") != document_id:
            raise ValueError(
                f"canonical provenance line {line_number} has wrong document_id"
            )
        records.append(value)
    if not records:
        raise ValueError("canonical provenance sidecar is empty")
    canonicalizers = {
        str(record.get("canonicalizer"))
        for record in records
        if record.get("canonicalizer")
    }
    canonicalizer = next(iter(canonicalizers)) if len(canonicalizers) == 1 else None
    canonical_digests = {
        str(record.get("canonical_digest"))
        for record in records
        if record.get("canonical_digest")
    }
    canonical_digest = (
        next(iter(canonical_digests)) if len(canonical_digests) == 1 else None
    )
    if canonicalizer != SUPPORTED_CANONICALIZER:
        return CanonicalDocumentMap(
            document_id=document_id,
            source_sha256=sha256_text(source),
            canonical_sidecar_sha256=actual_digest,
            canonical_digest=canonical_digest,
            canonicalizer=canonicalizer,
            objects=(),
            sections=(),
            diagnostics=(
                {
                    "reason": "unsupported_canonicalizer",
                    "object_id": "",
                },
            ),
        )
    structures, section_specs = _build_canonical_structure(records)
    objects, diagnostics = _align_canonicalizer_v1(source, records, structures)
    return CanonicalDocumentMap(
        document_id=document_id,
        source_sha256=sha256_text(source),
        canonical_sidecar_sha256=actual_digest,
        canonical_digest=canonical_digest,
        canonicalizer=canonicalizer,
        objects=tuple(objects),
        sections=tuple(_materialize_sections(section_specs, objects, source)),
        diagnostics=tuple(diagnostics),
    )


def runtime_chunk_mapping(
    *,
    chunk_id: str,
    document: CanonicalDocumentMap,
    source: str,
    content: str,
    source_span: Any,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "runtime_chunk_id": chunk_id,
        "document_id": document.document_id,
        "content_sha256": sha256_text(content),
        "provenance_status": "missing",
        "canonical_objects": [],
        "structure": {
            "metadata_status": "missing",
            "missing_fields": ["verified_source_span", "canonical_object_mapping"],
            "section_ids": [],
            "canonical_object_count": 0,
        },
    }
    span = normalize_source_span(source_span)
    if span is None:
        base["reason"] = "missing_or_malformed_source_span"
        return base
    start, end = span
    base["source_span"] = {"start": start, "end": end}
    if end > len(source):
        base["reason"] = "source_span_out_of_bounds"
        return base
    witness = source[start:end]
    base["source_witness_sha256"] = sha256_text(witness)
    if witness != content:
        base["reason"] = "runtime_content_source_witness_mismatch"
        return base
    mappings = document.intersect(start, end)
    base["canonical_objects"] = mappings
    if not mappings:
        base["reason"] = "no_canonical_object_overlap"
        base["structure"] = {
            "metadata_status": "missing",
            "missing_fields": ["canonical_object_mapping"],
            "section_ids": [],
            "canonical_object_count": 0,
        }
        return base
    base["provenance_status"] = (
        "full" if any(item["coverage"] == "full" for item in mappings) else "partial"
    )
    base["structure"] = document.structure_for_span(start, end, mappings)
    return base


def build_provenance_manifest(
    *,
    documents: dict[str, CanonicalDocumentMap],
    sources: dict[str, str],
    document_by_file: dict[str, str],
    stored_chunks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    runtime_chunks: dict[str, dict[str, Any]] = {}
    object_to_runtime_chunks: dict[str, list[dict[str, Any]]] = {}
    for chunk_id in sorted(stored_chunks):
        record = stored_chunks[chunk_id]
        file_name = Path(str(record.get("file_path") or "")).name
        document_id = document_by_file.get(file_name)
        if document_id is None or document_id not in documents:
            continue
        mapping = runtime_chunk_mapping(
            chunk_id=chunk_id,
            document=documents[document_id],
            source=sources[document_id],
            content=str(record.get("content") or ""),
            source_span=record.get("source_span"),
        )
        token_count = record.get("tokens")
        if isinstance(token_count, int) and not isinstance(token_count, bool):
            mapping["runtime_token_count"] = token_count
        else:
            mapping["runtime_token_count"] = None
        runtime_chunks[chunk_id] = mapping
        for item in mapping["canonical_objects"]:
            object_to_runtime_chunks.setdefault(item["object_id"], []).append(
                {
                    "runtime_chunk_id": chunk_id,
                    "coverage": item["coverage"],
                    "overlap_span": item["overlap_span"],
                }
            )
    for values in object_to_runtime_chunks.values():
        values.sort(key=lambda item: item["runtime_chunk_id"])
    return {
        "schema_version": MAP_SCHEMA_VERSION,
        "documents": {key: documents[key].as_dict() for key in sorted(documents)},
        "runtime_chunks": runtime_chunks,
        "object_to_runtime_chunks": {
            key: object_to_runtime_chunks[key]
            for key in sorted(object_to_runtime_chunks)
        },
    }


def write_provenance_manifest(path: Path, manifest: dict[str, Any]) -> str:
    payload = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    path.write_bytes(payload)
    return sha256_bytes(payload)


def normalize_source_span(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    start = value.get("start")
    end = value.get("end")
    if (
        not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
        or start < 0
        or end <= start
    ):
        return None
    return start, end


def _build_canonical_structure(
    records: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Build a document graph exclusively from canonicalizer-v1 fields.

    This is deliberately independent of execution text.  The canonicalizer
    owns heading levels, body order, section membership, and table topology;
    this bridge only preserves and relates those fields.
    """

    by_id = {
        str(record.get("object_id")): record
        for record in records
        if isinstance(record.get("object_id"), str) and record["object_id"]
    }
    section_records = [
        record for record in records if record.get("object_type") == "section"
    ]
    root_sections = [
        record
        for record in section_records
        if not isinstance(_heading_level(record), int)
    ]
    root_id = str(root_sections[0].get("object_id")) if root_sections else None
    heading_sections = sorted(
        (
            record
            for record in section_records
            if _body_ordinal(record) is not None
            and _heading_level(record) is not None
        ),
        key=lambda record: (_body_ordinal(record) or -1, str(record.get("object_id"))),
    )

    section_specs: dict[str, dict[str, Any]] = {}
    if root_id is not None:
        section_specs[root_id] = {
            "section_id": root_id,
            "heading_path": None,
            "parent_section_id": None,
            "heading_level": None,
            "document_order": None,
            "section_role": "document_body",
            "metadata_status": "partial",
            "missing_fields": ["heading_level", "document_order"],
        }
    stack: dict[int, str] = {}
    for record in heading_sections:
        section_id = str(record.get("object_id"))
        level = _heading_level(record)
        order = _body_ordinal(record)
        title = str(record.get("canonical_value") or "").strip()
        if not isinstance(level, int) or order is None:
            continue
        parent = next(
            (stack[key] for key in sorted(stack, reverse=True) if key < level),
            root_id,
        )
        parent_path = (
            str(section_specs[parent].get("heading_path") or "")
            if parent in section_specs
            else ""
        )
        path = " → ".join(value for value in (parent_path, title) if value)
        missing = [] if title else ["heading_title"]
        section_specs[section_id] = {
            "section_id": section_id,
            "heading_path": path or None,
            "parent_section_id": parent,
            "heading_level": level,
            "document_order": order,
            "section_role": "section",
            "metadata_status": "complete" if not missing else "partial",
            "missing_fields": missing,
        }
        stack[level] = section_id
        for nested in tuple(stack):
            if nested > level:
                del stack[nested]

    section_by_body = {
        _body_ordinal(record): str(record.get("object_id"))
        for record in heading_sections
        if _body_ordinal(record) is not None
    }
    block_sections: dict[str, str | None] = {}
    table_sections: dict[str, str | None] = {}
    row_by_table_position: dict[tuple[str, int], str] = {}
    for record in records:
        object_id = str(record.get("object_id") or "")
        locator = _structural_locator(record)
        object_type = str(record.get("object_type") or "")
        if object_type == "block":
            section_id = (
                section_by_body.get(_body_ordinal(record))
                if record.get("block_kind") == "heading"
                else _text_or_none(locator.get("section_id"))
            )
            block_sections[object_id] = section_id
        elif object_type == "table":
            table_sections[object_id] = _text_or_none(locator.get("section_id"))
        elif object_type == "row":
            table_id = _text_or_none(record.get("table_id")) or _text_or_none(
                locator.get("table_id")
            )
            row = locator.get("row")
            if table_id is not None and isinstance(row, int):
                row_by_table_position[(table_id, row)] = object_id

    structures: dict[str, dict[str, Any]] = {}
    role_by_block_kind = {
        "heading": "heading",
        "paragraph": "paragraph",
        "caption": "caption",
        "list_item": "list_item",
    }
    for object_id, record in by_id.items():
        locator = _structural_locator(record)
        object_type = str(record.get("object_type") or "")
        document_order = _body_ordinal(record)
        section_id: str | None
        parent_object_id: str | None
        table_id = _text_or_none(record.get("table_id")) or _text_or_none(
            locator.get("table_id")
        )
        row_id = _text_or_none(record.get("row_id"))
        row_number = locator.get("row")
        column_number = locator.get("column")
        if object_type == "section":
            section_id = object_id
            parent_object_id = _text_or_none(
                section_specs.get(object_id, {}).get("parent_section_id")
            )
        elif object_type == "block":
            section_id = block_sections.get(object_id)
            if record.get("block_kind") == "heading" and section_id in section_specs:
                parent_object_id = _text_or_none(
                    section_specs[section_id].get("parent_section_id")
                )
            else:
                parent_object_id = section_id
        elif object_type == "text_span":
            parent_object_id = _text_or_none(record.get("block_id")) or _text_or_none(
                locator.get("block_id")
            )
            section_id = block_sections.get(parent_object_id or "")
        elif object_type == "table":
            section_id = table_sections.get(object_id)
            parent_object_id = section_id
            table_id = object_id
        elif object_type == "row":
            section_id = table_sections.get(table_id or "")
            parent_object_id = table_id
            row_id = object_id
        elif object_type == "cell":
            section_id = table_sections.get(table_id or "")
            if table_id is not None and isinstance(row_number, int):
                parent_object_id = row_by_table_position.get((table_id, row_number))
            else:
                parent_object_id = None
        else:
            section_id = _text_or_none(locator.get("section_id"))
            parent_object_id = section_id

        section = section_specs.get(section_id or "")
        missing: list[str] = []
        if document_order is None and object_type not in {"document", "section"}:
            missing.append("document_order")
        if section is None:
            missing.append("section_mapping")
        elif section.get("metadata_status") != "complete":
            missing.append("complete_section_metadata")
        role = role_by_block_kind.get(
            str(record.get("block_kind") or ""),
            {
                "section": "section",
                "table": "table",
                "row": "table_row",
                "cell": "table_cell",
            }.get(object_type, object_type or "unknown"),
        )
        structures[object_id] = {
            "metadata_status": "complete" if not missing else "partial",
            "missing_fields": missing,
            "document_order": document_order,
            "section_id": section_id,
            "heading_path": section.get("heading_path") if section else None,
            "parent_section_id": section.get("parent_section_id") if section else None,
            "section_role": section.get("section_role") if section else None,
            "object_role": role,
            "parent_object_id": parent_object_id,
            "table_id": table_id,
            "row_id": row_id,
            "table_row_index": row_number if isinstance(row_number, int) else None,
            "table_column_index": (
                column_number if isinstance(column_number, int) else None
            ),
        }

    sibling_groups: dict[str, list[str]] = {}
    for object_id, structure in structures.items():
        parent = _text_or_none(structure.get("parent_object_id"))
        if parent is not None and parent != object_id:
            sibling_groups.setdefault(parent, []).append(object_id)
    role_order = {
        "section": 0,
        "heading": 1,
        "paragraph": 2,
        "list_item": 3,
        "table": 4,
        "caption": 5,
        "table_row": 6,
        "table_cell": 7,
    }
    for siblings in sibling_groups.values():
        siblings.sort(
            key=lambda object_id: (
                structures[object_id].get("document_order")
                if isinstance(structures[object_id].get("document_order"), int)
                else 10**12,
                role_order.get(str(structures[object_id].get("object_role")), 99),
                object_id,
            )
        )
        for index, object_id in enumerate(siblings):
            structures[object_id].update(
                {
                    "sibling_index": index,
                    "sibling_count": len(siblings),
                    "preceding_sibling_object_id": (
                        siblings[index - 1] if index else None
                    ),
                    "following_sibling_object_id": (
                        siblings[index + 1]
                        if index + 1 < len(siblings)
                        else None
                    ),
                }
            )
    return structures, section_specs


def _materialize_sections(
    section_specs: dict[str, dict[str, Any]],
    objects: list[CanonicalObjectSpan],
    source: str,
) -> list[dict[str, Any]]:
    """Attach exact execution spans to canonical section hierarchy entries."""

    source_length = len(source)
    heading_spans = {
        item.object_id: (
            source.rfind("\n", 0, item.start) + 1,
            item.end,
        )
        for item in objects
        if item.object_type == "section" and item.object_id in section_specs
    }
    ordered = sorted(
        heading_spans,
        key=lambda object_id: (heading_spans[object_id][0], object_id),
    )
    first_heading_start = heading_spans[ordered[0]][0] if ordered else source_length
    sections: list[dict[str, Any]] = []
    for section_id, spec in sorted(
        section_specs.items(),
        key=lambda item: (
            item[1].get("document_order")
            if isinstance(item[1].get("document_order"), int)
            else -1,
            item[0],
        ),
    ):
        value = dict(spec)
        span = heading_spans.get(section_id)
        if span is None:
            if value.get("section_role") == "document_body":
                value["active_source_span"] = {"start": 0, "end": first_heading_start}
            else:
                value["metadata_status"] = "partial"
                value["missing_fields"] = sorted(
                    set(value.get("missing_fields") or []) | {"source_span"}
                )
            sections.append(value)
            continue
        position = ordered.index(section_id)
        next_start = (
            heading_spans[ordered[position + 1]][0]
            if position + 1 < len(ordered)
            else source_length
        )
        value["source_span"] = {"start": span[0], "end": span[1]}
        value["active_source_span"] = {"start": span[0], "end": next_start}
        sections.append(value)
    return sections


def _structural_locator(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("structural_locator")
    return value if isinstance(value, dict) else {}


def _heading_level(record: dict[str, Any]) -> int | None:
    value = _structural_locator(record).get("heading_level")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _text_or_none(value: Any) -> str | None:
    return str(value) if isinstance(value, str) and value else None


def _align_canonicalizer_v1(
    source: str,
    records: list[dict[str, Any]],
    structures: dict[str, dict[str, Any]],
) -> tuple[list[CanonicalObjectSpan], list[dict[str, str]]]:
    aligned: dict[str, CanonicalObjectSpan] = {}
    diagnostics: list[dict[str, str]] = []
    lines = _source_lines(source)
    lines_by_text: dict[str, list[tuple[int, int]]] = {}
    for text, start, end in lines:
        lines_by_text.setdefault(text, []).append((start, end))
    records_by_type: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        records_by_type.setdefault(str(record.get("object_type") or ""), []).append(
            record
        )

    sections_by_body = {
        _body_ordinal(record): record
        for record in records_by_type.get("section", [])
        if _body_ordinal(record) is not None
    }
    blocks_by_body: dict[int, dict[str, Any]] = {}
    cursor = 0
    for record in sorted(
        records_by_type.get("block", []),
        key=lambda item: (_body_ordinal(item) or -1, str(item.get("object_id"))),
    ):
        if record.get("status") == "unsupported":
            _diagnose(diagnostics, record, "unsupported_object")
            continue
        body_ordinal = _body_ordinal(record)
        if body_ordinal is not None:
            blocks_by_body[body_ordinal] = record
        value = str(record.get("canonical_value") or "")
        expected = _rendered_block_line(record, sections_by_body.get(body_ordinal))
        matches = lines_by_text.get(expected, [])
        match = next((item for item in matches if item[0] >= cursor), None)
        if match is None or not value:
            _diagnose(diagnostics, record, "execution_line_not_found")
            continue
        line_start, line_end = match
        relative = expected.find(value)
        if relative < 0:
            _diagnose(diagnostics, record, "canonical_value_not_in_execution_line")
            continue
        _add_span(
            aligned,
            record,
            source,
            line_start + relative,
            line_start + relative + len(value),
            "canonicalizer_v1_block_line",
            structures,
        )
        cursor = line_end

    for record in records_by_type.get("text_span", []):
        block_id = str(record.get("block_id") or "")
        parent = aligned.get(block_id)
        if parent is None:
            _diagnose(diagnostics, record, "parent_block_not_aligned")
            continue
        _copy_span(
            aligned,
            record,
            source,
            parent,
            "canonicalizer_v1_text_span",
            structures,
        )
    for record in records_by_type.get("section", []):
        body_ordinal = _body_ordinal(record)
        block = blocks_by_body.get(body_ordinal) if body_ordinal is not None else None
        parent = aligned.get(str(block.get("object_id"))) if block else None
        if parent is None:
            _diagnose(diagnostics, record, "section_heading_not_aligned")
            continue
        _copy_span(
            aligned,
            record,
            source,
            parent,
            "canonicalizer_v1_section_heading",
            structures,
        )

    table_records = records_by_type.get("table", [])
    rows = records_by_type.get("row", [])
    cells = records_by_type.get("cell", [])
    for table in table_records:
        _align_table(source, table, rows, cells, aligned, diagnostics, structures)

    for object_type, prefix in (("figure", "Figure: "), ("equation", "Equation: ")):
        for record in records_by_type.get(object_type, []):
            if record.get("status") == "unsupported":
                _diagnose(diagnostics, record, "unsupported_object")
                continue
            value = str(record.get("canonical_value") or "")
            matches = lines_by_text.get(prefix + value, [])
            if len(matches) != 1 or not value:
                _diagnose(diagnostics, record, "rich_object_line_not_unique")
                continue
            start = matches[0][0] + len(prefix)
            _add_span(
                aligned,
                record,
                source,
                start,
                start + len(value),
                "canonicalizer_v1_rich_object_line",
                structures,
            )

    for object_type in ("reference", "note"):
        for record in records_by_type.get(object_type, []):
            if record.get("status") == "unsupported":
                _diagnose(diagnostics, record, "unsupported_object")
                continue
            body_ordinal = _body_ordinal(record)
            block = (
                blocks_by_body.get(body_ordinal) if body_ordinal is not None else None
            )
            parent = aligned.get(str(block.get("object_id"))) if block else None
            value = str(record.get("canonical_value") or "")
            if parent is None or not value:
                _diagnose(diagnostics, record, "body_anchor_not_aligned")
                continue
            parent_text = source[parent.start : parent.end]
            relative = parent_text.find(value)
            if relative < 0 or parent_text.find(value, relative + 1) >= 0:
                _diagnose(diagnostics, record, "anchored_value_not_unique")
                continue
            _add_span(
                aligned,
                record,
                source,
                parent.start + relative,
                parent.start + relative + len(value),
                "canonicalizer_v1_body_anchor",
                structures,
            )

    return (
        sorted(
            aligned.values(), key=lambda item: (item.start, item.end, item.object_id)
        ),
        sorted(diagnostics, key=lambda item: (item["object_id"], item["reason"])),
    )


def _align_table(
    source: str,
    table: dict[str, Any],
    rows: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    aligned: dict[str, CanonicalObjectSpan],
    diagnostics: list[dict[str, str]],
    structures: dict[str, dict[str, Any]],
) -> None:
    table_id = str(table.get("object_id") or "")
    width = table.get("column_count")
    row_count = table.get("row_count")
    if not isinstance(width, int) or width < 1 or not isinstance(row_count, int):
        _diagnose(diagnostics, table, "invalid_table_shape")
        return
    table_cells = [record for record in cells if record.get("table_id") == table_id]
    values = [["" for _ in range(width)] for _ in range(row_count)]
    cell_by_position: dict[tuple[int, int], dict[str, Any]] = {}
    for cell in table_cells:
        row = cell.get("row")
        column = cell.get("column")
        if not isinstance(row, int) or not isinstance(column, int):
            continue
        if 1 <= row <= row_count and 1 <= column <= width:
            values[row - 1][column - 1] = str(cell.get("canonical_value") or "")
            cell_by_position[(row, column)] = cell
    rendered_rows = [_render_table_row(row) for row in values]
    if not rendered_rows:
        _diagnose(diagnostics, table, "empty_table")
        return
    separator = "| " + " | ".join("---" for _ in range(width)) + " |"
    rendered_lines = [rendered_rows[0], separator, *rendered_rows[1:]]
    rendered = "\n".join(rendered_lines)
    first = source.find(rendered)
    if first < 0 or source.find(rendered, first + 1) >= 0:
        _diagnose(diagnostics, table, "table_rendering_not_unique")
        return
    _add_span(
        aligned,
        table,
        source,
        first,
        first + len(rendered),
        "canonicalizer_v1_table_rendering",
        structures,
    )
    rows_by_number = {
        record.get("row"): record
        for record in rows
        if record.get("table_id") == table_id
    }
    line_offsets: list[int] = []
    offset = 0
    for line in rendered_lines:
        line_offsets.append(offset)
        offset += len(line) + 1
    for row_number, rendered_row in enumerate(rendered_rows, start=1):
        line_index = 0 if row_number == 1 else row_number
        row_start = first + line_offsets[line_index]
        row_record = rows_by_number.get(row_number)
        if row_record is not None:
            _add_span(
                aligned,
                row_record,
                source,
                row_start,
                row_start + len(rendered_row),
                "canonicalizer_v1_table_row",
                structures,
            )
        value_offset = 2
        for column, value in enumerate(values[row_number - 1], start=1):
            rendered_value = value.replace("|", "\\|")
            cell = cell_by_position.get((row_number, column))
            if cell is not None and rendered_value:
                _add_span(
                    aligned,
                    cell,
                    source,
                    row_start + value_offset,
                    row_start + value_offset + len(rendered_value),
                    "canonicalizer_v1_table_cell",
                    structures,
                )
            value_offset += len(rendered_value)
            if column < width:
                value_offset += 3


def _rendered_block_line(block: dict[str, Any], section: dict[str, Any] | None) -> str:
    value = str(block.get("canonical_value") or "")
    kind = block.get("block_kind")
    if kind == "heading" and section is not None:
        locator = section.get("structural_locator")
        level = locator.get("heading_level") if isinstance(locator, dict) else None
        if isinstance(level, int) and 1 <= level <= 9:
            return "#" * level + " " + value
    if kind == "list_item":
        return "- " + value
    return value


def _render_table_row(values: list[str]) -> str:
    return "| " + " | ".join(value.replace("|", "\\|") for value in values) + " |"


def _source_lines(source: str) -> list[tuple[str, int, int]]:
    values: list[tuple[str, int, int]] = []
    cursor = 0
    for line in source.splitlines(keepends=True):
        text = line.rstrip("\r\n")
        values.append((text, cursor, cursor + len(text)))
        cursor += len(line)
    if source and not source.endswith(("\n", "\r")):
        return values
    return values


def _body_ordinal(record: dict[str, Any]) -> int | None:
    locator = record.get("structural_locator")
    value = locator.get("body_ordinal") if isinstance(locator, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _locator(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("object_type") == "cell":
        return {
            "type": "table_cell",
            "table_id": str(record.get("table_id") or ""),
            "row": record.get("row"),
            "column": record.get("column"),
        }
    return {
        "type": "object",
        "object_type": str(record.get("object_type") or ""),
        "object_id": str(record.get("object_id") or ""),
    }


def _add_span(
    aligned: dict[str, CanonicalObjectSpan],
    record: dict[str, Any],
    source: str,
    start: int,
    end: int,
    method: str,
    structures: dict[str, dict[str, Any]],
) -> None:
    object_id = str(record.get("object_id") or "")
    if not object_id or start < 0 or end <= start or end > len(source):
        return
    aligned[object_id] = CanonicalObjectSpan(
        object_id=object_id,
        object_type=str(record.get("object_type") or ""),
        status=str(record.get("status") or ""),
        start=start,
        end=end,
        locator=_locator(record),
        witness_sha256=sha256_text(source[start:end]),
        alignment_method=method,
        structure=dict(
            structures.get(
                object_id,
                {
                    "metadata_status": "missing",
                    "missing_fields": ["canonical_structure"],
                },
            )
        ),
    )


def _copy_span(
    aligned: dict[str, CanonicalObjectSpan],
    record: dict[str, Any],
    source: str,
    parent: CanonicalObjectSpan,
    method: str,
    structures: dict[str, dict[str, Any]],
) -> None:
    _add_span(
        aligned,
        record,
        source,
        parent.start,
        parent.end,
        method,
        structures,
    )


def _diagnose(
    diagnostics: list[dict[str, str]], record: dict[str, Any], reason: str
) -> None:
    diagnostics.append(
        {"object_id": str(record.get("object_id") or ""), "reason": reason}
    )
