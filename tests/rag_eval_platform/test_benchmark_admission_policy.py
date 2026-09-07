from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_eval.authoring.ledger import LifecycleState
from rag_eval.authoring.models import AnswerEvidenceCandidate, CandidateEvidence, DiscoveryMethod
from rag_eval.authoring.service import AuthoringService
from rag_eval.datasets.admission import (
    BenchmarkAdmissionService,
    CalibrationBaseline,
    CalibrationReferenceLock,
    CanonicalEvidenceScope,
    DocumentSourceRecord,
    DocumentType,
    PolicyResult,
    SimilarityDisposition,
    SourceAdmissionStatus,
    SourceFamilyClass,
    SourceFamilyRecord,
    SourceSimilarityAssessment,
    CaseAdmissionInput,
    MsesNecessityCheck,
    QuestionSimilarityAssessment,
    AdmissionChecklistAttestation,
)
from rag_eval.datasets.formal import FormalDatasetValidator
from rag_eval.datasets.portfolio import (
    BenchmarkPortfolioService,
    EvidenceRequirement,
    PortfolioUsage,
    SourceFamily,
    PortfolioLinks,
    PortfolioSlotState,
)
from rag_eval.contracts.canonical import RepresentationStatus
from tests.rag_eval_platform.test_authoring import mini_docx


SHA = "a" * 64


def _policy(tmp_path: Path) -> tuple[BenchmarkPortfolioService, BenchmarkAdmissionService]:
    portfolios = BenchmarkPortfolioService(
        tmp_path / "portfolios", source_root=BenchmarkPortfolioService.default_source_root()
    )
    portfolios.bootstrap_v0_dry_run()
    portfolios.bootstrap_v0_held_out()
    policy = BenchmarkAdmissionService(tmp_path / "admission", portfolios=portfolios)
    policy.bootstrap()
    return portfolios, policy


def _family() -> SourceFamilyRecord:
    return SourceFamilyRecord.build(
        source_family_id="heldout-family-a",
        classification=SourceFamilyClass.HELD_OUT,
        content_boundary="documents independently selected for the held-out family",
        owner="source-steward",
    )


def _source(*, disposition: SimilarityDisposition = SimilarityDisposition.DISTINCT, complete: bool = True) -> DocumentSourceRecord:
    return DocumentSourceRecord.build(
        source_document_id="heldout-document-a",
        source_family_id="heldout-family-a",
        revision=1,
        parent_revision_id=None,
        document_type="docx",
        content_summary="independent held-out source candidate",
        file_digest=SHA,
        canonical_document_digest="b" * 64,
        parser_identity="docx-parser/1",
        canonicalizer_identity="canonicalizer/1",
        parser_configuration_digest="c" * 64,
        parsing_completeness=RepresentationStatus.COMPLETE if complete else RepresentationStatus.PARTIAL,
        structure_completeness=RepresentationStatus.COMPLETE,
        evidence_locator_completeness=RepresentationStatus.COMPLETE,
        development_similarity=(
            SourceSimilarityAssessment(
                compared_document_id="development-document-a",
                compared_source_family_id="development-family-a",
                disposition=disposition,
                similarity_score=None if disposition == SimilarityDisposition.UNDETERMINED else 0.01,
                comparison_method="source-similarity-v1",
                comparison_corpus_digest="d" * 64,
            ),
        ),
        independent_test_eligible=True,
        admission_status=SourceAdmissionStatus.ADMITTED,
        actor="source-steward",
        reason="fixture source admission",
    )


