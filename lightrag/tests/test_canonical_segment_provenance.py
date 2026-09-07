"""Strict primary-corpus chunk-to-segment mapping regressions."""

from __future__ import annotations

import hashlib

import pytest

from rag_eval.datasets.canonical_segments import (
    CanonicalSegment,
    CanonicalSegmentBatch,
    CanonicalSegmentEdge,
    CanonicalSegmentManifest,
    CanonicalSegmentObject,
    CanonicalSegmentSource,
    render_batch,
)
from rag_eval_lightrag_adapter.canonical_provenance import (
    build_canonical_segment_provenance_manifest,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _manifest() -> CanonicalSegmentManifest:
    source = CanonicalSegmentSource(
        document_id="doc-1",
        source_sha256="a" * 64,
        canonical_sidecar_sha256="b" * 64,
    )
    object_value = CanonicalSegmentObject(
        object_id="doc-1:paragraph:1",
        document_id="doc-1",
        object_type="paragraph",
        locator={
            "type": "object",
            "object_type": "paragraph",
            "object_id": "doc-1:paragraph:1",
        },
        expected_extent={"status": "mapped", "object_id": "doc-1:paragraph:1"},
        mapping_status="mapped",
        source_sha256="a" * 64,
        witness_sha256=_sha("可靠的规范化段落。"),
    )
    segment = CanonicalSegment(
        segment_id="segment-1",
        document_id="doc-1",
        root_object_id="doc-1:paragraph:1",
        ordinal=0,
        content="【段落】\n可靠的规范化段落。",
        content_sha256=_sha("【段落】\n可靠的规范化段落。"),
        edges=(CanonicalSegmentEdge(object_id="doc-1:paragraph:1", coverage="full"),),
    )
    content = render_batch([segment])
    batch = CanonicalSegmentBatch(
        batch_id="batch-1",
        input_document_id="canonical-batch-1",
        document_id="doc-1",
        ordinal=0,
        segment_ids=(segment.segment_id,),
        content=content,
        content_sha256=_sha(content),
    )
    return CanonicalSegmentManifest.build(
        sources=[source], object_catalog=[object_value], segments=[segment], batches=[batch]
    )


def _stored(manifest: CanonicalSegmentManifest) -> dict[str, dict[str, object]]:
    batch = manifest.batches[0]
    return {
        "runtime-1": {
            "file_path": "source-00000.txt",
            "content": batch.content,
            "source_span": {"start": 0, "end": len(batch.content)},
            "full_doc_id": "lightrag-doc-1",
        }
    }


def test_primary_chunk_mapping_is_exact_and_contains_no_guesswork() -> None:
    manifest = _manifest()
    payload = build_canonical_segment_provenance_manifest(
        manifest=manifest,
        document_by_file={"source-00000.txt": "canonical-batch-1"},
        stored_chunks=_stored(manifest),
    )

    chunk = payload["runtime_chunks"]["runtime-1"]
    assert payload["primary_corpus"] == {
        "mode": "canonical-segments/v1",
        "manifest_digest": manifest.manifest_digest,
        "acceptance": "one_persisted_chunk_per_declared_batch",
    }
    assert payload["runtime_chunk_to_segment_ids"] == {"runtime-1": ["segment-1"]}
    assert payload["segment_to_runtime_chunks"] == {"segment-1": ["runtime-1"]}
    assert chunk["content_sha256"] == manifest.batches[0].content_sha256
    assert chunk["canonical_objects"][0]["object_id"] == "doc-1:paragraph:1"


def test_primary_chunk_mapping_rejects_a_split_batch() -> None:
    manifest = _manifest()
    chunks = _stored(manifest)
    chunks["runtime-2"] = dict(chunks["runtime-1"])
    with pytest.raises(ValueError, match="exactly one LightRAG chunk"):
        build_canonical_segment_provenance_manifest(
            manifest=manifest,
            document_by_file={"source-00000.txt": "canonical-batch-1"},
            stored_chunks=chunks,
        )


def test_primary_chunk_mapping_rejects_changed_batch_bytes() -> None:
    manifest = _manifest()
    chunks = _stored(manifest)
    chunks["runtime-1"]["content"] = "LightRAG changed the input"
    chunks["runtime-1"]["source_span"] = {"start": 0, "end": 26}
    with pytest.raises(ValueError, match="does not preserve canonical batch"):
        build_canonical_segment_provenance_manifest(
            manifest=manifest,
            document_by_file={"source-00000.txt": "canonical-batch-1"},
            stored_chunks=chunks,
        )
