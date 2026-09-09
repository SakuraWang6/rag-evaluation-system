from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_eval.authoring.ledger import (
    ActorRole,
    AuthoringOrigin,
    CaseDraft,
    EvidenceDependency,
    EvidenceRole,
    GoldAnswer,
    GoldEvidence,
    GoldPayload,
    LedgerError,
    LifecycleState,
    MsesClause,
    MsesPath,
    OriginKind,
    ReviewDecision,
    TargetKind,
    TrustLevel,
)
from rag_eval.authoring.models import AnswerEvidenceCandidate, CandidateEvidence, CandidateState, DiscoveryMethod
from rag_eval.authoring.service import AuthoringService
from rag_eval.datasets.registry import FROZEN_20_CASE_BUNDLE_ID
from tests.rag_eval_platform.test_authoring import mini_docx


def _dataset(tmp_path: Path):
    service = AuthoringService(tmp_path / "authoring")
    dataset = service.analyze(
        service.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )
    return service, dataset, service.workflow.ledger


def _origin(*, synthetic: bool = False) -> AuthoringOrigin:
    return AuthoringOrigin(
        kind=OriginKind.SYNTHETIC if synthetic else OriginKind.HUMAN,
        trust_level=TrustLevel.SYNTHETIC_UNVERIFIED if synthetic else TrustLevel.HUMAN_ASSERTED,
        generator_identity="fixture-generator" if synthetic else "fixture-author",
        source_world="private-docx",
    )


def _draft(dataset, case_id: str, *, origin: AuthoringOrigin | None = None) -> CaseDraft:
    return CaseDraft(
        case_id=case_id,
        target_id="target-1",
        question="What is the fixture value?",
        language="en",
        source_digest=dataset.source.sha256,
        canonical_contract_digest=dataset.canonical_contract_digest,
        canonical_compatibility_digest=dataset.canonical_digest,
        source_object_ids=("fixture-object-1",),
        origin=origin or _origin(),
    )


def _payload(*, alternative: bool = False, dependency: bool = False) -> GoldPayload:
    evidence = (
        GoldEvidence(evidence_id="required-a", canonical_object_id="fixture-object-1", role=EvidenceRole.REQUIRED),
        GoldEvidence(evidence_id="required-b", canonical_object_id="fixture-object-2", role=EvidenceRole.REQUIRED),
        GoldEvidence(evidence_id="support", canonical_object_id="fixture-object-3", role=EvidenceRole.SUPPORTING),
        GoldEvidence(evidence_id="conflict", canonical_object_id="fixture-object-4", role=EvidenceRole.CONFLICTING),
    )
    paths = (
        MsesPath(
            path_id="path-1",
            clauses=(
                MsesClause(clause_id="hop-1", alternatives=("required-a", "required-b")),
            ),
        ),
    )
    if alternative:
        paths += (
            MsesPath(
                path_id="path-2",
                clauses=(MsesClause(clause_id="hop-2", alternatives=("required-a",)),),
            ),
        )
    dependencies = (
        EvidenceDependency(dependency_id="retrieve-a", description="retrieve prerequisite"),
        EvidenceDependency(
            dependency_id="derive-answer",
            depends_on=("retrieve-a",),
            description="derive answer from prerequisite",
        ),
    ) if dependency else ()
    return GoldPayload(
        answer=GoldAnswer(kind="text", canonical="fixture"),
        evidence=evidence,
        mses_paths=paths,
        dependencies=dependencies,
    )


