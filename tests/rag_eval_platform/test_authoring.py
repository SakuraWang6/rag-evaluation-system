from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_eval.api import create_app
from rag_eval.authoring.models import AuthoringState
from rag_eval.authoring.models import AnswerEvidenceCandidate, CandidateEvidence, CandidateState, DiscoveryMethod
from rag_eval.authoring.service import AuthoringService
from rag_eval.authoring.storage import AuthoringStorageError
from rag_eval.authoring.workflow import AuthoringWorkflowError
from rag_eval.datasets.bundle import load_bundle
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths


DOCX_MAIN = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<w:body>
 <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>系统概述</w:t></w:r></w:p>
 <w:p><w:bookmarkStart w:id="8" w:name="Scope"/><w:r><w:t>受控延迟为 42 ms。</w:t></w:r><w:bookmarkEnd w:id="8"/></w:p>
 <w:p><w:hyperlink r:id="rIdHyper"><w:r><w:t>产品说明</w:t></w:r></w:hyperlink></w:p>
 <w:tbl>
  <w:tr><w:tc><w:p><w:r><w:t>指标</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>数值</w:t></w:r></w:p></w:tc></w:tr>
  <w:tr><w:tc><w:p><w:r><w:t>延迟</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>42 ms</w:t></w:r></w:p></w:tc></w:tr>
 </w:tbl>
 <w:p><w:pPr><w:pStyle w:val="Caption"/></w:pPr><w:r><w:t>表 1 延迟指标</w:t></w:r></w:p>
 <w:p><w:r><w:drawing><wp:inline><wp:docPr id="1" name="架构图" descr="系统架构"/><a:graphic><a:graphicData><a:blip r:embed="rIdImage"/></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>
 <w:p><m:oMath><m:r><m:t>x = 42</m:t></m:r></m:oMath></w:p>
 <w:p><w:r><w:t>注释正文</w:t></w:r><w:r><w:footnoteReference w:id="1"/></w:r></w:p>
 <w:p><w:r><w:pict><v:shape id="shape1" title="流程图"/></w:pict></w:r><w:r><w:object><o:OLEObject ProgID="Excel.Sheet.12" r:id="rIdOle"/></w:object></w:r></w:p>
 <w:p><w:fldSimple w:instr="PAGEREF Scope \\h"><w:r><w:t>第 1 页</w:t></w:r></w:fldSimple></w:p>
 <w:sectPr/>
</w:body></w:document>"""

STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
 <w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="Caption"/></w:style>
</w:styles>"""

RELATIONSHIPS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rIdImage" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>
 <Relationship Id="rIdHyper" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.invalid/product" TargetMode="External"/>
 <Relationship Id="rIdOle" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject" Target="embeddings/object1.bin"/>
</Relationships>"""

FOOTNOTES = """<?xml version="1.0" encoding="UTF-8"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:footnote w:id="1"><w:p><w:r><w:t>已锚定脚注</w:t></w:r></w:p></w:footnote>
 <w:footnote w:id="2"><w:p><w:r><w:t>未锚定脚注</w:t></w:r></w:p></w:footnote>
