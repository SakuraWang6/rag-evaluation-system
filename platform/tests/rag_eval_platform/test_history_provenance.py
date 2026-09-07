from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag_eval.evaluation.evidence import CorpusEvidenceIndex as EvaluationCorpusEvidenceIndex
from rag_eval.history_provenance.baseline import (
    capture_immutable_baseline,
    verify_immutable_baseline,
)
from rag_eval.history_provenance.acceptance import (
    PROJECTION_ACCEPTANCE_STATUS,
    accepted_projection_receipt,
    write_historical_rescore_projection_acceptance,
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


RUN = Path("/Users/sakura/RAG/.rag-eval-real-benchmark-pilot/runs/2ad4ecfc4c9d4d3ba30baf0ad9f276b3")
BASELINE = Path("/Users/sakura/RAG/rag-eval-platform/docs/evidence-repair/original-run-baseline.json")
V24 = Path("/Users/sakura/RAG/rag-eval-platform/docs/evidence-repair/historical-recovery-v2.4")


def _real_run_or_skip() -> Path:
    if not RUN.is_dir():
        pytest.skip("real benchmark run is not available in this checkout")
    return RUN


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
                        "canonical_jsonl": {"path": "/source.jsonl", "sha256": "b" * 64},
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
    receipt_path = tmp_path / "derived" / "historical-rescore-v1-projection-acceptance-p2.json"

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
    assert accepted_projection_receipt(
        written,
        run_dir=run,
        run_id="historical-run",
        rescore_path=rescore,
        rescore_identity="rescore-pin",
    ) is None


def test_real_reconstruction_proves_stream_and_native_join() -> None:
    run = _real_run_or_skip()
    result = reconstruct_historical_provenance(run, strict=True)
    history = result["history_reconstruction"]
    assert history["stream_exact"] is True
    assert history["lineage_integrity_ok"] is True
    assert history["method"] == "historical_structural_exact_stream"
    assert history["historical_reparse_exact_stream"] is False
    assert history["merged_stream_length"] == 113001
    assert history["native_table_count"] == 83
    assert len(result["runtime_chunks"]) == 196

    statuses = {status: sum(1 for item in result["runtime_chunks"].values() if item["provenance_status"] == status) for status in ("full", "partial", "missing")}
    assert statuses == {"full": 159, "partial": 36, "missing": 1}
    table17 = result["object_catalog"]["doc-7d50899d15356000:table:00017"]
    table39 = result["object_catalog"]["doc-7d50899d15356000:table:00039"]
    assert table17["source_coordinates"]["body_ordinal"] == 420
    assert table39["source_coordinates"]["body_ordinal"] == 733
    assert table17["known_native_chunk_ids"] != table39["known_native_chunk_ids"]


def test_real_matrix_is_exact_gold_not_semantic_duplicate() -> None:
    run = _real_run_or_skip()
    reconstruction = reconstruct_historical_provenance(run, strict=True)
    matrix = build_historical_localization_matrix(reconstruction, run)
    assert matrix["evidence_item_count"] == 19
    assert matrix["decision_count"] == 57
    assert matrix["status_counts"] == {"matched": 43, "partial": 0, "retrieval_missed": 14, "provenance_missing": 0}

    rows = {(row["case_id"], row["evidence_id"]): row for row in matrix["rows"]}
    backup = next(row for key, row in rows.items() if key[0] == "pilot-case-critical-backed-up-data" and "backup-description" in key[1])
    assert all(stage["status"] == "retrieval_missed" for stage in backup["stages"].values())
    good_text = next(row for key, row in rows.items() if key[0] == "pilot-case-good-not-excellent" and "observed-risk" in key[1])
    assert all(stage["status"] == "retrieval_missed" for stage in good_text["stages"].values())
    http = next(row for key, row in rows.items() if key[0] == "pilot-case-http-protocol" and key[1].endswith("required-http"))
    assert all(stage["status"] == "retrieval_missed" for stage in http["stages"].values())


def test_split_table_has_partial_table_and_full_row_cells() -> None:
    run = _real_run_or_skip()
    result = reconstruct_historical_provenance(run, strict=True)
    chunk = result["runtime_chunks"]["doc-cb7c02e61736ce20f0f3025c81e51f69-chunk-043"]
    assert chunk["provenance_status"] == "partial"
    table_id = "doc-7d50899d15356000:table:00019"
    assert chunk["objects"][table_id]["coverage"] == "partial"
    assert table_id not in chunk["canonical_full_object_ids"]
    assert any(result["object_catalog"][object_id]["object_type"] == "row" for object_id in chunk["canonical_full_object_ids"])


def test_shared_evidence_index_round_trips_map_and_digest() -> None:
    run = _real_run_or_skip()
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
    assert index.has_verified_object(document_id, f"{document_id}:table:00017")
    assert index.runtime_ids_for(document_id, f"{document_id}:table:00017")


def test_production_localizer_is_audited_without_catalog_bypass() -> None:
    run = _real_run_or_skip()
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
    assert all(
        all(row["comparison"].values())
        for row in audit["rows"]
    )


def test_baseline_and_destination_guards_are_read_only(tmp_path: Path) -> None:
    run = _real_run_or_skip()
    verification = verify_immutable_baseline(run, BASELINE)
    assert verification.ok is True
    with pytest.raises(ValueError):
        write_derived_json(run, run / "must-not-write.json", {})
    with pytest.raises(ValueError):
        write_reconstructed_provenance(run, tmp_path, filename=str(run / "must-not-write.json"))
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


def test_real_versioned_rescore_uses_production_metrics_and_pins_inputs() -> None:
    run = _real_run_or_skip()
    value = rescore_historical_run(
        run,
        V24 / "historical-provenance-v2.4.json",
        map_acceptance_path=V24 / "historical-recovery-v2.4-acceptance.json",
        matrix_path=V24 / "historical-localization-matrix-v2.4.json",
        baseline_path=BASELINE,
    )
    assert value["status"] == "UNVERIFIED"
    assert value["method"] == "historical_production_evaluate_case"
    assert value["case_count"] == 8
    assert value["production_index"] == {
        "loaded_once": True,
        "catalog_verified": True,
        "map_digest_verified": True,
        "source_pins_verified": True,
        "document_id": "doc-7d50899d15356000",
        "object_count": 8308,
        "runtime_chunk_count": 196,
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
    assert value["summary_policy"]["matrix_role"].startswith(
        "19 Gold x 3 stages = 57"
    )
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
    assert value["localization_summary"]["production_selected_path_clauses"]["by_stage"]["context"]["matched"] == 11
    assert value["localization_summary"]["production_selected_path_clauses"]["by_stage"]["context"]["denominator"] == 16
    assert set(value["source_drift"]) == {
        "detected",
        "pinned_from_map_acceptance",
        "current",
        "mismatches",
        "note",
    }
    assert value["after_summary"]["metrics"]["raw_recall@3"]["value"] == pytest.approx(
        7 / 12
    )
    assert value["after_summary"]["metrics"]["context_recall@3"]["value"] == pytest.approx(
        7 / 12
    )
    assert all(
        case["metric_changes"]
        and case["metrics_before"]
        and case["metrics_after"]
        and case["stage_localization"]
        for case in value["cases"]
    )
    backup = next(
        case
        for case in value["cases"]
        if case["case_id"] == "pilot-case-critical-backed-up-data"
    )
    backup_gold = next(
        row
        for row in backup["stage_localization"]
        if row["evidence_id"].endswith("required-backup-description")
    )
    assert all(
        stage["status"] == "retrieval_missed"
        for stage in backup_gold["stages"].values()
    )
