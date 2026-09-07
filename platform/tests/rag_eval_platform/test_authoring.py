from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from rag_eval.api import create_app
from rag_eval.authoring.models import (
    AuthoringState,
    DiscoveryJobPhase,
    DiscoveryJobStatus,
    GenerationJobItemState,
    GenerationJobStatus,
)
from rag_eval.authoring.models import AnswerEvidenceCandidate, CandidateEvidence, CandidateState, DiscoveryMethod
from rag_eval.authoring.service import AuthoringService
from rag_eval.authoring.canonical import CANONICALIZER_VERSION
from rag_eval.authoring.providers import ProposalProviderError
from rag_eval.authoring.storage import CANONICALIZER_IDENTITY, AuthoringStorageError
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
  <w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>
  <w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:p><w:r><w:t>指标</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>数值</w:t></w:r></w:p></w:tc></w:tr>
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

DOCX_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def mini_docx() -> bytes:
    value = io.BytesIO()
    with zipfile.ZipFile(value, "w") as archive:
        members = (
            ("[Content_Types].xml", "<Types/>"),
            ("word/document.xml", DOCX_MAIN),
            ("word/styles.xml", STYLES),
            ("word/_rels/document.xml.rels", RELATIONSHIPS),
            ("word/footnotes.xml", FOOTNOTES),
            ("word/media/image1.png", b"not-rendered-in-test"),
            ("word/embeddings/object1.bin", b"ole"),
        )
        for name, payload in members:
            info = zipfile.ZipInfo(name, date_time=DOCX_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, payload)
    return value.getvalue()


def test_source_manifest_identity_tracks_canonicalizer_implementation() -> None:
    assert CANONICALIZER_IDENTITY == CANONICALIZER_VERSION


def runtime_provenance_map(
    *,
    document_id: str,
    canonical_digest: str,
    object_id: str,
    coverage: str,
) -> dict[str, object]:
    chunk_id = "runtime-chunk-001"
    overlap_span = {"start": 10, "end": 20}
    return {
        "schema_version": 1,
        "documents": {
            document_id: {
                "document_id": document_id,
                "canonical_digest": canonical_digest,
            }
        },
        "runtime_chunks": {
            chunk_id: {
                "runtime_chunk_id": chunk_id,
                "document_id": document_id,
                "provenance_status": "full",
                "canonical_objects": [
                    {
                        "object_id": object_id,
                        "coverage": coverage,
                        "overlap_span": overlap_span,
                    }
                ],
            }
        },
        "object_to_runtime_chunks": {
            object_id: [
                {
                    "runtime_chunk_id": chunk_id,
                    "coverage": coverage,
                    "overlap_span": overlap_span,
                }
            ]
        },
    }


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


