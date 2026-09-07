from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_eval.authoring.ledger import LifecycleState, TargetKind
from rag_eval.authoring.models import AnswerEvidenceCandidate, CandidateEvidence, DiscoveryMethod
from rag_eval.authoring.service import AuthoringService
from rag_eval.datasets.formal import FormalDatasetReleaseService
from rag_eval.datasets.portfolio import (
    BenchmarkPortfolioService,
    EvidenceRequirement,
    PortfolioError,
    PortfolioBlockedReason,
    PortfolioAssignment,
    PortfolioLinks,
    PortfolioSlot,
    PortfolioSlotState,
    PortfolioUsage,
)
from rag_eval.datasets.registry import FROZEN_20_CASE_BUNDLE_ID
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths
from tests.rag_eval_platform.test_authoring import mini_docx


def _service(tmp_path: Path, **kwargs: object) -> BenchmarkPortfolioService:
    service = BenchmarkPortfolioService(
        tmp_path / "portfolios",
        source_root=BenchmarkPortfolioService.default_source_root(),
        **kwargs,
    )
    service.bootstrap_v0_dry_run()
    return service


def _bucket(report, *, axis: str, value: str):
    return next(item for item in report.coverage if item.axis.value == axis and item.value == value)


def test_blueprint_and_dry_run_are_imported_as_typed_immutable_portfolio(tmp_path: Path) -> None:
    service = _service(tmp_path)
    portfolio = service.store.get("benchmark-v0-dry-run-48")

    assert len(portfolio.matrix) == 19
    assert len(portfolio.slots) == 48
    assert {item.name for item in portfolio.artifacts} == {
        "BENCHMARK_BLUEPRINT_V0.md",
        "BENCHMARK_PROTOCOL_V0.md",
        "BENCHMARK_V0_CASE_MATRIX.csv",
        "BENCHMARK_48_CASE_DRY_RUN_PLAN.csv",
    }
    assert {slot.plan_group_id for slot in portfolio.slots} == {f"DRY-{number:02d}" for number in range(1, 13)}
    assert sum(slot.language.value == "en" for slot in portfolio.slots) == 36
    assert sum(slot.language.value == "zh" for slot in portfolio.slots) == 12
    assert {slot.source_type.value for slot in portfolio.slots} == {
        "human", "semi_synthetic", "synthetic", "adversarial"
    }
    assert all(slot.usage == PortfolioUsage.DEVELOPMENT for slot in portfolio.slots)
    assert all(slot.source_family.value == "unassigned" for slot in portfolio.slots)

    with pytest.raises(ValidationError):
        PortfolioSlot.model_validate(
            portfolio.slots[0].model_dump(mode="python") | {"usage": PortfolioUsage.HELD_OUT}
        )
    with pytest.raises(PortfolioError, match="immutable"):
        service.store.put(
            portfolio.model_copy(update={"title": "attempted rewrite"}),
            artifact_payloads={item.name: (BenchmarkPortfolioService.default_source_root() / item.name).read_bytes() for item in portfolio.artifacts},
        )


def test_coverage_deficits_are_deterministic_and_blocked_slots_do_not_complete(tmp_path: Path) -> None:
    service = _service(tmp_path)
    first = service.coverage_report()
    second = service.coverage_report()

    assert first.report_digest == second.report_digest
    assert dict(first.state_counts)[PortfolioSlotState.PLANNED] == 48
    assert _bucket(first, axis="evidence_requirement", value=EvidenceRequirement.MULTI_HOP.value).planned == 4
    assert _bucket(first, axis="evidence_requirement", value=EvidenceRequirement.MULTI_HOP.value).missing == 4
    assert _bucket(first, axis="source_type", value="human").planned == 12
    assert _bucket(first, axis="language", value="zh").planned == 12
    # Includes long-distance/lexical slots and the negative slots whose
    # Blueprint constraint permits the same Hard-retrieval/Easy-reasoning pair.
    assert _bucket(first, axis="retrieval_reasoning", value="Hard|Easy").planned == 16
    assert first.frozen_reference.bundle_id == FROZEN_20_CASE_BUNDLE_ID
    assert first.frozen_reference.case_count == 20
    assert not first.frozen_reference.held_out
    assert not first.frozen_reference.generalization_claim_allowed
    assert not first.frozen_reference.typed_case_axes_available

    blocked = service.transition_slot(
        "benchmark-v0-dry-run-48",
        slot_id="DRY-05-slot-01",
        state=PortfolioSlotState.BLOCKED,
        links=PortfolioLinks(),
        actor="protocol-owner",
        reason="independent calibration reference lock is not yet available",
        blocked_reason=PortfolioBlockedReason.INSUFFICIENT_MULTI_HOP_STRUCTURE,
    )
    assert blocked.state == PortfolioSlotState.BLOCKED
    report = service.coverage_report()
    multihop = _bucket(report, axis="evidence_requirement", value=EvidenceRequirement.MULTI_HOP.value)
    assert multihop.completed == 0
    assert multihop.missing == 4
    assert multihop.blocked == 1
    assert dict(report.state_counts)[PortfolioSlotState.BLOCKED] == 1

    with pytest.raises(PortfolioError, match="Authoring Ledger"):
        service.transition_slot(
            "benchmark-v0-dry-run-48",
            slot_id="DRY-01-slot-01",
            state=PortfolioSlotState.AUTHORED,
            links=PortfolioLinks(dataset_id="dataset", case_revision_id="case-revision-1"),
            actor="author",
            reason="must not bypass the Ledger",
        )
    assert "lightrag" not in inspect.getsource(__import__("rag_eval.datasets.portfolio", fromlist=["*"])).lower()


