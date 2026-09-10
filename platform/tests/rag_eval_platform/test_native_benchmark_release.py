from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from rag_eval.authoring.ledger import (
    EvidenceRole,
    GoldAnswer,
    GoldEvidence,
    GoldPayload,
    ReviewDecision,
    TargetKind,
)
from rag_eval.contracts.benchmark import (
    BenchmarkEvidenceRoleV2,
    native_benchmark_snapshot_digest,
)
from rag_eval.datasets.formal import FormalDatasetError
from tests.rag_eval_platform.test_formal_release_lineage import (
    _approve,
    _case_id,
    _workflow,
)


def _release(tmp_path: Path):
    authoring, dataset, candidate, _resolved, formal, _target = _workflow(tmp_path)
    _approve(authoring, dataset, candidate)
    release = formal.freeze(
        dataset.authoring_dataset_id,
        release_version="1.0.0",
        case_ids=(_case_id(formal, candidate),),
        actor="release-manager",
    )
    return authoring, dataset, candidate, formal, release


def test_native_benchmark_resolves_stably_without_editable_ledger(
    tmp_path: Path,
) -> None:
    authoring, dataset, _candidate, formal, release = _release(tmp_path)

    first = formal.resolve_native_benchmark(release.release_id)
    second = formal.resolve_native_benchmark(release.release_id)

    assert first == second
    assert first.snapshot_digest == second.snapshot_digest
    assert first.payload_snapshot_digest == release.payload_snapshot_digest
    assert first.source_identity.source_sha256 == release.document.source_digest
    assert first.case_ids == tuple(item.case_id for item in release.cases)
    assert first.cases[0].gold.gold_revision_id == release.gold[0].gold_revision_id

    shutil.rmtree(authoring.store.workspace(dataset.authoring_dataset_id))
    assert formal.resolve_native_benchmark(release.release_id) == first


def test_native_benchmark_preserves_exact_case_answer_and_mses_without_projection(
    tmp_path: Path,
) -> None:
    _authoring, _dataset, _candidate, formal, release = _release(tmp_path)
    benchmark = formal.resolve_native_benchmark(release.release_id)
    case = benchmark.cases[0]
    payload = formal.releases.payload_snapshots(release.release_id)
    frozen_case = payload["cases"][0]
    frozen_gold = payload["gold"][0]

    assert case.case_id == frozen_case["case_id"]
    assert case.question == frozen_case["draft"]["question"]
    assert case.gold.answer.canonical == frozen_gold["payload"]["answer"]["canonical"]
    assert case.gold.mses_paths
    assert {
        alternative
        for path in case.gold.mses_paths
        for clause in path.clauses
        for alternative in clause.alternatives
    } == {
        item.evidence_id
        for item in case.gold.evidence
        if item.role == BenchmarkEvidenceRoleV2.REQUIRED
    }


def test_native_benchmark_rejects_missing_payload_without_ledger_fallback(
    tmp_path: Path,
) -> None:
    _authoring, _dataset, _candidate, formal, release = _release(tmp_path)
    payload_path = (
        formal.releases.root
        / "payload-snapshots"
        / f"{release.release_id}.json"
    )
    payload_path.unlink()

    with pytest.raises(FormalDatasetError, match="sidecars"):
        formal.resolve_native_benchmark(release.release_id)


def test_native_benchmark_rejects_payload_content_tampering(tmp_path: Path) -> None:
    _authoring, _dataset, _candidate, formal, release = _release(tmp_path)
    payload_path = (
        formal.releases.root
        / "payload-snapshots"
        / f"{release.release_id}.json"
    )
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["cases"][0]["draft"]["question"] = "tampered question"
    payload_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(FormalDatasetError, match="sidecars"):
        formal.resolve_native_benchmark(release.release_id)


