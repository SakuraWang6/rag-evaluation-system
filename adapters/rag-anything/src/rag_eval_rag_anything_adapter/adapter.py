"""Run-scoped RAG-Anything Adapter behind direct Worker Wire 2.0."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import subprocess
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from threading import RLock
from time import monotonic
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field
from rag_eval.adapters.native_observation import unavailable_native_result
from rag_eval.contracts.adapter import (
    AdapterCapabilities,
    DocumentInput,
    IngestionResult,
    PrepareContext,
    PreparedSystem,
    ResetResult,
)
from rag_eval.contracts.native import (
    IngestionReceiptV2,
    NativeHealthReportV2,
    NativeQueryV2,
    OriginalDocumentV2,
    PreparedSystemV2,
    ResolvedAdapterConfigV2,
)
from rag_eval.contracts.observation import AdapterRunResultV2, ObservationStatus
from rag_eval.contracts.wire import WorkerIdentityV2
from rag_eval.worker.app import WorkerDefinition

from rag_eval_rag_anything_adapter.native_observation import (
    NativeObservationSnapshot,
    RuntimeIngestionCapture,
    RuntimeQueryCapture,
    build_native_observation_snapshot,
    build_native_run_result_v2,
    build_prepared_identities,
)

ADAPTER_VERSION = "0.1.0"
SUPPORTED_RAG_ANYTHING_MAJOR_MINOR = "1.3"
INGESTION_LIVENESS_FILE = "ingestion-liveness.json"
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
    # Native retrieval facts remain explicit observations so an unsupported
    # stage cannot turn into an observed-empty result.
    segment_traces=True,
    strict_segment_ranking=False,
)


@dataclass(slots=True)
class _ActiveQueryCapture:
    query_results: list[Mapping[str, Any]] = field(default_factory=list)
    query_parameters: list[dict[str, Any]] = field(default_factory=list)
    candidate_calls: list[tuple[int, list[Mapping[str, Any]]]] = field(
        default_factory=list
    )
    errors: list[str] = field(default_factory=list)


class OllamaModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding: Literal["ollama"] = "ollama"
    # The logical endpoint is resolved by ExecutionProvider immediately
    # before Worker launch.  The resolved address is deliberately absent from
    # ExperimentSpec and is passed only through this short-lived environment.
    host: str = Field(default_factory=lambda: os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"))
    llm_model: str = Field(default="qwen3:4b-instruct", min_length=1)
    embedding_model: str = Field(default="bge-m3:latest", min_length=1)
    embedding_dim: int = Field(default=1024, ge=1)
    embedding_max_tokens: int = Field(default=8192, ge=1)
    llm_num_ctx: int = Field(default=32768, ge=1024)
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


class NativeLivenessConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parse_timeout_seconds: float = Field(default=1200.0, gt=0)
    stall_timeout_seconds: float = Field(default=120.0, gt=0)
    poll_interval_seconds: float = Field(default=2.0, gt=0)


class RAGAnythingAdapterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_corpus: Literal[
        "source_document", "canonical_segments", "benchmark_segments"
    ] = "source_document"
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
    native_liveness: NativeLivenessConfig = Field(default_factory=NativeLivenessConfig)
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
        self,
        path: Path,
        *,
        document_id: str,
        file_name: str,
        progress: Callable[[str, dict[str, Any]], None] | None = None,
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
        parse_timeout_seconds: float,
    ) -> None:
        self.rag = rag
        self.system_version = system_version
        self.core_version = core_version
        self.model_digests = model_digests
        self.prompt_digests = prompt_digests
        self.output_dir = output_dir
        self.parse_timeout_seconds = parse_timeout_seconds
        self._active_query_capture: ContextVar[_ActiveQueryCapture | None] = (
            ContextVar(
                f"rag_anything_query_capture_{id(self)}",
                default=None,
            )
        )
        self._hooked_core: Any | None = None
        self._hooked_vector_store: Any | None = None
        self._original_aquery_llm: Any | None = None
        self._original_vector_query: Any | None = None

    @classmethod
    async def create(
        cls, config: RAGAnythingAdapterConfig, work_dir: Path, run_id: str
    ) -> OfficialRAGAnythingRuntime:
        force_run_scoped_environment(work_dir)
        from lightrag.llm.ollama import ollama_embed, ollama_model_complete
        from lightrag.utils import EmbeddingFunc
        from raganything import RAGAnything, RAGAnythingConfig

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
                    "options": ollama_llm_options(config),
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
            parse_timeout_seconds=config.native_liveness.parse_timeout_seconds,
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
        self,
        path: Path,
        *,
        document_id: str,
        file_name: str,
        progress: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        callback = processing_progress_callback(progress) if progress is not None else None
        if callback is not None:
            self.rag.callback_manager.register(callback)
        try:
            await self.rag.process_document_complete(
                file_path=str(path),
                output_dir=str(self.output_dir),
                doc_id=document_id,
                file_name=file_name,
                display_stats=False,
                timeout=self.parse_timeout_seconds,
            )
        finally:
            if callback is not None:
                self.rag.callback_manager.unregister(callback)

    async def _query_native(
        self,
        question: str,
        *,
        mode: str,
        generate_answer: bool,
        options: dict[str, Any],
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

    async def query(
        self, question: str, *, mode: str, generate_answer: bool, options: dict[str, Any]
    ) -> str | None:
        """Invoke the native RAG-Anything query API without a second execution."""

        return await self._query_native(
            question,
            mode=mode,
            generate_answer=generate_answer,
            options=options,
        )

    async def query_with_observation(
        self,
        question: str,
        *,
        mode: str,
        generate_answer: bool,
        options: dict[str, Any],
    ) -> RuntimeQueryCapture:
        """Observe one native query without replaying retrieval or generation."""

        declared = {
            "mode": mode,
            "vlm_enhanced": bool(options.get("vlm_enhanced", False)),
            "top_k": options.get("top_k"),
            "chunk_top_k": options.get("chunk_top_k"),
            "max_total_tokens": options.get("max_total_tokens"),
        }
        if mode != "naive":
            answer = await self._query_native(
                question,
                mode=mode,
                generate_answer=generate_answer,
                options=options,
            )
            return RuntimeQueryCapture.unavailable(
                answer=answer,
                reason="rag_anything_non_naive_stage_derivation_is_not_observable",
                query_parameters=declared,
            )
        if bool(options.get("vlm_enhanced", False)):
            answer = await self._query_native(
                question,
                mode=mode,
                generate_answer=generate_answer,
                options=options,
            )
            return RuntimeQueryCapture.unavailable(
                answer=answer,
                reason="rag_anything_vlm_stage_derivation_is_not_observable",
                query_parameters=declared,
            )
        hook_error = self._ensure_query_capture_hooks()
        if hook_error is not None:
            answer = await self._query_native(
                question,
                mode=mode,
                generate_answer=generate_answer,
                options=options,
            )
            return RuntimeQueryCapture.unavailable(
                answer=answer,
                reason=hook_error,
                query_parameters=declared,
            )

        active = _ActiveQueryCapture()
        token = self._active_query_capture.set(active)
        try:
            answer = await self._query_native(
                question,
                mode=mode,
                generate_answer=generate_answer,
                options=options,
            )
        finally:
            self._active_query_capture.reset(token)

        if active.errors:
            return RuntimeQueryCapture.unavailable(
                answer=answer,
                status=ObservationStatus.CORRUPTED,
                reason=(
                    "native query observation capture failed: "
                    + ", ".join(sorted(set(active.errors)))
                ),
                query_parameters=declared,
            )
        if len(active.query_results) != 1 or len(active.candidate_calls) != 1:
            return RuntimeQueryCapture.unavailable(
                answer=answer,
                status=ObservationStatus.CORRUPTED,
                reason="native query did not expose exactly one query and candidate boundary",
                query_parameters=declared,
            )
        query_result = active.query_results[0]
        parameters = active.query_parameters[0] if active.query_parameters else {}
        observed_mode = parameters.get("mode")
        if observed_mode != "naive":
            return RuntimeQueryCapture.unavailable(
                answer=answer,
                status=ObservationStatus.CORRUPTED,
                reason="captured LightRAG query mode differs from the requested native mode",
                query_parameters={**declared, **parameters},
            )
        if parameters.get("enable_rerank") is not False:
            return RuntimeQueryCapture.unavailable(
                answer=answer,
                reason="native rerank intermediate boundary is not observable",
                query_parameters={**declared, **parameters},
            )
        candidate_cutoff, candidate_items = active.candidate_calls[0]
        llm_response = query_result.get("llm_response")
        captured_answer = (
            llm_response.get("content") if isinstance(llm_response, Mapping) else None
        )
        if generate_answer and captured_answer != answer:
            return RuntimeQueryCapture.unavailable(
                answer=answer,
                status=ObservationStatus.CORRUPTED,
                reason="captured native answer differs from RAG-Anything public output",
                query_parameters={**declared, **parameters},
            )
        return RuntimeQueryCapture.observed(
            answer=answer,
            candidate_items=candidate_items,
            query_result=query_result,
            candidate_cutoff=candidate_cutoff,
            query_parameters={**declared, **parameters},
        )

    def _ensure_query_capture_hooks(self) -> str | None:
        core = getattr(self.rag, "lightrag", None)
        if core is None:
            return "rag_anything_lightrag_runtime_is_unavailable"
        vector_store = getattr(core, "chunks_vdb", None)
        aquery_llm = getattr(core, "aquery_llm", None)
        vector_query = getattr(vector_store, "query", None)
        if not callable(aquery_llm) or not callable(vector_query):
            return "rag_anything_native_query_hooks_are_unsupported"
        if self._hooked_core is core and self._hooked_vector_store is vector_store:
            return None
        if self._hooked_core is not None:
            return "rag_anything_native_query_runtime_changed_after_hook_installation"

        self._original_aquery_llm = aquery_llm
        self._original_vector_query = vector_query

        async def observed_aquery_llm(*args: Any, **kwargs: Any) -> Any:
            assert self._original_aquery_llm is not None
            result = await self._original_aquery_llm(*args, **kwargs)
            active = self._active_query_capture.get()
            if active is not None:
                try:
                    if not isinstance(result, Mapping):
                        raise TypeError("structured query result is not a mapping")
                    copied_result = copy.deepcopy(dict(result))
                    param = kwargs.get("param")
                    if param is None and len(args) >= 2:
                        param = args[1]
                    parameters = {
                        "mode": getattr(param, "mode", None),
                        "enable_rerank": getattr(param, "enable_rerank", None),
                        "top_k": getattr(param, "top_k", None),
                        "chunk_top_k": getattr(param, "chunk_top_k", None),
                        "max_total_tokens": getattr(param, "max_total_tokens", None),
                    }
                    active.query_results.append(copied_result)
                    active.query_parameters.append(parameters)
                except Exception as exc:  # noqa: BLE001 - observation is non-invasive
                    active.errors.append(
                        f"aquery_llm_capture:{type(exc).__name__}"
                    )
            return result

        async def observed_vector_query(*args: Any, **kwargs: Any) -> Any:
            assert self._original_vector_query is not None
            result = await self._original_vector_query(*args, **kwargs)
            active = self._active_query_capture.get()
            if active is not None:
                try:
                    top_k = kwargs.get("top_k")
                    if top_k is None and len(args) >= 2:
                        top_k = args[1]
                    if (
                        not isinstance(top_k, int)
                        or top_k < 1
                        or not isinstance(result, list)
                    ):
                        raise TypeError("candidate boundary has an invalid shape")
                    active.candidate_calls.append(
                        (top_k, copy.deepcopy(result))
                    )
                except Exception as exc:  # noqa: BLE001 - observation is non-invasive
                    active.errors.append(
                        f"candidate_capture:{type(exc).__name__}"
                    )
            return result

        try:
            core.aquery_llm = observed_aquery_llm
            vector_store.query = observed_vector_query
        except Exception:  # noqa: BLE001 - a failed hook must restore native behavior
            core.aquery_llm = aquery_llm
            vector_store.query = vector_query
            self._original_aquery_llm = None
            self._original_vector_query = None
            return "rag_anything_native_query_hooks_could_not_be_installed"
        self._hooked_core = core
        self._hooked_vector_store = vector_store
        return None

    async def observe_ingestion_catalog(self) -> RuntimeIngestionCapture:
        """Read the complete run-scoped JsonKV stores after ingestion."""

        core = getattr(self.rag, "lightrag", None)
        if core is None:
            raise RuntimeError("RAG-Anything did not initialize LightRAG storage")
        chunks = await self._snapshot_json_kv(getattr(core, "text_chunks", None))
        full_rows = await self._snapshot_json_kv(getattr(core, "full_docs", None))
        full_documents = {
            key: str(row["content"])
            for key, row in full_rows.items()
            if isinstance(row.get("content"), str)
        }
        return RuntimeIngestionCapture(
            chunks=chunks,
            full_documents=full_documents,
            storage_identity="JsonKVStorage/complete-run-snapshot",
        )

    @staticmethod
    async def _snapshot_json_kv(storage: Any) -> dict[str, Mapping[str, Any]]:
        if storage is None:
            raise RuntimeError("required LightRAG JsonKV storage is unavailable")
        all_keys = getattr(storage, "all_keys", None)
        get_by_ids = getattr(storage, "get_by_ids", None)
        if callable(all_keys) and callable(get_by_ids):
            keys = sorted(await all_keys())
            rows = await get_by_ids(keys)
            if len(rows) != len(keys) or any(not isinstance(row, Mapping) for row in rows):
                raise RuntimeError("LightRAG JsonKV snapshot is incomplete")
            return {
                key: copy.deepcopy(dict(row)) for key, row in zip(keys, rows)
            }
        # LightRAG 1.4.16's JsonKV backend predates public key enumeration.
        # This adapter pins that backend and reads its complete in-memory map
        # only after the ingestion barrier.  Other storage types fail closed.
        if type(storage).__name__ != "JsonKVStorage":
            raise RuntimeError("LightRAG storage cannot prove complete enumeration")
        raw = getattr(storage, "_data", None)
        if raw is None:
            raise RuntimeError("LightRAG JsonKV storage is not initialized")
        return {
            str(key): copy.deepcopy(dict(value))
            for key, value in dict(raw).items()
            if isinstance(value, Mapping)
        }

    async def close(self) -> None:
        if self._hooked_core is not None and self._original_aquery_llm is not None:
            self._hooked_core.aquery_llm = self._original_aquery_llm
        if self._hooked_vector_store is not None and self._original_vector_query is not None:
            self._hooked_vector_store.query = self._original_vector_query
        await self.rag.finalize_storages()


def processing_progress_callback(
    progress: Callable[[str, dict[str, Any]], None],
) -> Any:
    """Bridge RAG-Anything's public callbacks to privacy-safe stage updates."""

    from raganything.callbacks import ProcessingCallback

    class ProgressCallback(ProcessingCallback):
        def on_parse_start(self, **_kwargs: Any) -> None:
            progress("parsing", {"event": "parse_start"})

        def on_parse_complete(
            self, content_blocks: int = 0, duration_seconds: float = 0.0, **_kwargs: Any
        ) -> None:
            progress(
                "indexing",
                {
                    "event": "parse_complete",
                    "content_blocks": content_blocks,
                    "parse_duration_seconds": duration_seconds,
                },
            )

        def on_text_insert_start(self, text_length: int = 0, **_kwargs: Any) -> None:
            progress(
                "indexing",
                {"event": "text_insert_start", "text_length": text_length},
            )

        def on_multimodal_start(self, item_count: int = 0, **_kwargs: Any) -> None:
            progress(
                "indexing",
                {"event": "multimodal_start", "item_count": item_count},
            )

        def on_document_complete(self, duration_seconds: float = 0.0, **_kwargs: Any) -> None:
            progress(
                "completed",
                {"event": "document_complete", "duration_seconds": duration_seconds},
            )

        def on_document_error(
            self,
            error: BaseException | str = "",
            stage: str = "",
            **_kwargs: Any,
        ) -> None:
            exc_type = type(error).__name__ if isinstance(error, BaseException) else "Error"
            progress(
                "failed",
                {
                    "event": "document_error",
                    "failed_stage": stage or "unknown",
                    "exception_type": exc_type,
                    "message": str(error).strip() or "<no message>",
                },
            )

    return ProgressCallback()


