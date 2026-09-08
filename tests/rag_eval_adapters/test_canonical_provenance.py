from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rag_eval.contracts.adapter import RAGEvidenceItem
from rag_eval.contracts.dataset import GoldEvidence, ObjectLocator
from rag_eval.evaluation import evidence as evidence_module
from rag_eval.evaluation.evidence import CorpusEvidenceIndex, match_evidence
from rag_eval_lightrag_adapter.adapter import LightRAGAdapter
from rag_eval_lightrag_adapter.canonical_provenance import (
    build_provenance_manifest,
    load_canonical_document_map,
    runtime_chunk_mapping,
)

SOURCE = "Alpha statement.\n\nBeta statement is deliberately long.\n"


def _record(object_id: str, body_ordinal: int, value: str) -> dict:
    return {
        "record_type": "canonical_object",
        "document_id": "doc-1",
        "object_id": object_id,
        "object_type": "block",
        "status": "supported",
        "structural_locator": {
            "part": "word/document.xml",
            "body_ordinal": body_ordinal,
        },
        "canonical_value": value,
        "witness": value,
        "canonicalizer": "rag-eval-authoring-canonicalizer/1",
        "canonical_digest": "canonical-digest",
        "block_kind": "paragraph",
    }


def _document_map(tmp_path: Path):
    path = tmp_path / "evidence.jsonl"
    records = [
        _record("doc-1:block:00001", 1, "Alpha statement."),
        _record(
            "doc-1:block:00002",
            2,
            "Beta statement is deliberately long.",
        ),
    ]
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    return load_canonical_document_map(
        document_id="doc-1",
        source=SOURCE,
        sidecar_path=path,
        expected_sidecar_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_round_trip_overlaps_and_many_to_many_chunk_mapping(tmp_path: Path) -> None:
    document = _document_map(tmp_path)
    beta_start = SOURCE.index("Beta")
    stored_chunks = {
        "runtime-all": {
            "file_path": "source.txt",
            "content": SOURCE,
            "source_span": {"start": 0, "end": len(SOURCE)},
        },
        "runtime-beta-left": {
            "file_path": "source.txt",
            "content": SOURCE[beta_start : beta_start + 12],
            "source_span": {"start": beta_start, "end": beta_start + 12},
        },
        "runtime-beta-right": {
            "file_path": "source.txt",
            "content": SOURCE[beta_start + 8 : len(SOURCE)],
            "source_span": {"start": beta_start + 8, "end": len(SOURCE)},
        },
    }

    manifest = build_provenance_manifest(
        documents={"doc-1": document},
        sources={"doc-1": SOURCE},
        document_by_file={"source.txt": "doc-1"},
        stored_chunks=stored_chunks,
    )

    all_mapping = manifest["runtime_chunks"]["runtime-all"]
    assert all_mapping["provenance_status"] == "full"
    assert {item["object_id"] for item in all_mapping["canonical_objects"]} == {
        "doc-1:block:00001",
        "doc-1:block:00002",
    }
    assert (
        manifest["runtime_chunks"]["runtime-beta-left"]["provenance_status"]
        == "partial"
    )
    assert (
        manifest["runtime_chunks"]["runtime-beta-right"]["provenance_status"]
        == "partial"
    )
    reverse = manifest["object_to_runtime_chunks"]["doc-1:block:00002"]
    assert {item["runtime_chunk_id"] for item in reverse} == {
        "runtime-all",
        "runtime-beta-left",
        "runtime-beta-right",
    }
    assert {item["coverage"] for item in reverse} == {"full", "partial"}


def test_missing_and_partial_provenance_fail_closed(tmp_path: Path) -> None:
    document = _document_map(tmp_path)
    beta_start = SOURCE.index("Beta")

    missing = runtime_chunk_mapping(
        chunk_id="missing",
        document=document,
        source=SOURCE,
        content="Beta",
        source_span=None,
    )
    mismatch = runtime_chunk_mapping(
        chunk_id="mismatch",
        document=document,
        source=SOURCE,
        content="not the source witness",
        source_span={"start": beta_start, "end": beta_start + 4},
    )
    partial = runtime_chunk_mapping(
        chunk_id="partial",
        document=document,
        source=SOURCE,
        content=SOURCE[beta_start : beta_start + 4],
        source_span={"start": beta_start, "end": beta_start + 4},
    )

    assert missing["provenance_status"] == "missing"
    assert mismatch["reason"] == "runtime_content_source_witness_mismatch"
    assert partial["provenance_status"] == "partial"
    assert partial["canonical_objects"][0]["coverage"] == "partial"


def test_gold_matches_projected_full_object_without_gold_aware_mapping(
    tmp_path: Path,
) -> None:
    document = _document_map(tmp_path)
    manifest = build_provenance_manifest(
        documents={"doc-1": document},
        sources={"doc-1": SOURCE},
        document_by_file={"source.txt": "doc-1"},
        stored_chunks={
            "runtime-all": {
                "file_path": "source.txt",
                "content": SOURCE,
                "source_span": {"start": 0, "end": len(SOURCE)},
            }
        },
    )
    adapter = LightRAGAdapter()
    adapter._source_by_file = {"source.txt": "doc-1"}
    adapter._runtime_provenance_by_chunk = manifest["runtime_chunks"]
    map_digest = evidence_module._mapping_digest(manifest)
    adapter._provenance_map_digest = map_digest
    assert manifest["object_catalog"]["doc-1:block:00002"]["mapping_status"] == "mapped"
    assert manifest["object_catalog"]["doc-1:block:00002"]["expected_extent"] == {
        "start": SOURCE.index("Beta"),
        "end": SOURCE.index("Beta") + len("Beta statement is deliberately long."),
    }

    items = adapter._evidence_items(
        [
            {
                "item_id": "runtime-all",
                "native_id": "runtime-all",
                "rank": 1,
                "content": SOURCE,
                "file_path": "source.txt",
                "source_span": {"start": 0, "end": len(SOURCE)},
                "score": 0.9,
            }
        ],
        "raw",
    )

    assert len(items) == 1
    item = items[0]
    assert item.rank == 1
    assert item.native_id == "runtime-all"
    assert item.locator is None
    assert item.metadata["canonical_object_ids"] == [
        "doc-1:block:00001",
        "doc-1:block:00002",
    ]
    gold = GoldEvidence(
        evidence_id="gold-beta",
        document_id="doc-1",
        locator=ObjectLocator(object_type="block", object_id="doc-1:block:00002"),
        canonical_value="Beta statement is deliberately long.",
    )
    corpus = CorpusEvidenceIndex.from_provenance_map(
        manifest,
        documents={"doc-1": SOURCE},
        source_digests={
            "doc-1": hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()
        },
        expected_map_digest=map_digest,
    )
    assert corpus.has_provenance_catalog
    match = match_evidence(item, gold, corpus)
    assert match is not None
    assert match.kind == "exact_provenance"


def test_structure_bridge_preserves_hierarchy_table_topology_and_round_trips(
    tmp_path: Path,
) -> None:
    source = (
        "## Alpha\n\n"
        "Paragraph one.\n\n"
        "| H | V |\n"
        "| --- | --- |\n"
        "| a | b |\n"
    )
    root_id = "doc-1:section:00000"
    section_id = "doc-1:section:00001"
    heading_id = "doc-1:block:00001"
    paragraph_id = "doc-1:block:00002"
    table_id = "doc-1:table:00001"
    row_1 = "doc-1:row:00001"
    row_2 = "doc-1:row:00002"
    records = [
        {
            **_record(root_id, 0, "Document body"),
            "object_type": "section",
            "structural_locator": {"part": "word/document.xml", "ordinal": 0},
        },
        {
            **_record(heading_id, 1, "Alpha"),
            "block_kind": "heading",
            "structural_locator": {
                "part": "word/document.xml",
                "body_ordinal": 1,
                "section_id": root_id,
            },
        },
        {
            **_record(section_id, 1, "Alpha"),
            "object_type": "section",
            "structural_locator": {
                "part": "word/document.xml",
                "body_ordinal": 1,
                "heading_level": 2,
            },
        },
        {
            **_record("doc-1:text_span:00002", 2, "Paragraph one."),
            "object_type": "text_span",
            "block_id": paragraph_id,
            "structural_locator": {
                "part": "word/document.xml",
                "body_ordinal": 2,
                "block_id": paragraph_id,
                "span_ordinal": 1,
            },
        },
        {
            **_record(paragraph_id, 2, "Paragraph one."),
            "structural_locator": {
                "part": "word/document.xml",
                "body_ordinal": 2,
                "section_id": section_id,
            },
        },
        {
            **_record(table_id, 3, "H | V\na | b"),
            "object_type": "table",
            "row_count": 2,
            "column_count": 2,
            "structural_locator": {
                "part": "word/document.xml",
                "body_ordinal": 3,
                "section_id": section_id,
                "nested": False,
            },
        },
    ]
    for row_number, row_id, values in (
        (1, row_1, ("H", "V")),
        (2, row_2, ("a", "b")),
    ):
        records.append(
            {
                **_record(row_id, 3, " | ".join(values)),
                "object_type": "row",
                "table_id": table_id,
                "row": row_number,
                "structural_locator": {
                    "part": "word/document.xml",
                    "body_ordinal": 3,
                    "table_id": table_id,
                    "row": row_number,
                },
            }
        )
        for column, value in enumerate(values, start=1):
            cell_id = f"doc-1:cell:{row_number:05d}{column:05d}"
            records.append(
                {
                    **_record(cell_id, 3, value),
                    "object_type": "cell",
                    "table_id": table_id,
                    "row_id": row_id,
                    "row": row_number,
                    "column": column,
                    "structural_locator": {
                        "part": "word/document.xml",
                        "body_ordinal": 3,
                        "table_id": table_id,
                        "row": row_number,
                        "column": column,
                    },
                }
            )
    sidecar = tmp_path / "evidence.jsonl"
    sidecar.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    document = load_canonical_document_map(
        document_id="doc-1",
        source=source,
        sidecar_path=sidecar,
        expected_sidecar_sha256=hashlib.sha256(sidecar.read_bytes()).hexdigest(),
    )

    sections = {entry["section_id"]: entry for entry in document.sections}
    assert sections[section_id]["heading_path"] == "Alpha"
    assert sections[section_id]["parent_section_id"] == root_id
    assert sections[section_id]["active_source_span"] == {
        "start": 0,
        "end": len(source),
    }
    structures = {entry.object_id: entry.structure for entry in document.objects}
    assert structures[paragraph_id]["document_order"] == 2
    assert structures[paragraph_id]["section_id"] == section_id
    assert structures["doc-1:text_span:00002"]["parent_object_id"] == paragraph_id
    assert structures["doc-1:cell:0000200001"]["table_id"] == table_id
    assert structures["doc-1:cell:0000200001"]["row_id"] == row_2
    assert structures["doc-1:cell:0000200001"]["parent_object_id"] == row_2

    table_start = source.index("| H | V |")
    paragraph_start = source.index("Paragraph")
    stored_chunks = {
        "runtime-overlap": {
            "file_path": "source.md",
            "content": source[paragraph_start : table_start + 9],
            "source_span": {"start": paragraph_start, "end": table_start + 9},
        },
        "runtime-table": {
            "file_path": "source.md",
            "content": source[table_start:],
            "source_span": {"start": table_start, "end": len(source)},
        },
    }
    manifest = build_provenance_manifest(
        documents={"doc-1": document},
        sources={"doc-1": source},
        document_by_file={"source.md": "doc-1"},
        stored_chunks=stored_chunks,
    )
    assert manifest["schema_version"] == 2
    overlap = manifest["runtime_chunks"]["runtime-overlap"]
    assert overlap["structure"]["metadata_status"] == "complete"
    assert overlap["structure"]["heading_path"] == "Alpha"
    assert {item["object_id"] for item in overlap["canonical_objects"]} >= {
        paragraph_id,
        table_id,
    }
    assert {
        item["runtime_chunk_id"]
        for item in manifest["object_to_runtime_chunks"][table_id]
    } == {"runtime-overlap", "runtime-table"}

    adapter = LightRAGAdapter()
    adapter._source_by_file = {"source.md": "doc-1"}
    adapter._runtime_provenance_by_chunk = manifest["runtime_chunks"]
    adapter._provenance_map_digest = "structure-map-digest"
    items = adapter._evidence_items(
        [
            {
                "item_id": "runtime-table",
                "native_id": "runtime-table",
                "rank": 1,
                "content": source[table_start:],
                "file_path": "source.md",
                "source_span": {"start": table_start, "end": len(source)},
                "score": 0.9,
            }
        ],
        "raw",
    )
    assert len(items) == 1
    item = items[0]
    cell_edge = next(
        edge
        for edge in item.metadata["canonical_edges"]
        if edge["object_id"] == "doc-1:cell:0000200001"
    )
    assert item.metadata["runtime_structure"]["heading_path"] == "Alpha"
    assert cell_edge["structure"]["row_id"] == row_2
    assert RAGEvidenceItem.model_validate(item.model_dump()).metadata == item.metadata
