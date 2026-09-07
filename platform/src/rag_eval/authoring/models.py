"""Persistent models for one-private-DOCX authoring workspaces."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AuthoringModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthoringState(StrEnum):
    UPLOADED = "uploaded"
    ANALYZED = "analyzed"
    TARGETS_READY = "targets_ready"
    CANDIDATES_READY = "candidates_ready"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    EXPORTED = "exported"
    REGISTERED = "registered"
    FORMAL_RELEASED = "formal_released"
    FAILED = "failed"
    BLOCKED = "blocked"
    DELETED = "deleted"
    ARCHIVED = "archived"
    INTERRUPTED = "interrupted"


class SourceManifest(AuthoringModel):
    original_filename: str = Field(min_length=1)
    mime_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=1)
    ingested_at: datetime
    parser_identity: str = Field(min_length=1)
    canonicalizer_identity: str = Field(min_length=1)
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_inventory: dict[str, Any] = Field(default_factory=dict)


class AuthoringDataset(AuthoringModel):
    authoring_dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    state: AuthoringState
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    source: SourceManifest
    document_id: str | None = None
    canonical_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    canonical_contract_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    analysis: dict[str, Any] = Field(default_factory=dict)
    failure: str | None = None
    # This remains an internal trace of the creation flow.  Product users work
    # with the immutable formal release, not with this workspace record.
    formal_release_ids: list[str] = Field(default_factory=list)


class CanonicalView(AuthoringModel):
    document_id: str
    source_sha256: str
    canonical_digest: str
    execution_markdown: str
    evidence_records_path: str
    object_records_path: str
    summary_path: str
    diagnostics_path: str
    canonical_contract_schema_version: str | None = None
    canonical_contract_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    canonical_contract_manifest_path: str | None = None
    canonical_contract_objects_path: str | None = None
    canonical_contract_relations_path: str | None = None


class CandidateState(StrEnum):
    DRAFT = "draft"
    ANSWER_RESOLVED = "answer_resolved"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class GateStatus(StrEnum):
    PASS = "PASS"
    FLAG = "FLAG"
    FAIL = "FAIL"


class EvidenceRepresentabilityStatus(StrEnum):
    FULL = "FULL"
    PARTIAL_UNOBSERVABLE = "PARTIAL_UNOBSERVABLE"
    UNOBSERVABLE = "UNOBSERVABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class RuntimeEvidenceCoverage(AuthoringModel):
    runtime_chunk_id: str = Field(min_length=1)
    coverage: Literal["full", "partial"]
    overlap_span: dict[str, int]


class EvidenceRepresentabilityProfile(AuthoringModel):
    """Gold-independent runtime coverage projected into Authoring diagnostics."""

    profile_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    system_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    execution_view: Literal["canonical-text"] = "canonical-text"
    execution_profile_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance_map_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_id: str = Field(min_length=1)
    runtime_chunk_count: int = Field(ge=1)
    runtime_status_counts: dict[str, int] = Field(default_factory=dict)
    object_to_runtime_chunks: dict[str, list[RuntimeEvidenceCoverage]] = Field(
        default_factory=dict
    )


class DiscoveryMethod(StrEnum):
    RULE = "rule"
    OLLAMA = "ollama"
    REMOTE = "remote"
    MANUAL = "manual"


class BenchmarkTargetCandidate(AuthoringModel):
    target_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    capability: str = Field(min_length=1)
    source_object_ids: list[str] = Field(min_length=1)
    retrieval_route: list[str] = Field(min_length=1)
    distractor_object_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    discovery_method: DiscoveryMethod
    flags: list[str] = Field(default_factory=list)
    rationale: str = ""


class CandidateEvidence(AuthoringModel):
    source_object_id: str = Field(min_length=1)
    required_group: str = Field(default="group-1", min_length=1)
    near_miss_object_ids: list[str] = Field(default_factory=list)


class AnswerEvidenceCandidate(AuthoringModel):
    answer_kind: Literal["text", "numeric", "formula", "set", "abstain"]
    canonical_answer: str | list[str] | None = None
    accepted_values: list[str] = Field(default_factory=list)
    locale: str | None = None
    unit: str | None = None
    tolerance: Decimal | None = Field(default=None, ge=0)
    evidence: list[CandidateEvidence] = Field(default_factory=list)
    dependency_graph: list[dict[str, Any]] = Field(default_factory=list)
    negative_scope_object_ids: list[str] = Field(default_factory=list)
    negative_rationale: str | None = None
    resolution_method: DiscoveryMethod = DiscoveryMethod.MANUAL
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class QualityGateResult(AuthoringModel):
    gate_id: str
    status: GateStatus
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class QuestionCandidate(AuthoringModel):
    candidate_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    target_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    version: int = Field(default=1, ge=1)
    state: CandidateState = CandidateState.DRAFT
    question: str = Field(min_length=1)
    language: str = "zh-CN"
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_object_ids: list[str] = Field(min_length=1)
    generation_method: DiscoveryMethod
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    answer_evidence: AnswerEvidenceCandidate | None = None
    gates: list[QualityGateResult] = Field(default_factory=list)


class GenerationJobItemState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerationJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerationJobItem(AuthoringModel):
    target_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    state: GenerationJobItemState = GenerationJobItemState.PENDING
    attempts: int = Field(default=0, ge=0)
    candidate_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    error_code: str | None = None
    error_detail: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AuthoringGenerationJob(AuthoringModel):
    job_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    authoring_dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    provider: DiscoveryMethod = DiscoveryMethod.OLLAMA
    seed: int = 0
    remote_consent: bool = False
    state: GenerationJobStatus = GenerationJobStatus.QUEUED
    items: list[GenerationJobItem] = Field(min_length=1)
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancel_requested: bool = False


class DiscoveryJobStatus(StrEnum):
    """Lifecycle of a durable target-discovery request."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DiscoveryJobPhase(StrEnum):
    """Human-readable checkpoints persisted while target discovery runs."""

    QUEUED = "queued"
    BUILDING_RULE_TARGETS = "building_rule_targets"
    AWAITING_MODEL = "awaiting_model"
    SAVING_RESULTS = "saving_results"
    COMPLETED = "completed"
    FAILED = "failed"


