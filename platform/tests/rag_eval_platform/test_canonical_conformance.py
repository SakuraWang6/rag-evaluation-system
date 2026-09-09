from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rag_eval.authoring.canonical import DocxCanonicalizer
from rag_eval.authoring.service import AuthoringService
from rag_eval.canonical.conformance import (
    CANONICAL_GOLD_ELIGIBILITY_MATRIX,
    CanonicalConformanceSuite,
)
from rag_eval.contracts.canonical import (
    CanonicalConformanceReport,
    CanonicalConformanceStatus,
    CanonicalDocument,
    CanonicalObject,
    CanonicalObjectProvenance,
    CanonicalObjectType,
    RepresentationStatus,
    SourceSpan,
)
from rag_eval.datasets.formal import FormalDatasetError, FormalDatasetValidator
from tests.rag_eval_platform.test_authoring import mini_docx
from tests.rag_eval_platform.test_complex_table_canonicalization import (
    _cell,
    _docx_with_table,
)


def _load_artifacts(
    service: AuthoringService, dataset_id: str
) -> tuple[CanonicalDocument, CanonicalConformanceReport]:
    view = service.canonical_view(dataset_id)
    root = service.store.workspace(dataset_id)
    assert view.canonical_conformance_path is not None
    assert view.canonical_conformance_digest is not None
    assert view.canonical_conformance_sha256 is not None
    canonical = CanonicalDocument.model_validate(
        {
            "manifest": json.loads(
                (root / str(view.canonical_contract_manifest_path)).read_text()
            ),
            "objects": [
                json.loads(line)
                for line in (
                    root / str(view.canonical_contract_objects_path)
                ).read_text().splitlines()
            ],
            "relations": [
                json.loads(line)
                for line in (
                    root / str(view.canonical_contract_relations_path)
                ).read_text().splitlines()
            ],
        }
    )
    payload = (root / view.canonical_conformance_path).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == view.canonical_conformance_sha256
    report = CanonicalConformanceReport.model_validate_json(payload)
    assert report.report_digest == view.canonical_conformance_digest
    return canonical, report


def _analyze(
    root: Path, payload: bytes = mini_docx()
) -> tuple[CanonicalDocument, CanonicalConformanceReport]:
    service = AuthoringService(root)
    dataset = service.analyze(
        service.upload_docx(
            filename="conformance.docx", payload=payload
        ).authoring_dataset_id
    )
    return _load_artifacts(service, dataset.authoring_dataset_id)


def test_conformance_report_is_deterministic_and_snapshot_bound(
    tmp_path: Path,
) -> None:
    first_document, first = _analyze(tmp_path / "first")
    second_document, second = _analyze(tmp_path / "second")

    assert first == second
    assert first.report_digest == second.report_digest
    assert first.canonical_digest == first_document.manifest.canonical_digest
    assert first.source_sha256 == first_document.manifest.source_sha256
    assert first.parser_identity == first_document.manifest.parser_identity
    assert first.canonicalizer_identity == first_document.manifest.canonicalizer_identity
    assert first.configuration_digest == first_document.manifest.configuration_digest
    assert first_document.manifest == second_document.manifest
    assert first_document.objects == second_document.objects
    assert first_document.relations == second_document.relations
    assert all(item.locator_digest for item in first.object_results)
    assert all(
        item.witness_sha256
        for item in first.object_results
        if item.status == CanonicalConformanceStatus.CONFORMANT
    )


def test_changed_identity_creates_a_new_snapshot_without_rewriting_history(
    tmp_path: Path,
) -> None:
    service = AuthoringService(tmp_path)
    dataset = service.analyze(
        service.upload_docx(filename="history.docx", payload=mini_docx()).authoring_dataset_id
    )
    view = service.canonical_view(dataset.authoring_dataset_id)
    root = service.store.workspace(dataset.authoring_dataset_id)
    references = (
        view.canonical_contract_manifest_path,
        view.canonical_contract_objects_path,
        view.canonical_contract_relations_path,
        view.canonical_conformance_path,
    )
    assert all(references)
    original_paths = tuple(
        root / str(path)
        for path in references
    )
    original_bytes = {path: path.read_bytes() for path in original_paths}

    changed = DocxCanonicalizer().canonicalize(
        source_path=service.store.source_path(dataset.authoring_dataset_id),
        output_root=root,
        source_sha256=dataset.source.sha256,
        parser_identity=dataset.source.parser_identity,
        configuration_digest="c" * 64,
    )

    assert changed.canonical_contract_digest != view.canonical_contract_digest
    assert changed.contract_manifest_path.parent != original_paths[0].parent
    assert all(path.read_bytes() == payload for path, payload in original_bytes.items())


