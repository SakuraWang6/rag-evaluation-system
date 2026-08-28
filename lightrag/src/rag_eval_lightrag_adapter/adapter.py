"""Honest, run-scoped LightRAG adapter behind Wire Protocol 1.0."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import socket
import subprocess
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any, Literal
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
    RAGEvidenceItem,
    RAGQuery,
    RAGResult,
    ResetResult,
)
from rag_eval.contracts.dataset import ObjectLocator, TableCellLocator
from rag_eval.contracts.wire import HandshakeResponse
from rag_eval.worker.app import WorkerDefinition

from rag_eval_lightrag_adapter.canonical_provenance import (
    CanonicalDocumentMap,
    build_provenance_manifest,
    load_canonical_document_map,
    normalize_source_span,
    sha256_text,
    write_provenance_manifest,
)

ADAPTER_VERSION = "0.1.0"
CAPABILITIES = AdapterCapabilities(
    answer=True,
    raw_retrieval=True,
    ranked_retrieval=True,
    final_context=True,
    object_provenance=True,
    prompt_trace=False,
    rerank_trace=False,
    latency_breakdown=True,
    token_usage=False,
    reset=False,
)


class ChunkingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["fixed_token"] = "fixed_token"
    chunk_token_size: int = Field(default=1200, ge=1)
    chunk_overlap_token_size: int = Field(default=100, ge=0)


class ModelConfig(BaseModel):
    """Explicit model wiring; omitted fields retain a registered worker value.

    A formal run supplies these fields and the platform verifies the resolved
    artifact identities returned by ``prepare`` before ingestion.
    """

    model_config = ConfigDict(extra="forbid")

    llm_binding: str | None = None
    llm_model: str | None = None
    llm_host: str | None = None
    query_llm_binding: str | None = None
    query_llm_model: str | None = None
    query_llm_host: str | None = None
    embedding_binding: str | None = None
    embedding_model: str | None = None
    embedding_host: str | None = None
    llm_num_ctx: int = Field(default=32768, ge=1024)


class GenerationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature: float | None = Field(default=None, ge=0, le=2)
    seed: int | None = None
    user_prompt: str | None = None
    response_type: str | None = None


class LightRAGAdapterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: Literal["legacy", "structured"] = "legacy"
    query_mode: Literal["naive"] = "naive"
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    retrieval_candidate_k: int = Field(default=20, ge=1)
    final_context_k: int = Field(default=5, ge=1)
    max_context_tokens: int = Field(default=12000, ge=1)
    enable_rerank: bool = False
    rerank_model: str | None = None
    ranking_strategy: Literal["none", "structured"] = "none"
    exact_id_types: list[str] = Field(default_factory=list)
    table_preceding_context: bool = False
    table_structured_envelope: bool = False
    table_view: bool = False
    table_row_view: bool = False
    entity_extraction_instruction_profile: Literal["legacy", "structured_fidelity"] = (
        "legacy"
    )
    model: ModelConfig = Field(default_factory=ModelConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    server_start_timeout_seconds: float = Field(default=90.0, gt=0)
    ingestion_timeout_seconds: float = Field(default=900.0, gt=0)
    query_timeout_seconds: float = Field(default=180.0, gt=0)
    poll_interval_seconds: float = Field(default=0.25, gt=0)

    def validate_invariants(self) -> None:
        if self.chunking.chunk_overlap_token_size >= self.chunking.chunk_token_size:
            raise ValueError("chunk overlap must be smaller than chunk token size")
        invalid = [
            value
            for value in self.exact_id_types
            if not value or not value.replace("_", "").isalnum()
        ]
        if invalid:
            raise ValueError(f"invalid exact-ID prefixes: {invalid}")
        if self.enable_rerank and not self.rerank_model:
            raise ValueError("rerank_model is required when enable_rerank is true")


def resolve_config(raw: dict[str, Any]) -> LightRAGAdapterConfig:
    profile = str(raw.get("profile", "legacy"))
    defaults: dict[str, Any] = {}
    if profile == "structured":
        defaults = {
            "ranking_strategy": "structured",
            "exact_id_types": ["FACT", "EQ", "REF"],
            "table_preceding_context": True,
            "entity_extraction_instruction_profile": "structured_fidelity",
        }
    config = LightRAGAdapterConfig.model_validate({**defaults, **raw})
    config.validate_invariants()
    return config


class LightRAGAdapter:
    def __init__(self) -> None:
        self._config: LightRAGAdapterConfig | None = None
        self._context: PrepareContext | None = None
        self._server: subprocess.Popen[str] | None = None
        self._server_log = None
        self._server_log_path: Path | None = None
        self._server_log_redactions: tuple[str, ...] = ()
        self._client: httpx.AsyncClient | None = None
        self._endpoint: str | None = None
        self._closed = False
        self._source_by_file: dict[str, str] = {}
        self._source_text_by_document: dict[str, str] = {}
        self._canonical_provenance_by_document: dict[str, CanonicalDocumentMap] = {}
        self._runtime_provenance_by_chunk: dict[str, dict[str, Any]] = {}
        self._provenance_map_digest: str | None = None
        self._index_fingerprint: str | None = None
        self._work_dir: Path | None = None

    async def prepare(
        self, context: PrepareContext, config: dict[str, Any]
    ) -> PreparedSystem:
        if self._closed:
            raise RuntimeError("adapter is closed")
        if self._config is not None:
            raise RuntimeError("adapter is already prepared")
        effective = resolve_config(config)
        work_dir = Path(context.work_dir).resolve()
        if work_dir.exists() and any(work_dir.iterdir()):
            raise RuntimeError(
                "run work directory is not empty; refusing stale index reuse"
            )
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "inputs").mkdir()
        (work_dir / "storage").mkdir()

        self._context = context
        self._config = effective
        self._work_dir = work_dir
        await self._start_server(work_dir)
        runtime_identity = safe_runtime_identity(
            build_server_environment(effective, work_dir)
        )
        model_artifacts = await ollama_model_artifacts(runtime_identity)
        return PreparedSystem(
            effective_config={
                **effective.model_dump(mode="json"),
                "ingestion_policy": {
                    "process_options": "!",
                    "kg_extraction": False,
                    "reason": "naive_query_mode_uses_chunk_embeddings_only",
                },
                "runtime": runtime_identity,
                "model_digests": model_digests(model_artifacts),
                "model_artifacts": model_artifacts,
                "prompt_digests": {
                    "lightrag_prompt_sources": package_prompt_digest("lightrag")
                },
                "cache_policy": {"answer": False, "query": False, "llm": False},
                "isolation": "run_scoped_managed_process",
                "code_identity": code_identity(),
            },
            capabilities=CAPABILITIES,
            system_version=system_version(),
        )

    async def health(self) -> HealthReport:
        if self._closed:
            return HealthReport(status="closed", ready=False)
        if self._server is None:
            return HealthReport(
                status="initialized", ready=True, details={"prepared": False}
            )
        if self._server.poll() is not None:
            return HealthReport(
                status="failed",
                ready=False,
                details={"server_exit_code": self._server.returncode},
            )
        try:
            payload = await self._get_json("/health", timeout=2.0)
        except Exception as exc:  # noqa: BLE001
            return HealthReport(
                status="starting", ready=False, details={"reason": str(exc)}
            )
        return HealthReport(
            status=str(payload.get("status") or "ready"),
            ready=True,
            details={"endpoint": "loopback", "prepared": True},
        )

    async def ingest(self, documents: list[DocumentInput]) -> IngestionResult:
        config = self._require_prepared()
        digest = hashlib.sha256()
        digest.update(
            json.dumps(
                ingestion_identity(config), sort_keys=True, separators=(",", ":")
            ).encode()
        )
        failures: list[dict[str, str]] = []
        for index, document in enumerate(documents):
            if document.content is None:
                raise ValueError("LightRAGAdapter only supports text source documents")
            digest.update(document.document_id.encode())
            digest.update(b"\0")
            digest.update(document.content.encode())
            digest.update(b"\0")
            source_name = safe_source_name(index, document.document_id)
            self._source_by_file[source_name] = document.document_id
            self._source_text_by_document[document.document_id] = document.content
            canonical = self._load_canonical_provenance(document)
            if canonical is not None:
                self._canonical_provenance_by_document[document.document_id] = canonical
                digest.update(canonical.canonical_sidecar_sha256.encode())
                digest.update(b"\0")
            try:
                response = await self._post_document(
                    source_name,
                    document.content.encode("utf-8"),
                    document.mime_type,
                )
                track_id = response.get("track_id")
                if not isinstance(track_id, str) or not track_id:
                    raise RuntimeError("LightRAG ingestion did not return a track_id")
                await self._wait_for_ingestion(track_id)
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "document_id": document.document_id,
                        "exception_type": type(exc).__name__,
                        "message": exception_diagnostic(exc),
                    }
                )
                break
        if failures:
            raise RuntimeError(f"LightRAG ingestion failed: {failures}")
        provenance_manifest = self._build_ingestion_provenance_manifest()
        provenance_path = self._require_work_dir() / "canonical-provenance-map.json"
        self._provenance_map_digest = write_provenance_manifest(
            provenance_path, provenance_manifest
        )
        self._runtime_provenance_by_chunk = provenance_manifest["runtime_chunks"]
        self._index_fingerprint = digest.hexdigest()
        provenance_statuses: dict[str, int] = {}
        for mapping in self._runtime_provenance_by_chunk.values():
            status = str(mapping.get("provenance_status") or "missing")
            provenance_statuses[status] = provenance_statuses.get(status, 0) + 1
        return IngestionResult(
            ingested_documents=len(documents),
            index_fingerprint=self._index_fingerprint,
            details={
                "failed_documents": 0,
                "index_artifact_digest": directory_digest(
                    self._require_work_dir() / "storage"
                ),
                "canonical_provenance_map_digest": self._provenance_map_digest,
                "canonical_provenance_documents": len(
                    self._canonical_provenance_by_document
                ),
                "runtime_chunk_provenance": provenance_statuses,
            },
        )

    async def query(self, request: RAGQuery) -> RAGResult:
        config = self._require_prepared()
        candidate_k = request.retrieval_candidate_k or config.retrieval_candidate_k
        context_k = request.final_context_k or config.final_context_k
        max_tokens = request.max_context_tokens or config.max_context_tokens
        payload = {
            "query": request.question,
            "mode": config.query_mode,
            "retrieval_candidate_k": candidate_k,
            "chunk_top_k": context_k,
            "max_total_tokens": max_tokens,
            "enable_rerank": config.enable_rerank,
            "evaluation_trace": True,
            "include_references": True,
            "include_chunk_content": True,
            "stream": False,
        }
        payload.update(generation_payload(config, request.generation_options))
        started = monotonic()
        endpoint = "/query" if request.generate_answer else "/query/data"
        response = await self._post_json(endpoint, payload)
        elapsed = monotonic() - started
        trace = response.get("evaluation_trace")
        if not isinstance(trace, dict):
            raise RuntimeError("LightRAG did not return the requested evaluation trace")
        stages = trace.get("retrieval_stages")
        if not isinstance(stages, dict):
            raise RuntimeError("LightRAG evaluation trace lacks retrieval stages")
        raw_items = self._evidence_items(stages.get("raw_retrieval"), "raw")
        ranked_items = self._evidence_items(stages.get("ranked_retrieval"), "ranked")
        final_items = self._evidence_items(stages.get("final_context"), "context")
        answer = response.get("response") if request.generate_answer else None
        if request.generate_answer and not isinstance(answer, str):
            raise RuntimeError("LightRAG answer response is malformed")
        return RAGResult(
            answer=answer,
            raw_retrieval=raw_items,
            ranked_retrieval=ranked_items,
            final_context=final_items,
            latency={"native_query_latency": elapsed},
            trace=None,
            native_metadata={
                "query_mode": config.query_mode,
                "index_fingerprint": self._index_fingerprint,
                "core_trace_schema": trace.get("schema_version"),
                "canonical_provenance_map_digest": self._provenance_map_digest,
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
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()
        server, self._server = self._server, None
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                await asyncio.to_thread(server.wait, 5)
            except subprocess.TimeoutExpired:
                server.kill()
                await asyncio.to_thread(server.wait, 5)
        if self._server_log is not None:
            self._server_log.close()
            self._server_log = None
        if self._server_log_path is not None:
            redact_runtime_endpoints_in_logs(
                self._server_log_path.parent, self._server_log_redactions
            )
            self._server_log_path = None
            self._server_log_redactions = ()

    async def _start_server(self, work_dir: Path) -> None:
        assert self._config is not None
        port = reserve_loopback_port()
        self._endpoint = f"http://127.0.0.1:{port}"
        self._server_log_path = work_dir / "lightrag-server.log"
        self._server_log = self._server_log_path.open(
            "a", encoding="utf-8"
        )
        environment = build_server_environment(self._config, work_dir)
        self._server_log_redactions = tuple(
            value
            for key, value in environment.items()
            if key.endswith("_HOST") and value
        )
        command = [
            sys.executable,
            "-m",
            "lightrag.api.lightrag_server",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--working-dir",
            str(work_dir / "storage"),
            "--input-dir",
            str(work_dir / "inputs"),
            "--workspace",
            f"eval_{self._context.run_id}",
            "--workers",
            "1",
        ]
        self._server = subprocess.Popen(
            command,
            cwd=work_dir,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=self._server_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._client = httpx.AsyncClient(base_url=self._endpoint, timeout=180.0)
        deadline = monotonic() + self._config.server_start_timeout_seconds
        while monotonic() < deadline:
            if self._server.poll() is not None:
                self._redact_server_logs()
                raise RuntimeError(
                    f"managed LightRAG server exited with code {self._server.returncode}"
                )
            try:
                health = await self._get_json("/health", timeout=2.0)
                if str(health.get("status", "")).lower() == "healthy":
                    return
            except (httpx.HTTPError, ValueError):
                pass
            await asyncio.sleep(0.2)
        self._redact_server_logs()
        raise TimeoutError("managed LightRAG server did not become healthy")

    def _redact_server_logs(self) -> None:
        if self._server_log is not None:
            self._server_log.flush()
        if self._server_log_path is not None:
            redact_runtime_endpoints_in_logs(
                self._server_log_path.parent, self._server_log_redactions
            )

    async def _wait_for_ingestion(self, track_id: str) -> None:
        assert self._config is not None
        deadline = monotonic() + self._config.ingestion_timeout_seconds
        while monotonic() < deadline:
            payload = await self._get_json(
                f"/documents/track_status/{track_id}", timeout=30.0
            )
            documents = payload.get("documents")
            if isinstance(documents, list) and documents:
                statuses = {
                    str(item.get("status", "")).lower()
                    for item in documents
                    if isinstance(item, dict)
                }
                if statuses and statuses <= {"processed"}:
                    return
                if "failed" in statuses:
                    messages = [
                        str(item.get("error_msg") or "failed")
                        for item in documents
                        if isinstance(item, dict)
                    ]
                    raise RuntimeError(
                        f"LightRAG document processing failed: {messages}"
                    )
            await asyncio.sleep(self._config.poll_interval_seconds)
        raise TimeoutError(f"LightRAG ingestion timed out for track {track_id}")

    async def _get_json(self, path: str, *, timeout: float) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("LightRAG client is not initialized")
        response = await self._client.get(path, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("LightRAG returned a non-object response")
        return payload

    async def _post_json(
        self, path: str, payload: dict[str, Any], *, timeout: float | None = None
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("LightRAG client is not initialized")
        request_timeout = (
            timeout
            if timeout is not None
            else self._require_prepared().query_timeout_seconds
        )
        response = await self._client.post(path, json=payload, timeout=request_timeout)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("LightRAG returned a non-object response")
        return body

    async def _post_document(
        self, filename: str, content: bytes, mime_type: str
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("LightRAG client is not initialized")
        config = self._require_prepared()
        response = await self._client.post(
            "/documents/upload",
            files={"file": (filename, content, mime_type)},
            # The adapter exposes only LightRAG's naive query mode.  Naive
            # retrieval consumes chunk embeddings and never reads the KG, so
            # entity/relation extraction is unnecessary ingestion work.  The
            # documented `!` option keeps chunk insertion while skipping KG
            # extraction and its unrelated LLM failure surface.
            data={"process_options": "!"},
            timeout=config.ingestion_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("LightRAG returned a non-object response")
        return body

    def _evidence_items(self, raw: Any, stage: str) -> list[RAGEvidenceItem]:
        if not isinstance(raw, list):
            raise RuntimeError(f"LightRAG trace stage {stage!r} is not observable")
        items: list[RAGEvidenceItem] = []
        for expected_rank, value in enumerate(raw, start=1):
            if not isinstance(value, dict):
                raise RuntimeError(f"LightRAG trace stage {stage!r} is malformed")
            file_path = str(value.get("file_path") or "")
            document_id = self._source_by_file.get(Path(file_path).name)
            item_id = str(value.get("item_id") or f"{stage}-{expected_rank}")
            native_id = (
                str(value.get("native_id"))
                if value.get("native_id") is not None
                else None
            )
            content = str(value.get("content") or "")
            mapping = (
                self._runtime_provenance_by_chunk.get(native_id)
                if native_id is not None
                else None
            )
            trace_span = normalize_source_span(value.get("source_span"))
            if mapping is not None:
                document_id = (
                    str(mapping.get("document_id") or document_id or "") or None
                )
            mapping_span = normalize_source_span(
                mapping.get("source_span") if mapping is not None else None
            )
            mapping_valid = bool(
                mapping is not None
                and trace_span is not None
                and trace_span == mapping_span
                and mapping.get("content_sha256") == sha256_text(content)
            )
            canonical_objects = (
                list(mapping.get("canonical_objects") or [])
                if mapping_valid and mapping is not None
                else []
            )
            full_objects = [
                entry
                for entry in canonical_objects
                if isinstance(entry, dict) and entry.get("coverage") == "full"
            ]
            runtime_structure = (
                mapping.get("structure")
                if mapping_valid
                and mapping is not None
                and isinstance(mapping.get("structure"), dict)
                else {
                    "metadata_status": "missing",
                    "missing_fields": ["verified_runtime_structure"],
                    "section_ids": [],
                    "canonical_object_count": 0,
                }
            )
            base_metadata = {
                "file_path": file_path or None,
                "source_type": value.get("source_type"),
                "runtime_chunk_id": native_id,
                "runtime_source_span": (
                    {"start": trace_span[0], "end": trace_span[1]}
                    if trace_span is not None
                    else None
                ),
                "provenance_status": (
                    mapping.get("provenance_status")
                    if mapping_valid and mapping is not None
                    else "missing"
                ),
                "provenance_reason": (
                    mapping.get("reason")
                    if mapping_valid and mapping is not None
                    else "trace_ingestion_mapping_mismatch"
                ),
                "canonical_object_ids": [
                    entry.get("object_id")
                    for entry in canonical_objects
                    if isinstance(entry, dict)
                ],
                "canonical_full_object_ids": [
                    entry.get("object_id") for entry in full_objects
                ],
                "canonical_partial_object_ids": [
                    entry.get("object_id")
                    for entry in canonical_objects
                    if isinstance(entry, dict) and entry.get("coverage") == "partial"
                ],
                "runtime_structure": runtime_structure,
                "canonical_object_structures": [
                    entry.get("structure")
                    for entry in canonical_objects
                    if isinstance(entry, dict)
                    and isinstance(entry.get("structure"), dict)
                ],
                "source_witness_sha256": (
                    mapping.get("source_witness_sha256")
                    if mapping_valid and mapping is not None
                    else None
                ),
                "canonical_provenance_map_digest": self._provenance_map_digest,
            }
            if not full_objects:
                items.append(
                    self._evidence_item(
                        stage=stage,
                        item_id=item_id,
                        expected_rank=expected_rank,
                        content=content,
                        document_id=document_id,
                        native_id=native_id,
                        score=value.get("score"),
                        locator=None,
                        metadata=base_metadata,
                    )
                )
                continue
            for projection, entry in enumerate(full_objects, start=1):
                locator = entry.get("locator")
                if not isinstance(locator, dict):
                    continue
                parsed_locator = (
                    TableCellLocator.model_validate(locator)
                    if locator.get("type") == "table_cell"
                    else ObjectLocator.model_validate(locator)
                )
                projection_key = hashlib.sha256(
                    str(entry.get("object_id") or "").encode()
                ).hexdigest()[:12]
                items.append(
                    self._evidence_item(
                        stage=stage,
                        item_id=f"{item_id}:provenance-{projection_key}",
                        expected_rank=expected_rank,
                        content=content,
                        document_id=document_id,
                        native_id=native_id,
                        score=value.get("score"),
                        locator=parsed_locator,
                        metadata={
                            **base_metadata,
                            "provenance_projection": projection,
                            "provenance_projection_count": len(full_objects),
                            "canonical_object_id": entry.get("object_id"),
                            "canonical_object_type": entry.get("object_type"),
                            "canonical_object_status": entry.get("status"),
                            "canonical_object_span": entry.get("source_span"),
                            "canonical_overlap_span": entry.get("overlap_span"),
                            "canonical_witness_sha256": entry.get("witness_sha256"),
                            "canonical_alignment_method": entry.get("alignment_method"),
                            "canonical_structure": entry.get("structure"),
                        },
                    )
                )
        return items

    @staticmethod
    def _evidence_item(
        *,
        stage: str,
        item_id: str,
        expected_rank: int,
        content: str,
        document_id: str | None,
        native_id: str | None,
        score: Any,
        locator: ObjectLocator | TableCellLocator | None,
        metadata: dict[str, Any],
    ) -> RAGEvidenceItem:
        return RAGEvidenceItem(
            item_id=f"{stage}:{item_id}",
            rank=expected_rank,
            content=content,
            document_id=document_id,
            locator=locator,
            score=score if isinstance(score, (int, float)) else None,
            native_id=native_id,
            metadata=metadata,
        )

    def _load_canonical_provenance(
        self, document: DocumentInput
    ) -> CanonicalDocumentMap | None:
        raw_path = document.metadata.get("canonical_provenance_path")
        raw_digest = document.metadata.get("canonical_provenance_sha256")
        if raw_path is None and raw_digest is None:
            return None
        if not isinstance(raw_path, str) or Path(raw_path).name != raw_path:
            raise ValueError("canonical provenance path is not a safe staged filename")
        # The Platform stages every manifest canonical_path for source-only
        # workers. Only the authoring object-graph JSONL has the bridge contract;
        # ordinary canonical text files remain valid inputs with no provenance.
        if not raw_path.lower().endswith(".jsonl"):
            return None
        if (
            not isinstance(raw_digest, str)
            or len(raw_digest) != 64
            or any(character not in "0123456789abcdef" for character in raw_digest)
        ):
            raise ValueError("canonical provenance digest is malformed")
        if self._context is None or document.content is None:
            raise RuntimeError("canonical provenance requires prepared text ingestion")
        sidecar_path = Path(self._context.source_dir) / raw_path
        if not sidecar_path.is_file():
            raise ValueError(
                "canonical provenance sidecar is missing from source sandbox"
            )
        return load_canonical_document_map(
            document_id=document.document_id,
            source=document.content,
            sidecar_path=sidecar_path,
            expected_sidecar_sha256=raw_digest,
        )

    def _build_ingestion_provenance_manifest(self) -> dict[str, Any]:
        if not self._canonical_provenance_by_document:
            return build_provenance_manifest(
                documents={},
                sources={},
                document_by_file={},
                stored_chunks={},
            )
        candidates = sorted(
            (self._require_work_dir() / "storage").rglob("kv_store_text_chunks.json")
        )
        if len(candidates) != 1:
            raise RuntimeError(
                "LightRAG canonical provenance requires one authoritative "
                f"text chunk store; observed {len(candidates)}"
            )
        payload = json.loads(candidates[0].read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or any(
            not isinstance(value, dict) for value in payload.values()
        ):
            raise RuntimeError("LightRAG text chunk store is malformed")
        return build_provenance_manifest(
            documents=self._canonical_provenance_by_document,
            sources=self._source_text_by_document,
            document_by_file=self._source_by_file,
            stored_chunks=payload,
        )

    def _require_prepared(self) -> LightRAGAdapterConfig:
        if self._closed:
            raise RuntimeError("adapter is closed")
        if self._config is None or self._server is None:
            raise RuntimeError("adapter is not prepared")
        if self._server.poll() is not None:
            raise RuntimeError(
                f"managed LightRAG server exited with code {self._server.returncode}"
            )
        return self._config

    def _require_work_dir(self) -> Path:
        if self._work_dir is None:
            raise RuntimeError("adapter work directory is not initialized")
        return self._work_dir


def exception_diagnostic(exc: BaseException) -> str:
    """Return a non-empty diagnostic without discarding the exception type."""

    message = str(exc).strip() or "<no message>"
    return f"{type(exc).__name__}: {message}"


def build_server_environment(
    config: LightRAGAdapterConfig, work_dir: Path
) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        in {
            "PATH",
            "PYTHONPATH",
            "VIRTUAL_ENV",
            "CONDA_PREFIX",
            "SSL_CERT_FILE",
            "REQUESTS_CA_BUNDLE",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "http_proxy",
            "https_proxy",
            "LLM_BINDING",
            "LLM_MODEL",
            "LLM_BINDING_HOST",
            "OLLAMA_HOST",
            "QUERY_LLM_BINDING",
            "QUERY_LLM_MODEL",
            "QUERY_LLM_BINDING_HOST",
            "EMBEDDING_BINDING",
            "EMBEDDING_MODEL",
            "EMBEDDING_BINDING_HOST",
        }
    }
    environment.update(
        {
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
            "LIGHTRAG_DISABLE_EVAL_JOBS": "1",
            "LIGHTRAG_DISABLE_WEBUI": "1",
            "AUTH_ACCOUNTS": "",
            "LIGHTRAG_API_KEY": "",
            "LIGHTRAG_KV_STORAGE": "JsonKVStorage",
            "LIGHTRAG_DOC_STATUS_STORAGE": "JsonDocStatusStorage",
            "LIGHTRAG_GRAPH_STORAGE": "NetworkXStorage",
            "LIGHTRAG_VECTOR_STORAGE": "NanoVectorDBStorage",
            "WORKING_DIR": str(work_dir / "storage"),
            "INPUT_DIR": str(work_dir / "inputs"),
            "CHUNK_SIZE": str(config.chunking.chunk_token_size),
            "CHUNK_OVERLAP_SIZE": str(config.chunking.chunk_overlap_token_size),
            "LIGHTRAG_PARSER": "*:native-!",
            "ENABLE_LLM_CACHE": "0",
            "ENABLE_LLM_CACHE_FOR_EXTRACT": "0",
            "LIGHTRAG_EXACT_ID_TYPES": ",".join(
                value.upper() for value in config.exact_id_types
            ),
            "LIGHTRAG_RANKING_STRATEGY": config.ranking_strategy,
            "LIGHTRAG_TABLE_PRECEDING_CONTEXT": bool_env(
                config.table_preceding_context
            ),
            "LIGHTRAG_TABLE_STRUCTURED_ENVELOPE": bool_env(
                config.table_structured_envelope
            ),
            "LIGHTRAG_TABLE_VIEW": bool_env(config.table_view),
            "LIGHTRAG_TABLE_ROW_VIEW": bool_env(config.table_row_view),
            "ENTITY_EXTRACTION_INSTRUCTION_PROFILE": config.entity_extraction_instruction_profile,
            "RERANK_BY_DEFAULT": bool_env(config.enable_rerank),
            "RERANK_BINDING": "cohere" if config.enable_rerank else "null",
            "RERANK_MODEL": config.rerank_model or "",
            "OLLAMA_LLM_NUM_CTX": str(config.model.llm_num_ctx),
            "QUERY_OLLAMA_LLM_NUM_CTX": str(config.model.llm_num_ctx),
        }
    )
    apply_model_environment(environment, config.model)
    apply_generation_environment(environment, config)
    return environment


def redact_runtime_endpoints_in_log(path: Path, values: Iterable[str]) -> None:
    """Remove launch-only endpoint values before a worker log persists with a run."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for value in sorted(set(values), key=len, reverse=True):
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        text = text.replace(value, f"[redacted endpoint sha256:{digest}]")
    path.write_text(text, encoding="utf-8")


