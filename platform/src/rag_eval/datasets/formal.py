"""The Platform's single formal Dataset validator and immutable release lineage.

This contract sits above the versioned Canonical Data Model and the append-only
Authoring Ledger. Native execution resolves exactly one release-pinned original
DOCX plus its Platform-owned Benchmark and Canonical snapshots.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Literal

from lxml import etree
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.authoring.ledger import (
    LEDGER_SCHEMA_VERSION,
    Adjudication,
    Approval,
    AuthoringLedger,
    AuthoringOrigin,
    AuthoringRelease,
    CaseRevision,
    EvidenceRole,
    GoldRevision,
    LedgerError,
    LifecycleState,
    Review,
)
from rag_eval.authoring.models import AuthoringDataset, CanonicalView
from rag_eval.authoring.storage import AuthoringWorkspaceStore
from rag_eval.contracts.benchmark import (
    BenchmarkAnswerV2,
    BenchmarkCaseV2,
    BenchmarkEvidenceDependencyV2,
    BenchmarkEvidenceV2,
    BenchmarkGoldV2,
    BenchmarkMsesClauseV2,
    BenchmarkMsesPathV2,
    BenchmarkSourceIdentityV2,
    NativeBenchmarkReleaseV2,
    benchmark_case_selection_id,
    native_canonical_catalog_bytes,
    native_benchmark_snapshot_digest,
)
from rag_eval.contracts.canonical import (
    CANONICAL_GOLD_ELIGIBILITY_POLICY_IDENTITY,
    CANONICAL_SCHEMA_VERSION,
    LEGACY_CANONICAL_SCHEMA_VERSION,
    PREVIOUS_CANONICAL_SCHEMA_VERSION,
    CanonicalConformanceReport,
    CanonicalDocument,
    CanonicalObject,
    CanonicalRelation,
    RepresentationStatus,
)
from rag_eval.storage.atomic import atomic_write_bytes, atomic_write_json
from rag_eval.storage.ids import safe_id


FORMAL_VALIDATOR_VERSION = "formal-dataset-validator/2.0"
FORMAL_REPORT_SCHEMA_VERSION = "formal-validation-report/1.0"
FORMAL_RELEASE_SCHEMA_VERSION = "formal-dataset-release/2.0"
FORMAL_READ_MODEL_SCHEMA_VERSION = "formal-release-read-model/1"
_WORDPROCESSINGML = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class FormalDatasetError(ValueError):
    """The formal validation/release contract cannot be satisfied."""


class FormalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RuleSeverity(StrEnum):
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"


class RuleResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _json_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [_json_value(item) for item in value]
    return value


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InputDigest(FormalModel):
    name: str = Field(min_length=1)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class RuleEvidence(FormalModel):
    evidence_type: str = Field(min_length=1)
    identifier: str = Field(min_length=1)
    digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ValidationFinding(FormalModel):
    rule_id: str = Field(min_length=1)
    severity: RuleSeverity
    result: RuleResult
    message: str = Field(min_length=1)
    affected_ids: tuple[str, ...] = ()
    evidence: tuple[RuleEvidence, ...] = ()


class ValidationReport(FormalModel):
    schema_version: Literal[FORMAL_REPORT_SCHEMA_VERSION] = FORMAL_REPORT_SCHEMA_VERSION
    validator_version: Literal[FORMAL_VALIDATOR_VERSION] = FORMAL_VALIDATOR_VERSION
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    document_revision_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    case_revision_ids: tuple[str, ...] = ()
    gold_revision_ids: tuple[str, ...] = ()
    input_digests: tuple[InputDigest, ...]
    findings: tuple[ValidationFinding, ...]
    report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_digest_and_order(self) -> "ValidationReport":
        if tuple(sorted(self.case_revision_ids)) != self.case_revision_ids:
            raise ValueError("case revision IDs must be sorted")
        if tuple(sorted(self.gold_revision_ids)) != self.gold_revision_ids:
            raise ValueError("Gold revision IDs must be sorted")
        if tuple(sorted(self.input_digests, key=lambda item: item.name)) != self.input_digests:
            raise ValueError("input digests must be sorted")
        if tuple(sorted(self.findings, key=lambda item: item.rule_id)) != self.findings:
            raise ValueError("validation findings must be sorted by rule ID")
        expected = _canonical_digest(self._digest_payload())
        if self.report_digest != expected:
            raise ValueError("validation report digest does not match report content")
        return self

    def _digest_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "validator_version": self.validator_version,
            "dataset_id": self.dataset_id,
            "document_revision_id": self.document_revision_id,
            "case_revision_ids": self.case_revision_ids,
            "gold_revision_ids": self.gold_revision_ids,
            "input_digests": [item.model_dump(mode="json") for item in self.input_digests],
            "findings": [item.model_dump(mode="json") for item in self.findings],
        }

    @classmethod
    def build(
        cls,
        *,
        dataset_id: str,
        document_revision_id: str | None,
        case_revision_ids: tuple[str, ...],
        gold_revision_ids: tuple[str, ...],
        input_digests: tuple[InputDigest, ...],
        findings: tuple[ValidationFinding, ...],
    ) -> "ValidationReport":
        values = {
            "dataset_id": dataset_id,
            "document_revision_id": document_revision_id,
            "case_revision_ids": tuple(sorted(case_revision_ids)),
            "gold_revision_ids": tuple(sorted(gold_revision_ids)),
            "input_digests": tuple(sorted(input_digests, key=lambda item: item.name)),
            "findings": tuple(sorted(findings, key=lambda item: item.rule_id)),
        }
        digest = _canonical_digest(
            {
                "schema_version": FORMAL_REPORT_SCHEMA_VERSION,
                "validator_version": FORMAL_VALIDATOR_VERSION,
                **{key: [item.model_dump(mode="json") for item in value] if key in {"input_digests", "findings"} else value for key, value in values.items()},
            }
        )
        return cls(**values, report_digest=digest)

    @property
    def has_errors(self) -> bool:
        return any(
            item.severity == RuleSeverity.ERROR and item.result == RuleResult.FAIL
            for item in self.findings
        )


class ReleaseSchemaVersions(FormalModel):
    # Releases are immutable historical records.  New releases default to the
    # current Canonical schema, while the reader deliberately retains every
    # shipped Canonical generation needed by stored release lineage.
    canonical_schema_version: Literal[
        LEGACY_CANONICAL_SCHEMA_VERSION,
        PREVIOUS_CANONICAL_SCHEMA_VERSION,
        CANONICAL_SCHEMA_VERSION,
    ] = CANONICAL_SCHEMA_VERSION
    ledger_schema_version: Literal[LEDGER_SCHEMA_VERSION] = LEDGER_SCHEMA_VERSION
    validator_version: Literal[FORMAL_VALIDATOR_VERSION] = FORMAL_VALIDATOR_VERSION
    release_schema_version: Literal[FORMAL_RELEASE_SCHEMA_VERSION] = FORMAL_RELEASE_SCHEMA_VERSION


class ReleaseDocumentPin(FormalModel):
    document_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    document_id: str = Field(min_length=1)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_identity: str = Field(min_length=1)
    canonicalizer_identity: str = Field(min_length=1)
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReleaseCasePin(FormalModel):
    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    case_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ReleaseGoldPin(FormalModel):
    gold_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    gold_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    case_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    origin_kind: str = Field(min_length=1)
    origin_configuration_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ReleaseReviewPin(FormalModel):
    review_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    target_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    reviewer_identity: str = Field(min_length=1)
    decision: str = Field(min_length=1)


class ReleaseApprovalPin(FormalModel):
    approval_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    target_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    approver_identity: str = Field(min_length=1)
    approver_role: str = Field(min_length=1)


class ReleaseOriginPin(FormalModel):
    origin_kind: str = Field(min_length=1)
    trust_level: str = Field(min_length=1)
    generator_identity: str | None = None
    generator_version: str | None = None
    configuration_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_world: str | None = None
    source_document_ids: tuple[str, ...] = ()


class ReleaseLedgerState(FormalModel):
    ledger_selection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_event_ids: tuple[str, ...] = ()
    authoring_freeze_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")


class DatasetRelease(FormalModel):
    schema_version: Literal[FORMAL_RELEASE_SCHEMA_VERSION] = FORMAL_RELEASE_SCHEMA_VERSION
    release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    # Old releases predate this product-facing name.  Keeping it optional
    # leaves their immutable identities readable and unchanged.
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    release_version: str = Field(min_length=1)
    parent_release_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    document: ReleaseDocumentPin
    cases: tuple[ReleaseCasePin, ...] = Field(min_length=1)
    gold: tuple[ReleaseGoldPin, ...] = Field(min_length=1)
    validation_report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_report_version: Literal[FORMAL_VALIDATOR_VERSION] = FORMAL_VALIDATOR_VERSION
    schema_versions: ReleaseSchemaVersions
    ledger_state: ReleaseLedgerState
    reviews: tuple[ReleaseReviewPin, ...]
    approvals: tuple[ReleaseApprovalPin, ...] = Field(min_length=1)
    origins: tuple[ReleaseOriginPin, ...]
    created_by: str = Field(min_length=1)
    created_at: datetime
    release_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_pins_and_digest(self) -> "DatasetRelease":
        if tuple(sorted(self.cases, key=lambda item: item.case_id)) != self.cases:
            raise ValueError("release Case pins must be sorted")
        if tuple(sorted(self.gold, key=lambda item: item.gold_id)) != self.gold:
            raise ValueError("release Gold pins must be sorted")
        case_ids = [item.case_id for item in self.cases]
        gold_case_ids = [item.case_id for item in self.gold]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("release Case pins must have unique Case IDs")
        if len(gold_case_ids) != len(set(gold_case_ids)):
            raise ValueError("release Gold pins must have unique Case IDs")
        if {item.case_id for item in self.cases} != {item.case_id for item in self.gold}:
            raise ValueError("every released Case needs exactly one released Gold")
        if any(item.case_revision_id not in {case.case_revision_id for case in self.cases} for item in self.gold):
            raise ValueError("Gold pins must reference pinned Case revisions")
        expected = _canonical_digest(self._digest_payload())
        if self.release_digest != expected:
            raise ValueError("release digest does not match immutable release pins")
        return self

    def _digest_payload(self) -> dict[str, object]:
        value = self.model_dump(mode="json")
        value.pop("release_digest", None)
        value.pop("release_id", None)
        if value.get("display_name") is None:
            value.pop("display_name", None)
        # Audit time is recorded but does not change the reproducible identity
        # of an otherwise identical frozen release.
        value.pop("created_at", None)
        return value

    @classmethod
    def build(cls, **values: object) -> "DatasetRelease":
        payload = dict(values)
        payload.setdefault("validation_report_version", FORMAL_VALIDATOR_VERSION)
        payload["cases"] = tuple(sorted(payload["cases"], key=lambda item: item.case_id))  # type: ignore[index,union-attr]
        payload["gold"] = tuple(sorted(payload["gold"], key=lambda item: item.gold_id))  # type: ignore[index,union-attr]
        identity_payload = {
            "schema_version": FORMAL_RELEASE_SCHEMA_VERSION,
            **{key: value for key, value in payload.items() if key not in {"created_at", "release_id"}},
        }
        release_digest = _canonical_digest(identity_payload)
        payload["release_id"] = f"dataset-release-{release_digest[:24]}"
        payload["release_digest"] = release_digest
        return cls(**payload)


class FormalReleaseContent(FormalModel):
    """Read-only local inspection view of one immutable formal Release.

    This is deliberately a projection, not a second Authoring or Gold
    authority.  The source records remain the pinned Ledger revisions and the
    Canonical snapshot; this view merely joins them for the product UI.
    """

    release: dict[str, object]
    cases: tuple[dict[str, object], ...]


class FormalDocumentCell(FormalModel):
    """A readable cell in the release's source-faithful document view.

    ``object_ids`` are used only by the local product UI to apply a highlight;
    the view intentionally contains no digests or authoring metadata.
    """

    text: str
    row: int = Field(ge=1)
    column: int = Field(ge=1)
    row_span: int = Field(default=1, ge=1)
    column_span: int = Field(default=1, ge=1)
    object_ids: tuple[str, ...] = ()


class FormalDocumentBlock(FormalModel):
    """One document-order block reconstructed from the pinned Canonical view."""

    block_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    text: str = ""
    document_order: int = Field(ge=0)
    object_ids: tuple[str, ...] = ()
    cells: tuple[FormalDocumentCell, ...] = ()
    heading_level: int | None = Field(default=None, ge=1, le=9)
    page_break_before: bool = False
    list_level: int | None = Field(default=None, ge=0, le=9)


class FormalDocumentView(FormalModel):
    """Compact source-faithful reading view for a frozen release.

    This is deliberately a UI projection of the immutable Canonical snapshot,
    not another source of truth.  Tables retain logical cell topology and all
    blocks retain their Canonical object IDs for evidence highlighting.
    """

    document_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    blocks: tuple[FormalDocumentBlock, ...]


class ReleaseChangeSet(FormalModel):
    parent_release_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    added_case_ids: tuple[str, ...] = ()
    removed_case_ids: tuple[str, ...] = ()
    changed_case_ids: tuple[str, ...] = ()
    added_gold_ids: tuple[str, ...] = ()
    removed_gold_ids: tuple[str, ...] = ()
    changed_gold_ids: tuple[str, ...] = ()
    document_changed: bool = False


class ReleaseLineage(FormalModel):
    release: DatasetRelease
    source: ReleaseDocumentPin
    cases: tuple[ReleaseCasePin, ...]
    gold: tuple[ReleaseGoldPin, ...]
    reviews: tuple[ReleaseReviewPin, ...]
    approvals: tuple[ReleaseApprovalPin, ...]
    origins: tuple[ReleaseOriginPin, ...]
    changes_from_parent: ReleaseChangeSet


class RebuildVerification(FormalModel):
    release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    reproducible: bool
    validation_report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_validation_report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str | None = None


class FormalValidationReportStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, report: ValidationReport) -> ValidationReport:
        path = self.root / f"{report.report_digest}.json"
        if path.exists():
            existing = ValidationReport.model_validate_json(path.read_text(encoding="utf-8"))
            if existing != report:
                raise FormalDatasetError("validation report digest collision")
            return existing
        atomic_write_json(path, report.model_dump(mode="json"))
        return report

    def get(self, digest: str) -> ValidationReport:
        return ValidationReport.model_validate_json((self.root / f"{digest}.json").read_text(encoding="utf-8"))


class DatasetReleaseStore:
    """Global immutable store; this is the only formal Dataset Release authority."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.reports = FormalValidationReportStore(root / "validation-reports")

    def put(self, release: DatasetRelease) -> DatasetRelease:
        for existing in self.list(include_removed=True):
            if existing.dataset_id == release.dataset_id and existing.release_version == release.release_version:
                if existing.release_digest != release.release_digest:
                    raise FormalDatasetError("release version is immutable; create a successor version")
                if self.is_removed(existing.release_id):
                    raise FormalDatasetError(
                        "release version was removed from the product catalog; create a successor version"
                    )
                return existing
        path = self.root / f"{release.release_id}.json"
        if path.exists():
            existing = DatasetRelease.model_validate_json(path.read_text(encoding="utf-8"))
            if existing.release_digest != release.release_digest:
                raise FormalDatasetError("release ID collision")
            return existing
        atomic_write_json(path, release.model_dump(mode="json"))
        return release

    def get(self, release_id: str) -> DatasetRelease:
        return DatasetRelease.model_validate_json(
            (self.root / f"{safe_id(release_id)}.json").read_text(encoding="utf-8")
        )

    def list(self, *, include_removed: bool = False) -> list[DatasetRelease]:
        values = [
            DatasetRelease.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.root.glob("dataset-release-*.json"))
        ]
        if include_removed:
            return values
        return [item for item in values if not self.is_removed(item.release_id)]

    def is_removed(self, release_id: str) -> bool:
        return self._removed_path(release_id).is_file()

    def remove_from_catalog(self, release_id: str, *, actor: str) -> DatasetRelease:
        """Hide one immutable release from the editable product catalog.

        The frozen release files, source snapshot, and historical-run lineage
        stay intact.  Deletion therefore never mutates the release or breaks a
        past run; it only removes the version from the current dataset list.
        """

        release = self.get(release_id)
        path = self._removed_path(release_id)
        value = {
            "release_id": release.release_id,
            "release_digest": release.release_digest,
            "actor": actor.strip() or "local-user",
            "removed_at": datetime.now(UTC).isoformat(),
        }
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing.get("release_digest") != release.release_digest:
                raise FormalDatasetError("release removal marker does not match release digest")
            return release
        root = path.parent
        root.mkdir(exist_ok=True)
        atomic_write_json(path, value)
        return release

    def _removed_path(self, release_id: str) -> Path:
        return self.root / "removed-from-catalog" / f"{safe_id(release_id)}.json"

    def put_canonical_snapshot(self, release: DatasetRelease, document: CanonicalDocument) -> None:
        root = self.root / "canonical-snapshots"
        root.mkdir(exist_ok=True)
        path = root / f"{release.release_id}.json"
        value = document.model_dump(mode="json")
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != value:
                raise FormalDatasetError("canonical snapshot is immutable")
            return
        atomic_write_json(path, value)

    def canonical_snapshot(self, release_id: str) -> CanonicalDocument:
        path = self.root / "canonical-snapshots" / f"{safe_id(release_id)}.json"
        return CanonicalDocument.model_validate_json(path.read_text(encoding="utf-8"))

    def put_source_snapshot(self, release: DatasetRelease, source: Path) -> None:
        if not source.is_file():
            raise FormalDatasetError("release source document is missing")
        payload = source.read_bytes()
        if hashlib.sha256(payload).hexdigest() != release.document.source_digest:
            raise FormalDatasetError("release source document digest does not match pin")
        root = self.root / "source-snapshots"
        root.mkdir(exist_ok=True)
        path = root / f"{release.release_id}.docx"
        if path.exists():
            if path.read_bytes() != payload:
                raise FormalDatasetError("source snapshot is immutable")
            return
        atomic_write_bytes(path, payload)

    def source_snapshot(self, release_id: str) -> Path:
        path = self.root / "source-snapshots" / f"{safe_id(release_id)}.docx"
        if not path.is_file():
            raise FileNotFoundError(path.name)
        return path

    def put_payload_snapshots(
        self,
        release: DatasetRelease,
        *,
        cases: tuple[CaseRevision, ...],
        gold: tuple[GoldRevision, ...],
        case_history: dict[str, tuple[CaseRevision, ...]],
        gold_history: dict[str, tuple[GoldRevision, ...]],
        reviews: tuple[Review, ...],
        approvals: tuple[Approval, ...],
        adjudications: tuple[Adjudication, ...],
    ) -> None:
        """Persist the immutable payload needed to read a release later.

        A formal release must remain readable even after its editable
        authoring workspace is archived or removed.  The release pins still
        carry the identity and digest contract; this sidecar carries the
        already-frozen Case/Gold payloads and their audit lineage.
        """

        content = self.payload_snapshot_content(
            cases=cases,
            gold=gold,
            case_history=case_history,
            gold_history=gold_history,
            reviews=reviews,
            approvals=approvals,
            adjudications=adjudications,
        )
        payload_digest = _canonical_digest(content)
        if payload_digest != release.payload_snapshot_digest:
            raise FormalDatasetError(
                "release payload snapshot digest does not match its immutable pin"
            )
        root = self.root / "payload-snapshots"
        root.mkdir(exist_ok=True)
        path = root / f"{safe_id(release.release_id)}.json"
        value = {
            "release_id": release.release_id,
            "release_digest": release.release_digest,
            "payload_snapshot_digest": payload_digest,
            **content,
        }
        if path.is_file():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != value:
                raise FormalDatasetError("release payload snapshot is immutable")
            return
        atomic_write_json(path, value)

    @staticmethod
    def payload_snapshot_content(
        *,
        cases: tuple[CaseRevision, ...],
        gold: tuple[GoldRevision, ...],
        case_history: dict[str, tuple[CaseRevision, ...]],
        gold_history: dict[str, tuple[GoldRevision, ...]],
        reviews: tuple[Review, ...],
        approvals: tuple[Approval, ...],
        adjudications: tuple[Adjudication, ...],
    ) -> dict[str, object]:
        """Canonical content protected by ``DatasetRelease`` identity."""

        return {
            "cases": [item.model_dump(mode="json") for item in sorted(cases, key=lambda item: item.case_revision_id)],
            "gold": [item.model_dump(mode="json") for item in sorted(gold, key=lambda item: item.gold_revision_id)],
            "case_history": {
                key: [item.model_dump(mode="json") for item in sorted(items, key=lambda item: item.revision)]
                for key, items in sorted(case_history.items())
            },
            "gold_history": {
                key: [item.model_dump(mode="json") for item in sorted(items, key=lambda item: item.revision)]
                for key, items in sorted(gold_history.items())
            },
            "reviews": [item.model_dump(mode="json") for item in sorted(reviews, key=lambda item: item.review_id)],
            "approvals": [item.model_dump(mode="json") for item in sorted(approvals, key=lambda item: item.approval_id)],
            "adjudications": [item.model_dump(mode="json") for item in sorted(adjudications, key=lambda item: item.adjudication_id)],
        }

    @classmethod
    def payload_snapshot_digest(
        cls,
        *,
        cases: tuple[CaseRevision, ...],
        gold: tuple[GoldRevision, ...],
        case_history: dict[str, tuple[CaseRevision, ...]],
        gold_history: dict[str, tuple[GoldRevision, ...]],
        reviews: tuple[Review, ...],
        approvals: tuple[Approval, ...],
        adjudications: tuple[Adjudication, ...],
    ) -> str:
        return _canonical_digest(
            cls.payload_snapshot_content(
                cases=cases,
                gold=gold,
                case_history=case_history,
                gold_history=gold_history,
                reviews=reviews,
                approvals=approvals,
                adjudications=adjudications,
            )
        )

    def payload_snapshots(self, release_id: str) -> dict[str, object]:
        path = self.root / "payload-snapshots" / f"{safe_id(release_id)}.json"
        if not path.is_file():
            raise FileNotFoundError(path.name)
        return json.loads(path.read_text(encoding="utf-8"))

    def put_read_models(
        self,
        release: DatasetRelease,
        *,
        content: FormalReleaseContent,
        document: FormalDocumentView,
    ) -> None:
        """Persist disposable, local read models derived from a frozen release.

        The canonical snapshot remains the immutable audit and reproducibility
        authority.  These files intentionally contain only what interactive
        product views need, so opening a dataset never has to parse the full
        Canonical object graph again.
        """

        self.put_case_read_models(release, content=content)
        self.put_document_read_model(release, document=document)

    def put_case_read_models(
        self, release: DatasetRelease, *, content: FormalReleaseContent
    ) -> None:
        """Persist the lightweight Case navigation and per-Case projections."""

        root = self.root / "read-models" / safe_id(release.release_id)
        cases_root = root / "cases"
        cases_root.mkdir(parents=True, exist_ok=True)
        header = {
            "schema_version": FORMAL_READ_MODEL_SCHEMA_VERSION,
            "release_id": release.release_id,
            "release_digest": release.release_digest,
        }
        index = {
            "release": content.release,
            "cases": [
                {
                    "case_id": item["case_id"],
                    "question": item["question"],
                    "language": item["language"],
                    "lifecycle": item["lifecycle"],
                }
                for item in content.cases
            ],
        }
        self._put_read_model(root / "index.json", header, index)
        for item in content.cases:
            case_id = item.get("case_id")
            if not isinstance(case_id, str):
                raise FormalDatasetError("formal read-model Case is missing its case ID")
            self._put_read_model(
                cases_root / f"{safe_id(case_id)}.json", header, {"case": item}
            )

    def put_document_read_model(
        self, release: DatasetRelease, *, document: FormalDocumentView
    ) -> None:
        """Persist the source-faithful reading view separately from Cases."""

        root = self.root / "read-models" / safe_id(release.release_id)
        root.mkdir(parents=True, exist_ok=True)
        header = {
            "schema_version": FORMAL_READ_MODEL_SCHEMA_VERSION,
            "release_id": release.release_id,
            "release_digest": release.release_digest,
        }
        self._put_read_model(root / "document.json", header, {"document": document.model_dump(mode="json")})

    @staticmethod
    def _put_read_model(path: Path, header: dict[str, str], value: dict[str, object]) -> None:
        payload = {**header, **value}
        if path.is_file():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if all(existing.get(key) == expected for key, expected in header.items()):
                return
        atomic_write_json(path, payload)

    def read_case_index(self, release: DatasetRelease) -> dict[str, object] | None:
        value = self._read_model(release, "index.json")
        if value is None or not isinstance(value.get("release"), dict) or not isinstance(value.get("cases"), list):
            return None
        return {"release": value["release"], "cases": value["cases"]}

    def read_case(self, release: DatasetRelease, case_id: str) -> dict[str, object] | None:
        value = self._read_model(release, f"cases/{safe_id(case_id)}.json")
        case = value.get("case") if value is not None else None
        if not isinstance(case, dict) or case.get("case_id") != case_id:
            return None
        return case

    def read_document_view(self, release: DatasetRelease) -> FormalDocumentView | None:
        value = self._read_model(release, "document.json")
        document = value.get("document") if value is not None else None
        if not isinstance(document, dict):
            return None
        try:
            return FormalDocumentView.model_validate(document)
        except ValueError:
            return None

    def _read_model(self, release: DatasetRelease, relative: str) -> dict[str, object] | None:
        path = self.root / "read-models" / safe_id(release.release_id) / relative
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(value, dict):
            return None
        if (
            value.get("schema_version") != FORMAL_READ_MODEL_SCHEMA_VERSION
            or value.get("release_id") != release.release_id
            or value.get("release_digest") != release.release_digest
        ):
            return None
        return value


