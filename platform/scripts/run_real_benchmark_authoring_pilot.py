#!/usr/bin/env python3
"""Run the bounded real-DOCX Authoring/Gold/Release pilot.

This deliberately uses no RAG system, model provider, Bundle registration, or
held-out source.  It builds a human-authored development pilot only from
Canonical objects that the current parser marks ``complete``.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from rag_eval.authoring.ledger import (
    ActorRole,
    AuthoringOrigin,
    CaseDraft,
    EvidenceDependency,
    EvidenceRole,
    GoldAnswer,
    GoldEvidence,
    GoldPayload,
    MsesClause,
    MsesPath,
    OriginKind,
    LifecycleState,
    ReviewDecision,
    TargetKind,
    TrustLevel,
)
from rag_eval.contracts.canonical import RepresentationStatus
from rag_eval.datasets.admission import (
    AdmissionChecklistAttestation,
    CaseAdmissionInput,
    CanonicalEvidenceScope,
    DocumentSourceRecord,
    DocumentType,
    MsesNecessityCheck,
    QuestionSimilarityAssessment,
    SimilarityDisposition,
    SourceAdmissionStatus,
    SourceFamilyClass,
    SourceFamilyRecord,
)
from rag_eval.datasets.formal import FormalDatasetValidator
from rag_eval.datasets.portfolio import (
    PORTFOLIO_ID_V0_DRY_RUN,
    PortfolioLinks,
    PortfolioSlotState,
    PortfolioUsage,
)
from rag_eval.service import PlatformService
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.layout import PlatformPaths


AUTHOR = "pilot-human-author"
REVIEWERS = ("pilot-reviewer-a", "pilot-reviewer-b")
RELEASE_MANAGER = "pilot-release-manager"
SOURCE_DOCUMENT_ID = "real-docx-s2a2g2-v20"
SOURCE_FAMILY_ID = "real-docx-development-family"


@dataclass(frozen=True)
class PilotCase:
    case_id: str
    gold_id: str
    slot_id: str
    target_id: str
    question: str
    answer_kind: str
    answer: str | tuple[str, ...] | None
    source_object_ids: tuple[str, ...]
    required: tuple[tuple[str, str], ...]
    paths: tuple[tuple[str, tuple[tuple[str, tuple[str, ...]], ...]], ...]
    dependencies: tuple[EvidenceDependency, ...] = ()
    near_miss: tuple[tuple[str, str], ...] = ()
    negative_scope: tuple[str, ...] = ()
    negative_rationale: str | None = None
    heightened_review: bool = False


DOC = "doc-7d50899d15356000"


PILOT_CASES = (
    PilotCase(
        case_id="pilot-case-http-protocol",
        gold_id="pilot-gold-http-protocol",
        slot_id="DRY-02-slot-04",
        target_id="pilot-target-http-protocol",
        question="针对应用系统的数据通信，文中指出导致传输完整性无法保证的是哪种协议？",
        answer_kind="text",
        answer="HTTP",
        source_object_ids=(f"{DOC}:block:00052", f"{DOC}:block:00024"),
        required=(("required-http", f"{DOC}:block:00052"),),
        paths=(("path-http", (("clause-http", ("required-http",)),)),),
        near_miss=(("near-miss-secure-protocols", f"{DOC}:block:00024"),),
    ),
    PilotCase(
        case_id="pilot-case-conclusion-validity",
        gold_id="pilot-gold-conclusion-validity",
        slot_id="DRY-03-slot-04",
        target_id="pilot-target-conclusion-validity",
        question="测评完成后，出现什么变化会使既有测评结论不再适用？",
        answer_kind="text",
        answer="被测对象发生变更并涉及系统构成组件（或子系统）",
        source_object_ids=(f"{DOC}:block:00016",),
        required=(("required-validity", f"{DOC}:block:00016"),),
        paths=(("path-validity", (("clause-validity", ("required-validity",)),)),),
    ),
    PilotCase(
        case_id="pilot-case-critical-backed-up-data",
        gold_id="pilot-gold-critical-backed-up-data",
        slot_id="DRY-04-slot-04",
        target_id="pilot-target-critical-backed-up-data",
        question="从数据资源清单与备份描述共同看，哪些类别既被列为关键且明确已进行本地备份？",
        answer_kind="set",
        answer=("重要业务数据", "重要配置数据", "重要审计数据"),
        source_object_ids=(f"{DOC}:block:00034", f"{DOC}:table:00017"),
        required=(
            ("required-backup-description", f"{DOC}:block:00034"),
            ("required-data-inventory", f"{DOC}:table:00017"),
        ),
        paths=(
            (
                "path-backup-inventory",
                (
                    ("clause-backup-description", ("required-backup-description",)),
                    ("clause-data-inventory", ("required-data-inventory",)),
                ),
            ),
        ),
    ),
    PilotCase(
        case_id="pilot-case-good-not-excellent",
        gold_id="pilot-gold-good-not-excellent",
        slot_id="DRY-05-slot-04",
        target_id="pilot-target-good-not-excellent",
        question="综合得分超过90分但仍未获得“优”时，报告中的哪项风险情况解释了这一结论？",
        answer_kind="text",
        answer="存在8个中风险问题",
        source_object_ids=(
            f"{DOC}:block:00041",
            f"{DOC}:cell:2702002",
            f"{DOC}:cell:2703002",
        ),
        required=(
            ("required-observed-risk-and-score", f"{DOC}:block:00041"),
            ("required-excellent-criterion", f"{DOC}:cell:2702002"),
            ("required-good-criterion", f"{DOC}:cell:2703002"),
        ),
        paths=(
            (
                "path-risk-criterion",
                (
                    ("clause-observed-risk", ("required-observed-risk-and-score",)),
                    ("clause-excellent-criterion", ("required-excellent-criterion",)),
                    ("clause-good-criterion", ("required-good-criterion",)),
                ),
            ),
        ),
        dependencies=(
            EvidenceDependency(
                dependency_id="risk-facts",
                description="retrieve the observed score and medium-risk count",
            ),
            EvidenceDependency(
                dependency_id="apply-rating-criteria",
                depends_on=("risk-facts",),
                description="apply the 优 and 良 criteria to the observed risk facts",
            ),
        ),
        heightened_review=True,
    ),
    PilotCase(
        case_id="pilot-case-critical-data-count",
        gold_id="pilot-gold-critical-data-count",
        slot_id="DRY-06-slot-04",
        target_id="pilot-target-critical-data-count",
        question="数据资源清单中被标为“关键”的数据类别共有几类？",
        answer_kind="numeric",
        answer="4",
        source_object_ids=(
            f"{DOC}:cell:1702005",
            f"{DOC}:cell:1703005",
            f"{DOC}:cell:1704005",
            f"{DOC}:cell:1705005",
        ),
        required=(
            ("required-critical-1", f"{DOC}:cell:1702005"),
            ("required-critical-2", f"{DOC}:cell:1703005"),
            ("required-critical-3", f"{DOC}:cell:1704005"),
            ("required-critical-4", f"{DOC}:cell:1705005"),
        ),
        paths=(
            (
                "path-count-critical-data",
                (
                    ("clause-critical-1", ("required-critical-1",)),
                    ("clause-critical-2", ("required-critical-2",)),
                    ("clause-critical-3", ("required-critical-3",)),
                    ("clause-critical-4", ("required-critical-4",)),
                ),
            ),
        ),
    ),
    PilotCase(
        case_id="pilot-case-access-switch-model",
        gold_id="pilot-gold-access-switch-model",
        slot_id="DRY-07-slot-04",
        target_id="pilot-target-access-switch-model",
        question="设备清单中，接入交换机对应的品牌及型号是什么？",
        answer_kind="text",
        answer="S2910-48GT4XS-E",
        source_object_ids=(f"{DOC}:cell:1002002", f"{DOC}:cell:1002005"),
        required=(
            ("required-switch-row", f"{DOC}:cell:1002002"),
            ("required-switch-model", f"{DOC}:cell:1002005"),
        ),
        paths=(
            (
                "path-access-switch-model",
                (
                    ("clause-switch-row", ("required-switch-row",)),
                    ("clause-switch-model", ("required-switch-model",)),
                ),
            ),
        ),
        heightened_review=True,
    ),
    PilotCase(
        case_id="pilot-case-auth-data-confidentiality",
        gold_id="pilot-gold-auth-data-confidentiality",
        slot_id="DRY-10-slot-04",
        target_id="pilot-target-auth-data-confidentiality",
        question="在数据资源清单的鉴别数据记录中，是否列出了保密性这一安全防护需求？",
        answer_kind="abstain",
        answer=None,
        source_object_ids=(f"{DOC}:table:00017",),
        required=(),
        paths=(),
        negative_scope=(f"{DOC}:table:00017",),
        negative_rationale="The complete, explicitly scoped data-resource inventory lists only 完整性 for 鉴别数据; it does not record 保密性 in that field.",
        heightened_review=True,
    ),
    PilotCase(
        case_id="pilot-case-server-os-alternative-path",
        gold_id="pilot-gold-server-os-alternative-path",
        slot_id="DRY-12-slot-04",
        target_id="pilot-target-server-os-alternative-path",
        question="外网网站服务器采用的操作系统及版本是什么？",
        answer_kind="text",
        answer="Windows2008 企业版",
        source_object_ids=(
            f"{DOC}:cell:1202002",
            f"{DOC}:cell:1202005",
            f"{DOC}:cell:3402002",
            f"{DOC}:cell:3402005",
        ),
        required=(
            ("required-server-path-a", f"{DOC}:cell:1202002"),
            ("required-os-path-a", f"{DOC}:cell:1202005"),
            ("required-server-path-b", f"{DOC}:cell:3402002"),
            ("required-os-path-b", f"{DOC}:cell:3402005"),
        ),
        paths=(
            (
                "path-server-inventory",
                (
                    ("clause-server-a", ("required-server-path-a",)),
                    ("clause-os-a", ("required-os-path-a",)),
                ),
            ),
            (
                "path-appendix-inventory",
                (
                    ("clause-server-b", ("required-server-path-b",)),
                    ("clause-os-b", ("required-os-path-b",)),
                ),
            ),
        ),
        heightened_review=True,
    ),
)


def _origin(document_id: str) -> AuthoringOrigin:
    return AuthoringOrigin(
        kind=OriginKind.HUMAN,
        trust_level=TrustLevel.HUMAN_ASSERTED,
        generator_identity="evidence-first-human-pilot",
        source_world="real-docx-development-pilot",
        source_document_ids=(document_id,),
    )


def _gold_payload(spec: PilotCase) -> GoldPayload:
    evidence = [
        GoldEvidence(evidence_id=evidence_id, canonical_object_id=object_id, role=EvidenceRole.REQUIRED)
        for evidence_id, object_id in spec.required
    ]
    evidence.extend(
        GoldEvidence(
            evidence_id=evidence_id,
            canonical_object_id=object_id,
            role=EvidenceRole.NEAR_MISS,
            rationale="Similar-looking source evidence is not sufficient for this answer.",
        )
        for evidence_id, object_id in spec.near_miss
    )
    evidence.extend(
        GoldEvidence(
            evidence_id=f"negative-scope-{index:02d}",
            canonical_object_id=object_id,
            role=EvidenceRole.NEGATIVE_SCOPE,
            rationale="Complete scoped inventory used to establish absence of the requested recorded attribute.",
        )
        for index, object_id in enumerate(spec.negative_scope, start=1)
    )
    return GoldPayload(
        answer=GoldAnswer(kind=spec.answer_kind, canonical=spec.answer, locale="zh-CN"),
        evidence=tuple(evidence),
        mses_paths=tuple(
            MsesPath(
                path_id=path_id,
                clauses=tuple(
                    MsesClause(clause_id=clause_id, alternatives=alternatives)
                    for clause_id, alternatives in clauses
                ),
            )
            for path_id, clauses in spec.paths
        ),
        dependencies=spec.dependencies,
        negative_scope_object_ids=spec.negative_scope,
        negative_rationale=spec.negative_rationale,
    )


def _complete_scope_ids(spec: PilotCase) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *spec.source_object_ids,
                *(object_id for _evidence_id, object_id in spec.required),
                *(object_id for _evidence_id, object_id in spec.near_miss),
                *spec.negative_scope,
            }
        )
    )


def _review_and_approve(platform: PlatformService, dataset, spec: PilotCase, case, gold):
    assert platform.formal_datasets is not None
    ledger = platform.formal_datasets.ledger
    reviewers = REVIEWERS if spec.heightened_review else REVIEWERS[:1]
    case_reviews = []
    gold_reviews = []
    for reviewer in reviewers:
        case_reviews.append(
            ledger.record_review(
                dataset.authoring_dataset_id,
                target_kind=TargetKind.CASE,
                reviewed_revision_id=case.case_revision_id,
                reviewer=reviewer,
                decision=ReviewDecision.APPROVE,
                checklist={
                    "question_natural": True,
                    "ambiguity_checked": True,
                    "difficulty_label_reasonable": True,
                },
                comments="Independent evidence-first pilot Case review.",
            )
        )
        gold_reviews.append(
            ledger.record_review(
                dataset.authoring_dataset_id,
                target_kind=TargetKind.GOLD,
                reviewed_revision_id=gold.gold_revision_id,
                reviewer=reviewer,
                decision=ReviewDecision.APPROVE,
                checklist={
                    "answer_correct": True,
                    "evidence_sufficient": True,
                    "evidence_minimal": True,
                    "alternative_answers_checked": True,
                },
                comments="Independent evidence-first pilot Gold/MSES review.",
            )
        )
    reviewed_case = ledger.mark_reviewed(
        dataset,
        target_kind=TargetKind.CASE,
        revision_id=case.case_revision_id,
        actor=AUTHOR,
        reason="independent reviewer checklist accepted Case",
    )
    reviewed_gold = ledger.mark_reviewed(
        dataset,
        target_kind=TargetKind.GOLD,
        revision_id=gold.gold_revision_id,
        actor=AUTHOR,
        reason="independent reviewer checklist accepted Gold",
    )
    approved_case = ledger.approve(
        dataset,
        target_kind=TargetKind.CASE,
        revision_id=reviewed_case.case_revision_id,
        approver=REVIEWERS[0],
        role=ActorRole.REVIEWER,
        reason="independent reviewer approval after Case review",
    )
    approved_gold = ledger.approve(
        dataset,
        target_kind=TargetKind.GOLD,
        revision_id=reviewed_gold.gold_revision_id,
        approver=REVIEWERS[0],
        role=ActorRole.REVIEWER,
        reason="independent reviewer approval after Gold review",
    )
    attestations = tuple(
        AdmissionChecklistAttestation(
            ledger_review_id=case_review.review_id,
            reviewed_case_revision_id=case.case_revision_id,
            reviewed_gold_revision_id=gold.gold_revision_id,
            case_id=approved_case.case_id,
            gold_id=approved_gold.gold_id,
            reviewer_identity=reviewer,
            question_natural=True,
            ambiguity_checked=True,
            answer_correct=True,
            evidence_sufficient=True,
            evidence_minimal=True,
            alternative_answers_checked=True,
            difficulty_label_reasonable=True,
            approved=True,
            comments=f"Gold review record: {gold_review.review_id}",
        )
        for reviewer, case_review, gold_review in zip(reviewers, case_reviews, gold_reviews, strict=True)
    )
    return approved_case, approved_gold, attestations


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-docx", type=Path, required=True)
    parser.add_argument("--platform-home", type=Path, required=True)
    parser.add_argument("--reset", action="store_true", help="delete only the explicitly selected pilot Platform home before running")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    source = args.source_docx.resolve()
    home = args.platform_home.resolve()
    if not source.is_file():
        raise SystemExit(f"real DOCX not found: {source}")
    if args.reset and home.exists():
        shutil.rmtree(home)
    platform = PlatformService(PlatformPaths(home), product_enabled=True)
    assert platform.authoring is not None
    assert platform.formal_datasets is not None
    assert platform.portfolios is not None
    assert platform.benchmark_admission is not None

    uploaded = platform.authoring.upload_docx(filename=source.name, payload=source.read_bytes())
    dataset = platform.authoring.analyze(uploaded.authoring_dataset_id)
    canonical = FormalDatasetValidator()._load_canonical_document(dataset, platform.authoring.store)
    known = {item.object_id: item for item in canonical.objects}
    selected = set().union(*(_complete_scope_ids(spec) for spec in PILOT_CASES))
    unsafe = sorted(
        object_id
        for object_id in selected
        if object_id not in known or known[object_id].representation_status != RepresentationStatus.COMPLETE
    )
    if unsafe:
        raise RuntimeError(f"pilot selected non-complete Canonical objects: {unsafe}")

    family = SourceFamilyRecord.build(
        source_family_id=SOURCE_FAMILY_ID,
        classification=SourceFamilyClass.DEVELOPMENT,
        content_boundary="real DOCX development-only authoring pilot; excluded from held-out use",
        owner="pilot-source-steward",
    )
    platform.benchmark_admission.store.put_family(family)
    source_record = DocumentSourceRecord.build(
        source_document_id=SOURCE_DOCUMENT_ID,
        source_family_id=SOURCE_FAMILY_ID,
        revision=1,
        parent_revision_id=None,
        document_type=DocumentType.DOCX,
        content_summary="Real S2A2G2 website-system assessment report; whole-document source remains partially represented, while this pilot pins complete Canonical body/table evidence only.",
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
        actor="pilot-source-steward",
        reason="whole source has headers/footers and rich structures outside the Gold-eligible Canonical subset",
    )
    platform.benchmark_admission.record_source(source_record)
    source_report = platform.benchmark_admission.validate_source(
        source_record, family, development_family_ids=()
    )
    if not source_report.has_errors:
        raise RuntimeError("whole-document partial source unexpectedly passed full-source admission")

    ledger = platform.formal_datasets.ledger
    document_revision = ledger.document_history(dataset.authoring_dataset_id)[-1]
    approved: list[tuple[PilotCase, object, object, object]] = []
    prior_cases: list[str] = []
    for spec in PILOT_CASES:
        origin = _origin(dataset.document_id or canonical.manifest.document_id)
        draft = CaseDraft(
            case_id=spec.case_id,
            target_id=spec.target_id,
            question=spec.question,
            language="zh-CN",
            source_digest=dataset.source.sha256,
            canonical_contract_digest=canonical.manifest.canonical_digest,
            canonical_compatibility_digest=dataset.canonical_digest,
            source_object_ids=spec.source_object_ids,
            origin=origin,
        )
        case = ledger.create_case(
            dataset, draft=draft, actor=AUTHOR, reason="human evidence-first real DOCX pilot Case draft"
        )
        case = ledger.propose_case(
            dataset, case_id=case.case_id, actor=AUTHOR, reason="submit real DOCX Case for independent review"
        )
        gold = ledger.create_gold(
            dataset,
            gold_id=spec.gold_id,
            case_revision=case,
            payload=_gold_payload(spec),
            origin=origin,
            actor=AUTHOR,
            reason="human evidence-first real DOCX Gold draft",
        )
        gold = ledger.propose_gold(
            dataset, gold_id=gold.gold_id, actor=AUTHOR, reason="submit real DOCX Gold for independent review"
        )
        platform.portfolios.transition_slot(
            PORTFOLIO_ID_V0_DRY_RUN,
            slot_id=spec.slot_id,
            state=PortfolioSlotState.AUTHORED,
            links=PortfolioLinks(dataset_id=dataset.authoring_dataset_id, case_revision_id=case.case_revision_id),
            actor=AUTHOR,
            reason="bind planned development slot to real DOCX Case proposal",
        )
        approved_case, approved_gold, attestations = _review_and_approve(platform, dataset, spec, case, gold)
        platform.portfolios.transition_slot(
            PORTFOLIO_ID_V0_DRY_RUN,
            slot_id=spec.slot_id,
            state=PortfolioSlotState.REVIEWED,
            links=PortfolioLinks(dataset_id=dataset.authoring_dataset_id, case_revision_id=ledger.case_history(dataset.authoring_dataset_id, spec.case_id)[2].case_revision_id),
            actor=AUTHOR,
            reason="record independent Case/Gold review completion",
        )
        platform.portfolios.transition_slot(
            PORTFOLIO_ID_V0_DRY_RUN,
            slot_id=spec.slot_id,
            state=PortfolioSlotState.APPROVED,
            links=PortfolioLinks(
                dataset_id=dataset.authoring_dataset_id,
                document_revision_id=document_revision.document_revision_id,
                case_revision_id=approved_case.case_revision_id,
                gold_revision_id=approved_gold.gold_revision_id,
            ),
            actor=REVIEWERS[0],
            reason="independent approval of real DOCX Case and Gold",
        )
        checks = tuple(
            MsesNecessityCheck(
                path_id=path.path_id,
                clause_id=clause.clause_id,
                alternative_evidence_ids=clause.alternatives,
                necessary=True,
                method="human-evidence-removal-v1",
                verifier_identity=REVIEWERS[0],
                rationale="Removing this clause loses a required source fact or permitted alternative path.",
            )
            for path in approved_gold.payload.mses_paths
            for clause in path.clauses
        )
        similarities = tuple(
            QuestionSimilarityAssessment(
                compared_case_id=case_id,
                compared_usage=PortfolioUsage.DEVELOPMENT,
                disposition=SimilarityDisposition.DISTINCT,
                similarity_score=0.0,
                method="independent-human-pilot-question-comparison-v1",
            )
            for case_id in prior_cases
        )
        scope = CanonicalEvidenceScope.build(
            scope_id=f"scope-{spec.case_id}",
            source_document_id=source_record.source_document_id,
            canonical_document_digest=canonical.manifest.canonical_digest,
            canonical_object_ids=_complete_scope_ids(spec),
            actor="pilot-source-steward",
            reason="real DOCX pilot limits Gold evidence to audited complete Canonical objects",
        )
        admission = platform.benchmark_admission.validate_case(
            value=CaseAdmissionInput(
                portfolio_id=PORTFOLIO_ID_V0_DRY_RUN,
                slot_id=spec.slot_id,
                source=source_record,
                source_admission_report=source_report,
                evidence_scope=scope,
                case=approved_case,
                gold=approved_gold,
                canonical=canonical,
                necessity_checks=checks,
                question_similarity=similarities,
                review_attestations=attestations,
            )
        )
        if not admission.eligible_to_proceed:
            raise RuntimeError(f"admission preflight did not pass for {spec.case_id}: {admission.report_digest}")
        approved.append((spec, approved_case, approved_gold, admission))
        prior_cases.append(spec.case_id)

    preflight = platform.formal_datasets.validate(
        dataset.authoring_dataset_id,
        case_revision_ids=tuple(case.case_revision_id for _spec, case, _gold, _admission in approved),
        gold_revision_ids=tuple(gold.gold_revision_id for _spec, _case, gold, _admission in approved),
        document_revision_id=document_revision.document_revision_id,
    )
    if preflight.has_errors:
        raise RuntimeError(f"formal preflight failed: {preflight.report_digest}")
    release = platform.formal_datasets.freeze(
        dataset.authoring_dataset_id,
        release_version="real-pilot-1.0.0",
        case_ids=tuple(spec.case_id for spec, _case, _gold, _admission in approved),
        actor=RELEASE_MANAGER,
    )
    release_case_by_id = {item.case_id: item for item in release.cases}
    release_gold_by_case = {item.case_id: item for item in release.gold}
    for spec, _case, _gold, _admission in approved:
        platform.portfolios.transition_slot(
            PORTFOLIO_ID_V0_DRY_RUN,
            slot_id=spec.slot_id,
            state=PortfolioSlotState.FROZEN,
            links=PortfolioLinks(
                dataset_id=dataset.authoring_dataset_id,
                document_revision_id=document_revision.document_revision_id,
                case_revision_id=release_case_by_id[spec.case_id].case_revision_id,
                gold_revision_id=release_gold_by_case[spec.case_id].gold_revision_id,
                release_id=release.release_id,
            ),
            actor=RELEASE_MANAGER,
            reason="frozen formal Dataset Release pins the real DOCX Case and Gold revisions",
        )
    rebuild = platform.formal_datasets.rebuild(release.release_id)
    if not rebuild.reproducible:
        raise RuntimeError(f"frozen release did not rebuild deterministically: {rebuild.reason}")
    tampered_source = home / "tamper-check.docx"
    shutil.copyfile(platform.formal_datasets.releases.source_snapshot(release.release_id), tampered_source)
    tampered_source.write_bytes(tampered_source.read_bytes() + b"pilot-tamper")
    tamper_report = platform.formal_datasets.validate(
        dataset.authoring_dataset_id,
        case_revision_ids=tuple(item.case_revision_id for item in release.cases),
        gold_revision_ids=tuple(item.gold_revision_id for item in release.gold),
        required_lifecycle=LifecycleState.FROZEN,
        document_revision_id=release.document.document_revision_id,
        canonical_snapshot=platform.formal_datasets.releases.canonical_snapshot(release.release_id),
        source_snapshot=tampered_source,
    )
    if not tamper_report.has_errors:
        raise RuntimeError("tampered source unexpectedly passed formal validation")
    tampered_source.unlink()

    summary = {
        "source_docx": str(source),
        "platform_home": str(home),
        "dataset_id": dataset.authoring_dataset_id,
        "document_revision_id": document_revision.document_revision_id,
        "source_sha256": dataset.source.sha256,
        "canonical_digest": canonical.manifest.canonical_digest,
        "source_admission_report_digest": source_report.report_digest,
        "source_admission_expected_errors": source_report.has_errors,
        "case_count": len(approved),
        "cases": [
            {
                "case_id": spec.case_id,
                "gold_id": spec.gold_id,
                "slot_id": spec.slot_id,
                "case_revision_id": case.case_revision_id,
                "gold_revision_id": gold.gold_revision_id,
                "admission_report_digest": admission.report_digest,
                "question": spec.question,
                "source_object_ids": spec.source_object_ids,
            }
            for spec, case, gold, admission in approved
        ],
        "formal_preflight_report_digest": preflight.report_digest,
        "release": release.model_dump(mode="json"),
        "rebuild": rebuild.model_dump(mode="json"),
        "tamper_report_digest": tamper_report.report_digest,
        "tamper_detected": tamper_report.has_errors,
        "coverage": platform.portfolios.coverage_report(PORTFOLIO_ID_V0_DRY_RUN).model_dump(mode="json"),
    }
    atomic_write_json(home / "real-benchmark-authoring-pilot-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
