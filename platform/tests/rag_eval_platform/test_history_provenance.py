from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from rag_eval.evaluation.evidence import (
    CorpusEvidenceIndex as EvaluationCorpusEvidenceIndex,
)
from rag_eval.history_provenance.acceptance import (
    PROJECTION_ACCEPTANCE_STATUS,
    accepted_projection_receipt,
    write_historical_rescore_projection_acceptance,
)
from rag_eval.history_provenance.baseline import (
    capture_immutable_baseline,
    verify_immutable_baseline,
)
from rag_eval.history_provenance.reconstruction import (
    _json_array_spans,
    _mapping_for_chunk,
    build_historical_localization_matrix,
    build_production_localization_audit,
    reconstruct_historical_provenance,
    write_derived_json,
    write_reconstructed_provenance,
)
from rag_eval.history_provenance.rescore import rescore_historical_run

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "history_provenance" / "v1"
HISTORY_ASSERTION_TESTS = {
    "test_real_reconstruction_proves_stream_and_native_join",
    "test_real_matrix_is_exact_gold_not_semantic_duplicate",
    "test_split_table_has_partial_table_and_full_row_cells",
    "test_shared_evidence_index_round_trips_map_and_digest",
    "test_production_localizer_is_audited_without_catalog_bypass",
    "test_baseline_and_destination_guards_are_read_only",
    "test_real_versioned_rescore_uses_production_metrics_and_pins_inputs",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@pytest.fixture
def history_fixture(tmp_path: Path) -> dict[str, Path]:
    manifest = json.loads((FIXTURE_ROOT / "fixture-manifest.json").read_text())
    assert manifest["schema_version"] == "history-provenance-fixture/1"
    assert manifest["privacy"] == {
        "contains_external_business_data": False,
        "contains_original_document_hashes": False,
        "contains_original_filenames": False,
        "synthetic": True,
    }
    assert set(manifest["assertion_coverage"]) == HISTORY_ASSERTION_TESTS

    declared = {item["path"]: item for item in manifest["files"]}
    actual = {
        path.relative_to(FIXTURE_ROOT).as_posix()
        for path in FIXTURE_ROOT.rglob("*")
        if path.is_file() and path.name != "fixture-manifest.json"
    }
    assert actual == set(declared)
    prohibited = (b"/Users/", b".rag-eval-", b"pilot-case-")
    for relative, expected in declared.items():
        path = FIXTURE_ROOT / relative
        assert not path.is_symlink()
        assert path.stat().st_size == expected["size_bytes"]
        assert _sha256(path) == expected["sha256"]
        content = path.read_bytes()
        assert all(marker not in content for marker in prohibited)

    copied = tmp_path / "history-provenance-v1"
    shutil.copytree(FIXTURE_ROOT, copied)
    return {
        "root": copied,
        "run": copied / "run",
        "baseline": copied / "immutable-baseline.json",
        "map": copied / "derived" / "provenance-map.json",
        "acceptance": copied / "derived" / "map-acceptance.json",
        "matrix": copied / "derived" / "localization-matrix.json",
    }


def test_json_array_spans_keep_nested_array_endpoints() -> None:
    encoded = '[["a", 20], ["b", 100]]'
    spans = _json_array_spans(encoded)
    assert [encoded[start:end] for start, end in spans] == ['["a", 20]', '["b", 100]']
    assert spans[0][1] < spans[1][0]


def test_projection_acceptance_pins_the_offline_rescore_and_current_baseline(
    tmp_path: Path,
) -> None:
    run = tmp_path / "runs" / "historical-run"
    run.mkdir(parents=True)
    (run / "case.json").write_text('{"case":"retained"}\n', encoding="utf-8")
    baseline = capture_immutable_baseline(run, tmp_path / "baseline")
    verification = verify_immutable_baseline(run, baseline.path).as_dict()
    rescore = tmp_path / "derived" / "historical-rescore-v1.json"
    rescore.parent.mkdir(parents=True)
    rescore.write_text(
        json.dumps(
            {
                "schema_version": "historical-rescore/1",
                "status": "UNVERIFIED",
                "run_id": "historical-run",
                "rescore_identity": "rescore-pin",
                "inputs": {
                    "source": {
                        "source_docx": {"path": "/source.docx", "sha256": "a" * 64},
                        "canonical_jsonl": {
                            "path": "/source.jsonl",
                            "sha256": "b" * 64,
                        },
                    },
                    "map": {"file_sha256": "c" * 64},
                    "cases": {"files": {"case.json": "d" * 64}},
                },
                "baseline_verification": verification,
                "production_index": {
                    "catalog_verified": True,
                    "map_digest_verified": True,
                    "source_pins_verified": True,
                },
                "execution_scope": {
                    "retrieval_rerun": False,
                    "answer_generation_rerun": False,
                    "lightrag_rerun": False,
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    receipt_path = (
        tmp_path / "derived" / "historical-rescore-v1-projection-acceptance-p2.json"
    )

    written = write_historical_rescore_projection_acceptance(
        run,
        rescore,
        receipt_path,
        reviewer="root-reviewer",
        note="Pinned inputs and baseline were independently checked.",
    )

    assert written == receipt_path
    accepted = accepted_projection_receipt(
        written,
        run_dir=run,
        run_id="historical-run",
        rescore_path=rescore,
        rescore_identity="rescore-pin",
    )
    assert accepted is not None
    assert accepted["status"] == PROJECTION_ACCEPTANCE_STATUS
    assert accepted["scope"]["worker_runtime_verified"] is False

    (run / "case.json").write_text('{"case":"changed"}\n', encoding="utf-8")
    assert (
        accepted_projection_receipt(
            written,
            run_dir=run,
            run_id="historical-run",
            rescore_path=rescore,
            rescore_identity="rescore-pin",
        )
        is None
    )


def test_real_reconstruction_proves_stream_and_native_join(
    history_fixture: dict[str, Path],
) -> None:
    run = history_fixture["run"]
    result = reconstruct_historical_provenance(run, strict=True)
    history = result["history_reconstruction"]
    assert history["stream_exact"] is True
    assert history["lineage_integrity_ok"] is True
    assert history["method"] == "historical_structural_exact_stream"
    assert history["historical_reparse_exact_stream"] is False
    assert history["merged_stream_length"] == 1288
    assert history["native_table_count"] == 2
    assert len(result["runtime_chunks"]) == 24

    statuses = {
        status: sum(
            1
            for item in result["runtime_chunks"].values()
            if item["provenance_status"] == status
        )
        for status in ("full", "partial", "missing")
    }
    assert statuses == {"full": 21, "partial": 2, "missing": 1}
    table_a = result["object_catalog"]["doc-synthetic-history-v1:table:00001"]
    table_b = result["object_catalog"]["doc-synthetic-history-v1:table:00002"]
    assert table_a["source_coordinates"]["body_ordinal"] == 10
    assert table_b["source_coordinates"]["body_ordinal"] == 16
    assert table_a["known_native_chunk_ids"] != table_b["known_native_chunk_ids"]


def test_real_matrix_is_exact_gold_not_semantic_duplicate(
    history_fixture: dict[str, Path],
) -> None:
    run = history_fixture["run"]
    reconstruction = reconstruct_historical_provenance(run, strict=True)
    matrix = build_historical_localization_matrix(reconstruction, run)
    assert matrix["evidence_item_count"] == 19
    assert matrix["decision_count"] == 57
    assert matrix["status_counts"] == {
        "matched": 43,
        "partial": 0,
        "retrieval_missed": 14,
        "provenance_missing": 0,
    }

    rows = {(row["case_id"], row["evidence_id"]): row for row in matrix["rows"]}
    for key in (
        ("fixture-case-06", "fixture-evidence-16"),
        ("fixture-case-07", "fixture-evidence-17"),
        ("fixture-case-08", "fixture-evidence-19"),
    ):
        assert all(
            stage["status"] == "retrieval_missed"
            for stage in rows[key]["stages"].values()
        )


def test_split_table_has_partial_table_and_full_row_cells(
    history_fixture: dict[str, Path],
) -> None:
    run = history_fixture["run"]
    result = reconstruct_historical_provenance(run, strict=True)
    chunk = result["runtime_chunks"]["chunk-table-a-row-1"]
    assert chunk["provenance_status"] == "partial"
    table_id = "doc-synthetic-history-v1:table:00001"
    assert chunk["objects"][table_id]["coverage"] == "partial"
    assert table_id not in chunk["canonical_full_object_ids"]
    assert any(
        result["object_catalog"][object_id]["object_type"] == "row"
        for object_id in chunk["canonical_full_object_ids"]
    )


def test_shared_evidence_index_round_trips_map_and_digest(
    history_fixture: dict[str, Path],
) -> None:
    run = history_fixture["run"]
    result = reconstruct_historical_provenance(run, strict=True)
    document_id = next(iter(result["documents"]))
    full_doc_id = result["history_reconstruction"]["full_doc_id"]
    index = EvaluationCorpusEvidenceIndex.from_provenance_map(
        result,
        expected_map_digest=result["map_digest"],
        source_digests={document_id: result["documents"][document_id]["source_sha256"]},
        runtime_documents={document_id: result["runtime_documents"][full_doc_id]},
    )
    assert index.catalog_verified is True
    assert index.map_digest_verified is True
    assert index.has_verified_object(document_id, f"{document_id}:table:00001")
    assert index.runtime_ids_for(document_id, f"{document_id}:table:00001")


def test_production_localizer_is_audited_without_catalog_bypass(
    history_fixture: dict[str, Path],
) -> None:
    run = history_fixture["run"]
    result = reconstruct_historical_provenance(run, strict=True)
    matrix = build_historical_localization_matrix(result, run)
    audit = build_production_localization_audit(result, run, helper_matrix=matrix)
    assert audit["catalog_verified"] is True
    assert audit["map_digest_verified"] is True
    assert audit["decision_count"] == 57
    assert audit["helper_status_counts"] == {
        "matched": 43,
        "partial": 0,
        "retrieval_missed": 14,
        "provenance_missing": 0,
    }
    assert audit["status_counts"] == audit["helper_status_counts"]
    assert audit["difference_count"] == 0
    assert audit["differences"] == []
    assert all(all(row["comparison"].values()) for row in audit["rows"])


def test_baseline_and_destination_guards_are_read_only(
    tmp_path: Path,
    history_fixture: dict[str, Path],
) -> None:
    run = history_fixture["run"]
    verification = verify_immutable_baseline(run, history_fixture["baseline"])
    assert verification.ok is True
    with pytest.raises(ValueError):
        write_derived_json(run, run / "must-not-write.json", {})
    with pytest.raises(ValueError):
        write_reconstructed_provenance(
            run, tmp_path, filename=str(run / "must-not-write.json")
        )
    with pytest.raises(ValueError):
        write_reconstructed_provenance(
            run,
            run.parent,
            filename=f"{run.name}/must-not-write-relative.json",
        )
    with pytest.raises(ValueError):
        write_derived_json(
            run,
            run.parent / "derived-output" / ".." / run.name / "must-not-write.json",
            {},
        )


def test_explicit_bad_span_cannot_fall_through_to_table_recovery() -> None:
    structure = {
        "merged_stream": '<table id="native">[["x"]]</table>',
        "canonical_by_id": {},
        "extents": {},
        "source_integrity_ok": True,
        "full_doc_id": "doc-runtime",
        "native_render": {},
        "native_to_table": {},
        "members_by_table": {},
        "block_infos": [],
        "object_order": {},
    }
    mapping = _mapping_for_chunk(
        chunk_id="chunk-tampered",
        item={
            "content": '<table id="native">[["x"]]</table>',
            "source_span": {"start": 0, "end": 1},
            "sidecar": {"type": "table", "id": "native"},
        },
        structure=structure,
    )
    assert mapping["provenance_status"] == "missing"
    assert mapping["provenance_reason"] == "source_span_content_digest_mismatch"
    assert mapping["canonical_object_ids"] == []


def test_real_versioned_rescore_uses_production_metrics_and_pins_inputs(
    history_fixture: dict[str, Path],
) -> None:
    run = history_fixture["run"]
    value = rescore_historical_run(
        run,
        history_fixture["map"],
        map_acceptance_path=history_fixture["acceptance"],
        matrix_path=history_fixture["matrix"],
        baseline_path=history_fixture["baseline"],
    )
    assert value["status"] == "UNVERIFIED"
    assert value["method"] == "historical_production_evaluate_case"
    assert value["case_count"] == 8
    assert value["production_index"] == {
        "loaded_once": True,
        "catalog_verified": True,
        "map_digest_verified": True,
        "source_pins_verified": True,
        "document_id": "doc-synthetic-history-v1",
        "object_count": 34,
        "runtime_chunk_count": 24,
    }
    assert value["baseline_verification"]["ok"] is True
    assert value["baseline_verification"]["mismatches"] == []
    assert value["execution_scope"] == {
        "source_case_artifacts_reused": True,
        "retrieval_rerun": False,
        "answer_generation_rerun": False,
        "lightrag_rerun": False,
        "production_evaluate_case_invoked": True,
    }
    assert value["summary_policy"]["matrix_role"].startswith("19 Gold x 3 stages = 57")
    assert value["matrix"]["decision_count"] == 57
    assert value["matrix"]["status_counts"] == {
        "matched": 43,
        "partial": 0,
        "retrieval_missed": 14,
        "provenance_missing": 0,
    }
    assert value["localization_summary"]["matrix_19_gold_x_3_stages"]["by_stage"] == {
        "raw_retrieval": {
            "matched": 15,
            "partial": 0,
            "retrieval_missed": 4,
            "provenance_missing": 0,
            "denominator": 19,
        },
        "ranked_retrieval": {
            "matched": 15,
            "partial": 0,
            "retrieval_missed": 4,
            "provenance_missing": 0,
            "denominator": 19,
        },
        "final_context": {
            "matched": 13,
            "partial": 0,
            "retrieval_missed": 6,
            "provenance_missing": 0,
            "denominator": 19,
        },
    }
    assert (
        value["localization_summary"]["production_selected_path_clauses"]["by_stage"][
            "context"
        ]["matched"]
        == 13
    )
    assert (
        value["localization_summary"]["production_selected_path_clauses"]["by_stage"][
            "context"
        ]["denominator"]
        == 19
    )
    assert set(value["source_drift"]) == {
        "detected",
        "pinned_from_map_acceptance",
        "current",
        "mismatches",
        "note",
    }
    assert value["after_summary"]["metrics"]["raw_recall@3"]["value"] == pytest.approx(
        17 / 24
    )
    assert value["after_summary"]["metrics"]["context_recall@3"][
        "value"
    ] == pytest.approx(5 / 8)
    assert all(
        case["metric_changes"]
        and case["metrics_before"]
        and case["metrics_after"]
        and case["stage_localization"]
        for case in value["cases"]
    )
    missed_case = next(
        case for case in value["cases"] if case["case_id"] == "fixture-case-06"
    )
    missed_gold = next(
        row
        for row in missed_case["stage_localization"]
        if row["evidence_id"] == "fixture-evidence-16"
    )
    assert all(
        stage["status"] == "retrieval_missed"
        for stage in missed_gold["stages"].values()
    )
