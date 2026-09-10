from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_eval.authoring.ledger import (
    EvidenceRole,
    GoldAnswer,
    GoldEvidence,
    GoldPayload,
    MsesClause,
    MsesPath,
    ReviewDecision,
    TargetKind,
)
from rag_eval.authoring.models import AnswerEvidenceCandidate, CandidateEvidence, DiscoveryMethod
from rag_eval.authoring.service import AuthoringService
from rag_eval.datasets.formal import (
    FormalDatasetError,
    FormalDatasetReleaseService,
    ReleaseSchemaVersions,
    RuleResult,
    RuleSeverity,
)
from tests.rag_eval_platform.test_authoring import mini_docx


def _workflow(tmp_path: Path, *, question: str = "延迟指标对应的数值是多少？"):
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
        question=question,
    )
    resolved = authoring.workflow.resolve_answer_evidence(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=candidate.candidate_id,
        resolution=AnswerEvidenceCandidate(
            answer_kind="text",
            canonical_answer="42 ms",
            evidence=[CandidateEvidence(source_object_id=target.source_object_ids[0])],
        ),
    )
    formal = FormalDatasetReleaseService(
        authoring_store=authoring.store, release_root=tmp_path / "formal-releases"
    )
    return authoring, dataset, candidate, resolved, formal, target


def test_release_reader_rejects_retired_ledger_and_validator_contracts() -> None:
    with pytest.raises(ValidationError):
        ReleaseSchemaVersions.model_validate(
            {
                "canonical_schema_version": "1.1",
                "ledger_schema_version": "authoring-ledger/1.0",
                "validator_version": "formal-dataset-validator/1.0",
                "release_schema_version": "formal-dataset-release/2.0",
            }
        )


def test_release_resolves_a_pinned_native_benchmark_without_a_runtime_bundle(
    tmp_path: Path,
) -> None:
    authoring, dataset, candidate, _resolved, formal, _target = _workflow(tmp_path)
    _approve(authoring, dataset, candidate)
    release = formal.freeze(
        dataset.authoring_dataset_id,
        release_version="runtime-projection-1.0.0",
        case_ids=(_case_id(formal, candidate),),
        actor="fixture-release-manager",
    )

    benchmark = formal.resolve_native_benchmark(release.release_id)

    assert benchmark.cases[0].case_id == release.cases[0].case_id
    assert benchmark.release_id == release.release_id
    assert benchmark.release_digest == release.release_digest
    assert benchmark.source_identity.source_sha256 == release.document.source_digest
    assert benchmark.original_docx_path.read_bytes() == formal.releases.source_snapshot(
        release.release_id
    ).read_bytes()
    assert all(item.canonical_object_id for item in benchmark.cases[0].gold.evidence)


def _approve(authoring: AuthoringService, dataset, candidate) -> None:
    authoring.workflow.review(
        authoring.get(dataset.authoring_dataset_id),
        candidate_id=candidate.candidate_id,
        decision="accept",
        reviewer="fixture-reviewer",
    )


def _case_id(formal: FormalDatasetReleaseService, candidate) -> str:
    return formal.ledger.case_id_for_candidate(candidate.candidate_id)


def test_validator_generates_deterministic_error_report_and_blocks_freeze(tmp_path: Path) -> None:
    authoring, dataset, candidate, resolved, formal, _ = _workflow(
        tmp_path, question="42 ms 是延迟指标的数值吗？"
    )
    assert resolved.state.value == "blocked"
    case_id = _case_id(formal, candidate)
    case = formal.ledger.current_case(dataset.authoring_dataset_id, case_id)
    gold = formal.ledger.current_gold_for_case(dataset.authoring_dataset_id, case_id)
    first = formal.validate(
        dataset.authoring_dataset_id,
        case_revision_ids=(case.case_revision_id,),
        gold_revision_ids=(gold.gold_revision_id,),
    )
    second = formal.validate(
        dataset.authoring_dataset_id,
        case_revision_ids=(case.case_revision_id,),
        gold_revision_ids=(gold.gold_revision_id,),
    )
    assert first.report_digest == second.report_digest
    assert first.has_errors
    assert any(
        item.rule_id == "case.answer_leakage"
        and item.severity == RuleSeverity.ERROR
        and item.result == RuleResult.FAIL
        for item in first.findings
    )
    assert formal.releases.reports.get(first.report_digest) == first
    with pytest.raises(FormalDatasetError, match="report="):
        formal.freeze(
            dataset.authoring_dataset_id,
            release_version="1.0.0",
            case_ids=(case_id,),
            actor="release-manager",
        )
    assert formal.releases.list() == []


