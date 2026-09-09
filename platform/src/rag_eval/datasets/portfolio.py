"""Typed Benchmark Blueprint Portfolio, coverage, and deficit contracts.

This module turns the existing v0 Blueprint artifacts into a Platform-owned
planning contract.  It intentionally models *plans* rather than benchmark
cases: importing a plan never creates a Case, Gold, Bundle, or release.

The source taxonomy is the one frozen in ``BENCHMARK_BLUEPRINT_V0.md`` and
``BENCHMARK_V0_CASE_MATRIX.csv``.  In particular, it is not inferred from
RAG/chunker output and it does not add a second Gold or Authoring schema.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.authoring.ledger import AuthoringLedger, LifecycleState
from rag_eval.storage.atomic import atomic_write_bytes, atomic_write_json
from rag_eval.storage.ids import safe_id

if TYPE_CHECKING:
    from rag_eval.datasets.formal import DatasetReleaseStore


PORTFOLIO_SCHEMA_VERSION = "benchmark-portfolio/1.0"
PORTFOLIO_REPORT_SCHEMA_VERSION = "benchmark-portfolio-report/1.0"
PORTFOLIO_ID_V0_DRY_RUN = "benchmark-v0-dry-run-48"
PORTFOLIO_ID_V0_HELD_OUT = "benchmark-v0-held-out-96"


class PortfolioError(ValueError):
    """A typed Portfolio plan or its Authoring association is invalid."""


class PortfolioModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PortfolioSourceType(StrEnum):
    HUMAN = "human"
    SEMI_SYNTHETIC = "semi_synthetic"
    SYNTHETIC = "synthetic"
    ADVERSARIAL = "adversarial"


class PortfolioUsage(StrEnum):
    DEVELOPMENT = "development"
    HELD_OUT = "held_out"


class PortfolioSlotState(StrEnum):
    PLANNED = "planned"
    AUTHORED = "authored"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    FROZEN = "frozen"
    BLOCKED = "blocked"


class PortfolioBlockedReason(StrEnum):
    """Typed, evidence-based reason a planned slot cannot be actualized."""

    NO_GOLD_ELIGIBLE_EVIDENCE = "no_gold_eligible_evidence"
    UNSUPPORTED_MODALITY = "unsupported_modality"
    INSUFFICIENT_MULTI_HOP_STRUCTURE = "insufficient_multi_hop_structure"
    NO_NATURAL_NEGATIVE_SCOPE = "no_natural_negative_scope"
    NO_VALID_CONFLICT = "no_valid_conflict"
    LANGUAGE_REQUIREMENT_UNAVAILABLE = "language_requirement_unavailable"
    SOURCE_TYPE_NOT_REALIZABLE = "source_type_not_realizable"
    CROSS_DOCUMENT_EVIDENCE_UNAVAILABLE = "cross_document_evidence_unavailable"
    AUTHENTIC_AMBIGUITY_UNAVAILABLE = "authentic_ambiguity_unavailable"
    OTHER_DOCUMENTED = "other_documented_reason"


class BenchmarkLanguage(StrEnum):
    ENGLISH = "en"
    CHINESE = "zh"


class RetrievalDifficulty(StrEnum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


class ReasoningDifficulty(StrEnum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


class RetrievalRoute(StrEnum):
    SINGLE_SEMANTIC = "single_semantic"
    LEXICAL_CONFUSABLE = "lexical_confusable"
    LONG_DISTANCE = "long_distance"
    CROSS_SECTION = "cross_section"
    CROSS_DOCUMENT = "cross_document"
    AUTHORITY_BEARING = "authority_bearing"


class EvidenceComposition(StrEnum):
    SINGLE = "single"
    INDEPENDENT_MULTI = "independent_multi"
    DEPENDENT_CHAIN = "dependent_chain"
    ALTERNATIVE_PATH = "alternative_path"
    CONFLICT_SET = "conflict_set"
    PARTIAL_ONLY = "partial_only"


class ReasoningOperation(StrEnum):
    DIRECT_EXTRACT = "direct_extract"
    COMPARISON = "comparison"
    AGGREGATION = "aggregation"
    TEMPORAL_AUTHORITY = "temporal_authority"
    CONDITIONAL = "conditional"
    RELATION_CHAIN = "relation_chain"


class StructuredContent(StrEnum):
    NONE = "none"
    TABLE_FILTER = "table_filter"
    TABLE_COMPARE_AGGREGATE = "table_compare_aggregate"
    CROSS_TABLE = "cross_table"
    FIGURE_CAPTION_TEXT = "figure_caption_text"
    EQUATION_REFERENCE = "equation_reference"


class Answerability(StrEnum):
    ANSWERABLE = "answerable"
    PARTIALLY_SUPPORTED = "partially_supported"
    AMBIGUOUS = "ambiguous"
    CONFLICTING_RESOLVABLE = "conflicting_resolvable"
    CONFLICTING_UNRESOLVED = "conflicting_unresolved"
    UNANSWERABLE = "unanswerable"
    PLAUSIBLE_UNSUPPORTED = "plausible_unsupported"


class ContextPressure(StrEnum):
    NEAR = "near"
    CROSS_SECTION = "cross_section"
    CROSS_DOCUMENT = "cross_document"
    DENSE_DISTRACTORS = "dense_distractors"
    REPEATED_ENTITY = "repeated_entity"
    STALE_VERSION = "stale_version"
    NEAR_DUPLICATE = "near_duplicate"


class DocumentModality(StrEnum):
    TEXT = "text"
    TABLE_PLUS_TEXT = "table plus text"
    FIGURE_CAPTION_TEXT = "figure plus caption plus text"
    EQUATION_PLUS_TEXT = "equation plus text"
    FIGURE_EQUATION_TEXT = "figure plus equation plus text"
    TEXT_PLUS_RICH_STRUCTURE = "text plus rich structure"


class EvidenceRequirement(StrEnum):
    SINGLE_EVIDENCE = "single_evidence"
    MULTI_EVIDENCE = "multi_evidence"
    MULTI_HOP = "multi_hop"


class CasePolarity(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    ESCALATION = "escalation"


class PlannedOutcome(StrEnum):
    ANSWER = "answer"
    ABSTAIN = "abstain"
    NEEDS_REVIEW = "needs_review"


class SourceFamily(StrEnum):
    """Only a family assignment, never an invented document/source identity."""

    UNASSIGNED = "unassigned"
    FROZEN_REFERENCE_DIAGNOSTIC = "frozen_reference_diagnostic"
    HELD_OUT_ISOLATED_PENDING_ADMISSION = "held_out_isolated_pending_admission"


class TaskArchetype(StrEnum):
    SEMANTIC_SINGLE = "semantic single-evidence retrieval"
    LEXICAL_CONFUSABLE = "lexically confusable entity or attribute retrieval"
    LONG_DISTANCE = "long-distance or cross-document single evidence"
    INDEPENDENT_MULTI = "independent multi-evidence synthesis"
    DEPENDENT_MULTI_HOP = "dependent multi-hop relation chain"
    COMPARISON = "comparison under evidence competition"
    AGGREGATION = "aggregation with complete evidence retrieval"
    TEMPORAL_AUTHORITY = "temporal version and authority resolution"
    CONDITIONAL = "conditional reasoning with retrieved prerequisites"
    TABLE_FILTER = "table row filtering with header interpretation"
    TABLE_COMPARISON = "table comparison aggregation or cross-table reasoning"
    FIGURE_RELATION = "figure caption text relation"
    EQUATION_RELATION = "equation reference relation"
    DIRECT_CONTROL = "answerable direct control without cue leakage"
    PARTIAL_SUPPORT = "partial support does not establish target relation"
    AMBIGUOUS = "ambiguous question or evidence needs escalation"
    UNRESOLVED_CONFLICT = "unresolved source conflict needs escalation"
    TARGET_ABSENT = "target attribute absent despite related evidence"
    PLAUSIBLE_UNSUPPORTED = "plausible world-knowledge answer is unsupported"


class PortfolioAxis(StrEnum):
    PRIMARY_TASK = "primary_task"
    SOURCE_TYPE = "source_type"
    LANGUAGE = "language"
    RETRIEVAL_DIFFICULTY = "retrieval_difficulty"
    REASONING_DIFFICULTY = "reasoning_difficulty"
    MODALITY = "modality"
    ANSWERABILITY = "answerability"
    EVIDENCE_REQUIREMENT = "evidence_requirement"
    EVIDENCE_COMPOSITION = "evidence_composition"
    RETRIEVAL_REASONING = "retrieval_reasoning"
    SOURCE_FAMILY = "source_family"
    SLOT_STATE = "slot_state"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sorted_unique(values: tuple[StrEnum, ...]) -> tuple[StrEnum, ...]:
    return tuple(sorted(set(values), key=lambda value: value.value))


class BlueprintArtifact(PortfolioModel):
    name: str = Field(min_length=1)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(ge=1)


class BlueprintMatrixRow(PortfolioModel):
    """One typed row from the unmodified 96-case V0 case matrix."""

    primary_task: TaskArchetype
    retrieval_routes: tuple[RetrievalRoute, ...] = Field(min_length=1)
    evidence_compositions: tuple[EvidenceComposition, ...] = Field(min_length=1)
    reasoning_operations: tuple[ReasoningOperation, ...] = Field(min_length=1)
    structured_content: tuple[StructuredContent, ...] = Field(min_length=1)
    answerabilities: tuple[Answerability, ...] = Field(min_length=1)
    retrieval_difficulties: tuple[RetrievalDifficulty, ...] = Field(min_length=1)
    reasoning_difficulties: tuple[ReasoningDifficulty, ...] = Field(min_length=1)
    modalities: tuple[DocumentModality, ...] = Field(min_length=1)
    evidence_requirement: EvidenceRequirement
    context_pressures: tuple[ContextPressure, ...] = Field(min_length=1)
    source_type_counts: tuple[tuple[PortfolioSourceType, int], ...]
    language_counts: tuple[tuple[BenchmarkLanguage, int], ...]
    target_count: int = Field(ge=1)
    source_row_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _check_totals(self) -> "BlueprintMatrixRow":
        if sum(count for _, count in self.source_type_counts) != self.target_count:
            raise ValueError("matrix source-type counts must equal target count")
        if sum(count for _, count in self.language_counts) != self.target_count:
            raise ValueError("matrix language counts must equal target count")
        return self


class PortfolioSlot(PortfolioModel):
    """One planned slot.  Multiple allowed values preserve CSV alternatives."""

    slot_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    plan_group_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    plan_group_slot_ordinal: int = Field(ge=1)
    source_type: PortfolioSourceType
    usage: PortfolioUsage
    language: BenchmarkLanguage
    primary_tasks: tuple[TaskArchetype, ...] = Field(min_length=1)
    retrieval_routes: tuple[RetrievalRoute, ...] = Field(min_length=1)
    evidence_compositions: tuple[EvidenceComposition, ...] = Field(min_length=1)
    reasoning_operations: tuple[ReasoningOperation, ...] = Field(min_length=1)
    structured_content: tuple[StructuredContent, ...] = Field(min_length=1)
    answerabilities: tuple[Answerability, ...] = Field(min_length=1)
    retrieval_difficulties: tuple[RetrievalDifficulty, ...] = Field(min_length=1)
    reasoning_difficulties: tuple[ReasoningDifficulty, ...] = Field(min_length=1)
    modalities: tuple[DocumentModality, ...] = Field(min_length=1)
    evidence_requirement: EvidenceRequirement
    polarity: CasePolarity
    planned_outcome: PlannedOutcome
    context_pressures: tuple[ContextPressure, ...] = Field(min_length=1)
    source_family: SourceFamily = SourceFamily.UNASSIGNED
    plan_row_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _check_plan_semantics(self) -> "PortfolioSlot":
        if self.usage == PortfolioUsage.HELD_OUT and self.source_family != SourceFamily.HELD_OUT_ISOLATED_PENDING_ADMISSION:
            raise ValueError("held-out Portfolio slots must require an isolated admitted source family")
        if self.usage == PortfolioUsage.DEVELOPMENT and self.source_family == SourceFamily.HELD_OUT_ISOLATED_PENDING_ADMISSION:
            raise ValueError("reserved held-out source-family requirement cannot be used for development slots")
        if self.planned_outcome == PlannedOutcome.ABSTAIN and self.polarity != CasePolarity.NEGATIVE:
            raise ValueError("abstain plan slots must be negative")
        if self.planned_outcome == PlannedOutcome.NEEDS_REVIEW and self.polarity != CasePolarity.ESCALATION:
            raise ValueError("needs_review slots must be escalation slots")
        return self


class PortfolioLinks(PortfolioModel):
    """Typed references to existing formal Authoring and Release entities."""

    dataset_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    document_revision_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    case_revision_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    gold_revision_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    release_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    source_family_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    source_admission_report_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class PortfolioAssignment(PortfolioModel):
    """Append-only actualization state for one planned slot."""

    assignment_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    slot_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    revision: int = Field(ge=1)
    parent_assignment_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    state: PortfolioSlotState
    blocked_reason: PortfolioBlockedReason | None = None
    links: PortfolioLinks
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def _check_links(self) -> "PortfolioAssignment":
        if self.state == PortfolioSlotState.BLOCKED and self.blocked_reason is None:
            raise ValueError("a blocked Portfolio assignment requires a typed blocked_reason")
        if self.state != PortfolioSlotState.BLOCKED and self.blocked_reason is not None:
            raise ValueError("blocked_reason is only valid for a blocked Portfolio assignment")
        if self.state in {PortfolioSlotState.AUTHORED, PortfolioSlotState.REVIEWED, PortfolioSlotState.APPROVED, PortfolioSlotState.FROZEN}:
            if not self.links.dataset_id or not self.links.case_revision_id:
                raise ValueError("an actualized slot must link Dataset and CaseRevision")
        if self.state in {PortfolioSlotState.APPROVED, PortfolioSlotState.FROZEN}:
            if not self.links.document_revision_id or not self.links.gold_revision_id:
                raise ValueError("approved/frozen coverage must link DocumentRevision and GoldRevision")
        if self.state == PortfolioSlotState.FROZEN and not self.links.release_id:
            raise ValueError("frozen coverage must link an immutable Dataset Release")
        return self


class BenchmarkPortfolio(PortfolioModel):
    schema_version: Literal[PORTFOLIO_SCHEMA_VERSION] = PORTFOLIO_SCHEMA_VERSION
    portfolio_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1)
    artifacts: tuple[BlueprintArtifact, ...] = Field(min_length=4)
    matrix: tuple[BlueprintMatrixRow, ...] = Field(min_length=1)
    slots: tuple[PortfolioSlot, ...] = Field(min_length=1)
    contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_digest_and_order(self) -> "BenchmarkPortfolio":
        if tuple(sorted(self.artifacts, key=lambda item: item.name)) != self.artifacts:
            raise ValueError("artifacts must be ordered by name")
        if tuple(sorted(self.matrix, key=lambda item: item.primary_task.value)) != self.matrix:
            raise ValueError("matrix must be ordered by primary task")
        if tuple(sorted(self.slots, key=lambda item: item.slot_id)) != self.slots:
            raise ValueError("slots must be ordered by ID")
        if len({slot.slot_id for slot in self.slots}) != len(self.slots):
            raise ValueError("Portfolio slot IDs must be unique")
        expected = _digest(self._digest_payload())
        if self.contract_digest != expected:
            raise ValueError("Portfolio contract digest does not match content")
        return self

    def _digest_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "portfolio_id": self.portfolio_id,
            "title": self.title,
            "artifacts": [item.model_dump(mode="json") for item in self.artifacts],
            "matrix": [item.model_dump(mode="json") for item in self.matrix],
            "slots": [item.model_dump(mode="json") for item in self.slots],
        }

    @classmethod
    def build(
        cls,
        *,
        portfolio_id: str,
        title: str,
        artifacts: tuple[BlueprintArtifact, ...],
        matrix: tuple[BlueprintMatrixRow, ...],
        slots: tuple[PortfolioSlot, ...],
    ) -> "BenchmarkPortfolio":
        values = {
            "portfolio_id": portfolio_id,
            "title": title,
            "artifacts": tuple(sorted(artifacts, key=lambda item: item.name)),
            "matrix": tuple(sorted(matrix, key=lambda item: item.primary_task.value)),
            "slots": tuple(sorted(slots, key=lambda item: item.slot_id)),
        }
        digest = _digest({"schema_version": PORTFOLIO_SCHEMA_VERSION, **{key: [item.model_dump(mode="json") for item in value] if key in {"artifacts", "matrix", "slots"} else value for key, value in values.items()}})
        return cls(**values, contract_digest=digest)


class CoverageBucket(PortfolioModel):
    axis: PortfolioAxis
    value: str = Field(min_length=1)
    planned: int = Field(ge=0)
    completed: int = Field(ge=0)
    missing: int = Field(ge=0)
    blocked: int = Field(ge=0)
    overrepresented: int = Field(ge=0)


class CoverageDeficit(PortfolioModel):
    axis: PortfolioAxis
    value: str = Field(min_length=1)
    planned: int = Field(ge=0)
    completed: int = Field(ge=0)
    missing: int = Field(ge=0)
    blocked: int = Field(ge=0)
    reason: str = Field(min_length=1)


class FrozenReferenceObservation(PortfolioModel):
    bundle_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_count: int = Field(ge=1)
    usage: PortfolioUsage
    diagnostic_reference: bool
    held_out: bool
    generalization_claim_allowed: bool
    source_family: SourceFamily
    typed_case_axes_available: bool


class PortfolioCoverageReport(PortfolioModel):
    schema_version: Literal[PORTFOLIO_REPORT_SCHEMA_VERSION] = PORTFOLIO_REPORT_SCHEMA_VERSION
    portfolio_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    portfolio_contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_digests: tuple[BlueprintArtifact, ...]
    total_slots: int = Field(ge=0)
    state_counts: tuple[tuple[PortfolioSlotState, int], ...]
    coverage: tuple[CoverageBucket, ...]
    deficits: tuple[CoverageDeficit, ...]
    frozen_reference: FrozenReferenceObservation
    report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_digest(self) -> "PortfolioCoverageReport":
        if tuple(sorted(self.coverage, key=lambda item: (item.axis.value, item.value))) != self.coverage:
            raise ValueError("coverage buckets must be ordered")
        if tuple(sorted(self.deficits, key=lambda item: (item.axis.value, item.value))) != self.deficits:
            raise ValueError("deficits must be ordered")
        expected = _digest(self._digest_payload())
        if self.report_digest != expected:
            raise ValueError("coverage report digest does not match content")
        return self

    def _digest_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "portfolio_id": self.portfolio_id,
            "portfolio_contract_digest": self.portfolio_contract_digest,
            "input_digests": [item.model_dump(mode="json") for item in self.input_digests],
            "total_slots": self.total_slots,
            "state_counts": [(item.value, count) for item, count in self.state_counts],
            "coverage": [item.model_dump(mode="json") for item in self.coverage],
            "deficits": [item.model_dump(mode="json") for item in self.deficits],
            "frozen_reference": self.frozen_reference.model_dump(mode="json"),
        }

    @classmethod
    def build(
        cls,
        *,
        portfolio: BenchmarkPortfolio,
        state_counts: tuple[tuple[PortfolioSlotState, int], ...],
        coverage: tuple[CoverageBucket, ...],
        deficits: tuple[CoverageDeficit, ...],
        frozen_reference: FrozenReferenceObservation,
    ) -> "PortfolioCoverageReport":
        values = {
            "portfolio_id": portfolio.portfolio_id,
            "portfolio_contract_digest": portfolio.contract_digest,
            "input_digests": portfolio.artifacts,
            "total_slots": len(portfolio.slots),
            "state_counts": state_counts,
            "coverage": tuple(sorted(coverage, key=lambda item: (item.axis.value, item.value))),
            "deficits": tuple(sorted(deficits, key=lambda item: (item.axis.value, item.value))),
            "frozen_reference": frozen_reference,
        }
        digest = _digest({"schema_version": PORTFOLIO_REPORT_SCHEMA_VERSION, **{key: [item.model_dump(mode="json") for item in value] if key in {"input_digests", "coverage", "deficits"} else [(item.value, count) for item, count in value] if key == "state_counts" else value.model_dump(mode="json") if key == "frozen_reference" else value for key, value in values.items()}})
        return cls(**values, report_digest=digest)


def _enum_values(value: str, enum_type: type[StrEnum]) -> tuple[StrEnum, ...]:
    """Parse only the ``x or y`` alternatives already present in the matrix."""

    values = [part.strip() for part in value.split(" or ")]
    try:
        return tuple(enum_type(item) for item in values)
    except ValueError as exc:
        raise PortfolioError(f"unsupported Blueprint value {value!r} for {enum_type.__name__}") from exc


def _difficulty_values(value: str, enum_type: type[StrEnum]) -> tuple[StrEnum, ...]:
    normalized = value.replace("/", " or ")
    return _enum_values(normalized, enum_type)


_CONTEXT_PRESSURE_BY_MATRIX_DISTANCE: dict[str, tuple[ContextPressure, ...]] = {
    "near": (ContextPressure.NEAR,),
    "near or cross-section": (ContextPressure.NEAR, ContextPressure.CROSS_SECTION),
    "near with dense competitors": (ContextPressure.NEAR, ContextPressure.DENSE_DISTRACTORS),
    "cross-section or cross-document": (ContextPressure.CROSS_SECTION, ContextPressure.CROSS_DOCUMENT),
    "same or cross-section": (ContextPressure.NEAR, ContextPressure.CROSS_SECTION),
    "cross-section": (ContextPressure.CROSS_SECTION,),
    "cross-document": (ContextPressure.CROSS_DOCUMENT,),
    "cross-section or cross-table": (ContextPressure.CROSS_SECTION,),
    "table block plus header or note": (ContextPressure.NEAR,),
    "near with confusable evidence": (ContextPressure.NEAR, ContextPressure.DENSE_DISTRACTORS),
    "near with related entity evidence": (ContextPressure.NEAR, ContextPressure.REPEATED_ENTITY),
}


_TASKS_BY_DRY_RUN_CONSTRUCT: dict[str, tuple[TaskArchetype, ...]] = {
    "semantic single-evidence retrieval": (TaskArchetype.SEMANTIC_SINGLE,),
    "lexically confusable entity or attribute retrieval": (TaskArchetype.LEXICAL_CONFUSABLE,),
    "long-distance or cross-document single evidence": (TaskArchetype.LONG_DISTANCE,),
    "independent multi-evidence synthesis": (TaskArchetype.INDEPENDENT_MULTI,),
    "dependent multi-hop relation chain": (TaskArchetype.DEPENDENT_MULTI_HOP,),
    "comparison or aggregation": (TaskArchetype.COMPARISON, TaskArchetype.AGGREGATION),
    "table filter plus table comparison or cross-table aggregation": (TaskArchetype.TABLE_FILTER, TaskArchetype.TABLE_COMPARISON),
    "figure-caption relation plus equation-reference relation": (TaskArchetype.FIGURE_RELATION, TaskArchetype.EQUATION_RELATION),
    "temporal version and authority resolution": (TaskArchetype.TEMPORAL_AUTHORITY,),
    "partial support plus target-attribute absence plus plausible unsupported": (TaskArchetype.PARTIAL_SUPPORT, TaskArchetype.TARGET_ABSENT, TaskArchetype.PLAUSIBLE_UNSUPPORTED),
    "ambiguous interpretation plus unresolved source conflict": (TaskArchetype.AMBIGUOUS, TaskArchetype.UNRESOLVED_CONFLICT),
    "alternative MSES plus conditional cross-document reasoning": (TaskArchetype.CONDITIONAL,),
}


_SOURCE_TYPE_BY_PLAN_PORTFOLIO: dict[str, PortfolioSourceType] = {
    "Human Core": PortfolioSourceType.HUMAN,
    "Semi-synthetic Scale": PortfolioSourceType.SEMI_SYNTHETIC,
    "Synthetic Diagnostics": PortfolioSourceType.SYNTHETIC,
    "Adversarial Challenge": PortfolioSourceType.ADVERSARIAL,
}


def _evidence_requirement(shape: str) -> EvidenceRequirement:
    if "dependency graph" in shape:
        return EvidenceRequirement.MULTI_HOP
    if "single MSES" in shape or "partial evidence" in shape:
        return EvidenceRequirement.SINGLE_EVIDENCE
    return EvidenceRequirement.MULTI_EVIDENCE


def _planned_outcome(value: str) -> tuple[PlannedOutcome, CasePolarity]:
    mapping = {
        "answer": (PlannedOutcome.ANSWER, CasePolarity.POSITIVE),
        "abstain": (PlannedOutcome.ABSTAIN, CasePolarity.NEGATIVE),
        "needs_review": (PlannedOutcome.NEEDS_REVIEW, CasePolarity.ESCALATION),
    }
    try:
        return mapping[value]
    except KeyError as exc:
        raise PortfolioError(f"unsupported protocol outcome {value!r}") from exc


def _modality(value: str) -> tuple[DocumentModality, ...]:
    try:
        return (DocumentModality(value),)
    except ValueError as exc:
        raise PortfolioError(f"unsupported Blueprint modality {value!r}") from exc


class PortfolioStore:
    """Immutable contract import plus append-only slot actualization history."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, portfolio: BenchmarkPortfolio, *, artifact_payloads: dict[str, bytes]) -> BenchmarkPortfolio:
        root = self._root(portfolio.portfolio_id)
        path = root / "portfolio.json"
        if path.exists():
            existing = BenchmarkPortfolio.model_validate_json(path.read_text(encoding="utf-8"))
            if existing != portfolio:
                raise PortfolioError("a formal Portfolio contract is immutable; import a successor ID")
            return existing
        expected = {item.name: item for item in portfolio.artifacts}
        if set(expected) != set(artifact_payloads):
            raise PortfolioError("artifact snapshot names must exactly match Portfolio artifacts")
        for name, payload in artifact_payloads.items():
            artifact = expected[name]
            if len(payload) != artifact.byte_count or hashlib.sha256(payload).hexdigest() != artifact.digest:
                raise PortfolioError(f"artifact payload digest mismatch for {name}")
            atomic_write_bytes(root / "artifacts" / name, payload)
        atomic_write_json(path, portfolio.model_dump(mode="json"))
        return portfolio

    def get(self, portfolio_id: str) -> BenchmarkPortfolio:
        portfolio = BenchmarkPortfolio.model_validate_json(
            (self._root(portfolio_id) / "portfolio.json").read_text(encoding="utf-8")
        )
        for artifact in portfolio.artifacts:
            snapshot = self._root(portfolio_id) / "artifacts" / artifact.name
            if not snapshot.is_file() or _file_digest(snapshot) != artifact.digest:
                raise PortfolioError(f"immutable Portfolio artifact snapshot is missing or tampered: {artifact.name}")
        return portfolio

    def assignment_history(self, portfolio_id: str, slot_id: str) -> list[PortfolioAssignment]:
        path = self._root(portfolio_id) / "assignments" / safe_id(slot_id)
        return [
            PortfolioAssignment.model_validate_json(item.read_text(encoding="utf-8"))
            for item in sorted(path.glob("*.json"))
        ]

    def current_assignment(self, portfolio_id: str, slot_id: str) -> PortfolioAssignment | None:
        history = self.assignment_history(portfolio_id, slot_id)
        return history[-1] if history else None

    def append_assignment(self, portfolio_id: str, assignment: PortfolioAssignment) -> PortfolioAssignment:
        history = self.assignment_history(portfolio_id, assignment.slot_id)
        if history:
            current = history[-1]
            if assignment.revision != current.revision + 1 or assignment.parent_assignment_id != current.assignment_id:
                raise PortfolioError("Portfolio assignment revisions must be append-only")
        elif assignment.revision != 1 or assignment.parent_assignment_id is not None:
            raise PortfolioError("first Portfolio assignment must be revision 1 without a parent")
        path = self._root(portfolio_id) / "assignments" / safe_id(assignment.slot_id) / f"{assignment.revision:06d}.json"
        if path.exists():
            existing = PortfolioAssignment.model_validate_json(path.read_text(encoding="utf-8"))
            if existing != assignment:
                raise PortfolioError("Portfolio assignment revision is immutable")
            return existing
        atomic_write_json(path, assignment.model_dump(mode="json"))
        return assignment

    def _root(self, portfolio_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", portfolio_id):
            raise PortfolioError("invalid Portfolio ID")
        return self.root / safe_id(portfolio_id)


class BenchmarkPortfolioService:
    """Imports the frozen source artifacts and computes deterministic coverage."""

    def __init__(
        self,
        root: Path,
        *,
        source_root: Path,
        ledger: AuthoringLedger | None = None,
        releases: "DatasetReleaseStore | None" = None,
    ) -> None:
        self.store = PortfolioStore(root)
        self.source_root = source_root
        self.ledger = ledger
        self.releases = releases

    @classmethod
    def default_source_root(cls) -> Path:
        # Frozen Blueprint inputs belong to the Platform package so the same
        # immutable artifacts are available from a checkout and an installed wheel.
        return Path(__file__).resolve().parents[1] / "resources" / "benchmark-v0"

    def bootstrap_v0_dry_run(self) -> BenchmarkPortfolio:
        paths = self._artifact_paths()
        payloads = {name: path.read_bytes() for name, path in paths.items()}
        artifacts = tuple(
            BlueprintArtifact(name=name, digest=hashlib.sha256(payload).hexdigest(), byte_count=len(payload))
            for name, payload in sorted(payloads.items())
        )
        matrix = self._load_matrix(paths["BENCHMARK_V0_CASE_MATRIX.csv"])
        slots = self._load_dry_run_slots(paths["BENCHMARK_48_CASE_DRY_RUN_PLAN.csv"], matrix)
        portfolio = BenchmarkPortfolio.build(
            portfolio_id=PORTFOLIO_ID_V0_DRY_RUN,
            title="Benchmark V0 48-case protocol dry-run Portfolio",
            artifacts=artifacts,
            matrix=matrix,
            slots=slots,
        )
        return self.store.put(portfolio, artifact_payloads=payloads)

    def bootstrap_v0_held_out(self) -> BenchmarkPortfolio:
        """Create a separate 96-slot held-out plan from the unchanged matrix.

        These are source-family-isolation-constrained slots only.  They do not
        select documents, expose Gold, create Authoring entities, or alter the
        development dry-run Portfolio.
        """

        paths = self._artifact_paths()
        payloads = {name: path.read_bytes() for name, path in paths.items()}
        artifacts = tuple(
            BlueprintArtifact(name=name, digest=hashlib.sha256(payload).hexdigest(), byte_count=len(payload))
            for name, payload in sorted(payloads.items())
        )
        matrix = self._load_matrix(paths["BENCHMARK_V0_CASE_MATRIX.csv"])
        slots = self._load_held_out_slots(matrix)
        portfolio = BenchmarkPortfolio.build(
            portfolio_id=PORTFOLIO_ID_V0_HELD_OUT,
            title="Benchmark V0 isolated held-out 96-case Portfolio plan",
            artifacts=artifacts,
            matrix=matrix,
            slots=slots,
        )
        return self.store.put(portfolio, artifact_payloads=payloads)

    def coverage_report(self, portfolio_id: str = PORTFOLIO_ID_V0_DRY_RUN) -> PortfolioCoverageReport:
        portfolio = self.store.get(portfolio_id)
        states = {slot.slot_id: self._slot_state(portfolio_id, slot.slot_id) for slot in portfolio.slots}
        state_counts = tuple(
            (state, sum(1 for actual in states.values() if actual == state))
            for state in PortfolioSlotState
        )
        counters: dict[tuple[PortfolioAxis, str], Counter[str]] = defaultdict(Counter)
        for slot in portfolio.slots:
            state = states[slot.slot_id]
            completed = self._slot_is_completed(portfolio_id, slot.slot_id, state)
            blocked = state == PortfolioSlotState.BLOCKED
            values = self._slot_axis_values(slot)
            for axis, axis_values in values.items():
                for value in axis_values:
                    counters[(axis, value)]["planned"] += 1
                    if completed:
                        counters[(axis, value)]["completed"] += 1
                    if blocked:
                        counters[(axis, value)]["blocked"] += 1
        coverage = tuple(
            CoverageBucket(
                axis=axis,
                value=value,
                planned=counts["planned"],
                completed=counts["completed"],
                missing=max(0, counts["planned"] - counts["completed"]),
                blocked=counts["blocked"],
                overrepresented=max(0, counts["completed"] - counts["planned"]),
            )
            for (axis, value), counts in sorted(counters.items(), key=lambda item: (item[0][0].value, item[0][1]))
        )
        deficits = tuple(
            CoverageDeficit(
                axis=item.axis,
                value=item.value,
                planned=item.planned,
                completed=item.completed,
                missing=item.missing,
                blocked=item.blocked,
                reason="planned Portfolio coverage has not reached approved/frozen completion",
            )
            for item in coverage
            if item.missing > 0 or item.blocked > 0
        )
        from rag_eval.datasets.registry import FROZEN_20_CASE_BUNDLE_ID

        frozen = FrozenReferenceObservation(
            bundle_id=FROZEN_20_CASE_BUNDLE_ID,
            case_count=20,
            usage=PortfolioUsage.DEVELOPMENT,
            diagnostic_reference=True,
            held_out=False,
            generalization_claim_allowed=False,
            source_family=SourceFamily.FROZEN_REFERENCE_DIAGNOSTIC,
            typed_case_axes_available=False,
        )
        return PortfolioCoverageReport.build(
            portfolio=portfolio,
            state_counts=state_counts,
            coverage=coverage,
            deficits=deficits,
            frozen_reference=frozen,
        )

    def transition_slot(
        self,
        portfolio_id: str,
        *,
        slot_id: str,
        state: PortfolioSlotState,
        links: PortfolioLinks,
        actor: str,
        reason: str,
        blocked_reason: PortfolioBlockedReason | None = None,
    ) -> PortfolioAssignment:
        portfolio = self.store.get(portfolio_id)
        if slot_id not in {slot.slot_id for slot in portfolio.slots}:
            raise PortfolioError("unknown Portfolio slot")
        current = self.store.current_assignment(portfolio_id, slot_id)
        current_state = current.state if current else PortfolioSlotState.PLANNED
        allowed = {
            PortfolioSlotState.PLANNED: {PortfolioSlotState.AUTHORED, PortfolioSlotState.BLOCKED},
            PortfolioSlotState.AUTHORED: {PortfolioSlotState.REVIEWED, PortfolioSlotState.BLOCKED},
            PortfolioSlotState.REVIEWED: {PortfolioSlotState.APPROVED, PortfolioSlotState.BLOCKED},
            PortfolioSlotState.APPROVED: {PortfolioSlotState.FROZEN, PortfolioSlotState.BLOCKED},
            PortfolioSlotState.FROZEN: set(),
            PortfolioSlotState.BLOCKED: set(),
        }
        if state not in allowed[current_state]:
            raise PortfolioError(f"illegal Portfolio transition {current_state.value} -> {state.value}")
        slot = next(item for item in portfolio.slots if item.slot_id == slot_id)
        if slot.usage == PortfolioUsage.HELD_OUT and state != PortfolioSlotState.BLOCKED:
            if not links.source_family_id or not links.source_admission_report_digest:
                raise PortfolioError("held-out Portfolio actualization requires an isolated source-family ID and admission report digest")
        self._validate_authoring_links(state, links)
        revision = (current.revision if current else 0) + 1
        assignment = PortfolioAssignment(
            assignment_id=f"portfolio-assignment-{safe_id(slot_id)}-{revision:06d}",
            slot_id=slot_id,
            revision=revision,
            parent_assignment_id=current.assignment_id if current else None,
            state=state,
            blocked_reason=blocked_reason,
            links=links,
            actor=actor.strip(),
            reason=reason.strip(),
            created_at=datetime.now(UTC),
        )
        if not assignment.actor or not assignment.reason:
            raise PortfolioError("Portfolio transition needs actor and reason")
        return self.store.append_assignment(portfolio_id, assignment)

    def reassess_blocked_slot(
        self,
        portfolio_id: str,
        *,
        slot_id: str,
        actor: str,
        reason: str,
        blocked_reason: PortfolioBlockedReason,
    ) -> PortfolioAssignment:
        """Append an evidence-based re-assessment without rewriting a block.

        ``blocked`` is terminal for the actualization state machine: a later
        audit must never quietly resurrect a rejected planning decision.  A
        source or Canonical change can, however, make the *reason* for that
        terminal decision obsolete.  This method records that audit as the
        next immutable assignment revision while retaining ``blocked``.  A
        new planned Portfolio slot is required for any later actualization.
        """

        portfolio = self.store.get(portfolio_id)
        if slot_id not in {slot.slot_id for slot in portfolio.slots}:
            raise PortfolioError("unknown Portfolio slot")
        current = self.store.current_assignment(portfolio_id, slot_id)
        if current is None or current.state != PortfolioSlotState.BLOCKED:
            raise PortfolioError("only an existing blocked Portfolio slot can be reassessed")
        actor = actor.strip()
        reason = reason.strip()
        if not actor or not reason:
            raise PortfolioError("blocked reassessment needs actor and reason")
        assignment = PortfolioAssignment(
            assignment_id=f"portfolio-assignment-{safe_id(slot_id)}-{current.revision + 1:06d}",
            slot_id=slot_id,
            revision=current.revision + 1,
            parent_assignment_id=current.assignment_id,
            state=PortfolioSlotState.BLOCKED,
            blocked_reason=blocked_reason,
            links=PortfolioLinks(),
            actor=actor,
            reason=reason,
            created_at=datetime.now(UTC),
        )
        return self.store.append_assignment(portfolio_id, assignment)

    def _validate_authoring_links(self, state: PortfolioSlotState, links: PortfolioLinks) -> None:
        if state == PortfolioSlotState.BLOCKED:
            return
        if self.ledger is None:
            raise PortfolioError("Authoring Ledger is required to actualize a Portfolio slot")
        assert links.dataset_id and links.case_revision_id
        case = self.ledger.get_case_revision(links.dataset_id, links.case_revision_id)
        if state == PortfolioSlotState.AUTHORED and case.lifecycle not in {LifecycleState.DRAFT, LifecycleState.PROPOSED}:
            raise PortfolioError("authored slot must point to draft/proposed CaseRevision")
        if state == PortfolioSlotState.REVIEWED and case.lifecycle != LifecycleState.REVIEWED:
            raise PortfolioError("reviewed slot must point to reviewed CaseRevision")
        if state in {PortfolioSlotState.APPROVED, PortfolioSlotState.FROZEN}:
            if case.lifecycle not in {LifecycleState.APPROVED, LifecycleState.FROZEN}:
                raise PortfolioError("approved/frozen slot needs approved/frozen CaseRevision")
            assert links.document_revision_id and links.gold_revision_id
            document = self.ledger.get_document_revision(links.dataset_id, links.document_revision_id)
            gold = self.ledger.get_gold_revision(links.dataset_id, links.gold_revision_id)
            # Gold pins the Case revision that existed when it was authored;
            # Case review/approval then appends new immutable revisions.  The
            # stable Case identity, rather than an in-place revision equality,
            # is therefore the formal association used by the Ledger and
            # Dataset Release contracts.
            if gold.case_id != case.case_id or gold.lifecycle not in {LifecycleState.APPROVED, LifecycleState.FROZEN}:
                raise PortfolioError("approved/frozen slot needs matching approved/frozen GoldRevision")
            if document.dataset_id != links.dataset_id:
                raise PortfolioError("DocumentRevision must belong to slot Dataset")
        if state == PortfolioSlotState.FROZEN:
            if self.releases is None or not links.release_id:
                raise PortfolioError("Dataset Release store is required for frozen Portfolio coverage")
            release = self.releases.get(links.release_id)
            if release.dataset_id != links.dataset_id:
                raise PortfolioError("frozen release belongs to another Dataset")
            if links.case_revision_id not in {item.case_revision_id for item in release.cases}:
                raise PortfolioError("frozen release does not pin selected CaseRevision")
            if links.gold_revision_id not in {item.gold_revision_id for item in release.gold}:
                raise PortfolioError("frozen release does not pin selected GoldRevision")

    def _slot_state(self, portfolio_id: str, slot_id: str) -> PortfolioSlotState:
        assignment = self.store.current_assignment(portfolio_id, slot_id)
        return assignment.state if assignment else PortfolioSlotState.PLANNED

    def _slot_is_completed(
        self, portfolio_id: str, slot_id: str, state: PortfolioSlotState
    ) -> bool:
        """Count only still-valid approved/frozen Authoring references.

        A later Ledger invalidation/supersession never rewrites this assignment
        history, but it must remove the slot from current completion coverage.
        Historical Dataset Releases remain independently immutable; this is a
        current-portfolio health view, not a mutation of those releases.
        """

        if state not in {PortfolioSlotState.APPROVED, PortfolioSlotState.FROZEN}:
            return False
        assignment = self.store.current_assignment(portfolio_id, slot_id)
        if assignment is None:
            return False
        if self.ledger is None:
            return False
        links = assignment.links
        try:
            assert links.dataset_id and links.case_revision_id and links.gold_revision_id
            case = self.ledger.get_case_revision(links.dataset_id, links.case_revision_id)
            gold = self.ledger.get_gold_revision(links.dataset_id, links.gold_revision_id)
            current_case = self.ledger.current_case(links.dataset_id, case.case_id)
            current_gold = self.ledger.current_gold_for_case(links.dataset_id, case.case_id)
        except (AssertionError, ValueError):
            return False
        if case.lifecycle not in {LifecycleState.APPROVED, LifecycleState.FROZEN}:
            return False
        if gold.lifecycle not in {LifecycleState.APPROVED, LifecycleState.FROZEN}:
            return False
        if current_case.lifecycle in {LifecycleState.REJECTED, LifecycleState.INVALIDATED, LifecycleState.SUPERSEDED}:
            return False
        if current_gold.lifecycle in {LifecycleState.REJECTED, LifecycleState.INVALIDATED, LifecycleState.SUPERSEDED}:
            return False
        if current_gold.gold_id != gold.gold_id:
            return False
        if state == PortfolioSlotState.FROZEN:
            if self.releases is None or not links.release_id:
                return False
            try:
                release = self.releases.get(links.release_id)
            except FileNotFoundError:
                return False
            return (
                links.case_revision_id in {item.case_revision_id for item in release.cases}
                and links.gold_revision_id in {item.gold_revision_id for item in release.gold}
            )
        return True

    @staticmethod
    def _slot_axis_values(slot: PortfolioSlot) -> dict[PortfolioAxis, tuple[str, ...]]:
        return {
            PortfolioAxis.PRIMARY_TASK: tuple(item.value for item in slot.primary_tasks),
            PortfolioAxis.SOURCE_TYPE: (slot.source_type.value,),
            PortfolioAxis.LANGUAGE: (slot.language.value,),
            PortfolioAxis.RETRIEVAL_DIFFICULTY: tuple(item.value for item in slot.retrieval_difficulties),
            PortfolioAxis.REASONING_DIFFICULTY: tuple(item.value for item in slot.reasoning_difficulties),
            PortfolioAxis.MODALITY: tuple(item.value for item in slot.modalities),
            PortfolioAxis.ANSWERABILITY: tuple(item.value for item in slot.answerabilities),
            PortfolioAxis.EVIDENCE_REQUIREMENT: (slot.evidence_requirement.value,),
            PortfolioAxis.EVIDENCE_COMPOSITION: tuple(item.value for item in slot.evidence_compositions),
            PortfolioAxis.RETRIEVAL_REASONING: tuple(
                f"{retrieval.value}|{reasoning.value}"
                for retrieval in slot.retrieval_difficulties
                for reasoning in slot.reasoning_difficulties
            ),
            PortfolioAxis.SOURCE_FAMILY: (slot.source_family.value,),
        }

    def _artifact_paths(self) -> dict[str, Path]:
        names = (
            "BENCHMARK_BLUEPRINT_V0.md",
            "BENCHMARK_PROTOCOL_V0.md",
            "BENCHMARK_V0_CASE_MATRIX.csv",
            "BENCHMARK_48_CASE_DRY_RUN_PLAN.csv",
        )
        paths = {name: self.source_root / name for name in names}
        missing = [str(path) for path in paths.values() if not path.is_file()]
        if missing:
            raise PortfolioError("required Blueprint artifacts are unavailable: " + ", ".join(missing))
        return paths

    def _load_matrix(self, path: Path) -> tuple[BlueprintMatrixRow, ...]:
        rows: list[BlueprintMatrixRow] = []
        with path.open(encoding="utf-8", newline="") as stream:
            for raw in csv.DictReader(stream):
                primary = TaskArchetype(raw["primary_task_archetype"])
                count = int(raw["count"])
                cardinality = raw["evidence_cardinality"]
                requirement = EvidenceRequirement.MULTI_HOP if primary == TaskArchetype.DEPENDENT_MULTI_HOP else EvidenceRequirement.SINGLE_EVIDENCE if cardinality == "1" else EvidenceRequirement.MULTI_EVIDENCE
                context = _CONTEXT_PRESSURE_BY_MATRIX_DISTANCE.get(raw["document_distance"])
                if context is None:
                    raise PortfolioError(f"unmapped Blueprint document distance {raw['document_distance']!r}")
                rows.append(
                    BlueprintMatrixRow(
                        primary_task=primary,
                        retrieval_routes=_sorted_unique(_enum_values(raw["retrieval_route"], RetrievalRoute)),
                        evidence_compositions=_sorted_unique(_enum_values(raw["evidence_composition"], EvidenceComposition)),
                        reasoning_operations=_sorted_unique(_enum_values(raw["reasoning_operation"], ReasoningOperation)),
                        structured_content=_sorted_unique(_enum_values(raw["structured_content"], StructuredContent)),
                        answerabilities=(Answerability(raw["answerability"]),),
                        retrieval_difficulties=_sorted_unique(_difficulty_values(raw["retrieval_difficulty"].replace(" 4 / Hard 4", " or Hard").replace(" 5 / Hard 3", " or Hard"), RetrievalDifficulty)),
                        reasoning_difficulties=_sorted_unique(_difficulty_values(raw["reasoning_difficulty"], ReasoningDifficulty)),
                        modalities=(DocumentModality(raw["modality"]),),
                        evidence_requirement=requirement,
                        context_pressures=_sorted_unique(context),
                        source_type_counts=(
                            (PortfolioSourceType.HUMAN, int(raw["human_core_count"])),
                            (PortfolioSourceType.SEMI_SYNTHETIC, int(raw["semi_synthetic_count"])),
                            (PortfolioSourceType.SYNTHETIC, int(raw["synthetic_diagnostics_count"])),
                            (PortfolioSourceType.ADVERSARIAL, int(raw["adversarial_challenge_count"])),
                        ),
                        language_counts=(
                            (BenchmarkLanguage.ENGLISH, int(raw["english_count"])),
                            (BenchmarkLanguage.CHINESE, int(raw["chinese_count"])),
                        ),
                        target_count=count,
                        source_row_digest=_digest(raw),
                    )
                )
        if sum(item.target_count for item in rows) != 96:
            raise PortfolioError("V0 matrix target total must remain 96")
        return tuple(rows)

    def _load_dry_run_slots(self, path: Path, matrix: tuple[BlueprintMatrixRow, ...]) -> tuple[PortfolioSlot, ...]:
        matrix_by_task = {item.primary_task: item for item in matrix}
        slots: list[PortfolioSlot] = []
        with path.open(encoding="utf-8", newline="") as stream:
            for raw in csv.DictReader(line for line in stream if not line.startswith("#")):
                group_id = raw["plan_group_id"]
                count = int(raw["planned_slot_count"])
                en_count, zh_count = int(raw["english_count"]), int(raw["chinese_count"])
                if count != en_count + zh_count:
                    raise PortfolioError(f"language allocation does not match planned slots for {group_id}")
                tasks = _TASKS_BY_DRY_RUN_CONSTRUCT.get(raw["primary_constructs"])
                if tasks is None:
                    raise PortfolioError(f"unmapped dry-run primary construct {raw['primary_constructs']!r}")
                selected = [matrix_by_task[task] for task in tasks]
                outcome, polarity = _planned_outcome(raw["answerability_outcome"])
                languages = (BenchmarkLanguage.ENGLISH,) * en_count + (BenchmarkLanguage.CHINESE,) * zh_count
                for ordinal, language in enumerate(languages, start=1):
                    slots.append(
                        PortfolioSlot(
                            slot_id=f"{group_id}-slot-{ordinal:02d}",
                            plan_group_id=group_id,
                            plan_group_slot_ordinal=ordinal,
                            source_type=_SOURCE_TYPE_BY_PLAN_PORTFOLIO[raw["portfolio"]],
                            usage=PortfolioUsage.DEVELOPMENT,
                            language=language,
                            primary_tasks=tuple(tasks),
                            retrieval_routes=_sorted_unique(tuple(value for row in selected for value in row.retrieval_routes)),
                            evidence_compositions=_sorted_unique(tuple(value for row in selected for value in row.evidence_compositions) + ((EvidenceComposition.ALTERNATIVE_PATH,) if "OR MSES" in raw["evidence_shape"] else ())),
                            reasoning_operations=_sorted_unique(tuple(value for row in selected for value in row.reasoning_operations)),
                            structured_content=_sorted_unique(tuple(value for row in selected for value in row.structured_content)),
                            answerabilities=_sorted_unique(tuple(value for row in selected for value in row.answerabilities)),
                            retrieval_difficulties=_sorted_unique(_difficulty_values(raw["retrieval_difficulty"], RetrievalDifficulty)),
                            reasoning_difficulties=_sorted_unique(_difficulty_values(raw["reasoning_difficulty"], ReasoningDifficulty)),
                            modalities=_modality(raw["modality"]),
                            evidence_requirement=_evidence_requirement(raw["evidence_shape"]),
                            polarity=polarity,
                            planned_outcome=outcome,
                            context_pressures=_sorted_unique(tuple(value for row in selected for value in row.context_pressures)),
                            plan_row_digest=_digest(raw),
                        )
                    )
        if len(slots) != 48:
            raise PortfolioError("dry-run plan must import exactly 48 slots")
        return tuple(slots)

    @staticmethod
    def _load_held_out_slots(matrix: tuple[BlueprintMatrixRow, ...]) -> tuple[PortfolioSlot, ...]:
        """Derive slots mechanically from the frozen v0 matrix allocations."""

        slots: list[PortfolioSlot] = []
        for group_number, row in enumerate(matrix, start=1):
            group_id = f"HOLDOUT-{group_number:02d}"
            source_types = tuple(
                source_type
                for source_type, count in row.source_type_counts
                for _ in range(count)
            )
            languages = tuple(
                language
                for language, count in row.language_counts
                for _ in range(count)
            )
            if len(source_types) != row.target_count or len(languages) != row.target_count:
                raise PortfolioError("held-out matrix allocation is internally inconsistent")
            if row.answerabilities[0] in {
                Answerability.PARTIALLY_SUPPORTED,
                Answerability.UNANSWERABLE,
                Answerability.PLAUSIBLE_UNSUPPORTED,
            }:
                outcome, polarity = PlannedOutcome.ABSTAIN, CasePolarity.NEGATIVE
            elif row.answerabilities[0] in {
                Answerability.AMBIGUOUS,
                Answerability.CONFLICTING_UNRESOLVED,
            }:
                outcome, polarity = PlannedOutcome.NEEDS_REVIEW, CasePolarity.ESCALATION
            else:
                outcome, polarity = PlannedOutcome.ANSWER, CasePolarity.POSITIVE
            source_row_digest = row.source_row_digest
            for ordinal, (source_type, language) in enumerate(zip(source_types, languages, strict=True), start=1):
                slots.append(
                    PortfolioSlot(
                        slot_id=f"{group_id}-slot-{ordinal:02d}",
                        plan_group_id=group_id,
                        plan_group_slot_ordinal=ordinal,
                        source_type=source_type,
                        usage=PortfolioUsage.HELD_OUT,
                        language=language,
                        primary_tasks=(row.primary_task,),
                        retrieval_routes=row.retrieval_routes,
                        evidence_compositions=row.evidence_compositions,
                        reasoning_operations=row.reasoning_operations,
                        structured_content=row.structured_content,
                        answerabilities=row.answerabilities,
                        retrieval_difficulties=row.retrieval_difficulties,
                        reasoning_difficulties=row.reasoning_difficulties,
                        modalities=row.modalities,
                        evidence_requirement=row.evidence_requirement,
                        polarity=polarity,
                        planned_outcome=outcome,
                        context_pressures=row.context_pressures,
                        source_family=SourceFamily.HELD_OUT_ISOLATED_PENDING_ADMISSION,
                        plan_row_digest=source_row_digest,
                    )
                )
        if len(slots) != 96:
            raise PortfolioError("held-out v0 Portfolio must preserve all 96 matrix slots")
        return tuple(slots)