def test_independent_portfolio_preserves_v0_matrix_but_is_separate_from_development(tmp_path: Path) -> None:
    portfolios, _ = _policy(tmp_path)
    development = portfolios.store.get("benchmark-v0-dry-run-48")
    held_out = portfolios.store.get("benchmark-v0-held-out-96")

    assert len(development.slots) == 48
    assert len(held_out.slots) == 96
    assert all(slot.usage == PortfolioUsage.DEVELOPMENT for slot in development.slots)
    assert all(slot.usage == PortfolioUsage.HELD_OUT for slot in held_out.slots)
    assert all(slot.source_family == SourceFamily.HELD_OUT_ISOLATED_PENDING_ADMISSION for slot in held_out.slots)
    assert sum(slot.language.value == "en" for slot in held_out.slots) == 72
    assert sum(slot.language.value == "zh" for slot in held_out.slots) == 24
    assert {source.value: sum(slot.source_type == source for slot in held_out.slots) for source in set(slot.source_type for slot in held_out.slots)} == {
        "human": 36,
        "semi_synthetic": 28,
        "synthetic": 16,
        "adversarial": 16,
    }
    with pytest.raises(Exception, match="isolated source-family"):
        portfolios.transition_slot(
            held_out.portfolio_id,
            slot_id="HOLDOUT-01-slot-01",
            state=PortfolioSlotState.AUTHORED,
            links=PortfolioLinks(dataset_id="dataset", case_revision_id="case-revision-1"),
            actor="author",
            reason="must bind source admission first",
        )


def test_source_admission_fails_closed_for_parse_failure_overlap_and_unknown_similarity(tmp_path: Path) -> None:
    _, policy = _policy(tmp_path)
    family = _family()
    policy.store.put_family(family)
    source_record = _source()
    assert policy.record_source(source_record) == source_record

    valid = policy.validate_source(_source(), family, development_family_ids=("development-family-a",))
    assert not valid.has_errors
    assert not valid.requires_human_review
    assert valid.eligible_to_proceed
    assert (tmp_path / "admission" / "reports" / "source" / f"{valid.report_digest}.json").is_file()

    parse_failure = policy.validate_source(_source(complete=False), family, development_family_ids=("development-family-a",))
    assert parse_failure.has_errors
    assert any(item.rule_id == "source.parse_structure_locator" and item.result == PolicyResult.FAIL for item in parse_failure.findings)

    overlap = policy.validate_source(_source(disposition=SimilarityDisposition.NEAR_DUPLICATE), family, development_family_ids=("development-family-a",))
    assert overlap.has_errors
    assert any(item.rule_id == "source.family_isolation_and_similarity" and item.result == PolicyResult.FAIL for item in overlap.findings)

    unknown = policy.validate_source(_source(disposition=SimilarityDisposition.UNDETERMINED), family, development_family_ids=("development-family-a",))
    assert not unknown.has_errors
    assert unknown.requires_human_review
    assert not unknown.eligible_to_proceed


def test_fixed_calibration_process_requires_a_complete_immutable_harness_lock(tmp_path: Path) -> None:
    _, policy = _policy(tmp_path)
    process = policy.bootstrap()
    assert process.fixed_seeds == (20260824, 20260825, 20260826)
    assert process.baselines == (
        CalibrationBaseline.BM25,
        CalibrationBaseline.DENSE,
        CalibrationBaseline.NO_RETRIEVAL,
        CalibrationBaseline.ORACLE_EVIDENCE,
    )
    lock = CalibrationReferenceLock.build(
        reference_harness_id="reference-harness-v1",
        harness_revision="rev-1",
        harness_digest=SHA,
        tokenizer_or_preprocessing_digest="b" * 64,
        baseline_configuration_digests=tuple((item, "c" * 64) for item in process.baselines),
        prompt_digests=(
            (CalibrationBaseline.NO_RETRIEVAL, "d" * 64),
            (CalibrationBaseline.ORACLE_EVIDENCE, "e" * 64),
        ),
        actor="calibration-owner",
    )
    assert policy.store.put_lock(lock) == lock
    with pytest.raises((ValidationError, KeyError)):
        CalibrationReferenceLock.build(
            reference_harness_id="incomplete",
            harness_revision="rev-1",
            harness_digest=SHA,
            tokenizer_or_preprocessing_digest="b" * 64,
            baseline_configuration_digests=((CalibrationBaseline.BM25, "c" * 64),),
            prompt_digests=((CalibrationBaseline.NO_RETRIEVAL, "d" * 64),),
            actor="calibration-owner",
        )


