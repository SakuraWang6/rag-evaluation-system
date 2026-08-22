"""Run-scoped RAG-Anything adapter behind Wire Protocol 1.0."""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
from functools import partial
from pathlib import Path
from time import monotonic
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field
from rag_eval.contracts.adapter import (
    AdapterCapabilities,
    DocumentInput,
    HealthReport,
    IngestionResult,
    PrepareContext,
    PreparedSystem,
    RAGQuery,
    RAGResult,
    ResetResult,
)
from rag_eval.contracts.wire import HandshakeResponse
from rag_eval.worker.app import WorkerDefinition

ADAPTER_VERSION = "0.1.0"
SUPPORTED_RAG_ANYTHING_MAJOR_MINOR = "1.3"
CAPABILITIES = AdapterCapabilities(
    answer=True,
    raw_retrieval=False,
    ranked_retrieval=False,
    final_context=False,
    object_provenance=False,
    prompt_trace=False,
    rerank_trace=False,
    latency_breakdown=True,
    token_usage=False,
    reset=False,
)


class OllamaModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding: Literal["ollama"] = "ollama"
    host: str = "http://127.0.0.1:11434"
    llm_model: str = Field(default="qwen3:4b-instruct", min_length=1)
    embedding_model: str = Field(default="bge-m3:latest", min_length=1)
    embedding_dim: int = Field(default=1024, ge=1)
    embedding_max_tokens: int = Field(default=8192, ge=1)
    request_timeout_seconds: float = Field(default=180.0, gt=0)


class ChunkingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_token_size: int = Field(default=1200, ge=1)
    chunk_overlap_token_size: int = Field(default=100, ge=0)


class RAGAnythingAdapterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parser: Literal["mineru", "docling", "paddleocr"] = "mineru"
    parse_method: Literal["auto", "ocr", "txt"] = "auto"
    query_mode: Literal["local", "global", "hybrid", "naive", "mix"] = "mix"
    enable_image_processing: bool = True
    enable_table_processing: bool = True
    enable_equation_processing: bool = True
    enable_vlm_query: bool = False
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    model: OllamaModelConfig = Field(default_factory=OllamaModelConfig)
    top_k: int = Field(default=60, ge=1)
    chunk_top_k: int = Field(default=20, ge=1)
    max_context_tokens: int = Field(default=12000, ge=1)

    def validate_invariants(self) -> None:
        if self.chunking.chunk_overlap_token_size >= self.chunking.chunk_token_size:
            raise ValueError("chunk overlap must be smaller than chunk token size")


def resolve_config(raw: dict[str, Any]) -> RAGAnythingAdapterConfig:
    config = RAGAnythingAdapterConfig.model_validate(raw)
    config.validate_invariants()
    return config


class Runtime(Protocol):
    system_version: str
    core_version: str

    async def insert_text(
        self, content: str, *, document_id: str, file_name: str
    ) -> None: ...

    async def process_document(
        self, path: Path, *, document_id: str, file_name: str
    ) -> None: ...

    async def query(
        self, question: str, *, mode: str, generate_answer: bool, options: dict[str, Any]
    ) -> str | None: ...

    async def close(self) -> None: ...


