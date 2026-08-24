"""Run-scoped RAG-Anything adapter behind Wire Protocol 1.0."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import subprocess
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from time import monotonic
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx
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


class GenerationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature: float | None = Field(default=None, ge=0, le=2)
    seed: int | None = None
    user_prompt: str | None = None


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
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
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
    model_digests: dict[str, str]
    prompt_digests: dict[str, str]

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
        model_digests: dict[str, str],
        prompt_digests: dict[str, str],
        output_dir: Path,
    ) -> None:
        self.rag = rag
        self.system_version = system_version
        self.core_version = core_version
        self.model_digests = model_digests
        self.prompt_digests = prompt_digests
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
                    **{
                        key: value
                        for key, value in config.generation.model_dump(
                            exclude_none=True
                        ).items()
                        if key in {"temperature", "seed"}
                    },
                },
                "enable_llm_cache": False,
            },
        )
        return cls(
            rag,
            system_version=installed_version,
            core_version=distribution_version("lightrag-hku"),
            model_digests=await ollama_model_digests(config.model),
            prompt_digests={
                "raganything_prompt_sources": package_prompt_digest("raganything"),
                "lightrag_prompt_sources": package_prompt_digest("lightrag"),
            },
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
        self._work_dir: Path | None = None

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
        self._work_dir = work_dir
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
                "model_digests": self._runtime.model_digests,
                "model_artifacts": model_artifacts(
                    effective.model, self._runtime.model_digests
                ),
                "prompt_digests": self._runtime.prompt_digests,
                "cache_policy": {"answer": False, "query": False, "llm": False},
                "code_identity": code_identity(),
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
            details={
                "failed_documents": 0,
                "index_artifact_digest": directory_digest(
                    self._require_work_dir() / "storage"
                ),
            },
        )

    async def query(self, request: RAGQuery) -> RAGResult:
        runtime, config, _context = self._require_prepared()
        reserved = {"mode", "only_need_context", "only_need_prompt"}
        invalid = reserved.intersection(request.generation_options)
        if invalid:
            raise ValueError(f"reserved generation options: {sorted(invalid)}")
        options = generation_options(config, request.generation_options)
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
            latency={"native_query_latency": monotonic() - started},
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

    def _require_work_dir(self) -> Path:
        if self._work_dir is None:
            raise RuntimeError("adapter work directory is not initialized")
        return self._work_dir


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
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def force_run_scoped_environment(work_dir: Path) -> None:
    # The RAG-Anything process can import LightRAG.  Clear all experimental
    # LightRAG controls before setting the narrow run-scoped baseline so an
    # interactive shell cannot change this adapter's experiment semantics.
    for key in (
        "LIGHTRAG_EXACT_ID_TYPES",
        "LIGHTRAG_RANKING_STRATEGY",
        "LIGHTRAG_TABLE_PRECEDING_CONTEXT",
        "LIGHTRAG_TABLE_STRUCTURED_ENVELOPE",
        "LIGHTRAG_TABLE_VIEW",
        "LIGHTRAG_TABLE_ROW_VIEW",
        "ENTITY_EXTRACTION_INSTRUCTION_PROFILE",
        "RERANK_MODEL",
        "RERANK_BINDING",
        "RERANK_BY_DEFAULT",
        "ENABLE_LLM_CACHE",
        "ENABLE_LLM_CACHE_FOR_EXTRACT",
    ):
        os.environ.pop(key, None)
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
            "ENABLE_LLM_CACHE": "0",
            "ENABLE_LLM_CACHE_FOR_EXTRACT": "0",
        }
    )


def distribution_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError(f"required distribution is not installed: {name}") from exc


async def ollama_model_digests(config: OllamaModelConfig) -> dict[str, str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{config.host.rstrip('/')}/api/tags")
            response.raise_for_status()
            rows = response.json().get("models", [])
    except (httpx.HTTPError, AttributeError, ValueError):
        rows = []
    results: dict[str, str] = {}
    for role, model in (
        ("llm", config.llm_model),
        ("embedding", config.embedding_model),
    ):
        digest = None
        for item in rows:
            name = str(item.get("name") or item.get("model") or "")
            if name == model or name.split(":", 1)[0] == model.split(":", 1)[0]:
                digest = str(item.get("digest") or "") or None
                break
        results[role] = digest or identity_digest(config.binding, model)
    return results


def model_artifacts(
    config: OllamaModelConfig, digests: dict[str, str]
) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for role, requested in (("llm", config.llm_model), ("embedding", config.embedding_model)):
        digest = digests.get(role)
        verified = bool(digest and digest.startswith("sha256:") and len(digest) == 71)
        values[role] = {
            "display_name": requested.split(":", 1)[0],
            "requested_ref": requested,
            "resolved_digest": digest if verified else None,
            "revision": None,
            "resolver": config.binding,
            "resolved_at": datetime.now(UTC).isoformat(),
            "verified": verified,
        }
    return values


def generation_options(
    config: RAGAnythingAdapterConfig, requested: dict[str, Any]
) -> dict[str, Any]:
    options = dict(requested)
    for key in ("temperature", "seed"):
        configured = getattr(config.generation, key)
        if key in options and options[key] != configured:
            raise ValueError(f"{key} must be fixed during prepare")
        options.pop(key, None)
    if config.generation.user_prompt is not None:
        options.setdefault("user_prompt", config.generation.user_prompt)
    return options


def directory_digest(root: Path) -> str:
    digest = hashlib.sha256()
    if root.exists():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def code_identity() -> dict[str, dict[str, str | None]]:
    return {
        "adapter": source_identity("rag_eval_rag_anything_adapter"),
        "raganything": source_identity("raganything"),
        "lightrag": source_identity("lightrag"),
    }


def source_identity(package: str) -> dict[str, str | None]:
    spec = importlib.util.find_spec(package)
    source = Path(spec.origin).parent if spec and spec.origin else None
    root = find_git_root(source) if source else None
    return {
        "package_version": distribution_version_or_none(package),
        "git_commit": git_output(root, ["rev-parse", "HEAD"]) if root else None,
        "dirty_patch_digest": dirty_digest(root),
        "direct_url": direct_url(package),
    }


def find_git_root(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def git_output(root: Path, arguments: list[str]) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True, check=False
    )
    return (result.stdout.strip() or None) if result.returncode == 0 else None


def dirty_digest(root: Path | None) -> str | None:
    if root is None:
        return None
    status = git_output(root, ["status", "--porcelain=v1", "--untracked-files=all"])
    if not status:
        return None
    patch = git_output(root, ["diff", "--binary", "HEAD", "--"]) or ""
    return hashlib.sha256(f"{status}\0{patch}".encode()).hexdigest()


def direct_url(distribution: str) -> str | None:
    try:
        raw = importlib.metadata.distribution(distribution).read_text("direct_url.json")
    except importlib.metadata.PackageNotFoundError:
        return None
    if not raw:
        return None
    try:
        value = json.loads(raw).get("url")
        return safe_direct_url(value) if isinstance(value, str) else None
    except (TypeError, ValueError):
        return None


def distribution_version_or_none(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def safe_direct_url(value: str) -> str:
    parsed = urlsplit(value)
    if not parsed.scheme:
        return value
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit((parsed.scheme, hostname + port, parsed.path, "", ""))


def identity_digest(binding: str, model: str) -> str:
    return "identity-sha256:" + hashlib.sha256(
        f"{binding}\0{model}".encode()
    ).hexdigest()


def package_prompt_digest(package: str) -> str:
    spec = importlib.util.find_spec(package)
    if spec is None or spec.origin is None:
        return identity_digest("package", package)
    root = Path(spec.origin).parent
    files = sorted(
        path for path in root.rglob("*.py") if "prompt" in path.name.lower()
    )
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


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