def test_blocked_assignment_requires_a_typed_reason() -> None:
    base = {
        "assignment_id": "portfolio-assignment-DRY-01-slot-01-000001",
        "slot_id": "DRY-01-slot-01",
        "revision": 1,
        "parent_assignment_id": None,
        "state": PortfolioSlotState.BLOCKED,
        "links": PortfolioLinks(),
        "actor": "evidence-steward",
        "reason": "the real source lacks an eligible modality",
        "created_at": "2026-08-29T00:00:00Z",
    }
    with pytest.raises(ValidationError, match="typed blocked_reason"):
        PortfolioAssignment.model_validate(base)
    value = PortfolioAssignment.model_validate(
        base | {"blocked_reason": PortfolioBlockedReason.UNSUPPORTED_MODALITY}
    )
    assert value.blocked_reason == PortfolioBlockedReason.UNSUPPORTED_MODALITY
    with pytest.raises(ValidationError, match="only valid"):
        PortfolioAssignment.model_validate(
            base
            | {
                "state": PortfolioSlotState.PLANNED,
                "blocked_reason": PortfolioBlockedReason.UNSUPPORTED_MODALITY,
            }
        )


def test_blocked_slot_reassessment_is_append_only_and_does_not_reopen_slot(tmp_path: Path) -> None:
    service = _service(tmp_path)
    first = service.transition_slot(
        "benchmark-v0-dry-run-48",
        slot_id="DRY-08-slot-01",
        state=PortfolioSlotState.BLOCKED,
        links=PortfolioLinks(),
        actor="evidence-steward",
        reason="the first audit did not model source-rich content",
        blocked_reason=PortfolioBlockedReason.UNSUPPORTED_MODALITY,
    )
    second = service.reassess_blocked_slot(
        "benchmark-v0-dry-run-48",
        slot_id="DRY-08-slot-01",
        actor="canonical-auditor",
        reason="the modality is modeled, but no natural linked figure-and-equation claim exists",
        blocked_reason=PortfolioBlockedReason.OTHER_DOCUMENTED,
    )

    assert second.state == PortfolioSlotState.BLOCKED
    assert second.revision == 2
    assert second.parent_assignment_id == first.assignment_id
    assert second.blocked_reason == PortfolioBlockedReason.OTHER_DOCUMENTED
    assert service.store.assignment_history("benchmark-v0-dry-run-48", "DRY-08-slot-01") == [first, second]
    with pytest.raises(PortfolioError, match="illegal Portfolio transition"):
        service.transition_slot(
            "benchmark-v0-dry-run-48",
            slot_id="DRY-08-slot-01",
            state=PortfolioSlotState.AUTHORED,
            links=PortfolioLinks(dataset_id="dataset", case_revision_id="case-revision-1"),
            actor="author",
            reason="must not reopen a blocked slot",
        )


