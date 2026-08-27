from __future__ import annotations

import hashlib
from pathlib import Path

from rag_eval.contracts.dataset import DatasetBundleManifest
from rag_eval.datasets.bundle import DatasetBundle
from rag_eval.execution import source_only_documents


def test_source_only_documents_stages_canonical_provenance_sidecar(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "bundle"
    document_path = bundle_root / "documents" / "document.md"
    canonical_path = bundle_root / "canonical" / "evidence.jsonl"
    document_path.parent.mkdir(parents=True)
    canonical_path.parent.mkdir(parents=True)
    document_path.write_text("# Heading\n\nGrounded statement.\n", encoding="utf-8")
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
                        "path": "documents/document.md",
                        "canonical_path": "canonical/evidence.jsonl",
                        "sha256": hashlib.sha256(
                            document_path.read_bytes()
                        ).hexdigest(),
                        "mime_type": "text/markdown",
                    }
                ],
            }
        ),
        questions=(),
        gold_answers={},
        gold_evidence_sets={},
    )

    documents = source_only_documents(bundle, tmp_path / "run" / "source")

    assert len(documents) == 1
    metadata = documents[0].metadata
    staged_name = metadata["canonical_provenance_path"]
    assert isinstance(staged_name, str)
    assert "/" not in staged_name
    assert (
        tmp_path / "run" / "source" / staged_name
    ).read_bytes() == canonical_path.read_bytes()
    assert (
        metadata["canonical_provenance_sha256"]
        == hashlib.sha256(canonical_path.read_bytes()).hexdigest()
    )