class OfficialRAGAnythingRuntime:
    """Thin wrapper over RAG-Anything's documented public Python API."""

    def __init__(
        self,
        rag: Any,
        *,
        system_version: str,
        core_version: str,
        output_dir: Path,
    ) -> None:
        self.rag = rag
        self.system_version = system_version
        self.core_version = core_version
        self.output_dir = output_dir

    @classmethod
    async def create(
        cls, config: RAGAnythingAdapterConfig, work_dir: Path, run_id: str
    ) -> OfficialRAGAnythingRuntime:
        force_run_scoped_environment(work_dir)
        from raganything import RAGAnything, RAGAnythingConfig

        from lightrag.llm.ollama import ollama_embed, ollama_model_complete
        from lightrag.utils import EmbeddingFunc

        installed_version = distribution_version("raganything")
        if not installed_version.startswith(f"{SUPPORTED_RAG_ANYTHING_MAJOR_MINOR}."):
            raise RuntimeError(
                "unsupported RAG-Anything version "
                f"{installed_version!r}; expected {SUPPORTED_RAG_ANYTHING_MAJOR_MINOR}.x"
            )
        storage_dir = work_dir / "storage"
        output_dir = work_dir / "parser-output"
        storage_dir.mkdir()
        output_dir.mkdir()
        rag_config = RAGAnythingConfig(
            working_dir=str(storage_dir),
            parser_output_dir=str(output_dir),
            parser=config.parser,
            parse_method=config.parse_method,
            display_content_stats=False,
            enable_image_processing=config.enable_image_processing,
            enable_table_processing=config.enable_table_processing,
            enable_equation_processing=config.enable_equation_processing,
            use_full_path=False,
        )
        embedding = EmbeddingFunc(
            embedding_dim=config.model.embedding_dim,
            max_token_size=config.model.embedding_max_tokens,
            model_name=config.model.embedding_model,
            supports_asymmetric=True,
            func=partial(
                ollama_embed.func,
                embed_model=config.model.embedding_model,
                host=config.model.host,
                timeout=config.model.request_timeout_seconds,
            ),
        )
        rag = RAGAnything(
            config=rag_config,
            llm_model_func=ollama_model_complete,
            vision_model_func=None,
            embedding_func=embedding,
            lightrag_kwargs={
                "workspace": f"eval_{run_id}",
                "kv_storage": "JsonKVStorage",
                "doc_status_storage": "JsonDocStatusStorage",
                "graph_storage": "NetworkXStorage",
                "vector_storage": "NanoVectorDBStorage",
                "chunk_token_size": config.chunking.chunk_token_size,
                "chunk_overlap_token_size": config.chunking.chunk_overlap_token_size,
                "llm_model_name": config.model.llm_model,
                "llm_model_kwargs": {
                    "host": config.model.host,
                    "timeout": config.model.request_timeout_seconds,
                },
                "enable_llm_cache": False,
            },
        )
        return cls(
            rag,
            system_version=installed_version,
            core_version=distribution_version("lightrag-hku"),
            output_dir=output_dir,
        )

    async def insert_text(
        self, content: str, *, document_id: str, file_name: str
    ) -> None:
        await self.rag.insert_content_list(
            content_list=[{"type": "text", "text": content, "page_idx": 0}],
            file_path=file_name,
            doc_id=document_id,
            display_stats=False,
        )

    async def process_document(
        self, path: Path, *, document_id: str, file_name: str
    ) -> None:
        await self.rag.process_document_complete(
            file_path=str(path),
            output_dir=str(self.output_dir),
            doc_id=document_id,
            file_name=file_name,
            display_stats=False,
        )

    async def query(
        self, question: str, *, mode: str, generate_answer: bool, options: dict[str, Any]
    ) -> str | None:
        query_options = dict(options)
        query_options["vlm_enhanced"] = bool(query_options.pop("vlm_enhanced", False))
        if not generate_answer:
            query_options["only_need_context"] = True
        result = await self.rag.aquery(question, mode=mode, **query_options)
        if generate_answer:
            if not isinstance(result, str):
                raise RuntimeError("RAG-Anything returned a non-string answer")
            return result
        return None

    async def close(self) -> None:
        await self.rag.finalize_storages()


