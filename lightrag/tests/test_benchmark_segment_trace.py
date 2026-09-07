"""vNext benchmark leaf-to-native mapping regressions for LightRAG."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from rag_eval.contracts.adapter import DocumentInput
from rag_eval_lightrag_adapter.adapter import LightRAGAdapter, resolve_config


class _AliveServer:
    def poll(self) -> None:
        return None


def _document() -> DocumentInput:
    contract_digest = "a" * 64
    segment_id = "segment-vnext-1"
    content = f"[[RAG_BENCHMARK_SEGMENT id={segment_id}]]\n可靠的证据。"
    return DocumentInput(
        document_id=segment_id,
        content=content,
        source_path="input.txt",
        sha256=hashlib.sha256(content.encode()).hexdigest(),
        metadata={
            "primary_evaluation_corpus": "benchmark_segments",
            "benchmark_contract_schema_version": "rag-benchmark-contract/1",
            "benchmark_contract_digest": contract_digest,
            "benchmark_segment_id": segment_id,
            "benchmark_segment_content_sha256": hashlib.sha256("可靠的证据。".encode()).hexdigest(),
            "benchmark_segment_rendered_sha256": hashlib.sha256(content.encode()).hexdigest(),
        },
    )


def _adapter(tmp_path: Path) -> LightRAGAdapter:
    adapter = LightRAGAdapter()
    adapter._config = resolve_config({"evaluation_corpus": "benchmark_segments"})
    adapter._server = _AliveServer()  # type: ignore[assignment]
    adapter._work_dir = tmp_path / "work"
    (adapter._work_dir / "storage").mkdir(parents=True)
    return adapter


def _write_native_store(adapter: LightRAGAdapter, content: str, *, extra: bool = False) -> None:
    payload: dict[str, object] = {
        "native-1": {
            "file_path": "input.txt",
            "content": content,
            "source_span": {"start": 0, "end": len(content)},
        }
    }
    if extra:
        payload["native-2"] = dict(payload["native-1"])  # type: ignore[arg-type]
    (adapter._work_dir / "storage" / "kv_store_text_chunks.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def test_benchmark_leaf_mapping_and_trace_are_exact(tmp_path: Path) -> None:
    document = _document()
    adapter = _adapter(tmp_path)
    inputs = adapter._load_benchmark_segment_contract([document], adapter._config)
    assert inputs is not None
    adapter._source_by_file = {"input.txt": document.document_id}
    _write_native_store(adapter, document.content or "")

    mapping = adapter._build_benchmark_segment_mapping(inputs)
    adapter._benchmark_segment_inputs = inputs
    adapter._benchmark_runtime_by_chunk = mapping["runtime_chunks"]
    traces = adapter._benchmark_segment_traces(
        {
            "raw_retrieval": [{"native_id": "native-1", "file_path": "input.txt", "content": document.content}],
            "ranked_retrieval": [{"native_id": "native-1", "file_path": "input.txt", "content": document.content}],
            "final_context": [{"native_id": "native-1", "file_path": "input.txt", "content": document.content}],
        }
    )

    assert traces.raw.status.value == "observed"
    assert traces.raw.items[0].source_segment_ids == (document.document_id,)
    assert traces.raw.mapping_manifest_digest == "a" * 64


def test_benchmark_leaf_mapping_rejects_native_split(tmp_path: Path) -> None:
    document = _document()
    adapter = _adapter(tmp_path)
    inputs = adapter._load_benchmark_segment_contract([document], adapter._config)
    assert inputs is not None
    adapter._source_by_file = {"input.txt": document.document_id}
    _write_native_store(adapter, document.content or "", extra=True)

    with pytest.raises(RuntimeError, match="exactly one native chunk"):
        adapter._build_benchmark_segment_mapping(inputs)


def test_benchmark_uploads_are_admitted_as_a_bounded_batch(tmp_path: Path) -> None:
    """Transport batching must not turn independent leaves into one input."""

    first = _document()
    second_content = "[[RAG_BENCHMARK_SEGMENT id=segment-vnext-2]]\n另一条可靠的证据。"
    second = first.model_copy(
        update={
            "document_id": "segment-vnext-2",
            "content": second_content,
            "sha256": hashlib.sha256(second_content.encode()).hexdigest(),
            "metadata": {
                **first.metadata,
                "benchmark_segment_id": "segment-vnext-2",
                "benchmark_segment_content_sha256": hashlib.sha256(
                    "另一条可靠的证据。".encode()
                ).hexdigest(),
                "benchmark_segment_rendered_sha256": hashlib.sha256(
                    second_content.encode()
                ).hexdigest(),
            },
        }
    )
    adapter = _adapter(tmp_path)
    adapter._config = resolve_config(
        {"evaluation_corpus": "benchmark_segments", "benchmark_upload_batch_size": 2}
    )
    posted: list[str] = []

    async def post(filename: str, _content: bytes, _mime_type: str) -> dict[str, str]:
        posted.append(filename)
        return {"track_id": filename}

    async def wait(track_id: str) -> None:
        # Both independent uploads must be admitted before either status is
        # awaited, allowing LightRAG to drain the bounded mailbox as a group.
        assert len(posted) == 2
        assert track_id in posted

    adapter._post_document = post  # type: ignore[method-assign]
    adapter._wait_for_ingestion = wait  # type: ignore[method-assign]
    staged = [
        (first, first.content, "first.txt", (first.content or "").encode()),
        (second, second.content, "second.txt", (second.content or "").encode()),
    ]

    assert asyncio.run(adapter._ingest_benchmark_upload_batches(staged)) == []
    assert posted == ["first.txt", "second.txt"]
