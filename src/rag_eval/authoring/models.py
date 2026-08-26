"""Persistent models for one-private-DOCX authoring workspaces."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

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
    FAILED = "failed"
    BLOCKED = "blocked"
    DELETED = "deleted"
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
    source: SourceManifest
    document_id: str | None = None
    canonical_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    analysis: dict[str, Any] = Field(default_factory=dict)
    failure: str | None = None


class CanonicalView(AuthoringModel):
    document_id: str
    source_sha256: str
    canonical_digest: str
    execution_markdown: str
    evidence_records_path: str
    object_records_path: str
    summary_path: str
    diagnostics_path: str
