from __future__ import annotations

import io
import json
from pathlib import Path
import zipfile

import pytest
from lxml import etree
from pydantic import ValidationError

from rag_eval.authoring.canonical import DocxCanonicalizer
from rag_eval.authoring.service import AuthoringService
from rag_eval.contracts.canonical import (
    CANONICAL_SCHEMA_VERSION,
    CanonicalContractError,
    CanonicalDocument,
    CanonicalObject,
    CanonicalObjectProvenance,
    CanonicalObjectType,
    CanonicalRelation,
    CanonicalRelationProvenance,
    CanonicalRelationType,
    LEGACY_CANONICAL_SCHEMA_VERSION,
    PREVIOUS_CANONICAL_SCHEMA_VERSION,
    RepresentationStatus,
    SourceSpan,
    build_canonical_manifest,
)
from rag_eval.datasets.registry import (
    DatasetLifecycle,
    DatasetRegistryError,
    DatasetRegistryRecord,
    DatasetUsage,
    FROZEN_20_CASE_BUNDLE_ID,
    FROZEN_20_CASE_REFERENCE,
)
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths
from tests.rag_eval_platform.test_authoring import mini_docx


SOURCE_DIGEST = "a" * 64
CONFIG_DIGEST = "b" * 64


def span(order: int) -> SourceSpan:
    return SourceSpan(
        part="word/document.xml",
        coordinates={"body_ordinal": order},
        text_start=0,
        text_end=1,
    )


def canonical_object(
    object_id: str,
    object_type: CanonicalObjectType,
    order: int,
    *,
    status: RepresentationStatus = RepresentationStatus.COMPLETE,
) -> CanonicalObject:
    return CanonicalObject(
        object_id=object_id,
        document_id="doc-1",
        object_type=object_type,
        representation_status=status,
        document_order=order,
        canonical_value="x" if status != RepresentationStatus.MISSING else None,
        provenance=CanonicalObjectProvenance(
            source_sha256=SOURCE_DIGEST,
            parser_identity="docx-parser/1",
            canonicalizer_identity="canonicalizer/1",
            configuration_digest=CONFIG_DIGEST,
            extraction_method="fixture",
            source_spans=() if status == RepresentationStatus.MISSING else (span(order),),
        ),
    )


def relation(
    relation_id: str,
    relation_type: CanonicalRelationType,
    source: str,
    target: str,
) -> CanonicalRelation:
    return CanonicalRelation(
        relation_id=relation_id,
        document_id="doc-1",
        relation_type=relation_type,
        source_object_id=source,
        target_object_id=target,
        provenance=CanonicalRelationProvenance(
            extraction_method="fixture",
            source_object_ids=(source, target),
        ),
    )


def test_canonical_contract_validates_hierarchy_siblings_and_table_topology() -> None:
    objects = (
        canonical_object("doc", CanonicalObjectType.DOCUMENT, 0),
        canonical_object("section", CanonicalObjectType.SECTION, 1),
        canonical_object("heading", CanonicalObjectType.HEADING, 2),
        canonical_object("paragraph-a", CanonicalObjectType.PARAGRAPH, 3),
        canonical_object("paragraph-b", CanonicalObjectType.PARAGRAPH, 4),
        canonical_object("table", CanonicalObjectType.TABLE, 5),
        canonical_object("row", CanonicalObjectType.ROW, 6),
        canonical_object("cell", CanonicalObjectType.CELL, 7),
    )
    relations = (
        relation("r-1", CanonicalRelationType.PARENT_CHILD, "doc", "section"),
        relation("r-2", CanonicalRelationType.PARENT_CHILD, "section", "heading"),
        relation("r-3", CanonicalRelationType.PARENT_CHILD, "section", "paragraph-a"),
        relation("r-4", CanonicalRelationType.PARENT_CHILD, "section", "paragraph-b"),
        relation("r-5", CanonicalRelationType.SIBLING, "paragraph-a", "paragraph-b"),
        relation("r-6", CanonicalRelationType.PARENT_CHILD, "section", "table"),
        relation("r-7", CanonicalRelationType.PARENT_CHILD, "table", "row"),
        relation("r-8", CanonicalRelationType.TABLE_CONTAINS_ROW, "table", "row"),
        relation("r-9", CanonicalRelationType.PARENT_CHILD, "row", "cell"),
        relation("r-10", CanonicalRelationType.ROW_CONTAINS_CELL, "row", "cell"),
        relation("r-11", CanonicalRelationType.DOCUMENT_ORDER, "paragraph-a", "paragraph-b"),
    )
    document = CanonicalDocument.build(
        document_id="doc-1",
        source_sha256=SOURCE_DIGEST,
        parser_identity="docx-parser/1",
        canonicalizer_identity="canonicalizer/1",
        configuration_digest=CONFIG_DIGEST,
        objects=objects,
        relations=relations,
    )
    round_tripped = CanonicalDocument.model_validate_json(document.model_dump_json())
    assert round_tripped.manifest.schema_version == CANONICAL_SCHEMA_VERSION
    assert round_tripped.manifest.objects_digest == document.manifest.objects_digest
    assert round_tripped.manifest.relations_digest == document.manifest.relations_digest

    legacy = CanonicalDocument(
        manifest=build_canonical_manifest(
            schema_version=LEGACY_CANONICAL_SCHEMA_VERSION,
            document_id="doc-1",
            source_sha256=SOURCE_DIGEST,
            parser_identity="docx-parser/1",
            canonicalizer_identity="canonicalizer/1",
            configuration_digest=CONFIG_DIGEST,
            objects=objects,
            relations=relations,
        ),
        objects=objects,
        relations=relations,
    )
    assert legacy.manifest.schema_version == "1.0"

    previous = CanonicalDocument(
        manifest=build_canonical_manifest(
            schema_version=PREVIOUS_CANONICAL_SCHEMA_VERSION,
            document_id="doc-1",
            source_sha256=SOURCE_DIGEST,
            parser_identity="docx-parser/1",
            canonicalizer_identity="canonicalizer/3",
            configuration_digest=CONFIG_DIGEST,
            objects=objects,
            relations=relations,
        ),
        objects=objects,
        relations=relations,
    )
    assert previous.manifest.schema_version == "1.1"

    bad_sibling = relation("bad", CanonicalRelationType.SIBLING, "heading", "row")
    with pytest.raises(ValidationError, match="shared parent_child"):
        CanonicalDocument.build(
            document_id="doc-1",
            source_sha256=SOURCE_DIGEST,
            parser_identity="docx-parser/1",
            canonicalizer_identity="canonicalizer/1",
            configuration_digest=CONFIG_DIGEST,
            objects=objects,
            relations=relations + (bad_sibling,),
        )


