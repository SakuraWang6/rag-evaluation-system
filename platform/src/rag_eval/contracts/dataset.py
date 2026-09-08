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
    # Stable Canonical identity used by Wire 2.0 evaluation.  This is an
    # additive field so historical Bundle 2.0 readers remain valid.  New
    # Canonical Benchmark publications pin it explicitly, including for
    # table-cell locators whose human-readable coordinates are not identity.
    canonical_object_id: str | None = Field(default=None, min_length=1)
    canonical_value: str | None = None
    quote_anchor: str | None = None

    @model_validator(mode="after")
    def validate_witness(self) -> GoldEvidence:
        if not (self.canonical_value or "").strip() and not (
            self.quote_anchor or ""
        ).strip():
            raise ValueError("gold evidence requires canonical_value or quote_anchor")
        if (
            isinstance(self.locator, ObjectLocator)
            and self.canonical_object_id is not None
            and self.canonical_object_id != self.locator.object_id
        ):
            raise ValueError(
                "Gold canonical object identity must agree with its object locator"
            )
        return self


class GoldSourceIdentity(ContractModel):
    """Canonical Benchmark source pin required by Unified Evaluation v2."""

    document_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_coordinate_schema: str = Field(min_length=1)
    canonical_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GoldEvidenceSet(ContractModel):
    gold_evidence_set_id: str = Field(min_length=1)
    evidence: list[GoldEvidence]
    required_groups: list[list[str]]
    # Additive for historical Bundle 2.0 compatibility. New formal
    # publications always pin every document; Wire 2.0 scoring fails closed
    # when a required pin is absent.
    source_identities: tuple[GoldSourceIdentity, ...] = ()
    # Formal runtime projections retain the Ledger's exact OR(paths) of
    # AND(clauses) semantics.  ``required_groups`` remains the legacy/default
    # view for existing bundles; evidence IDs may legitimately repeat across
    # alternative paths here.
    mses_paths: list[list[list[str]]] | None = None

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
        flattened = [evidence_id for group in self.required_groups for evidence_id in group]
        if len(flattened) != len(set(flattened)):
            raise ValueError(
                "an evidence ID may occur in only one required group; duplicate "
                "groups distort the recall denominator"
            )
        if self.mses_paths is not None:
            if not self.mses_paths or any(not path or any(not group for group in path) for path in self.mses_paths):
                raise ValueError("mses_paths must contain non-empty paths and clauses")
            unknown_mses = {
                evidence_id
                for path in self.mses_paths
                for group in path
                for evidence_id in group
                if evidence_id not in known
            }
            if unknown_mses:
                raise ValueError(f"mses_paths reference unknown evidence: {sorted(unknown_mses)}")
        source_ids = [item.document_id for item in self.source_identities]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Gold source identities must have unique document IDs")
        if self.source_identities:
            unpinned = {
                item.document_id for item in self.evidence
            }.difference(source_ids)
            if unpinned:
                raise ValueError(
                    f"Gold evidence references unpinned documents: {sorted(unpinned)}"
                )
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