def test_first_wave_gold_eligibility_is_explicit_and_fail_closed(
    tmp_path: Path,
) -> None:
    document, report = _analyze(tmp_path)
    by_id = {item.object_id: item for item in report.object_results}

    paragraphs = [
        item
        for item in document.objects
        if item.object_type == CanonicalObjectType.PARAGRAPH
        and item.canonical_value
    ]
    spans = [
        item
        for item in document.objects
        if item.object_type == CanonicalObjectType.TEXT_SPAN
    ]
    assert paragraphs and spans
    assert all(by_id[item.object_id].gold_evidence_eligible for item in paragraphs)
    assert all(by_id[item.object_id].gold_evidence_eligible for item in spans)
    assert all(
        item.attributes["gold_evidence_eligible"]
        == by_id[item.object_id].gold_evidence_eligible
        for item in document.objects
    )
    assert all(
        item.attributes["gold_eligibility_policy"] == report.policy_identity
        for item in document.objects
    )
    assert all(
        not by_id[item.object_id].gold_evidence_eligible
        for item in document.objects
        if item.representation_status
        in {
            RepresentationStatus.PARTIAL,
            RepresentationStatus.UNSUPPORTED,
            RepresentationStatus.MISSING,
        }
    )
    assert all(
        not by_id[item.object_id].gold_evidence_eligible
        for item in document.objects
        if item.object_type
        in {
            CanonicalObjectType.FIGURE,
            CanonicalObjectType.EQUATION,
            CanonicalObjectType.CELL,
        }
    )