def test_rich_gold_is_preserved_without_a_lossy_runtime_projection(
    tmp_path: Path,
) -> None:
    authoring, dataset, candidate, _, formal, target = _workflow(tmp_path)
    _approve(authoring, dataset, candidate)
    case_id = _case_id(formal, candidate)
    case = formal.ledger.current_case(dataset.authoring_dataset_id, case_id)
    current_gold = formal.ledger.current_gold_for_case(dataset.authoring_dataset_id, case_id)
    rich = GoldPayload(
        answer=GoldAnswer(kind="text", canonical="42 ms"),
        evidence=(
            GoldEvidence(evidence_id="required-a", canonical_object_id=target.source_object_ids[0], role=EvidenceRole.REQUIRED),
            GoldEvidence(evidence_id="required-b", canonical_object_id=target.source_object_ids[0], role=EvidenceRole.REQUIRED),
            GoldEvidence(evidence_id="support", canonical_object_id=target.source_object_ids[0], role=EvidenceRole.SUPPORTING),
        ),
        mses_paths=(
            MsesPath(
                path_id="path-a",
                clauses=(MsesClause(clause_id="clause-a", alternatives=("required-a", "required-b")),),
            ),
            MsesPath(
                path_id="path-b",
                clauses=(MsesClause(clause_id="clause-b", alternatives=("required-a",)),),
            ),
        ),
    )
    revised = formal.ledger.revise_gold(
        dataset,
        gold_id=current_gold.gold_id,
        payload=rich,
        actor="authoring-author",
        reason="formal alternative MSES example",
        case_revision=case,
    )
    proposed = formal.ledger.propose_gold(
        dataset, gold_id=revised.gold_id, actor="authoring-author", reason="submit revised Gold"
    )
    formal.ledger.record_review(
        dataset.authoring_dataset_id,
        target_kind=TargetKind.GOLD,
        reviewed_revision_id=proposed.gold_revision_id,
        reviewer="fixture-reviewer",
        decision=ReviewDecision.APPROVE,
    )
    reviewed = formal.ledger.mark_reviewed(
        dataset,
        target_kind=TargetKind.GOLD,
        revision_id=proposed.gold_revision_id,
        actor="authoring-author",
        reason="reviewed rich Gold",
    )
    approved = formal.ledger.approve(
        dataset,
        target_kind=TargetKind.GOLD,
        revision_id=reviewed.gold_revision_id,
        approver="fixture-reviewer",
        reason="approve rich Gold",
    )
    report = formal.validate(
        dataset.authoring_dataset_id,
        case_revision_ids=(case.case_revision_id,),
        gold_revision_ids=(approved.gold_revision_id,),
    )
    assert not report.has_errors
    with pytest.raises(TypeError, match="bundle_id"):
        formal.freeze(
            dataset.authoring_dataset_id,
            release_version="1.0.0",
            case_ids=(case_id,),
            actor="release-manager",
            bundle_id="a" * 64,
        )
    release = formal.freeze(
        dataset.authoring_dataset_id,
        release_version="1.0.0",
        case_ids=(case_id,),
        actor="release-manager",
    )
    benchmark = formal.resolve_native_benchmark(release.release_id)
    gold = benchmark.cases[0].gold
    assert len(gold.mses_paths) == 2
    assert gold.mses_paths[0].clauses[0].alternatives == (
        "required-a",
        "required-b",
    )
    assert any(item.role.value == "supporting" for item in gold.evidence)


