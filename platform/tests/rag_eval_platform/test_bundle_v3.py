from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rag_eval.authoring.ledger import (
    EvidenceDependency,
    EvidenceRole,
    GoldAnswer,
    GoldEvidence,
    GoldPayload,
    GoldRevision,
    MsesClause,
    MsesPath,
)
from rag_eval.authoring.service import AuthoringService
from rag_eval.authoring.models import DiscoveryMethod
from rag_eval.contracts.canonical import CanonicalDocument
from rag_eval.datasets.bundle_v3 import (
    BundleV3Builder,
    BundleV3EvidenceRecord,
    BundleV3GoldRecord,
    BundleV3IntegrityError,
    BundleV3Store,
    _validate_gold_semantics,
    load_bundle_v3,
)
from rag_eval.datasets.formal import FormalDatasetReleaseService
from rag_eval.datasets.portfolio import (
    BenchmarkPortfolioService,
    PortfolioAssignment,
    PortfolioLinks,
    PortfolioSlotState,
)
from tests.rag_eval_platform.test_authoring import mini_docx
from tests.rag_eval_platform.test_rich_content_canonicalization import _rich_fixture


def _release_context(tmp_path: Path):
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
    from rag_eval.authoring.models import AnswerEvidenceCandidate, CandidateEvidence

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
    formal = FormalDatasetReleaseService(
        authoring_store=authoring.store,
        release_root=tmp_path / "formal-releases",
    )
    case_id = formal.ledger.case_id_for_candidate(candidate.candidate_id)
    release = formal.freeze(
        dataset.authoring_dataset_id,
        release_version="bundle-v3-fixture-1.0.0",
        case_ids=(case_id,),
        actor="release-manager",
    )
    portfolios = BenchmarkPortfolioService(
        tmp_path / "portfolios",
        source_root=BenchmarkPortfolioService.default_source_root(),
        ledger=formal.ledger,
        releases=formal.releases,
    )
    portfolio = portfolios.bootstrap_v0_dry_run()
    slot = portfolio.slots[0]
    case_pin = release.cases[0]
    gold_pin = release.gold[0]
    portfolios.store.append_assignment(
        portfolio.portfolio_id,
        PortfolioAssignment(
            assignment_id=f"portfolio-assignment-{slot.slot_id}-000001",
            slot_id=slot.slot_id,
            revision=1,
            state=PortfolioSlotState.FROZEN,
            links=PortfolioLinks(
                dataset_id=dataset.authoring_dataset_id,
                document_revision_id=release.document.document_revision_id,
                case_revision_id=case_pin.case_revision_id,
                gold_revision_id=gold_pin.gold_revision_id,
                release_id=release.release_id,
            ),
            actor="fixture-release-manager",
            reason="bind the frozen fixture release to typed Portfolio axes",
            created_at=datetime.now(UTC),
        ),
    )
    store = BundleV3Store(
        tmp_path / "bundles-v3",
        releases=formal.releases,
        authoring_store=authoring.store,
        portfolios=portfolios.store,
    )
    return authoring, formal, release, store, target


def test_bundle_v3_build_is_deterministic_and_offline_only(tmp_path: Path) -> None:
    _authoring, _formal, release, store, _target = _release_context(tmp_path)
    first = store.build_from_release(release.release_id)
    second = store.build_from_release(release.release_id)

    assert first.bundle_id == second.bundle_id
    assert first.manifest.case_count == first.manifest.gold_count == 1
    assert first.dataset.target_release_id == release.release_id
    assert first.cases[0].portfolio.slot.slot_id
    assert first.gold[0].gold.payload.answer.canonical == "42 ms"
    assert first.evidence[0].canonical.provenance.source_spans
    assert any(item.object_type.value == "logical_cell" for item in first.canonical_documents[release.release_id].objects)
    assert any(item.relation_type.value == "physical_to_logical_cell" for item in first.canonical_documents[release.release_id].relations)

    paths = {
        path.relative_to(first.root).as_posix()
        for path in first.root.rglob("*")
        if path.is_file()
    }
    assert f"private/source/{release.document.source_digest}.docx" in paths
    assert "private/gold.jsonl" in paths
    assert "runtime/manifest.json" not in paths
    assert "runtime/questions.jsonl" not in paths
    assert not hasattr(store, "export_runtime_view")