def test_authoring_archive_is_soft_and_preserves_source_workspace(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.upload_docx(filename="source.docx", payload=mini_docx())

    archived = authoring.archive(dataset.authoring_dataset_id)

    assert archived.state == AuthoringState.ARCHIVED
    assert archived.archived_at is not None
    assert authoring.get(dataset.authoring_dataset_id).state == AuthoringState.ARCHIVED
    assert authoring.store.source_path(dataset.authoring_dataset_id).is_file()


def test_authoring_delete_requires_an_explicit_archive(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.upload_docx(filename="source.docx", payload=mini_docx())

    with pytest.raises(AuthoringStorageError, match="only an archived"):
        authoring.delete(dataset.authoring_dataset_id)
    assert authoring.get(dataset.authoring_dataset_id).state == AuthoringState.UPLOADED

    authoring.archive(dataset.authoring_dataset_id)
    authoring.delete(dataset.authoring_dataset_id)
    with pytest.raises(FileNotFoundError):
        authoring.get(dataset.authoring_dataset_id)


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
    assert ("equation", "supported") in types
    assert ("embedded_object", "unsupported") in types
    assert ("note", "partial") in types
    assert ("note", "unsupported") in types
    assert ("reference", "partial") in types
    equation = next(item for item in records if item["object_type"] == "equation")
    assert equation["placement"] == "inline"
    assert equation["raw_omml"]
    assert equation["omml_tree"]
    assert equation["gold_evidence_eligible"] is False
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
    document = client.get(f"/api/v1/authoring/datasets/{dataset_id}/document")
    assert document.status_code == 200
    assert document.json()["filename"] == "private.docx"
    assert any(block["kind"] == "heading" and block["text"] == "系统概述" for block in document.json()["blocks"])
    table = next(block for block in document.json()["blocks"] if block["kind"] == "table")
    assert any(cell["text"] == "42 ms" and cell["object_ids"] for cell in table["cells"])
    native = client.get(f"/api/v1/authoring/datasets/{dataset_id}/document/native")
    assert native.status_code == 200
    assert native.headers["content-type"].startswith("text/html")
    assert "系统概述" in native.text
    assert "docx-heading-1" in native.text
    assert "docx-table" in native.text
    assert "第 1 页" in native.text
    # Word margins are often fractional pixels after twip conversion. The
    # native paginator must use integer layout space so it does not split each
    # following paragraph into its own otherwise blank page.
    assert "Math.floor(pageHeight - marginTop - marginBottom)" in native.text
    cannot_remove_active = client.delete(f"/api/v1/authoring/datasets/{dataset_id}")
    assert cannot_remove_active.status_code == 409
    assert "only an archived" in cannot_remove_active.json()["detail"]
    archived = client.post(f"/api/v1/authoring/datasets/{dataset_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["state"] == "archived"
    assert client.get(f"/api/v1/authoring/datasets/{dataset_id}/source").status_code == 200
    removed = client.delete(f"/api/v1/authoring/datasets/{dataset_id}")
    assert removed.status_code == 204
    assert client.get(f"/api/v1/authoring/datasets/{dataset_id}").status_code == 404


def test_authoring_document_view_is_cached_until_canonical_reanalysis(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )

    first = authoring.document_view(dataset.authoring_dataset_id)
    second = authoring.document_view(dataset.authoring_dataset_id)

    assert first is second
    heading = next(item for item in first.blocks if item.kind == "heading")
    assert heading.heading_level == 1
    assert heading.page_break_before is False
    authoring.analyze(dataset.authoring_dataset_id)
    assert authoring.document_view(dataset.authoring_dataset_id) is not first


def test_authoring_api_accepts_utf8_encoded_filename_header(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    client = TestClient(create_app(service, start_supervisor=False))
    filename = "XXX网站系统（S2A2G2）_V2.0.docx"

    uploaded = client.post(
        "/api/v1/authoring/datasets",
        content=mini_docx(),
        headers={
            "content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "x-rag-eval-filename": f"utf-8''{quote(filename, safe='')}",
        },
    )

    assert uploaded.status_code == 201
    assert uploaded.json()["source"]["original_filename"] == filename


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


@pytest.mark.parametrize(
    ("coverage", "expected_gate_status", "expected_case_status"),
    [
        ("full", "PASS", "FULL"),
        ("partial", "FLAG", "PARTIAL_UNOBSERVABLE"),
    ],
)
def test_runtime_evidence_representability_is_diagnostic_and_exported(
    tmp_path: Path,
    coverage: str,
    expected_gate_status: str,
    expected_case_status: str,
) -> None:
    authoring = AuthoringService(tmp_path / coverage / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )
    target = next(
        item
        for item in authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.RULE)
        if item.capability == "table_lookup" and not item.flags
    )
    assert dataset.document_id and dataset.canonical_digest
    profile = authoring.workflow.register_representability_profile(
        authoring.get(dataset.authoring_dataset_id),
        profile_id="lightrag-canonical-fixture",
        system_id="lightrag",
        adapter_id="lightrag",
        execution_profile_digest="0" * 64,
        runtime_map=runtime_provenance_map(
            document_id=dataset.document_id,
            canonical_digest=dataset.canonical_digest,
            object_id=target.source_object_ids[0],
            coverage=coverage,
        ),
    )
    assert profile.runtime_chunk_count == 1
    candidate = authoring.workflow.create_question(
        authoring.get(dataset.authoring_dataset_id),
        target_id=target.target_id,
        question="延迟指标对应的数值是多少？",
    )
    resolved = authoring.workflow.resolve_answer_evidence(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=candidate.candidate_id,
        resolution=AnswerEvidenceCandidate(
            answer_kind="text",
            canonical_answer="42 ms",
            evidence=[CandidateEvidence(source_object_id=target.source_object_ids[0])],
        ),
    )
    gate = next(
        item
        for item in resolved.gates
        if item.gate_id == "runtime_evidence_representability"
    )
    assert gate.status == expected_gate_status
    assert gate.details["case_status"] == expected_case_status

    approved = authoring.workflow.review(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=candidate.candidate_id,
        decision="accept",
        reviewer="fixture-reviewer",
        note="representability classification reviewed",
    )
    assert approved.state == CandidateState.APPROVED
    exported = authoring.workflow.export(
        authoring.get(dataset.authoring_dataset_id),
        name=f"representability-{coverage}",
        version="1.0.0",
    )
    bundle = load_bundle(
        authoring.store.workspace(dataset.authoring_dataset_id)
        / exported.views["canonical-text"]
    )
    diagnostic = bundle.questions[0].metadata["runtime_evidence_representability"]
    assert diagnostic["gate_status"] == expected_gate_status
    assert diagnostic["case_status"] == expected_case_status


def test_runtime_evidence_representability_rejects_non_round_tripping_map(
    tmp_path: Path,
) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )
    target = next(
        item
        for item in authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.RULE)
        if item.capability == "table_lookup" and not item.flags
    )
    assert dataset.document_id and dataset.canonical_digest
    runtime_map = runtime_provenance_map(
        document_id=dataset.document_id,
        canonical_digest=dataset.canonical_digest,
        object_id=target.source_object_ids[0],
        coverage="full",
    )
    runtime_map["runtime_chunks"]["runtime-chunk-001"]["canonical_objects"] = []  # type: ignore[index]
    with pytest.raises(AuthoringWorkflowError, match="round-trip"):
        authoring.workflow.register_representability_profile(
            authoring.get(dataset.authoring_dataset_id),
            profile_id="invalid-map",
            system_id="lightrag",
            adapter_id="lightrag",
            execution_profile_digest="0" * 64,
            runtime_map=runtime_map,
        )


def test_negative_cell_scope_exports_table_cell_locator_and_release_can_select_cases(
    tmp_path: Path,
) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )
    targets = authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.RULE)
    cell_target = next(
        item
        for item in targets
        if item.capability == "table_lookup" and not item.flags
    )
    records = [
        json.loads(line)
        for line in (
            authoring.store.workspace(dataset.authoring_dataset_id)
            / "canonical/evidence.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]
    cell = next(
        item
        for item in records
        if item["object_type"] == "cell" and item["canonical_value"] == "42 ms"
    )
    target = authoring.workflow.create_target(
        authoring.get(dataset.authoring_dataset_id),
        capability="negative_abstention",
        source_object_ids=[cell["object_id"]],
        retrieval_route=["table", "scoped_absence"],
    )
    negative = authoring.workflow.create_question(
        authoring.get(dataset.authoring_dataset_id),
        target_id=target.target_id,
        question="该表是否提供了未列出的延迟版本？",
    )
    negative = authoring.workflow.resolve_answer_evidence(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=negative.candidate_id,
        resolution=AnswerEvidenceCandidate(
            answer_kind="abstain",
            negative_scope_object_ids=[cell["object_id"]],
            negative_rationale="the scoped cell contains no separate version field",
        ),
    )
    negative = authoring.workflow.review(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=negative.candidate_id,
        decision="accept",
        reviewer="fixture-reviewer",
    )
    excluded = authoring.workflow.create_question(
        authoring.get(dataset.authoring_dataset_id),
        target_id=cell_target.target_id,
        question="延迟指标的值是多少？",
    )
    excluded = authoring.workflow.resolve_answer_evidence(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=excluded.candidate_id,
        resolution=AnswerEvidenceCandidate(
            answer_kind="text",
            canonical_answer="42 ms",
            evidence=[CandidateEvidence(source_object_id=cell_target.source_object_ids[0])],
        ),
    )
    excluded = authoring.workflow.review(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=excluded.candidate_id,
        decision="accept",
        reviewer="fixture-reviewer",
    )
    selected_case_id = f"case-{negative.candidate_id.removeprefix('candidate-')}"
    excluded_case_id = f"case-{excluded.candidate_id.removeprefix('candidate-')}"
    export = authoring.workflow.export(
        authoring.get(dataset.authoring_dataset_id),
        name="selected-negative",
        version="1.0.0",
        approved_case_ids=[selected_case_id],
    )
    assert export.approved_case_ids == [selected_case_id]
    assert excluded_case_id not in export.approved_case_ids
    bundle = load_bundle(
        authoring.store.workspace(dataset.authoring_dataset_id)
        / export.views["canonical-text"]
    )
    locator = next(iter(bundle.gold_evidence_sets.values())).evidence[0].locator
    assert locator.type == "table_cell"
    assert locator.table_id == cell["table_id"]
    assert locator.row == cell["row"]
    assert locator.column == cell["column"]


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


def test_rejected_candidate_does_not_block_regenerating_the_same_question(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )
    target = next(
        item
        for item in authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.RULE)
        if item.capability == "table_lookup" and not item.flags
    )
    question = "延迟指标对应的数值是多少？"
    first = authoring.workflow.create_question(
        authoring.get(dataset.authoring_dataset_id), target_id=target.target_id, question=question
    )
    first = authoring.workflow.resolve_answer_evidence(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=first.candidate_id,
        resolution=AnswerEvidenceCandidate(
            answer_kind="text",
            canonical_answer="42 ms",
            evidence=[CandidateEvidence(source_object_id=target.source_object_ids[0])],
        ),
    )
    assert first.state == CandidateState.REVIEW_REQUIRED
    rejected = authoring.workflow.review(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=first.candidate_id,
        decision="reject",
        reviewer="fixture-reviewer",
    )
    assert rejected.state == CandidateState.REJECTED

    regenerated = authoring.workflow.create_question(
        authoring.get(dataset.authoring_dataset_id), target_id=target.target_id, question=question
    )
    regenerated = authoring.workflow.resolve_answer_evidence(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=regenerated.candidate_id,
        resolution=AnswerEvidenceCandidate(
            answer_kind="text",
            canonical_answer="42 ms",
            evidence=[CandidateEvidence(source_object_id=target.source_object_ids[0])],
        ),
    )
    assert regenerated.state == CandidateState.REVIEW_REQUIRED
    duplicate_gate = next(item for item in regenerated.gates if item.gate_id == "duplicate_template_overlap")
    assert duplicate_gate.status == "PASS"

    # A failed historical proposal is likewise not an active question.  This
    # models a prior generation that was blocked before the author could
    # review it, then retries the same source after fixing the cause.
    authoring.workflow._save_candidate(
        authoring.get(dataset.authoring_dataset_id),
        regenerated.model_copy(update={"state": CandidateState.BLOCKED}),
    )
    retried = authoring.workflow.create_question(
        authoring.get(dataset.authoring_dataset_id), target_id=target.target_id, question=question
    )
    retried = authoring.workflow.resolve_answer_evidence(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=retried.candidate_id,
        resolution=AnswerEvidenceCandidate(
            answer_kind="text",
            canonical_answer="42 ms",
            evidence=[CandidateEvidence(source_object_id=target.source_object_ids[0])],
        ),
    )
    assert retried.state == CandidateState.REVIEW_REQUIRED
    duplicate_gate = next(item for item in retried.gates if item.gate_id == "duplicate_template_overlap")
    assert duplicate_gate.status == "PASS"


def test_non_ascii_evidence_group_is_serialized_with_a_safe_ledger_clause_id(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )
    target = next(
        item
        for item in authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.RULE)
        if item.capability == "table_lookup" and not item.flags
    )
    candidate = authoring.workflow.create_question(
        authoring.get(dataset.authoring_dataset_id),
        target_id=target.target_id,
        question="延迟指标对应的数值是多少？",
    )

    resolved = authoring.workflow.resolve_answer_evidence(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=candidate.candidate_id,
        resolution=AnswerEvidenceCandidate(
            answer_kind="text",
            canonical_answer="42 ms",
            evidence=[
                CandidateEvidence(
                    source_object_id=target.source_object_ids[0],
                    required_group="符合情况",
                )
            ],
        ),
    )

    assert resolved.state == CandidateState.REVIEW_REQUIRED
    gold = authoring.workflow.ledger.current_gold(
        dataset.authoring_dataset_id,
        authoring.workflow.ledger.gold_id_for_case(
            authoring.workflow.ledger.case_id_for_candidate(candidate.candidate_id)
        ),
    )
    assert gold.payload.mses_paths[0].clauses[0].clause_id == "clause-1"


