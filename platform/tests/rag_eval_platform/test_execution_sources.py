from __future__ import annotations

import hashlib
from pathlib import Path

from rag_eval.contracts.dataset import DatasetBundleManifest
from rag_eval.datasets.bundle import DatasetBundle
from rag_eval.execution import stage_original_document


def test_original_document_staging_pins_canonical_catalog(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    document_path = bundle_root / "documents" / "document.docx"
    canonical_path = bundle_root / "canonical" / "evidence.jsonl"
    document_path.parent.mkdir(parents=True)
    canonical_path.parent.mkdir(parents=True)
    document_path.write_bytes(b"PK\x03\x04native-docx-fixture")
    canonical_path.write_text(
        '{"document_id":"doc-1","object_id":"doc-1:block:00001"}\n',
        encoding="utf-8",
    )
    bundle = DatasetBundle(
        root=bundle_root,
        bundle_id="bundle-1",
        manifest=DatasetBundleManifest.model_validate(
            {
                "schema_version": 2,
                "name": "canonical-provenance-fixture",
                "version": "1",
                "created_at": "2026-08-28T00:00:00Z",
                "documents": [
                    {
                        "document_id": "doc-1",
                        "path": "documents/document.docx",
                        "canonical_path": "canonical/evidence.jsonl",
                        "sha256": hashlib.sha256(
                            document_path.read_bytes()
                        ).hexdigest(),
                        "mime_type": (
                            "application/vnd.openxmlformats-officedocument."
                            "wordprocessingml.document"
                        ),
                    }
                ],
            }
        ),
        questions=(),
        gold_answers={},
        gold_evidence_sets={},
    )

    document = stage_original_document(bundle, tmp_path / "run" / "source")

    staged_name = document.canonical_catalog_path
    assert "/" not in staged_name
    assert (
        tmp_path / "run" / "source" / staged_name
    ).read_bytes() == canonical_path.read_bytes()
    assert (
        document.canonical_catalog_sha256
        == hashlib.sha256(canonical_path.read_bytes()).hexdigest()
    )
