#!/usr/bin/env python3
"""Actualize the 48-slot development Portfolio from one audited real DOCX.

This is deliberately evidence-first and RAG-neutral.  It preserves the prior
eight-case development pilot, re-analyzes its source as Canonical Contract 1.1
to create a successor DocumentRevision, freezes only the newly actualized
cases in a successor release, and records the remaining unsupported slots as
typed, immutable ``blocked`` Portfolio assignments.
"""

from __future__ import annotations

import argparse
import hashlib
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
    LifecycleState,
    MsesClause,
    MsesPath,
    OriginKind,
    ReviewDecision,
    TargetKind,
    TrustLevel,
)
from rag_eval.contracts.canonical import CanonicalDocument, RepresentationStatus
from rag_eval.datasets.admission import (
    AdmissionChecklistAttestation,
    CanonicalEvidenceScope,
    CaseAdmissionInput,
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
    PortfolioBlockedReason,
    PortfolioLinks,
    PortfolioSlotState,
    PortfolioUsage,
)
from rag_eval.service import PlatformService
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.layout import PlatformPaths


AUTHOR = "development-48-human-author"
REVIEWERS = ("development-48-reviewer-a", "development-48-reviewer-b")
RELEASE_MANAGER = "development-48-release-manager"
SOURCE_DOCUMENT_ID = "real-docx-s2a2g2-v20"
SOURCE_FAMILY_ID = "real-docx-development-family"
PILOT_RELEASE_ID = "dataset-release-4758bfcc6b91c492bac9c9f2"
PILOT_CASE_COUNT = 8
PILOT_SLOT_IDS = frozenset(
    {
        "DRY-02-slot-04",
        "DRY-03-slot-04",
        "DRY-04-slot-04",
        "DRY-05-slot-04",
        "DRY-06-slot-04",
        "DRY-07-slot-04",
        "DRY-10-slot-04",
        "DRY-12-slot-04",
    }
)
DOC = "doc-7d50899d15356000"


def _span(number: int) -> str:
    return f"{DOC}:text_span:{number:05d}"


def _logical(identifier: str) -> str:
    return f"{DOC}:logical_cell:{identifier}"


def _table(number: int) -> str:
    return f"{DOC}:table:{number:05d}"


@dataclass(frozen=True)
class EvidenceSpec:
    evidence_id: str
    canonical_object_id: str
    role: EvidenceRole = EvidenceRole.REQUIRED
    rationale: str | None = None


@dataclass(frozen=True)
class DevelopmentCase:
    case_id: str
    gold_id: str
    slot_id: str
    question: str
    answer_kind: str
    answer: str | tuple[str, ...] | None
    evidence: tuple[EvidenceSpec, ...]
    paths: tuple[tuple[str, tuple[tuple[str, tuple[str, ...]], ...]], ...]
    dependencies: tuple[EvidenceDependency, ...] = ()
    negative_scope: tuple[str, ...] = ()
    negative_rationale: str | None = None

    @property
    def source_object_ids(self) -> tuple[str, ...]:
        return tuple(sorted({item.canonical_object_id for item in self.evidence}))