def test_target_discovery_source_is_bounded_without_witnesses(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )
    object_ids = [str(item["object_id"]) for item in authoring.workflow._records(dataset.authoring_dataset_id)]

    source = authoring.workflow._source_subset(
        dataset,
        object_ids,
        max_items=1,
        max_value_chars=1,
        include_witness=False,
    )

    assert len(source) == 1
    assert "witness" not in source[0]
    assert "canonical_value" in source[0]


def test_unavailable_local_model_falls_back_to_reviewable_direct_source_proposals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )
    records = {
        str(record["object_id"]): record
        for record in authoring.workflow._records(dataset.authoring_dataset_id)
    }
    target = next(
        item
        for item in authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.RULE)
        if item.capability == "table_lookup"
        and not item.flags
        and any(records[object_id]["canonical_value"] == "42 ms" for object_id in item.source_object_ids)
    )

    def unavailable(**_: object) -> tuple[dict[str, object], dict[str, object], DiscoveryMethod]:
        raise ProposalProviderError("Ollama is not available in this test")

    monkeypatch.setattr(authoring.workflow, "_proposal", unavailable)
    candidate = authoring.workflow.generate_question(
        authoring.get(dataset.authoring_dataset_id), target_id=target.target_id
    )
    resolved = authoring.workflow.generate_answer_evidence(
        authoring.get(dataset.authoring_dataset_id), candidate_id=candidate.candidate_id
    )

    assert candidate.generation_method == DiscoveryMethod.RULE
    assert candidate.question.startswith("文档表格中")
    assert resolved.answer_evidence is not None
    assert resolved.answer_evidence.canonical_answer == "42 ms"
    assert resolved.answer_evidence.resolution_method == DiscoveryMethod.RULE
    assert resolved.state == CandidateState.REVIEW_REQUIRED
    assert resolved.state != CandidateState.APPROVED