def _approved_case_and_gold(tmp_path: Path):
    service, dataset, ledger = _dataset(tmp_path)
    case = ledger.create_case(
        dataset,
        draft=_draft(dataset, "case-ledger-1"),
        actor="fixture-author",
        reason="write fixture Case",
    )
    proposed_case = ledger.propose_case(dataset, case_id=case.case_id, actor="fixture-author", reason="submit Case")
    gold = ledger.create_gold(
        dataset,
        gold_id="gold-ledger-1",
        case_revision=proposed_case,
        payload=_payload(),
        origin=_origin(),
        actor="fixture-author",
        reason="write fixture Gold",
    )
    proposed_gold = ledger.propose_gold(dataset, gold_id=gold.gold_id, actor="fixture-author", reason="submit Gold")
    ledger.record_review(
        dataset.authoring_dataset_id,
        target_kind=TargetKind.CASE,
        reviewed_revision_id=proposed_case.case_revision_id,
        reviewer="fixture-reviewer",
        decision=ReviewDecision.APPROVE,
        checklist={"source_grounded": True},
    )
    ledger.record_review(
        dataset.authoring_dataset_id,
        target_kind=TargetKind.GOLD,
        reviewed_revision_id=proposed_gold.gold_revision_id,
        reviewer="fixture-reviewer",
        decision=ReviewDecision.APPROVE,
        checklist={"mses_checked": True},
    )
    reviewed_case = ledger.mark_reviewed(
        dataset,
        target_kind=TargetKind.CASE,
        revision_id=proposed_case.case_revision_id,
        actor="fixture-author",
        reason="review complete",
    )
    reviewed_gold = ledger.mark_reviewed(
        dataset,
        target_kind=TargetKind.GOLD,
        revision_id=proposed_gold.gold_revision_id,
        actor="fixture-author",
        reason="review complete",
    )
    approved_case = ledger.approve(
        dataset,
        target_kind=TargetKind.CASE,
        revision_id=reviewed_case.case_revision_id,
        approver="fixture-reviewer",
        reason="approved Case",
    )
    approved_gold = ledger.approve(
        dataset,
        target_kind=TargetKind.GOLD,
        revision_id=reviewed_gold.gold_revision_id,
        approver="fixture-reviewer",
        reason="approved Gold",
    )
    return service, dataset, ledger, approved_case, approved_gold


def test_case_gold_history_is_append_only_and_requires_independent_review(tmp_path: Path) -> None:
    _, dataset, ledger, approved_case, approved_gold = _approved_case_and_gold(tmp_path)

    case_history = ledger.case_history(dataset.authoring_dataset_id, approved_case.case_id)
    gold_history = ledger.gold_history(dataset.authoring_dataset_id, approved_gold.gold_id)
    assert [item.lifecycle for item in case_history] == [
        LifecycleState.DRAFT,
        LifecycleState.PROPOSED,
        LifecycleState.REVIEWED,
        LifecycleState.APPROVED,
    ]
    assert [item.lifecycle for item in gold_history] == [
        LifecycleState.DRAFT,
        LifecycleState.PROPOSED,
        LifecycleState.REVIEWED,
        LifecycleState.APPROVED,
    ]
    assert case_history[-1].parent_revision_id == case_history[-2].case_revision_id
    assert gold_history[-1].parent_revision_id == gold_history[-2].gold_revision_id
    assert len(ledger.list_approvals(dataset.authoring_dataset_id)) == 2
    with pytest.raises(ValidationError):
        approved_case.draft.question = "mutate immutable history"  # type: ignore[misc]
    with pytest.raises(LedgerError, match="already exists"):
        ledger.create_case(dataset, draft=_draft(dataset, approved_case.case_id), actor="other", reason="overwrite")
    with pytest.raises(LedgerError, match="reviewed"):
        ledger.approve(
            dataset,
            target_kind=TargetKind.GOLD,
            revision_id=gold_history[1].gold_revision_id,
            approver="fixture-reviewer",
            reason="attempt to skip review state",
        )


