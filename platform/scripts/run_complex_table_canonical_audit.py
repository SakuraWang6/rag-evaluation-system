#!/usr/bin/env python3
"""Rebuild and source-verify DOCX complex-table Canonical topology.

The verifier compares Canonical physical table cells with the source OOXML
directly.  It does not rely on a retriever, a RAG result, or document-specific
text fixtures.
"""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

from rag_eval.authoring.service import AuthoringService
from rag_eval.storage.atomic import atomic_write_json


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def _tag(name: str) -> str:
    return f"{{{W}}}{name}"


def _value(element: etree._Element | None) -> str | None:
    return element.get(_tag("val")) if element is not None else None


def _compact(value: str) -> str:
    return " ".join(value.split())


def _paragraph_text(paragraph: etree._Element) -> str:
    parts: list[str] = []
    for item in paragraph.iter():
        if item.tag == _tag("t"):
            parts.append(item.text or "")
        elif item.tag == _tag("tab"):
            parts.append("\t")
        elif item.tag in {_tag("br"), _tag("cr")}:
            parts.append("\n")
    return _compact("".join(parts))


def _direct_cell_text(cell: etree._Element) -> str:
    """Exclude nested-table descendants from an outer-cell text witness."""

    return _compact("\n".join(_paragraph_text(item) for item in cell.findall("w:p", NS)))


def _grid_span(cell: etree._Element) -> int:
    properties = cell.find("w:tcPr", NS)
    item = properties.find("w:gridSpan", NS) if properties is not None else None
    value = _value(item) or "1"
    return int(value) if value.isdigit() and int(value) >= 1 else 1


def _v_merge(cell: etree._Element) -> str:
    properties = cell.find("w:tcPr", NS)
    item = properties.find("w:vMerge", NS) if properties is not None else None
    if item is None:
        return "none"
    value = _value(item)
    return "restart" if value == "restart" else "continue" if value in (None, "", "continue") else "invalid"


def _source_tables(source: Path) -> dict[int, dict[str, object]]:
    """Return source tables in the Canonicalizer's stable ID allocator order."""

    with zipfile.ZipFile(source) as package:
        document = etree.fromstring(package.read("word/document.xml"))
    body = document.find("w:body", NS)
    if body is None:
        raise ValueError("OOXML document has no body")
    direct = list(body.findall("w:tbl", NS))
    result: dict[int, dict[str, object]] = {}
    nested: list[tuple[etree._Element, int]] = []

    def inspect_table(table: etree._Element, ordinal: int, body_ordinal: int, *, is_nested: bool) -> None:
        rows = table.findall("w:tr", NS)
        grid = table.find("w:tblGrid", NS)
        cells: dict[tuple[int, int], dict[str, object]] = {}
        for row_index, row in enumerate(rows, start=1):
            cursor = 1
            for physical_index, cell in enumerate(row.findall("w:tc", NS), start=1):
                span = _grid_span(cell)
                cells[(row_index, physical_index)] = {
                    "text": _direct_cell_text(cell),
                    "column": cursor,
                    "grid_span": span,
                    "v_merge": _v_merge(cell),
                }
                cursor += span
                for child in cell.findall("w:tbl", NS):
                    nested.append((child, body_ordinal))
        result[ordinal] = {
            "body_ordinal": body_ordinal,
            "nested": is_nested,
            "row_count": len(rows),
            "physical_cell_count": len(cells),
            "grid_width": len(grid.findall("w:gridCol", NS)) if grid is not None else 0,
            "cells": cells,
        }

    for ordinal, table in enumerate(direct, start=1):
        inspect_table(table, ordinal, body.index(table), is_nested=False)
    for offset, (table, body_ordinal) in enumerate(nested, start=1):
        inspect_table(table, len(direct) + offset, body_ordinal, is_nested=True)
    return result


def _canonical(root: Path) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    manifest = json.loads((next(root.glob("*/canonical/canonical-contract-manifest.v1.json"))).read_text())
    objects = [
        json.loads(line)
        for line in next(root.glob("*/canonical/canonical-objects.v1.jsonl")).read_text().splitlines()
    ]
    relations = [
        json.loads(line)
        for line in next(root.glob("*/canonical/canonical-relations.v1.jsonl")).read_text().splitlines()
    ]
    return manifest, objects, relations