def test_production_composition_root_does_not_import_offline_bundle_v3() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import rag_eval.service; "
                "assert 'rag_eval.datasets.bundle_v3' not in sys.modules"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_bundle_v3_catalog_preserves_content_address_with_manifest(tmp_path: Path) -> None:
    _authoring, _formal, release, store, _target = _release_context(tmp_path)
    bundle = store.build_from_release(release.release_id)

    records = store.list_manifest_records()
    assert records == [(bundle.bundle_id, bundle.manifest)]
    # The compatibility helper remains a manifest-only view for callers that
    # do not need the directory identity.
    assert store.list_manifests() == [bundle.manifest]


def test_bundle_v3_preserves_and_or_mses_multihop_and_negative_scope(tmp_path: Path) -> None:
    _authoring, formal, release, store, _target = _release_context(tmp_path)
    bundle = store.build_from_release(release.release_id)
    base = bundle.gold[0].gold
    canonical = bundle.canonical_documents[release.release_id]
    object_id = next(item.object_id for item in canonical.objects if item.gold_evidence_eligible)
    rich_payload = GoldPayload(
        answer=GoldAnswer(kind="text", canonical="42 ms", accepted_values=("42ms",)),
        evidence=(
            GoldEvidence(evidence_id="required-a", canonical_object_id=object_id, role=EvidenceRole.REQUIRED),
            GoldEvidence(evidence_id="required-b", canonical_object_id=object_id, role=EvidenceRole.REQUIRED),
            GoldEvidence(evidence_id="required-c", canonical_object_id=object_id, role=EvidenceRole.REQUIRED),
            GoldEvidence(evidence_id="near-miss", canonical_object_id=object_id, role=EvidenceRole.NEAR_MISS),
        ),
        mses_paths=(
            MsesPath(
                path_id="path-and-or",
                clauses=(
                    MsesClause(clause_id="clause-or", alternatives=("required-a", "required-b")),
                    MsesClause(clause_id="clause-and", alternatives=("required-c",)),
                ),
            ),
            MsesPath(
                path_id="path-alternative",
                clauses=(MsesClause(clause_id="clause-alt", alternatives=("required-b",)),),
            ),
        ),
        dependencies=(
            EvidenceDependency(dependency_id="step-1", description="recover the first witness"),
            EvidenceDependency(dependency_id="step-2", depends_on=("step-1",), description="derive the answer from the first witness"),
        ),
    )
    rich_gold = GoldRevision.model_validate(
        base.model_dump(mode="json")
        | {
            "gold_revision_id": "gold-revision-bundle-v3-mses-000001",
            "gold_id": "gold-bundle-v3-mses",
            "payload": rich_payload.model_dump(mode="json"),
        }
    )
    rich_record = BundleV3GoldRecord(release_id=release.release_id, gold=rich_gold)
    round_trip = BundleV3GoldRecord.model_validate_json(rich_record.model_dump_json())
    assert round_trip.gold.payload == rich_payload
    rich_evidence = tuple(
        BundleV3Builder._evidence_records(
            release,
            rich_gold,
            {item.object_id: item for item in canonical.objects},
        )
    )
    _validate_gold_semantics((rich_record,), rich_evidence, {release.release_id: canonical})

    negative_payload = GoldPayload(
        answer=GoldAnswer(kind="abstain"),
        evidence=(GoldEvidence(evidence_id="scope-support", canonical_object_id=object_id, role=EvidenceRole.SUPPORTING),),
        negative_scope_object_ids=(object_id,),
        negative_rationale="the bounded source scope does not state the requested attribute",
    )
    negative_gold = GoldRevision.model_validate(
        base.model_dump(mode="json")
        | {
            "gold_revision_id": "gold-revision-bundle-v3-negative-000001",
            "gold_id": "gold-bundle-v3-negative",
            "payload": negative_payload.model_dump(mode="json"),
        }
    )
    negative_record = BundleV3GoldRecord(release_id=release.release_id, gold=negative_gold)
    negative_evidence = tuple(
        BundleV3Builder._evidence_records(
            release,
            negative_gold,
            {item.object_id: item for item in canonical.objects},
        )
    )
    assert any(item.origin == "negative_scope_projection" for item in negative_evidence)
    _validate_gold_semantics((negative_record,), negative_evidence, {release.release_id: canonical})
    assert formal.releases.get(release.release_id) == release


