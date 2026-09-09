"""Direct Native v2 Adapter contract.

The contract intentionally models one original DOCX and one run-scoped native
RAG instance.  Ingestion is part of ``prepare``; there is no independently
callable corpus upload operation and no legacy result envelope.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)

from rag_eval.contracts.observation import (
    AdapterRunResultV2,
    ObservationProfileIdentity,
    RuntimeProfileIdentity,
    SourceIdentity,
)

NATIVE_ADAPTER_PROTOCOL_VERSION = "2.0"
DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


class NativeContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _safe_relative_path(value: str, *, field_name: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise ValueError(f"{field_name} must be a safe relative path")
    return value


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class OriginalDocumentV2(NativeContractModel):
    """The sole native ingestion input staged in the Worker source sandbox."""

    schema_version: Literal["2.0"] = NATIVE_ADAPTER_PROTOCOL_VERSION
    document_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: Literal[
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ] = DOCX_MEDIA_TYPE
    original_name: str = Field(min_length=1)
    canonical_catalog_path: str = Field(min_length=1)
    canonical_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_paths(self) -> OriginalDocumentV2:
        _safe_relative_path(self.source_path, field_name="source_path")
        _safe_relative_path(
            self.canonical_catalog_path,
            field_name="canonical_catalog_path",
        )
        if PurePosixPath(self.source_path).suffix.lower() != ".docx":
            raise ValueError("Native v2 accepts only an original DOCX")
        if PurePosixPath(self.original_name).name != self.original_name:
            raise ValueError("original_name must not contain a path")
        return self


class ResolvedAdapterConfigV2(NativeContractModel):
    """Run-scoped, path-resolved Adapter configuration supplied at prepare."""

    schema_version: Literal["2.0"] = NATIVE_ADAPTER_PROTOCOL_VERSION
    run_id: str = Field(min_length=1)
    work_dir: str = Field(min_length=1)
    source_dir: str = Field(min_length=1)
    platform_version: str = Field(min_length=1)
    seed: StrictInt
    repetition: StrictInt = Field(ge=1)
    adapter_config: dict[str, Any]
    adapter_config_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_config_digest(self) -> ResolvedAdapterConfigV2:
        if "evaluation_corpus" in self.adapter_config:
            raise ValueError(
                "Direct Wire 2.0 does not accept a corpus-route selector"
            )
        if self.adapter_config_digest != _digest(self.adapter_config):
            raise ValueError("adapter_config_digest does not match adapter_config")
        return self


class IngestionReceiptV2(NativeContractModel):
    """Content-addressed proof that prepare indexed the declared DOCX once."""

    schema_version: Literal["2.0"] = NATIVE_ADAPTER_PROTOCOL_VERSION
    document_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ingested_documents: Literal[1] = 1
    failed_documents: Literal[0] = 0
    index_fingerprint: str = Field(min_length=1)
    index_artifact_digest: str | None = Field(
        default=None,
        pattern=r"^(sha256:)?[0-9a-f]{64}$",
    )
    details: dict[str, Any] = Field(default_factory=dict)
    receipt_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_receipt(self) -> IngestionReceiptV2:
        payload = self.model_dump(
            mode="json",
            exclude={"receipt_digest"},
            exclude_none=True,
        )
        if self.receipt_digest != _digest(payload):
            raise ValueError("ingestion receipt digest does not match its payload")
        return self

    @classmethod
    def build(
        cls,
        *,
        document_id: str,
        source_sha256: str,
        index_fingerprint: str,
        index_artifact_digest: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> IngestionReceiptV2:
        payload = {
            "schema_version": NATIVE_ADAPTER_PROTOCOL_VERSION,
            "document_id": document_id,
            "source_sha256": source_sha256,
            "ingested_documents": 1,
            "failed_documents": 0,
            "index_fingerprint": index_fingerprint,
            "details": dict(details or {}),
        }
        if index_artifact_digest is not None:
            payload["index_artifact_digest"] = index_artifact_digest
        return cls(**payload, receipt_digest=_digest(payload))


class PreparedSystemV2(NativeContractModel):
    """Immutable handle and identities for one successfully ingested system."""

    protocol_version: Literal["2.0"] = NATIVE_ADAPTER_PROTOCOL_VERSION
    prepared_system_id: str = Field(pattern=r"^prepared:sha256:[0-9a-f]{64}$")
    effective_config: dict[str, Any]
    source_identity: SourceIdentity
    runtime_profile: RuntimeProfileIdentity
    observation_profile: ObservationProfileIdentity
    ingestion_receipt: IngestionReceiptV2

    @model_validator(mode="after")
    def validate_prepared_system(self) -> PreparedSystemV2:
        if (
            self.source_identity.document_id != self.ingestion_receipt.document_id
            or self.source_identity.source_sha256
            != self.ingestion_receipt.source_sha256
        ):
            raise ValueError("prepared source identity differs from ingestion receipt")
        payload = self.model_dump(
            mode="json",
            exclude={"prepared_system_id"},
            exclude_none=True,
        )
        if self.prepared_system_id != f"prepared:{_digest(payload)}":
            raise ValueError("prepared_system_id does not match prepared identities")
        return self

    @classmethod
    def build(
        cls,
        *,
        effective_config: dict[str, Any],
        source_identity: SourceIdentity,
        runtime_profile: RuntimeProfileIdentity,
        observation_profile: ObservationProfileIdentity,
        ingestion_receipt: IngestionReceiptV2,
    ) -> PreparedSystemV2:
        payload = {
            "protocol_version": NATIVE_ADAPTER_PROTOCOL_VERSION,
            "effective_config": effective_config,
            "source_identity": source_identity,
            "runtime_profile": runtime_profile,
            "observation_profile": observation_profile,
            "ingestion_receipt": ingestion_receipt,
        }
        serialized = {
            key: (
                value.model_dump(mode="json", exclude_none=True)
                if isinstance(value, BaseModel)
                else value
            )
            for key, value in payload.items()
        }
        return cls(
            **payload,
            prepared_system_id=f"prepared:{_digest(serialized)}",
        )


class NativeQueryV2(NativeContractModel):
    schema_version: Literal["2.0"] = NATIVE_ADAPTER_PROTOCOL_VERSION
    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    generate_answer: StrictBool
    retrieval_candidate_k: StrictInt = Field(ge=1)
    final_context_k: StrictInt = Field(ge=1)
    max_context_tokens: StrictInt = Field(ge=1)
    generation_options: dict[str, Any]

    @model_validator(mode="after")
    def validate_cutoffs(self) -> NativeQueryV2:
        if self.final_context_k > self.retrieval_candidate_k:
            raise ValueError(
                "final_context_k cannot exceed retrieval_candidate_k"
            )
        return self


class NativeHealthReportV2(NativeContractModel):
    status: str = Field(min_length=1)
    ready: StrictBool
    details: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class NativeRAGAdapterV2(Protocol):
    async def prepare(
        self,
        original_docx: OriginalDocumentV2,
        resolved_config: ResolvedAdapterConfigV2,
    ) -> PreparedSystemV2: ...

    async def query(
        self,
        prepared_system: PreparedSystemV2,
        request: NativeQueryV2,
    ) -> AdapterRunResultV2: ...

    async def health(self) -> NativeHealthReportV2: ...

    async def close(self) -> None: ...


__all__ = [
    "DOCX_MEDIA_TYPE",
    "NATIVE_ADAPTER_PROTOCOL_VERSION",
    "IngestionReceiptV2",
    "NativeHealthReportV2",
    "NativeQueryV2",
    "NativeRAGAdapterV2",
    "OriginalDocumentV2",
    "PreparedSystemV2",
    "ResolvedAdapterConfigV2",
]