def test_rejection_invalidation_and_supersession_preserve_prior_gold(tmp_path: Path) -> None:
    _, dataset, ledger, approved_case, approved_gold = _approved_case_and_gold(tmp_path)
    invalidated = ledger.invalidate(
        dataset,
        target_kind=TargetKind.GOLD,
        revision_id=approved_gold.gold_revision_id,
        actor="fixture-adjudicator",
        reason="source correction invalidates original answer",
    )
    successor = ledger.supersede_gold(
        dataset,
        gold_id=approved_gold.gold_id,
        successor_gold_id="gold-ledger-2",
        case_revision=approved_case,
        payload=_payload(),
        origin=_origin(),
        actor="fixture-author-2",
        reason="new Gold follows corrected source",
    )
    assert invalidated.lifecycle == LifecycleState.INVALIDATED
    assert ledger.gold_history(dataset.authoring_dataset_id, approved_gold.gold_id)[-1] == invalidated
    assert successor.lifecycle == LifecycleState.DRAFT
    assert ledger.list_supersessions(dataset.authoring_dataset_id)[0].superseded_revision_id == invalidated.gold_revision_id

    rejected_case = ledger.create_case(
        dataset,
        draft=_draft(dataset, "case-rejected"),
        actor="fixture-author-2",
        reason="draft to reject",
    )
    rejected_case = ledger.propose_case(dataset, case_id=rejected_case.case_id, actor="fixture-author-2", reason="submit")
    rejected = ledger.reject(
        dataset,
        target_kind=TargetKind.CASE,
        revision_id=rejected_case.case_revision_id,
        reviewer="fixture-reviewer",
        reason="not sufficiently grounded",
    )
    assert rejected.lifecycle == LifecycleState.REJECTED


def test_disagreement_adjudication_and_synthetic_auto_approval_fail_closed(tmp_path: Path) -> None:
    _, dataset, ledger = _dataset(tmp_path)
    case = ledger.create_case(dataset, draft=_draft(dataset, "case-disagreement"), actor="fixture-author", reason="draft")
    proposed = ledger.propose_case(dataset, case_id=case.case_id, actor="fixture-author", reason="submit")
    positive = ledger.record_review(
        dataset.authoring_dataset_id,
        target_kind=TargetKind.CASE,
        reviewed_revision_id=proposed.case_revision_id,
        reviewer="reviewer-one",
        decision=ReviewDecision.APPROVE,
    )
    negative = ledger.record_review(
        dataset.authoring_dataset_id,
        target_kind=TargetKind.CASE,
        reviewed_revision_id=proposed.case_revision_id,
        reviewer="reviewer-two",
        decision=ReviewDecision.DISAGREE,
    )
    adjudication = ledger.adjudicate(
        dataset,
        target_kind=TargetKind.CASE,
        revision_id=proposed.case_revision_id,
        review_ids=(positive.review_id, negative.review_id),
        adjudicator="fixture-adjudicator",
        decision=ReviewDecision.APPROVE,
        comments="adjudicator resolves conflicting reviews",
    )
    resolved = ledger.approve_adjudication(
        dataset,
        target_kind=TargetKind.CASE,
        revision_id=proposed.case_revision_id,
        adjudication=adjudication,
    )
    assert resolved.lifecycle == LifecycleState.APPROVED

    synthetic_case = ledger.create_case(
        dataset,
        draft=_draft(dataset, "case-synthetic", origin=_origin(synthetic=True)),
        actor="synthetic-generator",
        reason="synthetic Case draft",
    )
    synthetic_case = ledger.propose_case(dataset, case_id=synthetic_case.case_id, actor="synthetic-generator", reason="submit synthetic proposal")
    synthetic_gold = ledger.create_gold(
        dataset,
        gold_id="gold-synthetic",
        case_revision=synthetic_case,
        payload=_payload(),
        origin=_origin(synthetic=True),
        actor="synthetic-generator",
        reason="synthetic Gold draft",
    )
    synthetic_gold = ledger.propose_gold(dataset, gold_id=synthetic_gold.gold_id, actor="synthetic-generator", reason="submit synthetic Gold")
    with pytest.raises(LedgerError, match="reviewed"):
        ledger.approve(
            dataset,
            target_kind=TargetKind.GOLD,
            revision_id=synthetic_gold.gold_revision_id,
            approver="synthetic-generator",
            reason="synthetic self approval",
        )
    with pytest.raises(LedgerError, match="cannot review"):
        ledger.record_review(
            dataset.authoring_dataset_id,
            target_kind=TargetKind.GOLD,
            reviewed_revision_id=synthetic_gold.gold_revision_id,
            reviewer="synthetic-generator",
            decision=ReviewDecision.APPROVE,
        )


