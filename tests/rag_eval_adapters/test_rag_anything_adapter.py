from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
import rag_eval_rag_anything_adapter.adapter as adapter_module
from rag_eval.contracts.adapter import DocumentInput, PrepareContext, RAGQuery
from rag_eval_rag_anything_adapter.adapter import (
    CAPABILITIES,
    INGESTION_LIVENESS_FILE,
    IngestionLiveness,
    OfficialRAGAnythingRuntime,
    RAGAnythingAdapter,
    exact_ollama_model_digest,
    force_run_scoped_environment,
    model_artifacts,
    normalize_ollama_digest,
    parse_cpu_time,
    resolve_config,
    verified_source_path,
)


def test_ollama_bare_digest_is_normalized_for_formal_model_lock() -> None:
    bare = "7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab"
    artifacts = model_artifacts(
        resolve_config({}).model,
        {"llm": bare, "embedding": bare},
    )

    assert normalize_ollama_digest(bare) == f"sha256:{bare}"
    assert artifacts["llm"]["resolved_digest"] == f"sha256:{bare}"
    assert artifacts["embedding"]["verified"] is True


def test_ollama_resolver_requires_an_exact_requested_tag() -> None:
    rows = [
        {"name": "qwen3:8b", "digest": "eight"},
        {"name": "qwen3:4b-instruct", "digest": "four"},
    ]

    assert exact_ollama_model_digest(rows, "qwen3:4b-instruct") == "four"
    assert exact_ollama_model_digest(rows, "qwen3") is None


class FakeRuntime:
    system_version = "1.3.1"
    core_version = "1.4.9"

    def __init__(self) -> None:
        self.model_digests = {"llm": "sha256:model"}
        self.prompt_digests = {"raganything_prompt_sources": "sha256:prompt"}
        self.text_documents: list[tuple[str, str, str]] = []
        self.binary_documents: list[tuple[Path, str, str]] = []
        self.queries: list[dict] = []
        self.closed = 0

    async def insert_text(
        self, content: str, *, document_id: str, file_name: str
    ) -> None:
        self.text_documents.append((content, document_id, file_name))

    async def process_document(
        self, path: Path, *, document_id: str, file_name: str, progress=None
    ) -> None:
        if progress is not None:
            progress("parsing", {"event": "parse_start"})
            progress("indexing", {"event": "parse_complete", "content_blocks": 1})
        self.binary_documents.append((path, document_id, file_name))

    async def query(
        self, question: str, *, mode: str, generate_answer: bool, options: dict
    ) -> str | None:
        self.queries.append(
            {
                "question": question,
                "mode": mode,
                "generate_answer": generate_answer,
                "options": options,
            }
        )
        return "42 ms" if generate_answer else None

    async def close(self) -> None:
        self.closed += 1


def context(tmp_path: Path) -> PrepareContext:
    source = tmp_path / "source"
    source.mkdir()
    return PrepareContext(
        run_id="run-1",
        work_dir=str(tmp_path / "work"),
        source_dir=str(source),
        platform_version="0.1.0",
    )