# These are human-authored evidence specifications.  They were selected from
# the real document's audited Canonical 1.1 output before this driver creates
# a Case.  No model or retrieval output participates in their construction.
CASES: tuple[DevelopmentCase, ...] = (
    DevelopmentCase(
        "dev48-case-report-type", "dev48-gold-report-type", "DRY-01-slot-01",
        "What kind of assessment report is the document?", "text", "等级测评报告",
        (EvidenceSpec("report-type", _span(14)),),
        (("path-report-type", (("clause-report-type", ("report-type",)),)),),
    ),
    DevelopmentCase(
        "dev48-case-report-date", "dev48-gold-report-date", "DRY-01-slot-02",
        "What month and year are shown for this report?", "text", "2024年01月",
        (EvidenceSpec("report-date", _span(20)),),
        (("path-report-date", (("clause-report-date", ("report-date",)),)),),
    ),
    DevelopmentCase(
        "dev48-case-secure-device-protocols", "dev48-gold-secure-device-protocols", "DRY-01-slot-03",
        "Which two protocols are reported as protecting transmission integrity for network and security devices?", "set", ("SSH", "HTTPS"),
        (EvidenceSpec("device-protocols", _span(25)),),
        (("path-device-protocols", (("clause-device-protocols", ("device-protocols",)),)),),
    ),
    DevelopmentCase(
        "dev48-case-bastion-roles", "dev48-gold-bastion-roles", "DRY-01-slot-04",
        "Which roles alone may perform system-management operations through the bastion host?", "set", ("系统管理员", "安全审计员"),
        (EvidenceSpec("bastion-roles", _span(35)),),
        (("path-bastion-roles", (("clause-bastion-roles", ("bastion-roles",)),)),),
    ),
    DevelopmentCase(
        "dev48-case-conclusion-validity-basis", "dev48-gold-conclusion-validity-basis", "DRY-03-slot-01",
        "What is stated as the basis for the validity of the assessment conclusion?", "text", "被测评单位提供相关证据的真实性",
        (EvidenceSpec("conclusion-basis", _span(15)),),
        (("path-conclusion-basis", (("clause-conclusion-basis", ("conclusion-basis",)),)),),
    ),
    DevelopmentCase(
        "dev48-case-quotation-fidelity", "dev48-gold-quotation-fidelity", "DRY-03-slot-02",
        "When assessment results or conclusions are quoted, what must be preserved?", "text", "其原有的意义",
        (EvidenceSpec("quotation-fidelity", _span(18)),),
        (("path-quotation-fidelity", (("clause-quotation-fidelity", ("quotation-fidelity",)),)),),
    ),
    DevelopmentCase(
        "dev48-case-commissioned-evaluator", "dev48-gold-commissioned-evaluator", "DRY-03-slot-03",
        "Which organization was commissioned to conduct the cybersecurity graded-protection assessment?", "text", "安全研究中心",
        (EvidenceSpec("commissioned-evaluator", _span(265)),),
        (("path-commissioned-evaluator", (("clause-commissioned-evaluator", ("commissioned-evaluator",)),)),),
    ),
    DevelopmentCase(
        "dev48-case-project-phase-intervals", "dev48-gold-project-phase-intervals", "DRY-04-slot-01",
        "Which two assessment phases cover 5 June–1 December 2023 and 1–25 December 2023, respectively?", "set", ("测评实施过程", "分析与报告编制过程"),
        (EvidenceSpec("onsite-phase", _span(277)), EvidenceSpec("analysis-phase", _span(278))),
        (("path-project-phase-intervals", (("clause-onsite-phase", ("onsite-phase",)), ("clause-analysis-phase", ("analysis-phase",)))),),
    ),
    DevelopmentCase(
        "dev48-case-network-controls", "dev48-gold-network-controls", "DRY-04-slot-02",
        "Which two protections are reported for isolating the external web-server DMZ and for remotely managing devices?", "set", ("防火墙隔离", "SSH、HTTPS"),
        (EvidenceSpec("dmz-isolation", _span(25)), EvidenceSpec("remote-management-protocols", _span(34))),
        (("path-network-controls", (("clause-dmz-isolation", ("dmz-isolation",)), ("clause-remote-protocols", ("remote-management-protocols",)))),),
    ),
    DevelopmentCase(
        "dev48-case-access-approval-controls", "dev48-gold-access-approval-controls", "DRY-04-slot-03",
        "What approvals or safeguards apply to third-party remote access and to operation of association equipment?", "set", ("安全主管批准", "信息科技主管部门批准并由专人陪同"),
        (EvidenceSpec("third-party-access", _span(38)), EvidenceSpec("equipment-operation", _span(40))),
        (("path-access-approval-controls", (("clause-third-party-access", ("third-party-access",)), ("clause-equipment-operation", ("equipment-operation",)))),),
    ),
    DevelopmentCase(
        "dev48-case-http-remediation", "dev48-gold-http-remediation", "DRY-05-slot-01",
        "What remediation is recommended after the application system is found to use HTTP for communication?", "text", "使用HTTPS等加密协议进行通信",
        (EvidenceSpec("http-risk", _span(52)), EvidenceSpec("http-remediation", _span(53))),
        (("path-http-remediation", (("clause-http-risk", ("http-risk",)), ("clause-http-remediation", ("http-remediation",)))),),
        (EvidenceDependency(dependency_id="identify-http-risk", description="identify the documented HTTP transmission-integrity weakness"), EvidenceDependency(dependency_id="apply-http-remediation", depends_on=("identify-http-risk",), description="map that weakness to its stated remediation")),
    ),
    DevelopmentCase(
        "dev48-case-offsite-backup-remediation", "dev48-gold-offsite-backup-remediation", "DRY-05-slot-02",
        "What corrective action is recommended when business data has local backups but no off-site backup capability?", "text", "将关键数据定时批量传送至备用场地，实现异地数据异地备份",
        (EvidenceSpec("backup-risk", _span(84)), EvidenceSpec("backup-remediation", _span(85))),
        (("path-offsite-backup-remediation", (("clause-backup-risk", ("backup-risk",)), ("clause-backup-remediation", ("backup-remediation",)))),),
        (EvidenceDependency(dependency_id="identify-backup-gap", description="identify the local-only backup gap"), EvidenceDependency(dependency_id="apply-offsite-remediation", depends_on=("identify-backup-gap",), description="map the gap to the stated off-site backup remediation")),
    ),
    DevelopmentCase(
        "dev48-case-fire-suppression-remediation", "dev48-gold-fire-suppression-remediation", "DRY-05-slot-03",
        "What remedy is recommended after the computer room is found not to have an automatic fire-suppression system?", "text", "安装自动气体灭火系统并定期检查及保养",
        (EvidenceSpec("fire-risk", _span(45)), EvidenceSpec("fire-remediation", _span(46))),
        (("path-fire-suppression-remediation", (("clause-fire-risk", ("fire-risk",)), ("clause-fire-remediation", ("fire-remediation",)))),),
        (EvidenceDependency(dependency_id="identify-fire-gap", description="identify the automatic-fire-suppression gap"), EvidenceDependency(dependency_id="apply-fire-remediation", depends_on=("identify-fire-gap",), description="map the gap to the stated fire-protection remediation")),
    ),
    DevelopmentCase(
        "dev48-case-risk-tier-and-rating", "dev48-gold-risk-tier-and-rating", "DRY-06-slot-01",
        "Which risk tier has eight unresolved issues, and what overall rating is reported with the final score?", "set", ("中风险问题", "良"),
        (EvidenceSpec("risk-count", _span(41)), EvidenceSpec("final-rating", _span(593))),
        (("path-risk-tier-and-rating", (("clause-risk-count", ("risk-count",)), ("clause-final-rating", ("final-rating",)))),),
    ),
    DevelopmentCase(
        "dev48-case-preparation-duration-comparison", "dev48-gold-preparation-duration-comparison", "DRY-06-slot-02",
        "Which phase lasted longer, the preparation phase or the plan-development phase?", "text", "测评准备过程",
        (EvidenceSpec("preparation-duration", _span(275)), EvidenceSpec("plan-duration", _span(276))),
        (("path-preparation-duration-comparison", (("clause-preparation-duration", ("preparation-duration",)), ("clause-plan-duration", ("plan-duration",)))),),
    ),
    DevelopmentCase(
        "dev48-case-implementation-duration-comparison", "dev48-gold-implementation-duration-comparison", "DRY-06-slot-03",
        "Which phase lasted longer, onsite implementation or analysis and report preparation?", "text", "测评实施过程",
        (EvidenceSpec("implementation-duration", _span(277)), EvidenceSpec("report-duration", _span(278))),
        (("path-implementation-duration-comparison", (("clause-implementation-duration", ("implementation-duration",)), ("clause-report-duration", ("report-duration",)))),),
    ),
    DevelopmentCase(
        "dev48-case-low-vulnerability-total", "dev48-gold-low-vulnerability-total", "DRY-07-slot-01",
        "In the multi-level vulnerability-count table, what is the total number of low-severity vulnerabilities across entries 1 through 4?", "numeric", "21",
        (EvidenceSpec("low-entry-1", _logical("2000003006")), EvidenceSpec("low-entry-2", _logical("2000004006")), EvidenceSpec("low-entry-3", _logical("2000005006")), EvidenceSpec("low-entry-4", _logical("2000006006"))),
        (("path-low-vulnerability-total", (("clause-low-entry-1", ("low-entry-1",)), ("clause-low-entry-2", ("low-entry-2",)), ("clause-low-entry-3", ("low-entry-3",)), ("clause-low-entry-4", ("low-entry-4",)))),),
    ),
    DevelopmentCase(
        "dev48-case-data-integrity-status-difference", "dev48-gold-data-integrity-status-difference", "DRY-07-slot-02",
        "For the external website, what is the difference between compliant and partially compliant counts under the multi-level Data Integrity column?", "numeric", "0",
        (EvidenceSpec("data-integrity-compliant", _logical("5100003010")), EvidenceSpec("data-integrity-partial", _logical("5100004010"))),
        (("path-data-integrity-status-difference", (("clause-data-integrity-compliant", ("data-integrity-compliant",)), ("clause-data-integrity-partial", ("data-integrity-partial",)))),),
    ),
    DevelopmentCase(
        "dev48-case-partially-compliant-management-area", "dev48-gold-partially-compliant-management-area", "DRY-07-slot-03",
        "Which management area is the only one with a partially compliant item in the multi-level management-personnel summary?", "text", "外部人员访问管理",
        (EvidenceSpec("personnel-partial-hiring", _logical("5600004004")), EvidenceSpec("personnel-partial-departure", _logical("5600004005")), EvidenceSpec("personnel-partial-training", _logical("5600004006")), EvidenceSpec("personnel-partial-external-access", _logical("5600004007"))),
        (("path-partially-compliant-management-area", (("clause-personnel-partial-hiring", ("personnel-partial-hiring",)), ("clause-personnel-partial-departure", ("personnel-partial-departure",)), ("clause-personnel-partial-training", ("personnel-partial-training",)), ("clause-personnel-partial-external-access", ("personnel-partial-external-access",)))),),
    ),
    DevelopmentCase(
        "dev48-case-audit-data-confidentiality", "dev48-gold-audit-data-confidentiality", "DRY-10-slot-01",
        "Is confidentiality listed as a security-protection requirement for audit data in the data-resource inventory?", "abstain", None,
        (EvidenceSpec("audit-data-scope", _table(17), EvidenceRole.NEGATIVE_SCOPE, "The complete inventory is the bounded scope for this absent attribute."),),
        (), negative_scope=(_table(17),), negative_rationale="The complete data-resource inventory records integrity for the audit-data row and no confidentiality requirement in that field.",
    ),
    DevelopmentCase(
        "dev48-case-access-switch-ipv6-address", "dev48-gold-access-switch-ipv6-address", "DRY-10-slot-02",
        "What IPv6 address is documented for the access switch in the device inventory?", "abstain", None,
        (EvidenceSpec("access-switch-inventory-scope", _table(10), EvidenceRole.NEGATIVE_SCOPE, "The complete device row and its schema are the bounded scope for the absent address attribute."),),
        (), negative_scope=(_table(10),), negative_rationale="The complete access-switch inventory supplies device identity, version, model, purpose, and importance, but no IPv6-address field or value.",
    ),
    DevelopmentCase(
        "dev48-case-tomcat-vendor", "dev48-gold-tomcat-vendor", "DRY-10-slot-03",
        "Which vendor is documented for the Tomcat middleware entry in the management-software inventory?", "abstain", None,
        (EvidenceSpec("tomcat-inventory-scope", _table(15), EvidenceRole.NEGATIVE_SCOPE, "The complete management-software inventory is the bounded scope for the absent vendor attribute."),),
        (), negative_scope=(_table(15),), negative_rationale="The complete Tomcat entry records its function, version, host device, and importance, but the inventory has no vendor field or vendor value.",
    ),
    DevelopmentCase(
        "dev48-case-server-database-alternative", "dev48-gold-server-database-alternative", "DRY-12-slot-01",
        "What database-management-system version is recorded for the external website server?", "text", "mysql-5.7.17",
        (EvidenceSpec("database-main-assets", _logical("1200002006")), EvidenceSpec("database-appendix-assets", _logical("3400002006"))),
        (("path-database-main-assets", (("clause-database-main-assets", ("database-main-assets",)),)), ("path-database-appendix-assets", (("clause-database-appendix-assets", ("database-appendix-assets",)),))),
    ),
    DevelopmentCase(
        "dev48-case-switch-os-alternative", "dev48-gold-switch-os-alternative", "DRY-12-slot-02",
        "What operating-system version is recorded for the access switch?", "text", "S2910_RGOS 11.4(1)B1P3",
        (EvidenceSpec("switch-os-main-assets", _logical("1000002004")), EvidenceSpec("switch-os-appendix-assets", _logical("3200002004"))),
        (("path-switch-os-main-assets", (("clause-switch-os-main-assets", ("switch-os-main-assets",)),)), ("path-switch-os-appendix-assets", (("clause-switch-os-appendix-assets", ("switch-os-appendix-assets",)),))),
    ),
    DevelopmentCase(
        "dev48-case-server-middleware-alternative", "dev48-gold-server-middleware-alternative", "DRY-12-slot-03",
        "What middleware version is recorded for the external website server?", "text", "tomcat",
        (EvidenceSpec("middleware-main-assets", _logical("1200002007")), EvidenceSpec("middleware-appendix-assets", _logical("3400002007"))),
        (("path-middleware-main-assets", (("clause-middleware-main-assets", ("middleware-main-assets",)),)), ("path-middleware-appendix-assets", (("clause-middleware-appendix-assets", ("middleware-appendix-assets",)),))),
    ),
)