def test_combined_proposal_normalizes_known_model_schema_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )
    records = {
        str(record["object_id"]): record
        for record in authoring.workflow._records(dataset.authoring_dataset_id)
    }
    target = next(
        item
        for item in authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.RULE)
        if item.capability == "table_lookup"
        and not item.flags
        and any(records[object_id]["canonical_value"] == "42 ms" for object_id in item.source_object_ids)
    )
    answer_object_id = next(
        object_id
        for object_id in target.source_object_ids
        if records[object_id]["canonical_value"] == "42 ms"
    )

    def generated(**kwargs: object) -> tuple[dict[str, object], dict[str, object], DiscoveryMethod]:
        if kwargs["task"] == "question_generation":
            return (
                {
                    "question": "延迟指标对应的数值是多少？",
                    "source_object_ids": [answer_object_id],
                },
                {"provider": "fixture-model"},
                DiscoveryMethod.OLLAMA,
            )
        assert kwargs["task"] == "answer_evidence_resolution"
        # These are realistic provider variants, not valid Platform contract
        # values.  The workflow must normalize their shape before validation.
        return (
            {
                "answer_kind": "canonical",
                "canonical_answer": "42 ms",
                "accepted_values": None,
                "evidence": {"source_object_id": answer_object_id},
                "dependency_graph": {
                    answer_object_id: {
                        "description": "该单元格给出延迟指标的数值",
                        "dependency_type": "defines",
                    }
                },
            },
            {"provider": "fixture-model"},
            DiscoveryMethod.OLLAMA,
        )

    monkeypatch.setattr(authoring.workflow, "_proposal", generated)
    candidate = authoring.workflow.generate_question_and_answer(
        authoring.get(dataset.authoring_dataset_id), target_id=target.target_id
    )

    assert candidate.state == CandidateState.REVIEW_REQUIRED
    assert candidate.answer_evidence is not None
    assert candidate.answer_evidence.answer_kind == "text"
    assert candidate.answer_evidence.accepted_values == []
    assert candidate.answer_evidence.evidence[0].source_object_id == answer_object_id
    assert candidate.answer_evidence.dependency_graph == [
        {
            "node_id": answer_object_id,
            "description": "该单元格给出延迟指标的数值",
            "dependency_type": "defines",
        }
    ]
    assert "answer_kind:canonical->text" in candidate.answer_evidence.provider_metadata["contract_normalizations"]
    assert "dependency_graph:adjacency-object->list" in candidate.answer_evidence.provider_metadata["contract_normalizations"]