class RAGAnythingAdapter:
    def __init__(self) -> None:
        self._context: PrepareContext | None = None
        self._config: RAGAnythingAdapterConfig | None = None
        self._runtime: Runtime | None = None
        self._closed = False
        self._index_fingerprint: str | None = None

    async def prepare(
        self, context: PrepareContext, config: dict[str, Any]
    ) -> PreparedSystem:
        if self._closed:
            raise RuntimeError("adapter is closed")
        if self._runtime is not None:
            raise RuntimeError("adapter is already prepared")
        effective = resolve_config(config)
        work_dir = Path(context.work_dir).resolve()
        if work_dir.exists() and any(work_dir.iterdir()):
            raise RuntimeError(
                "run work directory is not empty; refusing stale index reuse"
            )
        work_dir.mkdir(parents=True, exist_ok=True)
        source_dir = Path(context.source_dir).resolve()
        if not source_dir.is_dir():
            raise RuntimeError("source-only sandbox does not exist")
        self._context = context
        self._config = effective
        self._runtime = await OfficialRAGAnythingRuntime.create(
            effective, work_dir, context.run_id
        )
        return PreparedSystem(
            effective_config={
                **effective.model_dump(mode="json"),
                "runtime": {
                    "raganything_version": self._runtime.system_version,
                    "lightrag_version": self._runtime.core_version,
                    "isolation": "run_scoped_worker_process",
                },
            },
            capabilities=CAPABILITIES,
            system_version=self._runtime.system_version,
        )

    async def health(self) -> HealthReport:
        if self._closed:
            return HealthReport(status="closed", ready=False)
        return HealthReport(
            status="ready" if self._runtime is not None else "initialized",
            ready=True,
            details={"prepared": self._runtime is not None},
        )

    async def ingest(self, documents: list[DocumentInput]) -> IngestionResult:
        runtime, config, context = self._require_prepared()
        digest = hashlib.sha256()
        digest.update(
            ingestion_identity(
                config, runtime.system_version, runtime.core_version
            ).encode()
        )
        source_dir = Path(context.source_dir).resolve()
        for document in documents:
            path = verified_source_path(source_dir, document)
            digest.update(document.document_id.encode())
            digest.update(b"\0")
            digest.update(document_digest(document, path).encode())
            digest.update(b"\0")
            file_name = str(document.metadata.get("original_name") or path.name)
            if document.content is not None:
                await runtime.insert_text(
                    document.content,
                    document_id=document.document_id,
                    file_name=file_name,
                )
            else:
                await runtime.process_document(
                    path,
                    document_id=document.document_id,
                    file_name=file_name,
                )
        self._index_fingerprint = digest.hexdigest()
        return IngestionResult(
            ingested_documents=len(documents),
            index_fingerprint=self._index_fingerprint,
            details={"failed_documents": 0},
        )

    async def query(self, request: RAGQuery) -> RAGResult:
        runtime, config, _context = self._require_prepared()
        reserved = {"mode", "only_need_context", "only_need_prompt"}
        invalid = reserved.intersection(request.generation_options)
        if invalid:
            raise ValueError(f"reserved generation options: {sorted(invalid)}")
        options = dict(request.generation_options)
        options.update(
            {
                "top_k": request.retrieval_candidate_k or config.top_k,
                "chunk_top_k": request.final_context_k or config.chunk_top_k,
                "max_total_tokens": request.max_context_tokens
                or config.max_context_tokens,
                "vlm_enhanced": config.enable_vlm_query,
            }
        )
        started = monotonic()
        answer = await runtime.query(
            request.question,
            mode=config.query_mode,
            generate_answer=request.generate_answer,
            options=options,
        )
        return RAGResult(
            answer=answer,
            raw_retrieval=None,
            ranked_retrieval=None,
            final_context=None,
            latency={"query_seconds": monotonic() - started},
            native_metadata={
                "query_mode": config.query_mode,
                "index_fingerprint": self._index_fingerprint,
                "retrieval_observability": "unavailable_in_public_api",
            },
        )

    async def reset(self) -> ResetResult:
        return ResetResult(
            supported=False,
            reset=False,
            details={"reason": "adapter instances are run-scoped"},
        )

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        runtime, self._runtime = self._runtime, None
        if runtime is not None:
            await runtime.close()

    def _require_prepared(
        self,
    ) -> tuple[Runtime, RAGAnythingAdapterConfig, PrepareContext]:
        if self._closed:
            raise RuntimeError("adapter is closed")
        if self._runtime is None or self._config is None or self._context is None:
            raise RuntimeError("adapter is not prepared")
        return self._runtime, self._config, self._context


def verified_source_path(source_dir: Path, document: DocumentInput) -> Path:
    if document.source_path is None:
        raise ValueError("RAG-Anything requires a source-only sandbox path")
    path = (source_dir / document.source_path).resolve()
    if path.parent != source_dir or not path.is_file():
        raise ValueError("document source_path escapes or is absent from the sandbox")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if document.sha256 is not None and digest != document.sha256:
        raise ValueError(f"source checksum mismatch for {document.document_id}")
    return path


def document_digest(document: DocumentInput, path: Path) -> str:
    return document.sha256 or hashlib.sha256(path.read_bytes()).hexdigest()


def ingestion_identity(
    config: RAGAnythingAdapterConfig, version: str, core_version: str
) -> str:
    payload = {
        "system_version": version,
        "core_version": core_version,
        "parser": config.parser,
        "parse_method": config.parse_method,
        "multimodal": {
            "image": config.enable_image_processing,
            "table": config.enable_table_processing,
            "equation": config.enable_equation_processing,
        },
        "chunking": config.chunking.model_dump(mode="json"),
        "embedding_model": config.model.embedding_model,
        "embedding_dim": config.model.embedding_dim,
    }
    import json

    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def force_run_scoped_environment(work_dir: Path) -> None:
    os.environ.update(
        {
            "WORKING_DIR": str(work_dir / "storage"),
            "OUTPUT_DIR": str(work_dir / "parser-output"),
            "LIGHTRAG_KV_STORAGE": "JsonKVStorage",
            "LIGHTRAG_DOC_STATUS_STORAGE": "JsonDocStatusStorage",
            "LIGHTRAG_GRAPH_STORAGE": "NetworkXStorage",
            "LIGHTRAG_VECTOR_STORAGE": "NanoVectorDBStorage",
            "RERANK_BINDING": "null",
            "RERANK_BY_DEFAULT": "0",
        }
    )


def distribution_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError(f"required distribution is not installed: {name}") from exc


def create_worker_definition() -> WorkerDefinition:
    version = distribution_version("raganything")
    return WorkerDefinition(
        adapter=RAGAnythingAdapter(),
        handshake=HandshakeResponse(
            adapter_id="rag-anything",
            adapter_version=ADAPTER_VERSION,
            system_id="rag-anything",
            system_version=version,
            capabilities=CAPABILITIES,
        ),
    )