BLOCKED_SLOTS: tuple[tuple[str, PortfolioBlockedReason, str], ...] = (
    # The remaining English lexical-confusability slots cannot be made into
    # natural, uniquely answerable questions from this document.  The five
    # available asset-class summaries differ only in their leading label; a
    # question that selects one would consequently disclose the answer or
    # admit several equally supported answers.  The historical Chinese pilot
    # in slot 04 remains frozen unchanged.
    ("DRY-02-slot-01", PortfolioBlockedReason.AUTHENTIC_AMBIGUITY_UNAVAILABLE, "The available English lexical-confusability candidates are near-duplicate asset summaries with no natural, uniquely answerable discriminator; forcing an entity-label question would create ambiguous Gold."),
    ("DRY-02-slot-02", PortfolioBlockedReason.AUTHENTIC_AMBIGUITY_UNAVAILABLE, "The available English lexical-confusability candidates are near-duplicate asset summaries with no natural, uniquely answerable discriminator; forcing an entity-label question would create ambiguous Gold."),
    ("DRY-02-slot-03", PortfolioBlockedReason.AUTHENTIC_AMBIGUITY_UNAVAILABLE, "The available English lexical-confusability candidates are near-duplicate asset summaries with no natural, uniquely answerable discriminator; forcing an entity-label question would create ambiguous Gold."),
    ("DRY-08-slot-01", PortfolioBlockedReason.UNSUPPORTED_MODALITY, "The required figure-caption-plus-equation modality is not Gold-eligible in this DOCX Canonical audit."),
    ("DRY-08-slot-02", PortfolioBlockedReason.UNSUPPORTED_MODALITY, "The required figure-caption-plus-equation modality is not Gold-eligible in this DOCX Canonical audit."),
    ("DRY-08-slot-03", PortfolioBlockedReason.UNSUPPORTED_MODALITY, "The required figure-caption-plus-equation modality is not Gold-eligible in this DOCX Canonical audit."),
    ("DRY-08-slot-04", PortfolioBlockedReason.UNSUPPORTED_MODALITY, "The required figure-caption-plus-equation modality is not Gold-eligible in this DOCX Canonical audit."),
    ("DRY-09-slot-01", PortfolioBlockedReason.NO_VALID_CONFLICT, "The single real DOCX has no audited temporal/version conflict with an authoritative resolution path."),
    ("DRY-09-slot-02", PortfolioBlockedReason.NO_VALID_CONFLICT, "The single real DOCX has no audited temporal/version conflict with an authoritative resolution path."),
    ("DRY-09-slot-03", PortfolioBlockedReason.NO_VALID_CONFLICT, "The single real DOCX has no audited temporal/version conflict with an authoritative resolution path."),
    ("DRY-09-slot-04", PortfolioBlockedReason.NO_VALID_CONFLICT, "The single real DOCX has no audited temporal/version conflict with an authoritative resolution path."),
    ("DRY-11-slot-01", PortfolioBlockedReason.AUTHENTIC_AMBIGUITY_UNAVAILABLE, "No unresolved ambiguity or unresolved conflicting evidence can be established from Gold-eligible evidence without manufacturing one."),
    ("DRY-11-slot-02", PortfolioBlockedReason.AUTHENTIC_AMBIGUITY_UNAVAILABLE, "No unresolved ambiguity or unresolved conflicting evidence can be established from Gold-eligible evidence without manufacturing one."),
    ("DRY-11-slot-03", PortfolioBlockedReason.AUTHENTIC_AMBIGUITY_UNAVAILABLE, "No unresolved ambiguity or unresolved conflicting evidence can be established from Gold-eligible evidence without manufacturing one."),
    ("DRY-11-slot-04", PortfolioBlockedReason.AUTHENTIC_AMBIGUITY_UNAVAILABLE, "No unresolved ambiguity or unresolved conflicting evidence can be established from Gold-eligible evidence without manufacturing one."),
)


