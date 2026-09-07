"""System-neutral adapter models and the worker-internal Python protocol."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    # Segment-native traces are additive. Legacy adapters may retain the
    # pre-existing evidence-item fields while vNext benchmark adapters expose
    # an auditable stage result for every retrieval boundary.
    segment_traces: bool = False
    strict_segment_ranking: bool = False


class PrepareContext(ContractModel):
    run_id: str = Field(min_length=1)
    work_dir: str = Field(min_length=1)
    source_dir: str = Field(min_length=1)
    platform_version: str = Field(min_length=1)
    seed: int = 0
    repetition: int = Field(default=1, ge=1)


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
    content: str | None = None
    source_path: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    mime_type: str = "text/plain"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source(self) -> DocumentInput:
        if self.content is None and self.source_path is None:
            raise ValueError("document input requires inline text or a source-only path")
        if self.source_path is not None:
            parts = self.source_path.replace("\\", "/").split("/")
            if (
                self.source_path.startswith(("/", "\\"))
                or ":" in parts[0]
                or any(part in {"", ".", ".."} for part in parts)
            ):
                raise ValueError("source_path must be a safe relative path")
        return self


class IngestionResult(ContractModel):
    ingested_documents: int = Field(ge=0)
    failed_documents: int = Field(default=0, ge=0)
    index_fingerprint: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SegmentTraceStatus(StrEnum):
    """Observation state for one retrieval boundary in a benchmark query."""

    OBSERVED = "observed"
    UNSUPPORTED_STAGE = "unsupported_stage"
    RUNTIME_ERROR = "runtime_error"
    MAPPING_CORRUPTED = "mapping_corrupted"


class SegmentTraceItem(ContractModel):
    """A native retrieval item with an adapter-auditable segment relation."""

    native_chunk_id: str = Field(min_length=1)
    rank: int = Field(ge=1)
    content: str = ""
    score: float | None = None
    source_segment_ids: tuple[str, ...] = Field(min_length=1)
    mapping_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_segment_mapping(self) -> "SegmentTraceItem":
        if len(set(self.source_segment_ids)) != len(self.source_segment_ids):
            raise ValueError("segment trace item repeats source segment IDs")
        return self

    @property
    def strictly_rankable(self) -> bool:
        """Whether this item can participate in strict cross-system Recall@K."""

        return len(self.source_segment_ids) == 1


class SegmentTraceStage(ContractModel):
    """One of raw, ranked, or final-context retrieval observations."""

    stage: Literal["raw", "ranked", "context"]
    status: SegmentTraceStatus
    items: tuple[SegmentTraceItem, ...] = ()
    mapping_manifest_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    reason: str | None = None

    @model_validator(mode="after")
    def validate_stage(self) -> "SegmentTraceStage":
        if self.status == SegmentTraceStatus.OBSERVED:
            if self.mapping_manifest_digest is None:
                raise ValueError("observed segment trace requires a mapping manifest digest")
            ranks = [item.rank for item in self.items]
            if len(ranks) != len(set(ranks)):
                raise ValueError("observed segment trace repeats ranks")
        elif self.items:
            raise ValueError("non-observed segment trace cannot claim scoreable items")
        if self.status != SegmentTraceStatus.OBSERVED and not (self.reason or "").strip():
            raise ValueError("non-observed segment trace requires a reason")
        return self


class SegmentTraceSet(ContractModel):
    """The full stage set returned for one query under the vNext contract."""

    raw: SegmentTraceStage
    ranked: SegmentTraceStage
    context: SegmentTraceStage

    @model_validator(mode="after")
    def validate_stage_names(self) -> "SegmentTraceSet":
        expected = {"raw": self.raw, "ranked": self.ranked, "context": self.context}
        if any(stage.stage != name for name, stage in expected.items()):
            raise ValueError("segment trace keys and stage names must agree")
        return self


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
    segment_traces: SegmentTraceSet | None = None


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