async def prepare_with_fake(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[RAGAnythingAdapter, FakeRuntime, PrepareContext]:
    runtime = FakeRuntime()

    async def create(_config, _work_dir, _run_id):
        return runtime

    monkeypatch.setattr(OfficialRAGAnythingRuntime, "create", create)
    adapter = RAGAnythingAdapter()
    prepare_context = context(tmp_path)
    prepared = await adapter.prepare(prepare_context, {})
    assert prepared.system_version == "1.3.1"
    assert prepared.effective_config["runtime"]["lightrag_version"] == "1.4.9"
    return adapter, runtime, prepare_context


def test_capabilities_are_honest_about_public_api_observability() -> None:
    assert CAPABILITIES.answer
    assert CAPABILITIES.latency_breakdown
    assert not CAPABILITIES.raw_retrieval
    assert not CAPABILITIES.ranked_retrieval
    assert not CAPABILITIES.final_context
    assert not CAPABILITIES.object_provenance


def test_config_is_strict_and_model_identity_is_explicit() -> None:
    config = resolve_config({})
    assert config.model.llm_model == "qwen3:4b-instruct"
    assert config.model.embedding_model == "bge-m3:latest"
    assert config.query_mode == "mix"
    assert config.native_liveness.parse_timeout_seconds == 1200.0
    with pytest.raises(ValueError, match="chunk overlap"):
        resolve_config(
            {
                "chunking": {
                    "chunk_token_size": 10,
                    "chunk_overlap_token_size": 10,
                }
            }
        )


def test_worker_uses_provider_resolved_ollama_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://host.docker.internal:11434")
    assert resolve_config({}).model.host == "http://host.docker.internal:11434"


def test_rag_anything_clears_lightrag_experiment_environment(tmp_path: Path) -> None:
    keys = (
        "LIGHTRAG_EXACT_ID_TYPES", "LIGHTRAG_RANKING_STRATEGY", "LIGHTRAG_TABLE_VIEW",
        "LIGHTRAG_TABLE_PRECEDING_CONTEXT", "LIGHTRAG_TABLE_STRUCTURED_ENVELOPE",
        "LIGHTRAG_TABLE_ROW_VIEW", "ENTITY_EXTRACTION_INSTRUCTION_PROFILE",
        "RERANK_MODEL", "RERANK_BINDING", "RERANK_BY_DEFAULT", "ENABLE_LLM_CACHE",
        "ENABLE_LLM_CACHE_FOR_EXTRACT", "WORKING_DIR", "OUTPUT_DIR",
        "LIGHTRAG_KV_STORAGE", "LIGHTRAG_DOC_STATUS_STORAGE", "LIGHTRAG_GRAPH_STORAGE",
        "LIGHTRAG_VECTOR_STORAGE",
    )
    original = {key: os.environ.get(key) for key in keys}
    try:
        os.environ.update(
            {
                "LIGHTRAG_EXACT_ID_TYPES": "FACT,TBL",
                "LIGHTRAG_RANKING_STRATEGY": "structured",
                "LIGHTRAG_TABLE_VIEW": "1",
            }
        )
        force_run_scoped_environment(tmp_path)
        assert "LIGHTRAG_EXACT_ID_TYPES" not in os.environ
        assert "LIGHTRAG_RANKING_STRATEGY" not in os.environ
        assert "LIGHTRAG_TABLE_VIEW" not in os.environ
        assert os.environ["ENABLE_LLM_CACHE"] == "0"
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.mark.asyncio
async def test_text_and_binary_ingestion_use_source_only_sandbox(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter, runtime, prepare_context = await prepare_with_fake(monkeypatch, tmp_path)
    source = Path(prepare_context.source_dir)
    text_path = source / "source-00000.txt"
    text_path.write_text("The controlled latency is 42 ms.", encoding="utf-8")
    pdf_path = source / "source-00001.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 controlled")
    documents = [
        DocumentInput(
            document_id="doc-text",
            content=text_path.read_text(),
            source_path=text_path.name,
            sha256=hashlib.sha256(text_path.read_bytes()).hexdigest(),
            metadata={"original_name": "facts.txt"},
        ),
        DocumentInput(
            document_id="doc-pdf",
            source_path=pdf_path.name,
            sha256=hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            mime_type="application/pdf",
            metadata={"original_name": "report.pdf"},
        ),
    ]

    ingestion = await adapter.ingest(documents)

    assert ingestion.ingested_documents == 2
    assert len(ingestion.index_fingerprint or "") == 64
    assert runtime.text_documents == [
        ("The controlled latency is 42 ms.", "doc-text", "facts.txt")
    ]
    assert runtime.binary_documents[0][1:] == ("doc-pdf", "report.pdf")
    status = adapter._liveness.snapshot()
    assert status["stage"] == "completed"
    assert status["details"]["ingested_documents"] == 2
    assert (Path(prepare_context.work_dir) / INGESTION_LIVENESS_FILE).is_file()
    await adapter.close()


def test_native_liveness_distinguishes_stages_and_stall(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clock = [10.0]
    monkeypatch.setattr(adapter_module, "monotonic", lambda: clock[0])
    liveness = IngestionLiveness(
        tmp_path / INGESTION_LIVENESS_FILE, stall_timeout_seconds=5.0
    )

    liveness.transition("parsing", document_id="synthetic-document")
    liveness.observe_activity((0, 0, 1, 0.1), details={"child_processes": 1})
    assert liveness.snapshot()["stage"] == "parsing"

    clock[0] += 6.0
    liveness.observe_activity((0, 0, 1, 0.1), details={"child_processes": 1})
    assert liveness.snapshot()["stage"] == "stalled"
    assert liveness.snapshot()["active_stage"] == "parsing"

    liveness.transition("indexing", details={"event": "parse_complete"})
    assert liveness.snapshot()["stage"] == "indexing"
    liveness.transition("cancelled", details={"termination_confirmed": True})
    assert liveness.snapshot()["stage"] == "cancelled"
    assert liveness.snapshot()["terminal"] is True


def test_ps_cpu_time_parser_supports_mineru_process_formats() -> None:
    assert parse_cpu_time("01:02") == 62.0
    assert parse_cpu_time("01:02:03") == 3723.0
    assert parse_cpu_time("2-01:02:03") == 176523.0


@pytest.mark.asyncio
async def test_query_returns_none_for_unobservable_stages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter, runtime, _prepare_context = await prepare_with_fake(monkeypatch, tmp_path)

    result = await adapter.query(
        RAGQuery(
            case_id="case-1",
            question="What is the latency?",
            retrieval_candidate_k=7,
            final_context_k=3,
            max_context_tokens=900,
        )
    )

    assert result.answer == "42 ms"
    assert result.raw_retrieval is None
    assert result.ranked_retrieval is None
    assert result.final_context is None
    assert runtime.queries[0]["options"]["top_k"] == 7
    assert runtime.queries[0]["options"]["chunk_top_k"] == 3
    assert runtime.queries[0]["options"]["max_total_tokens"] == 900
    await adapter.close()
    await adapter.close()
    assert runtime.closed == 1


def test_source_path_cannot_escape_sandbox(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"outside")
    document = DocumentInput(
        document_id="doc",
        content="inline",
        source_path="inside.txt",
    )
    with pytest.raises(ValueError, match="escapes or is absent"):
        verified_source_path(source, document)