class IngestionLiveness:
    """Persist current ingestion stage without retaining source content or names."""

    def __init__(self, path: Path, *, stall_timeout_seconds: float) -> None:
        self.path = path
        self.stall_timeout_seconds = stall_timeout_seconds
        self._lock = RLock()
        self._last_progress_mono = monotonic()
        self._activity: tuple[int, int, int, float] | None = None
        self._record: dict[str, Any] = {
            "schema_version": 1,
            "stage": "idle",
            "active_stage": None,
            "document_id": None,
            "started_at": None,
            "updated_at": utc_now(),
            "last_progress_at": None,
            "progress_seq": 0,
            "details": {},
            "terminal": False,
            "cancellation_confirmed": False,
        }
        self._write()

    def transition(
        self,
        stage: str,
        *,
        document_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if stage not in {
            "idle",
            "parsing",
            "indexing",
            "stalled",
            "cancelling",
            "cancelled",
            "failed",
            "completed",
        }:
            raise ValueError(f"unknown ingestion liveness stage: {stage}")
        with self._lock:
            now = utc_now()
            if self._record["started_at"] is None and stage in {"parsing", "indexing"}:
                self._record["started_at"] = now
            if stage in {"parsing", "indexing"}:
                self._record["active_stage"] = stage
                self._last_progress_mono = monotonic()
                self._record["last_progress_at"] = now
                self._record["progress_seq"] += 1
            self._record.update(
                {
                    "stage": stage,
                    "updated_at": now,
                    "terminal": stage in {"cancelled", "failed", "completed"},
                    "details": dict(details or {}),
                }
            )
            if document_id is not None:
                self._record["document_id"] = document_id
            self._write()

    def observe_activity(
        self,
        activity: tuple[int, int, int, float],
        *,
        details: dict[str, Any],
    ) -> None:
        with self._lock:
            stage = str(self._record["stage"])
            active_stage = str(self._record.get("active_stage") or "parsing")
            if stage not in {"parsing", "indexing", "stalled"}:
                return
            if self._activity != activity:
                self._activity = activity
                self.transition(active_stage, details={"event": "activity", **details})
            elif monotonic() - self._last_progress_mono >= self.stall_timeout_seconds:
                self.transition(
                    "stalled",
                    details={"event": "no_observed_activity", **details},
                )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._record))

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(
            json.dumps(self._record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)


class RAGAnythingAdapter:
    def __init__(self) -> None:
        self._context: PrepareContext | None = None
        self._config: RAGAnythingAdapterConfig | None = None
        self._runtime: Runtime | None = None
        self._closed = False
        self._index_fingerprint: str | None = None
        self._work_dir: Path | None = None
        self._liveness: IngestionLiveness | None = None
        self._native_observation_snapshot: NativeObservationSnapshot | None = None
        self._native_observation_status = ObservationStatus.UNOBSERVED
        self._native_observation_reason = "native ingestion has not completed"
        self._prepared_system: PreparedSystemV2 | None = None

    async def prepare(
        self,
        original_docx: OriginalDocumentV2,
        resolved_config: ResolvedAdapterConfigV2,
    ) -> PreparedSystemV2:
        if "evaluation_corpus" in resolved_config.adapter_config:
            raise ValueError(
                "Direct Wire 2.0 owns the native source route; "
                "evaluation_corpus is not accepted"
            )
        context = PrepareContext(
            run_id=resolved_config.run_id,
            work_dir=resolved_config.work_dir,
            source_dir=resolved_config.source_dir,
            platform_version=resolved_config.platform_version,
            seed=resolved_config.seed,
            repetition=resolved_config.repetition,
        )
        prepared = await self._prepare_runtime(
            context,
            dict(resolved_config.adapter_config),
        )
        document = DocumentInput(
            document_id=original_docx.document_id,
            source_path=original_docx.source_path,
            sha256=original_docx.source_sha256,
            mime_type=original_docx.media_type,
            metadata={
                "original_name": original_docx.original_name,
                "canonical_provenance_path": original_docx.canonical_catalog_path,
                "canonical_provenance_sha256": (
                    original_docx.canonical_catalog_sha256
                ),
            },
        )
        ingestion = await self._ingest_documents([document])
        if ingestion.index_fingerprint is None:
            raise RuntimeError("RAG-Anything did not return an index fingerprint")
        runtime = self._require_prepared()[0]
        runtime_config = self._require_prepared()[1]
        query_observation_supported = (
            callable(getattr(runtime, "query_with_observation", None))
            and runtime_config.query_mode == "naive"
            and not runtime_config.enable_vlm_query
        )
        source, runtime_profile, observation = build_prepared_identities(
            document=original_docx,
            runtime_config=runtime_config.model_dump(mode="json"),
            system_version=runtime.system_version,
            core_version=runtime.core_version,
            adapter_version=ADAPTER_VERSION,
            ingestion_observation_supported=(
                self._native_observation_status != ObservationStatus.UNSUPPORTED
            ),
            query_observation_supported=query_observation_supported,
        )
        if self._native_observation_snapshot is not None:
            snapshot = self._native_observation_snapshot
            if (source, runtime_profile, observation) != (
                snapshot.source_identity,
                snapshot.runtime_profile,
                snapshot.observation_profile,
            ):
                raise RuntimeError(
                    "RAG-Anything prepared identities drifted after ingest"
                )
        artifact_digest = ingestion.details.get("index_artifact_digest")
        receipt = IngestionReceiptV2.build(
            document_id=original_docx.document_id,
            source_sha256=original_docx.source_sha256,
            index_fingerprint=ingestion.index_fingerprint,
            index_artifact_digest=(
                str(artifact_digest) if artifact_digest is not None else None
            ),
            details=dict(ingestion.details),
        )
        self._prepared_system = PreparedSystemV2.build(
            effective_config=prepared.effective_config,
            source_identity=source,
            runtime_profile=runtime_profile,
            observation_profile=observation,
            ingestion_receipt=receipt,
        )
        return self._prepared_system

    async def _prepare_runtime(
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
        self._liveness = IngestionLiveness(
            work_dir / INGESTION_LIVENESS_FILE,
            stall_timeout_seconds=effective.native_liveness.stall_timeout_seconds,
        )
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

    async def health(self) -> NativeHealthReportV2:
        if self._closed:
            return NativeHealthReportV2(status="closed", ready=False)
        liveness = self._liveness.snapshot() if self._liveness is not None else None
        stage = str((liveness or {}).get("stage") or "idle")
        status = stage if stage not in {"idle", "completed"} else (
            "ready" if self._runtime is not None else "initialized"
        )
        return NativeHealthReportV2(
            status=status,
            ready=stage not in {"stalled", "failed", "cancelled"},
            details={"prepared": self._runtime is not None, "ingestion": liveness},
        )

    async def _ingest_documents(
        self, documents: list[DocumentInput]
    ) -> IngestionResult:
        runtime, config, context = self._require_prepared()
        benchmark_documents = [
            document
            for document in documents
            if document.metadata.get("primary_evaluation_corpus")
            == "benchmark_segments"
        ]
        if benchmark_documents and len(benchmark_documents) != len(documents):
            raise ValueError("benchmark segment ingestion cannot be mixed with another corpus")
        if config.evaluation_corpus == "benchmark_segments" and not benchmark_documents:
            raise ValueError(
                "RAG-Anything is configured for benchmark_segments but received no benchmark leaf inputs"
            )
        if benchmark_documents and config.evaluation_corpus != "benchmark_segments":
            raise ValueError(
                "benchmark segment inputs require evaluation_corpus='benchmark_segments'"
            )
        benchmark_digest: str | None = None
        if benchmark_documents:
            values = [
                document.metadata.get("benchmark_contract_digest")
                for document in benchmark_documents
            ]
            if any(not isinstance(value, str) for value in values) or len(set(values)) != 1:
                raise ValueError("benchmark segment inputs must share one contract digest")
            benchmark_digest = values[0]
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
                self._set_liveness(
                    "indexing",
                    document_id=document.document_id,
                    details={"execution_view": "canonical-text"},
                )
                try:
                    await runtime.insert_text(
                        document.content,
                        document_id=document.document_id,
                        file_name=file_name,
                    )
                except Exception as exc:
                    self._set_liveness(
                        "failed",
                        document_id=document.document_id,
                        details=exception_details(exc, stage="indexing"),
                    )
                    raise
            else:
                self._set_liveness(
                    "parsing",
                    document_id=document.document_id,
                    details={"execution_view": "native-docx", "event": "submitted"},
                )
                monitor_stop = asyncio.Event()
                monitor = asyncio.create_task(
                    self._monitor_native_activity(monitor_stop),
                    name=f"native-liveness-{document.document_id}",
                )
                try:
                    await runtime.process_document(
                        path,
                        document_id=document.document_id,
                        file_name=file_name,
                        progress=self._native_progress,
                    )
                except asyncio.CancelledError:
                    self._set_liveness(
                        "cancelling",
                        document_id=document.document_id,
                        details={"stage": self._active_liveness_stage()},
                    )
                    raise
                except Exception as exc:
                    self._set_liveness(
                        "failed",
                        document_id=document.document_id,
                        details=exception_details(
                            exc, stage=self._active_liveness_stage()
                        ),
                    )
                    raise
                finally:
                    monitor_stop.set()
                    await monitor
        self._set_liveness(
            "completed", details={"ingested_documents": len(documents)}
        )
        self._index_fingerprint = digest.hexdigest()
        await self._capture_native_observation_snapshot(
            documents=documents,
            runtime=runtime,
            config=config,
            context=context,
        )
        details: dict[str, object] = {
            "failed_documents": 0,
            "index_artifact_digest": directory_digest(
                self._require_work_dir() / "storage"
            ),
            "native_observation": {
                "observation_status": self._native_observation_status.value,
                "reason": self._native_observation_reason,
                "runtime_chunk_count": (
                    len(self._native_observation_snapshot.runtime_chunks)
                    if self._native_observation_snapshot is not None
                    else None
                ),
            },
        }
        if benchmark_digest is not None:
            details.update(
                {
                    "benchmark_contract_schema_version": "rag-benchmark-contract/1",
                    "benchmark_contract_digest": benchmark_digest,
                    "benchmark_segment_mapping_status": "unsupported_stage",
                    "benchmark_segment_inputs": len(benchmark_documents),
                    "benchmark_segment_runtime_chunks": None,
                }
            )
        return IngestionResult(
            ingested_documents=len(documents),
            index_fingerprint=self._index_fingerprint,
            details=details,
        )

    async def query(
        self,
        prepared_system: PreparedSystemV2,
        request: NativeQueryV2,
    ) -> AdapterRunResultV2:
        if self._prepared_system is None or prepared_system != self._prepared_system:
            raise ValueError("query references a different prepared system")
        runtime, config, _context = self._require_prepared()
        reserved = {"mode", "only_need_context", "only_need_prompt"}
        invalid = reserved.intersection(request.generation_options)
        if invalid:
            raise ValueError(f"reserved generation options: {sorted(invalid)}")
        options = generation_options(config, request.generation_options)
        options.update(
            {
                "top_k": request.retrieval_candidate_k,
                "chunk_top_k": request.final_context_k,
                "max_total_tokens": request.max_context_tokens,
                "vlm_enhanced": config.enable_vlm_query,
            }
        )
        started = monotonic()
        query_with_observation = getattr(runtime, "query_with_observation", None)
        query_observation_supported = (
            prepared_system.observation_profile.capabilities.candidate_retrieval
        )
        capture: RuntimeQueryCapture | None = None
        if (
            self._native_observation_snapshot is not None
            and query_observation_supported
            and callable(query_with_observation)
        ):
            observed = await query_with_observation(
                request.question,
                mode=config.query_mode,
                generate_answer=request.generate_answer,
                options=options,
            )
            if not isinstance(observed, RuntimeQueryCapture):
                raise TypeError("runtime query observation has an invalid type")
            capture = observed
            answer = capture.answer
        else:
            answer = await runtime.query(
                request.question,
                mode=config.query_mode,
                generate_answer=request.generate_answer,
                options=options,
            )
            if self._native_observation_snapshot is not None:
                capture = RuntimeQueryCapture.unavailable(
                    answer=answer,
                    reason=(
                        "RAG-Anything profile does not expose verifiable "
                        "same-execution query stages"
                    ),
                    status=(
                        ObservationStatus.UNOBSERVED
                        if query_observation_supported
                        else ObservationStatus.UNSUPPORTED
                    ),
                    query_parameters={
                        "mode": config.query_mode,
                        "top_k": options["top_k"],
                        "chunk_top_k": options["chunk_top_k"],
                        "max_total_tokens": options["max_total_tokens"],
                    },
                )
        elapsed = monotonic() - started
        telemetry = {
            "latency": {"native_query_latency": elapsed},
            "native_query_executions": 1,
            "query_mode": config.query_mode,
            "index_fingerprint": self._index_fingerprint,
            "retrieval_observability": (
                capture.observation_status.value
                if capture is not None
                else self._native_observation_status.value
            ),
        }
        snapshot = self._native_observation_snapshot
        if snapshot is None:
            return unavailable_native_result(
                prepared=prepared_system,
                query=request,
                status=self._native_observation_status,
                reason=self._native_observation_reason,
                answer=answer,
                telemetry=telemetry,
            )
        if capture is None:
            capture = RuntimeQueryCapture.unavailable(
                answer=answer,
                reason="same-execution native query observation is unavailable",
            )
        try:
            result = build_native_run_result_v2(
                snapshot=snapshot,
                case_id=request.case_id,
                capture=capture,
                generate_answer=request.generate_answer,
                adapter_version=ADAPTER_VERSION,
            )
        except (TypeError, ValueError) as exc:
            return unavailable_native_result(
                prepared=prepared_system,
                query=request,
                status=ObservationStatus.CORRUPTED,
                reason=f"native Wire 2.0 trace failed validation: {exc}",
                answer=answer,
                telemetry=telemetry,
            )
        return result.model_copy(update={"telemetry": telemetry})

    async def _capture_native_observation_snapshot(
        self,
        *,
        documents: list[DocumentInput],
        runtime: Runtime,
        config: RAGAnythingAdapterConfig,
        context: PrepareContext,
    ) -> None:
        self._native_observation_snapshot = None
        self._native_observation_status = ObservationStatus.UNOBSERVED
        self._native_observation_reason = (
            "native observation requires one source-document DOCX with a canonical sidecar"
        )
        if config.evaluation_corpus != "source_document" or len(documents) != 1:
            return
        document = documents[0]
        if (
            document.content is not None
            or document.source_path is None
            or Path(document.source_path).suffix.lower() != ".docx"
        ):
            return
        observe_catalog = getattr(runtime, "observe_ingestion_catalog", None)
        if not callable(observe_catalog):
            self._native_observation_status = ObservationStatus.UNSUPPORTED
            self._native_observation_reason = (
                "runtime does not expose a complete native ingestion catalog"
            )
            return
        try:
            capture = await observe_catalog()
            if not isinstance(capture, RuntimeIngestionCapture):
                raise TypeError("runtime ingestion observation has an invalid type")
            snapshot = build_native_observation_snapshot(
                document=document,
                source_dir=Path(context.source_dir),
                capture=capture,
                runtime_config=config.model_dump(mode="json"),
                system_version=runtime.system_version,
                core_version=runtime.core_version,
                adapter_version=ADAPTER_VERSION,
                query_observation_supported=(
                    callable(getattr(runtime, "query_with_observation", None))
                    and config.query_mode == "naive"
                    and not config.enable_vlm_query
                ),
            )
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            self._native_observation_status = ObservationStatus.CORRUPTED
            self._native_observation_reason = (
                f"native ingestion observation failed validation: {exc}"
            )
            return
        self._native_observation_snapshot = snapshot
        self._native_observation_status = ObservationStatus.OBSERVED
        self._native_observation_reason = None

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

    def _native_progress(self, stage: str, details: dict[str, Any]) -> None:
        self._set_liveness(stage, details=details)

    async def _monitor_native_activity(self, stop: asyncio.Event) -> None:
        assert self._config is not None
        while not stop.is_set():
            activity = native_activity_snapshot(self._require_work_dir())
            details = {
                "output_files": activity[0],
                "output_bytes": activity[1],
                "child_processes": activity[2],
                "child_cpu_seconds": activity[3],
            }
            if self._liveness is not None:
                self._liveness.observe_activity(activity, details=details)
            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=self._config.native_liveness.poll_interval_seconds,
                )
            except TimeoutError:
                pass

    def _active_liveness_stage(self) -> str:
        if self._liveness is None:
            return "unknown"
        snapshot = self._liveness.snapshot()
        return str(snapshot.get("active_stage") or snapshot.get("stage") or "unknown")

    def _set_liveness(
        self,
        stage: str,
        *,
        document_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if self._liveness is not None:
            self._liveness.transition(
                stage, document_id=document_id, details=details or {}
            )

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


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def exception_details(exc: BaseException, *, stage: str) -> dict[str, str]:
    return {
        "failed_stage": stage,
        "exception_type": type(exc).__name__,
        "message": str(exc).strip() or "<no message>",
    }


def native_activity_snapshot(work_dir: Path) -> tuple[int, int, int, float]:
    """Return content-free filesystem and child-CPU liveness counters."""

    file_count = 0
    total_bytes = 0
    for name in ("parser-output", "storage"):
        root = work_dir / name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            file_count += 1
            total_bytes += size
    descendants = descendant_cpu_times(os.getpid())
    return file_count, total_bytes, len(descendants), round(sum(descendants), 3)


def descendant_cpu_times(parent_pid: int) -> list[float]:
    """Inspect descendants without persisting their commands or source paths."""

    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,time="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    rows: list[tuple[int, int, float]] = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 3:
            continue
        try:
            rows.append((int(fields[0]), int(fields[1]), parse_cpu_time(fields[2])))
        except ValueError:
            continue
    descendants: set[int] = set()
    frontier = {parent_pid}
    while frontier:
        children = {pid for pid, ppid, _cpu in rows if ppid in frontier}
        children -= descendants
        if not children:
            break
        descendants.update(children)
        frontier = children
    return [cpu for pid, _ppid, cpu in rows if pid in descendants]


def parse_cpu_time(value: str) -> float:
    """Parse the portable ps TIME form: [[dd-]hh:]mm:ss."""

    days = 0
    clock = value
    if "-" in clock:
        day_text, clock = clock.split("-", 1)
        days = int(day_text)
    fields = clock.split(":")
    if len(fields) == 2:
        hours = 0
        minutes, seconds = fields
    elif len(fields) == 3:
        hours, minutes, seconds = fields
    else:
        raise ValueError(f"unsupported ps TIME value: {value}")
    return days * 86400 + int(hours) * 3600 + int(minutes) * 60 + float(seconds)


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
        digest = normalize_ollama_digest(exact_ollama_model_digest(rows, model))
        results[role] = digest or identity_digest(config.binding, model)
    return results


def model_artifacts(
    config: OllamaModelConfig, digests: dict[str, str]
) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for role, requested in (
        ("llm", config.llm_model),
        ("embedding", config.embedding_model),
    ):
        digest = digests.get(role)
        normalized_digest = normalize_ollama_digest(digest)
        verified = normalized_digest is not None
        values[role] = {
            "display_name": requested.split(":", 1)[0],
            "requested_ref": requested,
            "resolved_digest": normalized_digest,
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


def ollama_llm_options(config: RAGAnythingAdapterConfig) -> dict[str, int]:
    return {"num_ctx": config.model.llm_num_ctx}


def normalize_ollama_digest(value: str | None) -> str | None:
    """Normalize Ollama's bare `/api/tags` digest to a contract SHA-256 URI."""

    candidate = str(value or "").strip()
    if candidate.startswith("sha256:"):
        candidate = candidate.removeprefix("sha256:")
    if len(candidate) != 64 or any(
        character not in "0123456789abcdef" for character in candidate
    ):
        return None
    return f"sha256:{candidate}"


def exact_ollama_model_digest(rows: object, requested_ref: str) -> str | None:
    """Resolve only the exact requested tag; short-name matching is ambiguous."""

    if not isinstance(rows, list):
        return None
    for item in rows:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("model") or "")
        if name == requested_ref:
            return str(item.get("digest") or "") or None
    return None


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
        identity=WorkerIdentityV2(
            adapter_id="rag-anything",
            adapter_version=ADAPTER_VERSION,
            system_id="rag-anything",
            system_version=version,
        ),
    )