def test_source_span_provenance_and_incomplete_evidence_fail_closed() -> None:
    with pytest.raises(ValidationError, match="safe OOXML"):
        SourceSpan(part="../word/document.xml", coordinates={"body_ordinal": 0})
    with pytest.raises(ValidationError, match="non-negative"):
        SourceSpan(part="word/document.xml", coordinates={"body_ordinal": -1})
    with pytest.raises(ValidationError, match="require direct source spans"):
        CanonicalObject(
            object_id="bad",
            document_id="doc-1",
            object_type=CanonicalObjectType.PARAGRAPH,
            representation_status=RepresentationStatus.COMPLETE,
            document_order=0,
            canonical_value="x",
            provenance=CanonicalObjectProvenance(
                source_sha256=SOURCE_DIGEST,
                parser_identity="docx-parser/1",
                canonicalizer_identity="canonicalizer/1",
                configuration_digest=CONFIG_DIGEST,
                extraction_method="fixture",
            ),
        )
    objects = (
        canonical_object("doc", CanonicalObjectType.DOCUMENT, 0),
        canonical_object("partial", CanonicalObjectType.EQUATION, 1, status=RepresentationStatus.PARTIAL),
        canonical_object("unsupported", CanonicalObjectType.EMBEDDED_OBJECT, 2, status=RepresentationStatus.UNSUPPORTED),
    )
    document = CanonicalDocument.build(
        document_id="doc-1",
        source_sha256=SOURCE_DIGEST,
        parser_identity="docx-parser/1",
        canonicalizer_identity="canonicalizer/1",
        configuration_digest=CONFIG_DIGEST,
        objects=objects,
        relations=(),
    )
    with pytest.raises(CanonicalContractError, match="partial"):
        document.require_complete_object("partial")
    with pytest.raises(CanonicalContractError, match="unsupported"):
        document.require_complete_object("unsupported")

    prohibited = canonical_object("prohibited", CanonicalObjectType.CELL, 3).model_copy(
        update={"attributes": {"gold_evidence_eligible": False}}
    )
    restricted = CanonicalDocument.build(
        document_id="doc-1",
        source_sha256=SOURCE_DIGEST,
        parser_identity="docx-parser/1",
        canonicalizer_identity="canonicalizer/1",
        configuration_digest=CONFIG_DIGEST,
        objects=(canonical_object("doc", CanonicalObjectType.DOCUMENT, 0), prohibited),
        relations=(),
    )
    with pytest.raises(CanonicalContractError, match="prohibited as Gold evidence"):
        restricted.require_complete_object("prohibited")