def test_malformed_local_answer_proposal_safely_falls_back_to_direct_canonical_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )
    records = {
        str(record["object_id"]): record
        for record in authoring.workflow._records(dataset.authoring_dataset_id)
    }
    target = next(
        item
        for item in authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.RULE)
        if item.capability == "table_lookup"
        and not item.flags
        and any(records[object_id]["canonical_value"] == "42 ms" for object_id in item.source_object_ids)
    )
    answer_object_id = next(
        object_id
        for object_id in target.source_object_ids
        if records[object_id]["canonical_value"] == "42 ms"
    )

    def malformed(**kwargs: object) -> tuple[dict[str, object], dict[str, object], DiscoveryMethod]:
        if kwargs["task"] == "question_generation":
            return (
                {
                    "question": "延迟指标对应的数值是多少？",
                    "source_object_ids": [answer_object_id],
                },
                {"provider": "fixture-model"},
                DiscoveryMethod.OLLAMA,
            )
        return (
            {
                "answer_kind": "not-a-formal-answer-kind",
                "canonical_answer": "42 ms",
                "evidence": [{"source_object_id": answer_object_id}],
                "dependency_graph": [],
            },
            {"provider": "fixture-model"},
            DiscoveryMethod.OLLAMA,
        )

    monkeypatch.setattr(authoring.workflow, "_proposal", malformed)
    candidate = authoring.workflow.generate_question_and_answer(
        authoring.get(dataset.authoring_dataset_id), target_id=target.target_id
    )

    assert candidate.state == CandidateState.REVIEW_REQUIRED
    assert candidate.answer_evidence is not None
    assert candidate.answer_evidence.canonical_answer == "42 ms"
    assert candidate.answer_evidence.resolution_method == DiscoveryMethod.RULE
    assert candidate.answer_evidence.provider_metadata["reason"] == "invalid_local_model_answer_contract"