def _verify_source_topology(
    *, source_tables: dict[int, dict[str, object]], objects: list[dict[str, object]], relations: list[dict[str, object]]
) -> dict[str, object]:
    tables = [item for item in objects if item["object_type"] == "table"]
    cells = [item for item in objects if item["object_type"] == "cell"]
    logical = {item["object_id"]: item for item in objects if item["object_type"] == "logical_cell"}
    by_table_cells: dict[str, list[dict[str, object]]] = {}
    for cell in cells:
        by_table_cells.setdefault(str(cell["attributes"]["table_id"]), []).append(cell)
    failures: list[str] = []
    verified_cells = 0
    for ordinal, expected in source_tables.items():
        table_id = f"{tables[0]['document_id']}:table:{ordinal:05d}"
        canonical_table = next((item for item in tables if item["object_id"] == table_id), None)
        if canonical_table is None:
            failures.append(f"missing_table:{ordinal}")
            continue
        attributes = canonical_table["attributes"]
        locator = canonical_table["provenance"]["source_spans"][0]["coordinates"]
        for key in ("body_ordinal", "nested"):
            if locator.get(key) != expected[key]:
                failures.append(f"table_locator_mismatch:{ordinal}:{key}")
        for key, attribute_key in (
            ("row_count", "physical_row_count"),
            ("physical_cell_count", "physical_cell_count"),
            ("grid_width", "table_grid_column_count"),
        ):
            if attributes.get(attribute_key) != expected[key]:
                failures.append(f"table_count_mismatch:{ordinal}:{attribute_key}")
        actual = {
            (
                int(item["attributes"]["row"]),
                int(item["attributes"]["physical_cell_index"]),
            ): item
            for item in by_table_cells.get(table_id, [])
        }
        if set(actual) != set(expected["cells"]):
            failures.append(f"physical_cell_set_mismatch:{ordinal}")
        for key, raw in expected["cells"].items():
            physical = actual.get(key)
            if physical is None:
                continue
            attributes = physical["attributes"]
            if any(attributes[field] != raw[field] for field in ("column", "grid_span", "v_merge")):
                failures.append(f"physical_topology_mismatch:{ordinal}:{key[0]}:{key[1]}")
            if physical["canonical_value"] != raw["text"]:
                failures.append(f"physical_text_mismatch:{ordinal}:{key[0]}:{key[1]}")
            logical_id = attributes.get("logical_cell_id")
            if physical["representation_status"] == "complete" and logical_id not in logical:
                failures.append(f"missing_logical_mapping:{ordinal}:{key[0]}:{key[1]}")
            verified_cells += 1
    relation_types = Counter(str(item["relation_type"]) for item in relations)
    complete_tables = [item for item in tables if item["representation_status"] == "complete"]
    gold_eligible = [
        item
        for item in complete_tables
        if (
            item["attributes"].get("header_row_count", 0) > 0
            or item["attributes"].get("header_column_count", 0) > 0
        )
        and any(
            relation["relation_type"] == "header_for"
            and logical.get(relation["target_object_id"], {}).get("attributes", {}).get("table_id") == item["object_id"]
            for relation in relations
        )
    ]
    flagged_gold_eligible = [
        item for item in tables if item["attributes"].get("gold_evidence_eligible") is True
    ]
    if {item["object_id"] for item in gold_eligible} != {
        item["object_id"] for item in flagged_gold_eligible
    }:
        failures.append("gold_eligibility_flag_mismatch")
    return {
        "source_verified": not failures,
        "failures": tuple(sorted(set(failures))),
        "verified_physical_cell_count": verified_cells,
        "source_table_count": len(source_tables),
        "canonical_table_count": len(tables),
        "complete_table_count": len(complete_tables),
        "partial_table_count": len(tables) - len(complete_tables),
        "gold_eligible_table_count": len(gold_eligible),
        "gold_eligibility_flagged_table_count": len(flagged_gold_eligible),
        "gold_prohibited_table_count": len(tables) - len(gold_eligible),
        "relation_type_counts": dict(sorted(relation_types.items())),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-docx", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--reset", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    source = args.source_docx.resolve()
    output = args.output_root.resolve()
    if not source.is_file():
        raise SystemExit(f"DOCX not found: {source}")
    if args.reset and output.exists():
        shutil.rmtree(output)
    source_tables = _source_tables(source)
    digests: list[str] = []
    first_objects: list[dict[str, object]] | None = None
    first_relations: list[dict[str, object]] | None = None
    for name in ("first", "second"):
        service = AuthoringService(output / name)
        dataset = service.analyze(
            service.upload_docx(filename=source.name, payload=source.read_bytes()).authoring_dataset_id
        )
        manifest, objects, relations = _canonical(output / name)
        digests.append(str(manifest["canonical_digest"]))
        if name == "first":
            first_objects, first_relations = objects, relations
        else:
            if first_objects != objects or first_relations != relations:
                raise RuntimeError("repeated canonicalization is not byte-stable")
        print(f"{name}: {dataset.canonical_contract_digest}")
    assert first_objects is not None and first_relations is not None
    verification = _verify_source_topology(
        source_tables=source_tables, objects=first_objects, relations=first_relations
    )
    if not verification["source_verified"]:
        raise RuntimeError("source-side table verification failed: " + ", ".join(verification["failures"]))
    classes = Counter(
        classification
        for item in first_objects
        if item["object_type"] == "table"
        for classification in item["attributes"].get("table_structure_classes", [])
    )
    object_status = {
        object_type: dict(
            sorted(
                Counter(
                    str(item["representation_status"])
                    for item in first_objects
                    if item["object_type"] == object_type
                ).items()
            )
        )
        for object_type in ("table", "row", "cell", "logical_row", "logical_column", "logical_cell")
    }
    summary = {
        "source_docx": str(source),
        "source_table_count": len(source_tables),
        "canonical_digests": tuple(digests),
        "deterministic_rebuild": len(set(digests)) == 1,
        "object_status": object_status,
        "table_structure_classes": dict(sorted(classes.items())),
        "source_side_verification": verification,
    }
    atomic_write_json(output / "complex-table-canonical-audit-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
