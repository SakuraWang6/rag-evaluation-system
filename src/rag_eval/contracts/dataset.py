"""Dataset Bundle 2.0 schema."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GoldAnswerKind(StrEnum):
    TEXT = "text"
    NUMERIC = "numeric"
    FORMULA = "formula"
    SET = "set"
    ABSTAIN = "abstain"


class TextSpanLocator(ContractModel):
    type: Literal["text_span"] = "text_span"
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_span(self) -> TextSpanLocator:
        if self.end <= self.start:
            raise ValueError("text span end must be greater than start")
        return self


class ObjectLocator(ContractModel):
    type: Literal["object"] = "object"
    object_type: str = Field(min_length=1)
    object_id: str = Field(min_length=1)


class TableCellLocator(ContractModel):
    type: Literal["table_cell"] = "table_cell"
    table_id: str = Field(min_length=1)
    row: int | str
    column: int | str


class PageRegionLocator(ContractModel):
    type: Literal["page_region"] = "page_region"
    page: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float

    @model_validator(mode="after")
    def validate_region(self) -> PageRegionLocator:
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("page region must have positive width and height")
        return self


EvidenceLocator = Annotated[
    TextSpanLocator | ObjectLocator | TableCellLocator | PageRegionLocator,
    Field(discriminator="type"),
]


class DocumentManifest(ContractModel):
    document_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    canonical_path: str | None = None
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mime_type: str = "text/plain"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Question(ContractModel):
    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    gold_answer_id: str = Field(min_length=1)
    gold_evidence_set_id: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GoldAnswer(ContractModel):
    gold_answer_id: str = Field(min_length=1)
    kind: GoldAnswerKind
    canonical: str | list[str] | None = None
    accepted_values: list[str] = Field(default_factory=list)
    locale: str | None = None
    unit: str | None = None
    tolerance: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_answer(self) -> GoldAnswer:
        if self.kind == GoldAnswerKind.ABSTAIN:
            return self
        if self.canonical in (None, "", []):
            raise ValueError("non-abstain gold answer requires a canonical value")
        if self.kind != GoldAnswerKind.NUMERIC and self.tolerance is not None:
            raise ValueError("tolerance is valid only for numeric answers")
        return self


class GoldEvidence(ContractModel):
    evidence_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    locator: EvidenceLocator
    canonical_value: str | None = None
    quote_anchor: str | None = None

    @model_validator(mode="after")
    def validate_witness(self) -> GoldEvidence:
        if not self.canonical_value and not self.quote_anchor:
            raise ValueError("gold evidence requires canonical_value or quote_anchor")
        return self


class GoldEvidenceSet(ContractModel):
    gold_evidence_set_id: str = Field(min_length=1)
    evidence: list[GoldEvidence]
    required_groups: list[list[str]]

    @model_validator(mode="after")
    def validate_groups(self) -> GoldEvidenceSet:
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence IDs must be unique within a set")
        known = set(evidence_ids)
        if not self.required_groups or any(not group for group in self.required_groups):
            raise ValueError("required_groups must contain non-empty groups")
        unknown = {
            evidence_id
            for group in self.required_groups
            for evidence_id in group
            if evidence_id not in known
        }
        if unknown:
            raise ValueError(f"required_groups reference unknown evidence: {sorted(unknown)}")
        return self


class DatasetBundleManifest(ContractModel):
    schema_version: Literal[2] = 2
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    created_at: datetime
    documents: list[DocumentManifest]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_documents(self) -> DatasetBundleManifest:
        ids = [document.document_id for document in self.documents]
        paths = [document.path for document in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("document IDs must be unique")
        if len(paths) != len(set(paths)):
            raise ValueError("document paths must be unique")
        all_paths = paths + [
            document.canonical_path
            for document in self.documents
            if document.canonical_path is not None
        ]
        if any(path.startswith("/") or ".." in path.split("/") for path in all_paths):
            raise ValueError("document paths must be safe relative paths")
        return self
