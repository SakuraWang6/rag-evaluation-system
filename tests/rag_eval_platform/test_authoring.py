from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_eval.api import create_app
from rag_eval.authoring.models import AuthoringState
from rag_eval.authoring.service import AuthoringService
from rag_eval.authoring.storage import AuthoringStorageError
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
