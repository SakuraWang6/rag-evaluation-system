"""Append-only Authoring Ledger and independent Gold lifecycle.

This module is the formal Authoring domain contract.  It deliberately stores
only references to Canonical Data Model objects; it does not introduce a
second representation of document structure.  The older ``QuestionCandidate``
files remain a Bundle 2.0 compatibility projection, while this ledger owns
revision history, review, adjudication, approval, and rich Gold semantics.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.authoring.models import (
    AnswerEvidenceCandidate,
    AuthoringDataset,
    CandidateState,
    DiscoveryMethod,
    QuestionCandidate,
)
from rag_eval.authoring.storage import AuthoringWorkspaceStore
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.runs import safe_id


LEDGER_SCHEMA_VERSION = "authoring-ledger/1.0"


class LedgerError(ValueError):
    """A formal Authoring state or immutability constraint was violated."""


class LedgerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LifecycleState(StrEnum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    FROZEN = "frozen"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"
    SUPERSEDED = "superseded"


class OriginKind(StrEnum):
    HUMAN = "human"
    TEMPLATE_ASSISTED = "template-assisted"
    SYNTHETIC = "synthetic"
    SEMI_SYNTHETIC = "semi-synthetic"
    IMPORTED = "imported"
    ADJUDICATED = "adjudicated"


class TrustLevel(StrEnum):
    HUMAN_ASSERTED = "human_asserted"
    REVIEW_REQUIRED = "review_required"
    IMPORTED_UNVERIFIED = "imported_unverified"
    SYNTHETIC_UNVERIFIED = "synthetic_unverified"
    ADJUDICATED = "adjudicated"
    APPROVED = "approved"


class EvidenceRole(StrEnum):
    REQUIRED = "required"
    SUPPORTING = "supporting"
    CONFLICTING = "conflicting"
    NEAR_MISS = "near_miss"
    NEGATIVE_SCOPE = "negative_scope"


class ActorRole(StrEnum):
    AUTHOR = "author"
    REVIEWER = "reviewer"
    ADJUDICATOR = "adjudicator"
    SYSTEM = "system"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    DISAGREE = "disagree"


class TargetKind(StrEnum):
    CASE = "case"
    GOLD = "gold"


def _json_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _revision_id(kind: str, entity_id: str, revision: int) -> str:
    return f"{kind}-revision-{safe_id(entity_id)}-{revision:06d}"


class AuthoringOrigin(LedgerModel):
    kind: OriginKind
    trust_level: TrustLevel
    generator_identity: str | None = None
    generator_version: str | None = None
    configuration_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    seed: int | None = None
    source_world: str | None = None
    source_document_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _synthetic_requires_unverified_trust(self) -> "AuthoringOrigin":
        if self.kind in {OriginKind.SYNTHETIC, OriginKind.SEMI_SYNTHETIC} and self.trust_level not in {
            TrustLevel.SYNTHETIC_UNVERIFIED,
            TrustLevel.REVIEW_REQUIRED,
        }:
            raise ValueError("synthetic origin must begin unverified or review-required")
        return self


class DatasetLedgerRecord(LedgerModel):
    schema_version: Literal[LEDGER_SCHEMA_VERSION] = LEDGER_SCHEMA_VERSION
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    created_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class DocumentRevision(LedgerModel):
    schema_version: Literal[LEDGER_SCHEMA_VERSION] = LEDGER_SCHEMA_VERSION
    document_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    revision: int = Field(ge=1)
    parent_revision_id: str | None = None
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_contract_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    parser_identity: str = Field(min_length=1)
    canonicalizer_identity: str = Field(min_length=1)
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor: str = Field(min_length=1)
    created_at: datetime
    reason: str = Field(min_length=1)


class CaseDraft(LedgerModel):
    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    target_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    question: str = Field(min_length=1)
    language: str = Field(min_length=1)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_contract_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    canonical_compatibility_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_object_ids: tuple[str, ...] = Field(min_length=1)
    origin: AuthoringOrigin
    legacy_candidate_id: str | None = None


class CaseRevision(LedgerModel):
    schema_version: Literal[LEDGER_SCHEMA_VERSION] = LEDGER_SCHEMA_VERSION
    case_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    revision: int = Field(ge=1)
    parent_revision_id: str | None = None
    lifecycle: LifecycleState
    draft: CaseDraft
    actor: str = Field(min_length=1)
    created_at: datetime
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def _matching_case_id(self) -> "CaseRevision":
        if self.case_id != self.draft.case_id:
            raise ValueError("case revision and draft case ID differ")
        return self


class GoldEvidence(LedgerModel):
    evidence_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    canonical_object_id: str = Field(min_length=1)
    role: EvidenceRole
    rationale: str | None = None


class MsesClause(LedgerModel):
    """An OR clause: any listed required evidence can satisfy this clause."""

    clause_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    alternatives: tuple[str, ...] = Field(min_length=1)


class MsesPath(LedgerModel):
    """An AND path: all clauses are required.  Paths are alternatives (OR)."""

    path_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    clauses: tuple[MsesClause, ...] = Field(min_length=1)


class EvidenceDependency(LedgerModel):
    dependency_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    depends_on: tuple[str, ...] = ()
    description: str = Field(min_length=1)


class GoldAnswer(LedgerModel):
    kind: Literal["text", "numeric", "formula", "set", "abstain"]
    canonical: str | tuple[str, ...] | None = None
    accepted_values: tuple[str, ...] = ()
    locale: str | None = None
    unit: str | None = None
    tolerance: str | None = None

    @model_validator(mode="after")
    def _answer_required_except_abstain(self) -> "GoldAnswer":
        if self.kind == "abstain":
            if self.canonical not in (None, "", ()):
                raise ValueError("abstention cannot contain a canonical answer")
        elif self.canonical in (None, "", ()):
            raise ValueError("non-abstain Gold needs a canonical answer")
        return self


class GoldPayload(LedgerModel):
    answer: GoldAnswer
    evidence: tuple[GoldEvidence, ...] = ()
    mses_paths: tuple[MsesPath, ...] = ()
    dependencies: tuple[EvidenceDependency, ...] = ()
    negative_scope_object_ids: tuple[str, ...] = ()
    negative_rationale: str | None = None

    @model_validator(mode="after")
    def _validate_evidence_semantics(self) -> "GoldPayload":
        ids = [item.evidence_id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("Gold evidence IDs must be unique")
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        if self.answer.kind == "abstain":
            if not self.negative_scope_object_ids:
                raise ValueError("unanswerable Gold requires a scoped negative witness")
        elif not self.mses_paths:
            raise ValueError("answerable Gold requires at least one MSES path")
        for path in self.mses_paths:
            clause_ids = [clause.clause_id for clause in path.clauses]
            if len(clause_ids) != len(set(clause_ids)):
                raise ValueError("MSES clause IDs must be unique within a path")
            for clause in path.clauses:
                if len(set(clause.alternatives)) != len(clause.alternatives):
                    raise ValueError("MSES alternatives must be unique")
                for evidence_id in clause.alternatives:
                    evidence = evidence_by_id.get(evidence_id)
                    if evidence is None:
                        raise ValueError("MSES cites an unknown evidence ID")
                    if evidence.role != EvidenceRole.REQUIRED:
                        raise ValueError("MSES can contain required evidence only")
        dependency_ids = {item.dependency_id for item in self.dependencies}
        for dependency in self.dependencies:
            if dependency.dependency_id in dependency.depends_on:
                raise ValueError("an evidence dependency cannot depend on itself")
            unknown = set(dependency.depends_on).difference(dependency_ids)
            if unknown:
                raise ValueError("multi-hop dependency cites an unknown dependency")
        return self


class GoldRevision(LedgerModel):
    schema_version: Literal[LEDGER_SCHEMA_VERSION] = LEDGER_SCHEMA_VERSION
    gold_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    gold_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    revision: int = Field(ge=1)
    parent_revision_id: str | None = None
    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    case_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    lifecycle: LifecycleState
    payload: GoldPayload
    origin: AuthoringOrigin
    actor: str = Field(min_length=1)
    created_at: datetime
    reason: str = Field(min_length=1)


class Review(LedgerModel):
    schema_version: Literal[LEDGER_SCHEMA_VERSION] = LEDGER_SCHEMA_VERSION
    review_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    target_kind: TargetKind
    reviewed_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    reviewer_identity: str = Field(min_length=1)
    reviewer_role: Literal[ActorRole.REVIEWER] = ActorRole.REVIEWER
    decision: ReviewDecision
    checklist: dict[str, bool] = Field(default_factory=dict)
    comments: str = ""
    created_at: datetime


class Adjudication(LedgerModel):
    schema_version: Literal[LEDGER_SCHEMA_VERSION] = LEDGER_SCHEMA_VERSION
    adjudication_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    target_kind: TargetKind
    target_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    review_ids: tuple[str, ...] = Field(min_length=1)
    adjudicator_identity: str = Field(min_length=1)
    adjudicator_role: Literal[ActorRole.ADJUDICATOR] = ActorRole.ADJUDICATOR
    decision: ReviewDecision
    comments: str = Field(min_length=1)
    created_at: datetime


class Approval(LedgerModel):
    schema_version: Literal[LEDGER_SCHEMA_VERSION] = LEDGER_SCHEMA_VERSION
    approval_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    target_kind: TargetKind
    approved_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    approver_identity: str = Field(min_length=1)
    approver_role: Literal[ActorRole.REVIEWER, ActorRole.ADJUDICATOR]
    reason: str = Field(min_length=1)
    created_at: datetime


class Invalidation(LedgerModel):
    schema_version: Literal[LEDGER_SCHEMA_VERSION] = LEDGER_SCHEMA_VERSION
    invalidation_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    target_kind: TargetKind
    invalidated_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    resulting_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    created_at: datetime


class Supersession(LedgerModel):
    schema_version: Literal[LEDGER_SCHEMA_VERSION] = LEDGER_SCHEMA_VERSION
    supersession_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    target_kind: TargetKind
    superseded_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    successor_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    created_at: datetime


class BundleV2Projection(LedgerModel):
    """An explicit, non-mutating assessment of the legacy Bundle v2 view."""

    runnable: bool
    lossy: bool
    reasons: tuple[str, ...] = ()


class AuthoringRelease(LedgerModel):
    """Historical Authoring snapshot; this is not a Bundle v3 release contract."""

    schema_version: Literal[LEDGER_SCHEMA_VERSION] = LEDGER_SCHEMA_VERSION
    ledger_release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    case_revision_ids: tuple[str, ...] = Field(min_length=1)
    gold_revision_ids: tuple[str, ...] = Field(min_length=1)
    bundle_v2_projection: tuple[BundleV2Projection, ...]
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    created_at: datetime


class LedgerEvent(LedgerModel):
    schema_version: Literal[LEDGER_SCHEMA_VERSION] = LEDGER_SCHEMA_VERSION
    event_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    event_type: str = Field(min_length=1)
    target_kind: TargetKind | Literal["dataset", "document", "release"]
    entity_id: str = Field(min_length=1)
    revision_id: str | None = None
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    created_at: datetime


class AuthoringLedger:
    """Filesystem-backed append-only ledger for one Authoring workspace."""

    def __init__(self, store: AuthoringWorkspaceStore) -> None:
        self.store = store

    def ensure_dataset(self, dataset: AuthoringDataset, *, actor: str = "authoring-system") -> None:
        root = self._root(dataset.authoring_dataset_id)
        dataset_path = root / "dataset.json"
        if not dataset_path.exists():
            value = DatasetLedgerRecord(
                dataset_id=dataset.authoring_dataset_id,
                source_digest=dataset.source.sha256,
                created_at=_now(),
                created_by=actor,
                reason="initialize Authoring Ledger for private DOCX dataset",
            )
            self._append(dataset_path, value)
            self._event("dataset_initialized", "dataset", dataset.authoring_dataset_id, actor, value.reason)
        documents = self.document_history(dataset.authoring_dataset_id)
        current = documents[-1] if documents else None
        if current and current.source_digest == dataset.source.sha256 and current.canonical_contract_digest == dataset.canonical_contract_digest:
            return
        revision = len(documents) + 1
        value = DocumentRevision(
            document_revision_id=_revision_id("document", dataset.authoring_dataset_id, revision),
            dataset_id=dataset.authoring_dataset_id,
            revision=revision,
            parent_revision_id=current.document_revision_id if current else None,
            source_digest=dataset.source.sha256,
            canonical_contract_digest=dataset.canonical_contract_digest,
            parser_identity=dataset.source.parser_identity,
            canonicalizer_identity=dataset.source.canonicalizer_identity,
            configuration_digest=dataset.source.configuration_digest,
            actor=actor,
            created_at=_now(),
            reason="record analyzed document revision and canonical contract digest",
        )
        self._append(self._document_path(dataset.authoring_dataset_id, revision), value)
        self._event("document_revision_created", "document", dataset.authoring_dataset_id, actor, value.reason, value.document_revision_id)

    def create_case(
        self,
        dataset: AuthoringDataset,
        *,
        draft: CaseDraft,
        actor: str,
        reason: str,
    ) -> CaseRevision:
        self.ensure_dataset(dataset)
        if self.case_history(dataset.authoring_dataset_id, draft.case_id):
            raise LedgerError("case already exists; create a new revision instead")
        result = CaseRevision(
            case_revision_id=_revision_id("case", draft.case_id, 1),
            case_id=draft.case_id,
            revision=1,
            lifecycle=LifecycleState.DRAFT,
            draft=draft,
            actor=actor,
            created_at=_now(),
            reason=reason,
        )
        self._append(self._case_path(dataset.authoring_dataset_id, draft.case_id, 1), result)
        self._event("case_created", TargetKind.CASE, draft.case_id, actor, reason, result.case_revision_id)
        return result

    def revise_case(
        self,
        dataset: AuthoringDataset,
        *,
        case_id: str,
        draft: CaseDraft,
        actor: str,
        reason: str,
        lifecycle: LifecycleState = LifecycleState.DRAFT,
    ) -> CaseRevision:
        current = self.current_case(dataset.authoring_dataset_id, case_id)
        if current.lifecycle in {LifecycleState.FROZEN, LifecycleState.INVALIDATED}:
            raise LedgerError("frozen or invalidated case must be superseded, not revised")
        return self._append_case_revision(dataset, current, draft=draft, actor=actor, reason=reason, lifecycle=lifecycle)

    def propose_case(self, dataset: AuthoringDataset, *, case_id: str, actor: str, reason: str) -> CaseRevision:
        current = self.current_case(dataset.authoring_dataset_id, case_id)
        if current.lifecycle not in {LifecycleState.DRAFT, LifecycleState.REJECTED}:
            raise LedgerError("only a draft or rejected case can be proposed")
        return self._append_case_revision(dataset, current, draft=current.draft, actor=actor, reason=reason, lifecycle=LifecycleState.PROPOSED)

    def create_gold(
        self,
        dataset: AuthoringDataset,
        *,
        gold_id: str,
        case_revision: CaseRevision,
        payload: GoldPayload,
        origin: AuthoringOrigin,
        actor: str,
        reason: str,
    ) -> GoldRevision:
        if self.gold_history(dataset.authoring_dataset_id, gold_id):
            raise LedgerError("Gold already exists; create a new revision instead")
        result = GoldRevision(
            gold_revision_id=_revision_id("gold", gold_id, 1),
            gold_id=gold_id,
            revision=1,
            case_id=case_revision.case_id,
            case_revision_id=case_revision.case_revision_id,
            lifecycle=LifecycleState.DRAFT,
            payload=payload,
            origin=origin,
            actor=actor,
            created_at=_now(),
            reason=reason,
        )
        self._append(self._gold_path(dataset.authoring_dataset_id, gold_id, 1), result)
        self._event("gold_created", TargetKind.GOLD, gold_id, actor, reason, result.gold_revision_id)
        return result

    def revise_gold(
        self,
        dataset: AuthoringDataset,
        *,
        gold_id: str,
        payload: GoldPayload,
        actor: str,
        reason: str,
        case_revision: CaseRevision | None = None,
    ) -> GoldRevision:
        current = self.current_gold(dataset.authoring_dataset_id, gold_id)
        if current.lifecycle in {LifecycleState.FROZEN, LifecycleState.INVALIDATED}:
            raise LedgerError("frozen or invalidated Gold must be superseded, not revised")
        return self._append_gold_revision(
            dataset,
            current,
            payload=payload,
            actor=actor,
            reason=reason,
            case_revision=case_revision,
            lifecycle=LifecycleState.DRAFT,
        )

    def propose_gold(self, dataset: AuthoringDataset, *, gold_id: str, actor: str, reason: str) -> GoldRevision:
        current = self.current_gold(dataset.authoring_dataset_id, gold_id)
        if current.lifecycle not in {LifecycleState.DRAFT, LifecycleState.REJECTED}:
            raise LedgerError("only a draft or rejected Gold can be proposed")
        return self._append_gold_revision(dataset, current, payload=current.payload, actor=actor, reason=reason, lifecycle=LifecycleState.PROPOSED)

    def record_review(
        self,
        dataset_id: str,
        *,
        target_kind: TargetKind,
        reviewed_revision_id: str,
        reviewer: str,
        decision: ReviewDecision,
        checklist: dict[str, bool] | None = None,
        comments: str = "",
    ) -> Review:
        target = self._revision_by_id(dataset_id, target_kind, reviewed_revision_id)
        if target.lifecycle not in {LifecycleState.PROPOSED, LifecycleState.REVIEWED}:
            raise LedgerError("only proposed or reviewed revisions can be reviewed")
        if reviewer == target.actor:
            raise LedgerError("an author cannot review their own revision")
        result = Review(
            review_id=f"review-{uuid.uuid4().hex}",
            target_kind=target_kind,
            reviewed_revision_id=reviewed_revision_id,
            reviewer_identity=reviewer,
            decision=decision,
            checklist=checklist or {},
            comments=comments,
            created_at=_now(),
        )
        self._append(self._root(dataset_id) / "reviews" / f"{result.review_id}.json", result)
        self._event("review_recorded", target_kind, self._entity_id(target), reviewer, decision.value, reviewed_revision_id)
        return result

    def mark_reviewed(
        self,
        dataset: AuthoringDataset,
        *,
        target_kind: TargetKind,
        revision_id: str,
        actor: str,
        reason: str,
    ) -> CaseRevision | GoldRevision:
        target = self._revision_by_id(dataset.authoring_dataset_id, target_kind, revision_id)
        if target.lifecycle != LifecycleState.PROPOSED:
            raise LedgerError("only proposed revisions can become reviewed")
        approving_reviews = [
            review for review in self.reviews_for(dataset.authoring_dataset_id, revision_id)
            if review.decision == ReviewDecision.APPROVE
        ]
        if not approving_reviews:
            raise LedgerError("reviewed state requires an approving review record")
        if target_kind == TargetKind.CASE:
            return self._append_case_revision(dataset, target, draft=target.draft, actor=actor, reason=reason, lifecycle=LifecycleState.REVIEWED)
        return self._append_gold_revision(dataset, target, payload=target.payload, actor=actor, reason=reason, lifecycle=LifecycleState.REVIEWED)

    def approve(
        self,
        dataset: AuthoringDataset,
        *,
        target_kind: TargetKind,
        revision_id: str,
        approver: str,
        role: ActorRole = ActorRole.REVIEWER,
        reason: str,
    ) -> CaseRevision | GoldRevision:
        if role not in {ActorRole.REVIEWER, ActorRole.ADJUDICATOR}:
            raise LedgerError("only reviewer or adjudicator may approve")
        target = self._revision_by_id(dataset.authoring_dataset_id, target_kind, revision_id)
        if target.lifecycle != LifecycleState.REVIEWED:
            raise LedgerError("only a reviewed revision can be approved")
        if approver == target.actor:
            raise LedgerError("an author cannot approve their own revision")
        approval = Approval(
            approval_id=f"approval-{uuid.uuid4().hex}",
            target_kind=target_kind,
            approved_revision_id=revision_id,
            approver_identity=approver,
            approver_role=role,
            reason=reason,
            created_at=_now(),
        )
        self._append(self._root(dataset.authoring_dataset_id) / "approvals" / f"{approval.approval_id}.json", approval)
        if target_kind == TargetKind.CASE:
            result: CaseRevision | GoldRevision = self._append_case_revision(dataset, target, draft=target.draft, actor=target.actor, reason=reason, lifecycle=LifecycleState.APPROVED)
        else:
            result = self._append_gold_revision(dataset, target, payload=target.payload, actor=target.actor, reason=reason, lifecycle=LifecycleState.APPROVED)
        self._event("approved", target_kind, self._entity_id(target), approver, reason, result.case_revision_id if isinstance(result, CaseRevision) else result.gold_revision_id)
        return result

    def reject(
        self,
        dataset: AuthoringDataset,
        *,
        target_kind: TargetKind,
        revision_id: str,
        reviewer: str,
        reason: str,
    ) -> CaseRevision | GoldRevision:
        target = self._revision_by_id(dataset.authoring_dataset_id, target_kind, revision_id)
        if target.lifecycle not in {LifecycleState.PROPOSED, LifecycleState.REVIEWED}:
            raise LedgerError("only proposed or reviewed revisions can be rejected")
        review = self.record_review(dataset.authoring_dataset_id, target_kind=target_kind, reviewed_revision_id=revision_id, reviewer=reviewer, decision=ReviewDecision.REJECT, comments=reason)
        if target_kind == TargetKind.CASE:
            return self._append_case_revision(dataset, target, draft=target.draft, actor=review.reviewer_identity, reason=reason, lifecycle=LifecycleState.REJECTED)
        return self._append_gold_revision(dataset, target, payload=target.payload, actor=review.reviewer_identity, reason=reason, lifecycle=LifecycleState.REJECTED)

    def adjudicate(
        self,
        dataset: AuthoringDataset,
        *,
        target_kind: TargetKind,
        revision_id: str,
        review_ids: tuple[str, ...],
        adjudicator: str,
        decision: ReviewDecision,
        comments: str,
    ) -> Adjudication:
        target = self._revision_by_id(dataset.authoring_dataset_id, target_kind, revision_id)
        if target.lifecycle not in {LifecycleState.PROPOSED, LifecycleState.REVIEWED}:
            raise LedgerError("only proposed or reviewed revisions can be adjudicated")
        reviews = {item.review_id: item for item in self.list_reviews(dataset.authoring_dataset_id)}
        if not review_ids or any(item not in reviews for item in review_ids):
            raise LedgerError("adjudication must cite existing review records")
        cited = [reviews[item] for item in review_ids]
        if any(item.target_kind != target_kind or item.reviewed_revision_id != revision_id for item in cited):
            raise LedgerError("adjudication reviews must address the same revision")
        if len({item.decision for item in cited}) < 2:
            raise LedgerError("adjudication requires reviewer disagreement")
        if adjudicator == target.actor or adjudicator in {item.reviewer_identity for item in cited}:
            raise LedgerError("adjudicator must be independent of author and reviewers")
        result = Adjudication(
            adjudication_id=f"adjudication-{uuid.uuid4().hex}",
            target_kind=target_kind,
            target_revision_id=revision_id,
            review_ids=review_ids,
            adjudicator_identity=adjudicator,
            decision=decision,
            comments=comments,
            created_at=_now(),
        )
        self._append(self._root(dataset.authoring_dataset_id) / "adjudications" / f"{result.adjudication_id}.json", result)
        self._event("adjudicated", target_kind, self._entity_id(target), adjudicator, comments, revision_id)
        return result

    def approve_adjudication(
        self,
        dataset: AuthoringDataset,
        *,
        target_kind: TargetKind,
        revision_id: str,
        adjudication: Adjudication,
    ) -> CaseRevision | GoldRevision:
        if adjudication.target_kind != target_kind or adjudication.target_revision_id != revision_id or adjudication.decision != ReviewDecision.APPROVE:
            raise LedgerError("adjudication does not approve this revision")
        target = self._revision_by_id(dataset.authoring_dataset_id, target_kind, revision_id)
        if target.lifecycle == LifecycleState.PROPOSED:
            # Adjudication is the independent review authority.
            if target_kind == TargetKind.CASE:
                target = self._append_case_revision(dataset, target, draft=target.draft, actor=target.actor, reason="reviewer disagreement resolved by adjudication", lifecycle=LifecycleState.REVIEWED)
            else:
                target = self._append_gold_revision(dataset, target, payload=target.payload, actor=target.actor, reason="reviewer disagreement resolved by adjudication", lifecycle=LifecycleState.REVIEWED)
        return self.approve(dataset, target_kind=target_kind, revision_id=target.case_revision_id if isinstance(target, CaseRevision) else target.gold_revision_id, approver=adjudication.adjudicator_identity, role=ActorRole.ADJUDICATOR, reason="approved by adjudication")

    def invalidate(
        self,
        dataset: AuthoringDataset,
        *,
        target_kind: TargetKind,
        revision_id: str,
        actor: str,
        reason: str,
    ) -> CaseRevision | GoldRevision:
        target = self._revision_by_id(dataset.authoring_dataset_id, target_kind, revision_id)
        if target.lifecycle not in {LifecycleState.APPROVED, LifecycleState.FROZEN, LifecycleState.REVIEWED}:
            raise LedgerError("only reviewed, approved, or frozen revisions can be invalidated")
        if target_kind == TargetKind.CASE:
            result: CaseRevision | GoldRevision = self._append_case_revision(dataset, target, draft=target.draft, actor=actor, reason=reason, lifecycle=LifecycleState.INVALIDATED)
            resulting_id = result.case_revision_id
        else:
            result = self._append_gold_revision(dataset, target, payload=target.payload, actor=actor, reason=reason, lifecycle=LifecycleState.INVALIDATED)
            resulting_id = result.gold_revision_id
        invalidation = Invalidation(
            invalidation_id=f"invalidation-{uuid.uuid4().hex}",
            target_kind=target_kind,
            invalidated_revision_id=revision_id,
            resulting_revision_id=resulting_id,
            actor=actor,
            reason=reason,
            created_at=_now(),
        )
        self._append(self._root(dataset.authoring_dataset_id) / "invalidations" / f"{invalidation.invalidation_id}.json", invalidation)
        self._event("invalidated", target_kind, self._entity_id(target), actor, reason, resulting_id)
        return result

    def supersede_gold(
        self,
        dataset: AuthoringDataset,
        *,
        gold_id: str,
        successor_gold_id: str,
        case_revision: CaseRevision,
        payload: GoldPayload,
        origin: AuthoringOrigin,
        actor: str,
        reason: str,
    ) -> GoldRevision:
        current = self.current_gold(dataset.authoring_dataset_id, gold_id)
        if current.lifecycle not in {LifecycleState.APPROVED, LifecycleState.FROZEN, LifecycleState.INVALIDATED}:
            raise LedgerError("only approved, frozen, or invalidated Gold can be superseded")
        successor = self.create_gold(dataset, gold_id=successor_gold_id, case_revision=case_revision, payload=payload, origin=origin, actor=actor, reason=reason)
        record = Supersession(
            supersession_id=f"supersession-{uuid.uuid4().hex}",
            target_kind=TargetKind.GOLD,
            superseded_revision_id=current.gold_revision_id,
            successor_revision_id=successor.gold_revision_id,
            actor=actor,
            reason=reason,
            created_at=_now(),
        )
        self._append(self._root(dataset.authoring_dataset_id) / "supersessions" / f"{record.supersession_id}.json", record)
        self._event("superseded", TargetKind.GOLD, gold_id, actor, reason, successor.gold_revision_id)
        return successor

    def freeze_release(
        self,
        dataset: AuthoringDataset,
        *,
        release_id: str,
        case_ids: tuple[str, ...],
        actor: str,
        reason: str,
    ) -> AuthoringRelease:
        """Pin approved historical revisions without changing Bundle bytes."""

        root = self._root(dataset.authoring_dataset_id)
        path = root / "releases" / f"{safe_id(release_id)}.json"
        if path.exists():
            return AuthoringRelease.model_validate_json(path.read_text(encoding="utf-8"))
        frozen_cases: list[CaseRevision] = []
        frozen_gold: list[GoldRevision] = []
        projections: list[BundleV2Projection] = []
        for case_id in sorted(case_ids):
            case = self.current_case(dataset.authoring_dataset_id, case_id)
            if case.lifecycle not in {LifecycleState.APPROVED, LifecycleState.FROZEN}:
                raise LedgerError("only approved or already frozen cases can enter a frozen authoring release")
            gold = self.current_gold_for_case(dataset.authoring_dataset_id, case_id)
            if gold.lifecycle not in {LifecycleState.APPROVED, LifecycleState.FROZEN}:
                raise LedgerError("only approved or already frozen Gold can enter a frozen authoring release")
            frozen_case = (
                case
                if case.lifecycle == LifecycleState.FROZEN
                # Freezing records the release action, not a new Case author.
                # Keeping the author of the approved revision preserves the
                # independent-review lineage used by formal validation.
                else self._append_case_revision(dataset, case, draft=case.draft, actor=case.actor, reason=reason, lifecycle=LifecycleState.FROZEN)
            )
            frozen_case_id = frozen_case.case_revision_id
            frozen_gold_item = (
                gold
                if gold.lifecycle == LifecycleState.FROZEN
                # As with Cases, the release manager is captured by the
                # AuthoringRelease/event, while the Gold revision retains its
                # original author for review and approval provenance.
                else self._append_gold_revision(dataset, gold, payload=gold.payload, actor=gold.actor, reason=reason, case_revision=frozen_case, lifecycle=LifecycleState.FROZEN)
            )
            frozen_cases.append(frozen_case)
            frozen_gold.append(frozen_gold_item)
            projections.append(self.assess_bundle_v2(frozen_gold_item))
            if frozen_case is not case:
                self._event("frozen", TargetKind.CASE, case_id, actor, reason, frozen_case_id)
            if frozen_gold_item is not gold:
                self._event("frozen", TargetKind.GOLD, gold.gold_id, actor, reason, frozen_gold_item.gold_revision_id)
        result = AuthoringRelease(
            ledger_release_id=f"ledger-{safe_id(release_id)}",
            dataset_id=dataset.authoring_dataset_id,
            case_revision_ids=tuple(item.case_revision_id for item in frozen_cases),
            gold_revision_ids=tuple(item.gold_revision_id for item in frozen_gold),
            bundle_v2_projection=tuple(projections),
            actor=actor,
            reason=reason,
            created_at=_now(),
        )
        self._append(path, result)
        self._event("release_frozen", "release", result.ledger_release_id, actor, reason)
        return result

    @staticmethod
    def assess_bundle_v2(gold: GoldRevision) -> BundleV2Projection:
        """Describe exactly where legacy Bundle 2.0 loses formal Gold semantics."""

        reasons: list[str] = []
        if len(gold.payload.mses_paths) > 1:
            reasons.append("alternative_mses_paths_are_not_representable")
        if any(len(clause.alternatives) > 1 for path in gold.payload.mses_paths for clause in path.clauses):
            reasons.append("or_alternatives_within_mses_clause_are_not_representable")
        if gold.payload.dependencies:
            reasons.append("multi_hop_dependencies_are_not_representable")
        roles = {item.role for item in gold.payload.evidence}
        if roles.intersection({EvidenceRole.SUPPORTING, EvidenceRole.CONFLICTING, EvidenceRole.NEAR_MISS}):
            reasons.append("non_required_evidence_roles_are_not_representable")
        if len(gold.payload.negative_scope_object_ids) > 1:
            reasons.append("multi_object_negative_scope_is_not_representable")
        runnable = not reasons
        return BundleV2Projection(runnable=runnable, lossy=bool(reasons), reasons=tuple(sorted(reasons)))

    def case_history(self, dataset_id: str, case_id: str) -> list[CaseRevision]:
        root = self._root(dataset_id) / "cases" / safe_id(case_id)
        return [CaseRevision.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(root.glob("*.json"))]

    def gold_history(self, dataset_id: str, gold_id: str) -> list[GoldRevision]:
        root = self._root(dataset_id) / "gold" / safe_id(gold_id)
        return [GoldRevision.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(root.glob("*.json"))]

    def document_history(self, dataset_id: str) -> list[DocumentRevision]:
        root = self._root(dataset_id) / "documents"
        return [DocumentRevision.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(root.glob("*.json"))]

    def get_document_revision(self, dataset_id: str, revision_id: str) -> DocumentRevision:
        for item in self.document_history(dataset_id):
            if item.document_revision_id == revision_id:
                return item
        raise LedgerError("unknown DocumentRevision")

    def current_case(self, dataset_id: str, case_id: str) -> CaseRevision:
        history = self.case_history(dataset_id, case_id)
        if not history:
            raise LedgerError("unknown case")
        return history[-1]

    def current_gold(self, dataset_id: str, gold_id: str) -> GoldRevision:
        history = self.gold_history(dataset_id, gold_id)
        if not history:
            raise LedgerError("unknown Gold")
        return history[-1]

    def current_gold_for_case(self, dataset_id: str, case_id: str) -> GoldRevision:
        candidates: list[GoldRevision] = []
        root = self._root(dataset_id) / "gold"
        for entity in sorted(root.iterdir()):
            if entity.is_dir():
                current = self.gold_history(dataset_id, entity.name)[-1]
                if current.case_id == case_id:
                    candidates.append(current)
        superseded = {
            item.superseded_revision_id
            for item in self.list_supersessions(dataset_id)
            if item.target_kind == TargetKind.GOLD
        }
        candidates = [item for item in candidates if item.gold_revision_id not in superseded]
        if len(candidates) != 1:
            raise LedgerError("case must have exactly one current Gold revision")
        return candidates[0]

    def get_case_revision(self, dataset_id: str, revision_id: str) -> CaseRevision:
        """Load one immutable Case revision by its formal revision ID."""

        value = self._revision_by_id(dataset_id, TargetKind.CASE, revision_id)
        assert isinstance(value, CaseRevision)
        return value

    def get_gold_revision(self, dataset_id: str, revision_id: str) -> GoldRevision:
        """Load one immutable Gold revision by its formal revision ID."""

        value = self._revision_by_id(dataset_id, TargetKind.GOLD, revision_id)
        assert isinstance(value, GoldRevision)
        return value

    def get_authoring_release(self, dataset_id: str, ledger_release_id: str) -> AuthoringRelease:
        """Read the Bundle-compatibility freeze marker by stable ledger release ID."""

        name = ledger_release_id.removeprefix("ledger-")
        path = self._root(dataset_id) / "releases" / f"{safe_id(name)}.json"
        if not path.is_file():
            raise LedgerError("unknown Authoring Ledger release")
        return AuthoringRelease.model_validate_json(path.read_text(encoding="utf-8"))

    def list_reviews(self, dataset_id: str) -> list[Review]:
        return [Review.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted((self._root(dataset_id) / "reviews").glob("*.json"))]

    def reviews_for(self, dataset_id: str, revision_id: str) -> list[Review]:
        return [item for item in self.list_reviews(dataset_id) if item.reviewed_revision_id == revision_id]

    def list_adjudications(self, dataset_id: str) -> list[Adjudication]:
        return [Adjudication.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted((self._root(dataset_id) / "adjudications").glob("*.json"))]

    def list_approvals(self, dataset_id: str) -> list[Approval]:
        return [Approval.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted((self._root(dataset_id) / "approvals").glob("*.json"))]

    def list_invalidations(self, dataset_id: str) -> list[Invalidation]:
        return [Invalidation.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted((self._root(dataset_id) / "invalidations").glob("*.json"))]

    def list_supersessions(self, dataset_id: str) -> list[Supersession]:
        return [Supersession.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted((self._root(dataset_id) / "supersessions").glob("*.json"))]

    def list_events(self, dataset_id: str) -> list[LedgerEvent]:
        return [LedgerEvent.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted((self._root(dataset_id) / "events").glob("*.json"))]

    def project_existing_candidate(self, dataset: AuthoringDataset, candidate: QuestionCandidate) -> tuple[CaseRevision, GoldRevision | None]:
        """One-time, non-destructive projection of existing Authoring files into the ledger."""

        self.ensure_dataset(dataset)
        case_id = self.case_id_for_candidate(candidate.candidate_id)
        existing = self.case_history(dataset.authoring_dataset_id, case_id)
        if existing:
            gold_id = self.gold_id_for_case(case_id)
            return existing[-1], self.current_gold(dataset.authoring_dataset_id, gold_id) if self.gold_history(dataset.authoring_dataset_id, gold_id) else None
        origin = self.origin_from_candidate(candidate).model_copy(
            update={"source_document_ids": (dataset.document_id,) if dataset.document_id else ()}
        )
        draft = self.case_draft_from_candidate(dataset, candidate, case_id=case_id, origin=origin)
        lifecycle = self._legacy_lifecycle(candidate.state)
        case = self.create_case(dataset, draft=draft, actor="existing-authoring-projection", reason="project existing QuestionCandidate as compatibility view")
        if lifecycle != LifecycleState.DRAFT:
            case = self._append_case_revision(dataset, case, draft=draft, actor="existing-authoring-projection", reason="preserve existing candidate state", lifecycle=lifecycle)
        gold: GoldRevision | None = None
        if candidate.answer_evidence is not None:
            gold = self.create_gold(
                dataset,
                gold_id=self.gold_id_for_case(case_id),
                case_revision=case,
                payload=self.gold_payload_from_candidate(candidate.answer_evidence),
                origin=origin,
                actor="existing-authoring-projection",
                reason="project existing answer/evidence as independent Gold",
            )
            if lifecycle != LifecycleState.DRAFT:
                gold = self._append_gold_revision(dataset, gold, payload=gold.payload, actor="existing-authoring-projection", reason="preserve existing candidate state", lifecycle=lifecycle)
        return case, gold

    @staticmethod
    def case_id_for_candidate(candidate_id: str) -> str:
        return f"case-{candidate_id.removeprefix('candidate-')}"

    @staticmethod
    def gold_id_for_case(case_id: str) -> str:
        return f"gold-{case_id.removeprefix('case-')}"

    @staticmethod
    def actor_from_candidate(candidate: QuestionCandidate) -> str:
        actor = candidate.provider_metadata.get("actor")
        return actor.strip() if isinstance(actor, str) and actor.strip() else "authoring-author"

    @staticmethod
    def origin_from_candidate(candidate: QuestionCandidate) -> AuthoringOrigin:
        mapping = {
            DiscoveryMethod.MANUAL: (OriginKind.HUMAN, TrustLevel.HUMAN_ASSERTED),
            DiscoveryMethod.RULE: (OriginKind.TEMPLATE_ASSISTED, TrustLevel.REVIEW_REQUIRED),
            DiscoveryMethod.OLLAMA: (OriginKind.SYNTHETIC, TrustLevel.SYNTHETIC_UNVERIFIED),
            DiscoveryMethod.REMOTE: (OriginKind.SEMI_SYNTHETIC, TrustLevel.SYNTHETIC_UNVERIFIED),
        }
        kind, trust = mapping[candidate.generation_method]
        metadata = candidate.provider_metadata
        config = metadata.get("configuration_digest")
        return AuthoringOrigin(
            kind=kind,
            trust_level=trust,
            generator_identity=str(metadata.get("provider", candidate.generation_method.value)),
            generator_version=str(metadata["provider_version"]) if metadata.get("provider_version") is not None else None,
            configuration_digest=config if isinstance(config, str) and len(config) == 64 else None,
            seed=metadata.get("seed") if isinstance(metadata.get("seed"), int) else None,
            source_world=str(metadata.get("source_world", "private-docx")),
        )

    @staticmethod
    def case_draft_from_candidate(dataset: AuthoringDataset, candidate: QuestionCandidate, *, case_id: str, origin: AuthoringOrigin) -> CaseDraft:
        source_document_ids = (dataset.document_id,) if dataset.document_id else ()
        return CaseDraft(
            case_id=case_id,
            target_id=candidate.target_id,
            question=candidate.question,
            language=candidate.language,
            source_digest=candidate.source_sha256,
            canonical_contract_digest=dataset.canonical_contract_digest,
            canonical_compatibility_digest=candidate.canonical_digest,
            source_object_ids=tuple(candidate.source_object_ids),
            origin=origin.model_copy(update={"source_document_ids": source_document_ids}),
            legacy_candidate_id=candidate.candidate_id,
        )

    @staticmethod
    def gold_payload_from_candidate(value: AnswerEvidenceCandidate) -> GoldPayload:
        required: list[GoldEvidence] = []
        near_miss: list[GoldEvidence] = []
        grouped: dict[str, list[str]] = {}
        for index, selection in enumerate(value.evidence, start=1):
            evidence_id = f"evidence-{index}"
            required.append(GoldEvidence(evidence_id=evidence_id, canonical_object_id=selection.source_object_id, role=EvidenceRole.REQUIRED))
            grouped.setdefault(selection.required_group, []).append(evidence_id)
            for near_index, object_id in enumerate(selection.near_miss_object_ids, start=1):
                near_miss.append(GoldEvidence(evidence_id=f"near-miss-{index}-{near_index}", canonical_object_id=object_id, role=EvidenceRole.NEAR_MISS))
        negative = tuple(value.negative_scope_object_ids)
        evidence = tuple(required + near_miss + [
            GoldEvidence(evidence_id=f"negative-scope-{index}", canonical_object_id=object_id, role=EvidenceRole.NEGATIVE_SCOPE)
            for index, object_id in enumerate(negative, start=1)
        ])
        paths: tuple[MsesPath, ...] = ()
        if value.answer_kind != "abstain":
            # ``required_group`` is a reviewer/model label used only to group
            # alternatives.  It may be natural-language text, while formal
            # clause IDs are intentionally restricted to portable ASCII IDs.
            # Keep the grouping semantics but issue stable ledger-owned IDs.
            paths = (
                MsesPath(
                    path_id="mses-path-1",
                    clauses=tuple(
                        MsesClause(clause_id=f"clause-{index}", alternatives=tuple(items))
                        for index, (_group, items) in enumerate(sorted(grouped.items()), start=1)
                    ),
                ),
            )
        canonical = tuple(value.canonical_answer) if isinstance(value.canonical_answer, list) else value.canonical_answer
        dependencies: list[EvidenceDependency] = []
        # Legacy dependency graph entries do not have stable node identifiers.
        # Retain their ordered multi-hop assertion with new formal IDs rather
        # than letting untyped legacy IDs corrupt the formal dependency graph.
        for index, raw in enumerate(value.dependency_graph, start=1):
            description = str(raw.get("description") or raw.get("relation") or "legacy multi-hop dependency")
            dependencies.append(
                EvidenceDependency(
                    dependency_id=f"dependency-{index}",
                    depends_on=() if index == 1 else (f"dependency-{index - 1}",),
                    description=description,
                )
            )
        return GoldPayload(
            answer=GoldAnswer(
                kind=value.answer_kind,
                canonical=canonical,
                accepted_values=tuple(value.accepted_values),
                locale=value.locale,
                unit=value.unit,
                tolerance=str(value.tolerance) if value.tolerance is not None else None,
            ),
            evidence=evidence,
            mses_paths=paths,
            dependencies=tuple(dependencies),
            negative_scope_object_ids=negative,
            negative_rationale=value.negative_rationale,
        )

    @staticmethod
    def _legacy_lifecycle(state: CandidateState) -> LifecycleState:
        return {
            CandidateState.DRAFT: LifecycleState.DRAFT,
            CandidateState.ANSWER_RESOLVED: LifecycleState.PROPOSED,
            CandidateState.REVIEW_REQUIRED: LifecycleState.PROPOSED,
            CandidateState.APPROVED: LifecycleState.APPROVED,
            CandidateState.REJECTED: LifecycleState.REJECTED,
            CandidateState.BLOCKED: LifecycleState.DRAFT,
        }[state]

    def _append_case_revision(self, dataset: AuthoringDataset, current: CaseRevision, *, draft: CaseDraft, actor: str, reason: str, lifecycle: LifecycleState) -> CaseRevision:
        revision = current.revision + 1
        result = CaseRevision(
            case_revision_id=_revision_id("case", current.case_id, revision),
            case_id=current.case_id,
            revision=revision,
            parent_revision_id=current.case_revision_id,
            lifecycle=lifecycle,
            draft=draft,
            actor=actor,
            created_at=_now(),
            reason=reason,
        )
        self._append(self._case_path(dataset.authoring_dataset_id, current.case_id, revision), result)
        self._event("case_revision_created", TargetKind.CASE, current.case_id, actor, reason, result.case_revision_id)
        return result

    def _append_gold_revision(self, dataset: AuthoringDataset, current: GoldRevision, *, payload: GoldPayload, actor: str, reason: str, lifecycle: LifecycleState, case_revision: CaseRevision | None = None) -> GoldRevision:
        revision = current.revision + 1
        case = case_revision or self.current_case(dataset.authoring_dataset_id, current.case_id)
        result = GoldRevision(
            gold_revision_id=_revision_id("gold", current.gold_id, revision),
            gold_id=current.gold_id,
            revision=revision,
            parent_revision_id=current.gold_revision_id,
            case_id=current.case_id,
            case_revision_id=case.case_revision_id,
            lifecycle=lifecycle,
            payload=payload,
            origin=current.origin,
            actor=actor,
            created_at=_now(),
            reason=reason,
        )
        self._append(self._gold_path(dataset.authoring_dataset_id, current.gold_id, revision), result)
        self._event("gold_revision_created", TargetKind.GOLD, current.gold_id, actor, reason, result.gold_revision_id)
        return result

    def _revision_by_id(self, dataset_id: str, target_kind: TargetKind, revision_id: str) -> CaseRevision | GoldRevision:
        root_name = "cases" if target_kind == TargetKind.CASE else "gold"
        model: type[CaseRevision] | type[GoldRevision] = CaseRevision if target_kind == TargetKind.CASE else GoldRevision
        for path in (self._root(dataset_id) / root_name).glob("*/*.json"):
            value = model.model_validate_json(path.read_text(encoding="utf-8"))
            if (value.case_revision_id if isinstance(value, CaseRevision) else value.gold_revision_id) == revision_id:
                return value
        raise LedgerError("unknown ledger revision")

    @staticmethod
    def _entity_id(value: CaseRevision | GoldRevision) -> str:
        return value.case_id if isinstance(value, CaseRevision) else value.gold_id

    def _root(self, dataset_id: str) -> Path:
        self._active_dataset_id = dataset_id
        root = self.store.workspace(dataset_id) / "ledger"
        for name in ("documents", "cases", "gold", "reviews", "adjudications", "approvals", "invalidations", "supersessions", "releases", "events"):
            (root / name).mkdir(parents=True, exist_ok=True)
        return root

    def _case_path(self, dataset_id: str, case_id: str, revision: int) -> Path:
        root = self._root(dataset_id) / "cases" / safe_id(case_id)
        root.mkdir(exist_ok=True)
        return root / f"{revision:06d}.json"

    def _gold_path(self, dataset_id: str, gold_id: str, revision: int) -> Path:
        root = self._root(dataset_id) / "gold" / safe_id(gold_id)
        root.mkdir(exist_ok=True)
        return root / f"{revision:06d}.json"

    def _document_path(self, dataset_id: str, revision: int) -> Path:
        return self._root(dataset_id) / "documents" / f"{revision:06d}.json"

    def _append(self, path: Path, value: LedgerModel) -> None:
        if path.exists():
            raise LedgerError(f"immutable ledger path already exists: {path.name}")
        atomic_write_json(path, value.model_dump(mode="json"))

    def _event(self, event_type: str, target_kind: TargetKind | Literal["dataset", "document", "release"], entity_id: str, actor: str, reason: str, revision_id: str | None = None) -> LedgerEvent:
        value = LedgerEvent(
            event_id=f"event-{uuid.uuid4().hex}",
            event_type=event_type,
            target_kind=target_kind,
            entity_id=entity_id,
            revision_id=revision_id,
            actor=actor,
            reason=reason,
            created_at=_now(),
        )
        self._append(self._root_from_entity(entity_id) / "events" / f"{value.event_id}.json", value)
        return value

    def _root_from_entity(self, entity_id: str) -> Path:
        if not hasattr(self, "_active_dataset_id"):
            raise LedgerError("ledger event lacks an active dataset context")
        return self._root(getattr(self, "_active_dataset_id"))
