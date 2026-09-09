from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from rag_eval.contracts.native import (
    NativeQueryV2,
    OriginalDocumentV2,
    ResolvedAdapterConfigV2,
)
from rag_eval.runs.plans import digest_json


def stage_native_worker_input(
    root: Path,
    *,
    run_id: str,
    adapter_config: dict[str, object] | None = None,
) -> tuple[OriginalDocumentV2, ResolvedAdapterConfigV2]:
    source_dir = root / "source"
    work_dir = root / "work"
    source_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    docx_path = source_dir / "original.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>The controlled value is 42.</w:t></w:r></w:p></w:body>
</w:document>""",
        )
    catalog_path = source_dir / "canonical.jsonl"
    catalog_path.write_text("{}\n", encoding="utf-8")

    config = dict(adapter_config or {"final_context_k": 1})
    original = OriginalDocumentV2(
        document_id="doc-1",
        source_path=docx_path.name,
        source_sha256=hashlib.sha256(docx_path.read_bytes()).hexdigest(),
        original_name="original.docx",
        canonical_catalog_path=catalog_path.name,
        canonical_catalog_sha256=hashlib.sha256(
            catalog_path.read_bytes()
        ).hexdigest(),
    )
    resolved = ResolvedAdapterConfigV2(
        run_id=run_id,
        work_dir=str(work_dir),
        source_dir=str(source_dir),
        platform_version="0.1.0",
        seed=17,
        repetition=1,
        adapter_config=config,
        adapter_config_digest=digest_json(config),
    )
    return original, resolved


def native_query(*, case_id: str = "case-1") -> NativeQueryV2:
    return NativeQueryV2(
        case_id=case_id,
        question="What is the controlled value?",
        generate_answer=True,
        retrieval_candidate_k=5,
        final_context_k=1,
        max_context_tokens=512,
        generation_options={},
    )