def test_immutable_release_parent_successor_lineage_and_deterministic_rebuild(tmp_path: Path) -> None:
    authoring, dataset, candidate, _, formal, _ = _workflow(tmp_path)
    _approve(authoring, dataset, candidate)
    case_id = _case_id(formal, candidate)
    first = formal.freeze(
        dataset.authoring_dataset_id,
        release_version="1.0.0",
        case_ids=(case_id,),
        actor="release-manager",
    )
    assert formal.rebuild(first.release_id).reproducible
    with pytest.raises(ValidationError):
        first.release_version = "mutated"  # type: ignore[misc]

    case = formal.ledger.current_case(dataset.authoring_dataset_id, case_id)
    original_gold = formal.ledger.current_gold_for_case(dataset.authoring_dataset_id, case_id)
    successor = formal.ledger.supersede_gold(
        dataset,
        gold_id=original_gold.gold_id,
        successor_gold_id="gold-successor",
        case_revision=case,
        payload=original_gold.payload,
        origin=original_gold.origin,
        actor="correcting-author",
        reason="corrected Gold successor",
    )
    successor = formal.ledger.propose_gold(
        dataset, gold_id=successor.gold_id, actor="correcting-author", reason="submit successor"
    )
    formal.ledger.record_review(
        dataset.authoring_dataset_id,
        target_kind=TargetKind.GOLD,
        reviewed_revision_id=successor.gold_revision_id,
        reviewer="successor-reviewer",
        decision=ReviewDecision.APPROVE,
    )
    successor = formal.ledger.mark_reviewed(
        dataset,
        target_kind=TargetKind.GOLD,
        revision_id=successor.gold_revision_id,
        actor="correcting-author",
        reason="review successor",
    )
    formal.ledger.approve(
        dataset,
        target_kind=TargetKind.GOLD,
        revision_id=successor.gold_revision_id,
        approver="successor-reviewer",
        reason="approve successor",
    )
    second = formal.freeze(
        dataset.authoring_dataset_id,
        release_version="1.1.0",
        case_ids=(case_id,),
        actor="release-manager",
        parent_release_id=first.release_id,
    )
    lineage = formal.lineage(second.release_id)
    assert lineage.changes_from_parent.parent_release_id == first.release_id
    assert lineage.changes_from_parent.added_gold_ids == ("gold-successor",)
    assert lineage.changes_from_parent.removed_gold_ids == (original_gold.gold_id,)
    assert formal.rebuild(first.release_id).reproducible
    assert formal.rebuild(second.release_id).reproducible

    source_path = formal.releases.source_snapshot(second.release_id)
    source_path.write_bytes(b"tampered source snapshot")
    assert not formal.rebuild(second.release_id).reproducible


def test_freeze_preserves_authorship_when_release_manager_is_the_reviewer(tmp_path: Path) -> None:
    """Freezing must not turn an independently approved item into self-approval."""

    authoring, dataset, candidate, _, formal, _ = _workflow(tmp_path)
    _approve(authoring, dataset, candidate)
    case_id = _case_id(formal, candidate)
    release = formal.freeze(
        dataset.authoring_dataset_id,
        release_version="1.0.0",
        case_ids=(case_id,),
        actor="fixture-reviewer",
    )

    frozen_case = formal.ledger.get_case_revision(dataset.authoring_dataset_id, release.cases[0].case_revision_id)
    frozen_gold = formal.ledger.get_gold_revision(dataset.authoring_dataset_id, release.gold[0].gold_revision_id)
    assert frozen_case.actor == "authoring-author"
    assert frozen_gold.actor == "authoring-author"
    marker = formal.ledger.get_authoring_release(
        dataset.authoring_dataset_id, release.ledger_state.authoring_freeze_id
    )
    assert marker.actor == "fixture-reviewer"


def test_formal_content_survives_authoring_workspace_removal(tmp_path: Path) -> None:
    """A published release must not become unreadable with its workspace."""

    authoring, dataset, candidate, _, formal, _ = _workflow(tmp_path)
    _approve(authoring, dataset, candidate)
    release = formal.freeze(
        dataset.authoring_dataset_id,
        release_version="1.0.0",
        case_ids=(_case_id(formal, candidate),),
        actor="release-manager",
    )
    before = formal.content(release.release_id)
    assert formal.releases.payload_snapshots(release.release_id)["release_id"] == release.release_id

    shutil.rmtree(authoring.store.workspace(dataset.authoring_dataset_id))

    after = formal.content(release.release_id)
    assert after == before


def test_removing_published_release_hides_catalog_entry_without_mutating_history(
    tmp_path: Path,
) -> None:
    authoring, dataset, candidate, _, formal, _ = _workflow(tmp_path)
    _approve(authoring, dataset, candidate)
    release = formal.freeze(
        dataset.authoring_dataset_id,
        release_version="1.0.0",
        case_ids=(_case_id(formal, candidate),),
        actor="release-manager",
    )

    removed = formal.remove_from_catalog(release.release_id, actor="fixture-user")

    assert removed.release_id == release.release_id
    assert formal.releases.is_removed(release.release_id)
    assert formal.releases.list() == []
    assert formal.releases.get(release.release_id) == release
    assert formal.rebuild(release.release_id).reproducible
