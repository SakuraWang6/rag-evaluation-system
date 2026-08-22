"""System-neutral adapter models and the worker-internal Python protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from rag_eval.contracts.dataset import EvidenceLocator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdapterCapabilities(ContractModel):
    answer: bool = False
    raw_retrieval: bool = False
    ranked_retrieval: bool = False
    final_context: bool = False
    object_provenance: bool = False
    prompt_trace: bool = False
    rerank_trace: bool = False
    latency_breakdown: bool = False
    token_usage: bool = False
    reset: bool = False


class PrepareContext(ContractModel):
    run_id: str = Field(min_length=1)
    work_dir: str = Field(min_length=1)
    source_dir: str = Field(min_length=1)
    platform_version: str = Field(min_length=1)


class PreparedSystem(ContractModel):
    effective_config: dict[str, Any]
    capabilities: AdapterCapabilities
    system_version: str = Field(min_length=1)


class HealthReport(ContractModel):
    status: str
    ready: bool
    details: dict[str, Any] = Field(default_factory=dict)


class DocumentInput(ContractModel):
    document_id: str = Field(min_length=1)
    content: str
    mime_type: str = "text/plain"
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestionResult(ContractModel):
    ingested_documents: int = Field(ge=0)
    failed_documents: int = Field(default=0, ge=0)
    index_fingerprint: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class RAGEvidenceItem(ContractModel):
    item_id: str = Field(min_length=1)
    rank: int = Field(ge=1)
    content: str
    document_id: str | None = None
    locator: EvidenceLocator | None = None
    score: float | None = None
    token_count: int | None = Field(default=None, ge=0)
    native_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGQuery(ContractModel):
    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    generate_answer: bool = True
    retrieval_candidate_k: int | None = Field(default=None, ge=1)
    final_context_k: int | None = Field(default=None, ge=1)
    max_context_tokens: int | None = Field(default=None, ge=1)
    generation_options: dict[str, Any] = Field(default_factory=dict)


class RAGResult(ContractModel):
    answer: str | None = None
    raw_retrieval: list[RAGEvidenceItem] | None = None
    ranked_retrieval: list[RAGEvidenceItem] | None = None
    final_context: list[RAGEvidenceItem] | None = None
    latency: dict[str, float] | None = None
    token_usage: dict[str, int] | None = None
    trace: dict[str, Any] | None = None
    native_metadata: dict[str, Any] = Field(default_factory=dict)


class ResetResult(ContractModel):
    supported: bool
    reset: bool
    details: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class RAGAdapter(Protocol):
    async def prepare(
        self, context: PrepareContext, config: dict[str, Any]
    ) -> PreparedSystem: ...

    async def health(self) -> HealthReport: ...

    async def ingest(self, documents: list[DocumentInput]) -> IngestionResult: ...

    async def query(self, request: RAGQuery) -> RAGResult: ...

    async def reset(self) -> ResetResult: ...

    async def close(self) -> None: ...