class FormalDatasetValidator:
    """Single fail-closed validator for formal Dataset Release inputs.

    Validation failures never escape as the only artifact: all expected input
    failures become a deterministic, persistable ValidationReport.
    """

    def validate(
        self,
        dataset: AuthoringDataset,
        ledger: AuthoringLedger,
        *,
        case_revision_ids: tuple[str, ...],
        gold_revision_ids: tuple[str, ...],
        required_lifecycle: LifecycleState | None = None,
        document_revision_id: str | None = None,
        canonical_snapshot: CanonicalDocument | None = None,
        source_snapshot: Path | None = None,
    ) -> ValidationReport:
        findings: list[ValidationFinding] = []
        canonical: CanonicalDocument | None = None
        canonical_error: Exception | None = None
        document_revision = (
            ledger.get_document_revision(dataset.authoring_dataset_id, document_revision_id)
            if document_revision_id is not None
            else (ledger.document_history(dataset.authoring_dataset_id)[-1] if ledger.document_history(dataset.authoring_dataset_id) else None)
        )
        try:
            canonical = canonical_snapshot or self._load_canonical_document(dataset, ledger.store)
            findings.append(self._pass("canonical.schema_relation_integrity", RuleSeverity.ERROR, "Canonical schema, object graph, and relation integrity are valid", (canonical.manifest.document_id,)))
        except Exception as exc:  # Converted into audit evidence, never the sole result.
            canonical_error = exc
            findings.append(self._fail("canonical.schema_relation_integrity", RuleSeverity.ERROR, f"Canonical contract is invalid: {exc}", evidence=(RuleEvidence(evidence_type="canonical_contract", identifier="canonical-document"),)))

        cases, case_errors = self._load_cases(ledger, dataset.authoring_dataset_id, case_revision_ids)
        gold, gold_errors = self._load_gold(ledger, dataset.authoring_dataset_id, gold_revision_ids)
        if not cases:
            case_errors.append("formal validation requires at least one Case revision")
        if not gold:
            gold_errors.append("formal validation requires at least one Gold revision")
        findings.append(
            self._fail_or_pass(
                "case_gold.revision_integrity",
                RuleSeverity.ERROR,
                case_errors + gold_errors,
                "Selected Case and Gold revisions are immutable, parseable ledger records",
            )
        )

        if canonical is None:
            findings.extend(
                [
                    self._na("canonical.object_span_provenance", RuleSeverity.ERROR, "Canonical contract unavailable"),
                    self._na("document.revision_digest_consistency", RuleSeverity.ERROR, "Canonical contract unavailable"),
                    self._na("cross_reference.integrity", RuleSeverity.ERROR, "Canonical contract unavailable"),
                    self._na("gold.evidence_reachability", RuleSeverity.ERROR, "Canonical contract unavailable"),
                    self._na("integrity.checksums", RuleSeverity.ERROR, "Canonical contract unavailable"),
                ]
            )
        else:
            findings.append(self._object_provenance(canonical))
            findings.append(self._document_consistency(dataset, document_revision, canonical))
            findings.append(self._cross_references(canonical, cases, gold))
            findings.append(self._reachable_evidence(canonical, gold))
            findings.append(
                self._checksums(
                    dataset,
                    ledger.store,
                    canonical,
                    current_contract=canonical_snapshot is None,
                    source_snapshot=source_snapshot,
                )
            )

        findings.append(self._lifecycle_integrity(cases, gold, required_lifecycle))
        findings.append(self._mses(cases, gold))
        findings.append(self._answer_evidence(cases, gold))
        findings.append(self._negative_scope(gold))
        findings.append(self._dependencies(gold))
        findings.append(self._duplicates(cases))
        findings.append(self._leakage(cases, gold))
        findings.append(self._ambiguity(gold))
        findings.append(self._review_approval(ledger, dataset.authoring_dataset_id, cases, gold))
        digests = self._input_digests(dataset, ledger, document_revision, cases, gold, canonical)
        return ValidationReport.build(
            dataset_id=dataset.authoring_dataset_id,
            document_revision_id=document_revision.document_revision_id if document_revision else None,
            case_revision_ids=tuple(item.case_revision_id for item in cases),
            gold_revision_ids=tuple(item.gold_revision_id for item in gold),
            input_digests=digests,
            findings=tuple(findings),
        )

    @staticmethod
    def _load_canonical_document(dataset: AuthoringDataset, store: AuthoringWorkspaceStore) -> CanonicalDocument:
        raw_view = dataset.analysis.get("canonical_view")
        if not raw_view:
            raise FormalDatasetError("dataset has no canonical view")
        view = CanonicalView.model_validate(raw_view)
        if not (view.canonical_contract_manifest_path and view.canonical_contract_objects_path and view.canonical_contract_relations_path):
            raise FormalDatasetError("dataset has no Canonical Data Model 1.0 artifacts")
        root = store.workspace(dataset.authoring_dataset_id)
        paths = [root / view.canonical_contract_manifest_path, root / view.canonical_contract_objects_path, root / view.canonical_contract_relations_path]
        if any(not path.is_file() for path in paths):
            raise FormalDatasetError("canonical contract artifact is missing")
        manifest = json.loads(paths[0].read_text(encoding="utf-8"))
        objects = tuple(CanonicalObject.model_validate(json.loads(line)) for line in paths[1].read_text(encoding="utf-8").splitlines() if line.strip())
        relations = tuple(CanonicalRelation.model_validate(json.loads(line)) for line in paths[2].read_text(encoding="utf-8").splitlines() if line.strip())
        document = CanonicalDocument.model_validate({"manifest": manifest, "objects": objects, "relations": relations})
        if dataset.canonical_contract_digest != document.manifest.canonical_digest:
            raise FormalDatasetError("dataset canonical contract digest does not match canonical manifest")
        FormalDatasetValidator._validate_canonical_conformance(
            document=document,
            view=view,
            root=root,
        )
        return document

    @staticmethod
    def _validate_canonical_conformance(
        *,
        document: CanonicalDocument,
        view: CanonicalView,
        root: Path,
    ) -> None:
        references = (
            view.canonical_conformance_path,
            view.canonical_conformance_digest,
            view.canonical_conformance_sha256,
        )
        has_current_policy = any(
            item.attributes.get("gold_eligibility_policy")
            == CANONICAL_GOLD_ELIGIBILITY_POLICY_IDENTITY
            for item in document.objects
        )
        if not any(references):
            if has_current_policy:
                raise FormalDatasetError(
                    "current canonical snapshot has no conformance artifact"
                )
            return
        if not all(references):
            raise FormalDatasetError("canonical conformance references are incomplete")

        path = root / str(view.canonical_conformance_path)
        if not path.is_file():
            raise FormalDatasetError("canonical conformance artifact is missing")
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != view.canonical_conformance_sha256:
            raise FormalDatasetError("canonical conformance artifact checksum mismatch")
        try:
            report = CanonicalConformanceReport.model_validate_json(payload)
        except ValueError as exc:
            raise FormalDatasetError(
                f"canonical conformance artifact is invalid: {exc}"
            ) from exc
        if report.report_digest != view.canonical_conformance_digest:
            raise FormalDatasetError("canonical conformance report digest mismatch")

        manifest = document.manifest
        bindings = {
            "canonical digest": (report.canonical_digest, manifest.canonical_digest),
            "source digest": (report.source_sha256, manifest.source_sha256),
            "parser identity": (report.parser_identity, manifest.parser_identity),
            "canonicalizer identity": (
                report.canonicalizer_identity,
                manifest.canonicalizer_identity,
            ),
            "configuration digest": (
                report.configuration_digest,
                manifest.configuration_digest,
            ),
        }
        mismatches = [name for name, values in bindings.items() if values[0] != values[1]]
        if mismatches:
            raise FormalDatasetError(
                "canonical conformance artifact is bound to a different snapshot: "
                + ", ".join(mismatches)
            )

        results = {item.object_id: item for item in report.object_results}
        if set(results) != {item.object_id for item in document.objects}:
            raise FormalDatasetError(
                "canonical conformance artifact does not cover the exact object set"
            )
        for item in document.objects:
            result = results[item.object_id]
            expected = (
                item.object_type,
                item.attributes.get("gold_evidence_eligible"),
                item.attributes.get("gold_eligibility_subtype"),
                tuple(item.attributes.get("gold_eligibility_reasons") or ()),
            )
            observed = (
                result.object_type,
                result.gold_evidence_eligible,
                result.subtype,
                result.reason_codes,
            )
            if observed != expected:
                raise FormalDatasetError(
                    "canonical conformance decision disagrees with canonical object "
                    f"{item.object_id!r}"
                )

    @staticmethod
    def _load_cases(ledger: AuthoringLedger, dataset_id: str, ids: tuple[str, ...]) -> tuple[list[CaseRevision], list[str]]:
        values: list[CaseRevision] = []
        errors: list[str] = []
        for revision_id in sorted(set(ids)):
            try:
                values.append(ledger.get_case_revision(dataset_id, revision_id))
            except Exception as exc:
                errors.append(f"{revision_id}: {exc}")
        if len(ids) != len(set(ids)):
            errors.append("duplicate Case revision ID in selection")
        return values, errors

    @staticmethod
    def _load_gold(ledger: AuthoringLedger, dataset_id: str, ids: tuple[str, ...]) -> tuple[list[GoldRevision], list[str]]:
        values: list[GoldRevision] = []
        errors: list[str] = []
        for revision_id in sorted(set(ids)):
            try:
                values.append(ledger.get_gold_revision(dataset_id, revision_id))
            except Exception as exc:
                errors.append(f"{revision_id}: {exc}")
        if len(ids) != len(set(ids)):
            errors.append("duplicate Gold revision ID in selection")
        return values, errors

    def _object_provenance(self, document: CanonicalDocument) -> ValidationFinding:
        bad = [
            item.object_id
            for item in document.objects
            if item.representation_status != RepresentationStatus.MISSING
            and (not item.provenance.source_spans or not item.provenance.source_sha256)
        ]
        return self._fail_or_pass(
            "canonical.object_span_provenance",
            RuleSeverity.ERROR,
            ["missing direct source span or provenance" for _ in bad],
            "Every canonical object has direct source spans and provenance",
            affected=tuple(bad),
        )

    def _document_consistency(self, dataset: AuthoringDataset, revision, document: CanonicalDocument) -> ValidationFinding:
        errors: list[str] = []
        if revision is None:
            errors.append("missing DocumentRevision")
        else:
            if revision.source_digest != document.manifest.source_sha256:
                errors.append("DocumentRevision source digest mismatch")
            if revision.canonical_contract_digest != document.manifest.canonical_digest:
                errors.append("DocumentRevision canonical digest mismatch")
            if revision.configuration_digest != document.manifest.configuration_digest:
                errors.append("DocumentRevision configuration digest mismatch")
            if revision.parser_identity != document.manifest.parser_identity:
                errors.append("DocumentRevision parser identity mismatch")
            if revision.canonicalizer_identity != document.manifest.canonicalizer_identity:
                errors.append("DocumentRevision canonicalizer identity mismatch")
        if dataset.source.sha256 != document.manifest.source_sha256:
            errors.append("dataset source digest mismatch")
        return self._fail_or_pass("document.revision_digest_consistency", RuleSeverity.ERROR, errors, "Dataset, DocumentRevision, and Canonical manifest digests are consistent")

    def _cross_references(self, document: CanonicalDocument, cases: list[CaseRevision], gold: list[GoldRevision]) -> ValidationFinding:
        known = {item.object_id for item in document.objects}
        cases_by_id = {item.case_id: item for item in cases}
        case_revisions = {item.case_revision_id for item in cases}
        errors: list[str] = []
        affected: list[str] = []
        for case in cases:
            missing = set(case.draft.source_object_ids).difference(known)
            if missing:
                errors.append(f"Case {case.case_id} cites unknown canonical objects")
                affected.extend(sorted(missing))
        for item in gold:
            if item.case_id not in cases_by_id or item.case_revision_id not in case_revisions:
                errors.append(f"Gold {item.gold_id} does not point to a selected Case revision")
                affected.append(item.gold_revision_id)
            if item.case_id in cases_by_id and item.case_revision_id != cases_by_id[item.case_id].case_revision_id:
                errors.append(f"Gold {item.gold_id} points to a mismatched Case revision")
                affected.append(item.gold_revision_id)
        if {item.case_id for item in cases} != {item.case_id for item in gold}:
            errors.append("selected Case and Gold IDs do not form one-to-one pairs")
        return self._fail_or_pass("cross_reference.integrity", RuleSeverity.ERROR, errors, "Case, Gold, and Canonical references form a one-to-one closed graph", affected=tuple(sorted(set(affected))))

    def _reachable_evidence(self, document: CanonicalDocument, gold: list[GoldRevision]) -> ValidationFinding:
        objects = {item.object_id: item for item in document.objects}
        errors: list[str] = []
        affected: list[str] = []
        for item in gold:
            for evidence in item.payload.evidence:
                target = objects.get(evidence.canonical_object_id)
                if target is None:
                    errors.append(f"Gold {item.gold_id} evidence is unreachable")
                    affected.append(evidence.canonical_object_id)
                elif not target.gold_evidence_eligible:
                    errors.append(f"Gold {item.gold_id} evidence is incomplete or Gold-prohibited")
                    affected.append(evidence.canonical_object_id)
        return self._fail_or_pass("gold.evidence_reachability", RuleSeverity.ERROR, errors, "All formal Gold evidence is reachable as complete Canonical objects", affected=tuple(sorted(set(affected))))

    def _checksums(
        self,
        dataset: AuthoringDataset,
        store: AuthoringWorkspaceStore,
        document: CanonicalDocument,
        *,
        current_contract: bool,
        source_snapshot: Path | None,
    ) -> ValidationFinding:
        errors: list[str] = []
        source = source_snapshot or store.source_path(dataset.authoring_dataset_id)
        if not source.is_file() or _file_digest(source) != dataset.source.sha256:
            errors.append("source DOCX checksum mismatch")
        if current_contract and dataset.canonical_contract_digest != document.manifest.canonical_digest:
            errors.append("canonical contract digest mismatch")
        return self._fail_or_pass("integrity.checksums", RuleSeverity.ERROR, errors, "Source and canonical checksum/digest values are consistent")

    def _lifecycle_integrity(self, cases: list[CaseRevision], gold: list[GoldRevision], expected: LifecycleState | None) -> ValidationFinding:
        errors: list[str] = []
        for item in [*cases, *gold]:
            if item.lifecycle in {LifecycleState.DRAFT, LifecycleState.PROPOSED, LifecycleState.REJECTED, LifecycleState.INVALIDATED, LifecycleState.SUPERSEDED}:
                errors.append(f"{self._revision_id(item)} is not release-eligible ({item.lifecycle})")
            if expected is not None and item.lifecycle != expected:
                errors.append(f"{self._revision_id(item)} is not {expected}")
        return self._fail_or_pass("case_gold.release_lifecycle", RuleSeverity.ERROR, errors, "Selected Case and Gold revisions are release-eligible")

    def _mses(self, cases: list[CaseRevision], gold: list[GoldRevision]) -> ValidationFinding:
        errors: list[str] = []
        for item in gold:
            if item.payload.answer.kind != "abstain" and not item.payload.mses_paths:
                errors.append(f"Gold {item.gold_id} has no MSES")
            if item.payload.answer.kind != "abstain":
                for path in item.payload.mses_paths:
                    if not path.clauses:
                        errors.append(f"Gold {item.gold_id} has an empty MSES path")
        return self._fail_or_pass("gold.mses_completeness", RuleSeverity.ERROR, errors, "Answerable Gold revisions have complete MSES paths")

    def _answer_evidence(self, cases: list[CaseRevision], gold: list[GoldRevision]) -> ValidationFinding:
        errors: list[str] = []
        for item in gold:
            required_ids = {evidence.evidence_id for evidence in item.payload.evidence if evidence.role == EvidenceRole.REQUIRED}
            if item.payload.answer.kind != "abstain" and not required_ids:
                errors.append(f"Gold {item.gold_id} has no required evidence")
            for path in item.payload.mses_paths:
                for clause in path.clauses:
                    if not set(clause.alternatives).issubset(required_ids):
                        errors.append(f"Gold {item.gold_id} MSES disagrees with required evidence")
        return self._fail_or_pass("gold.answer_evidence_consistency", RuleSeverity.ERROR, errors, "Gold answers and MSES evidence are consistent")

    def _negative_scope(self, gold: list[GoldRevision]) -> ValidationFinding:
        errors: list[str] = []
        for item in gold:
            negative_evidence = {evidence.canonical_object_id for evidence in item.payload.evidence if evidence.role == EvidenceRole.NEGATIVE_SCOPE}
            if item.payload.answer.kind == "abstain":
                if not item.payload.negative_scope_object_ids or not item.payload.negative_rationale:
                    errors.append(f"Gold {item.gold_id} has incomplete unanswerable scope")
                if not set(item.payload.negative_scope_object_ids).issubset(negative_evidence):
                    errors.append(f"Gold {item.gold_id} negative scope lacks typed evidence")
            elif item.payload.negative_scope_object_ids:
                errors.append(f"answerable Gold {item.gold_id} has unanswerable scope")
        return self._fail_or_pass("gold.negative_unanswerable_scope", RuleSeverity.ERROR, errors, "Negative/unanswerable Gold scopes are explicit and typed")

    def _dependencies(self, gold: list[GoldRevision]) -> ValidationFinding:
        errors: list[str] = []
        for item in gold:
            graph = {dependency.dependency_id: dependency.depends_on for dependency in item.payload.dependencies}
            visiting: set[str] = set()
            visited: set[str] = set()

            def visit(node: str) -> bool:
                if node in visiting:
                    return True
                if node in visited:
                    return False
                visiting.add(node)
                found = any(visit(child) for child in graph.get(node, ()))
                visiting.remove(node)
                visited.add(node)
                return found

            if any(visit(node) for node in graph):
                errors.append(f"Gold {item.gold_id} has a cyclic multi-hop dependency")
        return self._fail_or_pass("gold.multi_hop_dependency", RuleSeverity.ERROR, errors, "Multi-hop dependencies are acyclic and internally closed")

    def _duplicates(self, cases: list[CaseRevision]) -> ValidationFinding:
        normalized: dict[str, list[str]] = {}
        for item in cases:
            value = re.sub(r"\s+", "", item.draft.question).casefold()
            normalized.setdefault(value, []).append(item.case_id)
        duplicate = sorted(case_id for values in normalized.values() if len(values) > 1 for case_id in values)
        findings: list[str] = []
        if duplicate:
            findings.append("duplicate normalized Case questions")
        near: list[str] = []
        for index, first in enumerate(cases):
            left = self._question_tokens(first.draft.question)
            for second in cases[index + 1 :]:
                right = self._question_tokens(second.draft.question)
                if left and right and len(left & right) / len(left | right) >= 0.90:
                    near.extend((first.case_id, second.case_id))
        if findings:
            return self._fail_or_pass("case.duplicate_near_miss", RuleSeverity.ERROR, findings, "No duplicate Cases", affected=tuple(duplicate))
        if near:
            return self._fail("case.duplicate_near_miss", RuleSeverity.WARN, "Near-miss Case questions require reviewer confirmation", affected=tuple(sorted(set(near))))
        return self._pass("case.duplicate_near_miss", RuleSeverity.ERROR, "No duplicate or near-miss Case questions")

    def _leakage(self, cases: list[CaseRevision], gold: list[GoldRevision]) -> ValidationFinding:
        by_case = {item.case_id: item for item in cases}
        leaked: list[str] = []
        for item in gold:
            case = by_case.get(item.case_id)
            if case is None or item.payload.answer.kind == "abstain":
                continue
            canonical = item.payload.answer.canonical
            values = canonical if isinstance(canonical, tuple) else (canonical,)
            question = re.sub(r"\s+", "", case.draft.question).casefold()
            if any(isinstance(value, str) and len(re.sub(r"\s+", "", value)) >= 3 and re.sub(r"\s+", "", value).casefold() in question for value in values):
                leaked.append(case.case_id)
        return self._fail_or_pass("case.answer_leakage", RuleSeverity.ERROR, ["question contains its Gold answer" for _ in leaked], "No Case question leaks its canonical Gold answer", affected=tuple(sorted(leaked)))

    def _ambiguity(self, gold: list[GoldRevision]) -> ValidationFinding:
        errors: list[str] = []
        warns: list[str] = []
        for item in gold:
            values = [value.casefold() for value in item.payload.answer.accepted_values]
            if len(values) != len(set(values)):
                errors.append(f"Gold {item.gold_id} has duplicate accepted answers")
            conflicting = [evidence for evidence in item.payload.evidence if evidence.role == EvidenceRole.CONFLICTING]
            if any(not evidence.rationale for evidence in conflicting):
                warns.append(item.gold_id)
        if errors:
            return self._fail_or_pass("gold.ambiguity", RuleSeverity.ERROR, errors, "Gold answer values are unambiguous")
        if warns:
            return self._fail("gold.ambiguity", RuleSeverity.WARN, "Conflicting evidence lacks an adjudication rationale", affected=tuple(sorted(warns)))
        return self._pass("gold.ambiguity", RuleSeverity.ERROR, "Gold answer values are unambiguous")

    def _review_approval(self, ledger: AuthoringLedger, dataset_id: str, cases: list[CaseRevision], gold: list[GoldRevision]) -> ValidationFinding:
        approvals = ledger.list_approvals(dataset_id)
        reviews = ledger.list_reviews(dataset_id)
        errors: list[str] = []
        for item in [*cases, *gold]:
            history = ledger.case_history(dataset_id, item.case_id) if isinstance(item, CaseRevision) else ledger.gold_history(dataset_id, item.gold_id)
            ids = {self._revision_id(revision) for revision in history}
            matching_approvals = [approval for approval in approvals if approval.approved_revision_id in ids]
            if not matching_approvals:
                errors.append(f"{self._revision_id(item)} has no approval in its revision lineage")
                continue
            for approval in matching_approvals:
                if approval.approver_identity == item.actor:
                    errors.append(f"{self._revision_id(item)} was self-approved")
            if not any(review.reviewed_revision_id in ids for review in reviews):
                errors.append(f"{self._revision_id(item)} has no review in its revision lineage")
        return self._fail_or_pass("ledger.review_approval_integrity", RuleSeverity.ERROR, errors, "Every released Case and Gold has independent review and approval lineage")

    def _input_digests(self, dataset: AuthoringDataset, ledger: AuthoringLedger, document_revision, cases: list[CaseRevision], gold: list[GoldRevision], canonical: CanonicalDocument | None) -> tuple[InputDigest, ...]:
        lineage_ids = {
            *(revision.case_revision_id for item in cases for revision in ledger.case_history(dataset.authoring_dataset_id, item.case_id)),
            *(revision.gold_revision_id for item in gold for revision in ledger.gold_history(dataset.authoring_dataset_id, item.gold_id)),
        }
        selection = {
            "document_revision": document_revision.model_dump(mode="json") if document_revision else None,
            "cases": [item.model_dump(mode="json") for item in cases],
            "gold": [item.model_dump(mode="json") for item in gold],
            "reviews": [item.model_dump(mode="json") for item in ledger.list_reviews(dataset.authoring_dataset_id) if item.reviewed_revision_id in lineage_ids],
            "approvals": [item.model_dump(mode="json") for item in ledger.list_approvals(dataset.authoring_dataset_id) if item.approved_revision_id in lineage_ids],
        }
        values = [
            InputDigest(name="source", digest=dataset.source.sha256),
            InputDigest(
                name="authoring_config",
                digest=document_revision.configuration_digest
                if document_revision
                else dataset.source.configuration_digest,
            ),
            InputDigest(name="ledger_selection", digest=_canonical_digest(selection)),
        ]
        if canonical is not None:
            values.extend(
                (
                    InputDigest(name="canonical_document", digest=canonical.manifest.canonical_digest),
                    InputDigest(name="canonical_objects", digest=canonical.manifest.objects_digest),
                    InputDigest(name="canonical_relations", digest=canonical.manifest.relations_digest),
                )
            )
        else:
            values.append(InputDigest(name="canonical_document", digest="0" * 64))
        return tuple(sorted(values, key=lambda item: item.name))

    @staticmethod
    def _revision_id(item: CaseRevision | GoldRevision) -> str:
        return item.case_revision_id if isinstance(item, CaseRevision) else item.gold_revision_id

    @staticmethod
    def _question_tokens(value: str) -> set[str]:
        return set(re.findall(r"[A-Za-z0-9_.-]+|[\u4e00-\u9fff]{2,8}", value.casefold()))

    @staticmethod
    def _pass(rule_id: str, severity: RuleSeverity, message: str, affected: tuple[str, ...] = ()) -> ValidationFinding:
        return ValidationFinding(rule_id=rule_id, severity=severity, result=RuleResult.PASS, message=message, affected_ids=tuple(sorted(affected)))

    @staticmethod
    def _fail(rule_id: str, severity: RuleSeverity, message: str, affected: tuple[str, ...] = (), evidence: tuple[RuleEvidence, ...] = ()) -> ValidationFinding:
        return ValidationFinding(rule_id=rule_id, severity=severity, result=RuleResult.FAIL, message=message, affected_ids=tuple(sorted(affected)), evidence=evidence)

    def _fail_or_pass(self, rule_id: str, severity: RuleSeverity, errors: list[str], success: str, affected: tuple[str, ...] = ()) -> ValidationFinding:
        if errors:
            return self._fail(rule_id, severity, "; ".join(sorted(set(errors))), affected=affected)
        return self._pass(rule_id, severity, success)

    @staticmethod
    def _na(rule_id: str, severity: RuleSeverity, message: str) -> ValidationFinding:
        return ValidationFinding(rule_id=rule_id, severity=severity, result=RuleResult.NOT_APPLICABLE, message=message)