@pytest.mark.parametrize("sidecar", ["source", "canonical", "report"])
def test_native_benchmark_rejects_tampered_release_sidecars(
    tmp_path: Path, sidecar: str
) -> None:
    _authoring, _dataset, _candidate, formal, release = _release(tmp_path)
    if sidecar == "source":
        formal.releases.source_snapshot(release.release_id).write_bytes(
            b"tampered DOCX"
        )
    elif sidecar == "canonical":
        path = (
            formal.releases.root
            / "canonical-snapshots"
            / f"{release.release_id}.json"
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        value["objects"][0]["canonical_value"] = "tampered canonical value"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    else:
        path = (
            formal.releases.reports.root
            / f"{release.validation_report_digest}.json"
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        value["dataset_id"] = "tampered-dataset"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(FormalDatasetError):
        formal.resolve_native_benchmark(release.release_id)


def test_native_benchmark_rejects_removed_release_and_selection_mismatch(
    tmp_path: Path,
) -> None:
    _authoring, _dataset, _candidate, formal, release = _release(tmp_path)
    case_id = release.cases[0].case_id

    with pytest.raises(FormalDatasetError, match="selection ID"):
        formal.resolve_native_benchmark(
            release.release_id,
            case_ids=(case_id,),
            expected_case_selection_id="0" * 64,
        )
    with pytest.raises(FormalDatasetError, match="duplicates"):
        formal.resolve_native_benchmark(
            release.release_id,
            case_ids=(case_id, case_id),
        )

    formal.remove_from_catalog(release.release_id, actor="fixture-user")
    with pytest.raises(FormalDatasetError, match="removed"):
        formal.resolve_native_benchmark(release.release_id)


def test_native_benchmark_preserves_every_abstention_scope_as_an_and_clause(
    tmp_path: Path,
) -> None:
    authoring, dataset, candidate, _resolved, formal, _target = _workflow(tmp_path)
    _approve(authoring, dataset, candidate)
    case_id = _case_id(formal, candidate)
    case = formal.ledger.current_case(dataset.authoring_dataset_id, case_id)
    current_gold = formal.ledger.current_gold_for_case(
        dataset.authoring_dataset_id, case_id
    )
    canonical = formal.validator._load_canonical_document(dataset, authoring.store)
    scope_ids = tuple(
        item.object_id
        for item in canonical.objects
        if item.gold_evidence_eligible and item.canonical_value
    )[:2]
    assert len(scope_ids) == 2
    revised = formal.ledger.revise_gold(
        dataset,
        gold_id=current_gold.gold_id,
        payload=GoldPayload(
            answer=GoldAnswer(kind="abstain"),
            evidence=tuple(
                GoldEvidence(
                    evidence_id=f"scope-{index}",
                    canonical_object_id=object_id,
                    role=EvidenceRole.NEGATIVE_SCOPE,
                )
                for index, object_id in enumerate(scope_ids, start=1)
            ),
            negative_scope_object_ids=scope_ids,
            negative_rationale="the complete declared scope contains no answer",
        ),
        actor="authoring-author",
        reason="publish a multi-object abstention scope",
        case_revision=case,
    )
    proposed = formal.ledger.propose_gold(
        dataset,
        gold_id=revised.gold_id,
        actor="authoring-author",
        reason="submit abstention Gold",
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
        reason="reviewed abstention Gold",
    )
    formal.ledger.approve(
        dataset,
        target_kind=TargetKind.GOLD,
        revision_id=reviewed.gold_revision_id,
        approver="fixture-reviewer",
        reason="approve abstention Gold",
    )
    release = formal.freeze(
        dataset.authoring_dataset_id,
        release_version="abstention-1.0.0",
        case_ids=(case_id,),
        actor="release-manager",
    )

    benchmark = formal.resolve_native_benchmark(release.release_id)
    gold = benchmark.cases[0].gold

    assert gold.negative_scope_object_ids == scope_ids
    assert [item.role for item in gold.evidence] == [
        BenchmarkEvidenceRoleV2.NEGATIVE_SCOPE,
        BenchmarkEvidenceRoleV2.NEGATIVE_SCOPE,
    ]
    scoring_path = gold.scoring_paths()[0]
    assert len(scoring_path.clauses) == 2
    assert [item.alternatives for item in scoring_path.clauses] == [
        ("scope-1",),
        ("scope-2",),
    ]


def test_native_benchmark_digest_covers_source_case_and_gold_content(
    tmp_path: Path,
) -> None:
    _authoring, _dataset, _candidate, formal, release = _release(tmp_path)
    benchmark = formal.resolve_native_benchmark(release.release_id)
    values = {
        "release_id": benchmark.release_id,
        "release_digest": benchmark.release_digest,
        "validation_report_digest": benchmark.validation_report_digest,
        "payload_snapshot_digest": benchmark.payload_snapshot_digest,
        "dataset_id": benchmark.dataset_id,
        "release_version": benchmark.release_version,
        "source_identity": benchmark.source_identity,
        "cases": benchmark.cases,
        "case_selection_policy": benchmark.case_selection_policy,
        "case_selection_seed": benchmark.case_selection_seed,
        "case_selection_id": benchmark.case_selection_id,
    }

    changed_source = benchmark.source_identity.model_copy(
        update={"source_sha256": "f" * 64}
    )
    changed_case = benchmark.cases[0].model_copy(
        update={"question": benchmark.cases[0].question + " changed"}
    )
    changed_answer = benchmark.cases[0].gold.answer.model_copy(
        update={"accepted_values": ("different",)}
    )
    changed_gold = benchmark.cases[0].gold.model_copy(
        update={"answer": changed_answer}
    )
    case_with_changed_gold = benchmark.cases[0].model_copy(
        update={"gold": changed_gold}
    )

    assert native_benchmark_snapshot_digest(
        **{**values, "source_identity": changed_source}
    ) != benchmark.snapshot_digest
    assert native_benchmark_snapshot_digest(
        **{**values, "cases": (changed_case,)}
    ) != benchmark.snapshot_digest
    assert native_benchmark_snapshot_digest(
        **{**values, "cases": (case_with_changed_gold,)}
    ) != benchmark.snapshot_digest
