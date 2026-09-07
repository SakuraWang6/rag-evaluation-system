"""Publisher and reader for ``rag-benchmark-contract/1`` packages.

The publisher consumes an immutable Bundle 2.0 runtime projection but never
changes it.  The resulting package contains the one canonical leaf corpus used
by every compliant RAG Adapter and the segment-native Gold used by the new
retrieval evaluator.
"""

from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from rag_eval.contracts.benchmark import (
    BENCHMARK_CONTRACT_SCHEMA_VERSION,
    MAX_ENVELOPED_SEGMENT_CHARACTERS,
    BenchmarkContractError,
    BenchmarkDataset,
    BenchmarkGold,
    BenchmarkManifest,
    BenchmarkPresentationLocation,
    BenchmarkQuestion,
    BenchmarkSegment,
    BenchmarkSegmentationPolicy,
    benchmark_json,
    benchmark_sha256,
    render_benchmark_segment,
)
from rag_eval.contracts.adapter import DocumentInput
from rag_eval.contracts.dataset import (
    GoldEvidence,
    ObjectLocator,
    TableCellLocator,
)
from rag_eval.datasets.bundle import DatasetBundle
from rag_eval.storage.atomic import atomic_write_bytes, atomic_write_json


BENCHMARK_MANIFEST_NAME = "manifest.json"
BENCHMARK_SEGMENTS_NAME = "segments.jsonl"
BENCHMARK_QUESTIONS_NAME = "questions.jsonl"
BENCHMARK_GOLD_NAME = "gold.jsonl"
BENCHMARK_RUNTIME_REFERENCE_NAME = "benchmark-contract-reference.json"
_CONTRACT_FILES = (
    BENCHMARK_SEGMENTS_NAME,
    BENCHMARK_QUESTIONS_NAME,
    BENCHMARK_GOLD_NAME,
)
_ROOT_TYPES = {
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
_CELL_TYPES = {"cell", "table_cell", "logical_cell"}


def formal_release_benchmark_contract_path(release_root: Path, release_id: str) -> Path:
    """Return the stable v1 artifact location beside immutable Releases."""

    safe_release_id = "".join(
        character
        for character in release_id
        if character.isascii() and (character.isalnum() or character in {"_", "-"})
    )
    if not safe_release_id or safe_release_id != release_id:
        raise BenchmarkContractError("benchmark release ID is not safe")
    return (
        release_root
        / "benchmark-contracts"
        / safe_release_id
        / "rag-benchmark-contract-1"
    )


@dataclass(frozen=True, slots=True)
class _SourceLeaf:
    segment_id: str
    start: int
    end: int
    source_text: str


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def _comparison_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _jsonl(values: Iterable[object]) -> bytes:
    rows: list[str] = []
    for value in values:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        rows.append(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return ("\n".join(rows) + "\n").encode("utf-8")


def _record_attributes(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("attributes")
    return value if isinstance(value, Mapping) else {}


def _record_field(record: Mapping[str, Any], name: str) -> Any:
    if name in record:
        return record[name]
    return _record_attributes(record).get(name)


def _record_text(record: Mapping[str, Any]) -> str:
    for name in ("canonical_value", "value", "text"):
        value = record.get(name)
        if isinstance(value, str):
            return _normalize(value)
    return ""


def _sort_key(value: object) -> tuple[int, str]:
    if isinstance(value, int) and not isinstance(value, bool):
        return (0, f"{value:020d}")
    return (1, str(value))


def _canonical_records(bundle: DatasetBundle) -> dict[str, list[dict[str, Any]]]:
    values: dict[str, list[dict[str, Any]]] = {}
    for document in bundle.manifest.documents:
        if document.canonical_path is None:
            raise BenchmarkContractError(
                f"document {document.document_id!r} has no canonical source"
            )
        path = bundle.root / document.canonical_path
        if not path.is_file():
            raise BenchmarkContractError(
                f"canonical source is missing for document {document.document_id!r}"
            )
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BenchmarkContractError(
                    f"{document.canonical_path}:{line_number} is not valid JSON"
                ) from exc
            if not isinstance(raw, dict):
                raise BenchmarkContractError(
                    f"{document.canonical_path}:{line_number} is not an object"
                )
            if raw.get("document_id") != document.document_id:
                raise BenchmarkContractError(
                    f"canonical record {line_number} has the wrong document ID"
                )
            if not isinstance(raw.get("object_id"), str) or not raw["object_id"]:
                raise BenchmarkContractError(
                    f"canonical record {line_number} lacks object_id"
                )
            if not isinstance(raw.get("object_type"), str) or not raw["object_type"]:
                raise BenchmarkContractError(
                    f"canonical record {line_number} lacks object_type"
                )
            records.append(raw)
        if not records:
            raise BenchmarkContractError(
                f"canonical source for {document.document_id!r} is empty"
            )
        identifiers = [str(item["object_id"]) for item in records]
        if len(identifiers) != len(set(identifiers)):
            raise BenchmarkContractError(
                f"canonical source for {document.document_id!r} repeats object IDs"
            )
        values[document.document_id] = records
    return values


def _presentation_locations(record: Mapping[str, Any]) -> tuple[BenchmarkPresentationLocation, ...]:
    provenance = record.get("provenance")
    if not isinstance(provenance, Mapping):
        return ()
    raw_spans = provenance.get("source_spans")
    if not isinstance(raw_spans, list):
        return ()
    locations: list[BenchmarkPresentationLocation] = []
    for span in raw_spans:
        if not isinstance(span, Mapping):
            continue
        coordinate_system = span.get("coordinate_system")
        coordinates = span.get("coordinates")
        if isinstance(coordinate_system, str) and isinstance(coordinates, Mapping):
            safe = {
                str(key): value
                for key, value in coordinates.items()
                if isinstance(value, (str, int, float, bool))
            }
            locations.append(
                BenchmarkPresentationLocation(
                    coordinate_system=coordinate_system,
                    coordinates=safe,
                )
            )
    return tuple(locations)


def _lineage(record: Mapping[str, Any]) -> dict[str, Any]:
    provenance = record.get("provenance")
    derived: list[str] = []
    if isinstance(provenance, Mapping):
        raw = provenance.get("derived_from_object_ids")
        if isinstance(raw, list):
            derived = [value for value in raw if isinstance(value, str)]
    attributes = _record_attributes(record)
    return {
        "canonical_object_id": str(record["object_id"]),
        "canonical_object_type": str(record["object_type"]),
        "derived_from_object_ids": sorted(set(derived)),
        "table_id": _record_field(record, "table_id"),
        "row": _record_field(record, "row"),
        "column": _record_field(record, "column"),
        "parent_object_id": attributes.get("parent_object_id"),
    }


def _split_preserving_text(value: str, maximum: int) -> list[tuple[int, int, str]]:
    """Split normalized source text without dropping or rewriting a character."""

    if maximum < 1:
        raise BenchmarkContractError("segment prefix leaves no room for source content")
    if not value:
        return []
    values: list[tuple[int, int, str]] = []
    start = 0
    boundaries = frozenset("\n。！？；.!?;，,、：:")
    while start < len(value):
        remaining = len(value) - start
        if remaining <= maximum:
            values.append((start, len(value), value[start:]))
            break
        ceiling = start + maximum
        split_at = max(
            (index + 1 for index in range(start, ceiling) if value[index] in boundaries),
            default=ceiling,
        )
        if split_at <= start:
            split_at = ceiling
        values.append((start, split_at, value[start:split_at]))
        start = split_at
    if "".join(item[2] for item in values) != value:
        raise AssertionError("deterministic splitter lost source content")
    return values


def _segment_prefix(
    structure_type: str,
    *,
    table_id: object | None = None,
    row: object | None = None,
    column: object | None = None,
    row_header: str | None = None,
    column_header: str | None = None,
) -> str:
    if structure_type != "table_cell":
        return f"【{structure_type}】\n"
    lines = ["【table-cell】", f"table: {table_id}", f"row: {row}", f"column: {column}"]
    if row_header:
        lines.append(f"row_header: {row_header}")
    if column_header:
        lines.append(f"column_header: {column_header}")
    lines.append("value:")
    return "\n".join(lines) + "\n"


def _leaf_segments(
    *,
    dataset_id: str,
    version: str,
    document_id: str,
    root_object_id: str,
    structure_type: str,
    source_object_ids: tuple[str, ...],
    source_text: str,
    prefix: str,
    ordinal_start: int,
    lineage: dict[str, Any],
    presentation_locations: tuple[BenchmarkPresentationLocation, ...],
) -> tuple[list[BenchmarkSegment], list[_SourceLeaf]]:
    # ``segment-`` plus a SHA-256 hex digest is a fixed-size stable ID.
    probe_id = "segment-" + "0" * 64
    envelope_overhead = len(f"[[RAG_BENCHMARK_SEGMENT id={probe_id}]]\n")
    pieces = _split_preserving_text(
        source_text,
        MAX_ENVELOPED_SEGMENT_CHARACTERS - envelope_overhead - len(prefix),
    )
    if not pieces:
        return [], []
    parent_id = None
    if len(pieces) > 1:
        parent_id = "segment-parent-" + benchmark_sha256(
            "\0".join(
                (
                    BENCHMARK_CONTRACT_SCHEMA_VERSION,
                    dataset_id,
                    version,
                    document_id,
                    root_object_id,
                    benchmark_sha256(source_text),
                )
            )
        )
    segments: list[BenchmarkSegment] = []
    source_leaves: list[_SourceLeaf] = []
    for child_ordinal, (start, end, piece) in enumerate(pieces):
        content = prefix + piece
        content_digest = benchmark_sha256(content)
        segment_id = "segment-" + benchmark_sha256(
            "\0".join(
                (
                    BENCHMARK_CONTRACT_SCHEMA_VERSION,
                    dataset_id,
                    version,
                    document_id,
                    root_object_id,
                    str(child_ordinal),
                    content_digest,
                )
            )
        )
        value = BenchmarkSegment(
            segment_id=segment_id,
            parent_segment_id=parent_id,
            document_id=document_id,
            root_object_id=root_object_id,
            structure_type=structure_type,
            source_object_ids=source_object_ids,
            ordinal=ordinal_start + child_ordinal,
            content=content,
            content_sha256=content_digest,
            lineage={
                **lineage,
                "source_start": start,
                "source_end": end,
                "child_ordinal": child_ordinal,
                "child_count": len(pieces),
            },
            presentation_locations=presentation_locations,
        )
        segments.append(value)
        source_leaves.append(
            _SourceLeaf(
                segment_id=segment_id,
                start=start,
                end=end,
                source_text=source_text,
            )
        )
    return segments, source_leaves


def _table_cell_context(
    record: Mapping[str, Any],
    cells: Mapping[tuple[str, object, object], Mapping[str, Any]],
) -> tuple[str, str, str, tuple[str, ...]]:
    table_id = str(_record_field(record, "table_id") or "")
    row = _record_field(record, "row")
    column = _record_field(record, "column")
    in_table = [key for key in cells if key[0] == table_id]
    rows = sorted({key[1] for key in in_table}, key=_sort_key)
    columns = sorted({key[2] for key in in_table}, key=_sort_key)
    header_row = rows[0] if rows else row
    header_column = columns[0] if columns else column
    column_record = cells.get((table_id, header_row, column))
    row_record = cells.get((table_id, row, header_column))
    column_header = _record_text(column_record) if column_record else ""
    row_header = _record_text(row_record) if row_record else ""
    source_object_ids = tuple(
        dict.fromkeys(
            object_id
            for candidate in (record, row_record, column_record)
            if candidate is not None
            and isinstance((object_id := candidate.get("object_id")), str)
            and object_id
        )
    )
    return table_id, row_header, column_header, source_object_ids


def _build_segments(
    *,
    bundle: DatasetBundle,
    dataset_id: str,
    version: str,
) -> tuple[tuple[BenchmarkSegment, ...], dict[str, list[_SourceLeaf]], dict[str, dict[str, Any]]]:
    records_by_document = _canonical_records(bundle)
    segments: list[BenchmarkSegment] = []
    # The map deliberately includes both retrievable leaves' direct canonical
    # objects and their structural table/row ancestors.  A legacy Gold locator
    # can name a table as one logical fact; its vNext projection must then
    # explicitly require the child table-cell leaves rather than invent a
    # table-sized retrieval chunk.
    leaves_by_object: dict[str, list[_SourceLeaf]] = defaultdict(list)
    records_by_object: dict[str, dict[str, Any]] = {}
    ordinal = 0
    for document_id in sorted(records_by_document):
        records = records_by_document[document_id]
        records_by_object.update({str(item["object_id"]): item for item in records})
        cells: dict[tuple[str, object, object], dict[str, Any]] = {}
        for record in records:
            if record.get("object_type") not in _CELL_TYPES:
                continue
            table_id = _record_field(record, "table_id")
            row = _record_field(record, "row")
            column = _record_field(record, "column")
            if isinstance(table_id, str) and row is not None and column is not None:
                cells[(table_id, row, column)] = record

        consumed: set[str] = set()
        leaves_by_table: dict[str, list[_SourceLeaf]] = defaultdict(list)
        leaves_by_table_row: dict[tuple[str, object], list[_SourceLeaf]] = defaultdict(list)
        for key, record in sorted(
            cells.items(), key=lambda item: (_sort_key(item[0][1]), _sort_key(item[0][2]), item[0][0])
        ):
            text = _record_text(record)
            if not text:
                continue
            object_id = str(record["object_id"])
            table_id, row_header, column_header, source_object_ids = _table_cell_context(
                record, cells
            )
            leaf_segments, leaves = _leaf_segments(
                dataset_id=dataset_id,
                version=version,
                document_id=document_id,
                root_object_id=object_id,
                structure_type="table_cell",
                source_object_ids=source_object_ids,
                source_text=text,
                prefix=_segment_prefix(
                    "table_cell",
                    table_id=table_id,
                    row=_record_field(record, "row"),
                    column=_record_field(record, "column"),
                    row_header=row_header,
                    column_header=column_header,
                ),
                ordinal_start=ordinal,
                lineage=_lineage(record),
                presentation_locations=_presentation_locations(record),
            )
            segments.extend(leaf_segments)
            leaves_by_object[object_id].extend(leaves)
            leaves_by_table[table_id].extend(leaves)
            leaves_by_table_row[(table_id, _record_field(record, "row"))].extend(leaves)
            ordinal += len(leaf_segments)
            consumed.add(object_id)

        # Preserve structural lineage without creating retrievable table or
        # row aggregate chunks.  Their Gold projection becomes an AND of the
        # deterministically ordered child leaves.
        for record in records:
            object_id = str(record["object_id"])
            object_type = str(record.get("object_type") or "")
            if object_type == "table":
                table_id = str(_record_field(record, "table_id") or object_id)
                if leaves_by_table.get(table_id):
                    leaves_by_object[object_id].extend(leaves_by_table[table_id])
            elif object_type == "row":
                table_id = _record_field(record, "table_id")
                row = _record_field(record, "row")
                if isinstance(table_id, str) and leaves_by_table_row.get((table_id, row)):
                    leaves_by_object[object_id].extend(leaves_by_table_row[(table_id, row)])

        for record in records:
            object_type = str(record.get("object_type") or "")
            object_id = str(record["object_id"])
            if object_id in consumed or object_type not in _ROOT_TYPES:
                continue
            text = _record_text(record)
            if not text:
                continue
            leaf_segments, leaves = _leaf_segments(
                dataset_id=dataset_id,
                version=version,
                document_id=document_id,
                root_object_id=object_id,
                structure_type=object_type,
                source_object_ids=(object_id,),
                source_text=text,
                prefix=_segment_prefix(object_type),
                ordinal_start=ordinal,
                lineage=_lineage(record),
                presentation_locations=_presentation_locations(record),
            )
            segments.extend(leaf_segments)
            leaves_by_object[object_id].extend(leaves)
            ordinal += len(leaf_segments)

    if not segments:
        raise BenchmarkContractError("canonical corpus has no retrievable benchmark segments")
    identifiers = [item.segment_id for item in segments]
    if len(identifiers) != len(set(identifiers)):
        raise BenchmarkContractError("benchmark segment IDs are not unique")
    for object_id, leaves in leaves_by_object.items():
        # A cell can be reached directly and through its structural parent.
        # Preserve first occurrence because ordinal is a stable corpus order.
        leaves_by_object[object_id] = list(
            dict.fromkeys(leaves)
        )
    return tuple(segments), leaves_by_object, records_by_object


def _cell_object_id(
    evidence: GoldEvidence,
    records: Mapping[str, Mapping[str, Any]],
) -> str:
    locator = evidence.locator
    if isinstance(locator, ObjectLocator):
        return locator.object_id
    if isinstance(locator, TableCellLocator):
        candidates = [
            object_id
            for object_id, record in records.items()
            if record.get("document_id") == evidence.document_id
            and record.get("object_type") in _CELL_TYPES
            and _record_field(record, "table_id") == locator.table_id
            and _record_field(record, "row") == locator.row
            and _record_field(record, "column") == locator.column
        ]
        if len(candidates) != 1:
            raise BenchmarkContractError(
                f"{evidence.evidence_id}: table-cell locator is not uniquely canonical"
            )
        return candidates[0]
    raise BenchmarkContractError(
        f"{evidence.evidence_id}: Gold locator type has no segment-native projection"
    )


def _gold_segments(
    evidence: GoldEvidence,
    *,
    leaves_by_object: Mapping[str, list[_SourceLeaf]],
    records: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    object_id = _cell_object_id(evidence, records)
    leaves = leaves_by_object.get(object_id, [])
    if not leaves:
        raise BenchmarkContractError(
            f"{evidence.evidence_id}: Gold object has no benchmark leaf segment"
        )
    # Table and row nodes are structural, non-retrievable parents.  Their
    # legacy object locator intentionally projects to every ordered child
    # cell leaf, making the resulting Gold an explicit AND rather than a
    # synthetic aggregate chunk.  A table's own canonical text cannot be used
    # to calculate offsets in one cell, so attempting a witness match here
    # would be both incorrect and unnecessary.
    if isinstance(evidence.locator, ObjectLocator) and evidence.locator.object_type in {
        "table",
        "row",
    }:
        return tuple(item.segment_id for item in leaves)
    if len(leaves) == 1:
        return (leaves[0].segment_id,)
    witness = evidence.canonical_value or evidence.quote_anchor
    if not witness:
        # A full canonical object without a narrower witness genuinely spans
        # all child leaves; preserve that fact as deterministic AND evidence.
        return tuple(item.segment_id for item in leaves)
    source = leaves[0].source_text
    if _comparison_text(witness) == _comparison_text(source):
        return tuple(item.segment_id for item in leaves)
    # This is exact normalized witness matching during *publication*, never a
    # runtime fallback.  It lets a Gold fact whose source object was split map
    # to the one or more children that contain its declared canonical witness.
    normalized_source = _comparison_text(source)
    normalized_witness = _comparison_text(witness)
    if not normalized_witness or normalized_source.count(normalized_witness) != 1:
        raise BenchmarkContractError(
            f"{evidence.evidence_id}: split Gold witness is ambiguous; curate a leaf-level Gold"
        )
    # Whitespace normalization loses exact offsets.  A conservative fallback
    # is safe only when every resulting child would be required; otherwise
    # publishing must stop for curator selection.
    raw_start = source.find(_normalize(witness))
    if raw_start < 0:
        raise BenchmarkContractError(
            f"{evidence.evidence_id}: normalized witness has no exact source range"
        )
    raw_end = raw_start + len(_normalize(witness))
    selected = tuple(
        item.segment_id
        for item in leaves
        if item.start < raw_end and item.end > raw_start
    )
    if not selected:
        raise BenchmarkContractError(
            f"{evidence.evidence_id}: Gold witness is outside published leaf ranges"
        )
    return selected


def _expanded_paths(
    original_paths: Iterable[Iterable[Iterable[str]]],
    evidence_segments: Mapping[str, tuple[str, ...]],
) -> tuple[tuple[tuple[str, ...], ...], ...]:
    """Distribute legacy OR-evidence choices over multi-leaf AND mappings."""

    paths: list[tuple[tuple[str, ...], ...]] = []
    for original_path in original_paths:
        clauses = [tuple(clause) for clause in original_path]
        if not clauses or any(not clause for clause in clauses):
            raise BenchmarkContractError("Gold MSES path has an empty clause")
        for selected in product(*clauses):
            groups: list[tuple[str, ...]] = []
            for evidence_id in selected:
                segment_ids = evidence_segments.get(evidence_id)
                if not segment_ids:
                    raise BenchmarkContractError(
                        f"Gold MSES references evidence without benchmark leaves: {evidence_id}"
                    )
                groups.extend((segment_id,) for segment_id in segment_ids)
            paths.append(tuple(groups))
    unique = tuple(dict.fromkeys(paths))
    if not unique:
        raise BenchmarkContractError("Gold MSES has no benchmark evidence path")
    if len(unique) > 1024:
        raise BenchmarkContractError("Gold MSES expansion exceeds the 1024-path safety limit")
    return unique


def build_benchmark_dataset(
    bundle: DatasetBundle,
    *,
    source_release_id: str | None = None,
    source_release_digest: str | None = None,
) -> BenchmarkDataset:
    """Build, validate, and return an in-memory v1 benchmark package."""

    dataset_id = bundle.bundle_id
    name = bundle.manifest.name
    version = bundle.manifest.version
    segments, leaves_by_object, records = _build_segments(
        bundle=bundle,
        dataset_id=dataset_id,
        version=version,
    )
    questions: list[BenchmarkQuestion] = []
    gold: list[BenchmarkGold] = []
    for question in sorted(bundle.questions, key=lambda item: item.case_id):
        answer = bundle.gold_answers[question.gold_answer_id]
        evidence_set = bundle.gold_evidence_sets[question.gold_evidence_set_id]
        mappings = {
            evidence.evidence_id: _gold_segments(
                evidence,
                leaves_by_object=leaves_by_object,
                records=records,
            )
            for evidence in evidence_set.evidence
        }
        if answer.kind.value == "abstain":
            paths: tuple[tuple[tuple[str, ...], ...], ...] = ()
        else:
            original_paths = evidence_set.mses_paths or [evidence_set.required_groups]
            paths = _expanded_paths(original_paths, mappings)
        gold_id = f"gold-{question.case_id}"
        questions.append(
            BenchmarkQuestion(
                case_id=question.case_id,
                question=question.question,
                gold_id=gold_id,
                tags=tuple(question.tags),
                metadata=dict(question.metadata),
            )
        )
        gold.append(
            BenchmarkGold(
                gold_id=gold_id,
                case_id=question.case_id,
                answer=answer,
                evidence_paths=paths,
                source_evidence_segment_ids={
                    key: tuple(value) for key, value in sorted(mappings.items())
                },
            )
        )
    segment_bytes = _jsonl(segments)
    question_bytes = _jsonl(questions)
    gold_bytes = _jsonl(gold)
    checksums = {
        BENCHMARK_SEGMENTS_NAME: benchmark_sha256(segment_bytes),
        BENCHMARK_QUESTIONS_NAME: benchmark_sha256(question_bytes),
        BENCHMARK_GOLD_NAME: benchmark_sha256(gold_bytes),
    }
    manifest = BenchmarkManifest.build(
        dataset_id=dataset_id,
        name=name,
        version=version,
        source_release_id=source_release_id,
        source_release_digest=source_release_digest,
        corpus_digest=benchmark_sha256(segment_bytes),
        segmentation_policy=BenchmarkSegmentationPolicy(),
        file_checksums=checksums,
        segment_count=len(segments),
        case_count=len(questions),
    )
    _validate_dataset(
        manifest=manifest,
        segments=tuple(segments),
        questions=tuple(questions),
        gold=tuple(gold),
    )
    return BenchmarkDataset(
        root=Path("."),
        manifest=manifest,
        segments=tuple(segments),
        questions=tuple(questions),
        gold=tuple(gold),
    )


def _validate_dataset(
    *,
    manifest: BenchmarkManifest,
    segments: tuple[BenchmarkSegment, ...],
    questions: tuple[BenchmarkQuestion, ...],
    gold: tuple[BenchmarkGold, ...],
) -> None:
    known_segment_ids = {item.segment_id for item in segments}
    if len(known_segment_ids) != len(segments):
        raise BenchmarkContractError("benchmark package repeats segment IDs")
    if any(len(render_benchmark_segment(item)) > manifest.segmentation_policy.max_enveloped_characters for item in segments):
        raise BenchmarkContractError("benchmark package contains an overlong leaf segment")
    question_ids = [item.case_id for item in questions]
    if len(question_ids) != len(set(question_ids)):
        raise BenchmarkContractError("benchmark package repeats case IDs")
    gold_by_id = {item.gold_id: item for item in gold}
    if len(gold_by_id) != len(gold) or set(question_ids) != {item.case_id for item in gold}:
        raise BenchmarkContractError("benchmark questions and Gold records do not match")
    for question in questions:
        if question.gold_id not in gold_by_id:
            raise BenchmarkContractError(f"{question.case_id}: missing benchmark Gold")
    for item in gold:
        unknown = {
            segment_id
            for path in item.evidence_paths
            for clause in path
            for segment_id in clause
            if segment_id not in known_segment_ids
        }
        if unknown:
            raise BenchmarkContractError(
                f"{item.case_id}: Gold references unknown segments: {sorted(unknown)}"
            )
        unknown_source_map = {
            segment_id
            for mapped_segment_ids in item.source_evidence_segment_ids.values()
            for segment_id in mapped_segment_ids
            if segment_id not in known_segment_ids
        }
        if unknown_source_map:
            raise BenchmarkContractError(
                f"{item.case_id}: source Gold mapping references unknown segments: "
                f"{sorted(unknown_source_map)}"
            )


def publish_benchmark_dataset(
    bundle: DatasetBundle,
    root: Path,
    *,
    source_release_id: str | None = None,
    source_release_digest: str | None = None,
) -> BenchmarkDataset:
    """Publish a content-verified contract without modifying the source Bundle."""

    dataset = build_benchmark_dataset(
        bundle,
        source_release_id=source_release_id,
        source_release_digest=source_release_digest,
    )
    root = root.resolve()
    segment_bytes = _jsonl(dataset.segments)
    question_bytes = _jsonl(dataset.questions)
    gold_bytes = _jsonl(dataset.gold)
    expected = {
        BENCHMARK_SEGMENTS_NAME: segment_bytes,
        BENCHMARK_QUESTIONS_NAME: question_bytes,
        BENCHMARK_GOLD_NAME: gold_bytes,
    }
    manifest_path = root / BENCHMARK_MANIFEST_NAME
    if manifest_path.is_file():
        existing = load_benchmark_dataset(root)
        if existing.manifest.contract_digest != dataset.manifest.contract_digest:
            raise BenchmarkContractError(
                "benchmark contract path is immutable; choose a new release directory"
            )
        return existing
    root.mkdir(parents=True, exist_ok=True)
    for name, payload in expected.items():
        atomic_write_bytes(root / name, payload)
    atomic_write_json(root / BENCHMARK_MANIFEST_NAME, dataset.manifest.model_dump(mode="json"))
    return load_benchmark_dataset(root)


def _read_jsonl(path: Path, model: type[Any]) -> tuple[Any, ...]:
    values: list[Any] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            values.append(model.model_validate_json(line))
        except Exception as exc:  # noqa: BLE001
            raise BenchmarkContractError(f"{path.name}:{line_number}: {exc}") from exc
    return tuple(values)


def load_benchmark_dataset(root: Path) -> BenchmarkDataset:
    """Load and verify an immutable benchmark package."""

    root = root.resolve()
    required = (BENCHMARK_MANIFEST_NAME, *_CONTRACT_FILES)
    if any(not (root / name).is_file() for name in required):
        raise BenchmarkContractError("benchmark package is missing a required contract file")
    manifest = BenchmarkManifest.model_validate_json(
        (root / BENCHMARK_MANIFEST_NAME).read_text(encoding="utf-8")
    )
    for name, expected in manifest.file_checksums.items():
        actual = benchmark_sha256((root / name).read_bytes())
        if actual != expected:
            raise BenchmarkContractError(f"benchmark checksum mismatch: {name}")
    segments = _read_jsonl(root / BENCHMARK_SEGMENTS_NAME, BenchmarkSegment)
    questions = _read_jsonl(root / BENCHMARK_QUESTIONS_NAME, BenchmarkQuestion)
    gold = _read_jsonl(root / BENCHMARK_GOLD_NAME, BenchmarkGold)
    if len(segments) != manifest.segment_count or len(questions) != manifest.case_count:
        raise BenchmarkContractError("benchmark manifest counts do not match contract files")
    _validate_dataset(manifest=manifest, segments=segments, questions=questions, gold=gold)
    return BenchmarkDataset(
        root=root,
        manifest=manifest,
        segments=segments,
        questions=questions,
        gold=gold,
    )


def materialize_benchmark_segment_documents(
    dataset: BenchmarkDataset,
    source_dir: Path,
) -> list[DocumentInput]:
    """Stage exactly one immutable leaf as each Adapter ingestion input.

    The runtime reference is deliberately tiny: it pins the externally stored
    immutable contract for reproduction, while the adapter receives inline
    rendered leaf content and can verify every byte after native ingestion.
    No Word/OOXML location is copied into this retrieval-scoring input.
    """

    source_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        source_dir / BENCHMARK_RUNTIME_REFERENCE_NAME,
        {
            "schema_version": BENCHMARK_CONTRACT_SCHEMA_VERSION,
            "contract_digest": dataset.manifest.contract_digest,
            "source_release_id": dataset.manifest.source_release_id,
            "source_release_digest": dataset.manifest.source_release_digest,
            "file_checksums": dataset.manifest.file_checksums,
            "segment_count": len(dataset.segments),
        },
    )
    inputs: list[DocumentInput] = []
    for ordinal, segment in enumerate(sorted(
        dataset.segments,
        key=lambda item: (item.document_id, item.ordinal, item.segment_id),
    )):
        rendered = render_benchmark_segment(segment)
        rendered_sha256 = benchmark_sha256(rendered)
        source_name = f"benchmark-leaf-{ordinal:05d}-{rendered_sha256[:12]}.txt"
        atomic_write_bytes(source_dir / source_name, rendered.encode("utf-8"))
        inputs.append(
            DocumentInput(
                document_id=segment.segment_id,
                content=rendered,
                source_path=source_name,
                sha256=rendered_sha256,
                mime_type="text/plain",
                metadata={
                    "primary_evaluation_corpus": "benchmark_segments",
                    "benchmark_contract_schema_version": BENCHMARK_CONTRACT_SCHEMA_VERSION,
                    "benchmark_contract_digest": dataset.manifest.contract_digest,
                    "benchmark_segment_id": segment.segment_id,
                    "benchmark_segment_content_sha256": segment.content_sha256,
                    "benchmark_segment_rendered_sha256": rendered_sha256,
                },
            )
        )
    if len(inputs) != dataset.manifest.segment_count:
        raise BenchmarkContractError("benchmark runtime input count does not match manifest")
    return inputs