def test_malformed_local_target_discovery_falls_back_to_safe_rule_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )

    def malformed(*args: object, **kwargs: object) -> list[object]:
        raise AuthoringWorkflowError("target proposal must contain a targets array")

    monkeypatch.setattr(authoring.workflow, "_ollama_targets", malformed)
    targets = authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.OLLAMA)

    assert targets
    assert all("invalid_local_model_target_contract" in target.flags for target in targets)
    assert any(target.capability == "table_lookup" for target in targets)
    assert any(target.capability == "negative_candidate" for target in targets)


def test_unexpected_local_target_discovery_error_falls_back_to_safe_rule_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provider integration failures must not disconnect the authoring UI."""

    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )

    def unexpected(*args: object, **kwargs: object) -> list[object]:
        raise RuntimeError("fixture provider normalization failed")

    monkeypatch.setattr(authoring.workflow, "_ollama_targets", unexpected)
    targets = authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.OLLAMA)

    assert targets
    assert all(
        "local_model_discovery_failed_rule_fallback:RuntimeError" in target.flags
        for target in targets
    )
    assert any(target.capability == "table_lookup" for target in targets)


def test_authoring_api_generates_one_complete_reviewable_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    client = TestClient(create_app(service, start_supervisor=False))
    uploaded = client.post(
        "/api/v1/authoring/datasets",
        content=mini_docx(),
        headers={"x-rag-eval-filename": "private.docx"},
    )
    dataset_id = uploaded.json()["authoring_dataset_id"]
    assert client.post(f"/api/v1/authoring/datasets/{dataset_id}/analyze").status_code == 200
    targets = client.post(
        f"/api/v1/authoring/datasets/{dataset_id}/targets/discover",
        json={"provider": "rule"},
    ).json()
    dataset = service.authoring.get(dataset_id)
    records = {
        str(record["object_id"]): record
        for record in service.authoring.workflow._records(dataset_id)
    }
    target = next(
        item
        for item in targets
        if item["capability"] == "table_lookup"
        and not item["flags"]
        and any(records[object_id]["canonical_value"] == "42 ms" for object_id in item["source_object_ids"])
    )
    answer_object_id = next(
        object_id
        for object_id in target["source_object_ids"]
        if records[object_id]["canonical_value"] == "42 ms"
    )

    def generated(**kwargs: object) -> tuple[dict[str, object], dict[str, object], DiscoveryMethod]:
        if kwargs["task"] == "question_generation":
            return (
                {"question": "延迟指标对应的数值是多少？", "source_object_ids": [answer_object_id]},
                {"provider": "fixture-model"},
                DiscoveryMethod.OLLAMA,
            )
        return (
            {
                "answer_kind": "canonical",
                "canonical_answer": "42 ms",
                "evidence": [{"source_object_id": answer_object_id}],
                "dependency_graph": {},
            },
            {"provider": "fixture-model"},
            DiscoveryMethod.OLLAMA,
        )

    monkeypatch.setattr(service.authoring.workflow, "_proposal", generated)
    response = client.post(
        f"/api/v1/authoring/datasets/{dataset_id}/candidates/generate-proposal",
        json={"target_id": target["target_id"]},
    )

    assert response.status_code == 201
    assert response.json()["state"] == "review_required"
    assert response.json()["answer_evidence"]["canonical_answer"] == "42 ms"
    assert response.json()["answer_evidence"]["answer_kind"] == "text"


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


def test_authoring_api_publishes_and_removes_formal_catalog_version_without_erasing_history(
    tmp_path: Path,
) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    client = TestClient(create_app(service, start_supervisor=False))
    uploaded = client.post(
        "/api/v1/authoring/datasets",
        content=mini_docx(),
        headers={"x-rag-eval-filename": "private.docx"},
    )
    dataset_id = uploaded.json()["authoring_dataset_id"]
    assert client.post(f"/api/v1/authoring/datasets/{dataset_id}/analyze").status_code == 200
    targets = client.post(
        f"/api/v1/authoring/datasets/{dataset_id}/targets/discover",
        json={"provider": "rule"},
    ).json()
    target = next(item for item in targets if item["capability"] == "table_lookup" and not item["flags"])
    created = client.post(
        f"/api/v1/authoring/datasets/{dataset_id}/candidates",
        json={"target_id": target["target_id"], "question": "延迟指标对应的数值是多少？"},
    )
    assert created.status_code == 201
    candidate_id = created.json()["candidate_id"]
    resolved = client.post(
        f"/api/v1/authoring/datasets/{dataset_id}/candidates/{candidate_id}/resolve",
        json={
            "resolution": {
                "answer_kind": "text",
                "canonical_answer": "42 ms",
                "evidence": [{"source_object_id": target["source_object_ids"][0]}],
            }
        },
    )
    assert resolved.json()["state"] == "review_required"
    assert client.post(
        f"/api/v1/authoring/datasets/{dataset_id}/candidates/{candidate_id}/review",
        json={"decision": "accept", "reviewer": "fixture-reviewer"},
    ).json()["state"] == "approved"

    published = client.post(
        f"/api/v1/authoring/datasets/{dataset_id}/formal-releases",
        json={
            "display_name": "网络安全测评",
            "release_version": "1.0.0",
            "actor": "release-manager",
        },
    )

    assert published.status_code == 201
    release_id = published.json()["release_id"]
    assert published.json()["name"] == "网络安全测评"
    # The internal workspace is retained for immutable provenance only.  It
    # must no longer be mistaken for a resumable product-flow draft.
    assert service.authoring.get(dataset_id).state == AuthoringState.FORMAL_RELEASED
    # Existing local workspaces published before this transition are migrated
    # when the product next lists authoring records.
    service.authoring.store.save(
        service.authoring.get(dataset_id).model_copy(
            update={"state": AuthoringState.APPROVED, "formal_release_ids": []}
        )
    )
    assert client.get("/api/v1/authoring/datasets").status_code == 200
    released_workspace = client.get(f"/api/v1/authoring/datasets/{dataset_id}")
    assert released_workspace.status_code == 200
    assert released_workspace.json()["state"] == AuthoringState.FORMAL_RELEASED
    assert released_workspace.json()["formal_release_ids"] == [release_id]
    frozen_mutation = client.post(
        f"/api/v1/authoring/datasets/{dataset_id}/candidates/{candidate_id}/resolve",
        json={
            "resolution": {
                "answer_kind": "text",
                "canonical_answer": "42 ms",
                "evidence": [{"source_object_id": target["source_object_ids"][0]}],
            }
        },
    )
    assert frozen_mutation.status_code == 400
    assert "already published" in frozen_mutation.json()["detail"]
    catalog = client.get("/api/v1/product/formal-datasets")
    assert release_id in [item["release_id"] for item in catalog.json()["releases"]]
    assert next(item for item in catalog.json()["releases"] if item["release_id"] == release_id)["name"] == "网络安全测评"
    assert client.delete(f"/api/v1/product/formal-datasets/{release_id}").status_code == 200
    assert release_id not in [item["release_id"] for item in client.get("/api/v1/product/formal-datasets").json()["releases"]]
    # A removed catalog item remains resolvable for historical lineage and
    # never deletes the immutable Case/Gold/source snapshots.
    assert client.get(f"/api/v1/product/formal-datasets/{release_id}/content").status_code == 200


def test_authoring_batch_generation_job_persists_partial_failure_and_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Closing/reopening a flow can read a per-target job, including diagnostics."""

    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )
    targets = [
        item
        for item in authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.RULE)
        if not item.flags
    ][:2]
    assert len(targets) == 2
    attempts: dict[str, int] = {}

    class Generated:
        def __init__(self, target_id: str) -> None:
            self.candidate_id = f"candidate-{target_id.removeprefix('target-')[:16]}"

    def generated(_dataset: object, *, target_id: str, **_: object) -> Generated:
        attempts[target_id] = attempts.get(target_id, 0) + 1
        if target_id == targets[1].target_id and attempts[target_id] == 1:
            raise ProposalProviderError("fixture model connection timed out")
        return Generated(target_id)

    monkeypatch.setattr(authoring.workflow, "generate_question_and_answer", generated)
    job = authoring.workflow.create_generation_job(
        dataset, target_ids=[item.target_id for item in targets]
    )
    assert authoring.store.generation_job_path(dataset.authoring_dataset_id, job.job_id).is_file()

    partial = authoring.workflow.run_generation_job(dataset, job_id=job.job_id)
    assert partial.state == GenerationJobStatus.PARTIAL
    assert [item.state for item in partial.items] == [
        GenerationJobItemState.SUCCEEDED,
        GenerationJobItemState.FAILED,
    ]
    assert partial.items[1].error_code == "provider_unavailable"
    assert partial.items[1].error_detail == "fixture model connection timed out"

    retried = authoring.workflow.retry_generation_job(dataset, job_id=job.job_id)
    assert retried.state == GenerationJobStatus.QUEUED
    assert retried.items[0].state == GenerationJobItemState.SUCCEEDED
    assert retried.items[1].state == GenerationJobItemState.PENDING
    completed = authoring.workflow.run_generation_job(dataset, job_id=job.job_id)
    assert completed.state == GenerationJobStatus.COMPLETED
    assert [item.attempts for item in completed.items] == [1, 2]