def test_table_and_cell_subtype_matrix_is_explicit(tmp_path: Path) -> None:
    decisions = {
        item.subtype: item.gold_evidence_eligible
        for item in CANONICAL_GOLD_ELIGIBILITY_MATRIX
    }
    assert decisions == {
        "logical_cell.horizontal_merge.with_headers": True,
        "logical_cell.inferred_regular_grid.with_headers": True,
        "logical_cell.irregular_or_partial": False,
        "logical_cell.missing_table": False,
        "logical_cell.mixed_merge.with_headers": True,
        "logical_cell.nested": False,
        "logical_cell.regular.with_headers": True,
        "logical_cell.table_without_data": False,
        "logical_cell.vertical_merge.with_headers": True,
        "logical_cell.headerless": False,
        "paragraph.list_item": True,
        "paragraph.standard": True,
        "physical_cell.proof_only": False,
        "table.headerless": False,
        "table.horizontal_merge.with_headers": True,
        "table.inferred_regular_grid.with_headers": True,
        "table.irregular_or_partial": False,
        "table.mixed_merge.with_headers": True,
        "table.nested": False,
        "table.regular.with_headers": True,
        "table.table_without_data": False,
        "table.vertical_merge.with_headers": True,
        "text_span.standard": True,
    }

    regular = (
        b"<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>"
        b"<w:tr><w:trPr><w:tblHeader/></w:trPr>"
        + _cell("name")
        + _cell("value")
        + b"</w:tr><w:tr>"
        + _cell("latency")
        + _cell("42")
        + b"</w:tr></w:tbl>"
    )
    inferred = (
        b"<w:tbl><w:tr><w:trPr><w:tblHeader/></w:trPr>"
        + _cell("name")
        + _cell("value")
        + b"</w:tr><w:tr>"
        + _cell("latency")
        + _cell("42")
        + b"</w:tr></w:tbl>"
    )
    horizontal = (
        b"<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/><w:gridCol/></w:tblGrid>"
        b"<w:tr><w:trPr><w:tblHeader/></w:trPr>"
        + _cell("group", b'<w:tcPr><w:gridSpan w:val="2"/></w:tcPr>')
        + _cell("total")
        + b"</w:tr><w:tr>"
        + _cell("a")
        + _cell("b")
        + _cell("42")
        + b"</w:tr></w:tbl>"
    )
    vertical = (
        b"<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>"
        b"<w:tr><w:trPr><w:tblHeader/></w:trPr>"
        + _cell("name")
        + _cell("value")
        + b"</w:tr><w:tr>"
        + _cell("latency", b'<w:tcPr><w:vMerge w:val="restart"/></w:tcPr>')
        + _cell("42")
        + b"</w:tr><w:tr>"
        + _cell("", b"<w:tcPr><w:vMerge/></w:tcPr>")
        + _cell("43")
        + b"</w:tr></w:tbl>"
    )
    header_only = (
        b"<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>"
        b"<w:tr><w:trPr><w:tblHeader/></w:trPr>"
        + _cell("name")
        + _cell("value")
        + b"</w:tr></w:tbl>"
    )
    nested_table = (
        b"<w:tbl><w:tblGrid><w:gridCol/></w:tblGrid><w:tr><w:tc>"
        b"<w:p><w:r><w:t>outer</w:t></w:r></w:p>"
        b"<w:tbl><w:tblGrid><w:gridCol/></w:tblGrid><w:tr>"
        + _cell("nested")
        + b"</w:tr></w:tbl></w:tc></w:tr></w:tbl>"
    )
    cases = (
        ("regular", regular, "table.regular.with_headers", True),
        (
            "inferred",
            inferred,
            "table.inferred_regular_grid.with_headers",
            True,
        ),
        (
            "horizontal",
            horizontal,
            "table.horizontal_merge.with_headers",
            True,
        ),
        ("vertical", vertical, "table.vertical_merge.with_headers", True),
        ("header-only", header_only, "table.table_without_data", False),
        ("nested", nested_table, "table.nested", False),
    )
    for name, table_xml, expected_subtype, expected_eligible in cases:
        document, report = _analyze(
            tmp_path / name,
            _docx_with_table(table_xml),
        )
        result = next(
            item
            for item in report.object_results
            if item.object_type == CanonicalObjectType.TABLE
            and item.subtype == expected_subtype
        )
        assert result.gold_evidence_eligible is expected_eligible
        assert document.object_by_id(result.object_id).attributes[
            "gold_evidence_eligible"
        ] is expected_eligible

    mixed = (
        b"<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/><w:gridCol/></w:tblGrid>"
        b"<w:tr><w:trPr><w:tblHeader/></w:trPr>"
        + _cell("Group", b'<w:tcPr><w:gridSpan w:val="2"/></w:tcPr>')
        + _cell("Total")
        + b"</w:tr><w:tr>"
        + _cell("A", b'<w:tcPr><w:vMerge w:val="restart"/></w:tcPr>')
        + _cell("Ann")
        + _cell("90")
        + b"</w:tr><w:tr>"
        + _cell("", b"<w:tcPr><w:vMerge/></w:tcPr>")
        + _cell("Bo")
        + _cell("80")
        + b"</w:tr></w:tbl>"
    )
    mixed_document, mixed_report = _analyze(
        tmp_path / "mixed", _docx_with_table(mixed)
    )
    mixed_table = next(
        item
        for item in mixed_document.objects
        if item.object_type == CanonicalObjectType.TABLE
    )
    mixed_result = mixed_report.result_for(mixed_table.object_id)
    assert mixed_result.subtype == "table.mixed_merge.with_headers"
    assert mixed_result.gold_evidence_eligible is True

    headerless = (
        b"<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>"
        b"<w:tr>"
        + _cell("name")
        + _cell("value")
        + b"</w:tr><w:tr>"
        + _cell("latency")
        + _cell("42")
        + b"</w:tr></w:tbl>"
    )
    headerless_document, headerless_report = _analyze(
        tmp_path / "headerless", _docx_with_table(headerless)
    )
    headerless_table = next(
        item
        for item in headerless_document.objects
        if item.object_type == CanonicalObjectType.TABLE
    )
    result = headerless_report.result_for(headerless_table.object_id)
    assert result.subtype == "table.headerless"
    assert result.gold_evidence_eligible is False

    orphan = (
        b"<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>"
        b"<w:tr>"
        + _cell("name")
        + _cell("value")
        + b"</w:tr><w:tr>"
        + _cell("", b"<w:tcPr><w:vMerge/></w:tcPr>")
        + _cell("bad")
        + b"</w:tr></w:tbl>"
    )
    orphan_document, orphan_report = _analyze(
        tmp_path / "orphan", _docx_with_table(orphan)
    )
    orphan_table = next(
        item
        for item in orphan_document.objects
        if item.object_type == CanonicalObjectType.TABLE
    )
    result = orphan_report.result_for(orphan_table.object_id)
    assert result.subtype == "table.irregular_or_partial"
    assert result.gold_evidence_eligible is False

    assert all(
        not item.gold_evidence_eligible
        for item in mixed_report.object_results
        if item.object_type == CanonicalObjectType.CELL
    )
    assert any(
        item.gold_evidence_eligible
        for item in mixed_report.object_results
        if item.object_type == CanonicalObjectType.LOGICAL_CELL
    )


