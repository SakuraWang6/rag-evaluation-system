"""Lossless, release-derived Bundle 3.0 delivery format.

Bundle 3.0 is an immutable projection of frozen Dataset Release lineage.  It
is intentionally *not* an Authoring importer and never becomes the source of
truth for Canonical, Ledger, Gold, review, or release data.  A private
evaluation package and a separately exportable runtime-only view make the
Gold-leak boundary explicit in both the contract and filesystem layout.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.authoring.ledger import (
    Adjudication,
    Approval,
    AuthoringLedger,
    CaseRevision,
    EvidenceRole,
    GoldEvidence,
    GoldRevision,
    LifecycleState,
    Review,
)
from rag_eval.authoring.storage import AuthoringWorkspaceStore
from rag_eval.contracts.canonical import CanonicalDocument, CanonicalObject
from rag_eval.datasets.bundle import canonical_file_hashes, digest_file_hashes
from rag_eval.datasets.formal import (
    DatasetRelease,
    DatasetReleaseStore,
    FormalDatasetError,
    ReleaseCasePin,
    ReleaseGoldPin,
    ValidationReport,
)
from rag_eval.datasets.portfolio import (
    BenchmarkPortfolio,
    PortfolioAssignment,
    PortfolioSlot,
    PortfolioSlotState,
    PortfolioStore,
)
from rag_eval.storage.atomic import atomic_write_bytes
from rag_eval.storage.runs import safe_id


BUNDLE_V3_SCHEMA_VERSION = "dataset-bundle/3.0"
BUNDLE_V3_RUNTIME_SCHEMA_VERSION = "dataset-bundle-runtime/3.0"
BUNDLE_V3_BUILDER_VERSION = "rag-eval-bundle-v3-builder/1.0"


class BundleV3IntegrityError(ValueError):
    """A Bundle 3.0 artifact is incomplete, altered, or semantically lossy."""


class BundleV3Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _canonical_bytes(value: object) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _jsonl_bytes(values: Iterable[BaseModel]) -> bytes:
    return b"".join(_canonical_bytes(value) for value in values)


def _digest_value(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _read_jsonl(path: Path, model: type[BaseModel]) -> list[BaseModel]:
    values: list[BaseModel] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            values.append(model.model_validate_json(line))
        except Exception as exc:
            raise BundleV3IntegrityError(f"{path.relative_to(path.parents[2])}:{line_number}: {exc}") from exc
    return values


class BundleV3ReleasePin(BundleV3Model):
    release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    release_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_release_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    release_version: str = Field(min_length=1)
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    validation_report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_document_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def from_release(cls, release: DatasetRelease) -> "BundleV3ReleasePin":
        return cls(
            release_id=release.release_id,
            release_digest=release.release_digest,
            parent_release_id=release.parent_release_id,
            release_version=release.release_version,
            dataset_id=release.dataset_id,
            validation_report_digest=release.validation_report_digest,
            canonical_document_digest=release.document.canonical_digest,
            source_digest=release.document.source_digest,
        )


class BundleV3CanonicalPin(BundleV3Model):
    release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    document_id: str = Field(min_length=1)
    canonical_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: Literal["1.0", "1.1", "1.2"]
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_path: str = Field(min_length=1)
    objects_path: str = Field(min_length=1)
    relations_path: str = Field(min_length=1)


class BundleV3SourcePin(BundleV3Model):
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_path: str = Field(min_length=1)
    document_ids: tuple[str, ...] = Field(min_length=1)


class BundleV3Manifest(BundleV3Model):
    schema_version: Literal[BUNDLE_V3_SCHEMA_VERSION] = BUNDLE_V3_SCHEMA_VERSION
    builder_version: Literal[BUNDLE_V3_BUILDER_VERSION] = BUNDLE_V3_BUILDER_VERSION
    target_release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    target_release_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    release_chain: tuple[BundleV3ReleasePin, ...] = Field(min_length=1)
    canonical_documents: tuple[BundleV3CanonicalPin, ...] = Field(min_length=1)
    source_documents: tuple[BundleV3SourcePin, ...] = Field(min_length=1)
    case_count: int = Field(ge=1)
    gold_count: int = Field(ge=1)
    evidence_count: int = Field(ge=1)
    runtime_manifest_path: Literal["runtime/manifest.json"] = "runtime/manifest.json"
    private_dataset_path: Literal["private/dataset.json"] = "private/dataset.json"

    @model_validator(mode="after")
    def _validate_lineage(self) -> "BundleV3Manifest":
        if self.release_chain[-1].release_id != self.target_release_id:
            raise ValueError("target release must be the final release-chain member")
        if self.release_chain[-1].release_digest != self.target_release_digest:
            raise ValueError("target release digest must match final release-chain member")
        if len({item.release_id for item in self.release_chain}) != len(self.release_chain):
            raise ValueError("release chain contains duplicate release IDs")
        if any(item.dataset_id != self.dataset_id for item in self.release_chain):
            raise ValueError("all release-chain members must belong to the Bundle dataset")
        if len({item.release_id for item in self.canonical_documents}) != len(self.canonical_documents):
            raise ValueError("Canonical pins must have one record per release")
        if not {item.release_id for item in self.canonical_documents}.issubset(
            {item.release_id for item in self.release_chain}
        ):
            raise ValueError("Canonical pin references a release outside the release chain")
        return self


class BundleV3Dataset(BundleV3Model):
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    target_release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    release_chain_ids: tuple[str, ...] = Field(min_length=1)
    release_chain_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_count: int = Field(ge=1)
    gold_count: int = Field(ge=1)


class BundleV3PortfolioBinding(BundleV3Model):
    portfolio_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    portfolio_contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    slot: PortfolioSlot
    assignment: PortfolioAssignment

    @model_validator(mode="after")
    def _validate_binding(self) -> "BundleV3PortfolioBinding":
        if self.slot.slot_id != self.assignment.slot_id:
            raise ValueError("Portfolio binding slot and assignment differ")
        if self.assignment.state != PortfolioSlotState.FROZEN:
            raise ValueError("Bundle 3.0 requires a frozen Portfolio assignment")
        return self


class BundleV3CaseRecord(BundleV3Model):
    release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    case: CaseRevision
    portfolio: BundleV3PortfolioBinding

    @model_validator(mode="after")
    def _validate_case(self) -> "BundleV3CaseRecord":
        if self.case.lifecycle != LifecycleState.FROZEN:
            raise ValueError("Bundle 3.0 Case must be frozen")
        if self.portfolio.assignment.links.case_revision_id != self.case.case_revision_id:
            raise ValueError("Portfolio binding does not pin this Case revision")
        return self


class BundleV3GoldRecord(BundleV3Model):
    release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    gold: GoldRevision

    @model_validator(mode="after")
    def _validate_gold(self) -> "BundleV3GoldRecord":
        if self.gold.lifecycle != LifecycleState.FROZEN:
            raise ValueError("Bundle 3.0 Gold must be frozen")
        return self


class BundleV3EvidenceRecord(BundleV3Model):
    evidence_key: str = Field(min_length=1)
    release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    gold_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    gold_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    evidence_id: str = Field(min_length=1)
    role: EvidenceRole
    origin: Literal["gold_payload", "negative_scope_projection"]
    source_evidence: GoldEvidence | None = None
    canonical: CanonicalObject

    @model_validator(mode="after")
    def _validate_evidence(self) -> "BundleV3EvidenceRecord":
        if self.canonical.object_id != self.canonical.object_id.strip():
            raise ValueError("Canonical object ID must be normalized")
        if self.origin == "gold_payload":
            if self.source_evidence is None:
                raise ValueError("Gold-payload evidence must retain its source evidence record")
            if self.source_evidence.evidence_id != self.evidence_id:
                raise ValueError("evidence ID does not match source Gold evidence")
            if self.source_evidence.role != self.role:
                raise ValueError("evidence role does not match source Gold evidence")
            if self.source_evidence.canonical_object_id != self.canonical.object_id:
                raise ValueError("Gold evidence canonical object does not match locator witness")
        elif self.source_evidence is not None or self.role != EvidenceRole.NEGATIVE_SCOPE:
            raise ValueError("negative-scope projection must be role-only and cannot alter Gold evidence")
        if not self.canonical.provenance.source_spans:
            raise ValueError("Bundle evidence must retain Canonical source spans")
        return self


class BundleV3RuntimeQuestion(BundleV3Model):
    """The only Case representation allowed to enter a system-under-test view."""

    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    case_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    question: str = Field(min_length=1)
    language: str = Field(min_length=1)
    portfolio_slot: PortfolioSlot


class BundleV3RuntimeManifest(BundleV3Model):
    schema_version: Literal[BUNDLE_V3_RUNTIME_SCHEMA_VERSION] = BUNDLE_V3_RUNTIME_SCHEMA_VERSION
    target_release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    questions_path: Literal["questions.jsonl"] = "questions.jsonl"
    source_documents: tuple[BundleV3SourcePin, ...] = Field(min_length=1)
    case_count: int = Field(ge=1)


@dataclass(frozen=True, slots=True)
class DatasetBundleV3:
    root: Path
    bundle_id: str
    manifest: BundleV3Manifest
    dataset: BundleV3Dataset
    cases: tuple[BundleV3CaseRecord, ...]
    gold: tuple[BundleV3GoldRecord, ...]
    evidence: tuple[BundleV3EvidenceRecord, ...]
    canonical_documents: dict[str, CanonicalDocument]


@dataclass(frozen=True, slots=True)
class DatasetBundleV3Runtime:
    root: Path
    runtime_bundle_id: str
    manifest: BundleV3RuntimeManifest
    questions: tuple[BundleV3RuntimeQuestion, ...]


def _canonical_path(release_id: str, filename: str) -> str:
    return f"private/canonical/{safe_id(release_id)}/{filename}"


def _release_chain(releases: DatasetReleaseStore, target_release_id: str) -> tuple[DatasetRelease, ...]:
    values: list[DatasetRelease] = []
    seen: set[str] = set()
    current = releases.get(target_release_id)
    while True:
        if current.release_id in seen:
            raise BundleV3IntegrityError("Dataset Release parent lineage contains a cycle")
        seen.add(current.release_id)
        values.append(current)
        if current.parent_release_id is None:
            break
        current = releases.get(current.parent_release_id)
    values.reverse()
    if len({item.dataset_id for item in values}) != 1:
        raise BundleV3IntegrityError("a Bundle release chain cannot cross Dataset IDs")
    return tuple(values)


def _effective_release_selection(
    chain: tuple[DatasetRelease, ...],
) -> dict[str, tuple[DatasetRelease, ReleaseCasePin, ReleaseGoldPin]]:
    """Apply append-only successor releases to their complete lineage closure."""

    selected: dict[str, tuple[DatasetRelease, ReleaseCasePin, ReleaseGoldPin]] = {}
    for release in chain:
        gold_by_case = {item.case_id: item for item in release.gold}
        if set(gold_by_case) != {item.case_id for item in release.cases}:
            raise BundleV3IntegrityError(f"{release.release_id}: Case/Gold release pins diverge")
        for case in release.cases:
            gold = gold_by_case[case.case_id]
            selected[case.case_id] = (release, case, gold)
    if not selected:
        raise BundleV3IntegrityError("release chain contains no selected Case/Gold pairs")
    return dict(sorted(selected.items()))


class BundleV3Builder:
    """Builds a Bundle only from frozen Release snapshots and Ledger records."""

    def __init__(
        self,
        *,
        releases: DatasetReleaseStore,
        authoring_store: AuthoringWorkspaceStore,
        portfolios: PortfolioStore,
    ) -> None:
        self.releases = releases
        self.authoring_store = authoring_store
        self.ledger = AuthoringLedger(authoring_store)
        self.portfolios = portfolios

    def materialize(self, target_release_id: str) -> "BundleV3Materialization":
        chain = _release_chain(self.releases, target_release_id)
        dataset_id = chain[-1].dataset_id
        selected = _effective_release_selection(chain)
        canonicals: dict[str, CanonicalDocument] = {}
        reports: dict[str, ValidationReport] = {}
        source_payloads: dict[str, bytes] = {}
        for release in chain:
            report = self.releases.reports.get(release.validation_report_digest)
            if report.has_errors:
                raise BundleV3IntegrityError(
                    f"{release.release_id}: ERROR validation report cannot produce Bundle 3.0"
                )
            if report.dataset_id != dataset_id:
                raise BundleV3IntegrityError(f"{release.release_id}: validation report dataset mismatch")
            canonical = self.releases.canonical_snapshot(release.release_id)
            if canonical.manifest.canonical_digest != release.document.canonical_digest:
                raise BundleV3IntegrityError(f"{release.release_id}: canonical snapshot digest differs from release pin")
            if canonical.manifest.source_sha256 != release.document.source_digest:
                raise BundleV3IntegrityError(f"{release.release_id}: canonical source digest differs from release pin")
            source = self.releases.source_snapshot(release.release_id).read_bytes()
            if hashlib.sha256(source).hexdigest() != release.document.source_digest:
                raise BundleV3IntegrityError(f"{release.release_id}: source snapshot digest differs from release pin")
            canonicals[release.release_id] = canonical
            reports[release.validation_report_digest] = report
            source_payloads.setdefault(release.document.source_digest, source)

        cases: list[BundleV3CaseRecord] = []
        gold: list[BundleV3GoldRecord] = []
        evidence: list[BundleV3EvidenceRecord] = []
        for case_id, (release, case_pin, gold_pin) in selected.items():
            case = self.ledger.get_case_revision(dataset_id, case_pin.case_revision_id)
            gold_revision = self.ledger.get_gold_revision(dataset_id, gold_pin.gold_revision_id)
            self._validate_selected_revisions(release, case_pin, gold_pin, case, gold_revision)
            binding = self._portfolio_binding(
                release_chain_ids={item.release_id for item in chain},
                dataset_id=dataset_id,
                case=case,
                gold=gold_revision,
            )
            cases.append(BundleV3CaseRecord(release_id=release.release_id, case=case, portfolio=binding))
            gold.append(BundleV3GoldRecord(release_id=release.release_id, gold=gold_revision))
            objects = {item.object_id: item for item in canonicals[release.release_id].objects}
            evidence.extend(self._evidence_records(release, gold_revision, objects))

        reviews, approvals, adjudications = self._lineage_records(chain, dataset_id)
        pins = tuple(BundleV3ReleasePin.from_release(release) for release in chain)
        canonical_pins = tuple(
            BundleV3CanonicalPin(
                release_id=release.release_id,
                document_id=canonical.manifest.document_id,
                canonical_digest=canonical.manifest.canonical_digest,
                schema_version=canonical.manifest.schema_version,
                source_digest=canonical.manifest.source_sha256,
                manifest_path=_canonical_path(release.release_id, "manifest.json"),
                objects_path=_canonical_path(release.release_id, "objects.jsonl"),
                relations_path=_canonical_path(release.release_id, "relations.jsonl"),
            )
            for release, canonical in ((release, canonicals[release.release_id]) for release in chain)
        )
        source_pins = tuple(
            BundleV3SourcePin(
                source_digest=digest,
                runtime_path=f"source/{digest}.docx",
                document_ids=tuple(sorted({canonical.manifest.document_id for canonical in canonicals.values() if canonical.manifest.source_sha256 == digest})),
            )
            for digest in sorted(source_payloads)
        )
        cases.sort(key=lambda item: item.case.case_id)
        gold.sort(key=lambda item: item.gold.gold_id)
        evidence.sort(key=lambda item: item.evidence_key)
        if len({item.evidence_key for item in evidence}) != len(evidence):
            raise BundleV3IntegrityError("Bundle evidence projection produced duplicate keys")
        dataset = BundleV3Dataset(
            dataset_id=dataset_id,
            target_release_id=chain[-1].release_id,
            release_chain_ids=tuple(item.release_id for item in chain),
            release_chain_digest=_digest_value([item.model_dump(mode="json") for item in pins]),
            case_count=len(cases),
            gold_count=len(gold),
        )
        manifest = BundleV3Manifest(
            target_release_id=chain[-1].release_id,
            target_release_digest=chain[-1].release_digest,
            dataset_id=dataset_id,
            release_chain=pins,
            canonical_documents=canonical_pins,
            source_documents=source_pins,
            case_count=len(cases),
            gold_count=len(gold),
            evidence_count=len(evidence),
        )
        runtime = BundleV3RuntimeManifest(
            target_release_id=manifest.target_release_id,
            dataset_id=dataset_id,
            source_documents=source_pins,
            case_count=len(cases),
        )
        runtime_questions = tuple(
            BundleV3RuntimeQuestion(
                case_id=item.case.case_id,
                case_revision_id=item.case.case_revision_id,
                question=item.case.draft.question,
                language=item.case.draft.language,
                portfolio_slot=item.portfolio.slot,
            )
            for item in cases
        )
        return BundleV3Materialization(
            manifest=manifest,
            dataset=dataset,
            cases=tuple(cases),
            gold=tuple(gold),
            evidence=tuple(evidence),
            canonical_documents=canonicals,
            source_payloads=source_payloads,
            releases=chain,
            validation_reports=reports,
            reviews=reviews,
            approvals=approvals,
            adjudications=adjudications,
            runtime_manifest=runtime,
            runtime_questions=runtime_questions,
        )

    @staticmethod
    def _validate_selected_revisions(
        release: DatasetRelease,
        case_pin: ReleaseCasePin,
        gold_pin: ReleaseGoldPin,
        case: CaseRevision,
        gold: GoldRevision,
    ) -> None:
        if case.case_id != case_pin.case_id or case.case_revision_id != case_pin.case_revision_id:
            raise BundleV3IntegrityError(f"{release.release_id}: Case revision differs from release pin")
        if gold.gold_id != gold_pin.gold_id or gold.gold_revision_id != gold_pin.gold_revision_id:
            raise BundleV3IntegrityError(f"{release.release_id}: Gold revision differs from release pin")
        if gold.case_id != case.case_id or gold.case_revision_id != case.case_revision_id:
            raise BundleV3IntegrityError(f"{release.release_id}: Gold does not pin the selected Case revision")
        if case.lifecycle != LifecycleState.FROZEN or gold.lifecycle != LifecycleState.FROZEN:
            raise BundleV3IntegrityError(f"{release.release_id}: Bundle 3.0 needs frozen Case and Gold revisions")
        if case.draft.source_digest != release.document.source_digest:
            raise BundleV3IntegrityError(f"{case.case_revision_id}: source digest differs from release document")
        if case.draft.canonical_contract_digest not in {None, release.document.canonical_digest}:
            raise BundleV3IntegrityError(f"{case.case_revision_id}: Canonical digest differs from release document")

    def _portfolio_binding(
        self,
        *,
        release_chain_ids: set[str],
        dataset_id: str,
        case: CaseRevision,
        gold: GoldRevision,
    ) -> BundleV3PortfolioBinding:
        matches: list[BundleV3PortfolioBinding] = []
        for path in sorted(self.portfolios.root.glob("*/portfolio.json")):
            portfolio = self.portfolios.get(path.parent.name)
            for slot in portfolio.slots:
                assignment = self.portfolios.current_assignment(portfolio.portfolio_id, slot.slot_id)
                if assignment is None or assignment.state != PortfolioSlotState.FROZEN:
                    continue
                links = assignment.links
                if links.dataset_id != dataset_id or links.case_revision_id != case.case_revision_id:
                    continue
                if links.gold_revision_id != gold.gold_revision_id or links.release_id not in release_chain_ids:
                    continue
                matches.append(
                    BundleV3PortfolioBinding(
                        portfolio_id=portfolio.portfolio_id,
                        portfolio_contract_digest=portfolio.contract_digest,
                        slot=slot,
                        assignment=assignment,
                    )
                )
        if len(matches) != 1:
            raise BundleV3IntegrityError(
                f"{case.case_revision_id}: requires exactly one frozen typed Portfolio binding, found {len(matches)}"
            )
        return matches[0]

    @staticmethod
    def _evidence_records(
        release: DatasetRelease,
        gold: GoldRevision,
        objects: dict[str, CanonicalObject],
    ) -> list[BundleV3EvidenceRecord]:
        values: list[BundleV3EvidenceRecord] = []
        covered_negative: set[str] = set()
        for evidence in gold.payload.evidence:
            canonical = objects.get(evidence.canonical_object_id)
            if canonical is None:
                raise BundleV3IntegrityError(f"{gold.gold_revision_id}: evidence points outside release Canonical snapshot")
            if not canonical.gold_evidence_eligible:
                raise BundleV3IntegrityError(f"{gold.gold_revision_id}: evidence points to a non-eligible Canonical object")
            values.append(
                BundleV3EvidenceRecord(
                    evidence_key=f"{gold.gold_revision_id}:{evidence.evidence_id}",
                    release_id=release.release_id,
                    case_id=gold.case_id,
                    gold_id=gold.gold_id,
                    gold_revision_id=gold.gold_revision_id,
                    evidence_id=evidence.evidence_id,
                    role=evidence.role,
                    origin="gold_payload",
                    source_evidence=evidence,
                    canonical=canonical,
                )
            )
            if evidence.role == EvidenceRole.NEGATIVE_SCOPE:
                covered_negative.add(evidence.canonical_object_id)
        for index, object_id in enumerate(gold.payload.negative_scope_object_ids, 1):
            canonical = objects.get(object_id)
            if canonical is None or not canonical.gold_evidence_eligible:
                raise BundleV3IntegrityError(f"{gold.gold_revision_id}: negative scope is not reachable Gold evidence")
            if object_id in covered_negative:
                continue
            values.append(
                BundleV3EvidenceRecord(
                    evidence_key=f"{gold.gold_revision_id}:negative-scope:{index:04d}",
                    release_id=release.release_id,
                    case_id=gold.case_id,
                    gold_id=gold.gold_id,
                    gold_revision_id=gold.gold_revision_id,
                    evidence_id=f"negative-scope-{index:04d}",
                    role=EvidenceRole.NEGATIVE_SCOPE,
                    origin="negative_scope_projection",
                    canonical=canonical,
                )
            )
        return values

    def _lineage_records(
        self,
        chain: tuple[DatasetRelease, ...],
        dataset_id: str,
    ) -> tuple[tuple[Review, ...], tuple[Approval, ...], tuple[Adjudication, ...]]:
        review_by_id = {item.review_id: item for item in self.ledger.list_reviews(dataset_id)}
        approval_by_id = {item.approval_id: item for item in self.ledger.list_approvals(dataset_id)}
        review_ids = {item.review_id for release in chain for item in release.reviews}
        approval_ids = {item.approval_id for release in chain for item in release.approvals}
        missing_reviews = sorted(review_ids.difference(review_by_id))
        missing_approvals = sorted(approval_ids.difference(approval_by_id))
        if missing_reviews or missing_approvals:
            raise BundleV3IntegrityError(
                f"release review/approval pin is missing from Ledger: reviews={missing_reviews}, approvals={missing_approvals}"
            )
        reviews = tuple(sorted((review_by_id[item] for item in review_ids), key=lambda item: item.review_id))
        approvals = tuple(sorted((approval_by_id[item] for item in approval_ids), key=lambda item: item.approval_id))
        adjudications = tuple(
            sorted(
                (
                    item
                    for item in self.ledger.list_adjudications(dataset_id)
                    if set(item.review_ids).intersection(review_ids)
                ),
                key=lambda item: item.adjudication_id,
            )
        )
        return reviews, approvals, adjudications


@dataclass(frozen=True, slots=True)
class BundleV3Materialization:
    manifest: BundleV3Manifest
    dataset: BundleV3Dataset
    cases: tuple[BundleV3CaseRecord, ...]
    gold: tuple[BundleV3GoldRecord, ...]
    evidence: tuple[BundleV3EvidenceRecord, ...]
    canonical_documents: dict[str, CanonicalDocument]
    source_payloads: dict[str, bytes]
    releases: tuple[DatasetRelease, ...]
    validation_reports: dict[str, ValidationReport]
    reviews: tuple[Review, ...]
    approvals: tuple[Approval, ...]
    adjudications: tuple[Adjudication, ...]
    runtime_manifest: BundleV3RuntimeManifest
    runtime_questions: tuple[BundleV3RuntimeQuestion, ...]


class BundleV3Store:
    """Content-addressed immutable private Bundle 3.0 package store."""

    def __init__(
        self,
        root: Path,
        *,
        releases: DatasetReleaseStore,
        authoring_store: AuthoringWorkspaceStore,
        portfolios: PortfolioStore,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.builder = BundleV3Builder(
            releases=releases,
            authoring_store=authoring_store,
            portfolios=portfolios,
        )

    def build_from_release(self, target_release_id: str) -> DatasetBundleV3:
        material = self.builder.materialize(target_release_id)
        staging = Path(tempfile.mkdtemp(prefix=".bundle-v3-", dir=self.root))
        try:
            self._write(staging, material)
            built = load_bundle_v3(staging)
            destination = self.root / built.bundle_id
            if destination.exists():
                existing = load_bundle_v3(destination)
                if existing.manifest != built.manifest:
                    raise BundleV3IntegrityError("content-address collision with different Bundle manifest")
                return existing
            staging.rename(destination)
            return load_bundle_v3(destination)
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise

    def get(self, bundle_id: str) -> DatasetBundleV3:
        if not bundle_id or any(char not in "0123456789abcdef" for char in bundle_id):
            raise ValueError("Bundle 3.0 ID must be a lowercase hexadecimal digest")
        bundle = load_bundle_v3(self.root / bundle_id)
        if bundle.bundle_id != bundle_id:
            raise BundleV3IntegrityError("Bundle directory name differs from content-address")
        return bundle

    def list_manifests(self) -> list[BundleV3Manifest]:
        """List sealed Bundle 3.0 manifests without opening private records."""
        return [manifest for _bundle_id, manifest in self.list_manifest_records()]

    def list_manifest_records(self) -> list[tuple[str, BundleV3Manifest]]:
        """List ``(bundle_id, manifest)`` pairs from sealed Bundle 3.0 roots.

        The content address is intentionally carried by the directory name,
        rather than copied into the manifest.  Keeping the pair here avoids
        callers having to infer an ID from a manifest that does not contain it.
        """
        values: list[tuple[str, BundleV3Manifest]] = []
        for path in sorted(self.root.glob("*/manifest.json")):
            bundle_id = path.parent.name
            if len(bundle_id) != 64 or any(char not in "0123456789abcdef" for char in bundle_id):
                continue
            try:
                manifest = BundleV3Manifest.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            values.append((bundle_id, manifest))
        return values

    @staticmethod
    def _bundle_id_for_manifest(_manifest: BundleV3Manifest, directory_name: str) -> str:
        # The manifest itself deliberately does not contain its content address;
        # the directory is the identity after checksums have been validated by
        # ``get``.  Catalog listing therefore only accepts digest-shaped IDs.
        if len(directory_name) != 64 or any(char not in "0123456789abcdef" for char in directory_name):
            return ""
        return directory_name

    def export_runtime_view(self, bundle_id: str, runtime_root: Path) -> DatasetBundleV3Runtime:
        bundle = self.get(bundle_id)
        source = bundle.root / "runtime"
        runtime_root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".bundle-v3-runtime-", dir=runtime_root))
        try:
            for path in sorted(item for item in source.rglob("*") if item.is_file()):
                relative = path.relative_to(source)
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_bytes(target, path.read_bytes())
            runtime = load_bundle_v3_runtime(staging)
            destination = runtime_root / runtime.runtime_bundle_id
            if destination.exists():
                existing = load_bundle_v3_runtime(destination)
                if existing.manifest != runtime.manifest:
                    raise BundleV3IntegrityError("runtime content-address collision")
                return existing
            staging.rename(destination)
            return load_bundle_v3_runtime(destination)
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise

    @staticmethod
    def _write(root: Path, material: BundleV3Materialization) -> None:
        atomic_write_bytes(root / "manifest.json", _canonical_bytes(material.manifest))
        atomic_write_bytes(root / "private/dataset.json", _canonical_bytes(material.dataset))
        atomic_write_bytes(root / "private/cases.jsonl", _jsonl_bytes(material.cases))
        atomic_write_bytes(root / "private/gold.jsonl", _jsonl_bytes(material.gold))
        atomic_write_bytes(root / "private/evidence.jsonl", _jsonl_bytes(material.evidence))
        atomic_write_bytes(root / "private/lineage/releases.jsonl", _jsonl_bytes(material.releases))
        atomic_write_bytes(root / "private/lineage/reviews.jsonl", _jsonl_bytes(material.reviews))
        atomic_write_bytes(root / "private/lineage/approvals.jsonl", _jsonl_bytes(material.approvals))
        atomic_write_bytes(root / "private/lineage/adjudications.jsonl", _jsonl_bytes(material.adjudications))
        for report in sorted(material.validation_reports.values(), key=lambda item: item.report_digest):
            atomic_write_bytes(
                root / f"private/lineage/validation/{report.report_digest}.json",
                _canonical_bytes(report),
            )
        for release_id, canonical in sorted(material.canonical_documents.items()):
            atomic_write_bytes(root / _canonical_path(release_id, "manifest.json"), _canonical_bytes(canonical.manifest))
            atomic_write_bytes(root / _canonical_path(release_id, "objects.jsonl"), _jsonl_bytes(canonical.objects))
            atomic_write_bytes(root / _canonical_path(release_id, "relations.jsonl"), _jsonl_bytes(canonical.relations))
        atomic_write_bytes(root / "runtime/manifest.json", _canonical_bytes(material.runtime_manifest))
        atomic_write_bytes(root / "runtime/questions.jsonl", _jsonl_bytes(material.runtime_questions))
        for digest, payload in sorted(material.source_payloads.items()):
            atomic_write_bytes(root / f"runtime/source/{digest}.docx", payload)
        runtime_files = canonical_file_hashes(root / "runtime")
        atomic_write_bytes(
            root / "runtime/checksums.json",
            _canonical_bytes({"schema_version": BUNDLE_V3_RUNTIME_SCHEMA_VERSION, "runtime_bundle_id": digest_file_hashes(runtime_files), "files": runtime_files}),
        )
        files = canonical_file_hashes(root)
        atomic_write_bytes(
            root / "checksums.json",
            _canonical_bytes({"schema_version": BUNDLE_V3_SCHEMA_VERSION, "bundle_id": digest_file_hashes(files), "files": files}),
        )


def load_bundle_v3(root: Path) -> DatasetBundleV3:
    root = root.resolve()
    required = (
        "manifest.json",
        "checksums.json",
        "runtime/manifest.json",
        "runtime/questions.jsonl",
        "runtime/checksums.json",
        "private/dataset.json",
        "private/cases.jsonl",
        "private/gold.jsonl",
        "private/evidence.jsonl",
        "private/lineage/releases.jsonl",
        "private/lineage/reviews.jsonl",
        "private/lineage/approvals.jsonl",
        "private/lineage/adjudications.jsonl",
    )
    if any(not (root / item).is_file() for item in required):
        missing = [item for item in required if not (root / item).is_file()]
        raise BundleV3IntegrityError(f"Bundle 3.0 is missing required artifact(s): {missing}")
    _validate_checksums(root, schema_version=BUNDLE_V3_SCHEMA_VERSION, key="bundle_id")
    manifest = BundleV3Manifest.model_validate_json((root / "manifest.json").read_text(encoding="utf-8"))
    dataset = BundleV3Dataset.model_validate_json((root / "private/dataset.json").read_text(encoding="utf-8"))
    cases = tuple(_read_jsonl(root / "private/cases.jsonl", BundleV3CaseRecord))
    gold = tuple(_read_jsonl(root / "private/gold.jsonl", BundleV3GoldRecord))
    evidence = tuple(_read_jsonl(root / "private/evidence.jsonl", BundleV3EvidenceRecord))
    releases = tuple(_read_jsonl(root / "private/lineage/releases.jsonl", DatasetRelease))
    reviews = tuple(_read_jsonl(root / "private/lineage/reviews.jsonl", Review))
    approvals = tuple(_read_jsonl(root / "private/lineage/approvals.jsonl", Approval))
    adjudications = tuple(_read_jsonl(root / "private/lineage/adjudications.jsonl", Adjudication))
    canonical_documents = _load_canonical_documents(root, manifest)
    _validate_bundle_v3(
        root=root,
        manifest=manifest,
        dataset=dataset,
        cases=cases,
        gold=gold,
        evidence=evidence,
        releases=releases,
        reviews=reviews,
        approvals=approvals,
        adjudications=adjudications,
        canonical_documents=canonical_documents,
    )
    runtime = load_bundle_v3_runtime(root / "runtime")
    _validate_runtime_matches_private(runtime, manifest, cases)
    bundle_id = _validate_checksums(root, schema_version=BUNDLE_V3_SCHEMA_VERSION, key="bundle_id")
    return DatasetBundleV3(
        root=root,
        bundle_id=bundle_id,
        manifest=manifest,
        dataset=dataset,
        cases=cases,
        gold=gold,
        evidence=evidence,
        canonical_documents=canonical_documents,
    )


def load_bundle_v3_runtime(root: Path) -> DatasetBundleV3Runtime:
    root = root.resolve()
    required = ("manifest.json", "questions.jsonl", "checksums.json")
    if any(not (root / item).is_file() for item in required):
        raise BundleV3IntegrityError("runtime view is missing manifest, questions, or checksums")
    runtime_id = _validate_checksums(root, schema_version=BUNDLE_V3_RUNTIME_SCHEMA_VERSION, key="runtime_bundle_id")
    _validate_runtime_layout(root)
    manifest = BundleV3RuntimeManifest.model_validate_json((root / "manifest.json").read_text(encoding="utf-8"))
    questions = tuple(_read_jsonl(root / "questions.jsonl", BundleV3RuntimeQuestion))
    if len(questions) != manifest.case_count or len({item.case_id for item in questions}) != len(questions):
        raise BundleV3IntegrityError("runtime questions must be unique and match the declared Case count")
    for source in manifest.source_documents:
        payload = root / source.runtime_path
        if not payload.is_file() or hashlib.sha256(payload.read_bytes()).hexdigest() != source.source_digest:
            raise BundleV3IntegrityError(f"runtime source checksum mismatch: {source.runtime_path}")
    return DatasetBundleV3Runtime(root=root, runtime_bundle_id=runtime_id, manifest=manifest, questions=questions)


def _validate_checksums(root: Path, *, schema_version: str, key: str) -> str:
    path = root / "checksums.json"
    try:
        checksums = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise BundleV3IntegrityError("invalid checksums.json") from exc
    files = canonical_file_hashes(root)
    digest = digest_file_hashes(files)
    if (
        checksums.get("schema_version") != schema_version
        or checksums.get(key) != digest
        or checksums.get("files") != files
    ):
        raise BundleV3IntegrityError("checksums.json does not match Bundle content")
    return digest


def _validate_runtime_layout(root: Path) -> None:
    allowed = {"manifest.json", "questions.jsonl", "checksums.json"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in allowed or relative.startswith("source/"):
            continue
        raise BundleV3IntegrityError(f"runtime view exposes a private or unknown artifact: {relative}")


def _load_canonical_documents(root: Path, manifest: BundleV3Manifest) -> dict[str, CanonicalDocument]:
    values: dict[str, CanonicalDocument] = {}
    for pin in manifest.canonical_documents:
        paths = [root / pin.manifest_path, root / pin.objects_path, root / pin.relations_path]
        if any(not path.is_file() for path in paths):
            raise BundleV3IntegrityError(f"missing Canonical artifact for {pin.release_id}")
        try:
            document = CanonicalDocument.model_validate(
                {
                    "manifest": json.loads(paths[0].read_text(encoding="utf-8")),
                    "objects": [json.loads(line) for line in paths[1].read_text(encoding="utf-8").splitlines() if line.strip()],
                    "relations": [json.loads(line) for line in paths[2].read_text(encoding="utf-8").splitlines() if line.strip()],
                }
            )
        except Exception as exc:
            raise BundleV3IntegrityError(f"invalid Canonical snapshot for {pin.release_id}: {exc}") from exc
        if (
            document.manifest.canonical_digest != pin.canonical_digest
            or document.manifest.document_id != pin.document_id
            or document.manifest.source_sha256 != pin.source_digest
            or document.manifest.schema_version != pin.schema_version
        ):
            raise BundleV3IntegrityError(f"Canonical pin does not match stored snapshot: {pin.release_id}")
        values[pin.release_id] = document
    return values


def _validate_bundle_v3(
    *,
    root: Path,
    manifest: BundleV3Manifest,
    dataset: BundleV3Dataset,
    cases: tuple[BundleV3CaseRecord, ...],
    gold: tuple[BundleV3GoldRecord, ...],
    evidence: tuple[BundleV3EvidenceRecord, ...],
    releases: tuple[DatasetRelease, ...],
    reviews: tuple[Review, ...],
    approvals: tuple[Approval, ...],
    adjudications: tuple[Adjudication, ...],
    canonical_documents: dict[str, CanonicalDocument],
) -> None:
    if dataset.dataset_id != manifest.dataset_id or dataset.target_release_id != manifest.target_release_id:
        raise BundleV3IntegrityError("private dataset record differs from Bundle manifest")
    if dataset.case_count != len(cases) or dataset.gold_count != len(gold):
        raise BundleV3IntegrityError("private Case/Gold counts differ from dataset declaration")
    release_ids = tuple(item.release_id for item in releases)
    if release_ids != tuple(item.release_id for item in manifest.release_chain):
        raise BundleV3IntegrityError("stored Dataset Release lineage differs from manifest")
    if tuple(item.release_id for item in manifest.release_chain) != dataset.release_chain_ids:
        raise BundleV3IntegrityError("dataset release chain differs from manifest")
    if _digest_value([item.model_dump(mode="json") for item in manifest.release_chain]) != dataset.release_chain_digest:
        raise BundleV3IntegrityError("dataset release-chain digest mismatch")
    for release, pin in zip(releases, manifest.release_chain, strict=True):
        if release.release_id != pin.release_id or release.release_digest != pin.release_digest:
            raise BundleV3IntegrityError("release lineage content differs from pinned identity")
        report_path = root / f"private/lineage/validation/{release.validation_report_digest}.json"
        if not report_path.is_file():
            raise BundleV3IntegrityError(f"missing validation report for {release.release_id}")
        report = ValidationReport.model_validate_json(report_path.read_text(encoding="utf-8"))
        if report.report_digest != release.validation_report_digest or report.has_errors:
            raise BundleV3IntegrityError(f"release validation is missing, altered, or contains ERROR: {release.release_id}")
    expected = _effective_release_selection(releases)
    if set(expected) != {item.case.case_id for item in cases}:
        raise BundleV3IntegrityError("Bundle Case set differs from effective frozen release lineage")
    gold_by_case = {item.gold.case_id: item for item in gold}
    if len(gold_by_case) != len(gold) or set(gold_by_case) != set(expected):
        raise BundleV3IntegrityError("Bundle Gold set must contain one Gold per effective Case")
    case_by_id = {item.case.case_id: item for item in cases}
    for case_id, (release, case_pin, gold_pin) in expected.items():
        case = case_by_id[case_id]
        gold_record = gold_by_case[case_id]
        if case.release_id != release.release_id or gold_record.release_id != release.release_id:
            raise BundleV3IntegrityError(f"{case_id}: Bundle release owner differs from frozen lineage")
        BundleV3Builder._validate_selected_revisions(release, case_pin, gold_pin, case.case, gold_record.gold)
        if case.portfolio.assignment.links.gold_revision_id != gold_record.gold.gold_revision_id:
            raise BundleV3IntegrityError(f"{case_id}: typed Portfolio link differs from Bundle Gold")
        if case.portfolio.assignment.links.release_id != release.release_id:
            raise BundleV3IntegrityError(f"{case_id}: typed Portfolio link differs from Bundle Release")
    _validate_gold_semantics(gold, evidence, canonical_documents)
    _validate_review_lineage(releases, reviews, approvals, adjudications)
    for source in manifest.source_documents:
        source_path = root / "runtime" / source.runtime_path
        if not source_path.is_file() or hashlib.sha256(source_path.read_bytes()).hexdigest() != source.source_digest:
            raise BundleV3IntegrityError(f"source digest mismatch: {source.runtime_path}")


def _validate_gold_semantics(
    gold: tuple[BundleV3GoldRecord, ...],
    evidence: tuple[BundleV3EvidenceRecord, ...],
    canonical_documents: dict[str, CanonicalDocument],
) -> None:
    if len({item.evidence_key for item in evidence}) != len(evidence):
        raise BundleV3IntegrityError("Bundle evidence keys must be unique")
    by_gold: dict[str, list[BundleV3EvidenceRecord]] = {}
    for item in evidence:
        by_gold.setdefault(item.gold_revision_id, []).append(item)
    for record in gold:
        item = record.gold
        canonical = canonical_documents.get(record.release_id)
        if canonical is None:
            raise BundleV3IntegrityError(f"{item.gold_revision_id}: missing owning Canonical snapshot")
        objects = {value.object_id: value for value in canonical.objects}
        rows = by_gold.get(item.gold_revision_id, [])
        payload_rows = {row.evidence_id: row for row in rows if row.origin == "gold_payload"}
        if set(payload_rows) != {value.evidence_id for value in item.payload.evidence}:
            raise BundleV3IntegrityError(f"{item.gold_revision_id}: Bundle evidence does not exactly preserve Gold roles")
        for value in item.payload.evidence:
            row = payload_rows[value.evidence_id]
            if row.canonical != objects.get(value.canonical_object_id):
                raise BundleV3IntegrityError(f"{item.gold_revision_id}: evidence locator/provenance does not match Canonical snapshot")
        for scope in item.payload.negative_scope_object_ids:
            if not any(row.role == EvidenceRole.NEGATIVE_SCOPE and row.canonical.object_id == scope for row in rows):
                raise BundleV3IntegrityError(f"{item.gold_revision_id}: bounded negative scope is not represented as evidence")
        _validate_dependency_graph(item)
        # GoldPayload's strict Pydantic validation retains AND/OR MSES.  This
        # additional assertion catches a hand-edited record that somehow
        # omitted a required evidence witness after parsing.
        evidence_ids = {value.evidence_id for value in item.payload.evidence}
        for path in item.payload.mses_paths:
            for clause in path.clauses:
                if not set(clause.alternatives).issubset(evidence_ids):
                    raise BundleV3IntegrityError(f"{item.gold_revision_id}: MSES alternative is not present in evidence")


def _validate_dependency_graph(gold: GoldRevision) -> None:
    dependencies = {item.dependency_id: item for item in gold.payload.dependencies}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identifier: str) -> None:
        if identifier in visited:
            return
        if identifier in visiting:
            raise BundleV3IntegrityError(f"{gold.gold_revision_id}: dependency graph contains a cycle")
        visiting.add(identifier)
        for parent in dependencies[identifier].depends_on:
            if parent not in dependencies:
                raise BundleV3IntegrityError(f"{gold.gold_revision_id}: dependency graph references unknown node")
            visit(parent)
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in dependencies:
        visit(identifier)


def _validate_review_lineage(
    releases: tuple[DatasetRelease, ...],
    reviews: tuple[Review, ...],
    approvals: tuple[Approval, ...],
    adjudications: tuple[Adjudication, ...],
) -> None:
    review_ids = {item.review_id for item in reviews}
    approval_ids = {item.approval_id for item in approvals}
    expected_reviews = {item.review_id for release in releases for item in release.reviews}
    expected_approvals = {item.approval_id for release in releases for item in release.approvals}
    if review_ids != expected_reviews or approval_ids != expected_approvals:
        raise BundleV3IntegrityError("review/approval lineage differs from frozen Release pins")
    if any(not set(item.review_ids).intersection(review_ids) for item in adjudications):
        raise BundleV3IntegrityError("adjudication does not relate to packaged review lineage")


def _validate_runtime_matches_private(
    runtime: DatasetBundleV3Runtime,
    manifest: BundleV3Manifest,
    cases: tuple[BundleV3CaseRecord, ...],
) -> None:
    if runtime.manifest.target_release_id != manifest.target_release_id or runtime.manifest.dataset_id != manifest.dataset_id:
        raise BundleV3IntegrityError("runtime manifest differs from private Bundle identity")
    expected = {
        item.case.case_id: (item.case.case_revision_id, item.case.draft.question, item.case.draft.language, item.portfolio.slot)
        for item in cases
    }
    actual = {
        item.case_id: (item.case_revision_id, item.question, item.language, item.portfolio_slot)
        for item in runtime.questions
    }
    if actual != expected:
        raise BundleV3IntegrityError("runtime questions differ from private frozen Case records")