def test_docx_adapter_preserves_hierarchy_topology_and_contract_determinism(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    first = authoring.analyze(authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id)
    second = authoring.analyze(authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id)
    first_view = authoring.canonical_view(first.authoring_dataset_id)
    second_view = authoring.canonical_view(second.authoring_dataset_id)
    assert first.canonical_digest == second.canonical_digest  # Existing Bundle v2 projection digest.
    assert first.canonical_contract_digest == second.canonical_contract_digest
    assert first_view.canonical_contract_digest == first.canonical_contract_digest
    root = authoring.store.workspace(first.authoring_dataset_id)
    manifest = json.loads((root / str(first_view.canonical_contract_manifest_path)).read_text())
    objects = [json.loads(line) for line in (root / str(first_view.canonical_contract_objects_path)).read_text().splitlines()]
    relations = [json.loads(line) for line in (root / str(first_view.canonical_contract_relations_path)).read_text().splitlines()]
    assert manifest["canonical_digest"] == first.canonical_contract_digest
    assert {item["object_type"] for item in objects}.issuperset({"section", "heading", "paragraph", "table", "row", "cell", "figure", "caption", "equation", "reference", "footnote"})
    relation_types = {item["relation_type"] for item in relations}
    assert {"parent_child", "sibling", "section_hierarchy", "document_order", "caption_of", "table_contains_row", "row_contains_cell", "reference_to"}.issubset(relation_types)
    caption = next(item for item in objects if item["object_type"] == "caption")
    assert caption["representation_status"] == "complete"
    assert any(
        item["relation_type"] == "caption_of" and item["source_object_id"] == caption["object_id"]
        for item in relations
    )
    assert (root / "canonical" / "evidence.jsonl").is_file()  # Bundle 2.0 compatibility projection remains present.
    second_root = authoring.store.workspace(second.authoring_dataset_id)
    for relative in (
        first_view.canonical_contract_manifest_path,
        first_view.canonical_contract_objects_path,
        first_view.canonical_contract_relations_path,
    ):
        assert relative is not None
        assert (root / relative).read_bytes() == (second_root / relative).read_bytes()


def test_math_paragraph_is_not_emitted_twice_as_nested_omml(tmp_path: Path) -> None:
    """A display ``oMathPara`` contains an ``oMath`` child, but is one formula."""

    original = mini_docx()
    old = b"<w:p><m:oMath><m:r><m:t>x = 42</m:t></m:r></m:oMath></w:p>"
    new = b"<w:p><m:oMathPara><m:oMath><m:r><m:t>x = 42</m:t></m:r></m:oMath></m:oMathPara></w:p>"
    rewritten = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(rewritten, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "word/document.xml":
                assert old in data
                data = data.replace(old, new)
            target.writestr(info, data)
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="math-para.docx", payload=rewritten.getvalue()).authoring_dataset_id
    )
    view = authoring.canonical_view(dataset.authoring_dataset_id)
    root = authoring.store.workspace(dataset.authoring_dataset_id)
    objects = [
        json.loads(line)
        for line in (root / str(view.canonical_contract_objects_path)).read_text().splitlines()
    ]
    assert sum(item["object_type"] == "equation" for item in objects) == 1


def test_nested_table_locator_and_digest_are_deterministic(tmp_path: Path) -> None:
    """Nested tables retain the ordinal of their top-level body ancestor."""

    nested_table = (
        b"<w:tbl><w:tr><w:tc><w:p><w:r><w:t>nested</w:t></w:r>"
        b"</w:p></w:tc></w:tr></w:tbl>"
    )
    old = b"<w:tc><w:p><w:r><w:t>\xe6\x8c\x87\xe6\xa0\x87</w:t></w:r></w:p></w:tc>"
    new = old[:-7] + nested_table + b"</w:tc>"
    rewritten = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(mini_docx())) as source, zipfile.ZipFile(rewritten, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "word/document.xml":
                assert old in data
                data = data.replace(old, new)
            target.writestr(info, data)

    authoring = AuthoringService(tmp_path / "authoring")
    first = authoring.analyze(
        authoring.upload_docx(filename="nested.docx", payload=rewritten.getvalue()).authoring_dataset_id
    )
    second = authoring.analyze(
        authoring.upload_docx(filename="nested.docx", payload=rewritten.getvalue()).authoring_dataset_id
    )
    assert first.canonical_contract_digest == second.canonical_contract_digest
    view = authoring.canonical_view(first.authoring_dataset_id)
    root = authoring.store.workspace(first.authoring_dataset_id)
    objects = [
        json.loads(line)
        for line in (root / str(view.canonical_contract_objects_path)).read_text().splitlines()
    ]
    nested = next(item for item in objects if item["object_type"] == "table" and item["attributes"]["nested"])
    assert nested["provenance"]["source_spans"][0]["coordinates"]["body_ordinal"] >= 0


def test_heading_bookmarks_are_retained_as_canonical_references(tmp_path: Path) -> None:
    original = mini_docx()
    old = b'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
    new = old + b'<w:bookmarkStart w:id="99" w:name="HeadingScope"/>'
    rewritten = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(rewritten, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "word/document.xml":
                assert old in data
                data = data.replace(old, new, 1)
            target.writestr(info, data)
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="heading-bookmark.docx", payload=rewritten.getvalue()).authoring_dataset_id
    )
    view = authoring.canonical_view(dataset.authoring_dataset_id)
    root = authoring.store.workspace(dataset.authoring_dataset_id)
    objects = [
        json.loads(line)
        for line in (root / str(view.canonical_contract_objects_path)).read_text().splitlines()
    ]
    assert any(
        item["object_type"] == "reference"
        and item["attributes"].get("reference_kind") == "bookmark"
        and item["attributes"].get("bookmark_name") == "HeadingScope"
        for item in objects
    )


