from __future__ import annotations

import io
import json
from pathlib import Path
import zipfile

from rag_eval.authoring.service import AuthoringService
from tests.rag_eval_platform.test_authoring import mini_docx


_OLD_TABLE = (
    b" <w:tbl>\n"
    b"  <w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>\n"
    b"  <w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:p><w:r><w:t>\xe6\x8c\x87\xe6\xa0\x87</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>\xe6\x95\xb0\xe5\x80\xbc</w:t></w:r></w:p></w:tc></w:tr>\n"
    b"  <w:tr><w:tc><w:p><w:r><w:t>\xe5\xbb\xb6\xe8\xbf\x9f</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>42 ms</w:t></w:r></w:p></w:tc></w:tr>\n"
    b" </w:tbl>"
)


def _docx_with_table(table: bytes) -> bytes:
    rewritten = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(mini_docx())) as source, zipfile.ZipFile(rewritten, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "word/document.xml":
                assert _OLD_TABLE in data
                data = data.replace(_OLD_TABLE, table, 1)
            target.writestr(info, data)
    return rewritten.getvalue()


def _canonical(tmp_path: Path, payload: bytes) -> tuple[object, list[dict[str, object]], list[dict[str, object]]]:
    service = AuthoringService(tmp_path / "authoring")
    dataset = service.analyze(
        service.upload_docx(filename="table.docx", payload=payload).authoring_dataset_id
    )
    view = service.canonical_view(dataset.authoring_dataset_id)
    root = service.store.workspace(dataset.authoring_dataset_id)
    objects = [
        json.loads(line)
        for line in (root / str(view.canonical_contract_objects_path)).read_text().splitlines()
    ]
    relations = [
        json.loads(line)
        for line in (root / str(view.canonical_contract_relations_path)).read_text().splitlines()
    ]
    return dataset, objects, relations


def _cell(value: str, properties: bytes = b"") -> bytes:
    return b"<w:tc>" + properties + b"<w:p><w:r><w:t>" + value.encode() + b"</w:t></w:r></w:p></w:tc>"


def test_merged_table_recovers_physical_logical_mapping_and_header_paths(tmp_path: Path) -> None:
    table = (
        b"<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/><w:gridCol/></w:tblGrid>"
        b"<w:tr><w:trPr><w:tblHeader/></w:trPr>"
        + _cell("Group", b"<w:tcPr><w:gridSpan w:val=\"2\"/></w:tcPr>")
        + _cell("Total")
        + b"</w:tr><w:tr><w:trPr><w:tblHeader/></w:trPr>"
        + _cell("Team")
        + _cell("Member")
        + _cell("Score")
        + b"</w:tr><w:tr>"
        + _cell("A", b"<w:tcPr><w:vMerge w:val=\"restart\"/></w:tcPr>")
        + _cell("Ann")
        + _cell("90")
        + b"</w:tr><w:tr>"
        + _cell("", b"<w:tcPr><w:vMerge/></w:tcPr>")
        + _cell("Bo")
        + _cell("80")
        + b"</w:tr></w:tbl>"
    )
    first, objects, relations = _canonical(tmp_path / "first", _docx_with_table(table))
    second, second_objects, _ = _canonical(tmp_path / "second", _docx_with_table(table))
    assert first.canonical_contract_digest == second.canonical_contract_digest
    assert objects == second_objects

    canonical_table = next(item for item in objects if item["object_type"] == "table")
    assert canonical_table["representation_status"] == "complete"
    assert {"horizontal_merge", "vertical_merge", "mixed_merge", "multi_level_header"}.issubset(
        canonical_table["attributes"]["table_structure_classes"]
    )
    assert canonical_table["attributes"]["logical_column_count"] == 3
    logical = [item for item in objects if item["object_type"] == "logical_cell"]
    team = next(item for item in logical if item["canonical_value"] == "A")
    assert team["attributes"]["row_span"] == 2
    physical = [item for item in objects if item["object_type"] == "cell"]
    continuation = next(item for item in physical if item["attributes"]["v_merge"] == "continue")
    assert continuation["attributes"]["logical_cell_id"] == team["object_id"]
    assert continuation["attributes"]["merged_cell_origin_physical_id"] == team["attributes"]["origin_physical_cell_id"]
    score = next(item for item in logical if item["canonical_value"] == "90")
    assert score["attributes"]["effective_header_path"] == ["Total", "Score"]
    assert any(
        item["relation_type"] == "physical_to_logical_cell"
        and item["source_object_id"] == continuation["object_id"]
        and item["target_object_id"] == team["object_id"]
        for item in relations
    )
    assert any(
        item["relation_type"] == "header_for" and item["target_object_id"] == score["object_id"]
        for item in relations
    )
    assert continuation["provenance"]["source_spans"][0]["coordinates"]["physical_cell_index"] == 1


def test_orphan_vertical_merge_fails_closed_without_logical_mapping(tmp_path: Path) -> None:
    table = (
        b"<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>"
        b"<w:tr>" + _cell("name") + _cell("value") + b"</w:tr>"
        b"<w:tr>" + _cell("", b"<w:tcPr><w:vMerge/></w:tcPr>") + _cell("bad") + b"</w:tr>"
        b"</w:tbl>"
    )
    _dataset, objects, _relations = _canonical(tmp_path, _docx_with_table(table))
    canonical_table = next(item for item in objects if item["object_type"] == "table")
    assert canonical_table["representation_status"] == "partial"
    assert any("orphan_or_ambiguous_vMerge_continue" in item for item in canonical_table["attributes"]["topology_errors"])
    continuation = next(
        item
        for item in objects
        if item["object_type"] == "cell" and item["attributes"]["v_merge"] == "continue"
    )
    assert continuation["representation_status"] == "partial"
    assert continuation["attributes"]["logical_cell_id"] is None


def test_headerless_complete_table_is_explicitly_prohibited_as_gold_evidence(tmp_path: Path) -> None:
    table = (
        b"<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>"
        b"<w:tr>" + _cell("name") + _cell("value") + b"</w:tr>"
        b"<w:tr>" + _cell("latency") + _cell("42") + b"</w:tr>"
        b"</w:tbl>"
    )
    _dataset, objects, _relations = _canonical(tmp_path, _docx_with_table(table))
    canonical_table = next(item for item in objects if item["object_type"] == "table")
    assert canonical_table["representation_status"] == "complete"
    assert canonical_table["attributes"]["gold_evidence_eligible"] is False
    assert all(
        item["attributes"]["gold_evidence_eligible"] is False
        for item in objects
        if item["object_type"] == "cell"
    )


def test_explicit_first_column_header_builds_row_header_path(tmp_path: Path) -> None:
    table = (
        b"<w:tbl><w:tblPr><w:tblLook w:firstColumn=\"1\"/></w:tblPr>"
        b"<w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>"
        b"<w:tr>" + _cell("metric") + _cell("value") + b"</w:tr>"
        b"<w:tr>" + _cell("latency") + _cell("42") + b"</w:tr>"
        b"</w:tbl>"
    )
    _dataset, objects, relations = _canonical(tmp_path, _docx_with_table(table))
    canonical_table = next(item for item in objects if item["object_type"] == "table")
    assert canonical_table["attributes"]["header_column_count"] == 1
    assert canonical_table["attributes"]["gold_evidence_eligible"] is True
    value = next(
        item for item in objects if item["object_type"] == "logical_cell" and item["canonical_value"] == "42"
    )
    assert value["attributes"]["effective_header_path"] == ["latency"]
    assert any(
        item["relation_type"] == "header_for" and item["target_object_id"] == value["object_id"]
        for item in relations
    )


def test_grid_offset_irregularity_remains_partial(tmp_path: Path) -> None:
    table = (
        b"<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/><w:gridCol/></w:tblGrid>"
        b"<w:tr><w:trPr><w:gridBefore w:val=\"1\"/></w:trPr>"
        + _cell("a")
        + _cell("b")
        + b"</w:tr></w:tbl>"
    )
    _dataset, objects, _relations = _canonical(tmp_path, _docx_with_table(table))
    canonical_table = next(item for item in objects if item["object_type"] == "table")
    assert canonical_table["representation_status"] == "partial"
    assert "irregular_grid" in canonical_table["attributes"]["table_structure_classes"]
    assert any("grid_offset" in error for error in canonical_table["attributes"]["topology_errors"])


def test_nested_table_has_typed_outer_cell_topology_and_no_text_flattening(tmp_path: Path) -> None:
    nested = (
        b"<w:tbl><w:tblGrid><w:gridCol/></w:tblGrid>"
        b"<w:tr>" + _cell("nested-value") + b"</w:tr></w:tbl>"
    )
    table = (
        b"<w:tbl><w:tblGrid><w:gridCol/></w:tblGrid><w:tr><w:tc>"
        b"<w:p><w:r><w:t>outer-value</w:t></w:r></w:p>" + nested + b"</w:tc></w:tr></w:tbl>"
    )
    _dataset, objects, relations = _canonical(tmp_path, _docx_with_table(table))
    tables = [item for item in objects if item["object_type"] == "table"]
    outer = next(item for item in tables if not item["attributes"]["nested"])
    nested_table = next(item for item in tables if item["attributes"]["nested"])
    assert outer["representation_status"] == "partial"
    assert outer["attributes"]["nested_table_ids"] == [nested_table["object_id"]]
    assert nested_table["representation_status"] == "complete"
    outer_cell = next(
        item for item in objects if item["object_type"] == "cell" and item["attributes"]["table_id"] == outer["object_id"]
    )
    assert outer_cell["canonical_value"] == "outer-value"
    assert "nested-value" not in outer_cell["canonical_value"]
    assert any(
        item["relation_type"] == "nested_table_in_cell"
        and item["source_object_id"] == outer_cell["object_id"]
        and item["target_object_id"] == nested_table["object_id"]
        for item in relations
    )


def test_grid_overflow_is_partial_and_preserves_source_locator(tmp_path: Path) -> None:
    table = (
        b"<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid><w:tr>"
        + _cell("too-wide", b"<w:tcPr><w:gridSpan w:val=\"3\"/></w:tcPr>")
        + b"</w:tr></w:tbl>"
    )
    _dataset, objects, _relations = _canonical(tmp_path, _docx_with_table(table))
    canonical_table = next(item for item in objects if item["object_type"] == "table")
    assert canonical_table["representation_status"] == "partial"
    assert any("grid_overflow" in item for item in canonical_table["attributes"]["topology_errors"])
    cell = next(item for item in objects if item["object_type"] == "cell")
    coordinates = cell["provenance"]["source_spans"][0]["coordinates"]
    assert coordinates["grid_span"] == 3
    assert coordinates["physical_cell_index"] == 1