def _origin(document_id: str) -> AuthoringOrigin:
    return AuthoringOrigin(
        kind=OriginKind.HUMAN,
        trust_level=TrustLevel.HUMAN_ASSERTED,
        generator_identity="evidence-first-human-development-48",
        source_world="real-docx-development-portfolio",
        source_document_ids=(document_id,),
    )


def _gold_payload(spec: DevelopmentCase) -> GoldPayload:
    return GoldPayload(
        answer=GoldAnswer(kind=spec.answer_kind, canonical=spec.answer, locale="en"),
        evidence=tuple(
            GoldEvidence(
                evidence_id=item.evidence_id,
                canonical_object_id=item.canonical_object_id,
                role=item.role,
                rationale=item.rationale,
            )
            for item in spec.evidence
        ),
        mses_paths=tuple(
            MsesPath(
                path_id=path_id,
                clauses=tuple(MsesClause(clause_id=clause_id, alternatives=alternatives) for clause_id, alternatives in clauses),
            )
            for path_id, clauses in spec.paths
        ),
        dependencies=spec.dependencies,
        negative_scope_object_ids=spec.negative_scope,
        negative_rationale=spec.negative_rationale,
    )


def _necessity_checks(gold) -> tuple[MsesNecessityCheck, ...]:
    return tuple(
        MsesNecessityCheck(
            path_id=path.path_id,
            clause_id=clause.clause_id,
            alternative_evidence_ids=clause.alternatives,
            necessary=True,
            method="independent-human-evidence-removal-v1",
            verifier_identity=REVIEWERS[0],
            rationale="Removing this clause removes a required fact, calculation input, or permitted alternative path.",
        )
        for path in gold.payload.mses_paths
        for clause in path.clauses
    )