def redact_runtime_endpoints_in_logs(directory: Path, values: Iterable[str]) -> None:
    for path in directory.glob("*.log"):
        redact_runtime_endpoints_in_log(path, values)


def ingestion_identity(config: LightRAGAdapterConfig) -> dict[str, Any]:
    return {
        "process_options": "!",
        "chunking": config.chunking.model_dump(mode="json"),
        "profile": config.profile,
        "ranking_strategy": config.ranking_strategy,
        "exact_id_types": config.exact_id_types,
        "table_preceding_context": config.table_preceding_context,
        "table_structured_envelope": config.table_structured_envelope,
        "table_view": config.table_view,
        "table_row_view": config.table_row_view,
        "entity_extraction_instruction_profile": config.entity_extraction_instruction_profile,
        "embedding_binding": config.model.embedding_binding
        or os.getenv("EMBEDDING_BINDING"),
        "embedding_model": config.model.embedding_model or os.getenv("EMBEDDING_MODEL"),
        "embedding_host": config.model.embedding_host
        or os.getenv("EMBEDDING_BINDING_HOST")
        or os.getenv("OLLAMA_HOST"),
        "system_version": system_version(),
    }


def safe_runtime_identity(environment: dict[str, str]) -> dict[str, str | None]:
    return {
        name.lower(): environment.get(name)
        for name in (
            "LLM_BINDING",
            "LLM_MODEL",
            "QUERY_LLM_BINDING",
            "QUERY_LLM_MODEL",
            "QUERY_LLM_BINDING_HOST",
            "EMBEDDING_BINDING",
            "EMBEDDING_MODEL",
            "EMBEDDING_BINDING_HOST",
            "LLM_BINDING_HOST",
            "OLLAMA_HOST",
        )
    }