def test_mses_alternatives_multihop_and_negative_scope_are_formal_and_bundle_v2_is_explicitly_lossy(tmp_path: Path) -> None:
    rich = _payload(alternative=True, dependency=True)
    assert len(rich.mses_paths) == 2  # Alternative MSES paths (OR).
    assert rich.mses_paths[0].clauses[0].alternatives == ("required-a", "required-b")  # Clause OR.
    assert rich.dependencies[1].depends_on == ("retrieve-a",)  # Multi-hop.
    negative = GoldPayload(
        answer=GoldAnswer(kind="abstain"),
        evidence=(GoldEvidence(evidence_id="scope", canonical_object_id="fixture-object-1", role=EvidenceRole.NEGATIVE_SCOPE),),
        negative_scope_object_ids=("fixture-object-1", "fixture-object-2"),
        negative_rationale="scoped absence only",
    )
    assert negative.answer.kind == "abstain"
    with pytest.raises(ValidationError, match="scoped negative"):
        GoldPayload(answer=GoldAnswer(kind="abstain"))
    with pytest.raises(ValidationError, match="MSES path"):
        GoldPayload(
            answer=GoldAnswer(kind="text", canonical="must fail closed"),
            evidence=(GoldEvidence(evidence_id="required", canonical_object_id="object", role=EvidenceRole.REQUIRED),),
        )

    _, dataset, ledger, _, approved_gold = _approved_case_and_gold(tmp_path)
    rich_revision = ledger.revise_gold(
        dataset,
        gold_id=approved_gold.gold_id,
        payload=rich,
        actor="fixture-author",
        reason="express alternative MSES paths and multi-hop evidence",
    )
    assessment = ledger.assess_bundle_v2(rich_revision)
    assert not assessment.runnable and assessment.lossy
    assert set(assessment.reasons).issuperset(
        {
            "alternative_mses_paths_are_not_representable",
            "or_alternatives_within_mses_clause_are_not_representable",
            "multi_hop_dependencies_are_not_representable",
            "non_required_evidence_roles_are_not_representable",
        }
    )


def test_docx_authoring_freezes_ledger_without_changing_frozen_registry(tmp_path: Path) -> None:
    service, dataset, ledger = _dataset(tmp_path)
    target = next(
        item
        for item in service.workflow.discover_targets(dataset, provider=DiscoveryMethod.RULE)
        if item.capability == "table_lookup" and not item.flags
    )
    candidate = service.workflow.create_question(
        service.get(dataset.authoring_dataset_id),
        target_id=target.target_id,
        question="延迟指标对应的数值是多少？",
    )
    resolved = service.workflow.resolve_answer_evidence(
        service.get(dataset.authoring_dataset_id),
        candidate_id=candidate.candidate_id,
        resolution=AnswerEvidenceCandidate(
            answer_kind="text",
            canonical_answer="42 ms",
            evidence=[CandidateEvidence(source_object_id=target.source_object_ids[0])],
        ),
    )
    assert resolved.state == CandidateState.REVIEW_REQUIRED
    service.workflow.review(
        service.get(dataset.authoring_dataset_id),
        candidate_id=candidate.candidate_id,
        decision="accept",
        reviewer="fixture-reviewer",
    )
    case_id = ledger.case_id_for_candidate(candidate.candidate_id)
    frozen = ledger.freeze_release(
        service.get(dataset.authoring_dataset_id),
        release_id="ledger-fixture",
        case_ids=(case_id,),
        actor="fixture-release-manager",
        reason="freeze approved native benchmark state",
    )
    assert frozen.ledger_release_id == "ledger-ledger-fixture"
    gold_id = ledger.gold_id_for_case(case_id)
    assert ledger.current_case(dataset.authoring_dataset_id, case_id).lifecycle == LifecycleState.FROZEN
    assert ledger.current_gold(dataset.authoring_dataset_id, gold_id).lifecycle == LifecycleState.FROZEN
    report_registry = Path(__file__).resolve().parents[2] / "registries" / "reference-datasets" / f"{FROZEN_20_CASE_BUNDLE_ID}.json"
    frozen_record = json.loads(report_registry.read_text(encoding="utf-8"))
    assert frozen_record["bundle_id"] == FROZEN_20_CASE_BUNDLE_ID
    assert frozen_record["metadata"]["bundle_mutated"] is False