class AuthoringDiscoveryJob(AuthoringModel):
    """One background target-discovery operation that survives UI reconnects."""

    job_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    authoring_dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    provider: DiscoveryMethod = DiscoveryMethod.OLLAMA
    seed: int = 0
    remote_consent: bool = False
    state: DiscoveryJobStatus = DiscoveryJobStatus.QUEUED
    phase: DiscoveryJobPhase = DiscoveryJobPhase.QUEUED
    phase_detail: str = "任务已排队"
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_source_records: int = Field(default=0, ge=0)
    model_source_records: int = Field(default=0, ge=0)
    rule_target_count: int = Field(default=0, ge=0)
    target_count: int = Field(default=0, ge=0)
    error_code: str | None = None
    error_detail: str | None = None


class ReviewRecord(AuthoringModel):
    review_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    candidate_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    candidate_version: int = Field(ge=1)
    decision: Literal["accept", "edit", "reject"]
    reviewer: str = Field(min_length=1)
    note: str = ""
    edited_fields: list[str] = Field(default_factory=list)
    created_at: datetime


class ApprovedCase(AuthoringModel):
    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    candidate_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    candidate_version: int = Field(ge=1)
    approved_at: datetime
    approved_by: str
    candidate: QuestionCandidate


class AuthoringExport(AuthoringModel):
    release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_case_ids: list[str] = Field(min_length=1)
    views: dict[str, str] = Field(default_factory=dict)
    blocked_cases: list[dict[str, Any]] = Field(default_factory=list)
    registered_bundle_ids: dict[str, str] = Field(default_factory=dict)
    ledger_release_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
