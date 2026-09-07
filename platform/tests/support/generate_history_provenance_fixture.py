#!/usr/bin/env python3
"""Generate the synthetic, immutable history/provenance regression fixture."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path
from typing import Any
from zipfile import ZIP_STORED, ZipFile, ZipInfo

PLATFORM_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLATFORM_ROOT / "src"))

from rag_eval.history_provenance.baseline import (
    capture_immutable_baseline,
    verify_immutable_baseline,
)
from rag_eval.history_provenance.reconstruction import (
    build_historical_localization_matrix,
    build_production_localization_audit,
    reconstruct_historical_provenance,
)
from rag_eval.history_provenance.rescore import rescore_historical_run

DOCUMENT_ID = "doc-synthetic-history-v1"
FULL_DOCUMENT_ID = "full-doc-synthetic-history-v1"
RUN_ID = "synthetic-history-run-v1"
FIXTURE_SCHEMA = "history-provenance-fixture/1"
PARAGRAPHS = tuple(
    f"Synthetic signal {index:02d} establishes deterministic evidence {index:02d}."
    for index in range(1, 20)
)
TABLES = {
    "a": [["ALPHA-A1", "ALPHA-A2"], ["ALPHA-A3", "ALPHA-A4"]],
    "b": [["BETA-B1", "BETA-B2"], ["BETA-B3", "BETA-B4"]],
}
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def paragraph_id(index: int) -> str:
    return f"1000{index:04X}"


def paragraph_object_id(index: int) -> str:
    return f"{DOCUMENT_ID}:paragraph:{index:05d}"


def table_object_id(name: str) -> str:
    return f"{DOCUMENT_ID}:table:{1 if name == 'a' else 2:05d}"


def table_render(name: str) -> str:
    rows = json.dumps(TABLES[name], ensure_ascii=False, separators=(",", ":"))
    return f'<table id="native-table-{name}">{rows}</table>'


def body_layout() -> list[tuple[str, int | str]]:
    return [
        *(("paragraph", index) for index in range(1, 11)),
        ("table", "a"),
        *(("paragraph", index) for index in range(11, 16)),
        ("table", "b"),
        *(("paragraph", index) for index in range(16, 20)),
    ]


def block_id_for_body_ordinal(body_ordinal: int) -> str:
    if body_ordinal <= 10:
        return "block-synthetic-01"
    if body_ordinal <= 16:
        return "block-synthetic-02"
    return "block-synthetic-03"


def execution_blocks() -> tuple[dict[str, Any], ...]:
    return (
        {
            "blockid": "block-synthetic-01",
            "content": "\n".join((*PARAGRAPHS[:10], table_render("a"))),
            "positions": [{"range": [paragraph_id(1), paragraph_id(10)]}],
        },
        {
            "blockid": "block-synthetic-02",
            "content": "\n".join((*PARAGRAPHS[10:15], table_render("b"))),
            "positions": [{"range": [paragraph_id(11), paragraph_id(15)]}],
        },
        {
            "blockid": "block-synthetic-03",
            "content": "\n".join(PARAGRAPHS[15:]),
            "positions": [{"range": [paragraph_id(16), paragraph_id(19)]}],
        },
    )


def document_xml() -> bytes:
    values = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml">'
        ),
        "<w:body>",
    ]
    for kind, value in body_layout():
        if kind == "paragraph":
            index = int(value)
            values.append(
                f'<w:p w14:paraId="{paragraph_id(index)}"><w:r><w:t>'
                f"{html.escape(PARAGRAPHS[index - 1])}</w:t></w:r></w:p>"
            )
            continue
        name = str(value)
        values.append("<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>")
        for row in TABLES[name]:
            values.append("<w:tr>")
            for cell in row:
                values.append(
                    f"<w:tc><w:tcPr/><w:p><w:r><w:t>{html.escape(cell)}</w:t>"
                    "</w:r></w:p></w:tc>"
                )
            values.append("</w:tr>")
        values.append("</w:tbl>")
    values.extend(("<w:sectPr/>", "</w:body>", "</w:document>"))
    return "".join(values).encode("utf-8")


def zip_member(name: str, content: bytes) -> tuple[ZipInfo, bytes]:
    info = ZipInfo(name, date_time=FIXED_ZIP_TIME)
    info.compress_type = ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info, content


def write_docx(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    members = (
        (
            "[Content_Types].xml",
            (
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                b'<Default Extension="xml" ContentType="application/xml"/>'
                b'<Override PartName="/word/document.xml" '
                b'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                b"</Types>"
            ),
        ),
        (
            "_rels/.rels",
            (
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                b'<Relationship Id="rId1" '
                b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                b'Target="word/document.xml"/></Relationships>'
            ),
        ),
        ("word/document.xml", document_xml()),
        (
            "word/_rels/document.xml.rels",
            (
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
            ),
        ),
    )
    with ZipFile(path, "w") as archive:
        for name, content in members:
            info, payload = zip_member(name, content)
            archive.writestr(info, payload)


def provenance(source_sha256: str, coordinates: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_sha256": source_sha256,
        "source_spans": [
            {
                "coordinate_system": "ooxml-structural-v1",
                "coordinates": coordinates,
            }
        ],
    }


def canonical_records(source_sha256: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = [
        {
            "object_id": DOCUMENT_ID,
            "document_id": DOCUMENT_ID,
            "object_type": "document",
            "canonical_value": "Synthetic history provenance fixture",
            "document_order": 0,
            "provenance": provenance(source_sha256, {"body_ordinal": 0}),
        }
    ]
    order = 1
    for body_ordinal, (kind, value) in enumerate(body_layout()):
        if kind == "paragraph":
            index = int(value)
            block_id = block_id_for_body_ordinal(body_ordinal)
            records.append(
                {
                    "object_id": paragraph_object_id(index),
                    "document_id": DOCUMENT_ID,
                    "object_type": "paragraph",
                    "canonical_value": PARAGRAPHS[index - 1],
                    "document_order": order,
                    "body_ordinal": body_ordinal,
                    "block_id": block_id,
                    "provenance": provenance(
                        source_sha256,
                        {
                            "body_ordinal": body_ordinal,
                            "block_id": block_id,
                            "para_id": paragraph_id(index),
                        },
                    ),
                }
            )
            order += 1
            continue

        name = str(value)
        table_id = table_object_id(name)
        block_id = block_id_for_body_ordinal(body_ordinal)
        table_coordinates = {
            "body_ordinal": body_ordinal,
            "block_id": block_id,
            "nested": False,
        }
        records.append(
            {
                "object_id": table_id,
                "document_id": DOCUMENT_ID,
                "object_type": "table",
                "canonical_value": json.dumps(
                    TABLES[name], ensure_ascii=False, separators=(",", ":")
                ),
                "document_order": order,
                "body_ordinal": body_ordinal,
                "block_id": "block-synthetic-v1",
                "provenance": provenance(source_sha256, table_coordinates),
            }
        )
        order += 1
        for row_number, row in enumerate(TABLES[name], start=1):
            row_id = f"{table_id}:row:{row_number:05d}"
            row_coordinates = {
                **table_coordinates,
                "table_id": table_id,
                "row": row_number,
            }
            records.append(
                {
                    "object_id": row_id,
                    "document_id": DOCUMENT_ID,
                    "object_type": "row",
                    "table_id": table_id,
                    "row": row_number,
                    "canonical_value": json.dumps(
                        row, ensure_ascii=False, separators=(",", ":")
                    ),
                    "document_order": order,
                    "provenance": provenance(source_sha256, row_coordinates),
                }
            )
            order += 1
            for column, cell in enumerate(row, start=1):
                cell_coordinates = {
                    **row_coordinates,
                    "column": column,
                    "grid_span": 1,
                }
                records.append(
                    {
                        "object_id": f"{row_id}:cell:{column:05d}",
                        "document_id": DOCUMENT_ID,
                        "object_type": "cell",
                        "table_id": table_id,
                        "row": row_number,
                        "column": column,
                        "grid_span": 1,
                        "canonical_value": cell,
                        "document_order": order,
                        "provenance": provenance(source_sha256, cell_coordinates),
                    }
                )
                order += 1
    return records


def execution_stream() -> str:
    return "\n\n".join(str(block["content"]) for block in execution_blocks())


def runtime_chunks(stream: str) -> dict[str, dict[str, Any]]:
    chunks: dict[str, dict[str, Any]] = {}
    order = 0
    for index, paragraph in enumerate(PARAGRAPHS, start=1):
        start = stream.index(paragraph)
        chunk_id = f"chunk-paragraph-{index:02d}"
        chunks[chunk_id] = {
            "_id": chunk_id,
            "content": paragraph,
            "source_span": {"start": start, "end": start + len(paragraph)},
            "chunk_order_index": order,
            "full_doc_id": FULL_DOCUMENT_ID,
            "file_path": "synthetic.docx",
        }
        order += 1
    for name in ("a", "b"):
        rendered = table_render(name)
        start = stream.index(rendered)
        chunk_id = f"chunk-table-{name}-full"
        chunks[chunk_id] = {
            "_id": chunk_id,
            "content": rendered,
            "source_span": {"start": start, "end": start + len(rendered)},
            "chunk_order_index": order,
            "full_doc_id": FULL_DOCUMENT_ID,
            "file_path": "synthetic.docx",
            "sidecar": {"type": "table", "id": f"native-table-{name}"},
        }
        order += 1

    fragment = (
        '<table id="native-table-a">'
        + json.dumps([TABLES["a"][0]], ensure_ascii=False, separators=(",", ":"))
        + "</table>"
    )
    chunks["chunk-table-a-row-1"] = {
        "_id": "chunk-table-a-row-1",
        "content": fragment,
        "chunk_order_index": order,
        "full_doc_id": FULL_DOCUMENT_ID,
        "file_path": "synthetic.docx",
        "sidecar": {"type": "table", "id": "native-table-a"},
    }
    order += 1
    partial = "Synthetic signal 01"
    partial_start = stream.index(partial)
    chunks["chunk-paragraph-01-partial"] = {
        "_id": "chunk-paragraph-01-partial",
        "content": partial,
        "source_span": {
            "start": partial_start,
            "end": partial_start + len(partial),
        },
        "chunk_order_index": order,
        "full_doc_id": FULL_DOCUMENT_ID,
        "file_path": "synthetic.docx",
    }
    order += 1
    chunks["chunk-corrupted-span"] = {
        "_id": "chunk-corrupted-span",
        "content": "synthetic-corruption-witness",
        "source_span": {"start": 0, "end": 1},
        "chunk_order_index": order,
        "full_doc_id": FULL_DOCUMENT_ID,
        "file_path": "synthetic.docx",
    }
    return chunks


def stage_items(indices: list[int], stage: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for rank, index in enumerate(indices, start=1):
        chunk_id = f"chunk-paragraph-{index:02d}"
        result.append(
            {
                "item_id": f"{stage}:{chunk_id}",
                "rank": rank,
                "content": PARAGRAPHS[index - 1],
                "document_id": DOCUMENT_ID,
                "native_id": chunk_id,
                "metadata": {"fixture_stage": stage},
            }
        )
    return result


def case_payload(case_number: int, evidence_indices: list[int]) -> dict[str, Any]:
    case_id = f"fixture-case-{case_number:02d}"
    evidence = [
        {
            "evidence_id": f"fixture-evidence-{index:02d}",
            "document_id": DOCUMENT_ID,
            "locator": {
                "type": "object",
                "object_type": "paragraph",
                "object_id": paragraph_object_id(index),
            },
            "canonical_value": PARAGRAPHS[index - 1],
        }
        for index in evidence_indices
    ]
    required_groups = [[item["evidence_id"]] for item in evidence]
    raw_indices = [index for index in evidence_indices if index <= 15]
    context_indices = [index for index in evidence_indices if index <= 13]
    answer = f"deterministic answer {case_number:02d}"
    return {
        "case_id": case_id,
        "status": "completed",
        "question": f"Which synthetic signals belong to case {case_number:02d}?",
        "gold_answer": {
            "gold_answer_id": f"gold-answer-{case_number:02d}",
            "kind": "text",
            "canonical": answer,
            "accepted_values": [],
        },
        "gold_evidence_set": {
            "gold_evidence_set_id": f"gold-evidence-set-{case_number:02d}",
            "evidence": evidence,
            "required_groups": required_groups,
            "mses_paths": [required_groups],
        },
        "rag_result": {
            "answer": answer,
            "raw_retrieval": stage_items(raw_indices, "raw"),
            "ranked_retrieval": stage_items(raw_indices, "ranked"),
            "final_context": stage_items(context_indices, "context"),
            "latency": {"fixture_seconds": 0.01},
            "native_metadata": {"fixture": FIXTURE_SCHEMA},
        },
        "metrics": [
            {
                "metric_id": "legacy-placeholder",
                "status": "unavailable",
                "scorer_id": "synthetic-legacy-scorer",
                "scorer_version": "1",
                "scorer_digest": "synthetic-fixture-v1",
                "reason": "intentionally replaced by the production evaluator",
            }
        ],
        "started_at": "2020-01-01T00:00:00Z",
        "completed_at": "2020-01-01T00:00:01Z",
        "repetition": 1,
        "seed": 0,
    }


def implementation_hashes() -> dict[str, str]:
    source = PLATFORM_ROOT / "src" / "rag_eval"
    paths = {
        "history_provenance.reconstruction": source
        / "history_provenance"
        / "reconstruction.py",
        "history_provenance.baseline": source / "history_provenance" / "baseline.py",
        "evaluation.evidence": source / "evaluation" / "evidence.py",
        "evaluation.metrics": source / "evaluation" / "metrics.py",
        "evaluation.engine": source / "evaluation" / "engine.py",
    }
    return {name: sha256_file(path) for name, path in paths.items()}


def create_run(root: Path) -> Path:
    run = root / "run"
    source = run / "source" / "synthetic-history.docx"
    write_docx(source)
    source_sha256 = sha256_file(source)
    records = canonical_records(source_sha256)
    canonical_path = run / "source" / "canonical-synthetic-history.jsonl"
    canonical_path.write_text(
        "".join(
            json.dumps(
                record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            + "\n"
            for record in records
        ),
        encoding="utf-8",
    )

    parsed = (
        run
        / "work"
        / "rep-0001"
        / "inputs"
        / "synthetic"
        / "__parsed__"
        / "synthetic-history.docx"
    )
    parsed.parent.mkdir(parents=True, exist_ok=True)
    parsed.write_bytes(source.read_bytes())

    stream = execution_stream()
    blocks = (
        run / "work" / "rep-0001" / "inputs" / "synthetic" / "synthetic.blocks.jsonl"
    )
    blocks.parent.mkdir(parents=True, exist_ok=True)
    block_rows = (
        {"type": "meta", "schema_version": "synthetic-blocks/1"},
        *({"type": "content", **block} for block in execution_blocks()),
    )
    blocks.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in block_rows
        ),
        encoding="utf-8",
    )

    storage = run / "work" / "rep-0001" / "storage" / "synthetic"
    write_json(storage / "kv_store_text_chunks.json", runtime_chunks(stream))
    write_json(
        storage / "kv_store_full_docs.json",
        {FULL_DOCUMENT_ID: {"content": "{{LRdoc}}" + stream}},
    )
    write_json(
        run / "work" / "rep-0001" / "canonical-provenance-map.json",
        {"schema_version": "historical-placeholder/1", "status": "retained"},
    )

    groups = (
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
        [10, 11],
        [12, 13],
        [14, 15, 16],
        [17, 18],
        [19],
    )
    cases = run / "cases"
    for case_number, indices in enumerate(groups, start=1):
        write_json(
            cases / f"case-{case_number:02d}.json", case_payload(case_number, indices)
        )
    write_json(
        cases / "case-order.json",
        {"case_ids": [f"fixture-case-{index:02d}" for index in range(1, 9)]},
    )
    write_json(run / "experiment.json", {"metric_config": {"k_values": [1, 3, 5]}})
    write_json(run / "summary.json", {"status": "historical-synthetic-baseline"})
    return run


def fixture_file_entries(root: Path) -> list[dict[str, Any]]:
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "fixture-manifest.json":
            continue
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return entries


def generate(output: Path) -> None:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"fixture output already exists: {output}")
    output.mkdir(parents=True)
    run = create_run(output)

    baseline_dir = output / ".baseline-build"
    baseline = capture_immutable_baseline(run, baseline_dir, run_id=RUN_ID)
    baseline_path = output / "immutable-baseline.json"
    baseline.path.replace(baseline_path)
    baseline_dir.rmdir()

    reconstruction = reconstruct_historical_provenance(run, strict=True)
    derived = output / "derived"
    map_path = derived / "provenance-map.json"
    write_json(map_path, reconstruction)
    matrix = build_historical_localization_matrix(reconstruction, run)
    matrix_path = derived / "localization-matrix.json"
    write_json(matrix_path, matrix)
    audit = build_production_localization_audit(
        reconstruction, run, helper_matrix=matrix
    )
    if audit.get("difference_count") != 0:
        raise RuntimeError("synthetic fixture disagrees with the production localizer")
    acceptance = {
        "schema_version": "historical-recovery-acceptance/2",
        "status": "UNVERIFIED",
        "run_id": RUN_ID,
        "map": {
            "path": "derived/provenance-map.json",
            "file_sha256": sha256_file(map_path),
            "logical_map_sha256": reconstruction["map_digest"],
        },
        "matrix": {
            "path": "derived/localization-matrix.json",
            "file_sha256": sha256_file(matrix_path),
            "decision_count": matrix["decision_count"],
            "status_counts": matrix["status_counts"],
        },
        "implementation_source_sha256": implementation_hashes(),
        "baseline_verification": {
            **verify_immutable_baseline(run, baseline_path).as_dict(),
            "manifest_path": "immutable-baseline.json",
        },
        "input_proof": {
            "stream_exact": reconstruction["history_reconstruction"]["stream_exact"],
            "lineage_integrity_ok": reconstruction["history_reconstruction"][
                "lineage_integrity_ok"
            ],
        },
    }
    acceptance_path = derived / "map-acceptance.json"
    write_json(acceptance_path, acceptance)

    rescore = rescore_historical_run(
        run,
        map_path,
        map_acceptance_path=acceptance_path,
        matrix_path=matrix_path,
        baseline_path=baseline_path,
    )
    status_counts = {"full": 0, "partial": 0, "missing": 0}
    for chunk in reconstruction["runtime_chunks"].values():
        status_counts[chunk["provenance_status"]] += 1
    expected = {
        "canonical_object_count": 34,
        "runtime_chunk_count": 24,
        "runtime_chunk_status_counts": {"full": 21, "partial": 2, "missing": 1},
        "case_count": 8,
        "gold_evidence_count": 19,
        "stage_count": 3,
        "decision_count": 57,
        "localization_status_counts": {
            "matched": 43,
            "partial": 0,
            "retrieval_missed": 14,
            "provenance_missing": 0,
        },
    }
    observed = {
        "canonical_object_count": len(reconstruction["object_catalog"]),
        "runtime_chunk_count": len(reconstruction["runtime_chunks"]),
        "runtime_chunk_status_counts": status_counts,
        "case_count": rescore["case_count"],
        "gold_evidence_count": matrix["evidence_item_count"],
        "stage_count": matrix["stage_count"],
        "decision_count": matrix["decision_count"],
        "localization_status_counts": matrix["status_counts"],
    }
    if observed != expected:
        raise RuntimeError(f"fixture invariant mismatch: {observed!r}")

    manifest = {
        "schema_version": FIXTURE_SCHEMA,
        "generator": "platform/tests/support/generate_history_provenance_fixture.py",
        "manifest_excludes": ["fixture-manifest.json"],
        "privacy": {
            "synthetic": True,
            "contains_external_business_data": False,
            "contains_original_document_hashes": False,
            "contains_original_filenames": False,
        },
        "expected": expected,
        "assertion_coverage": {
            "test_real_reconstruction_proves_stream_and_native_join": [
                "source/canonical/parsed byte join",
                "exact retained execution stream",
                "full/partial/missing runtime mappings",
                "two structurally distinct native tables",
            ],
            "test_real_matrix_is_exact_gold_not_semantic_duplicate": [
                "19 Gold x 3 stages",
                "exact object misses without content substitution",
            ],
            "test_split_table_has_partial_table_and_full_row_cells": [
                "spanless sidecar table fragment",
                "partial table with complete row and cells",
            ],
            "test_shared_evidence_index_round_trips_map_and_digest": [
                "map digest",
                "source pin",
                "runtime document pin",
            ],
            "test_production_localizer_is_audited_without_catalog_bypass": [
                "helper/production decision parity",
                "catalog verification without bypass",
            ],
            "test_baseline_and_destination_guards_are_read_only": [
                "immutable byte baseline",
                "run subtree write rejection",
                "path traversal rejection",
            ],
            "test_real_versioned_rescore_uses_production_metrics_and_pins_inputs": [
                "production evaluate_case",
                "8 completed cases",
                "map/matrix/source/baseline pins",
                "no retrieval, answer, or runtime rerun",
            ],
        },
        "files": fixture_file_entries(output),
    }
    write_json(output / "fixture-manifest.json", manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PLATFORM_ROOT / "tests" / "fixtures" / "history_provenance" / "v1",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generate(args.output)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