</w:footnotes>"""


def mini_docx() -> bytes:
    value = io.BytesIO()
    with zipfile.ZipFile(value, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", DOCX_MAIN)
        archive.writestr("word/styles.xml", STYLES)
        archive.writestr("word/_rels/document.xml.rels", RELATIONSHIPS)
        archive.writestr("word/footnotes.xml", FOOTNOTES)
        archive.writestr("word/media/image1.png", b"not-rendered-in-test")
        archive.writestr("word/embeddings/object1.bin", b"ole")
    return value.getvalue()


def test_docx_ingest_rejects_extension_zip_and_traversal(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    with pytest.raises(AuthoringStorageError, match=".docx"):
        authoring.upload_docx(filename="source.txt", payload=mini_docx())
    with pytest.raises(AuthoringStorageError, match="OOXML ZIP"):
        authoring.upload_docx(filename="source.docx", payload=b"not a zip")

    unsafe = io.BytesIO()
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", DOCX_MAIN)
        archive.writestr("../outside.txt", "unsafe")
    with pytest.raises(AuthoringStorageError, match="unsafe ZIP"):
        authoring.upload_docx(filename="source.docx", payload=unsafe.getvalue())


def test_canonicalization_is_deterministic_and_inventories_rich_objects(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    first = authoring.upload_docx(filename="private.docx", payload=mini_docx())
    second = authoring.upload_docx(filename="private.docx", payload=mini_docx())
    first = authoring.analyze(first.authoring_dataset_id)
    second = authoring.analyze(second.authoring_dataset_id)

    assert first.state == AuthoringState.ANALYZED
    assert first.source.sha256 == second.source.sha256
    assert first.canonical_digest == second.canonical_digest
    assert first.document_id == second.document_id
    assert (tmp_path / "authoring" / first.authoring_dataset_id / "source" / "original.docx").read_bytes() == mini_docx()

    view = authoring.canonical_view(first.authoring_dataset_id)
    records = [json.loads(line) for line in (tmp_path / "authoring" / first.authoring_dataset_id / view.evidence_records_path).read_text().splitlines()]
    types = {(item["object_type"], item["status"]) for item in records}
    assert ("block", "supported") in types
    assert ("text_span", "supported") in types
    assert ("table", "supported") in types
    assert ("row", "supported") in types
    assert ("cell", "supported") in types
    assert ("figure", "supported") in types
    assert ("equation", "partial") in types
    assert ("embedded_object", "unsupported") in types
    assert ("note", "partial") in types
    assert ("note", "unsupported") in types
    assert ("reference", "partial") in types
    cell = next(item for item in records if item["object_type"] == "cell" and item["canonical_value"] == "42 ms")
    assert cell["table_id"] and cell["row"] == 2 and cell["column"] == 2
    markdown = authoring.canonical_markdown(first.authoring_dataset_id)
    assert "# 系统概述" in markdown
    assert "| 指标 | 数值 |" in markdown
    assert first.document_id not in markdown


def test_authoring_api_uses_private_workspace_and_explicit_analysis(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    client = TestClient(create_app(service, start_supervisor=False))
    uploaded = client.post(
        "/api/v1/authoring/datasets",
        content=mini_docx(),
        headers={"x-rag-eval-filename": "private.docx", "content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    )
    assert uploaded.status_code == 201
    dataset_id = uploaded.json()["authoring_dataset_id"]
    assert uploaded.json()["state"] == "uploaded"
    assert client.get("/api/v1/authoring/datasets").json()[0]["authoring_dataset_id"] == dataset_id

    analyzed = client.post(f"/api/v1/authoring/datasets/{dataset_id}/analyze")
    assert analyzed.status_code == 200
    assert analyzed.json()["state"] == "analyzed"
    canonical = client.get(f"/api/v1/authoring/datasets/{dataset_id}/canonical")
    assert canonical.status_code == 200
    assert "系统概述" in canonical.json()["execution_markdown"]
    removed = client.delete(f"/api/v1/authoring/datasets/{dataset_id}")
    assert removed.status_code == 204
    assert client.get(f"/api/v1/authoring/datasets/{dataset_id}").status_code == 404


def test_authoring_api_is_not_available_when_product_layer_is_disabled(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=False)
    client = TestClient(create_app(service, start_supervisor=False))
    assert client.get("/api/v1/authoring/datasets").status_code == 404


def test_rule_targets_manual_candidate_review_export_and_registration(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    assert service.authoring is not None
    dataset = service.authoring.upload_docx(filename="private.docx", payload=mini_docx())
    dataset = service.authoring.analyze(dataset.authoring_dataset_id)
    targets = service.authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.RULE)
    table_target = next(item for item in targets if item.capability == "table_lookup" and not item.flags)
    candidate = service.authoring.workflow.create_question(
        service.authoring.get(dataset.authoring_dataset_id),
        target_id=table_target.target_id,
        question="延迟指标对应的数值是多少？",
    )
    resolved = service.authoring.workflow.resolve_answer_evidence(
        service.authoring.get(dataset.authoring_dataset_id),
        candidate_id=candidate.candidate_id,
        resolution=AnswerEvidenceCandidate(
            answer_kind="text",
            canonical_answer="42 ms",
            evidence=[CandidateEvidence(source_object_id=table_target.source_object_ids[0])],
        ),
    )
    assert resolved.state == CandidateState.REVIEW_REQUIRED
    assert all(item.status != "FAIL" for item in resolved.gates)
    approved = service.authoring.workflow.review(
        service.authoring.get(dataset.authoring_dataset_id),
        candidate_id=candidate.candidate_id,
        decision="accept",
        reviewer="fixture-reviewer",
    )
    assert approved.state == CandidateState.APPROVED
    export = service.authoring.workflow.export(service.authoring.get(dataset.authoring_dataset_id), name="fixture-private-docx", version="1.0.0")
    root = service.authoring.store.workspace(dataset.authoring_dataset_id)
    canonical = load_bundle(root / export.views["canonical-text"])
    native = load_bundle(root / export.views["native-docx"])
    assert canonical.questions[0].case_id == native.questions[0].case_id
    assert canonical.manifest.documents[0].mime_type == "text/markdown"
    assert native.manifest.documents[0].mime_type.endswith("document")
    registered = service.datasets.register(root / export.views["canonical-text"])
    marked = service.authoring.workflow.mark_registered(service.authoring.get(dataset.authoring_dataset_id), release_id=export.release_id, view="canonical-text", bundle_id=registered.bundle_id)
    assert marked.registered_bundle_ids["canonical-text"] == registered.bundle_id


def test_failed_leakage_candidate_cannot_be_accepted_and_edit_versions_candidate(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id)
    target = next(item for item in authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.RULE) if item.capability == "table_lookup" and not item.flags)
    candidate = authoring.workflow.create_question(authoring.get(dataset.authoring_dataset_id), target_id=target.target_id, question="42 ms 是延迟指标的数值吗？")
    failed = authoring.workflow.resolve_answer_evidence(authoring.get(dataset.authoring_dataset_id), candidate_id=candidate.candidate_id, resolution=AnswerEvidenceCandidate(answer_kind="text", canonical_answer="42 ms", evidence=[CandidateEvidence(source_object_id=target.source_object_ids[0])]))
    assert failed.state == CandidateState.BLOCKED
    assert any(gate.gate_id == "answer_leakage" and gate.status == "FAIL" for gate in failed.gates)
    with pytest.raises(AuthoringWorkflowError, match="gate-reviewed"):
        authoring.workflow.review(authoring.get(dataset.authoring_dataset_id), candidate_id=candidate.candidate_id, decision="accept", reviewer="fixture-reviewer")
    edited = authoring.workflow.review(authoring.get(dataset.authoring_dataset_id), candidate_id=candidate.candidate_id, decision="edit", reviewer="fixture-reviewer", edited_question="延迟指标对应的数值是多少？")
    assert edited.version == 2
    assert edited.state == CandidateState.REVIEW_REQUIRED
    assert authoring.workflow.list_reviews(authoring.get(dataset.authoring_dataset_id))[0].decision == "edit"


def test_authoring_api_manual_review_export_and_bundle_registration(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    client = TestClient(create_app(service, start_supervisor=False))
    uploaded = client.post("/api/v1/authoring/datasets", content=mini_docx(), headers={"x-rag-eval-filename": "private.docx"})
    dataset_id = uploaded.json()["authoring_dataset_id"]
    assert client.post(f"/api/v1/authoring/datasets/{dataset_id}/analyze").status_code == 200
    targets = client.post(f"/api/v1/authoring/datasets/{dataset_id}/targets/discover", json={"provider": "rule"})
    assert targets.status_code == 200
    target = next(item for item in targets.json() if item["capability"] == "table_lookup" and not item["flags"])
    candidate = client.post(f"/api/v1/authoring/datasets/{dataset_id}/candidates", json={"target_id": target["target_id"], "question": "延迟指标对应的数值是多少？"})
    assert candidate.status_code == 201
    candidate_id = candidate.json()["candidate_id"]
    resolved = client.post(f"/api/v1/authoring/datasets/{dataset_id}/candidates/{candidate_id}/resolve", json={"resolution": {"answer_kind": "text", "canonical_answer": "42 ms", "evidence": [{"source_object_id": target["source_object_ids"][0]}]}})
    assert resolved.json()["state"] == "review_required"
    accepted = client.post(f"/api/v1/authoring/datasets/{dataset_id}/candidates/{candidate_id}/review", json={"decision": "accept", "reviewer": "fixture-reviewer"})
    assert accepted.json()["state"] == "approved"
    exported = client.post(f"/api/v1/authoring/datasets/{dataset_id}/exports", json={"name": "api-fixture", "version": "1.0.0"})
    assert exported.status_code == 201
    release_id = exported.json()["release_id"]
    registered = client.post(f"/api/v1/authoring/datasets/{dataset_id}/exports/{release_id}/register/canonical-text")
    assert registered.status_code == 200
    assert registered.json()["bundle_id"] in [item["bundle_id"] for item in client.get("/api/v1/datasets").json()]
