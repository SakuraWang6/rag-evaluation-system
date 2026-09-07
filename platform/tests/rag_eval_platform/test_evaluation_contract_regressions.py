"""P1 evaluation-contract regressions.

These tests intentionally describe the post-P0 evidence contract.  They are
kept separate from the legacy evaluator tests so a red result identifies a
contract gap rather than changing the historical baseline in place.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from rag_eval.contracts.adapter import RAGEvidenceItem, RAGResult
from rag_eval.contracts.dataset import (
    GoldAnswer,
    GoldAnswerKind,
    GoldEvidence,
    GoldEvidenceSet,
    ObjectLocator,
    TextSpanLocator,
)
from rag_eval.contracts.run import CaseResult, MetricStatus
from rag_eval.evaluation.engine import evaluate_case
from rag_eval.evaluation.evidence import CorpusEvidenceIndex, match_evidence
from rag_eval.evaluation.metrics import evaluate_retrieval_stages
from rag_eval.run_history import RunHistory
from rag_eval.storage.runs import RunStore


_SPAN_SOURCE = "abcdefghij0123456789"
_SPAN_SOURCE_DIGEST = hashlib.sha256(_SPAN_SOURCE.encode("utf-8")).hexdigest()


def _span_proof(
    start: int,
    end: int,
    *,
    source: str = _SPAN_SOURCE,
    object_id: str = "span-1",
    expected_start: int = 10,
    expected_end: int = 20,
) -> dict[str, object]:
    """Build a source-backed witness for a partial-range fixture.

    The evaluator has not yet frozen the P1 metadata model, so the fixture
    keeps the bridge facts explicit rather than asserting a particular model
    class: schema, complete expected extent, source digest, and the observed
    overlap/witness digest.  Locators and corpus text remain the authoritative
    geometry checks; these fields prevent a future implementation from making
    a bare ``coverage=full`` flag sufficient evidence.
    """

    witness_sha256 = hashlib.sha256(source[start:end].encode("utf-8")).hexdigest()
    return {
        "schema_version": 2,
        "provenance_schema": "canonical-provenance/v2",
        "provenance_status": "full",
        "provenance_reason": None,
        "source_sha256": (
            _SPAN_SOURCE_DIGEST
            if source == _SPAN_SOURCE
            else hashlib.sha256(source.encode("utf-8")).hexdigest()
        ),
        "runtime_source_span": {"start": start, "end": end},
        "content_sha256": witness_sha256,
        "canonical_object_ids": [object_id],
        "canonical_full_object_ids": [],
        "canonical_partial_object_ids": [object_id],
        "canonical_object_id": object_id,
        "canonical_object_type": "text_span",
        "canonical_object_status": "verified",
        "canonical_object_coverage": "partial",
        "coverage": "partial",
        "canonical_alignment_method": "fixture_source_span",
        "canonical_object_span": {"start": expected_start, "end": expected_end},
        "expected_extent": {
            "document_id": "doc-1",
            "start": expected_start,
            "end": expected_end,
            "coordinate_system": "utf8_codepoint_half_open",
        },
        "canonical_overlap_span": {"start": start, "end": end},
        "canonical_witness_sha256": witness_sha256,
    }


def _metric(metrics, metric_id: str):
    return next(item for item in metrics if item.metric_id == metric_id)


def _object_gold(
    evidence_ids: list[str],
    *,
    paths: list[list[list[str]]] | None = None,
    required_ids: list[str] | None = None,
) -> GoldEvidenceSet:
    evidence = [
        GoldEvidence(
            evidence_id=evidence_id,
            document_id="doc-1",
            locator=ObjectLocator(object_type="fact", object_id=evidence_id),
            canonical_value=evidence_id,
        )
        for evidence_id in evidence_ids
    ]
    return GoldEvidenceSet(
        gold_evidence_set_id="set-1",
        evidence=evidence,
        required_groups=[
            [evidence_id] for evidence_id in (required_ids or evidence_ids)
        ],
        mses_paths=paths,
    )


def _object_item(evidence_id: str, rank: int) -> RAGEvidenceItem:
    return RAGEvidenceItem(
        item_id=f"item-{evidence_id}-{rank}",
        rank=rank,
        document_id="doc-1",
        content=evidence_id,
        locator=ObjectLocator(object_type="fact", object_id=evidence_id),
    )


def test_provenance_missing_in_raw_does_not_mask_observed_ranked_context(tmp_path) -> None:
    """A stage-local bridge failure must not make the whole Case unavailable."""

    evidence_set = _object_gold(["e-1", "e-2"])
    raw_unknown = RAGEvidenceItem(
        item_id="raw-e-2",
        rank=2,
        document_id="doc-1",
        content="e-2",
        metadata={
            "provenance_status": "missing",
            "provenance_reason": "trace_ingestion_mapping_mismatch",
        },
    )
    result = RAGResult(
        answer="answer",
        raw_retrieval=[_object_item("e-1", 1), raw_unknown],
        ranked_retrieval=[_object_item("e-1", 1), _object_item("e-2", 2)],
        final_context=[_object_item("e-1", 1), _object_item("e-2", 2)],
    )
    answer = GoldAnswer(
        gold_answer_id="a-1", kind=GoldAnswerKind.TEXT, canonical="answer"
    )
    metrics = evaluate_case(
        result,
        answer,
        evidence_set,
        CorpusEvidenceIndex({"doc-1": "e-1 e-2"}),
        k_values=(2,),
    )
    case = CaseResult(
        case_id="case-1",
        status="completed",
        question="q",
        gold_answer=answer,
        gold_evidence_set=evidence_set,
        rag_result=result,
        metrics=metrics,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )

    projected = RunHistory(RunStore(tmp_path / "runs"))._project_case_for_product(
        "run-1", case
    )

    # The unresolved required item may remain unavailable/needs-review in the
    # raw projection, but it must not rewrite independently observed stages.
    assert _metric(projected.metrics, "raw_recall@2").status in {
        MetricStatus.UNAVAILABLE,
        MetricStatus.NEEDS_REVIEW,
    }
    assert _metric(projected.metrics, "ranked_recall@2").status == MetricStatus.OBSERVED
    assert _metric(projected.metrics, "context_recall@2").status == MetricStatus.OBSERVED
    assert _metric(projected.metrics, "answer_accuracy").status == MetricStatus.OBSERVED
    assert _metric(projected.metrics, "answer_groundedness").status == MetricStatus.OBSERVED


def test_source_digest_tamper_cannot_prove_exact_locator() -> None:
    evidence = GoldEvidence(
        evidence_id="source-digest",
        document_id="doc-1",
        locator=TextSpanLocator(start=10, end=20),
        canonical_value="0123456789",
    )
    metadata = _span_proof(
        10,
        20,
        object_id="source-digest",
    )
    metadata["source_sha256"] = "0" * 64
    item = RAGEvidenceItem(
        item_id="tampered-source-digest",
        rank=1,
        document_id="doc-1",
        content=_SPAN_SOURCE[10:20],
        locator=TextSpanLocator(start=10, end=20),
        metadata=metadata,
    )

    assert (
        match_evidence(
            item,
            evidence,
            CorpusEvidenceIndex({"doc-1": _SPAN_SOURCE}),
        )
        is None
    )


def test_trace_content_digest_tamper_cannot_prove_exact_locator() -> None:
    evidence = GoldEvidence(
        evidence_id="trace-digest",
        document_id="doc-1",
        locator=TextSpanLocator(start=10, end=20),
        canonical_value="0123456789",
    )
    metadata = _span_proof(10, 20, object_id="trace-digest")
    metadata["content_sha256"] = hashlib.sha256(b"tampered").hexdigest()
    item = RAGEvidenceItem(
        item_id="tampered-trace-content",
        rank=1,
        document_id="doc-1",
        content=_SPAN_SOURCE[10:20],
        locator=TextSpanLocator(start=10, end=20),
        metadata=metadata,
    )

    assert (
        match_evidence(
            item,
            evidence,
            CorpusEvidenceIndex({"doc-1": _SPAN_SOURCE}),
        )
        is None
    )


def test_complete_alternative_path_is_not_penalized_by_unmatched_alternative() -> None:
    evidence_set = _object_gold(
        ["a-1", "a-2", "b-1", "b-2", "near-miss"],
        paths=[[["a-1"], ["a-2"]], [["b-1"], ["b-2"]]],
        required_ids=["a-1", "a-2", "b-1", "b-2"],
    )
    result = RAGResult(
        raw_retrieval=[
            _object_item("b-1", 1),
            _object_item("a-1", 4),
            _object_item("a-2", 5),
            _object_item("near-miss", 6),
        ],
        ranked_retrieval=[
            _object_item("b-1", 1),
            _object_item("a-1", 4),
            _object_item("a-2", 5),
            _object_item("near-miss", 6),
        ],
        final_context=[],
    )

    metrics = evaluate_retrieval_stages(
        result,
        evidence_set,
        CorpusEvidenceIndex({"doc-1": "a-1 a-2 b-1 b-2 near-miss"}),
        k_values=(1, 5),
    )

    # At five, path A is complete.  Missing b-2 and the non-required
    # near-miss must not lower the valid path's recall or MRR.
    assert _metric(metrics, "ranked_recall@5").value == 1.0
    assert _metric(metrics, "ranked_mrr").value == 1 / 5
    # A near-miss is diagnostic only and cannot become a required hit.
    assert _metric(metrics, "ranked_recall@1").value == 0.5


def test_complete_alternative_path_survives_unknown_chunk_in_other_path() -> None:
    """An unknown B-path item must not hide a complete A-path result."""

    evidence_set = _object_gold(
        ["a-1", "a-2", "b-1", "b-2"],
        paths=[[["a-1"], ["a-2"]], [["b-1"], ["b-2"]]],
        required_ids=["a-1", "a-2", "b-1", "b-2"],
    )
    unknown_b2 = RAGEvidenceItem(
        item_id="unknown-b-2",
        rank=2,
        document_id="doc-1",
        content="b-2",
        metadata={
            "provenance_status": "missing",
            "provenance_reason": "trace_ingestion_mapping_mismatch",
        },
    )
    result = RAGResult(
        raw_retrieval=[
            _object_item("b-1", 1),
            unknown_b2,
            _object_item("a-1", 4),
            _object_item("a-2", 5),
        ],
        ranked_retrieval=[
            _object_item("b-1", 1),
            unknown_b2,
            _object_item("a-1", 4),
            _object_item("a-2", 5),
        ],
        final_context=[],
    )

    metrics = evaluate_retrieval_stages(
        result,
        evidence_set,
        CorpusEvidenceIndex({"doc-1": "a-1 a-2 b-1 b-2"}),
        k_values=(5,),
    )

    assert _metric(metrics, "ranked_recall@5").status == MetricStatus.OBSERVED
    assert _metric(metrics, "ranked_recall@5").value == 1.0
    assert _metric(metrics, "ranked_mrr").value == 1 / 5


def test_unmapped_near_miss_does_not_hide_complete_required_path() -> None:
    """Near-miss evidence remains diagnostic and cannot poison required MSES."""

    evidence_set = _object_gold(
        ["required-1", "required-2", "near-miss"],
        paths=[[["required-1"], ["required-2"]]],
        required_ids=["required-1", "required-2"],
    )
    unknown_near_miss = RAGEvidenceItem(
        item_id="unknown-near-miss",
        rank=2,
        document_id="doc-1",
        content="near-miss",
        metadata={
            "provenance_status": "missing",
            "provenance_reason": "trace_ingestion_mapping_mismatch",
        },
    )
    result = RAGResult(
        raw_retrieval=[
            _object_item("required-1", 1),
            unknown_near_miss,
            _object_item("required-2", 3),
        ],
        ranked_retrieval=[
            _object_item("required-1", 1),
            unknown_near_miss,
            _object_item("required-2", 3),
        ],
        final_context=[],
    )

    metrics = evaluate_retrieval_stages(
        result,
        evidence_set,
        CorpusEvidenceIndex({"doc-1": "required-1 required-2 near-miss"}),
        k_values=(3,),
    )

    assert _metric(metrics, "ranked_recall@3").status == MetricStatus.OBSERVED
    assert _metric(metrics, "ranked_recall@3").value == 1.0
    assert _metric(metrics, "ranked_mrr").value == 1 / 3


def test_projected_objects_keep_source_chunk_rank_and_identity() -> None:
    """One runtime chunk may project two objects without inventing ranks."""

    evidence_set = _object_gold(["object-1", "object-2"])
    shared_metadata = {
        "schema_version": 2,
        "provenance_status": "full",
        "runtime_chunk_id": "chunk-1",
        "canonical_object_ids": ["object-1", "object-2"],
        "canonical_full_object_ids": ["object-1", "object-2"],
        "provenance_projection_count": 2,
    }
    projected = [
        RAGEvidenceItem(
            item_id="ranked:chunk-1:object-1",
            native_id="chunk-1",
            rank=1,
            document_id="doc-1",
            content="object-1",
            locator=ObjectLocator(object_type="fact", object_id="object-1"),
            metadata={**shared_metadata, "provenance_projection": 1},
        ),
        RAGEvidenceItem(
            item_id="ranked:chunk-1:object-2",
            native_id="chunk-1",
            rank=1,
            document_id="doc-1",
            content="object-2",
            locator=ObjectLocator(object_type="fact", object_id="object-2"),
            metadata={**shared_metadata, "provenance_projection": 2},
        ),
    ]
    metrics = evaluate_retrieval_stages(
        RAGResult(
            raw_retrieval=projected,
            ranked_retrieval=projected,
            final_context=projected,
        ),
        evidence_set,
        CorpusEvidenceIndex({"doc-1": "object-1 object-2"}),
        k_values=(1,),
    )

    ranked = _metric(metrics, "ranked_recall@1")
    assert [item.rank for item in projected] == [1, 1]
    assert ranked.value == 1.0
    assert ranked.numerator == 2.0
    assert ranked.denominator == 2.0
    assert _metric(metrics, "ranked_mrr").value == 1.0


def test_duplicate_table_content_cannot_substitute_canonical_table_identity() -> None:
    """Identical grids remain distinct when their canonical IDs differ."""

    evidence = GoldEvidence(
        evidence_id="table-17",
        document_id="doc-1",
        locator=ObjectLocator(object_type="table", object_id="table-17"),
        canonical_value="A | B | C",
    )
    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="duplicate-table-set",
        evidence=[evidence],
        required_groups=[["table-17"]],
    )
    duplicate_table = RAGEvidenceItem(
        item_id="table-39",
        rank=1,
        document_id="doc-1",
        content="A | B | C",
        locator=ObjectLocator(object_type="table", object_id="table-39"),
    )
    gold_table = RAGEvidenceItem(
        item_id="table-17",
        rank=2,
        document_id="doc-1",
        content="A | B | C",
        locator=ObjectLocator(object_type="table", object_id="table-17"),
    )
    metrics = evaluate_retrieval_stages(
        RAGResult(
            raw_retrieval=[duplicate_table, gold_table],
            ranked_retrieval=[duplicate_table, gold_table],
            final_context=[duplicate_table, gold_table],
        ),
        evidence_set,
        CorpusEvidenceIndex({"doc-1": "A | B | C\nA | B | C"}),
        k_values=(1, 2),
    )

    assert _metric(metrics, "ranked_recall@1").value == 0.0
    assert _metric(metrics, "ranked_recall@2").value == 1.0
    assert _metric(metrics, "ranked_mrr").value == 1 / 2


def test_partial_text_span_union_only_matches_when_cutoff_covers_full_span() -> None:
    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="span-set",
        evidence=[
            GoldEvidence(
                evidence_id="span-1",
                document_id="doc-1",
                locator=TextSpanLocator(start=10, end=20),
                canonical_value="0123456789",
            )
        ],
        required_groups=[["span-1"]],
    )
    items = [
        RAGEvidenceItem(
            item_id="span-1",
            rank=1,
            document_id="doc-1",
            content="0123",
            locator=TextSpanLocator(start=10, end=14),
            metadata=_span_proof(10, 14, object_id="span-1"),
        ),
        RAGEvidenceItem(
            item_id="span-2",
            rank=2,
            document_id="doc-1",
            content="456",
            locator=TextSpanLocator(start=14, end=17),
            metadata=_span_proof(14, 17, object_id="span-1"),
        ),
        RAGEvidenceItem(
            item_id="span-3",
            rank=3,
            document_id="doc-1",
            content="789",
            locator=TextSpanLocator(start=17, end=20),
            metadata=_span_proof(17, 20, object_id="span-1"),
        ),
    ]
    result = RAGResult(
        raw_retrieval=items,
        ranked_retrieval=items,
        final_context=items,
    )

    metrics = evaluate_retrieval_stages(
        result,
        evidence_set,
        CorpusEvidenceIndex({"doc-1": _SPAN_SOURCE}),
        k_values=(1, 2, 3),
    )

    # Partial coverage is retained as a diagnostic; it cannot be promoted to
    # a required hit until the union covers the complete Gold span.
    assert _metric(metrics, "ranked_recall@1").value == 0.0
    assert _metric(metrics, "ranked_recall@2").value == 0.0
    assert _metric(metrics, "ranked_recall@3").value == 1.0
    assert _metric(metrics, "ranked_mrr").value == 1 / 3


def test_partial_span_gap_cannot_be_treated_as_full_union() -> None:
    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="span-gap-set",
        evidence=[
            GoldEvidence(
                evidence_id="span-gap",
                document_id="doc-1",
                locator=TextSpanLocator(start=10, end=20),
                canonical_value="0123456789",
            )
        ],
        required_groups=[["span-gap"]],
    )
    items = [
        RAGEvidenceItem(
            item_id="gap-left",
            rank=1,
            document_id="doc-1",
            content="0123",
            locator=TextSpanLocator(start=10, end=14),
            metadata=_span_proof(10, 14, object_id="span-gap"),
        ),
        # Offset 14 is missing.  A union implementation must not bridge this
        # gap merely because both ranges overlap the Gold span.
        RAGEvidenceItem(
            item_id="gap-right",
            rank=2,
            document_id="doc-1",
            content="56789",
            locator=TextSpanLocator(start=15, end=20),
            metadata=_span_proof(15, 20, object_id="span-gap"),
        ),
    ]
    metrics = evaluate_retrieval_stages(
        RAGResult(raw_retrieval=items, ranked_retrieval=items, final_context=items),
        evidence_set,
        CorpusEvidenceIndex({"doc-1": _SPAN_SOURCE}),
        k_values=(2,),
    )

    assert _metric(metrics, "ranked_recall@2").value == 0.0
    assert _metric(metrics, "ranked_mrr").value == 0.0


def test_partial_span_outside_gold_range_is_not_clipped_into_a_match() -> None:
    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="span-tamper-set",
        evidence=[
            GoldEvidence(
                evidence_id="span-tamper",
                document_id="doc-1",
                locator=TextSpanLocator(start=10, end=20),
                canonical_value="0123456789",
            )
        ],
        required_groups=[["span-tamper"]],
    )
    items = [
        RAGEvidenceItem(
            item_id="tamper-left",
            rank=1,
            document_id="doc-1",
            content="01234",
            locator=TextSpanLocator(start=10, end=15),
            metadata=_span_proof(
                10,
                15,
                source=f"{_SPAN_SOURCE}+tampered",
                object_id="span-tamper",
            ),
        ),
        # This claims bytes beyond the Gold target.  It is a malformed
        # coverage witness, not a range that may be clipped to [15, 20].
        RAGEvidenceItem(
            item_id="tamper-right",
            rank=2,
            document_id="doc-1",
            content=f"{_SPAN_SOURCE[15:20]}+tamp",
            locator=TextSpanLocator(start=15, end=25),
            metadata=_span_proof(
                15,
                25,
                source=f"{_SPAN_SOURCE}+tampered",
                object_id="span-tamper",
            ),
        ),
    ]
    metrics = evaluate_retrieval_stages(
        RAGResult(raw_retrieval=items, ranked_retrieval=items, final_context=items),
        evidence_set,
        CorpusEvidenceIndex({"doc-1": f"{_SPAN_SOURCE}+tampered"}),
        k_values=(2,),
    )

    assert _metric(metrics, "ranked_recall@2").value == 0.0
    assert _metric(metrics, "ranked_mrr").value == 0.0


def test_partial_span_piece_after_cutoff_cannot_complete_union() -> None:
    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="span-cutoff-set",
        evidence=[
            GoldEvidence(
                evidence_id="span-cutoff",
                document_id="doc-1",
                locator=TextSpanLocator(start=10, end=20),
                canonical_value="0123456789",
            )
        ],
        required_groups=[["span-cutoff"]],
    )
    items = [
        RAGEvidenceItem(
            item_id="cutoff-left",
            rank=1,
            document_id="doc-1",
            content="01234",
            locator=TextSpanLocator(start=10, end=15),
            metadata=_span_proof(10, 15, object_id="span-cutoff"),
        ),
        RAGEvidenceItem(
            item_id="cutoff-right",
            rank=3,
            document_id="doc-1",
            content="56789",
            locator=TextSpanLocator(start=15, end=20),
            metadata=_span_proof(15, 20, object_id="span-cutoff"),
        ),
    ]
    metrics = evaluate_retrieval_stages(
        RAGResult(raw_retrieval=items, ranked_retrieval=items, final_context=items),
        evidence_set,
        CorpusEvidenceIndex({"doc-1": _SPAN_SOURCE}),
        k_values=(2, 3),
    )

    assert _metric(metrics, "ranked_recall@2").value == 0.0
    assert _metric(metrics, "ranked_recall@3").value == 1.0
    assert _metric(metrics, "ranked_mrr").value == 1 / 3


def test_whole_table_scope_cannot_be_satisfied_by_one_cell() -> None:
    from rag_eval.contracts.dataset import TableCellLocator

    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="table-set",
        evidence=[
            GoldEvidence(
                evidence_id="table-1",
                document_id="doc-1",
                locator=ObjectLocator(object_type="table", object_id="table-1"),
                canonical_value="A | B | C",
            )
        ],
        required_groups=[["table-1"]],
    )
    cell = RAGEvidenceItem(
        item_id="cell-1",
        rank=1,
        document_id="doc-1",
        content="A",
        locator=TableCellLocator(table_id="table-1", row=1, column=1),
    )
    metrics = evaluate_retrieval_stages(
        RAGResult(raw_retrieval=[cell], ranked_retrieval=[cell], final_context=[cell]),
        evidence_set,
        CorpusEvidenceIndex({"doc-1": "A | B | C"}),
        k_values=(1,),
    )

    assert _metric(metrics, "ranked_recall@1").value == 0.0


def test_table_cell_scope_requires_the_same_physical_cell_identity() -> None:
    from rag_eval.contracts.dataset import TableCellLocator

    evidence = GoldEvidence(
        evidence_id="table-17-cell-r2-c5",
        document_id="doc-1",
        locator=TableCellLocator(table_id="table-17", row=2, column=5),
        canonical_value="42",
    )
    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="table-cell-set",
        evidence=[evidence],
        required_groups=[["table-17-cell-r2-c5"]],
    )
    same_text_wrong_scope = RAGEvidenceItem(
        item_id="table-17-whole",
        rank=1,
        document_id="doc-1",
        content="42",
        locator=ObjectLocator(object_type="table", object_id="table-17"),
    )
    exact_cell = RAGEvidenceItem(
        item_id="table-17-cell-r2-c5",
        rank=2,
        document_id="doc-1",
        content="42",
        locator=TableCellLocator(table_id="table-17", row=2, column=5),
    )
    metrics = evaluate_retrieval_stages(
        RAGResult(
            raw_retrieval=[same_text_wrong_scope, exact_cell],
            ranked_retrieval=[same_text_wrong_scope, exact_cell],
            final_context=[same_text_wrong_scope, exact_cell],
        ),
        evidence_set,
        CorpusEvidenceIndex({"doc-1": "42"}),
        k_values=(1, 2),
    )

    assert _metric(metrics, "ranked_recall@1").value == 0.0
    assert _metric(metrics, "ranked_recall@2").value == 1.0
    assert _metric(metrics, "ranked_mrr").value == 1 / 2
