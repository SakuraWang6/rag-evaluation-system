from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rag_eval.contracts.dataset import GoldEvidence, ObjectLocator
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
    adapter._provenance_map_digest = "map-digest"

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

    assert len(items) == 2
    assert {item.rank for item in items} == {1}
    gold = GoldEvidence(
        evidence_id="gold-beta",
        document_id="doc-1",
        locator=ObjectLocator(object_type="block", object_id="doc-1:block:00002"),
        canonical_value="Beta statement is deliberately long.",
    )
    match = next(
        (
            match_evidence(item, gold, CorpusEvidenceIndex({"doc-1": SOURCE}))
            for item in items
            if item.locator == gold.locator
        ),
        None,
    )
    assert match is not None
    assert match.kind == "exact_provenance"