def test_authoring_discovery_job_persists_progress_and_allows_a_slow_local_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )
    observed_timeouts: list[float | None] = []

    def model_targets(*_args: object, timeout_seconds: float | None, **_kwargs: object) -> list[object]:
        observed_timeouts.append(timeout_seconds)
        return []

    monkeypatch.setattr(authoring.workflow, "_ollama_targets", model_targets)
    job = authoring.workflow.create_discovery_job(dataset)
    assert authoring.store.discovery_job_path(dataset.authoring_dataset_id, job.job_id).is_file()

    completed = authoring.workflow.run_discovery_job(dataset, job_id=job.job_id)

    assert observed_timeouts == [None]
    assert completed.state == DiscoveryJobStatus.COMPLETED
    assert completed.phase == DiscoveryJobPhase.COMPLETED
    assert completed.total_source_records > 0
    assert completed.rule_target_count > 0
    assert completed.target_count > 0
    assert authoring.workflow.get_discovery_job(dataset, job.job_id) == completed
    assert authoring.workflow.list_targets(dataset)


def test_authoring_discovery_job_api_queues_and_lists_a_persisted_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    client = TestClient(create_app(service, start_supervisor=False))
    uploaded = client.post(
        "/api/v1/authoring/datasets",
        content=mini_docx(),
        headers={"x-rag-eval-filename": "private.docx"},
    )
    dataset_id = uploaded.json()["authoring_dataset_id"]
    assert client.post(f"/api/v1/authoring/datasets/{dataset_id}/analyze").status_code == 200
    observed_timeouts: list[float | None] = []

    def model_targets(*_args: object, timeout_seconds: float | None, **_kwargs: object) -> list[object]:
        observed_timeouts.append(timeout_seconds)
        return []

    monkeypatch.setattr(service.authoring.workflow, "_ollama_targets", model_targets)
    queued = client.post(
        f"/api/v1/authoring/datasets/{dataset_id}/discovery-jobs",
        json={"provider": "ollama"},
    )

    assert queued.status_code == 202
    job_id = queued.json()["job_id"]
    jobs = client.get(f"/api/v1/authoring/datasets/{dataset_id}/discovery-jobs")
    assert jobs.status_code == 200
    assert jobs.json()[0]["job_id"] == job_id
    assert jobs.json()[0]["state"] == DiscoveryJobStatus.COMPLETED
    assert observed_timeouts == [None]