def test_case_admission_requires_evidence_minimality_human_review_and_contamination_check(tmp_path: Path) -> None:
    portfolios, policy = _policy(tmp_path)
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
    ledger = authoring.workflow.ledger
    case_id = ledger.case_id_for_candidate(candidate.candidate_id)
    case = ledger.current_case(dataset.authoring_dataset_id, case_id)
    gold = ledger.current_gold_for_case(dataset.authoring_dataset_id, case_id)
    canonical = FormalDatasetValidator()._load_canonical_document(dataset, authoring.store)
    source = DocumentSourceRecord.build(
        source_document_id="heldout-document-real",
        source_family_id="heldout-family-a",
        revision=1,
        parent_revision_id=None,
        document_type="docx",
        content_summary="fixture document mapped to canonical source",
        file_digest=dataset.source.sha256,
        canonical_document_digest=canonical.manifest.canonical_digest,
        parser_identity=canonical.manifest.parser_identity,
        canonicalizer_identity=canonical.manifest.canonicalizer_identity,
        parser_configuration_digest=canonical.manifest.configuration_digest,
        parsing_completeness=RepresentationStatus.COMPLETE,
        structure_completeness=RepresentationStatus.COMPLETE,
        evidence_locator_completeness=RepresentationStatus.COMPLETE,
        development_similarity=(
            SourceSimilarityAssessment(
                compared_document_id="development-document-a",
                compared_source_family_id="development-family-a",
                disposition=SimilarityDisposition.DISTINCT,
                similarity_score=0.01,
                comparison_method="source-similarity-v1",
                comparison_corpus_digest="d" * 64,
            ),
        ),
        independent_test_eligible=True,
        admission_status=SourceAdmissionStatus.ADMITTED,
        actor="source-steward",
        reason="fixture only",
    )
    checks = tuple(
        MsesNecessityCheck(
            path_id=path.path_id,
            clause_id=clause.clause_id,
            alternative_evidence_ids=clause.alternatives,
            necessary=True,
            method="removal-test-v1",
            verifier_identity="evidence-reviewer",
        )
        for path in gold.payload.mses_paths
        for clause in path.clauses
    )
    input_value = CaseAdmissionInput(
        portfolio_id="benchmark-v0-held-out-96",
        slot_id="HOLDOUT-01-slot-01",
        source=source,
        source_admission_report=policy.validate_source(
            source, _family(), development_family_ids=("development-family-a",)
        ),
        case=case,
        gold=gold,
        canonical=canonical,
        necessity_checks=checks,
        question_similarity=(
            QuestionSimilarityAssessment(
                compared_case_id="development-case-a",
                compared_usage=PortfolioUsage.DEVELOPMENT,
                disposition=SimilarityDisposition.DISTINCT,
                similarity_score=0.02,
                method="question-similarity-v1",
            ),
        ),
    )
    pending = policy.validate_case(input_value)
    assert not pending.has_errors
    assert pending.requires_human_review
    assert not pending.eligible_to_proceed

    attestation = AdmissionChecklistAttestation(
        ledger_review_id="review-policy-fixture",
        reviewed_case_revision_id=case.case_revision_id,
        reviewed_gold_revision_id=gold.gold_revision_id,
        reviewer_identity="independent-reviewer",
        question_natural=True,
        ambiguity_checked=True,
        answer_correct=True,
        evidence_sufficient=True,
        evidence_minimal=True,
        alternative_answers_checked=True,
        difficulty_label_reasonable=True,
        approved=True,
    )
    approved = policy.validate_case(input_value.model_copy(update={"review_attestations": (attestation,)}))
    assert approved.eligible_to_proceed

    # The actual Ledger review applies to the proposed parent revisions; the
    # policy must accept that honest lineage reference after approval appends
    # immutable successor revisions.
    proposed_case = ledger.case_history(dataset.authoring_dataset_id, case.case_id)[1]
    proposed_gold = ledger.gold_history(dataset.authoring_dataset_id, gold.gold_id)[1]
    lineage_attestation = attestation.model_copy(
        update={
            "reviewed_case_revision_id": proposed_case.case_revision_id,
            "reviewed_gold_revision_id": proposed_gold.gold_revision_id,
            "case_id": case.case_id,
            "gold_id": gold.gold_id,
        }
    )
    assert policy.validate_case(
        input_value.model_copy(update={"review_attestations": (lineage_attestation,)})
    ).eligible_to_proceed

    scoped_development_source = DocumentSourceRecord.build(
        source_document_id="development-document-scoped",
        source_family_id="development-family-a",
        revision=1,
        parent_revision_id=None,
        document_type=DocumentType.DOCX,
        content_summary="partially represented DOCX with an explicitly selected complete evidence subset",
        file_digest=dataset.source.sha256,
        canonical_document_digest=canonical.manifest.canonical_digest,
        parser_identity=canonical.manifest.parser_identity,
        canonicalizer_identity=canonical.manifest.canonicalizer_identity,
        parser_configuration_digest=canonical.manifest.configuration_digest,
        parsing_completeness=RepresentationStatus.PARTIAL,
        structure_completeness=RepresentationStatus.PARTIAL,
        evidence_locator_completeness=RepresentationStatus.COMPLETE,
        independent_test_eligible=False,
        admission_status=SourceAdmissionStatus.CANDIDATE,
        actor="source-steward",
        reason="whole document remains partial; pilot uses only complete Canonical evidence",
    )
    scope = CanonicalEvidenceScope.build(
        scope_id="scope-development-complete",
        source_document_id=scoped_development_source.source_document_id,
        canonical_document_digest=canonical.manifest.canonical_digest,
        canonical_object_ids=tuple(
            sorted(
                {
                    *case.draft.source_object_ids,
                    *(item.canonical_object_id for item in gold.payload.evidence),
                }
            )
        ),
        actor="source-steward",
        reason="bind the development Case to complete source locators only",
    )
    scoped = policy.validate_case(
        input_value.model_copy(
            update={
                "portfolio_id": "benchmark-v0-dry-run-48",
                "slot_id": "DRY-01-slot-01",
                "source": scoped_development_source,
                "source_admission_report": None,
                "evidence_scope": scope,
                "review_attestations": (lineage_attestation,),
            }
        )
    )
    assert scoped.eligible_to_proceed
    assert any(
        item.rule_id == "case.reliable_canonical_evidence_scope"
        and item.result == PolicyResult.PASS
        for item in scoped.findings
    )

    contaminated = policy.validate_case(
        input_value.model_copy(
            update={
                "review_attestations": (attestation,),
                "question_similarity": (
                    QuestionSimilarityAssessment(
                        compared_case_id="development-case-a",
                        compared_usage=PortfolioUsage.DEVELOPMENT,
                        disposition=SimilarityDisposition.NEAR_DUPLICATE,
                        similarity_score=0.99,
                        method="question-similarity-v1",
                    ),
                ),
            }
        )
    )
    assert contaminated.has_errors
    assert any(item.rule_id == "case.duplicate_and_contamination" and item.result == PolicyResult.FAIL for item in contaminated.findings)

    multi_hop_slot = next(
        item
        for item in portfolios.store.get("benchmark-v0-held-out-96").slots
        if item.evidence_requirement == EvidenceRequirement.MULTI_HOP
    )
    missing_dependency = policy.validate_case(
        input_value.model_copy(
            update={
                "slot_id": multi_hop_slot.slot_id,
                "review_attestations": (attestation,),
            }
        )
    )
    assert missing_dependency.has_errors
    assert any(item.rule_id == "gold.multi_hop_dependency" and item.result == PolicyResult.FAIL for item in missing_dependency.findings)

    leaky_case = case.model_copy(
        update={"draft": case.draft.model_copy(update={"question": "42 ms 对应的延迟指标是什么？"})}
    )
    leakage = policy.validate_case(
        input_value.model_copy(
            update={"case": leaky_case, "review_attestations": (attestation,)}
        )
    )
    assert leakage.has_errors
    assert any(item.rule_id == "case.answer_leakage" and item.result == PolicyResult.FAIL for item in leakage.findings)