def test_duplicate_typed_locator_fails_conformance_without_mutating_snapshot() -> None:
    source_digest = "a" * 64
    config_digest = "b" * 64

    def object_value(
        object_id: str, object_type: CanonicalObjectType, order: int
    ) -> CanonicalObject:
        return CanonicalObject(
            object_id=object_id,
            document_id="doc-duplicate",
            object_type=object_type,
            representation_status=RepresentationStatus.COMPLETE,
            document_order=order,
            canonical_value=object_id,
            provenance=CanonicalObjectProvenance(
                source_sha256=source_digest,
                parser_identity="parser/1",
                canonicalizer_identity="canonicalizer/legacy",
                configuration_digest=config_digest,
                extraction_method="fixture",
                source_spans=(
                    SourceSpan(
                        part="word/document.xml",
                        coordinates={"body_ordinal": 0},
                        text_start=0,
                        text_end=len(object_id),
                    ),
                ),
            ),
        )

    document = CanonicalDocument.build(
        document_id="doc-duplicate",
        source_sha256=source_digest,
        parser_identity="parser/1",
        canonicalizer_identity="canonicalizer/legacy",
        configuration_digest=config_digest,
        objects=(
            object_value("document", CanonicalObjectType.DOCUMENT, 0),
            object_value("paragraph-a", CanonicalObjectType.PARAGRAPH, 1),
            object_value("paragraph-b", CanonicalObjectType.PARAGRAPH, 2),
        ),
        relations=(),
    )
    before = document.model_dump_json()

    report = CanonicalConformanceSuite().evaluate(document)

    assert document.model_dump_json() == before
    for object_id in ("paragraph-a", "paragraph-b"):
        result = report.result_for(object_id)
        assert result.status == CanonicalConformanceStatus.NONCONFORMANT
        assert "duplicate_typed_locator" in result.reason_codes
        assert result.gold_evidence_eligible is False


def test_formal_loader_rejects_tampered_current_conformance_artifact(
    tmp_path: Path,
) -> None:
    service = AuthoringService(tmp_path)
    dataset = service.analyze(
        service.upload_docx(filename="tampered.docx", payload=mini_docx()).authoring_dataset_id
    )
    view = service.canonical_view(dataset.authoring_dataset_id)
    assert view.canonical_conformance_path is not None
    report_path = service.store.workspace(dataset.authoring_dataset_id) / view.canonical_conformance_path
    report_path.write_bytes(report_path.read_bytes() + b"\n")

    with pytest.raises(
        FormalDatasetError,
        match="canonical conformance artifact checksum mismatch",
    ):
        FormalDatasetValidator._load_canonical_document(dataset, service.store)


def test_canonical_and_benchmark_policy_do_not_import_adapter_capabilities() -> None:
    root = Path(__file__).resolve().parents[2]
    canonical_paths = (
        root / "src" / "rag_eval" / "canonical",
        root / "src" / "rag_eval" / "contracts" / "canonical.py",
    )
    benchmark_paths = (
        root / "src" / "rag_eval" / "datasets" / "admission.py",
        root / "src" / "rag_eval" / "datasets" / "bundle_v3.py",
        root / "src" / "rag_eval" / "datasets" / "formal.py",
    )
    canonical_forbidden = (
        "rag_eval.contracts.adapter",
        "rag_eval_lightrag_adapter",
        "rag_eval_rag_anything_adapter",
        "AdapterCapabilities",
    )
    capability_forbidden = (
        "rag_eval_lightrag_adapter",
        "rag_eval_rag_anything_adapter",
        "AdapterCapabilities",
    )
    for path in canonical_paths:
        values = path.rglob("*.py") if path.is_dir() else (path,)
        for value in values:
            source = value.read_text(encoding="utf-8")
            assert not any(item in source for item in canonical_forbidden), value
    for value in benchmark_paths:
        source = value.read_text(encoding="utf-8")
        assert not any(item in source for item in capability_forbidden), value
