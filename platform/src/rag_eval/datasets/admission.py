"""Benchmark data-generation and admission policy v1.

This is a pre-authoring policy layer, not a new Case, Gold, scorer, or RAG
contract.  It consumes the Canonical Data Model and the formal Authoring
Ledger, emits auditable fail-closed findings, and leaves all semantic matters
that cannot be established programmatically in an explicit human-review
state.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.authoring.ledger import (
    CaseRevision,
    EvidenceRole,
    GoldRevision,
    LifecycleState,
    OriginKind,
)
from rag_eval.contracts.canonical import CanonicalDocument, RepresentationStatus
from rag_eval.datasets.portfolio import (
    BenchmarkPortfolioService,
    EvidenceRequirement,
    PortfolioSlot,
    PortfolioUsage,
)
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.ids import safe_id


DATA_GENERATION_POLICY_VERSION = "benchmark-data-generation-policy/1.0"
ADMISSION_REPORT_SCHEMA_VERSION = "benchmark-admission-report/1.0"
CALIBRATION_PROCESS_VERSION = "benchmark-calibration-reference-process/1.0"


class BenchmarkAdmissionError(ValueError):
    """A policy input, source registry record, or promotion attempt is invalid."""


class PolicyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceFamilyClass(StrEnum):
    DEVELOPMENT = "development"
    HELD_OUT = "held_out"
    REFERENCE_DIAGNOSTIC = "reference_diagnostic"


class SourceAdmissionStatus(StrEnum):
    CANDIDATE = "candidate"
    ADMITTED = "admitted"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"


class DocumentType(StrEnum):
    """P1 keeps actual admission scoped to the existing DOCX canonicalizer."""

    DOCX = "docx"


class SimilarityDisposition(StrEnum):
    DISTINCT = "distinct"
    NEAR_DUPLICATE = "near_duplicate"
    EXACT_DUPLICATE = "exact_duplicate"
    UNDETERMINED = "undetermined"


class PolicySeverity(StrEnum):
    ERROR = "ERROR"
    WARN = "WARN"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    INFO = "INFO"


class PolicyResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReviewTier(StrEnum):
    STANDARD = "standard"
    HEIGHTENED = "heightened"


class ModelUse(StrEnum):
    CANDIDATE_QUESTION = "candidate_question_generation"
    QUESTION_REWRITE = "question_rewrite"
    CANDIDATE_ANSWER_EVIDENCE = "candidate_answer_evidence_suggestion"
    DISTRACTOR_SUGGESTION = "distractor_suggestion"
    QUALITY_ASSISTANCE = "quality_assistance"


class CalibrationBaseline(StrEnum):
    BM25 = "bm25_v0"
    DENSE = "dense_v0"
    NO_RETRIEVAL = "no_retrieval_llm_v0"
    ORACLE_EVIDENCE = "oracle_evidence_llm_v0"


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


class SourceFamilyRecord(PolicyModel):
    source_family_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    classification: SourceFamilyClass
    content_boundary: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    created_at: datetime
    record_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_digest(self) -> "SourceFamilyRecord":
        expected = _digest(self._payload())
        if self.record_digest != expected:
            raise ValueError("source family record digest does not match content")
        return self

    def _payload(self) -> dict[str, object]:
        return {
            "source_family_id": self.source_family_id,
            "classification": self.classification.value,
            "content_boundary": self.content_boundary,
            "owner": self.owner,
        }

    @classmethod
    def build(
        cls, *, source_family_id: str, classification: SourceFamilyClass, content_boundary: str, owner: str
    ) -> "SourceFamilyRecord":
        payload = {
            "source_family_id": source_family_id,
            "classification": classification,
            "content_boundary": content_boundary.strip(),
            "owner": owner.strip(),
        }
        return cls(**payload, created_at=datetime.now(UTC), record_digest=_digest({**payload, "classification": classification.value}))


class SourceSimilarityAssessment(PolicyModel):
    compared_document_id: str = Field(min_length=1)
    compared_source_family_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    disposition: SimilarityDisposition
    similarity_score: float | None = Field(default=None, ge=0.0, le=1.0)
    comparison_method: str = Field(min_length=1)
    comparison_corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rationale: str | None = None

    @model_validator(mode="after")
    def _score_rules(self) -> "SourceSimilarityAssessment":
        if self.disposition == SimilarityDisposition.UNDETERMINED and self.similarity_score is not None:
            raise ValueError("undetermined similarity cannot claim a score")
        if self.disposition != SimilarityDisposition.UNDETERMINED and self.similarity_score is None:
            raise ValueError("determined similarity must include a score")
        return self


class DocumentSourceRecord(PolicyModel):
    """A source admission revision; no source document is admitted by default."""

    source_document_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    source_family_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    revision: int = Field(ge=1)
    parent_revision_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    document_type: DocumentType
    content_summary: str = Field(min_length=1)
    file_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_document_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_identity: str = Field(min_length=1)
    canonicalizer_identity: str = Field(min_length=1)
    parser_configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    parsing_completeness: RepresentationStatus
    structure_completeness: RepresentationStatus
    evidence_locator_completeness: RepresentationStatus
    development_similarity: tuple[SourceSimilarityAssessment, ...] = ()
    independent_test_eligible: bool
    admission_status: SourceAdmissionStatus
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    created_at: datetime
    record_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_order_and_digest(self) -> "DocumentSourceRecord":
        if tuple(sorted(self.development_similarity, key=lambda item: item.compared_document_id)) != self.development_similarity:
            raise ValueError("source similarity assessments must be ordered by compared document")
        expected = _digest(self._payload())
        if self.record_digest != expected:
            raise ValueError("source document record digest does not match content")
        return self

    def _payload(self) -> dict[str, object]:
        value = self.model_dump(mode="json")
        value.pop("record_digest")
        value.pop("created_at")
        return value

    @classmethod
    def build(cls, **values: object) -> "DocumentSourceRecord":
        payload = dict(values)
        payload["development_similarity"] = tuple(
            sorted(payload.get("development_similarity", ()), key=lambda item: item.compared_document_id)  # type: ignore[union-attr]
        )
        payload.setdefault("created_at", datetime.now(UTC))
        digest_payload = dict(payload)
        digest_payload.pop("created_at", None)
        return cls(**payload, record_digest=_digest(_json_model_values(digest_payload)))


class CanonicalEvidenceScope(PolicyModel):
    """A reviewed complete-evidence subset of a partially supported source.

    This never upgrades the document's own parsing-completeness status.  It
    simply makes the narrowly permitted Canonical objects explicit and
    auditable for development authoring.
    """

    scope_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    source_document_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    canonical_document_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_object_ids: tuple[str, ...] = Field(min_length=1)
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    created_at: datetime
    scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_scope(self) -> "CanonicalEvidenceScope":
        if tuple(sorted(set(self.canonical_object_ids))) != self.canonical_object_ids:
            raise ValueError("Canonical evidence scope object IDs must be ordered and unique")
        if self.scope_digest != _digest(self._payload()):
            raise ValueError("Canonical evidence scope digest does not match content")
        return self

    def _payload(self) -> dict[str, object]:
        return {
            "scope_id": self.scope_id,
            "source_document_id": self.source_document_id,
            "canonical_document_digest": self.canonical_document_digest,
            "canonical_object_ids": self.canonical_object_ids,
            "actor": self.actor,
            "reason": self.reason,
        }

    @classmethod
    def build(
        cls,
        *,
        scope_id: str,
        source_document_id: str,
        canonical_document_digest: str,
        canonical_object_ids: tuple[str, ...],
        actor: str,
        reason: str,
    ) -> "CanonicalEvidenceScope":
        payload = {
            "scope_id": scope_id,
            "source_document_id": source_document_id,
            "canonical_document_digest": canonical_document_digest,
            "canonical_object_ids": tuple(sorted(set(canonical_object_ids))),
            "actor": actor.strip(),
            "reason": reason.strip(),
        }
        return cls(**payload, created_at=datetime.now(UTC), scope_digest=_digest(payload))


class MsesNecessityCheck(PolicyModel):
    """Audit evidence necessity at an MSES clause, preserving OR alternatives."""

    path_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    clause_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    alternative_evidence_ids: tuple[str, ...] = Field(min_length=1)
    necessary: bool | None
    method: str = Field(min_length=1)
    verifier_identity: str | None = None
    rationale: str | None = None


class ModelAssistanceRecord(PolicyModel):
    """Trace a permitted LLM suggestion without promoting its output to Gold."""

    assistance_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    permitted_use: ModelUse
    model_identity: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    seed: int | None = None
    output_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposal_only: Literal[True] = True


class QuestionSimilarityAssessment(PolicyModel):
    compared_case_id: str = Field(min_length=1)
    compared_usage: PortfolioUsage
    disposition: SimilarityDisposition
    similarity_score: float | None = Field(default=None, ge=0.0, le=1.0)
    method: str = Field(min_length=1)

    @model_validator(mode="after")
    def _score_rules(self) -> "QuestionSimilarityAssessment":
        if self.disposition == SimilarityDisposition.UNDETERMINED and self.similarity_score is not None:
            raise ValueError("undetermined question similarity cannot claim a score")
        if self.disposition != SimilarityDisposition.UNDETERMINED and self.similarity_score is None:
            raise ValueError("determined question similarity must include a score")
        return self


class AdmissionChecklistAttestation(PolicyModel):
    """Policy-specific checklist that references, rather than replaces, Ledger Review."""

    ledger_review_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    reviewed_case_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    reviewed_gold_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    # Ledger review happens on a proposed immutable revision; approval then
    # appends another immutable revision.  These stable identities let the
    # policy attest to the actual reviewed lineage without claiming that an
    # approval revision itself was reviewed in place.
    case_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    gold_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    reviewer_identity: str = Field(min_length=1)
    question_natural: bool
    ambiguity_checked: bool
    answer_correct: bool
    evidence_sufficient: bool
    evidence_minimal: bool
    alternative_answers_checked: bool
    difficulty_label_reasonable: bool
    approved: bool
    comments: str = ""

    @model_validator(mode="after")
    def _stable_ids_are_paired(self) -> "AdmissionChecklistAttestation":
        if (self.case_id is None) != (self.gold_id is None):
            raise ValueError("admission checklist stable Case/Gold IDs must be supplied together")
        return self

    @property
    def complete(self) -> bool:
        return self.approved and all(
            (
                self.question_natural,
                self.ambiguity_checked,
                self.answer_correct,
                self.evidence_sufficient,
                self.evidence_minimal,
                self.alternative_answers_checked,
                self.difficulty_label_reasonable,
            )
        )


class CaseAdmissionInput(PolicyModel):
    portfolio_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    slot_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    source: DocumentSourceRecord
    source_admission_report: "AdmissionReport | None" = None
    evidence_scope: CanonicalEvidenceScope | None = None
    case: CaseRevision
    gold: GoldRevision
    canonical: CanonicalDocument
    necessity_checks: tuple[MsesNecessityCheck, ...] = ()
    model_assistance: tuple[ModelAssistanceRecord, ...] = ()
    question_similarity: tuple[QuestionSimilarityAssessment, ...] = ()
    review_attestations: tuple[AdmissionChecklistAttestation, ...] = ()


class PolicyFinding(PolicyModel):
    rule_id: str = Field(min_length=1)
    severity: PolicySeverity
    result: PolicyResult
    message: str = Field(min_length=1)
    affected_ids: tuple[str, ...] = ()


class AdmissionReport(PolicyModel):
    schema_version: Literal[ADMISSION_REPORT_SCHEMA_VERSION] = ADMISSION_REPORT_SCHEMA_VERSION
    policy_version: Literal[DATA_GENERATION_POLICY_VERSION] = DATA_GENERATION_POLICY_VERSION
    scope: Literal["source", "case"]
    subject_ids: tuple[str, ...] = Field(min_length=1)
    subject_digests: tuple[str, ...] = Field(min_length=1)
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    findings: tuple[PolicyFinding, ...]
    report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_digest_and_order(self) -> "AdmissionReport":
        if tuple(sorted(self.findings, key=lambda item: item.rule_id)) != self.findings:
            raise ValueError("policy findings must be ordered by rule ID")
        expected = _digest(self._payload())
        if self.report_digest != expected:
            raise ValueError("admission report digest does not match content")
        return self

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "scope": self.scope,
            "subject_ids": self.subject_ids,
            "subject_digests": self.subject_digests,
            "input_digest": self.input_digest,
            "findings": [item.model_dump(mode="json") for item in self.findings],
        }

    @classmethod
    def build(cls, *, scope: Literal["source", "case"], subject_ids: tuple[str, ...], subject_digests: tuple[str, ...], input_value: object, findings: tuple[PolicyFinding, ...]) -> "AdmissionReport":
        values = {
            "scope": scope,
            "subject_ids": tuple(sorted(subject_ids)),
            "subject_digests": tuple(sorted(subject_digests)),
            "input_digest": _digest(_json_model_values(input_value)),
            "findings": tuple(sorted(findings, key=lambda item: item.rule_id)),
        }
        digest = _digest(
            {
                "schema_version": ADMISSION_REPORT_SCHEMA_VERSION,
                "policy_version": DATA_GENERATION_POLICY_VERSION,
                "scope": scope,
                "subject_ids": values["subject_ids"],
                "subject_digests": values["subject_digests"],
                "input_digest": values["input_digest"],
                "findings": [item.model_dump(mode="json") for item in values["findings"]],
            }
        )
        return cls(**values, report_digest=digest)

    @property
    def has_errors(self) -> bool:
        return any(item.severity == PolicySeverity.ERROR and item.result == PolicyResult.FAIL for item in self.findings)

    @property
    def requires_human_review(self) -> bool:
        return any(item.result == PolicyResult.HUMAN_REVIEW_REQUIRED for item in self.findings)

    @property
    def eligible_to_proceed(self) -> bool:
        return not self.has_errors and not self.requires_human_review


class CalibrationReferenceProcess(PolicyModel):
    """Fixed policy workflow; a concrete harness lock is recorded separately."""

    process_version: Literal[CALIBRATION_PROCESS_VERSION] = CALIBRATION_PROCESS_VERSION
    baselines: tuple[CalibrationBaseline, ...] = (
        CalibrationBaseline.BM25,
        CalibrationBaseline.DENSE,
        CalibrationBaseline.NO_RETRIEVAL,
        CalibrationBaseline.ORACLE_EVIDENCE,
    )
    fixed_seeds: tuple[int, ...] = (20260824, 20260825, 20260826)
    rule: str = "Calibration checks declared difficulty only; it never edits Gold, selects Gold evidence, or defines difficulty from one RAG system outcome."
    process_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify(self) -> "CalibrationReferenceProcess":
        if self.baselines != (
            CalibrationBaseline.BM25,
            CalibrationBaseline.DENSE,
            CalibrationBaseline.NO_RETRIEVAL,
            CalibrationBaseline.ORACLE_EVIDENCE,
        ):
            raise ValueError("calibration baseline roles are fixed by the v0 Protocol")
        if self.fixed_seeds != (20260824, 20260825, 20260826):
            raise ValueError("calibration seed policy is fixed by the v0 Protocol")
        if self.process_digest != _digest(self._payload()):
            raise ValueError("calibration process digest does not match content")
        return self

    def _payload(self) -> dict[str, object]:
        return {
            "process_version": self.process_version,
            "baselines": [item.value for item in self.baselines],
            "fixed_seeds": self.fixed_seeds,
            "rule": self.rule,
        }

    @classmethod
    def build(cls) -> "CalibrationReferenceProcess":
        values = {
            "baselines": (
                CalibrationBaseline.BM25,
                CalibrationBaseline.DENSE,
                CalibrationBaseline.NO_RETRIEVAL,
                CalibrationBaseline.ORACLE_EVIDENCE,
            ),
            "fixed_seeds": (20260824, 20260825, 20260826),
            "rule": "Calibration checks declared difficulty only; it never edits Gold, selects Gold evidence, or defines difficulty from one RAG system outcome.",
        }
        payload = {
            "process_version": CALIBRATION_PROCESS_VERSION,
            "baselines": [item.value for item in values["baselines"]],
            "fixed_seeds": values["fixed_seeds"],
            "rule": values["rule"],
        }
        return cls(**values, process_digest=_digest(payload))


class CalibrationReferenceLock(PolicyModel):
    process_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_harness_id: str = Field(min_length=1)
    harness_revision: str = Field(min_length=1)
    harness_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    tokenizer_or_preprocessing_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_configuration_digests: tuple[tuple[CalibrationBaseline, str], ...] = Field(min_length=4)
    prompt_digests: tuple[tuple[CalibrationBaseline, str], ...] = Field(min_length=2)
    fixed_seeds: tuple[int, ...]
    actor: str = Field(min_length=1)
    locked_at: datetime
    lock_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_lock(self) -> "CalibrationReferenceLock":
        process = CalibrationReferenceProcess.build()
        if self.process_digest != process.process_digest:
            raise ValueError("calibration lock uses a different process")
        if self.fixed_seeds != process.fixed_seeds:
            raise ValueError("calibration lock must use fixed Protocol seeds")
        baseline_keys = {item for item, _ in self.baseline_configuration_digests}
        if baseline_keys != set(process.baselines):
            raise ValueError("lock must contain every fixed calibration baseline")
        if any(not re.fullmatch(r"[0-9a-f]{64}", digest) for _, digest in [*self.baseline_configuration_digests, *self.prompt_digests]):
            raise ValueError("calibration digests must be SHA-256")
        if self.lock_digest != _digest(self._payload()):
            raise ValueError("calibration lock digest does not match content")
        return self

    def _payload(self) -> dict[str, object]:
        value = self.model_dump(mode="json")
        value.pop("lock_digest")
        value.pop("locked_at")
        return value

    @classmethod
    def build(cls, **values: object) -> "CalibrationReferenceLock":
        payload = dict(values)
        payload.setdefault("process_digest", CalibrationReferenceProcess.build().process_digest)
        payload.setdefault("fixed_seeds", (20260824, 20260825, 20260826))
        payload.setdefault("locked_at", datetime.now(UTC))
        payload["baseline_configuration_digests"] = tuple(sorted(payload["baseline_configuration_digests"], key=lambda item: item[0].value))  # type: ignore[index,union-attr]
        payload["prompt_digests"] = tuple(sorted(payload["prompt_digests"], key=lambda item: item[0].value))  # type: ignore[index,union-attr]
        digest_payload = _json_model_values({key: value for key, value in payload.items() if key != "locked_at"})
        return cls(**payload, lock_digest=_digest(digest_payload))


def _json_model_values(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_model_values(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_model_values(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    return value


class BenchmarkAdmissionStore:
    """Small append-only policy registry.  It never writes Bundle/Gold files."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put_process(self, process: CalibrationReferenceProcess) -> CalibrationReferenceProcess:
        path = self.root / "calibration-process.json"
        if path.exists():
            existing = CalibrationReferenceProcess.model_validate_json(path.read_text(encoding="utf-8"))
            if existing != process:
                raise BenchmarkAdmissionError("calibration reference process is immutable")
            return existing
        atomic_write_json(path, process.model_dump(mode="json"))
        return process

    def put_family(self, family: SourceFamilyRecord) -> SourceFamilyRecord:
        path = self.root / "source-families" / f"{safe_id(family.source_family_id)}.json"
        if path.exists():
            existing = SourceFamilyRecord.model_validate_json(path.read_text(encoding="utf-8"))
            if existing != family:
                raise BenchmarkAdmissionError("source family registry records are immutable")
            return existing
        atomic_write_json(path, family.model_dump(mode="json"))
        return family

    def put_lock(self, lock: CalibrationReferenceLock) -> CalibrationReferenceLock:
        path = self.root / "calibration-locks" / f"{safe_id(lock.lock_digest)}.json"
        if path.exists():
            existing = CalibrationReferenceLock.model_validate_json(path.read_text(encoding="utf-8"))
            if existing != lock:
                raise BenchmarkAdmissionError("calibration lock is immutable")
            return existing
        atomic_write_json(path, lock.model_dump(mode="json"))
        return lock

    def put_report(self, report: AdmissionReport) -> AdmissionReport:
        path = self.root / "reports" / report.scope / f"{report.report_digest}.json"
        if path.exists():
            existing = AdmissionReport.model_validate_json(path.read_text(encoding="utf-8"))
            if existing != report:
                raise BenchmarkAdmissionError("admission report digest collision")
            return existing
        atomic_write_json(path, report.model_dump(mode="json"))
        return report

    def append_source(self, source: DocumentSourceRecord) -> DocumentSourceRecord:
        root = self.root / "source-documents" / safe_id(source.source_document_id)
        history = [
            DocumentSourceRecord.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(root.glob("*.json"))
        ]
        if history:
            current = history[-1]
            if source.revision != current.revision + 1 or source.parent_revision_id != self._source_revision_id(current):
                raise BenchmarkAdmissionError("document source revisions must be append-only")
        elif source.revision != 1 or source.parent_revision_id is not None:
            raise BenchmarkAdmissionError("first source admission revision must be revision 1 without a parent")
        path = root / f"{source.revision:06d}.json"
        if path.exists():
            existing = DocumentSourceRecord.model_validate_json(path.read_text(encoding="utf-8"))
            if existing != source:
                raise BenchmarkAdmissionError("document source admission revision is immutable")
            return existing
        atomic_write_json(path, source.model_dump(mode="json"))
        return source

    def locks(self) -> list[CalibrationReferenceLock]:
        return [
            CalibrationReferenceLock.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted((self.root / "calibration-locks").glob("*.json"))
        ]

    @staticmethod
    def _source_revision_id(source: DocumentSourceRecord) -> str:
        return f"source-revision-{source.source_document_id}-{source.revision:06d}"


