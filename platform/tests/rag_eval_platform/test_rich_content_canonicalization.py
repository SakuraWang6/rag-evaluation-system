from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_eval.authoring.service import AuthoringService
from rag_eval.contracts.canonical import CanonicalContractError, CanonicalDocument
from tests.rag_eval_platform.test_authoring import mini_docx


INLINE_DRAWING = (
    b'<w:p><w:r><w:drawing><wp:inline><wp:docPr id="1" name="\xe6\x9e\xb6\xe6\x9e\x84\xe5\x9b\xbe" descr="\xe7\xb3\xbb\xe7\xbb\x9f\xe6\x9e\xb6\xe6\x9e\x84"/>'
    b'<a:graphic><a:graphicData><a:blip r:embed="rIdImage"/></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
)


def _rewrite_document(payload: bytes, old: bytes, new: bytes) -> bytes:
    rewritten = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(payload)) as source, zipfile.ZipFile(rewritten, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "word/document.xml":
                assert old in data
                data = data.replace(old, new, 1)
            target.writestr(info, data)
    return rewritten.getvalue()


def _rich_fixture(*, ambiguous_caption: bool = False) -> bytes:
    caption = (
        b'<w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr><w:bookmarkStart w:id="71" w:name="FigureOne"/>'
        b'<w:r><w:t>Figure 1 Topology</w:t></w:r><w:bookmarkEnd w:id="71"/></w:p>'
    )
    anchor = (
        b'<w:p><w:r><w:drawing><wp:anchor><wp:extent cx="111" cy="222"/>'
        b'<wp:docPr id="2" name="Anchor diagram" descr="Anchor description"/>'
        b'<a:graphic><a:graphicData><a:blip r:embed="rIdImage"/></a:graphicData></a:graphic>'
        b'</wp:anchor></w:drawing></w:r></w:p>'
    )
    formula = (
        b'<w:p><w:r><w:t>\xe6\xa0\xb9\xe6\x8d\xae\xe4\xb8\x8b\xe5\x88\x97\xe5\x85\xac\xe5\xbc\x8f\xe8\xae\xa1\xe7\xae\x97\xe6\x80\xbb\xe5\x88\x86\xe3\x80\x82</w:t></w:r></w:p>'
        b'<w:p><m:oMathPara><m:oMath><m:r><m:t>F = 42</m:t></m:r></m:oMath></m:oMathPara></w:p>'
        b'<w:p><w:r><w:t>\xe5\x85\xb6\xe4\xb8\xad F \xe8\xa1\xa8\xe7\xa4\xba\xe6\x80\xbb\xe5\x88\x86\xef\xbc\x8c\xe5\x8f\xaf\xe7\x94\xb1\xe5\xae\xa1\xe6\xa0\xb8\xe5\x91\x98\xe9\xaa\x8c\xe8\xaf\x81\xe3\x80\x82</w:t></w:r></w:p>'
    )
    reference = (
        b'<w:p><w:r><w:t>\xe5\xa6\x82\xe5\x9b\xbe 1 \xe6\x89\x80\xe7\xa4\xba\xef\xbc\x8c\xe6\x8b\x93\xe6\x89\x91\xe5\x8f\x97\xe6\x8e\xa7\xe3\x80\x82</w:t></w:r></w:p>'
        b'<w:p><w:fldSimple w:instr="REF FigureOne \\h"><w:r><w:t>Figure 1</w:t></w:r></w:fldSimple></w:p>'
    )
    if ambiguous_caption:
        two_figures = INLINE_DRAWING.replace(
            b"</w:p>",
            b'<w:r><w:drawing><wp:inline><wp:docPr id="3" name="second"/>'
            b'<a:graphic><a:graphicData><a:blip r:embed="rIdImage"/></a:graphicData></a:graphic>'
            b"</wp:inline></w:drawing></w:r></w:p>",
        )
        replacement = two_figures + caption
    else:
        replacement = reference + INLINE_DRAWING + caption + anchor + formula
    return _rewrite_document(mini_docx(), INLINE_DRAWING, replacement)


def _contract(authoring: AuthoringService, payload: bytes, tmp_path: Path) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    dataset = authoring.analyze(authoring.upload_docx(filename="rich.docx", payload=payload).authoring_dataset_id)
    view = authoring.canonical_view(dataset.authoring_dataset_id)
    root = authoring.store.workspace(dataset.authoring_dataset_id)
    manifest = json.loads((root / str(view.canonical_contract_manifest_path)).read_text())
    objects = [json.loads(line) for line in (root / str(view.canonical_contract_objects_path)).read_text().splitlines()]
    relations = [json.loads(line) for line in (root / str(view.canonical_contract_relations_path)).read_text().splitlines()]
    return manifest, objects, relations


def test_rich_drawingml_caption_reference_and_omml_are_auditable_and_deterministic(tmp_path: Path) -> None:
    payload = _rich_fixture()
    first_authoring = AuthoringService(tmp_path / "first")
    second_authoring = AuthoringService(tmp_path / "second")
    first_manifest, first_objects, first_relations = _contract(first_authoring, payload, tmp_path)
    second_manifest, second_objects, second_relations = _contract(second_authoring, payload, tmp_path)

    assert first_manifest["schema_version"] == "1.2"
    assert first_manifest == second_manifest
    assert first_objects == second_objects
    assert first_relations == second_relations

    figures = [item for item in first_objects if item["object_type"] == "figure"]
    inline = next(item for item in figures if item["attributes"]["anchor_kind"] == "inline")
    anchor = next(item for item in figures if item["attributes"]["anchor_kind"] == "anchor")
    assert inline["representation_status"] == "complete"
    assert inline["attributes"]["gold_evidence_eligible"] is True
    assert inline["attributes"]["gold_evidence_scope"] == "caption_and_text_only"
    assert inline["attributes"]["visual_semantic_status"] == "unverified"
    assert anchor["representation_status"] == "complete"
    assert anchor["attributes"]["gold_evidence_eligible"] is False  # no textual figure reference
    assert anchor["attributes"]["width_emu"] == 111
    assert anchor["attributes"]["height_emu"] == 222

    resources = [item for item in first_objects if item["object_type"] == "media_resource"]
    assert len(resources) == 1  # both drawings share one resource without duplicate objects
    assert resources[0]["attributes"]["gold_evidence_eligible"] is False
    assert resources[0]["attributes"]["visual_semantic_status"] == "unverified"

    relations = {(item["relation_type"], item["source_object_id"], item["target_object_id"]) for item in first_relations}
    assert ("figure_has_resource", inline["object_id"], inline["attributes"]["resource_object_id"]) in relations
    assert any(item["relation_type"] == "caption_of" and item["target_object_id"] == inline["object_id"] for item in first_relations)
    assert any(item["relation_type"] == "paragraph_references_figure" and item["target_object_id"] == inline["object_id"] for item in first_relations)
    assert any(item["relation_type"] == "reference_to" and item["target_object_id"] == inline["object_id"] for item in first_relations)
    assert any(item["relation_type"] == "section_contains_figure" and item["target_object_id"] == inline["object_id"] for item in first_relations)

    equations = [item for item in first_objects if item["object_type"] == "equation"]
    inline_equation = next(item for item in equations if item["attributes"]["placement"] == "inline")
    block_equation = next(item for item in equations if item["attributes"]["placement"] == "block")
    assert inline_equation["representation_status"] == "complete"
    assert inline_equation["attributes"]["gold_evidence_eligible"] is False
    assert block_equation["representation_status"] == "complete"
    assert block_equation["attributes"]["gold_evidence_eligible"] is True
    assert block_equation["attributes"]["raw_omml"]
    assert block_equation["attributes"]["raw_omml_sha256"]
    assert block_equation["attributes"]["omml_tree"]["tag"] == "oMathPara"
    assert block_equation["attributes"]["paragraph_object_id"]
    assert block_equation["attributes"]["context_before_paragraph_id"]
    assert block_equation["attributes"]["context_after_paragraph_id"]
    assert any(item["relation_type"] == "equation_in_paragraph" and item["source_object_id"] == block_equation["object_id"] for item in first_relations)
    assert any(item["relation_type"] == "section_contains_equation" and item["target_object_id"] == block_equation["object_id"] for item in first_relations)

    contract = CanonicalDocument.model_validate(
        {"manifest": first_manifest, "objects": first_objects, "relations": first_relations}
    )
    with pytest.raises(CanonicalContractError, match="prohibited as Gold evidence"):
        contract.require_complete_object(anchor["object_id"])


def test_ambiguous_multi_figure_caption_fails_closed(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    _manifest, objects, relations = _contract(authoring, _rich_fixture(ambiguous_caption=True), tmp_path)
    figures = [item for item in objects if item["object_type"] == "figure" and item["representation_status"] == "complete"]
    captions = [item for item in objects if item["object_type"] == "caption" and item["canonical_value"] == "Figure 1 Topology"]
    assert len(figures) == 2
    assert captions[0]["representation_status"] == "partial"
    assert all(item["attributes"]["gold_evidence_eligible"] is False for item in figures)
    assert not any(item["relation_type"] == "caption_of" and item["target_object_id"] in {figure["object_id"] for figure in figures} for item in relations)


def test_gold_eligible_figure_contract_requires_reliable_textual_topology(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    manifest, objects, relations = _contract(authoring, _rich_fixture(), tmp_path)
    anchor_index = next(index for index, item in enumerate(objects) if item["object_type"] == "figure" and item["attributes"]["anchor_kind"] == "anchor")
    invalid = json.loads(json.dumps({"manifest": manifest, "objects": objects, "relations": relations}))
    invalid["objects"][anchor_index]["attributes"]["gold_evidence_eligible"] = True
    with pytest.raises(ValidationError, match="Gold-eligible figure"):
        CanonicalDocument.model_validate(invalid)