async def ollama_model_artifacts(
    identity: dict[str, str | None],
) -> dict[str, dict[str, Any]]:
    roles = {
        "llm": (
            identity.get("query_llm_binding") or identity.get("llm_binding"),
            identity.get("query_llm_model") or identity.get("llm_model"),
            identity.get("query_llm_binding_host")
            or identity.get("llm_binding_host")
            or identity.get("ollama_host")
            or "http://127.0.0.1:11434",
        ),
        "embedding": (
            identity.get("embedding_binding"),
            identity.get("embedding_model"),
            identity.get("embedding_binding_host")
            or identity.get("ollama_host")
            or "http://127.0.0.1:11434",
        ),
    }
    results: dict[str, dict[str, Any]] = {}
    for role, (binding, model, host) in roles.items():
        if not model:
            continue
        digest = None
        if str(binding or "").lower() == "ollama":
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{str(host).rstrip('/')}/api/tags")
                    response.raise_for_status()
                    digest = exact_ollama_model_digest(
                        response.json().get("models", []), str(model)
                    )
            except (httpx.HTTPError, AttributeError, ValueError):
                digest = None
        resolved = normalize_ollama_digest(digest)
        results[role] = {
            "display_name": str(model).split(":", 1)[0],
            "requested_ref": str(model),
            "resolved_digest": resolved,
            "revision": None,
            "resolver": str(binding or "unknown"),
            "resolved_at": datetime.now(UTC).isoformat(),
            "verified": resolved is not None,
        }
    return results