class BenchmarkAdmissionService:
    """Policy preflight coordinator; not a replacement for the formal release validator."""

    def __init__(self, root: Path, *, portfolios: BenchmarkPortfolioService) -> None:
        self.store = BenchmarkAdmissionStore(root)
        self.portfolios = portfolios

    def bootstrap(self) -> CalibrationReferenceProcess:
        return self.store.put_process(CalibrationReferenceProcess.build())

    def record_source(self, source: DocumentSourceRecord) -> DocumentSourceRecord:
        """Append a candidate/admitted source record without touching the file itself."""

        return self.store.append_source(source)

    def validate_source(
        self,
        source: DocumentSourceRecord,
        family: SourceFamilyRecord,
        *,
        development_family_ids: tuple[str, ...],
    ) -> AdmissionReport:
        findings: list[PolicyFinding] = []
        complete = (
            source.parsing_completeness == RepresentationStatus.COMPLETE
            and source.structure_completeness == RepresentationStatus.COMPLETE
            and source.evidence_locator_completeness == RepresentationStatus.COMPLETE
        )
        findings.append(
            _finding(
                "source.parse_structure_locator",
                PolicySeverity.ERROR,
                PolicyResult.PASS if complete else PolicyResult.FAIL,
                "DOCX source has complete parsing, structural preservation, and reliable evidence locators" if complete else "formal Gold source requires complete parsing, structure, and evidence locators",
                (source.source_document_id,),
            )
        )
        family_ok = source.source_family_id == family.source_family_id
        if source.independent_test_eligible:
            family_ok = family_ok and family.classification == SourceFamilyClass.HELD_OUT
        findings.append(
            _finding(
                "source.family_classification",
                PolicySeverity.ERROR,
                PolicyResult.PASS if family_ok else PolicyResult.FAIL,
                "source family classification matches its intended Portfolio usage" if family_ok else "independent-test source must be registered in an isolated held-out source family",
                (source.source_family_id,),
            )
        )
        by_family = {item.compared_source_family_id: item for item in source.development_similarity}
        missing = sorted(set(development_family_ids).difference(by_family)) if source.independent_test_eligible else []
        bad = [
            item for item in source.development_similarity
            if item.compared_source_family_id in development_family_ids
            and item.disposition in {SimilarityDisposition.EXACT_DUPLICATE, SimilarityDisposition.NEAR_DUPLICATE}
        ]
        unknown = [
            item for item in source.development_similarity
            if item.compared_source_family_id in development_family_ids and item.disposition == SimilarityDisposition.UNDETERMINED
        ]
        if missing or bad:
            result, severity, message = PolicyResult.FAIL, PolicySeverity.ERROR, "held-out source is missing development-family comparison or overlaps development data"
        elif unknown:
            result, severity, message = PolicyResult.HUMAN_REVIEW_REQUIRED, PolicySeverity.HUMAN_REVIEW, "source similarity cannot be determined automatically; independent human adjudication is required"
        else:
            result, severity, message = PolicyResult.PASS, PolicySeverity.ERROR, "held-out source family is explicitly isolated from all registered development families"
        findings.append(_finding("source.family_isolation_and_similarity", severity, result, message, tuple(sorted({*missing, *(item.compared_document_id for item in bad), *(item.compared_document_id for item in unknown)}))))
        status_ok = source.admission_status == SourceAdmissionStatus.ADMITTED
        findings.append(_finding("source.admission_status", PolicySeverity.ERROR, PolicyResult.PASS if status_ok else PolicyResult.HUMAN_REVIEW_REQUIRED, "source has an approved admission decision" if status_ok else "source remains candidate/quarantined until independent admission review", (source.source_document_id,)))
        return self.store.put_report(AdmissionReport.build(scope="source", subject_ids=(source.source_document_id,), subject_digests=(source.record_digest,), input_value={"source": source, "family": family, "development_family_ids": development_family_ids}, findings=tuple(findings)))

    def validate_case(self, value: CaseAdmissionInput) -> AdmissionReport:
        portfolio = self.portfolios.store.get(value.portfolio_id)
        slot = next((item for item in portfolio.slots if item.slot_id == value.slot_id), None)
        if slot is None:
            raise BenchmarkAdmissionError("case admission references an unknown Portfolio slot")
        findings: list[PolicyFinding] = []
        source_preflight = value.source_admission_report
        source_report_ok = (
            source_preflight is not None
            and source_preflight.scope == "source"
            and value.source.source_document_id in source_preflight.subject_ids
            and value.source.record_digest in source_preflight.subject_digests
            and source_preflight.eligible_to_proceed
        )
        scope_finding = self._reliable_evidence_scope(value)
        scope_ok = scope_finding.result == PolicyResult.PASS
        # Held-out material remains whole-source admitted and isolated.  A
        # development pilot may instead use an explicit complete Canonical
        # subset; that does not launder the source record into "complete".
        source_required = (
            value.source.independent_test_eligible and source_report_ok
            if slot.usage == PortfolioUsage.HELD_OUT
            else source_report_ok or scope_ok
        )
        source_ok = source_required and value.source.canonical_document_digest == value.canonical.manifest.canonical_digest
        findings.append(_finding("case.source_and_slot_binding", PolicySeverity.ERROR, PolicyResult.PASS if source_ok else PolicyResult.FAIL, "Case is bound to a Portfolio slot and matching admitted canonical source" if source_ok else "Case source/Portfolio binding is incomplete or does not match canonical digest", (value.slot_id, value.source.source_document_id)))
        findings.append(scope_finding)
        if value.case.draft.source_digest != value.canonical.manifest.source_sha256 or value.gold.case_id != value.case.case_id:
            findings.append(_finding("case.gold_lineage", PolicySeverity.ERROR, PolicyResult.FAIL, "Case/Gold/source lineage is inconsistent", (value.case.case_revision_id, value.gold.gold_revision_id)))
        else:
            findings.append(_finding("case.gold_lineage", PolicySeverity.ERROR, PolicyResult.PASS, "Case and independent Gold share canonical source lineage", (value.case.case_revision_id, value.gold.gold_revision_id)))
        reachable = self._evidence_reachability(value.gold, value.canonical)
        findings.append(reachable)
        findings.append(self._necessity(value.gold, value.necessity_checks))
        findings.append(self._negative_scope(value.gold, value.canonical))
        findings.append(self._multi_hop(slot, value.gold))
        findings.append(self._answer_leakage(value.case, value.gold))
        findings.append(self._question_similarity(slot, value.question_similarity))
        findings.append(self._model_proposal_status(value.case, value.gold, value.model_assistance, value.review_attestations))
        findings.append(self._human_review(slot, value.case, value.gold, value.review_attestations))
        return self.store.put_report(AdmissionReport.build(scope="case", subject_ids=(value.case.case_revision_id, value.gold.gold_revision_id, value.slot_id), subject_digests=(value.source.record_digest, value.canonical.manifest.canonical_digest), input_value=value, findings=tuple(findings)))

    @staticmethod
    def _reliable_evidence_scope(value: CaseAdmissionInput) -> PolicyFinding:
        """Require a complete, source-matching scope when it is supplied."""

        scope = value.evidence_scope
        if scope is None:
            return _finding(
                "case.reliable_canonical_evidence_scope",
                PolicySeverity.INFO,
                PolicyResult.NOT_APPLICABLE,
                "no scoped Canonical evidence selection supplied; whole-source admission is required",
            )
        known = {item.object_id: item for item in value.canonical.objects}
        selected = set(scope.canonical_object_ids)
        required = {
            *value.case.draft.source_object_ids,
            *(item.canonical_object_id for item in value.gold.payload.evidence),
        }
        errors: list[str] = []
        if scope.source_document_id != value.source.source_document_id:
            errors.append("scope source document does not match Case source")
        if scope.canonical_document_digest != value.canonical.manifest.canonical_digest:
            errors.append("scope canonical digest does not match Canonical document")
        missing = required.difference(selected)
        if missing:
            errors.append("scope does not include every Case/Gold evidence object")
        unsafe = sorted(
            object_id
            for object_id in selected
            if object_id not in known
            or not known[object_id].gold_evidence_eligible
        )
        if unsafe:
            errors.append("scope contains missing, incomplete, or Gold-prohibited Canonical objects")
        return _finding(
            "case.reliable_canonical_evidence_scope",
            PolicySeverity.ERROR,
            PolicyResult.FAIL if errors else PolicyResult.PASS,
            "explicit Canonical evidence scope is complete and exactly traceable"
            if not errors
            else "; ".join(errors),
            tuple(sorted({*missing, *unsafe})),
        )

    @staticmethod
    def _evidence_reachability(gold: GoldRevision, canonical: CanonicalDocument) -> PolicyFinding:
        known = {item.object_id: item for item in canonical.objects}
        bad = [
            item.canonical_object_id
            for item in gold.payload.evidence
            if item.canonical_object_id not in known
            or not known[item.canonical_object_id].gold_evidence_eligible
        ]
        return _finding("gold.evidence_reachability", PolicySeverity.ERROR, PolicyResult.FAIL if bad else PolicyResult.PASS, "Gold evidence is reachable at Gold-eligible canonical locators" if not bad else "Gold cites missing, incomplete, or Gold-prohibited canonical evidence", tuple(sorted(set(bad))))

    @staticmethod
    def _necessity(gold: GoldRevision, checks: tuple[MsesNecessityCheck, ...]) -> PolicyFinding:
        required = {
            (path.path_id, clause.clause_id, tuple(sorted(clause.alternatives)))
            for path in gold.payload.mses_paths
            for clause in path.clauses
        }
        available = {(item.path_id, item.clause_id, tuple(sorted(item.alternative_evidence_ids))): item for item in checks}
        missing = sorted(f"{path}/{clause}" for path, clause, _ in required.difference(available))
        bad = sorted(f"{item.path_id}/{item.clause_id}" for item in checks if item.necessary is False)
        undetermined = sorted(f"{item.path_id}/{item.clause_id}" for item in checks if item.necessary is None)
        if missing or bad:
            return _finding("gold.mses_minimality", PolicySeverity.ERROR, PolicyResult.FAIL, "every MSES clause needs a positive necessity check and no redundant clause", tuple(missing + bad))
        if undetermined:
            return _finding("gold.mses_minimality", PolicySeverity.HUMAN_REVIEW, PolicyResult.HUMAN_REVIEW_REQUIRED, "MSES clause necessity cannot be decided automatically", tuple(undetermined))
        return _finding("gold.mses_minimality", PolicySeverity.ERROR, PolicyResult.PASS, "every MSES clause has an audited necessity check")

    @staticmethod
    def _multi_hop(slot: PortfolioSlot, gold: GoldRevision) -> PolicyFinding:
        requires = slot.evidence_requirement == EvidenceRequirement.MULTI_HOP
        valid = not requires or bool(gold.payload.dependencies)
        return _finding("gold.multi_hop_dependency", PolicySeverity.ERROR, PolicyResult.PASS if valid else PolicyResult.FAIL, "multi-hop slot has typed dependency graph" if valid else "multi-hop Portfolio slot requires a typed Gold dependency graph", (gold.gold_revision_id,))

    @staticmethod
    def _negative_scope(gold: GoldRevision, canonical: CanonicalDocument) -> PolicyFinding:
        if gold.payload.answer.kind != "abstain":
            return _finding("gold.negative_scope", PolicySeverity.INFO, PolicyResult.NOT_APPLICABLE, "answerable Gold does not use an unanswerable scope")
        known = {item.object_id: item for item in canonical.objects}
        cited = {item.canonical_object_id for item in gold.payload.evidence if item.role == EvidenceRole.NEGATIVE_SCOPE}
        scoped = set(gold.payload.negative_scope_object_ids)
        valid = bool(scoped) and scoped.issubset(cited) and all(
            item in known and known[item].gold_evidence_eligible
            for item in scoped
        ) and bool(gold.payload.negative_rationale)
        return _finding("gold.negative_scope", PolicySeverity.ERROR, PolicyResult.PASS if valid else PolicyResult.FAIL, "unanswerable Gold defines a complete, evidence-backed negative scope" if valid else "unanswerable Gold needs a complete canonical negative scope and rationale", tuple(sorted(scoped.difference(cited))))

    @staticmethod
    def _answer_leakage(case: CaseRevision, gold: GoldRevision) -> PolicyFinding:
        if gold.payload.answer.kind == "abstain":
            return _finding("case.answer_leakage", PolicySeverity.INFO, PolicyResult.NOT_APPLICABLE, "abstention Gold has no canonical answer string")
        answer = gold.payload.answer.canonical
        candidates = answer if isinstance(answer, tuple) else (answer,)
        question = re.sub(r"\s+", "", case.draft.question).casefold()
        leaked = any(
            isinstance(item, str) and len(re.sub(r"\s+", "", item)) >= 3 and re.sub(r"\s+", "", item).casefold() in question
            for item in candidates
        )
        return _finding("case.answer_leakage", PolicySeverity.ERROR, PolicyResult.FAIL if leaked else PolicyResult.PASS, "question has no direct canonical-answer leak" if not leaked else "question contains a canonical Gold answer", (case.case_revision_id,))

    @staticmethod
    def _question_similarity(slot: PortfolioSlot, comparisons: tuple[QuestionSimilarityAssessment, ...]) -> PolicyFinding:
        heldout = slot.usage == PortfolioUsage.HELD_OUT
        dev = [item for item in comparisons if item.compared_usage == PortfolioUsage.DEVELOPMENT]
        duplicates = [item for item in comparisons if item.disposition in {SimilarityDisposition.EXACT_DUPLICATE, SimilarityDisposition.NEAR_DUPLICATE}]
        unknown = [item for item in comparisons if item.disposition == SimilarityDisposition.UNDETERMINED]
        if duplicates:
            return _finding("case.duplicate_and_contamination", PolicySeverity.ERROR, PolicyResult.FAIL, "duplicate/near-duplicate question comparison detected", tuple(item.compared_case_id for item in duplicates))
        if heldout and not dev:
            return _finding("case.duplicate_and_contamination", PolicySeverity.HUMAN_REVIEW, PolicyResult.HUMAN_REVIEW_REQUIRED, "held-out question needs development-case contamination comparison", ())
        if unknown:
            return _finding("case.duplicate_and_contamination", PolicySeverity.HUMAN_REVIEW, PolicyResult.HUMAN_REVIEW_REQUIRED, "question similarity requires human semantic review", tuple(item.compared_case_id for item in unknown))
        return _finding("case.duplicate_and_contamination", PolicySeverity.ERROR, PolicyResult.PASS, "no duplicate, near-duplicate, or unresolved contamination comparison")

    @staticmethod
    def _model_proposal_status(case: CaseRevision, gold: GoldRevision, assistance: tuple[ModelAssistanceRecord, ...], attestations: tuple[AdmissionChecklistAttestation, ...]) -> PolicyFinding:
        generated = case.draft.origin.kind in {OriginKind.SYNTHETIC, OriginKind.SEMI_SYNTHETIC} or gold.origin.kind in {OriginKind.SYNTHETIC, OriginKind.SEMI_SYNTHETIC}
        malformed = [item.assistance_id for item in assistance if item.case_id != case.case_id or not item.proposal_only]
        if malformed:
            return _finding("model.output_proposal_only", PolicySeverity.ERROR, PolicyResult.FAIL, "model assistance must be traceable to the Case and remain proposal-only", tuple(malformed))
        independent = any(
            _attestation_matches_lineage(item, case, gold)
            and item.reviewer_identity not in {case.actor, gold.actor}
            and item.complete
            for item in attestations
        )
        if generated and not assistance:
            return _finding("model.output_proposal_only", PolicySeverity.HUMAN_REVIEW, PolicyResult.HUMAN_REVIEW_REQUIRED, "model-origin Case/Gold needs a permitted-use assistance record and independent review", (case.case_revision_id, gold.gold_revision_id))
        if generated and not independent:
            return _finding("model.output_proposal_only", PolicySeverity.HUMAN_REVIEW, PolicyResult.HUMAN_REVIEW_REQUIRED, "model output is only a proposal until independently reviewed", (case.case_revision_id, gold.gold_revision_id))
        return _finding("model.output_proposal_only", PolicySeverity.ERROR, PolicyResult.PASS, "model assistance, if any, is gated by independent review rather than auto-Gold promotion")

    @staticmethod
    def _human_review(slot: PortfolioSlot, case: CaseRevision, gold: GoldRevision, attestations: tuple[AdmissionChecklistAttestation, ...]) -> PolicyFinding:
        high_risk = (
            slot.evidence_requirement == EvidenceRequirement.MULTI_HOP
            or slot.source_type.value == "adversarial"
            or len(gold.payload.mses_paths) > 1
            or any(item.role in {EvidenceRole.CONFLICTING, EvidenceRole.NEGATIVE_SCOPE} for item in gold.payload.evidence)
            or any(item.value != "none" for item in slot.structured_content)
        )
        required = 2 if high_risk else 1
        valid = [
            item
            for item in attestations
            if _attestation_matches_lineage(item, case, gold)
            and item.reviewer_identity not in {case.actor, gold.actor}
            and item.complete
        ]
        identities = {item.reviewer_identity for item in valid}
        if len(identities) < required:
            return _finding("review.independent_admission_checklist", PolicySeverity.HUMAN_REVIEW, PolicyResult.HUMAN_REVIEW_REQUIRED, f"{ReviewTier.HEIGHTENED.value if high_risk else ReviewTier.STANDARD.value} independent admission review checklist is required", (case.case_revision_id, gold.gold_revision_id))
        return _finding("review.independent_admission_checklist", PolicySeverity.ERROR, PolicyResult.PASS, "independent admission checklist covers naturalness, ambiguity, answer, evidence, alternatives, and difficulty")


def _finding(rule_id: str, severity: PolicySeverity, result: PolicyResult, message: str, affected: tuple[str, ...] = ()) -> PolicyFinding:
    return PolicyFinding(rule_id=rule_id, severity=severity, result=result, message=message, affected_ids=tuple(sorted(set(affected))))


def _attestation_matches_lineage(
    attestation: AdmissionChecklistAttestation,
    case: CaseRevision,
    gold: GoldRevision,
) -> bool:
    """Accept exact current revisions or an honest stable-entity lineage link."""

    return (
        attestation.reviewed_case_revision_id == case.case_revision_id
        and attestation.reviewed_gold_revision_id == gold.gold_revision_id
    ) or (
        attestation.case_id == case.case_id and attestation.gold_id == gold.gold_id
    )