def test_authoring_batch_generation_api_queues_and_lists_a_persisted_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    client = TestClient(create_app(service, start_supervisor=False))
    uploaded = client.post(
        "/api/v1/authoring/datasets",
        content=mini_docx(),
        headers={"x-rag-eval-filename": "private.docx"},
    )
    dataset_id = uploaded.json()["authoring_dataset_id"]
    assert client.post(f"/api/v1/authoring/datasets/{dataset_id}/analyze").status_code == 200
    targets = client.post(
        f"/api/v1/authoring/datasets/{dataset_id}/targets/discover",
        json={"provider": "rule"},
    ).json()
    target = next(item for item in targets if not item["flags"])

    class Generated:
        candidate_id = "candidate-fixture-job"

    monkeypatch.setattr(
        service.authoring.workflow,
        "generate_question_and_answer",
        lambda *_args, **_kwargs: Generated(),
    )
    queued = client.post(
        f"/api/v1/authoring/datasets/{dataset_id}/generation-jobs",
        json={"target_ids": [target["target_id"]]},
    )

    assert queued.status_code == 202
    job_id = queued.json()["job_id"]
    jobs = client.get(f"/api/v1/authoring/datasets/{dataset_id}/generation-jobs")
    assert jobs.status_code == 200
    assert jobs.json()[0]["job_id"] == job_id
    assert jobs.json()[0]["state"] == GenerationJobStatus.COMPLETED


def test_authoring_target_preview_exposes_frozen_source_without_internal_ids(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    client = TestClient(create_app(service, start_supervisor=False))
    uploaded = client.post("/api/v1/authoring/datasets", content=mini_docx(), headers={"x-rag-eval-filename": "private.docx"})
    dataset_id = uploaded.json()["authoring_dataset_id"]
    assert client.post(f"/api/v1/authoring/datasets/{dataset_id}/analyze").status_code == 200
    targets = client.post(f"/api/v1/authoring/datasets/{dataset_id}/targets/discover", json={"provider": "rule"})
    target = next(item for item in targets.json() if item["capability"] == "table_lookup" and not item["flags"])

    preview = client.get(f"/api/v1/authoring/datasets/{dataset_id}/targets/{target['target_id']}/preview")

    assert preview.status_code == 200
    assert preview.json()["target_id"] == target["target_id"]
    source = preview.json()["source"]
    value = next(item for item in source if item["object_type"] == "cell")
    assert value["object_type"] == "cell"
    assert value["text"]
    assert value["table"]["row"] is not None
    assert value["table"]["column"] is not None
    assert "object_id" not in value
    assert all("object_id" not in item for item in preview.json()["context"])