def test_caption_immediately_before_table_preserves_caption_topology(tmp_path: Path) -> None:
    table = (
        b" <w:tbl>\n"
        b"  <w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>\n"
        b"  <w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:p><w:r><w:t>\xe6\x8c\x87\xe6\xa0\x87</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>\xe6\x95\xb0\xe5\x80\xbc</w:t></w:r></w:p></w:tc></w:tr>\n"
        b"  <w:tr><w:tc><w:p><w:r><w:t>\xe5\xbb\xb6\xe8\xbf\x9f</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>42 ms</w:t></w:r></w:p></w:tc></w:tr>\n"
        b" </w:tbl>"
    )
    caption = b' <w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr><w:r><w:t>\xe8\xa1\xa8 1 \xe5\xbb\xb6\xe8\xbf\x9f\xe6\x8c\x87\xe6\xa0\x87</w:t></w:r></w:p>'
    rewritten = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(mini_docx())) as source, zipfile.ZipFile(rewritten, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "word/document.xml":
                assert table + b"\n" + caption in data
                data = data.replace(table + b"\n" + caption, caption + b"\n" + table, 1)
            target.writestr(info, data)
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="caption-before-table.docx", payload=rewritten.getvalue()).authoring_dataset_id
    )
    view = authoring.canonical_view(dataset.authoring_dataset_id)
    root = authoring.store.workspace(dataset.authoring_dataset_id)
    objects = [
        json.loads(line)
        for line in (root / str(view.canonical_contract_objects_path)).read_text().splitlines()
    ]
    relations = [
        json.loads(line)
        for line in (root / str(view.canonical_contract_relations_path)).read_text().splitlines()
    ]
    caption_object = next(item for item in objects if item["object_type"] == "caption")
    assert caption_object["representation_status"] == "complete"
    assert any(
        item["relation_type"] == "caption_of"
        and item["source_object_id"] == caption_object["object_id"]
        for item in relations
    )


def test_ooxml_non_breaking_hyphen_is_preserved_in_source_text() -> None:
    paragraph = etree.fromstring(
        b'<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b'<w:r><w:t>\xe8\xa1\xa8 2</w:t></w:r><w:r><w:noBreakHyphen/></w:r>'
        b'<w:r><w:t>7 \xe7\xbd\x91\xe7\xbb\x9c\xe8\xae\xbe\xe5\xa4\x87</w:t></w:r></w:p>'
    )

    assert DocxCanonicalizer._paragraph_text(paragraph) == "表 2-7 网络设备"


def test_frozen_20_case_external_registry_is_immutable_and_does_not_touch_bundle(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=False)
    record = service.dataset_registry.get(FROZEN_20_CASE_BUNDLE_ID)
    assert record == FROZEN_20_CASE_REFERENCE
    assert record.lifecycle.value == "frozen"
    assert record.usage.value == "development/reference_diagnostic"
    assert record.held_out is False
    assert record.generalization_claim_allowed is False
    assert not (service.paths.datasets / FROZEN_20_CASE_BUNDLE_ID).exists()
    changed = DatasetRegistryRecord.build(
        bundle_id=FROZEN_20_CASE_BUNDLE_ID,
        lifecycle=DatasetLifecycle.RETIRED,
        usage=DatasetUsage.DEVELOPMENT_REFERENCE_DIAGNOSTIC,
        held_out=False,
        generalization_claim_allowed=False,
    )
    with pytest.raises(DatasetRegistryError, match="immutable"):
        service.dataset_registry.register(changed)
    source_record = Path(__file__).resolve().parents[2] / "registries" / "reference-datasets" / f"{FROZEN_20_CASE_BUNDLE_ID}.json"
    assert json.loads(source_record.read_text()) == FROZEN_20_CASE_REFERENCE.model_dump(mode="json")