def test_bundle_v3_retains_figure_and_equation_locator_boundaries(tmp_path: Path) -> None:
    authoring = AuthoringService(tmp_path / "authoring")
    dataset = authoring.analyze(authoring.upload_docx(filename="rich.docx", payload=_rich_fixture()).authoring_dataset_id)
    view = authoring.canonical_view(dataset.authoring_dataset_id)
    root = authoring.store.workspace(dataset.authoring_dataset_id)
    canonical = CanonicalDocument.model_validate(
        {
            "manifest": json.loads((root / str(view.canonical_contract_manifest_path)).read_text()),
            "objects": [json.loads(line) for line in (root / str(view.canonical_contract_objects_path)).read_text().splitlines()],
            "relations": [json.loads(line) for line in (root / str(view.canonical_contract_relations_path)).read_text().splitlines()],
        }
    )
    figure = next(
        item
        for item in canonical.objects
        if item.object_type.value == "figure"
        and item.representation_status.value == "complete"
        and item.attributes.get("gold_evidence_scope") == "caption_and_text_only"
    )
    equation = next(
        item
        for item in canonical.objects
        if item.object_type.value == "equation"
        and item.representation_status.value == "complete"
        and item.attributes.get("placement") == "block"
    )
    for evidence_id, object_ in (("figure", figure), ("equation", equation)):
        record = BundleV3EvidenceRecord(
            evidence_key=f"gold-revision-rich-000001:{evidence_id}",
            release_id="dataset-release-rich",
            case_id="case-rich",
            gold_id="gold-rich",
            gold_revision_id="gold-revision-rich-000001",
            evidence_id=evidence_id,
            role=EvidenceRole.REQUIRED,
            origin="gold_payload",
            source_evidence=GoldEvidence(evidence_id=evidence_id, canonical_object_id=object_.object_id, role=EvidenceRole.REQUIRED),
            canonical=object_,
        )
        assert BundleV3EvidenceRecord.model_validate_json(record.model_dump_json()).canonical == object_
    assert figure.attributes["gold_evidence_scope"] == "caption_and_text_only"
    assert figure.attributes["visual_semantic_status"] == "unverified"
    assert figure.gold_evidence_eligible is False
    assert equation.attributes["raw_omml_sha256"]
    assert equation.attributes["omml_tree"]
    assert equation.gold_evidence_eligible is False


def test_bundle_v3_tamper_and_release_snapshot_mismatch_fail_closed(tmp_path: Path) -> None:
    _authoring, formal, release, store, _target = _release_context(tmp_path)
    bundle = store.build_from_release(release.release_id)
    (bundle.root / "private/gold.jsonl").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(BundleV3IntegrityError, match="checksums"):
        load_bundle_v3(bundle.root)

    source_snapshot = formal.releases.source_snapshot(release.release_id)
    source_snapshot.write_bytes(source_snapshot.read_bytes() + b"tampered")
    with pytest.raises(BundleV3IntegrityError, match="source snapshot digest"):
        store.build_from_release(release.release_id)


def test_offline_bundle_v3_is_not_a_production_runtime_dependency() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src" / "rag_eval"
    for relative in (
        "runtime_admission.py",
        "execution.py",
        "service.py",
        "api.py",
    ):
        source = (source_root / relative).read_text(encoding="utf-8")
        assert "bundle_v3" not in source
        assert "BundleV3" not in source