def model_digests(artifacts: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {
        role: str(value.get("resolved_digest") or identity_digest(
            str(value.get("resolver")), str(value.get("requested_ref"))
        ))
        for role, value in artifacts.items()
    }


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


def apply_model_environment(environment: dict[str, str], model: ModelConfig) -> None:
    values = {
        "LLM_BINDING": model.llm_binding,
        "LLM_MODEL": model.llm_model,
        "LLM_BINDING_HOST": model.llm_host,
        "QUERY_LLM_BINDING": model.query_llm_binding,
        "QUERY_LLM_MODEL": model.query_llm_model,
        "QUERY_LLM_BINDING_HOST": model.query_llm_host,
        "EMBEDDING_BINDING": model.embedding_binding,
        "EMBEDDING_MODEL": model.embedding_model,
        "EMBEDDING_BINDING_HOST": model.embedding_host,
    }
    environment.update({key: value for key, value in values.items() if value is not None})


def apply_generation_environment(
    environment: dict[str, str], config: LightRAGAdapterConfig
) -> None:
    generation = config.generation
    binding = config.model.query_llm_binding or config.model.llm_binding or environment.get(
        "QUERY_LLM_BINDING"
    ) or environment.get("LLM_BINDING")
    if str(binding or "").lower() != "ollama":
        return
    if generation.temperature is not None:
        environment["OLLAMA_LLM_TEMPERATURE"] = str(generation.temperature)
    if generation.seed is not None:
        environment["OLLAMA_LLM_SEED"] = str(generation.seed)


def generation_payload(
    config: LightRAGAdapterConfig, requested: dict[str, Any]
) -> dict[str, Any]:
    allowed = {"user_prompt", "response_type", "temperature", "seed"}
    unknown = sorted(set(requested).difference(allowed))
    if unknown:
        raise ValueError(f"unsupported LightRAG generation options: {unknown}")
    payload: dict[str, Any] = {}
    for key in ("user_prompt", "response_type"):
        value = requested.get(key, getattr(config.generation, key))
        if value is not None:
            payload[key] = value
    for key in ("temperature", "seed"):
        value = requested.get(key)
        configured = getattr(config.generation, key)
        if value is not None and value != configured:
            raise ValueError(
                f"{key} must be fixed during prepare; request-level override is not supported"
            )
    return payload


def directory_digest(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return "sha256:" + digest.hexdigest()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def code_identity() -> dict[str, dict[str, str | None]]:
    return {
        "adapter": package_source_identity("rag_eval_lightrag_adapter"),
        "lightrag": package_source_identity("lightrag"),
    }


def package_source_identity(package: str) -> dict[str, str | None]:
    spec = importlib.util.find_spec(package)
    root = Path(spec.origin).parent if spec and spec.origin else None
    git_root = find_git_root(root) if root else None
    return {
        "package_version": distribution_version_or_none(package),
        "git_commit": git_output(git_root, ["rev-parse", "HEAD"]) if git_root else None,
        "dirty_patch_digest": dirty_digest(git_root),
        "direct_url": direct_url(package),
    }


def find_git_root(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def git_output(root: Path, arguments: list[str]) -> str | None:
    result = subprocess.run(["git", "-C", str(root), *arguments], capture_output=True, text=True, check=False)
    return result.stdout.strip() or None if result.returncode == 0 else None


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


def safe_source_name(index: int, document_id: str) -> str:
    suffix = hashlib.sha256(document_id.encode()).hexdigest()[:12]
    return f"source-{index:05d}-{suffix}.txt"


def bool_env(value: bool) -> str:
    return "1" if value else "0"


def reserve_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def system_version() -> str:
    for distribution in ("lightrag-hku", "lightrag"):
        try:
            return importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            continue
    return "unknown"


def create_worker_definition() -> WorkerDefinition:
    return WorkerDefinition(
        adapter=LightRAGAdapter(),
        handshake=HandshakeResponse(
            adapter_id="lightrag",
            adapter_version=ADAPTER_VERSION,
            system_id="lightrag",
            system_version=system_version(),
            capabilities=CAPABILITIES,
        ),
    )