class FormalDatasetReleaseService:
    """Coordinates validation, immutable release pins, typed lineage, and rebuilds."""

    def __init__(self, *, authoring_store: AuthoringWorkspaceStore, release_root: Path) -> None:
        self.authoring_store = authoring_store
        self.ledger = AuthoringLedger(authoring_store)
        self.validator = FormalDatasetValidator()
        self.releases = DatasetReleaseStore(release_root)
        # Formal releases are immutable, so a source-faithful reading view can
        # safely be cached by release ID for the lifetime of the process.
        self._document_views: dict[str, FormalDocumentView] = {}
        self._read_model_locks: dict[str, Lock] = {}
        self._read_model_locks_guard = Lock()

    def validate(
        self,
        dataset_id: str,
        *,
        case_revision_ids: tuple[str, ...],
        gold_revision_ids: tuple[str, ...],
        required_lifecycle: LifecycleState | None = None,
        document_revision_id: str | None = None,
        canonical_snapshot: CanonicalDocument | None = None,
        source_snapshot: Path | None = None,
    ) -> ValidationReport:
        dataset = self.authoring_store.get(dataset_id)
        report = self.validator.validate(
            dataset,
            self.ledger,
            case_revision_ids=case_revision_ids,
            gold_revision_ids=gold_revision_ids,
            required_lifecycle=required_lifecycle,
            document_revision_id=document_revision_id,
            canonical_snapshot=canonical_snapshot,
            source_snapshot=source_snapshot,
        )
        return self.releases.reports.put(report)

    def freeze(
        self,
        dataset_id: str,
        *,
        release_version: str,
        case_ids: tuple[str, ...],
        actor: str,
        display_name: str | None = None,
        parent_release_id: str | None = None,
    ) -> DatasetRelease:
        if not release_version.strip() or not actor.strip() or not case_ids:
            raise FormalDatasetError("release version, actor, and at least one Case are required")
        dataset = self.authoring_store.get(dataset_id)
        display_name = (display_name or "").strip() or Path(dataset.source.original_filename).stem
        if not display_name:
            display_name = dataset_id
        current_cases = tuple(self.ledger.current_case(dataset_id, case_id) for case_id in sorted(set(case_ids)))
        current_gold = tuple(self.ledger.current_gold_for_case(dataset_id, case.case_id) for case in current_cases)
        preflight = self.validator.validate(
            dataset,
            self.ledger,
            case_revision_ids=tuple(item.case_revision_id for item in current_cases),
            gold_revision_ids=tuple(item.gold_revision_id for item in current_gold),
        )
        self.releases.reports.put(preflight)
        if preflight.has_errors:
            raise FormalDatasetError(f"formal validation failed; report={preflight.report_digest}")
        if parent_release_id is not None:
            parent = self.releases.get(parent_release_id)
            if parent.dataset_id != dataset_id:
                raise FormalDatasetError("parent release belongs to a different dataset")
        freeze_marker = self.ledger.freeze_release(
            dataset,
            release_id=f"formal-{dataset_id}-{_canonical_digest({'release_version': release_version})[:16]}",
            case_ids=tuple(item.case_id for item in current_cases),
            actor=actor.strip(),
            reason="freeze revisions selected for formal Dataset Release",
        )
        report = self.validator.validate(
            dataset,
            self.ledger,
            case_revision_ids=freeze_marker.case_revision_ids,
            gold_revision_ids=freeze_marker.gold_revision_ids,
            required_lifecycle=LifecycleState.FROZEN,
        )
        self.releases.reports.put(report)
        if report.has_errors:
            raise FormalDatasetError(f"formal validation failed after freeze; report={report.report_digest}")
        frozen_cases = tuple(
            self.ledger.get_case_revision(dataset_id, item)
            for item in freeze_marker.case_revision_ids
        )
        frozen_gold = tuple(
            self.ledger.get_gold_revision(dataset_id, item)
            for item in freeze_marker.gold_revision_ids
        )
        case_history = {
            item.case_id: tuple(self.ledger.case_history(dataset_id, item.case_id))
            for item in frozen_cases
        }
        gold_history = {
            item.gold_id: tuple(self.ledger.gold_history(dataset_id, item.gold_id))
            for item in frozen_gold
        }
        lineage_ids = {
            revision.case_revision_id
            for history in case_history.values()
            for revision in history
        } | {
            revision.gold_revision_id
            for history in gold_history.values()
            for revision in history
        }
        payload_reviews = tuple(
            item
            for item in self.ledger.list_reviews(dataset_id)
            if item.reviewed_revision_id in lineage_ids
        )
        payload_approvals = tuple(
            item
            for item in self.ledger.list_approvals(dataset_id)
            if item.approved_revision_id in lineage_ids
        )
        payload_adjudications = tuple(
            item
            for item in self.ledger.list_adjudications(dataset_id)
            if item.target_revision_id in lineage_ids
        )
        payload_snapshot_digest = self.releases.payload_snapshot_digest(
            cases=frozen_cases,
            gold=frozen_gold,
            case_history=case_history,
            gold_history=gold_history,
            reviews=payload_reviews,
            approvals=payload_approvals,
            adjudications=payload_adjudications,
        )
        release = self._build_release(
            dataset,
            freeze_marker,
            report,
            display_name=display_name,
            release_version=release_version.strip(),
            actor=actor.strip(),
            parent_release_id=parent_release_id,
            payload_snapshot_digest=payload_snapshot_digest,
        )
        canonical = self.validator._load_canonical_document(dataset, self.authoring_store)
        self.releases.put_canonical_snapshot(release, canonical)
        self.releases.put_source_snapshot(
            release, self.authoring_store.source_path(dataset.authoring_dataset_id)
        )
        self.releases.put_payload_snapshots(
            release,
            cases=frozen_cases,
            gold=frozen_gold,
            case_history=case_history,
            gold_history=gold_history,
            reviews=payload_reviews,
            approvals=payload_approvals,
            adjudications=payload_adjudications,
        )
        # Build the small product-facing projections once, when the immutable
        # release is published.  The full Canonical snapshot stays available
        # for audit/rebuild work but is never the normal page-read path.
        self._materialize_read_models(release)
        return self.releases.put(release)

    def remove_from_catalog(self, release_id: str, *, actor: str) -> DatasetRelease:
        """Remove an immutable release from the current product catalog only."""

        return self.releases.remove_from_catalog(release_id, actor=actor)

    def lineage(self, release_id: str) -> ReleaseLineage:
        release = self.releases.get(release_id)
        parent = self.releases.get(release.parent_release_id) if release.parent_release_id else None
        return ReleaseLineage(
            release=release,
            source=release.document,
            cases=release.cases,
            gold=release.gold,
            reviews=release.reviews,
            approvals=release.approvals,
            origins=release.origins,
            changes_from_parent=self._diff(parent, release),
        )

    def resolve_native_benchmark(
        self,
        release_id: str,
        *,
        case_ids: tuple[str, ...] | None = None,
        seed: int = 0,
        expected_case_selection_id: str | None = None,
    ) -> NativeBenchmarkReleaseV2:
        """Resolve one Release directly into a verified Native v2 Benchmark.

        This path intentionally requires every immutable Release sidecar.  It
        never falls back to the editable Authoring Ledger or an exported
        Bundle, so admission can fail closed without changing Benchmark Gold.
        """

        try:
            release = self.releases.get(release_id)
        except (OSError, ValueError) as exc:
            raise FormalDatasetError(
                "immutable Benchmark Release is unavailable or invalid"
            ) from exc
        if self.releases.is_removed(release.release_id):
            raise FormalDatasetError("Benchmark Release was removed from the catalog")

        try:
            report = self.releases.reports.get(release.validation_report_digest)
        except (OSError, ValueError) as exc:
            raise FormalDatasetError(
                "Benchmark Release validation report is unavailable or invalid"
            ) from exc
        expected_case_revisions = tuple(
            sorted(item.case_revision_id for item in release.cases)
        )
        expected_gold_revisions = tuple(
            sorted(item.gold_revision_id for item in release.gold)
        )
        if (
            report.dataset_id != release.dataset_id
            or report.report_digest != release.validation_report_digest
            or report.case_revision_ids != expected_case_revisions
            or report.gold_revision_ids != expected_gold_revisions
            or report.has_errors
        ):
            raise FormalDatasetError(
                "Benchmark Release validation report does not admit its exact payload"
            )

        try:
            source_path = self.releases.source_snapshot(release.release_id)
            canonical = self.releases.canonical_snapshot(release.release_id)
            payload = self._load_pinned_payload_snapshot(release)
        except (OSError, ValueError, LedgerError) as exc:
            raise FormalDatasetError(
                "immutable Benchmark Release sidecars are unavailable or invalid"
            ) from exc

        if hashlib.sha256(source_path.read_bytes()).hexdigest() != release.document.source_digest:
            raise FormalDatasetError("Benchmark Release source snapshot digest mismatch")
        manifest = canonical.manifest
        if (
            manifest.document_id != release.document.document_id
            or manifest.source_sha256 != release.document.source_digest
            or manifest.canonical_digest != release.document.canonical_digest
            or manifest.parser_identity != release.document.parser_identity
            or manifest.canonicalizer_identity != release.document.canonicalizer_identity
            or manifest.configuration_digest != release.document.configuration_digest
        ):
            raise FormalDatasetError(
                "Benchmark Release Canonical snapshot does not match its document pin"
            )
        report_inputs = {item.name: item.digest for item in report.input_digests}
        if (
            report_inputs.get("source") != release.document.source_digest
            or report_inputs.get("canonical_document")
            != release.document.canonical_digest
            or report_inputs.get("canonical_objects") != manifest.objects_digest
            or report_inputs.get("canonical_relations") != manifest.relations_digest
            or report_inputs.get("authoring_config")
            != release.document.configuration_digest
        ):
            raise FormalDatasetError(
                "Benchmark Release validation inputs do not match its source pins"
            )

        case_revisions = payload["cases"]
        gold_revisions = payload["gold"]
        assert isinstance(case_revisions, dict)
        assert isinstance(gold_revisions, dict)
        if set(case_revisions) != set(expected_case_revisions) or set(
            gold_revisions
        ) != set(expected_gold_revisions):
            raise FormalDatasetError(
                "Benchmark Release payload contains unpinned or missing revisions"
            )

        objects = {item.object_id: item for item in canonical.objects}
        source_identity = BenchmarkSourceIdentityV2(
            document_id=release.document.document_id,
            source_sha256=release.document.source_digest,
            canonical_schema_version=manifest.schema_version,
            canonical_digest=manifest.canonical_digest,
            canonical_catalog_sha256=hashlib.sha256(
                native_canonical_catalog_bytes(canonical)
            ).hexdigest(),
            parser_identity=manifest.parser_identity,
            canonicalizer_identity=manifest.canonicalizer_identity,
            configuration_digest=manifest.configuration_digest,
        )
        gold_pin_by_case = {item.case_id: item for item in release.gold}
        resolved_cases: dict[str, BenchmarkCaseV2] = {}
        for case_pin in release.cases:
            case = case_revisions[case_pin.case_revision_id]
            if not isinstance(case, CaseRevision):
                raise FormalDatasetError("release payload contains an invalid Case revision")
            gold_pin = gold_pin_by_case[case_pin.case_id]
            gold = gold_revisions[gold_pin.gold_revision_id]
            if not isinstance(gold, GoldRevision):
                raise FormalDatasetError("release payload contains an invalid Gold revision")
            self._verify_release_case_and_gold_pins(
                release=release,
                case_pin=case_pin,
                case=case,
                gold_pin=gold_pin,
                gold=gold,
            )
            unknown_source_objects = sorted(
                set(case.draft.source_object_ids).difference(objects)
            )
            if unknown_source_objects:
                raise FormalDatasetError(
                    "released Case references unknown Canonical objects: "
                    f"{unknown_source_objects}"
                )
            evidence: list[BenchmarkEvidenceV2] = []
            for item in gold.payload.evidence:
                canonical_object = objects.get(item.canonical_object_id)
                if (
                    canonical_object is None
                    or not canonical_object.gold_evidence_eligible
                    or canonical_object.representation_status
                    != RepresentationStatus.COMPLETE
                    or canonical_object.canonical_value is None
                    or not canonical_object.provenance.source_spans
                ):
                    raise FormalDatasetError(
                        f"Gold evidence {item.evidence_id!r} lacks a complete, "
                        "eligible Canonical witness"
                    )
                evidence.append(
                    BenchmarkEvidenceV2(
                        evidence_id=item.evidence_id,
                        document_id=canonical_object.document_id,
                        canonical_object_id=canonical_object.object_id,
                        role=item.role.value,
                        rationale=item.rationale,
                        canonical_object_type=canonical_object.object_type,
                        source_spans=canonical_object.provenance.source_spans,
                        canonical_value=canonical_object.canonical_value,
                        canonical_witness_sha256=hashlib.sha256(
                            canonical_object.canonical_value.encode("utf-8")
                        ).hexdigest(),
                    )
                )
            benchmark_gold = BenchmarkGoldV2(
                gold_id=gold.gold_id,
                gold_revision_id=gold.gold_revision_id,
                case_id=gold.case_id,
                case_revision_id=gold.case_revision_id,
                source_identity=source_identity,
                answer=BenchmarkAnswerV2(
                    kind=gold.payload.answer.kind,
                    canonical=gold.payload.answer.canonical,
                    accepted_values=gold.payload.answer.accepted_values,
                    locale=gold.payload.answer.locale,
                    unit=gold.payload.answer.unit,
                    tolerance=gold.payload.answer.tolerance,
                ),
                evidence=tuple(evidence),
                mses_paths=tuple(
                    BenchmarkMsesPathV2(
                        path_id=path.path_id,
                        clauses=tuple(
                            BenchmarkMsesClauseV2(
                                clause_id=clause.clause_id,
                                alternatives=clause.alternatives,
                            )
                            for clause in path.clauses
                        ),
                    )
                    for path in gold.payload.mses_paths
                ),
                dependencies=tuple(
                    BenchmarkEvidenceDependencyV2(
                        dependency_id=item.dependency_id,
                        depends_on=item.depends_on,
                        description=item.description,
                    )
                    for item in gold.payload.dependencies
                ),
                negative_scope_object_ids=gold.payload.negative_scope_object_ids,
                negative_rationale=gold.payload.negative_rationale,
            )
            resolved_cases[case.case_id] = BenchmarkCaseV2(
                case_id=case.case_id,
                case_revision_id=case.case_revision_id,
                target_id=case.draft.target_id,
                question=case.draft.question,
                language=case.draft.language,
                source_object_ids=case.draft.source_object_ids,
                gold=benchmark_gold,
            )

        available_case_ids = tuple(sorted(resolved_cases))
        selection_policy = "all" if case_ids is None else "explicit"
        selected_case_ids = (
            available_case_ids if case_ids is None else tuple(sorted(case_ids))
        )
        if not selected_case_ids:
            raise FormalDatasetError("Native Benchmark must select at least one Case")
        if len(selected_case_ids) != len(set(selected_case_ids)):
            raise FormalDatasetError("Native Benchmark Case selection contains duplicates")
        unknown = sorted(set(selected_case_ids).difference(available_case_ids))
        if unknown:
            raise FormalDatasetError(
                f"Native Benchmark references unknown Cases: {unknown}"
            )
        selection_id = benchmark_case_selection_id(
            selected_case_ids,
            policy=selection_policy,
            seed=seed,
        )
        if (
            expected_case_selection_id is not None
            and expected_case_selection_id != selection_id
        ):
            raise FormalDatasetError(
                "Native Benchmark case selection ID does not match its inputs"
            )
        selected_cases = tuple(resolved_cases[item] for item in selected_case_ids)
        snapshot_digest = native_benchmark_snapshot_digest(
            release_id=release.release_id,
            release_digest=release.release_digest,
            validation_report_digest=release.validation_report_digest,
            payload_snapshot_digest=release.payload_snapshot_digest,
            dataset_id=release.dataset_id,
            release_version=release.release_version,
            source_identity=source_identity,
            cases=selected_cases,
            case_selection_policy=selection_policy,
            case_selection_seed=seed,
            case_selection_id=selection_id,
        )
        return NativeBenchmarkReleaseV2(
            release_id=release.release_id,
            release_digest=release.release_digest,
            validation_report_digest=release.validation_report_digest,
            payload_snapshot_digest=release.payload_snapshot_digest,
            dataset_id=release.dataset_id,
            release_version=release.release_version,
            source_identity=source_identity,
            original_docx_path=source_path.resolve(),
            canonical_snapshot=canonical,
            cases=selected_cases,
            case_ids=selected_case_ids,
            case_selection_policy=selection_policy,
            case_selection_seed=seed,
            case_selection_id=selection_id,
            snapshot_digest=snapshot_digest,
        )

    @staticmethod
    def _verify_release_case_and_gold_pins(
        *,
        release: DatasetRelease,
        case_pin: ReleaseCasePin,
        case: CaseRevision,
        gold_pin: ReleaseGoldPin,
        gold: GoldRevision,
    ) -> None:
        if (
            case.lifecycle != LifecycleState.FROZEN
            or case.case_id != case_pin.case_id
            or case.case_revision_id != case_pin.case_revision_id
            or case.draft.source_digest != case_pin.source_digest
            or case.draft.canonical_contract_digest != case_pin.canonical_digest
            or case.draft.source_digest != release.document.source_digest
            or case.draft.canonical_contract_digest
            != release.document.canonical_digest
        ):
            raise FormalDatasetError("released Case does not match its immutable pin")
        if (
            gold.lifecycle != LifecycleState.FROZEN
            or gold.gold_id != gold_pin.gold_id
            or gold.gold_revision_id != gold_pin.gold_revision_id
            or gold.case_id != case.case_id
            or gold.case_revision_id != case.case_revision_id
            or gold.origin.kind.value != gold_pin.origin_kind
            or gold.origin.configuration_digest
            != gold_pin.origin_configuration_digest
        ):
            raise FormalDatasetError("released Gold does not match its immutable pin")

    @staticmethod
    def _payload_from_json(value: dict[str, object]) -> dict[str, object]:
        """Decode an immutable release payload sidecar or bundle records."""

        cases = tuple(
            CaseRevision.model_validate(item)
            for item in value.get("cases", [])
            if isinstance(item, dict)
        )
        gold = tuple(
            GoldRevision.model_validate(item)
            for item in value.get("gold", [])
            if isinstance(item, dict)
        )
        case_history: dict[str, tuple[CaseRevision, ...]] = {}
        raw_case_history = value.get("case_history", {})
        if isinstance(raw_case_history, dict):
            for key, items in raw_case_history.items():
                if isinstance(items, list):
                    case_history[str(key)] = tuple(
                        CaseRevision.model_validate(item)
                        for item in items
                        if isinstance(item, dict)
                    )
        gold_history: dict[str, tuple[GoldRevision, ...]] = {}
        raw_gold_history = value.get("gold_history", {})
        if isinstance(raw_gold_history, dict):
            for key, items in raw_gold_history.items():
                if isinstance(items, list):
                    gold_history[str(key)] = tuple(
                        GoldRevision.model_validate(item)
                        for item in items
                        if isinstance(item, dict)
                    )
        reviews = tuple(
            Review.model_validate(item)
            for item in value.get("reviews", [])
            if isinstance(item, dict)
        )
        approvals = tuple(
            Approval.model_validate(item)
            for item in value.get("approvals", [])
            if isinstance(item, dict)
        )
        adjudications = tuple(
            Adjudication.model_validate(item)
            for item in value.get("adjudications", [])
            if isinstance(item, dict)
        )
        return {
            "cases": {item.case_revision_id: item for item in cases},
            "gold": {item.gold_revision_id: item for item in gold},
            "case_history": case_history,
            "gold_history": gold_history,
            "reviews": reviews,
            "approvals": approvals,
            "adjudications": adjudications,
        }

    def _validate_payload_for_release(
        self, release: DatasetRelease, payload: dict[str, object]
    ) -> dict[str, object]:
        cases = payload["cases"]
        gold = payload["gold"]
        assert isinstance(cases, dict)
        assert isinstance(gold, dict)
        missing_cases = [
            item.case_revision_id
            for item in release.cases
            if item.case_revision_id not in cases
        ]
        missing_gold = [
            item.gold_revision_id
            for item in release.gold
            if item.gold_revision_id not in gold
        ]
        if missing_cases or missing_gold:
            raise LedgerError(
                "immutable release payload is incomplete"
                f" (missing cases={missing_cases}, gold={missing_gold})"
            )
        return payload

    def _load_pinned_payload_snapshot(
        self, release: DatasetRelease
    ) -> dict[str, object]:
        """Load only the immutable, Release-digested payload sidecar."""

        snapshot = self.releases.payload_snapshots(release.release_id)
        content_keys = {
            "cases",
            "gold",
            "case_history",
            "gold_history",
            "reviews",
            "approvals",
            "adjudications",
        }
        expected_keys = content_keys | {
            "release_id",
            "release_digest",
            "payload_snapshot_digest",
        }
        if set(snapshot) != expected_keys:
            raise FormalDatasetError(
                "release payload snapshot has an unexpected contract shape"
            )
        content = {key: snapshot[key] for key in sorted(content_keys)}
        payload_digest = _canonical_digest(content)
        if (
            snapshot.get("release_id") != release.release_id
            or snapshot.get("release_digest") != release.release_digest
            or snapshot.get("payload_snapshot_digest") != payload_digest
            or payload_digest != release.payload_snapshot_digest
        ):
            raise FormalDatasetError("release payload snapshot identity mismatch")
        return self._validate_payload_for_release(
            release, self._payload_from_json(snapshot)
        )

    def _build_content_from_snapshot(self, release: DatasetRelease) -> FormalReleaseContent:
        """Join pinned Case/Gold revisions with Canonical evidence.

        This expensive path is deliberately reserved for publishing a new
        read model or one-time migration of a legacy release.  Interactive
        requests use the precomputed read-model files below instead.
        """

        canonical = self.releases.canonical_snapshot(release.release_id)
        objects = {item.object_id: item for item in canonical.objects}
        relations = tuple(
            item
            for item in canonical.relations
            if item.source_object_id in objects and item.target_object_id in objects
        )
        payload = self._load_pinned_payload_snapshot(release)
        case_revisions = payload["cases"]
        gold_revisions = payload["gold"]
        case_histories = payload["case_history"]
        gold_histories = payload["gold_history"]
        reviews = payload["reviews"]
        approvals = payload["approvals"]
        adjudications = payload["adjudications"]
        assert isinstance(case_revisions, dict)
        assert isinstance(gold_revisions, dict)
        assert isinstance(case_histories, dict)
        assert isinstance(gold_histories, dict)
        assert isinstance(reviews, tuple)
        assert isinstance(approvals, tuple)
        assert isinstance(adjudications, tuple)
        lineage_ids: set[str] = set(case_revisions) | set(gold_revisions)
        for item in case_revisions.values():
            lineage_ids.update(
                revision.case_revision_id
                for revision in case_histories.get(item.case_id, (item,))
            )
        for item in gold_revisions.values():
            lineage_ids.update(
                revision.gold_revision_id
                for revision in gold_histories.get(item.gold_id, (item,))
            )

        cases: list[dict[str, object]] = []
        gold_by_case = {item.case_id: item for item in release.gold}
        for case_pin in release.cases:
            case = case_revisions[case_pin.case_revision_id]
            gold_pin = gold_by_case[case.case_id]
            gold = gold_revisions[gold_pin.gold_revision_id]
            case_history = case_histories.get(case.case_id, (case,))
            evidence: list[dict[str, object]] = []
            evidence_ids = {
                item.canonical_object_id for item in gold.payload.evidence
            }
            selected_ids = set(case.draft.source_object_ids) | evidence_ids
            for item in gold.payload.evidence:
                canonical_object = objects.get(item.canonical_object_id)
                evidence.append(
                    {
                        "evidence_id": item.evidence_id,
                        "canonical_object_id": item.canonical_object_id,
                        "role": item.role.value,
                        "rationale": item.rationale,
                        "reachable": canonical_object is not None,
                        "canonical": canonical_object.model_dump(mode="json")
                        if canonical_object is not None
                        else None,
                    }
                )
            relation_context = [
                {
                    "relation_id": item.relation_id,
                    "relation_type": item.relation_type.value,
                    "source_object_id": item.source_object_id,
                    "target_object_id": item.target_object_id,
                    "attributes": item.attributes,
                }
                for item in relations
                if item.source_object_id in selected_ids
                and item.target_object_id in selected_ids
            ]
            case_lineage = {
                "reviews": [
                    item.model_dump(mode="json")
                    for item in reviews
                    if item.reviewed_revision_id in {
                        revision.case_revision_id
                        for revision in case_history
                    }
                ],
                "approvals": [
                    item.model_dump(mode="json")
                    for item in approvals
                    if item.approved_revision_id in {
                        revision.case_revision_id
                        for revision in case_history
                    }
                ],
                "adjudications": [
                    item.model_dump(mode="json")
                    for item in adjudications
                    if item.target_revision_id in {
                        revision.case_revision_id
                        for revision in case_history
                    }
                ],
            }
            gold_lineage_ids = {
                revision.gold_revision_id
                for revision in gold_histories.get(gold.gold_id, (gold,))
            }
            gold_lineage = {
                "reviews": [
                    item.model_dump(mode="json")
                    for item in reviews
                    if item.reviewed_revision_id in gold_lineage_ids
                ],
                "approvals": [
                    item.model_dump(mode="json")
                    for item in approvals
                    if item.approved_revision_id in gold_lineage_ids
                ],
                "adjudications": [
                    item.model_dump(mode="json")
                    for item in adjudications
                    if item.target_revision_id in gold_lineage_ids
                ],
            }
            cases.append(
                {
                    "case_id": case.case_id,
                    "case_revision_id": case.case_revision_id,
                    "revision": case.revision,
                    "lifecycle": case.lifecycle.value,
                    "question": case.draft.question,
                    "language": case.draft.language,
                    "target_id": case.draft.target_id,
                    "source_object_ids": list(case.draft.source_object_ids),
                    "source_digest": case.draft.source_digest,
                    "canonical_contract_digest": case.draft.canonical_contract_digest,
                    "origin": case.draft.origin.model_dump(mode="json"),
                    "actor": case.actor,
                    "reason": case.reason,
                    "gold": {
                        "gold_id": gold.gold_id,
                        "gold_revision_id": gold.gold_revision_id,
                        "revision": gold.revision,
                        "lifecycle": gold.lifecycle.value,
                        "answer": gold.payload.answer.model_dump(mode="json"),
                        "evidence": evidence,
                        "mses_paths": [
                            item.model_dump(mode="json")
                            for item in gold.payload.mses_paths
                        ],
                        "dependencies": [
                            item.model_dump(mode="json")
                            for item in gold.payload.dependencies
                        ],
                        "negative_scope_object_ids": list(
                            gold.payload.negative_scope_object_ids
                        ),
                        "negative_rationale": gold.payload.negative_rationale,
                        "origin": gold.origin.model_dump(mode="json"),
                        "actor": gold.actor,
                        "reason": gold.reason,
                        "lineage": gold_lineage,
                    },
                    "relation_context": relation_context,
                    "lineage": case_lineage,
                }
            )
        return FormalReleaseContent(
            release={
                "release_id": release.release_id,
                "dataset_id": release.dataset_id,
                "version": release.release_version,
                "release_digest": release.release_digest,
                "parent_release_id": release.parent_release_id,
                "canonical_digest": release.document.canonical_digest,
                "source_digest": release.document.source_digest,
                "validation_report_digest": release.validation_report_digest,
                "case_count": len(release.cases),
                "gold_count": len(release.gold),
                "canonical_schema_version": release.schema_versions.canonical_schema_version,
            },
            cases=tuple(cases),
        )

    def content(self, release_id: str) -> FormalReleaseContent:
        """Return a complete local inspection view without parsing Canonical JSON.

        The product reader may ask for all Cases at once.  The data is
        assembled from the per-Case read models, never from the full snapshot.
        """

        release = self.releases.get(release_id)
        cached = self._content_from_read_models(release)
        if cached is not None:
            return cached
        self._ensure_case_read_models(release)
        cached = self._content_from_read_models(release)
        if cached is None:
            raise FormalDatasetError("formal Dataset Release Case read model is unavailable")
        return cached

    def case_index(self, release_id: str) -> dict[str, object]:
        """Return the product's fast Case navigation model for one Release."""

        release = self.releases.get(release_id)
        cached = self.releases.read_case_index(release)
        if cached is not None:
            return cached
        self._ensure_case_read_models(release)
        cached = self.releases.read_case_index(release)
        if cached is None:
            raise FormalDatasetError("formal Dataset Release Case index is unavailable")
        return cached

    def case_content(self, release_id: str, case_id: str) -> dict[str, object]:
        """Return one Case's detail model for the local product reader."""

        release = self.releases.get(release_id)
        cached = self.releases.read_case(release, case_id)
        if cached is not None:
            return cached
        self._ensure_case_read_models(release)
        cached = self.releases.read_case(release, case_id)
        if cached is None:
            raise FormalDatasetError(f"formal Dataset Release Case not found: {case_id}")
        return cached

    def _content_from_read_models(
        self, release: DatasetRelease
    ) -> FormalReleaseContent | None:
        index = self.releases.read_case_index(release)
        if index is None:
            return None
        case_items = index.get("cases")
        release_value = index.get("release")
        if not isinstance(case_items, list) or not isinstance(release_value, dict):
            return None
        cases: list[dict[str, object]] = []
        for item in case_items:
            if not isinstance(item, dict) or not isinstance(item.get("case_id"), str):
                return None
            detail = self.releases.read_case(release, item["case_id"])
            if detail is None:
                return None
            cases.append(detail)
        return FormalReleaseContent(release=release_value, cases=tuple(cases))

    def _ensure_case_read_models(self, release: DatasetRelease) -> None:
        with self._read_model_lock(release.release_id):
            if self._content_from_read_models(release) is not None:
                return
            content = self._build_content_from_snapshot(release)
            self.releases.put_case_read_models(release, content=content)

    def _ensure_document_read_model(self, release: DatasetRelease) -> FormalDocumentView:
        cached = self.releases.read_document_view(release)
        if cached is not None:
            return cached
        with self._read_model_lock(release.release_id):
            cached = self.releases.read_document_view(release)
            if cached is not None:
                return cached
            document = self._build_document_view(release)
            self.releases.put_document_read_model(release, document=document)
            return document

    def _materialize_read_models(self, release: DatasetRelease) -> None:
        """Publish all product read models from the frozen source of truth."""

        with self._read_model_lock(release.release_id):
            content = self._build_content_from_snapshot(release)
            document = self._build_document_view(release)
            self.releases.put_read_models(release, content=content, document=document)
            self._document_views[release.release_id] = document

    def materialize_read_models(self, release_id: str) -> None:
        """One-time migration hook for releases created before read models."""

        self._materialize_read_models(self.releases.get(release_id))

    def _read_model_lock(self, release_id: str) -> Lock:
        with self._read_model_locks_guard:
            return self._read_model_locks.setdefault(release_id, Lock())

    @staticmethod
    def _source_body_ordinal(item: CanonicalObject) -> int | None:
        """Return the direct OOXML body position for a Canonical object."""

        for span in item.provenance.source_spans:
            value = span.coordinates.get("body_ordinal")
            if isinstance(value, int) and not isinstance(value, bool):
                return value
        return None

    @staticmethod
    def _source_paragraph_text_by_body(source: Path) -> dict[int, str]:
        """Read presentation text that OOXML keeps outside ``w:t`` nodes.

        Frozen Canonical snapshots remain immutable.  The local document reader
        may nevertheless repair its *display* of a source caption by reading
        the pinned DOCX: Word represents non-breaking caption separators, for
        example the hyphen in ``表 2-7``, as ``w:noBreakHyphen``.  This helper
        is intentionally a read-only source-faithful presentation projection.
        """

        try:
            with zipfile.ZipFile(source) as package:
                root = etree.fromstring(package.read("word/document.xml"))
        except (KeyError, OSError, zipfile.BadZipFile, etree.XMLSyntaxError):
            return {}
        body = root.find(f"{{{_WORDPROCESSINGML}}}body")
        if body is None:
            return {}
        paragraph_tag = f"{{{_WORDPROCESSINGML}}}p"
        section_tag = f"{{{_WORDPROCESSINGML}}}sectPr"
        text_tag = f"{{{_WORDPROCESSINGML}}}t"
        tab_tag = f"{{{_WORDPROCESSINGML}}}tab"
        break_tags = {
            f"{{{_WORDPROCESSINGML}}}br",
            f"{{{_WORDPROCESSINGML}}}cr",
        }
        non_break_hyphen_tag = f"{{{_WORDPROCESSINGML}}}noBreakHyphen"
        soft_hyphen_tag = f"{{{_WORDPROCESSINGML}}}softHyphen"
        values: dict[int, str] = {}
        for body_ordinal, child in enumerate(body):
            if child.tag == section_tag:
                continue
            if child.tag != paragraph_tag:
                continue
            pieces: list[str] = []
            for element in child.iter():
                if element.tag == text_tag:
                    pieces.append(element.text or "")
                elif element.tag == tab_tag:
                    pieces.append("\t")
                elif element.tag in break_tags:
                    pieces.append("\n")
                elif element.tag in {non_break_hyphen_tag, soft_hyphen_tag}:
                    pieces.append("-")
            text = re.sub(r"[ \t\r\n]+", " ", "".join(pieces)).strip()
            if text:
                values[body_ordinal] = text
        return values

    @staticmethod
    def _source_paragraph_layout_by_body(source: Path) -> dict[int, tuple[bool, int | None]]:
        """Read stable DOCX layout hints for the local reading projection.

        Word calculates final pages from fonts and printer settings, so its
        physical page count cannot be made a durable data contract. Explicit
        page breaks and list nesting are source facts though; carrying them
        lets the browser paginate consistently while retaining Word intent.
        """

        try:
            with zipfile.ZipFile(source) as package:
                root = etree.fromstring(package.read("word/document.xml"))
        except (KeyError, OSError, zipfile.BadZipFile, etree.XMLSyntaxError):
            return {}
        body = root.find(f"{{{_WORDPROCESSINGML}}}body")
        if body is None:
            return {}
        paragraph_tag = f"{{{_WORDPROCESSINGML}}}p"
        section_tag = f"{{{_WORDPROCESSINGML}}}sectPr"
        page_break_before_tag = f"{{{_WORDPROCESSINGML}}}pageBreakBefore"
        break_tag = f"{{{_WORDPROCESSINGML}}}br"
        type_attribute = f"{{{_WORDPROCESSINGML}}}type"
        list_level_path = f"{{{_WORDPROCESSINGML}}}pPr/{{{_WORDPROCESSINGML}}}numPr/{{{_WORDPROCESSINGML}}}ilvl"
        value_attribute = f"{{{_WORDPROCESSINGML}}}val"
        values: dict[int, tuple[bool, int | None]] = {}
        for body_ordinal, child in enumerate(body):
            if child.tag == section_tag or child.tag != paragraph_tag:
                continue
            explicit_break = child.find(f"{{{_WORDPROCESSINGML}}}pPr/{page_break_before_tag}") is not None
            inline_break = any(
                element.tag == break_tag and element.get(type_attribute) == "page"
                for element in child.iter()
            )
            raw_level = child.find(list_level_path)
            level: int | None = None
            if raw_level is not None:
                try:
                    level = max(0, min(9, int(raw_level.get(value_attribute, "0"))))
                except ValueError:
                    level = None
            if explicit_break or inline_break or level is not None:
                values[body_ordinal] = (explicit_break or inline_break, level)
        return values

    def document_view(self, release_id: str) -> FormalDocumentView:
        """Return a cached, source-faithful reading view for the UI.

        The document projection is materialized during release publication and
        survives process restarts.  A legacy release is migrated once on its
        first reader request; it is not reparsed on every request.
        """

        cached = self._document_views.get(release_id)
        if cached is not None:
            return cached
        release = self.releases.get(release_id)
        cached = self.releases.read_document_view(release)
        if cached is None:
            cached = self._ensure_document_read_model(release)
        # The filename is presentation metadata, not part of a pinned Canonical
        # object. Refresh legacy read models in memory so an old internal
        # document ID never becomes the label shown in the evidence modal.
        filename = self._source_filename_for_release(release)
        if cached.filename != filename:
            cached = cached.model_copy(update={"filename": filename})
        self._document_views[release_id] = cached
        return cached

    def source_filename(self, release_id: str) -> str:
        """Return the source filename for a frozen Release without an ID label.

        Early formal releases recorded a legacy dataset ID that can no longer
        identify their authoring workspace.  Their source digest remains an
        immutable pin, so matching it to a retained local workspace is a safe
        presentation fallback; it does not alter the release or its document
        snapshot.
        """

        return self._source_filename_for_release(self.releases.get(release_id))

    def _source_filename_for_release(self, release: DatasetRelease) -> str:
        try:
            filename = self.authoring_store.get(
                release.dataset_id
            ).source.original_filename
            if filename.strip():
                return filename
        except (FileNotFoundError, OSError, ValueError, AttributeError):
            pass
        matches: list[tuple[str, str]] = []
        try:
            datasets = self.authoring_store.list()
        except (FileNotFoundError, OSError, ValueError):
            datasets = []
        for dataset in datasets:
            source = getattr(dataset, "source", None)
            if getattr(source, "sha256", None) != release.document.source_digest:
                continue
            filename = getattr(source, "original_filename", None)
            dataset_id = getattr(dataset, "authoring_dataset_id", "")
            if isinstance(filename, str) and filename.strip():
                matches.append((str(dataset_id), filename))
        if matches:
            return sorted(matches)[0][1]
        return f"{release.document.document_id}.docx"

    def _build_document_view(self, release: DatasetRelease) -> FormalDocumentView:
        """Build the source-faithful reader projection from Canonical data.

        The pinned Canonical snapshot is the source of truth.  We group its
        directly located objects by the original ``w:body`` ordinal and keep
        table logical cells, spans, and merge coordinates.  No retrieval trace
        or free-form metadata is consulted.  This runs at publication or one
        legacy migration, never in the normal page-read path.
        """

        canonical = self.releases.canonical_snapshot(release.release_id)
        source_text_by_body = self._source_paragraph_text_by_body(
            self.releases.source_snapshot(release.release_id)
        )
        groups: dict[int, list[CanonicalObject]] = {}
        for item in canonical.objects:
            ordinal = self._source_body_ordinal(item)
            if ordinal is None:
                continue
            groups.setdefault(ordinal, []).append(item)

        blocks: list[FormalDocumentBlock] = []
        primary_types = {"heading", "paragraph", "caption"}
        table_types = {"table", "row", "cell", "logical_row", "logical_column", "logical_cell"}
        for ordinal in sorted(groups):
            members = sorted(groups[ordinal], key=lambda item: item.document_order)
            object_ids = tuple(item.object_id for item in members)
            table = next((item for item in members if item.object_type.value == "table"), None)
            if table is not None:
                table_id = table.object_id
                table_members = [
                    item for item in members
                    if item.object_type.value in table_types
                    and (item.object_type.value == "table" or item.attributes.get("table_id") == table_id)
                ]
                logical_cells = [item for item in table_members if item.object_type.value == "logical_cell"]
                cells_source = logical_cells or [item for item in table_members if item.object_type.value == "cell"]
                physical_by_id = {
                    item.object_id: item
                    for item in table_members
                    if item.object_type.value == "cell"
                }
                cells: list[FormalDocumentCell] = []
                for cell in sorted(
                    cells_source,
                    key=lambda item: (
                        int(item.attributes.get("row", item.attributes.get("logical_row_start", 0))),
                        int(item.attributes.get("column", item.attributes.get("logical_column_start", 0))),
                        item.document_order,
                    ),
                ):
                    attrs = cell.attributes
                    row = int(attrs.get("row", attrs.get("logical_row_start", 1)))
                    column = int(attrs.get("column", attrs.get("logical_column_start", 1)))
                    row_span = int(attrs.get("row_span", 1) or 1)
                    column_span = int(attrs.get("column_span", attrs.get("grid_span", 1)) or 1)
                    related_ids = [cell.object_id]
                    for key in ("origin_physical_cell_id", "logical_cell_id", "row_id", "logical_row_id"):
                        value = attrs.get(key)
                        if isinstance(value, str) and value not in related_ids:
                            related_ids.append(value)
                    origin_id = attrs.get("origin_physical_cell_id")
                    origin = physical_by_id.get(origin_id) if isinstance(origin_id, str) else None
                    if origin is not None:
                        row_id = origin.attributes.get("row_id")
                        if isinstance(row_id, str) and row_id not in related_ids:
                            related_ids.append(row_id)
                    for column_id in attrs.get("logical_column_ids", ()):
                        if isinstance(column_id, str) and column_id not in related_ids:
                            related_ids.append(column_id)
                    cells.append(
                        FormalDocumentCell(
                            text=cell.canonical_value or "",
                            row=max(1, row),
                            column=max(1, column),
                            row_span=max(1, row_span),
                            column_span=max(1, column_span),
                            object_ids=tuple(related_ids),
                        )
                    )
                blocks.append(
                    FormalDocumentBlock(
                        block_id=table_id,
                        kind="table",
                        text=table.canonical_value or "",
                        document_order=min(item.document_order for item in members),
                        object_ids=object_ids,
                        cells=tuple(cells),
                    )
                )
                continue

            primary = next((item for item in members if item.object_type.value in primary_types), None)
            if primary is None:
                primary = next(
                    (item for item in members if item.object_type.value in {"figure", "equation", "reference", "footnote", "endnote"}),
                    None,
                )
            if primary is None:
                continue
            text = primary.canonical_value or ""
            # Older frozen Canonical snapshots predate preservation of OOXML
            # non-breaking hyphens.  Captions are displayed from the immutable
            # source snapshot so labels such as ``表 2-7`` are not rendered as
            # the different number ``表 27``.
            if primary.object_type.value == "caption":
                text = source_text_by_body.get(ordinal, text)
            if not text:
                text = "\n".join(item.canonical_value or "" for item in members if item.canonical_value)
            blocks.append(
                FormalDocumentBlock(
                    block_id=primary.object_id,
                    kind=primary.object_type.value,
                    text=text,
                    document_order=min(item.document_order for item in members),
                    object_ids=object_ids,
                )
            )

        filename = self._source_filename_for_release(release)
        view = FormalDocumentView(
            document_id=canonical.manifest.document_id,
            filename=filename,
            blocks=tuple(blocks),
        )
        return view

    def rebuild(self, release_id: str) -> RebuildVerification:
        release = self.releases.get(release_id)
        report = self.validate(
            release.dataset_id,
            case_revision_ids=tuple(item.case_revision_id for item in release.cases),
            gold_revision_ids=tuple(item.gold_revision_id for item in release.gold),
            required_lifecycle=LifecycleState.FROZEN,
            document_revision_id=release.document.document_revision_id,
            canonical_snapshot=self.releases.canonical_snapshot(release.release_id),
            source_snapshot=self.releases.source_snapshot(release.release_id),
        )
        reproducible = report.report_digest == release.validation_report_digest
        return RebuildVerification(
            release_id=release.release_id,
            reproducible=reproducible,
            validation_report_digest=report.report_digest,
            expected_validation_report_digest=release.validation_report_digest,
            reason=None if reproducible else "pinned input checksum, revision, or validation state changed",
        )

    def _build_release(self, dataset: AuthoringDataset, marker: AuthoringRelease, report: ValidationReport, *, display_name: str, release_version: str, actor: str, parent_release_id: str | None, payload_snapshot_digest: str) -> DatasetRelease:
        document = self.ledger.document_history(dataset.authoring_dataset_id)[-1]
        cases = tuple(self.ledger.get_case_revision(dataset.authoring_dataset_id, item) for item in marker.case_revision_ids)
        gold = tuple(self.ledger.get_gold_revision(dataset.authoring_dataset_id, item) for item in marker.gold_revision_ids)
        source_document = ReleaseDocumentPin(
            document_revision_id=document.document_revision_id,
            document_id=dataset.document_id or "unknown-document",
            source_digest=document.source_digest,
            canonical_digest=document.canonical_contract_digest or "0" * 64,
            parser_identity=document.parser_identity,
            canonicalizer_identity=document.canonicalizer_identity,
            configuration_digest=document.configuration_digest,
        )
        case_pins = tuple(
            ReleaseCasePin(
                case_id=item.case_id,
                case_revision_id=item.case_revision_id,
                source_digest=item.draft.source_digest,
                canonical_digest=item.draft.canonical_contract_digest,
            )
            for item in cases
        )
        gold_pins = tuple(
            ReleaseGoldPin(
                gold_id=item.gold_id,
                gold_revision_id=item.gold_revision_id,
                case_id=item.case_id,
                case_revision_id=item.case_revision_id,
                origin_kind=item.origin.kind.value,
                origin_configuration_digest=item.origin.configuration_digest,
            )
            for item in gold
        )
        revision_ids = {*(item.case_revision_id for item in cases), *(item.gold_revision_id for item in gold)}
        all_case_lineage = {revision.case_revision_id for item in cases for revision in self.ledger.case_history(dataset.authoring_dataset_id, item.case_id)}
        all_gold_lineage = {revision.gold_revision_id for item in gold for revision in self.ledger.gold_history(dataset.authoring_dataset_id, item.gold_id)}
        lineage_ids = all_case_lineage | all_gold_lineage | revision_ids
        reviews = tuple(
            ReleaseReviewPin(review_id=item.review_id, target_revision_id=item.reviewed_revision_id, reviewer_identity=item.reviewer_identity, decision=item.decision.value)
            for item in self.ledger.list_reviews(dataset.authoring_dataset_id)
            if item.reviewed_revision_id in lineage_ids
        )
        approvals = tuple(
            ReleaseApprovalPin(approval_id=item.approval_id, target_revision_id=item.approved_revision_id, approver_identity=item.approver_identity, approver_role=item.approver_role.value)
            for item in self.ledger.list_approvals(dataset.authoring_dataset_id)
            if item.approved_revision_id in lineage_ids
        )
        origins = tuple(sorted({self._origin_pin(item.draft.origin) for item in cases} | {self._origin_pin(item.origin) for item in gold}, key=lambda item: _canonical_digest(item.model_dump(mode="json"))))
        selection = {
            "document": document.model_dump(mode="json"),
            "cases": [item.model_dump(mode="json") for item in cases],
            "gold": [item.model_dump(mode="json") for item in gold],
            "reviews": [item.model_dump(mode="json") for item in reviews],
            "approvals": [item.model_dump(mode="json") for item in approvals],
        }
        events = tuple(
            item.event_id
            for item in self.ledger.list_events(dataset.authoring_dataset_id)
            if item.revision_id in lineage_ids
        )
        return DatasetRelease.build(
            dataset_id=dataset.authoring_dataset_id,
            display_name=display_name,
            release_version=release_version,
            parent_release_id=parent_release_id,
            document=source_document,
            cases=case_pins,
            gold=gold_pins,
            validation_report_digest=report.report_digest,
            payload_snapshot_digest=payload_snapshot_digest,
            schema_versions=ReleaseSchemaVersions(),
            ledger_state=ReleaseLedgerState(ledger_selection_digest=_canonical_digest(selection), source_event_ids=tuple(sorted(events)), authoring_freeze_id=marker.ledger_release_id),
            reviews=tuple(sorted(reviews, key=lambda item: item.review_id)),
            approvals=tuple(sorted(approvals, key=lambda item: item.approval_id)),
            origins=origins,
            created_by=actor,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _origin_pin(origin: AuthoringOrigin) -> ReleaseOriginPin:
        return ReleaseOriginPin(
            origin_kind=origin.kind.value,
            trust_level=origin.trust_level.value,
            generator_identity=origin.generator_identity,
            generator_version=origin.generator_version,
            configuration_digest=origin.configuration_digest,
            source_world=origin.source_world,
            source_document_ids=origin.source_document_ids,
        )

    @staticmethod
    def _diff(parent: DatasetRelease | None, current: DatasetRelease) -> ReleaseChangeSet:
        if parent is None:
            return ReleaseChangeSet()
        parent_cases = {item.case_id: item.case_revision_id for item in parent.cases}
        current_cases = {item.case_id: item.case_revision_id for item in current.cases}
        parent_gold = {item.gold_id: item.gold_revision_id for item in parent.gold}
        current_gold = {item.gold_id: item.gold_revision_id for item in current.gold}
        return ReleaseChangeSet(
            parent_release_id=parent.release_id,
            added_case_ids=tuple(sorted(set(current_cases).difference(parent_cases))),
            removed_case_ids=tuple(sorted(set(parent_cases).difference(current_cases))),
            changed_case_ids=tuple(sorted(case_id for case_id in set(parent_cases).intersection(current_cases) if parent_cases[case_id] != current_cases[case_id])),
            added_gold_ids=tuple(sorted(set(current_gold).difference(parent_gold))),
            removed_gold_ids=tuple(sorted(set(parent_gold).difference(current_gold))),
            changed_gold_ids=tuple(sorted(gold_id for gold_id in set(parent_gold).intersection(current_gold) if parent_gold[gold_id] != current_gold[gold_id])),
            document_changed=parent.document.canonical_digest != current.document.canonical_digest or parent.document.source_digest != current.document.source_digest,
        )


def build_source_faithful_document_view(
    *,
    canonical: CanonicalDocument,
    source_path: Path,
    filename: str,
) -> FormalDocumentView:
    """Project one Canonical document into the shared local reading surface.

    This is intentionally a read-only UI projection.  It preserves the exact
    object IDs needed for highlighting but does not become a second Canonical
    or Gold source of truth.  Both a published release and an editable DOCX
    workspace use this same projection so the user sees the document the same
    way in review and after publication.
    """

    source_text_by_body = FormalDatasetReleaseService._source_paragraph_text_by_body(source_path)
    source_layout_by_body = FormalDatasetReleaseService._source_paragraph_layout_by_body(source_path)
    groups: dict[int, list[CanonicalObject]] = {}
    for item in canonical.objects:
        ordinal = FormalDatasetReleaseService._source_body_ordinal(item)
        if ordinal is None:
            continue
        groups.setdefault(ordinal, []).append(item)

    blocks: list[FormalDocumentBlock] = []
    primary_types = {"heading", "paragraph", "caption"}
    table_types = {
        "table",
        "row",
        "cell",
        "logical_row",
        "logical_column",
        "logical_cell",
    }
    for ordinal in sorted(groups):
        members = sorted(groups[ordinal], key=lambda item: item.document_order)
        object_ids = tuple(item.object_id for item in members)
        page_break_before, list_level = source_layout_by_body.get(ordinal, (False, None))
        table = next((item for item in members if item.object_type.value == "table"), None)
        if table is not None:
            table_id = table.object_id
            table_members = [
                item
                for item in members
                if item.object_type.value in table_types
                and (
                    item.object_type.value == "table"
                    or item.attributes.get("table_id") == table_id
                )
            ]
            logical_cells = [
                item
                for item in table_members
                if item.object_type.value == "logical_cell"
            ]
            cells_source = logical_cells or [
                item for item in table_members if item.object_type.value == "cell"
            ]
            physical_by_id = {
                item.object_id: item
                for item in table_members
                if item.object_type.value == "cell"
            }
            cells: list[FormalDocumentCell] = []
            for cell in sorted(
                cells_source,
                key=lambda item: (
                    int(item.attributes.get("row", item.attributes.get("logical_row_start", 0))),
                    int(
                        item.attributes.get(
                            "column", item.attributes.get("logical_column_start", 0)
                        )
                    ),
                    item.document_order,
                ),
            ):
                attrs = cell.attributes
                row = int(attrs.get("row", attrs.get("logical_row_start", 1)))
                column = int(attrs.get("column", attrs.get("logical_column_start", 1)))
                row_span = int(attrs.get("row_span", 1) or 1)
                column_span = int(attrs.get("column_span", attrs.get("grid_span", 1)) or 1)
                related_ids = [cell.object_id]
                for key in (
                    "origin_physical_cell_id",
                    "logical_cell_id",
                    "row_id",
                    "logical_row_id",
                ):
                    value = attrs.get(key)
                    if isinstance(value, str) and value not in related_ids:
                        related_ids.append(value)
                origin_id = attrs.get("origin_physical_cell_id")
                origin = physical_by_id.get(origin_id) if isinstance(origin_id, str) else None
                if origin is not None:
                    row_id = origin.attributes.get("row_id")
                    if isinstance(row_id, str) and row_id not in related_ids:
                        related_ids.append(row_id)
                for column_id in attrs.get("logical_column_ids", ()):
                    if isinstance(column_id, str) and column_id not in related_ids:
                        related_ids.append(column_id)
                cells.append(
                    FormalDocumentCell(
                        text=cell.canonical_value or "",
                        row=max(1, row),
                        column=max(1, column),
                        row_span=max(1, row_span),
                        column_span=max(1, column_span),
                        object_ids=tuple(related_ids),
                    )
                )
            blocks.append(
                FormalDocumentBlock(
                    block_id=table_id,
                    kind="table",
                    text=table.canonical_value or "",
                    document_order=min(item.document_order for item in members),
                    object_ids=object_ids,
                    cells=tuple(cells),
                    page_break_before=page_break_before,
                )
            )
            continue

        primary = next(
            (item for item in members if item.object_type.value in primary_types), None
        )
        if primary is None:
            primary = next(
                (
                    item
                    for item in members
                    if item.object_type.value
                    in {"figure", "equation", "reference", "footnote", "endnote"}
                ),
                None,
            )
        if primary is None:
            continue
        text = primary.canonical_value or ""
        if primary.object_type.value == "caption":
            text = source_text_by_body.get(ordinal, text)
        if not text:
            text = "\n".join(
                item.canonical_value or ""
                for item in members
                if item.canonical_value
            )
        heading_level: int | None = None
        if primary.object_type.value == "heading":
            for member in members:
                if member.object_type.value != "section":
                    continue
                for span in member.provenance.source_spans:
                    value = span.coordinates.get("heading_level")
                    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 9:
                        heading_level = value
                        break
                if heading_level is not None:
                    break
        blocks.append(
            FormalDocumentBlock(
                block_id=primary.object_id,
                kind=primary.object_type.value,
                text=text,
                document_order=min(item.document_order for item in members),
                object_ids=object_ids,
                heading_level=heading_level,
                page_break_before=page_break_before,
                list_level=list_level,
            )
        )

    return FormalDocumentView(
        document_id=canonical.manifest.document_id,
        filename=filename,
        blocks=tuple(blocks),
    )