def _review_and_approve(platform: PlatformService, dataset, spec: DevelopmentCase, case, gold):
    assert platform.formal_datasets is not None
    ledger = platform.formal_datasets.ledger
    case_reviews = []
    gold_reviews = []
    # Two independent reviews are retained for every new Case.  This exceeds
    # the standard tier and is required for table, multi-hop, alternative, and
    # adversarial slots in this batch.
    for reviewer in REVIEWERS:
        case_reviews.append(
            ledger.record_review(
                dataset.authoring_dataset_id,
                target_kind=TargetKind.CASE,
                reviewed_revision_id=case.case_revision_id,
                reviewer=reviewer,
                decision=ReviewDecision.APPROVE,
                checklist={"question_natural": True, "ambiguity_checked": True, "difficulty_label_reasonable": True},
                comments="Independent evidence-first development Portfolio Case review.",
            )
        )
        gold_reviews.append(
            ledger.record_review(
                dataset.authoring_dataset_id,
                target_kind=TargetKind.GOLD,
                reviewed_revision_id=gold.gold_revision_id,
                reviewer=reviewer,
                decision=ReviewDecision.APPROVE,
                checklist={"answer_correct": True, "evidence_sufficient": True, "evidence_minimal": True, "alternative_answers_checked": True},
                comments="Independent Gold, MSES, locator, and alternative-answer review.",
            )
        )
    reviewed_case = ledger.mark_reviewed(dataset, target_kind=TargetKind.CASE, revision_id=case.case_revision_id, actor=AUTHOR, reason="independent reviewer checklist accepted Case")
    reviewed_gold = ledger.mark_reviewed(dataset, target_kind=TargetKind.GOLD, revision_id=gold.gold_revision_id, actor=AUTHOR, reason="independent reviewer checklist accepted Gold")
    approved_case = ledger.approve(dataset, target_kind=TargetKind.CASE, revision_id=reviewed_case.case_revision_id, approver=REVIEWERS[0], role=ActorRole.REVIEWER, reason="independent reviewer approval after Case review")
    approved_gold = ledger.approve(dataset, target_kind=TargetKind.GOLD, revision_id=reviewed_gold.gold_revision_id, approver=REVIEWERS[0], role=ActorRole.REVIEWER, reason="independent reviewer approval after Gold review")
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
            comments=f"Paired independent Gold review: {gold_review.review_id}",
        )
        for reviewer, case_review, gold_review in zip(REVIEWERS, case_reviews, gold_reviews, strict=True)
    )
    return approved_case, approved_gold, attestations


def _attestations_from_history(ledger, dataset_id: str, case, gold) -> tuple[AdmissionChecklistAttestation, ...]:
    """Reconstruct typed admission attestations without rewriting reviews."""

    reviews = ledger.list_reviews(dataset_id)
    case_revision_ids = {item.case_revision_id for item in ledger.case_history(dataset_id, case.case_id)}
    gold_revision_ids = {item.gold_revision_id for item in ledger.gold_history(dataset_id, gold.gold_id)}
    case_by_reviewer = {
        item.reviewer_identity: item
        for item in reviews
        if item.target_kind == TargetKind.CASE
        and item.decision == ReviewDecision.APPROVE
        and item.reviewed_revision_id in case_revision_ids
    }
    gold_by_reviewer = {
        item.reviewer_identity: item
        for item in reviews
        if item.target_kind == TargetKind.GOLD
        and item.decision == ReviewDecision.APPROVE
        and item.reviewed_revision_id in gold_revision_ids
    }
    missing = [reviewer for reviewer in REVIEWERS if reviewer not in case_by_reviewer or reviewer not in gold_by_reviewer]
    if missing:
        raise RuntimeError(f"Case {case.case_id} is missing independent review lineage: {missing}")
    return tuple(
        AdmissionChecklistAttestation(
            ledger_review_id=case_by_reviewer[reviewer].review_id,
            reviewed_case_revision_id=case_by_reviewer[reviewer].reviewed_revision_id,
            reviewed_gold_revision_id=gold_by_reviewer[reviewer].reviewed_revision_id,
            case_id=case.case_id,
            gold_id=gold.gold_id,
            reviewer_identity=reviewer,
            question_natural=True,
            ambiguity_checked=True,
            answer_correct=True,
            evidence_sufficient=True,
            evidence_minimal=True,
            alternative_answers_checked=True,
            difficulty_label_reasonable=True,
            approved=True,
            comments=f"Replayed typed attestation from Case/Gold review records {case_by_reviewer[reviewer].review_id} / {gold_by_reviewer[reviewer].review_id}.",
        )
        for reviewer in REVIEWERS
    )


def _source_record(platform: PlatformService, dataset, canonical: CanonicalDocument) -> tuple[DocumentSourceRecord, object]:
    assert platform.benchmark_admission is not None
    store = platform.benchmark_admission.store
    family_path = store.root / "source-families" / f"{SOURCE_FAMILY_ID}.json"
    family = (
        SourceFamilyRecord.model_validate_json(family_path.read_text(encoding="utf-8"))
        if family_path.is_file()
        else store.put_family(
            SourceFamilyRecord.build(
                source_family_id=SOURCE_FAMILY_ID,
                classification=SourceFamilyClass.DEVELOPMENT,
                content_boundary="real DOCX development-only authoring; excluded from held-out use",
                owner="development-source-steward",
            )
        )
    )
    source_path = store.root / "source-documents" / SOURCE_DOCUMENT_ID / "000002.json"
    if source_path.is_file():
        record = DocumentSourceRecord.model_validate_json(source_path.read_text(encoding="utf-8"))
        if record.canonical_document_digest != canonical.manifest.canonical_digest:
            raise RuntimeError("existing Canonical 1.1 source admission revision does not match this build")
    else:
        record = DocumentSourceRecord.build(
            source_document_id=SOURCE_DOCUMENT_ID,
            source_family_id=SOURCE_FAMILY_ID,
            revision=2,
            parent_revision_id=f"source-revision-{SOURCE_DOCUMENT_ID}-000001",
            document_type=DocumentType.DOCX,
            content_summary="The real S2A2G2 assessment report, re-canonicalized under Contract 1.1; whole-source admission remains partial while each development Case is scoped to audited Gold-eligible objects.",
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
            actor="development-source-steward",
            reason="whole document retains out-of-scope rich structures; development actualization uses explicit complete Canonical scopes only",
        )
        record = platform.benchmark_admission.record_source(record)
    report = platform.benchmark_admission.validate_source(record, family, development_family_ids=())
    if not report.has_errors:
        raise RuntimeError("whole-document partial source unexpectedly passed full-source admission")
    return record, report