def test_authoring_and_release_links_gate_completed_coverage_and_invalidation(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(
        authoring.upload_docx(filename="private.docx", payload=mini_docx()).authoring_dataset_id
    )
    target = next(
        item
        for item in authoring.workflow.discover_targets(dataset, provider=DiscoveryMethod.RULE)
        if item.capability == "table_lookup" and not item.flags
    )
    candidate = authoring.workflow.create_question(
        authoring.get(dataset.authoring_dataset_id),
        target_id=target.target_id,
        question="延迟指标对应的数值是多少？",
    )
    ledger = authoring.workflow.ledger
    case_id = ledger.case_id_for_candidate(candidate.candidate_id)
    draft_case = ledger.current_case(dataset.authoring_dataset_id, case_id)
    formal = FormalDatasetReleaseService(authoring_store=authoring.store, release_root=tmp_path / "formal")
    service = _service(tmp_path, ledger=ledger, releases=formal.releases)
    slot_id = "DRY-01-slot-01"

    service.transition_slot(
        "benchmark-v0-dry-run-48",
        slot_id=slot_id,
        state=PortfolioSlotState.AUTHORED,
        links=PortfolioLinks(
            dataset_id=dataset.authoring_dataset_id,
            case_revision_id=draft_case.case_revision_id,
        ),
        actor="fixture-author",
        reason="created formal Case draft",
    )
    authoring.workflow.resolve_answer_evidence(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=candidate.candidate_id,
        resolution=AnswerEvidenceCandidate(
            answer_kind="text",
            canonical_answer="42 ms",
            evidence=[CandidateEvidence(source_object_id=target.source_object_ids[0])],
        ),
    )
    authoring.workflow.review(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=candidate.candidate_id,
        decision="accept",
        reviewer="independent-reviewer",
    )
    reviewed_case = next(
        item
        for item in ledger.case_history(dataset.authoring_dataset_id, case_id)
        if item.lifecycle == LifecycleState.REVIEWED
    )
    service.transition_slot(
        "benchmark-v0-dry-run-48",
        slot_id=slot_id,
        state=PortfolioSlotState.REVIEWED,
        links=PortfolioLinks(
            dataset_id=dataset.authoring_dataset_id,
            case_revision_id=reviewed_case.case_revision_id,
        ),
        actor="fixture-author",
        reason="independent reviewer completed Case review",
    )
    approved_case = ledger.current_case(dataset.authoring_dataset_id, case_id)
    approved_gold = ledger.current_gold_for_case(dataset.authoring_dataset_id, case_id)
    document = ledger.document_history(dataset.authoring_dataset_id)[-1]
    service.transition_slot(
        "benchmark-v0-dry-run-48",
        slot_id=slot_id,
        state=PortfolioSlotState.APPROVED,
        links=PortfolioLinks(
            dataset_id=dataset.authoring_dataset_id,
            document_revision_id=document.document_revision_id,
            case_revision_id=approved_case.case_revision_id,
            gold_revision_id=approved_gold.gold_revision_id,
        ),
        actor="independent-reviewer",
        reason="formal Case and Gold were independently approved",
    )
    approved = service.coverage_report()
    assert _bucket(approved, axis="source_type", value="human").completed == 1

    release = formal.freeze(
        dataset.authoring_dataset_id,
        release_version="1.0.0",
        case_ids=(case_id,),
        actor="release-manager",
    )
    frozen_case_id = release.cases[0].case_revision_id
    frozen_gold_id = release.gold[0].gold_revision_id
    service.transition_slot(
        "benchmark-v0-dry-run-48",
        slot_id=slot_id,
        state=PortfolioSlotState.FROZEN,
        links=PortfolioLinks(
            dataset_id=dataset.authoring_dataset_id,
            document_revision_id=document.document_revision_id,
            case_revision_id=frozen_case_id,
            gold_revision_id=frozen_gold_id,
            release_id=release.release_id,
        ),
        actor="release-manager",
        reason="immutable formal release pins Case and Gold revisions",
    )
    assert _bucket(service.coverage_report(), axis="source_type", value="human").completed == 1

    ledger.invalidate(
        authoring.get(dataset.authoring_dataset_id),
        target_kind=TargetKind.CASE,
        revision_id=ledger.current_case(dataset.authoring_dataset_id, case_id).case_revision_id,
        actor="independent-reviewer",
        reason="fixture invalidation verifies fail-closed coverage",
    )
    invalidated = service.coverage_report()
    assert _bucket(invalidated, axis="source_type", value="human").completed == 0
    assert _bucket(invalidated, axis="source_type", value="human").missing == 12


def test_platform_bootstraps_planning_contract_without_touching_bundle_store(tmp_path: Path) -> None:
    platform = PlatformService(PlatformPaths(tmp_path))
    assert platform.portfolios is not None
    portfolio = platform.portfolios.store.get("benchmark-v0-dry-run-48")
    assert len(portfolio.slots) == 48
    assert list((tmp_path / "datasets").glob("*.json")) == []