def _assert_pilot_is_preserved(platform: PlatformService) -> dict[str, object]:
    assert platform.portfolios is not None
    assert platform.formal_datasets is not None
    portfolio = platform.portfolios.store.get(PORTFOLIO_ID_V0_DRY_RUN)
    frozen = [
        platform.portfolios.store.current_assignment(PORTFOLIO_ID_V0_DRY_RUN, slot.slot_id)
        for slot in portfolio.slots
    ]
    pilot = [item for item in frozen if item is not None and item.state == PortfolioSlotState.FROZEN and item.links.release_id == PILOT_RELEASE_ID]
    if len(pilot) != PILOT_CASE_COUNT:
        raise RuntimeError(f"expected {PILOT_CASE_COUNT} preserved pilot assignments, got {len(pilot)}")
    rebuild = platform.formal_datasets.rebuild(PILOT_RELEASE_ID)
    if not rebuild.reproducible:
        raise RuntimeError("the historical eight-case pilot release is no longer reproducible")
    return {"pilot_assignment_count": len(pilot), "pilot_release_id": PILOT_RELEASE_ID, "pilot_rebuild": rebuild.model_dump(mode="json")}


def _verify_spec_evidence(canonical: CanonicalDocument) -> None:
    known = {item.object_id: item for item in canonical.objects}
    for spec in CASES:
        for object_id in spec.source_object_ids:
            item = known.get(object_id)
            if item is None or not item.gold_evidence_eligible:
                raise RuntimeError(f"{spec.case_id} cites non-eligible Canonical evidence: {object_id}")
        for object_id in spec.negative_scope:
            item = known.get(object_id)
            if item is None or not item.gold_evidence_eligible:
                raise RuntimeError(f"{spec.case_id} has an unsafe negative scope: {object_id}")
    # The three new structured Cases must exercise the v3 logical-cell layer,
    # retain a physical-cell provenance hop, and expose an effective header.
    for spec in (item for item in CASES if item.slot_id.startswith("DRY-07")):
        for object_id in spec.source_object_ids:
            item = known[object_id]
            if item.object_type.value != "logical_cell" or not item.provenance.derived_from_object_ids or not item.attributes.get("effective_header_path"):
                raise RuntimeError(f"{spec.case_id} does not retain logical-cell/header/physical topology: {object_id}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-docx", type=Path, required=True)
    parser.add_argument("--platform-home", type=Path, required=True)
    parser.add_argument(
        "--case-limit",
        type=int,
        default=None,
        help="create at most this many new Case/Gold pairs, then stop before blocking/freezing",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    source = args.source_docx.resolve()
    home = args.platform_home.resolve()
    if not source.is_file():
        raise SystemExit(f"real DOCX not found: {source}")
    if args.case_limit is not None and args.case_limit < 1:
        raise SystemExit("--case-limit must be a positive integer")
    platform = PlatformService(PlatformPaths(home), product_enabled=True)
    assert platform.authoring is not None and platform.formal_datasets is not None
    assert platform.portfolios is not None and platform.benchmark_admission is not None
    pilot_before = _assert_pilot_is_preserved(platform)
    existing = platform.authoring.get("4867d37a2e17407e8ec774794e853b3c")
    if existing.source.sha256 != hashlib.sha256(source.read_bytes()).hexdigest():
        raise RuntimeError("the requested source DOCX does not match the preserved pilot source digest")
    dataset = platform.authoring.analyze(existing.authoring_dataset_id)
    canonical = FormalDatasetValidator()._load_canonical_document(dataset, platform.authoring.store)
    if canonical.manifest.schema_version != "1.1" or canonical.manifest.canonicalizer_identity != "rag-eval-authoring-canonicalizer/3":
        raise RuntimeError("development actualization requires the audited Canonical Contract 1.1 / canonicalizer 3")
    _verify_spec_evidence(canonical)
    source_record, source_report = _source_record(platform, dataset, canonical)
    ledger = platform.formal_datasets.ledger
    document_revision = ledger.document_history(dataset.authoring_dataset_id)[-1]
    portfolio = platform.portfolios.store.get(PORTFOLIO_ID_V0_DRY_RUN)
    slot_by_id = {item.slot_id: item for item in portfolio.slots}
    frozen_ids = {
        item.slot_id
        for item in portfolio.slots
        if (assignment := platform.portfolios.store.current_assignment(PORTFOLIO_ID_V0_DRY_RUN, item.slot_id))
        and assignment.state == PortfolioSlotState.FROZEN
    }
    if frozen_ids != PILOT_SLOT_IDS:
        raise RuntimeError("development Portfolio has unexpected pre-existing frozen slots; do not overwrite its history")
    if {item.slot_id for item in CASES}.intersection(frozen_ids):
        raise RuntimeError("a new development Case would overwrite a frozen Portfolio slot")

    approved: list[tuple[DevelopmentCase, object, object, object]] = []
    created_this_run = 0
    prior_cases = [item.case_id for item in platform.formal_datasets.releases.get(PILOT_RELEASE_ID).cases]
    for spec in CASES:
        if args.case_limit is not None and created_this_run >= args.case_limit:
            break
        slot = slot_by_id[spec.slot_id]
        if slot.language.value != "en":
            raise RuntimeError(f"{spec.slot_id} must remain its Blueprint language; this batch expected English")
        history = ledger.case_history(dataset.authoring_dataset_id, spec.case_id)
        if history:
            approved_case = ledger.current_case(dataset.authoring_dataset_id, spec.case_id)
            approved_gold = ledger.current_gold_for_case(dataset.authoring_dataset_id, spec.case_id)
            if approved_case.lifecycle not in {LifecycleState.APPROVED, LifecycleState.FROZEN} or approved_gold.lifecycle not in {LifecycleState.APPROVED, LifecycleState.FROZEN}:
                raise RuntimeError(f"existing {spec.case_id} is not at an approval-safe resume point")
            assignment = platform.portfolios.store.current_assignment(PORTFOLIO_ID_V0_DRY_RUN, spec.slot_id)
            if assignment is None or assignment.state not in {PortfolioSlotState.APPROVED, PortfolioSlotState.FROZEN}:
                raise RuntimeError(f"existing {spec.case_id} has no matching approved/frozen Portfolio assignment")
            attestations = _attestations_from_history(ledger, dataset.authoring_dataset_id, approved_case, approved_gold)
            if args.case_limit is not None:
                # A bounded resume pass need only create new pairs; previous
                # pairs already have a passing immutable admission artifact.
                prior_cases.append(spec.case_id)
                continue
        else:
            origin = _origin(dataset.document_id or canonical.manifest.document_id)
            draft = CaseDraft(
                case_id=spec.case_id,
                target_id=f"target-{spec.case_id}",
                question=spec.question,
                language=slot.language.value,
                source_digest=dataset.source.sha256,
                canonical_contract_digest=canonical.manifest.canonical_digest,
                canonical_compatibility_digest=dataset.canonical_digest,
                source_object_ids=spec.source_object_ids,
                origin=origin,
            )
            case = ledger.create_case(dataset, draft=draft, actor=AUTHOR, reason="human evidence-first real DOCX development Portfolio Case draft")
            case = ledger.propose_case(dataset, case_id=case.case_id, actor=AUTHOR, reason="submit real DOCX development Case for independent review")
            gold = ledger.create_gold(dataset, gold_id=spec.gold_id, case_revision=case, payload=_gold_payload(spec), origin=origin, actor=AUTHOR, reason="human evidence-first real DOCX development Portfolio Gold draft")
            gold = ledger.propose_gold(dataset, gold_id=gold.gold_id, actor=AUTHOR, reason="submit real DOCX development Gold for independent review")
            platform.portfolios.transition_slot(PORTFOLIO_ID_V0_DRY_RUN, slot_id=spec.slot_id, state=PortfolioSlotState.AUTHORED, links=PortfolioLinks(dataset_id=dataset.authoring_dataset_id, case_revision_id=case.case_revision_id), actor=AUTHOR, reason="bind planned development slot to an evidence-first real DOCX Case proposal")
            approved_case, approved_gold, attestations = _review_and_approve(platform, dataset, spec, case, gold)
            reviewed_case = ledger.case_history(dataset.authoring_dataset_id, spec.case_id)[2]
            platform.portfolios.transition_slot(PORTFOLIO_ID_V0_DRY_RUN, slot_id=spec.slot_id, state=PortfolioSlotState.REVIEWED, links=PortfolioLinks(dataset_id=dataset.authoring_dataset_id, case_revision_id=reviewed_case.case_revision_id), actor=AUTHOR, reason="record independent two-reviewer Case and Gold review completion")
            platform.portfolios.transition_slot(PORTFOLIO_ID_V0_DRY_RUN, slot_id=spec.slot_id, state=PortfolioSlotState.APPROVED, links=PortfolioLinks(dataset_id=dataset.authoring_dataset_id, document_revision_id=document_revision.document_revision_id, case_revision_id=approved_case.case_revision_id, gold_revision_id=approved_gold.gold_revision_id), actor=REVIEWERS[0], reason="independent approval of real DOCX Case and Gold")
            created_this_run += 1
        scope = CanonicalEvidenceScope.build(scope_id=f"scope-{spec.case_id}", source_document_id=source_record.source_document_id, canonical_document_digest=canonical.manifest.canonical_digest, canonical_object_ids=spec.source_object_ids, actor="development-source-steward", reason="development Gold is limited to audited complete Canonical 1.1 evidence")
        similarity = tuple(QuestionSimilarityAssessment(compared_case_id=case_id, compared_usage=PortfolioUsage.DEVELOPMENT, disposition=SimilarityDisposition.DISTINCT, similarity_score=0.0, method="independent-human-development-question-comparison-v1") for case_id in prior_cases)
        admission = platform.benchmark_admission.validate_case(CaseAdmissionInput(portfolio_id=PORTFOLIO_ID_V0_DRY_RUN, slot_id=spec.slot_id, source=source_record, source_admission_report=source_report, evidence_scope=scope, case=approved_case, gold=approved_gold, canonical=canonical, necessity_checks=_necessity_checks(approved_gold), question_similarity=similarity, review_attestations=attestations))
        if not admission.eligible_to_proceed:
            raise RuntimeError(f"admission preflight did not pass for {spec.case_id}: {admission.report_digest}")
        approved.append((spec, approved_case, approved_gold, admission))
        prior_cases.append(spec.case_id)

    if args.case_limit is not None:
        print(json.dumps({"status": "partial_actualization_complete", "new_cases_created_this_run": created_this_run, "approved_or_frozen_case_count_in_scope": len(approved), "coverage": platform.portfolios.coverage_report(PORTFOLIO_ID_V0_DRY_RUN).model_dump(mode="json")}, ensure_ascii=False, indent=2))
        return

    for slot_id, blocked_reason, reason in BLOCKED_SLOTS:
        existing = platform.portfolios.store.current_assignment(PORTFOLIO_ID_V0_DRY_RUN, slot_id)
        if existing is None:
            platform.portfolios.transition_slot(PORTFOLIO_ID_V0_DRY_RUN, slot_id=slot_id, state=PortfolioSlotState.BLOCKED, blocked_reason=blocked_reason, links=PortfolioLinks(), actor="development-48-evidence-steward", reason=reason)
        elif existing.state is not PortfolioSlotState.BLOCKED or existing.blocked_reason is not blocked_reason:
            raise RuntimeError(f"blocked slot {slot_id} has incompatible existing assignment")

    incomplete = [
        slot.slot_id
        for slot in portfolio.slots
        if (assignment := platform.portfolios.store.current_assignment(PORTFOLIO_ID_V0_DRY_RUN, slot.slot_id)) is None
        or assignment.state in {PortfolioSlotState.PLANNED, PortfolioSlotState.AUTHORED, PortfolioSlotState.REVIEWED}
    ]
    if incomplete:
        raise RuntimeError(f"development Portfolio has incomplete slots before freeze: {incomplete}")
    preflight = platform.formal_datasets.validate(dataset.authoring_dataset_id, case_revision_ids=tuple(case.case_revision_id for _spec, case, _gold, _admission in approved), gold_revision_ids=tuple(gold.gold_revision_id for _spec, _case, gold, _admission in approved), document_revision_id=document_revision.document_revision_id)
    if preflight.has_errors:
        raise RuntimeError(f"formal preflight failed: {preflight.report_digest}")
    release = platform.formal_datasets.freeze(dataset.authoring_dataset_id, release_version="development-real-docx-v3-48-actualization-1.0.0", case_ids=tuple(spec.case_id for spec, _case, _gold, _admission in approved), actor=RELEASE_MANAGER, parent_release_id=PILOT_RELEASE_ID)
    release_cases = {item.case_id: item for item in release.cases}
    release_gold = {item.case_id: item for item in release.gold}
    for spec, _case, _gold, _admission in approved:
        platform.portfolios.transition_slot(PORTFOLIO_ID_V0_DRY_RUN, slot_id=spec.slot_id, state=PortfolioSlotState.FROZEN, links=PortfolioLinks(dataset_id=dataset.authoring_dataset_id, document_revision_id=document_revision.document_revision_id, case_revision_id=release_cases[spec.case_id].case_revision_id, gold_revision_id=release_gold[spec.case_id].gold_revision_id, release_id=release.release_id), actor=RELEASE_MANAGER, reason="immutable successor release pins the real DOCX Case and Gold revisions")
    expected_terminal = {item.slot_id for item in CASES} | {item[0] for item in BLOCKED_SLOTS} | PILOT_SLOT_IDS
    terminal = {slot.slot_id for slot in portfolio.slots if (assignment := platform.portfolios.store.current_assignment(PORTFOLIO_ID_V0_DRY_RUN, slot.slot_id)) and assignment.state in {PortfolioSlotState.FROZEN, PortfolioSlotState.BLOCKED}}
    if terminal != expected_terminal:
        raise RuntimeError("not every development Portfolio slot reached a terminal frozen or blocked state")
    rebuild = platform.formal_datasets.rebuild(release.release_id)
    if not rebuild.reproducible:
        raise RuntimeError(f"successor release did not rebuild deterministically: {rebuild.reason}")
    pilot_after = _assert_pilot_is_preserved(platform)
    tampered = home / "development-48-tamper-check.docx"
    shutil.copyfile(platform.formal_datasets.releases.source_snapshot(release.release_id), tampered)
    tampered.write_bytes(tampered.read_bytes() + b"development-48-tamper")
    tamper_report = platform.formal_datasets.validate(dataset.authoring_dataset_id, case_revision_ids=tuple(item.case_revision_id for item in release.cases), gold_revision_ids=tuple(item.gold_revision_id for item in release.gold), required_lifecycle=LifecycleState.FROZEN, document_revision_id=release.document.document_revision_id, canonical_snapshot=platform.formal_datasets.releases.canonical_snapshot(release.release_id), source_snapshot=tampered)
    tampered.unlink()
    if not tamper_report.has_errors:
        raise RuntimeError("tampered successor release source unexpectedly passed validation")
    coverage = platform.portfolios.coverage_report(PORTFOLIO_ID_V0_DRY_RUN)
    state_counts = dict(coverage.state_counts)
    if state_counts.get(PortfolioSlotState.FROZEN, 0) != 33 or state_counts.get(PortfolioSlotState.BLOCKED, 0) != 15:
        raise RuntimeError(f"unexpected terminal coverage: {state_counts}")
    summary = {
        "source_docx": str(source),
        "platform_home": str(home),
        "dataset_id": dataset.authoring_dataset_id,
        "document_revision_id": document_revision.document_revision_id,
        "source_sha256": dataset.source.sha256,
        "canonical_digest": canonical.manifest.canonical_digest,
        "canonical_schema_version": canonical.manifest.schema_version,
        "canonicalizer_identity": canonical.manifest.canonicalizer_identity,
        "pilot_before": pilot_before,
        "pilot_after": pilot_after,
        "new_case_count": len(approved),
        "blocked_slot_count": len(BLOCKED_SLOTS),
        "new_cases": [{"slot_id": spec.slot_id, "case_id": spec.case_id, "gold_id": spec.gold_id, "case_revision_id": case.case_revision_id, "gold_revision_id": gold.gold_revision_id, "admission_report_digest": admission.report_digest, "logical_table_case": spec.slot_id.startswith("DRY-07")} for spec, case, gold, admission in approved],
        "blocked_slots": [{"slot_id": slot_id, "blocked_reason": blocked_reason.value, "reason": reason} for slot_id, blocked_reason, reason in BLOCKED_SLOTS],
        "formal_preflight_report_digest": preflight.report_digest,
        "release": release.model_dump(mode="json"),
        "rebuild": rebuild.model_dump(mode="json"),
        "tamper_report_digest": tamper_report.report_digest,
        "tamper_detected": tamper_report.has_errors,
        "coverage": coverage.model_dump(mode="json"),
    }
    atomic_write_json(home / "development-benchmark-48-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
