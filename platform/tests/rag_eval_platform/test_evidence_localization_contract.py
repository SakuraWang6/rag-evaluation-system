"""Focused formal evidence-localization regressions.

These fixtures intentionally use a run-level forward/reverse map.  They are
not a replacement for the real 57-cell acceptance run; they exercise the
identity and coverage invariants that must hold before that run is consumed.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from rag_eval.contracts.adapter import DocumentInput, RAGEvidenceItem, RAGResult
from rag_eval.contracts.dataset import (
    GoldAnswer,
    GoldAnswerKind,
    GoldEvidence,
    GoldEvidenceSet,
    ObjectLocator,
    Question,
    TableCellLocator,
)
from rag_eval.contracts.run import MetricStatus
from rag_eval.evaluation import evidence as evidence_module
from rag_eval.evaluation.engine import evaluate_case
from rag_eval.evaluation.evidence import (
    CorpusEvidenceIndex,
    EvidenceMatchKind,
    LocalizationStatus,
    localize_gold_evidence,
    localize_stage,
    match_evidence,
)
from rag_eval.evaluation.metrics import evaluate_retrieval_stages
from rag_eval.execution import (
    NativeProvenanceContractError,
    corpus_evidence_index_after_ingest,
    validate_native_provenance_contract,
)


DOC_ID = "doc-1"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _extent(start: int, end: int) -> dict[str, object]:
    return {
        "document_id": DOC_ID,
        "coordinate_system": "execution-stream-v1",
        "ranges": [{"start": start, "end": end}],
        "status": "complete",
        "witness_sha256": _sha(f"extent:{start}:{end}"),
    }


def _locator_json(locator: object) -> dict[str, object]:
    return locator.model_dump(mode="json")


def _edge(
    object_id: str,
    object_type: str,
    locator: object,
    extent: dict[str, object],
    *,
    coverage: str = "full",
    overlap: tuple[int, int] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "object_id": object_id,
        "object_type": object_type,
        "document_id": DOC_ID,
        "locator": _locator_json(locator),
        "expected_extent": copy.deepcopy(extent),
        "coverage": coverage,
        "runtime_chunk_id": "placeholder",
    }
    if overlap is not None:
        value["overlap_span"] = {"start": overlap[0], "end": overlap[1]}
    return value


def _formal_map(
    source: str,
    objects: dict[str, dict[str, object]],
    runtime_specs: dict[str, tuple[int, int, list[dict[str, object]]]],
) -> dict[str, object]:
    """Build the smallest accepted map: source pin, catalog, forward, reverse."""

    runtime_chunks: dict[str, dict[str, object]] = {}
    reverse: dict[str, list[dict[str, object]]] = {}
    for runtime_id, (start, end, raw_edges) in runtime_specs.items():
        forward: list[dict[str, object]] = []
        for raw in raw_edges:
            value = copy.deepcopy(raw)
            value["runtime_chunk_id"] = runtime_id
            forward.append(value)
            object_id = str(value["object_id"])
            reverse.setdefault(object_id, []).append(copy.deepcopy(value))
        runtime_chunks[runtime_id] = {
            "runtime_chunk_id": runtime_id,
            "document_id": DOC_ID,
            "source_span": {"start": start, "end": end},
            "source_span_status": "verified",
            "provenance_status": "full",
            "content_sha256": _sha(source[start:end]),
            "canonical_objects": forward,
        }
    payload: dict[str, object] = {
        "schema_version": 2,
        "documents": {
            DOC_ID: {
                "document_id": DOC_ID,
                "source_sha256": _sha(source),
            }
        },
        "runtime_chunks": runtime_chunks,
        "object_catalog": copy.deepcopy(objects),
        "object_to_runtime_chunks": reverse,
    }
    return payload


def _index(source: str, payload: dict[str, object]) -> CorpusEvidenceIndex:
    return CorpusEvidenceIndex.from_provenance_map(
        payload,
        documents={DOC_ID: source},
        runtime_documents={DOC_ID: source},
        source_digests={DOC_ID: _sha(source)},
        expected_map_digest=evidence_module._mapping_digest(payload),
    )


def _object_record(
    object_id: str,
    locator: ObjectLocator | TableCellLocator,
    extent: dict[str, object],
) -> dict[str, object]:
    return {
        "object_id": object_id,
        "document_id": DOC_ID,
        "object_type": (
            "cell" if isinstance(locator, TableCellLocator) else locator.object_type
        ),
        "locator": _locator_json(locator),
        "expected_extent": copy.deepcopy(extent),
        "mapping_status": "complete",
        "source_sha256": "placeholder",
    }


def _set_object_source_hash(
    source: str, objects: dict[str, dict[str, object]]
) -> None:
    for value in objects.values():
        value["source_sha256"] = _sha(source)


def _formal_item(
    source: str,
    runtime_id: str,
    start: int,
    end: int,
    *,
    object_id: str,
    object_type: str,
    object_start: int,
    object_end: int,
    coverage: str = "full",
    locator: object | None = None,
) -> RAGEvidenceItem:
    content = source[start:end]
    metadata = {
        "provenance_schema": "canonical-provenance/v2",
        "provenance_status": coverage,
        "source_sha256": _sha(source),
        "content_sha256": _sha(content),
        "runtime_chunk_id": runtime_id,
        "runtime_source_span": {"start": start, "end": end},
        "canonical_object_id": object_id,
        "canonical_object_ids": [object_id],
        "canonical_object_type": object_type,
        "canonical_object_coverage": coverage,
        "canonical_object_span": {
            "start": object_start,
            "end": object_end,
        },
        "canonical_overlap_span": {"start": start, "end": end},
        "expected_extent": _extent(object_start, object_end),
    }
    return RAGEvidenceItem(
        item_id=f"item-{runtime_id}",
        rank=1,
        content=content,
        document_id=DOC_ID,
        locator=locator,
        native_id=runtime_id,
        metadata=metadata,
    )


def test_formal_locator_requires_catalog_edge_even_with_correct_hashes() -> None:
    source = "canonical source with an unrelated returned value"
    gold = GoldEvidence(
        evidence_id="secret",
        document_id=DOC_ID,
        locator=ObjectLocator(object_type="paragraph", object_id="p-secret"),
        canonical_value="actual gold value",
    )
    item = RAGEvidenceItem(
        item_id="spoof",
        rank=1,
        content="unrelated returned value",
        document_id=DOC_ID,
        locator=gold.locator,
        metadata={
            "provenance_schema": "canonical-provenance/v2",
            "provenance_status": "full",
            "source_sha256": _sha(source),
            "content_sha256": _sha("unrelated returned value"),
        },
    )

    corpus = CorpusEvidenceIndex({DOC_ID: source})
    assert match_evidence(item, gold, corpus) is None
    localized = localize_gold_evidence([item], gold, corpus)
    assert localized.status == LocalizationStatus.PROVENANCE_MISSING


def test_formal_locator_cannot_fall_back_to_unique_quote_without_edge() -> None:
    """Formal hashes/locator do not silently re-enter the legacy quote path."""

    source = "the uniquely rendered Gold value"
    gold = GoldEvidence(
        evidence_id="strict-quote",
        document_id=DOC_ID,
        locator=ObjectLocator(object_type="paragraph", object_id="p-gold"),
        canonical_value=source,
        quote_anchor=source,
    )
    item = RAGEvidenceItem(
        item_id="strict-quote-item",
        rank=1,
        document_id=DOC_ID,
        content=source,
        locator=gold.locator,
        metadata={
            "provenance_schema": "canonical-provenance/v2",
            "provenance_status": "full",
            "source_sha256": _sha(source),
            "content_sha256": _sha(source),
        },
    )
    assert match_evidence(item, gold, CorpusEvidenceIndex({DOC_ID: source})) is None
    assert localize_gold_evidence([item], gold, CorpusEvidenceIndex({DOC_ID: source})).status == LocalizationStatus.PROVENANCE_MISSING


def test_explicit_missing_status_blocks_legacy_typed_locator() -> None:
    source = "a value"
    locator = ObjectLocator(object_type="paragraph", object_id="p-gold")
    gold = GoldEvidence(
        evidence_id="missing-status",
        document_id=DOC_ID,
        locator=locator,
        canonical_value=source,
    )
    item = RAGEvidenceItem(
        item_id="missing-status-item",
        rank=1,
        document_id=DOC_ID,
        content=source,
        locator=locator,
        metadata={"provenance_status": "missing"},
    )
    assert match_evidence(item, gold, CorpusEvidenceIndex({DOC_ID: source})) is None


def test_catalog_verified_flag_or_schema_version_cannot_bypass_pins() -> None:
    source = "known text"
    locator = ObjectLocator(object_type="paragraph", object_id="p-1")
    extent = _extent(0, len(source))
    objects = {"p-1": _object_record("p-1", locator, extent)}
    edge = _edge("p-1", "paragraph", locator, extent)
    payload = _formal_map(source, objects, {"chunk-1": (0, len(source), [edge])})

    no_pin = CorpusEvidenceIndex.from_provenance_map(
        payload, documents={DOC_ID: source}, runtime_documents={DOC_ID: source}, catalog_verified=True
    )
    assert no_pin.catalog_verified is False

    wrong_pin = CorpusEvidenceIndex.from_provenance_map(
        payload,
        documents={DOC_ID: source},
        runtime_documents={DOC_ID: source},
        source_digests={DOC_ID: _sha(source)},
        expected_map_digest="0" * 64,
    )
    assert wrong_pin.catalog_verified is False


def test_p0_mapped_catalog_extent_without_nested_status_is_formal() -> None:
    """Accept the P0 serializer's explicit mapped/extent contract."""

    source = "known text"
    locator = ObjectLocator(object_type="paragraph", object_id="p-1")
    extent = _extent(0, len(source))
    extent.pop("status")
    objects = {
        "p-1": {
            **_object_record("p-1", locator, extent),
            "mapping_status": "mapped",
        }
    }
    edge = _edge("p-1", "paragraph", locator, extent)
    payload = _formal_map(source, objects, {"chunk-1": (0, len(source), [edge])})
    # P0 intentionally keeps the reverse edge compact; forward records carry
    # the typed locator and expected extent used for the identity check.
    payload["object_to_runtime_chunks"] = {
        "p-1": [
            {
                "runtime_chunk_id": "chunk-1",
                "coverage": "full",
                "mapping_status": "mapped",
                "reason": "native-span",
            }
        ]
    }
    index = CorpusEvidenceIndex.from_provenance_map(
        payload,
        documents={DOC_ID: source},
        runtime_documents={DOC_ID: source},
        source_digests={DOC_ID: _sha(source)},
        expected_map_digest=evidence_module._mapping_digest(payload),
    )
    assert index.catalog_verified is True
    assert index.has_complete_expected_extent(DOC_ID, "p-1") is True


def test_typed_structural_paragraph_extent_supports_full_locator() -> None:
    source = "paragraph native text"
    locator = ObjectLocator(object_type="paragraph", object_id="p-42")
    extent = {"body_ordinal": 42, "status": "complete"}
    objects = {
        "p-42": {
            "object_id": "p-42",
            "document_id": DOC_ID,
            "object_type": "paragraph",
            "locator": _locator_json(locator),
            "expected_extent": extent,
            "mapping_status": "mapped",
        }
    }
    edge = _edge("p-42", "paragraph", locator, extent)
    payload = _formal_map(source, objects, {"chunk-42": (0, len(source), [edge])})
    index = _index(source, payload)
    assert index.catalog_verified is True
    assert index.has_complete_expected_extent(DOC_ID, "p-42") is True
    item = _formal_item(
        source,
        "chunk-42",
        0,
        len(source),
        object_id="p-42",
        object_type="paragraph",
        object_start=0,
        object_end=len(source),
    )
    gold = GoldEvidence(
        evidence_id="p-42",
        document_id=DOC_ID,
        locator=locator,
        canonical_value=source,
    )
    assert match_evidence(item, gold, index) is not None


def test_typed_structural_cell_extent_resolves_table_cell_identity() -> None:
    source = "cell-value"
    table_id = "table-7"
    locator = TableCellLocator(table_id=table_id, row=2, column=5)
    extent = {
        "table_id": table_id,
        "row": 2,
        "column": 5,
        "status": "complete",
    }
    objects = {
        "cell-2-5": {
            "object_id": "cell-2-5",
            "document_id": DOC_ID,
            "object_type": "cell",
            "locator": _locator_json(locator),
            "expected_extent": extent,
            "mapping_status": "mapped",
        }
    }
    edge = _edge("cell-2-5", "cell", locator, extent)
    payload = _formal_map(source, objects, {"cell-chunk": (0, len(source), [edge])})
    index = _index(source, payload)
    assert index.catalog_verified is True
    assert index.object_ids_for_locator(DOC_ID, locator) == ("cell-2-5",)
    item = _formal_item(
        source,
        "cell-chunk",
        0,
        len(source),
        object_id="cell-2-5",
        object_type="cell",
        object_start=0,
        object_end=len(source),
        locator=locator,
    )
    gold = GoldEvidence(
        evidence_id="cell",
        document_id=DOC_ID,
        locator=locator,
        canonical_value=source,
    )
    assert match_evidence(item, gold, index) is not None


def test_serialized_map_pin_is_not_confused_with_logical_map_digest() -> None:
    source = "中文 native stream"
    locator = ObjectLocator(object_type="paragraph", object_id="p-1")
    extent = _extent(0, len(source))
    objects = {"p-1": _object_record("p-1", locator, extent)}
    payload = _formal_map(source, objects, {"chunk-1": (0, len(source), [_edge("p-1", "paragraph", locator, extent)])})
    serialized = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    bytes_digest = hashlib.sha256(serialized).hexdigest()
    index = CorpusEvidenceIndex.from_provenance_map(
        payload,
        documents={DOC_ID: source},
        runtime_documents={DOC_ID: source},
        source_digests={DOC_ID: _sha(source)},
        expected_map_bytes_digest=bytes_digest,
        map_bytes_digest=bytes_digest,
    )
    assert index.map_digest_verified is False
    assert index.map_bytes_digest_verified is True
    assert index.map_pin_verified is True
    assert index.catalog_verified is True


@pytest.mark.parametrize("tamper", ["swapped_catalog_id", "missing_forward_edge"])
def test_forward_reverse_catalog_tamper_fails_closed(tamper: str) -> None:
    source = "known text"
    locator = ObjectLocator(object_type="paragraph", object_id="p-1")
    extent = _extent(0, len(source))
    objects = {"p-1": _object_record("p-1", locator, extent)}
    edge = _edge("p-1", "paragraph", locator, extent)
    payload = _formal_map(source, objects, {"chunk-1": (0, len(source), [edge])})
    if tamper == "swapped_catalog_id":
        payload["object_catalog"]["p-1"]["object_id"] = "p-other"
    else:
        payload["runtime_chunks"]["chunk-1"]["canonical_objects"] = []
    index = _index(source, payload)
    assert index.catalog_verified is False
    assert index.runtime_edges_for(DOC_ID, "p-1") == ()


def test_unrelated_bad_forward_edge_isolated_from_valid_gold_edge() -> None:
    """A bad component is unavailable without disabling good components."""

    source = "GOODBADTEXT"
    good_locator = ObjectLocator(object_type="paragraph", object_id="good")
    bad_locator = ObjectLocator(object_type="paragraph", object_id="bad")
    objects = {
        "good": _object_record("good", good_locator, _extent(0, 4)),
        "bad": _object_record("bad", bad_locator, _extent(4, 11)),
    }
    payload = _formal_map(
        source,
        objects,
        {
            "good-chunk": (
                0,
                4,
                [_edge("good", "paragraph", good_locator, _extent(0, 4))],
            ),
            "bad-chunk": (
                4,
                11,
                [_edge("bad", "paragraph", bad_locator, _extent(4, 11))],
            ),
        },
    )
    # Keep the malformed component in the pinned forward map but remove only
    # its reverse record.  The map is not globally clean.  The good edge stays
    # available in the diagnostic indexes, but the formal scorer must fail
    # closed for the run rather than treating a partially trusted map as a
    # verified catalog.
    payload["object_to_runtime_chunks"].pop("bad")
    index = _index(source, payload)
    assert index.catalog_verified is False
    assert index.catalog_round_trip_verified is False
    good = GoldEvidence(
        evidence_id="good",
        document_id=DOC_ID,
        locator=good_locator,
        canonical_value="GOOD",
    )
    item = _formal_item(
        source,
        "good-chunk",
        0,
        4,
        object_id="good",
        object_type="paragraph",
        object_start=0,
        object_end=4,
    )
    matched = match_evidence(item, good, index)
    assert matched is None


def test_one_runtime_chunk_projects_multiple_objects_at_original_rank() -> None:
    source = "same runtime text"
    locators = {
        object_id: ObjectLocator(object_type="paragraph", object_id=object_id)
        for object_id in ("p-1", "p-2")
    }
    extent = _extent(0, len(source))
    objects = {
        object_id: _object_record(object_id, locator, extent)
        for object_id, locator in locators.items()
    }
    edges = [
        _edge(object_id, "paragraph", locator, extent)
        for object_id, locator in locators.items()
    ]
    index = _index(
        source,
        _formal_map(source, objects, {"chunk-1": (0, len(source), edges)}),
    )
    items = [
        _formal_item(
            source,
            "chunk-1",
            0,
            len(source),
            object_id=object_id,
            object_type="paragraph",
            object_start=0,
            object_end=len(source),
            locator=locator,
        )
        for object_id, locator in locators.items()
    ]
    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="set",
        evidence=[
            GoldEvidence(
                evidence_id=object_id,
                document_id=DOC_ID,
                locator=locator,
                canonical_value=object_id,
            )
            for object_id, locator in locators.items()
        ],
        required_groups=[["p-1"], ["p-2"]],
    )
    localized = localize_stage(items, evidence_set, index, stage="ranked")
    assert all(value.status == LocalizationStatus.MATCHED for value in localized.gold.values())
    assert all(value.rank == 1 for value in localized.gold.values())
    assert {match_evidence(item, evidence, index).kind for item, evidence in zip(items, evidence_set.evidence, strict=True)} == {EvidenceMatchKind.EXACT_PROVENANCE}


def test_object_locator_partial_union_requires_same_object_and_no_gap() -> None:
    source = "0123456789abcdefghij"
    locator = ObjectLocator(object_type="paragraph", object_id="p-1")
    extent = _extent(10, 20)
    objects = {"p-1": _object_record("p-1", locator, extent)}
    edges = [
        _edge("p-1", "paragraph", locator, extent, coverage="partial", overlap=(10, 15)),
    ]
    edges2 = [
        _edge("p-1", "paragraph", locator, extent, coverage="partial", overlap=(15, 20)),
    ]
    payload = _formal_map(
        source,
        objects,
        {
            "chunk-left": (10, 15, edges),
            "chunk-right": (15, 20, edges2),
        },
    )
    index = _index(source, payload)
    gold = GoldEvidence(
        evidence_id="paragraph",
        document_id=DOC_ID,
        locator=locator,
        canonical_value="abcdefghij",
    )
    left = _formal_item(
        source,
        "chunk-left",
        10,
        15,
        object_id="p-1",
        object_type="paragraph",
        object_start=10,
        object_end=20,
        coverage="partial",
    )
    right = _formal_item(
        source,
        "chunk-right",
        15,
        20,
        object_id="p-1",
        object_type="paragraph",
        object_start=10,
        object_end=20,
        coverage="partial",
    )
    one = localize_gold_evidence([left], gold, index)
    both = localize_gold_evidence([left, right], gold, index)
    assert one.status == LocalizationStatus.PARTIAL
    assert both.status == LocalizationStatus.MATCHED
    assert both.rank == 1

    gap_right = _formal_item(
        source,
        "chunk-right",
        16,
        20,
        object_id="p-1",
        object_type="paragraph",
        object_start=10,
        object_end=20,
        coverage="partial",
    )
    gap = localize_gold_evidence([left, gap_right], gold, index)
    assert gap.status == LocalizationStatus.PARTIAL


def test_table_cell_locator_partial_union_uses_typed_cell_identity() -> None:
    source = "abcdefghij"
    cell_locator = TableCellLocator(table_id="table-1", row=1, column=2)
    extent = _extent(0, len(source))
    objects = {"cell-1": _object_record("cell-1", cell_locator, extent)}
    payload = _formal_map(
        source,
        objects,
        {
            "cell-left": (
                0,
                5,
                [_edge("cell-1", "cell", cell_locator, extent, coverage="partial", overlap=(0, 5))],
            ),
            "cell-right": (
                5,
                10,
                [_edge("cell-1", "cell", cell_locator, extent, coverage="partial", overlap=(5, 10))],
            ),
        },
    )
    index = _index(source, payload)
    gold = GoldEvidence(
        evidence_id="cell",
        document_id=DOC_ID,
        locator=cell_locator,
        canonical_value=source,
    )
    items = [
        _formal_item(
            source,
            runtime_id,
            start,
            end,
            object_id="cell-1",
            object_type="cell",
            object_start=0,
            object_end=10,
            coverage="partial",
        )
        for runtime_id, start, end in (
            ("cell-left", 0, 5),
            ("cell-right", 5, 10),
        )
    ]
    assert localize_gold_evidence(items[:1], gold, index).status == LocalizationStatus.PARTIAL
    assert localize_gold_evidence(items, gold, index).status == LocalizationStatus.MATCHED


def test_whole_table_requires_all_physical_cells_not_table_full_flag() -> None:
    source = "AABBCC"
    table_locator = ObjectLocator(object_type="table", object_id="table-1")
    cell_locators = {
        "cell-a": TableCellLocator(table_id="table-1", row=1, column=1),
        "cell-b": TableCellLocator(table_id="table-1", row=1, column=2),
        "cell-c": TableCellLocator(table_id="table-1", row=1, column=3),
    }
    objects: dict[str, dict[str, object]] = {
        "table-1": _object_record("table-1", table_locator, _extent(0, 6)),
    }
    objects.update(
        {
            object_id: _object_record(object_id, locator, _extent(start, end))
            for object_id, locator, start, end in (
                ("cell-a", cell_locators["cell-a"], 0, 2),
                ("cell-b", cell_locators["cell-b"], 2, 4),
                ("cell-c", cell_locators["cell-c"], 4, 6),
            )
        }
    )
    _set_object_source_hash(source, objects)
    table_edge = _edge("table-1", "table", table_locator, _extent(0, 6))
    all_edges = [
        table_edge,
        *[
            _edge(object_id, "cell", locator, objects[object_id]["expected_extent"])
            for object_id, locator in cell_locators.items()
        ],
    ]
    full_payload = _formal_map(source, objects, {"table-all": (0, 6, all_edges)})
    full_index = _index(source, full_payload)
    full_item = _formal_item(
        source,
        "table-all",
        0,
        6,
        object_id="table-1",
        object_type="table",
        object_start=0,
        object_end=6,
        locator=table_locator,
    )
    gold = GoldEvidence(
        evidence_id="table",
        document_id=DOC_ID,
        locator=table_locator,
        canonical_value=source,
    )
    # A whole-table Gold is complete only when every physical cell has a full
    # runtime witness, not because a table envelope calls itself full.
    assert full_index.has_complete_table_footprint(DOC_ID, "table-1") is True
    assert localize_gold_evidence([full_item], gold, full_index).status == LocalizationStatus.MATCHED

    # The same self-declared table-full edge with only one cell must fail.
    one_cell_payload = _formal_map(
        source,
        objects,
        {
            "table-spoof": (
                0,
                2,
                [table_edge, all_edges[1]],
            )
        },
    )
    one_cell_index = _index(source, one_cell_payload)
    one_cell_item = _formal_item(
        source,
        "table-spoof",
        0,
        2,
        object_id="table-1",
        object_type="table",
        object_start=0,
        object_end=6,
        locator=table_locator,
    )
    assert one_cell_index.has_complete_table_footprint(DOC_ID, "table-1") is False
    assert localize_gold_evidence([one_cell_item], gold, one_cell_index).status != LocalizationStatus.MATCHED


def test_whole_table_with_verified_footprint_reports_partial_not_unavailable() -> None:
    """A retrieved row is a measurable partial result, not a map failure."""

    source = "AABBCC"
    table_id = "table-verified-partial"
    table_locator = ObjectLocator(object_type="table", object_id=table_id)
    cell_locators = {
        "cell-a": TableCellLocator(table_id=table_id, row=1, column=1),
        "cell-b": TableCellLocator(table_id=table_id, row=1, column=2),
        "cell-c": TableCellLocator(table_id=table_id, row=1, column=3),
    }
    objects: dict[str, dict[str, object]] = {
        table_id: _object_record(table_id, table_locator, _extent(0, 6)),
    }
    objects.update(
        {
            object_id: _object_record(object_id, locator, _extent(start, end))
            for object_id, locator, start, end in (
                ("cell-a", cell_locators["cell-a"], 0, 2),
                ("cell-b", cell_locators["cell-b"], 2, 4),
                ("cell-c", cell_locators["cell-c"], 4, 6),
            )
        }
    )
    _set_object_source_hash(source, objects)
    payload = _formal_map(
        source,
        objects,
        {
            "table-row-a": (
                0,
                2,
                [
                    _edge(table_id, "table", table_locator, _extent(0, 6), coverage="partial"),
                    _edge("cell-a", "cell", cell_locators["cell-a"], _extent(0, 2)),
                ],
            ),
            "table-row-b": (
                2,
                4,
                [
                    _edge(table_id, "table", table_locator, _extent(0, 6), coverage="partial"),
                    _edge("cell-b", "cell", cell_locators["cell-b"], _extent(2, 4)),
                ],
            ),
            "table-row-c": (
                4,
                6,
                [
                    _edge(table_id, "table", table_locator, _extent(0, 6), coverage="partial"),
                    _edge("cell-c", "cell", cell_locators["cell-c"], _extent(4, 6)),
                ],
            ),
        },
    )
    index = _index(source, payload)
    assert index.has_complete_table_footprint(DOC_ID, table_id) is True
    gold = GoldEvidence(
        evidence_id="table",
        document_id=DOC_ID,
        locator=table_locator,
        canonical_value=source,
    )
    selected = _formal_item(
        source,
        "table-row-a",
        0,
        2,
        object_id=table_id,
        object_type="table",
        object_start=0,
        object_end=6,
        coverage="partial",
        locator=table_locator,
    )
    partial = localize_gold_evidence([selected], gold, index)
    assert partial.status == LocalizationStatus.PARTIAL
    assert partial.item_ids == (selected.item_id,)
    assert partial.reason == "verified physical table footprint is incomplete at this stage"
    assert localize_gold_evidence([], gold, index).status == LocalizationStatus.RETRIEVAL_MISSED


def test_whole_table_accepts_typed_structural_table_and_cell_extents() -> None:
    source = "AABBCC"
    table_id = "table-structural"
    table_locator = ObjectLocator(object_type="table", object_id=table_id)
    cell_locators = {
        "cell-a": TableCellLocator(table_id=table_id, row=1, column=1),
        "cell-b": TableCellLocator(table_id=table_id, row=1, column=2),
        "cell-c": TableCellLocator(table_id=table_id, row=1, column=3),
    }
    table_extent = {"table_id": table_id, "status": "complete"}
    cell_extents = {
        object_id: {
            "table_id": table_id,
            "row": locator.row,
            "column": locator.column,
            "status": "complete",
        }
        for object_id, locator in cell_locators.items()
    }
    objects: dict[str, dict[str, object]] = {
        table_id: {
            "object_id": table_id,
            "document_id": DOC_ID,
            "object_type": "table",
            "locator": _locator_json(table_locator),
            "expected_extent": table_extent,
            "mapping_status": "mapped",
        }
    }
    objects.update(
        {
            object_id: {
                "object_id": object_id,
                "document_id": DOC_ID,
                "object_type": "cell",
                "locator": _locator_json(locator),
                "expected_extent": cell_extents[object_id],
                "mapping_status": "mapped",
            }
            for object_id, locator in cell_locators.items()
        }
    )
    edges = [_edge(table_id, "table", table_locator, table_extent)]
    edges.extend(
        _edge(object_id, "cell", locator, cell_extents[object_id])
        for object_id, locator in cell_locators.items()
    )
    payload = _formal_map(source, objects, {"table-chunk": (0, len(source), edges)})
    index = _index(source, payload)
    assert index.catalog_verified is True
    assert index.has_complete_expected_extent(DOC_ID, table_id) is True
    assert len(index.table_cell_objects(DOC_ID, table_id)) == 3
    item = _formal_item(
        source,
        "table-chunk",
        0,
        len(source),
        object_id=table_id,
        object_type="table",
        object_start=0,
        object_end=len(source),
        locator=table_locator,
    )
    gold = GoldEvidence(
        evidence_id="table",
        document_id=DOC_ID,
        locator=table_locator,
        canonical_value=source,
    )
    assert localize_gold_evidence([item], gold, index).status == LocalizationStatus.MATCHED


def test_whole_table_uses_complete_cells_when_table_envelope_is_partial() -> None:
    """Merged-cell rendering may degrade only the table summary witness.

    A complete physical-cell footprint remains a stronger proof than that
    renderer-specific envelope.  The inverse remains covered above: one cell
    or a self-asserted table-full flag cannot stand in for a whole table.
    """

    source = "AABB"
    table_id = "table-partial-envelope"
    table_locator = ObjectLocator(object_type="table", object_id=table_id)
    cell_locators = {
        "cell-a": TableCellLocator(table_id=table_id, row=1, column=1),
        "cell-b": TableCellLocator(table_id=table_id, row=1, column=2),
    }
    table_extent = {"table_id": table_id, "status": "complete"}
    objects: dict[str, dict[str, object]] = {
        table_id: _object_record(table_id, table_locator, table_extent),
    }
    # The envelope itself is diagnostic-only, but the independently catalogued
    # cell footprint is complete.
    objects[table_id]["mapping_status"] = "partial"
    for object_id, locator in cell_locators.items():
        objects[object_id] = _object_record(
            object_id,
            locator,
            {
                "table_id": table_id,
                "row": locator.row,
                "column": locator.column,
                "status": "complete",
            },
        )
    _set_object_source_hash(source, objects)
    edges = [
        _edge(
            table_id,
            "table",
            table_locator,
            table_extent,
            coverage="partial",
        ),
        *[
            _edge(
                object_id,
                "cell",
                locator,
                objects[object_id]["expected_extent"],
            )
            for object_id, locator in cell_locators.items()
        ],
    ]
    payload = _formal_map(source, objects, {"table-chunk": (0, len(source), edges)})
    index = _index(source, payload)
    assert index.catalog_verified is True
    assert index.has_complete_expected_extent(DOC_ID, table_id) is False
    gold = GoldEvidence(
        evidence_id="table",
        document_id=DOC_ID,
        locator=table_locator,
        canonical_value=source,
    )
    item = _formal_item(
        source,
        "table-chunk",
        0,
        len(source),
        object_id=table_id,
        object_type="table",
        object_start=0,
        object_end=len(source),
        coverage="partial",
        locator=table_locator,
    )
    assert localize_gold_evidence([item], gold, index).status == LocalizationStatus.MATCHED


def test_verified_gold_miss_beats_unrelated_partial_duplicate_text() -> None:
    """A partial duplicate must not turn a proved Gold miss into unknown."""

    source = "GOLDGOLD"
    gold_locator = ObjectLocator(object_type="paragraph", object_id="gold")
    duplicate_locator = ObjectLocator(object_type="paragraph", object_id="duplicate")
    gold_extent = _extent(0, 4)
    duplicate_extent = _extent(4, 8)
    objects = {
        "gold": _object_record("gold", gold_locator, gold_extent),
        "duplicate": _object_record("duplicate", duplicate_locator, duplicate_extent),
    }
    objects["duplicate"]["mapping_status"] = "partial"
    _set_object_source_hash(source, objects)
    payload = _formal_map(
        source,
        objects,
        {
            "gold-chunk": (
                0,
                4,
                [_edge("gold", "paragraph", gold_locator, gold_extent)],
            ),
            "duplicate-chunk": (
                4,
                8,
                [
                    _edge(
                        "duplicate",
                        "paragraph",
                        duplicate_locator,
                        duplicate_extent,
                        coverage="partial",
                        overlap=(4, 8),
                    )
                ],
            ),
        },
    )
    # The partial runtime item cannot prove where every byte in its envelope
    # came from; its identical text therefore used to create a false
    # ``provenance_missing`` diagnostic for the first paragraph.
    payload["runtime_chunks"]["duplicate-chunk"]["provenance_status"] = "partial"
    index = _index(source, payload)
    assert index.catalog_verified is True
    gold = GoldEvidence(
        evidence_id="gold",
        document_id=DOC_ID,
        locator=gold_locator,
        canonical_value="GOLD",
    )
    duplicate = _formal_item(
        source,
        "duplicate-chunk",
        4,
        8,
        object_id="duplicate",
        object_type="paragraph",
        object_start=4,
        object_end=8,
        coverage="partial",
    )
    localized = localize_gold_evidence([duplicate], gold, index)
    assert localized.status == LocalizationStatus.RETRIEVAL_MISSED
    assert localized.reason == "verified canonical object runtime chunks are absent from this stage"


def test_engine_uses_object_partial_union_and_separates_wrong_answer_support() -> None:
    source = "0123456789abcdefghij"
    locator = ObjectLocator(object_type="paragraph", object_id="p-1")
    extent = _extent(10, 20)
    objects = {"p-1": _object_record("p-1", locator, extent)}
    payload = _formal_map(
        source,
        objects,
        {
            "chunk-left": (
                10,
                15,
                [_edge("p-1", "paragraph", locator, extent, coverage="partial", overlap=(10, 15))],
            ),
            "chunk-right": (
                15,
                20,
                [_edge("p-1", "paragraph", locator, extent, coverage="partial", overlap=(15, 20))],
            ),
        },
    )
    index = _index(source, payload)
    left = _formal_item(
        source,
        "chunk-left",
        10,
        15,
        object_id="p-1",
        object_type="paragraph",
        object_start=10,
        object_end=20,
        coverage="partial",
    ).model_copy(update={"rank": 1})
    right = _formal_item(
        source,
        "chunk-right",
        15,
        20,
        object_id="p-1",
        object_type="paragraph",
        object_start=10,
        object_end=20,
        coverage="partial",
    ).model_copy(update={"rank": 2})
    evidence = GoldEvidence(
        evidence_id="paragraph",
        document_id=DOC_ID,
        locator=locator,
        canonical_value="abcdefghij",
    )
    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="set",
        evidence=[evidence],
        required_groups=[["paragraph"]],
    )
    result = RAGResult(
        answer="999",
        raw_retrieval=None,
        ranked_retrieval=None,
        final_context=[left, right],
    )
    metrics = evaluate_case(
        result,
        GoldAnswer(
            gold_answer_id="answer",
            kind=GoldAnswerKind.NUMERIC,
            canonical="42",
        ),
        evidence_set,
        index,
        k_values=(1, 2),
    )
    context_at_1 = next(item for item in metrics if item.metric_id == "context_recall@1")
    context_at_2 = next(item for item in metrics if item.metric_id == "context_recall@2")
    accuracy = next(item for item in metrics if item.metric_id == "answer_accuracy")
    grounded = next(item for item in metrics if item.metric_id == "answer_groundedness")
    unsupported = next(item for item in metrics if item.metric_id == "unsupported_answer_rate")
    assert context_at_1.status == MetricStatus.OBSERVED and context_at_1.value == 0.0
    assert context_at_2.status == MetricStatus.OBSERVED and context_at_2.value == 1.0
    assert accuracy.status == MetricStatus.OBSERVED and accuracy.value == 0.0
    assert grounded.status == MetricStatus.OBSERVED and grounded.value == 1.0
    assert unsupported.status == MetricStatus.NEEDS_REVIEW


def test_partial_object_mapping_of_other_object_does_not_prove_gold_miss() -> None:
    source = "AAAAABBBBB"
    a_locator = ObjectLocator(object_type="paragraph", object_id="a")
    b_locator = ObjectLocator(object_type="paragraph", object_id="b")
    objects = {
        "a": _object_record("a", a_locator, _extent(0, 5)),
        "b": _object_record("b", b_locator, _extent(5, 10)),
    }
    # The runtime envelope spans both regions but only B is attributed.  The
    # un-attributed A region makes the Gold result unknown, not a true miss.
    payload = _formal_map(
        source,
        objects,
        {
            "mixed": (
                0,
                10,
                [_edge("b", "paragraph", b_locator, _extent(5, 10), coverage="partial", overlap=(5, 10))],
            )
        },
    )
    payload["runtime_chunks"]["mixed"]["provenance_status"] = "partial"
    index = _index(source, payload)
    gold = GoldEvidence(
        evidence_id="a",
        document_id=DOC_ID,
        locator=a_locator,
        canonical_value="AAAAA",
    )
    item = _formal_item(
        source,
        "mixed",
        0,
        10,
        object_id="b",
        object_type="paragraph",
        object_start=5,
        object_end=10,
        coverage="partial",
    )
    localized = localize_gold_evidence([item], gold, index)
    assert localized.status == LocalizationStatus.PROVENANCE_MISSING


def test_catalogued_unmapped_gold_is_not_scored_as_retrieval_missed() -> None:
    """A catalog entry without a complete reverse map cannot prove absence."""

    source = "GOLDOTHER"
    gold_locator = ObjectLocator(object_type="paragraph", object_id="gold")
    other_locator = ObjectLocator(object_type="paragraph", object_id="other")
    objects = {
        "gold": _object_record("gold", gold_locator, _extent(0, 4)),
        "other": _object_record("other", other_locator, _extent(4, 9)),
    }
    objects["gold"]["mapping_status"] = "unmapped"
    _set_object_source_hash(source, objects)
    payload = _formal_map(
        source,
        objects,
        {
            "other-chunk": (
                4,
                9,
                [_edge("other", "paragraph", other_locator, _extent(4, 9))],
            )
        },
    )
    index = _index(source, payload)
    gold = GoldEvidence(
        evidence_id="gold",
        document_id=DOC_ID,
        locator=gold_locator,
        canonical_value="GOLD",
    )

    assert index.catalog_verified is True
    assert index.has_verified_object(DOC_ID, "gold") is True
    assert index.prove_true_miss(DOC_ID, "gold", ()) is False

    unrelated_item = _formal_item(
        source,
        "other-chunk",
        4,
        9,
        object_id="other",
        object_type="paragraph",
        object_start=4,
        object_end=9,
        locator=other_locator,
    )
    for selected in ([], [unrelated_item]):
        localized = localize_gold_evidence(selected, gold, index)
        assert localized.status == LocalizationStatus.PROVENANCE_MISSING
        assert localized.reason == (
            "canonical evidence absence is not proven by a complete runtime mapping"
        )

    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="unmapped-gold-set",
        evidence=[gold],
        required_groups=[[gold.evidence_id]],
    )
    metrics = evaluate_retrieval_stages(
        RAGResult(
            answer="",
            raw_retrieval=[],
            ranked_retrieval=[],
            final_context=[],
        ),
        evidence_set,
        index,
        k_values=(1,),
    )
    raw_recall = next(metric for metric in metrics if metric.metric_id == "raw_recall@1")
    assert raw_recall.status == MetricStatus.UNAVAILABLE
    assert raw_recall.reason == (
        "runtime provenance mapping is unavailable for required Gold Evidence"
    )


def test_executor_map_loader_keeps_rep_boundary_and_native_stream_separate(tmp_path: Path) -> None:
    """The helper is unit-tested with a tiny bundle-like object to avoid a run."""

    class Bundle:
        def source_documents(self):
            return {DOC_ID: '{"canonical": "jsonl"}'}

    source = "native execution stream"
    locator = ObjectLocator(object_type="paragraph", object_id="p-1")
    extent = _extent(0, len(source))
    objects = {"p-1": _object_record("p-1", locator, extent)}
    payload = _formal_map(source, objects, {"chunk-1": (0, len(source), [_edge("p-1", "paragraph", locator, extent)])})
    rep_dir = tmp_path / "work" / "rep-0001"
    rep_dir.mkdir(parents=True)
    map_path = rep_dir / "canonical-provenance-map.json"
    map_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    details = {
        "canonical_provenance_map_path": "canonical-provenance-map.json",
        "canonical_provenance_map_digest": hashlib.sha256(map_path.read_bytes()).hexdigest(),
    }
    document = DocumentInput(
        document_id=DOC_ID,
        content=source,
        sha256=_sha(source),
    )
    index = corpus_evidence_index_after_ingest(
        Bundle(),
        [document],
        run_dir=tmp_path,
        repetition=1,
        ingestion_details=details,
    )
    assert index.catalog_verified is True
    assert index.map_digest_verified is True
    assert index.source_pins_verified is True
    assert index.documents[DOC_ID] == '{"canonical": "jsonl"}'
    assert index.runtime_documents[DOC_ID] == source

    container_path = corpus_evidence_index_after_ingest(
        Bundle(),
        [document],
        run_dir=tmp_path,
        repetition=1,
        ingestion_details={
            "canonical_provenance_map_path": "/rag-eval/work/rep-0001/canonical-provenance-map.json",
            "canonical_provenance_map_digest": details["canonical_provenance_map_digest"],
        },
    )
    assert container_path.catalog_verified is True

    # A path escaping this repetition is rejected; no default map from rep 2
    # may be silently consumed.
    (tmp_path / "work" / "rep-0002").mkdir(parents=True)
    (tmp_path / "work" / "rep-0002" / "canonical-provenance-map.json").write_text(
        map_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    escaped = corpus_evidence_index_after_ingest(
        Bundle(),
        [document],
        run_dir=tmp_path,
        repetition=1,
        ingestion_details={
            "canonical_provenance_map_path": "../rep-0002/canonical-provenance-map.json",
            "canonical_provenance_map_digest": details["canonical_provenance_map_digest"],
        },
    )
    assert escaped.catalog_verified is False
    assert any("outside" in reason or "missing" in reason for reason in escaped.catalog_diagnostics)


def test_native_docx_contract_rejects_the_historical_empty_mapping() -> None:
    """A syntactically valid empty map must stop a DOCX run before queries."""

    from types import SimpleNamespace

    locator = TableCellLocator(table_id="table-1", row=2, column=5)
    evidence = GoldEvidence(
        evidence_id="gold-cell",
        document_id=DOC_ID,
        locator=locator,
        canonical_value="expected value",
    )
    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="evidence-set",
        evidence=[evidence],
        required_groups=[[evidence.evidence_id]],
    )
    bundle = SimpleNamespace(gold_evidence_sets={evidence_set.gold_evidence_set_id: evidence_set})
    question = Question(
        case_id="case-1",
        question="where is the expected value?",
        gold_answer_id="answer-1",
        gold_evidence_set_id=evidence_set.gold_evidence_set_id,
    )
    document = DocumentInput(
        document_id=DOC_ID,
        source_path="source.docx",
        sha256="a" * 64,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    empty_map = {
        "schema_version": 2,
        "documents": {},
        "runtime_chunks": {},
        "object_to_runtime_chunks": {},
    }
    corpus = CorpusEvidenceIndex.from_provenance_map(
        empty_map,
        documents={DOC_ID: "canonical source"},
        runtime_documents={DOC_ID: "runtime source"},
        source_digests={DOC_ID: "a" * 64},
        expected_map_digest=evidence_module._mapping_digest(empty_map),
    )

    with pytest.raises(NativeProvenanceContractError, match="no runtime chunks"):
        validate_native_provenance_contract(
            bundle,
            [question],
            [document],
            corpus,
            ingestion_details={"canonical_provenance_documents": 0},
        )


def test_native_docx_contract_accepts_verified_catalog_and_gold_locator() -> None:
    """Catalog preflight checks locator existence, not a future retrieval hit."""

    from types import SimpleNamespace

    source = "cell-value"
    locator = TableCellLocator(table_id="table-7", row=2, column=5)
    extent = {
        "table_id": "table-7",
        "row": 2,
        "column": 5,
        "status": "complete",
    }
    objects = {
        "cell-2-5": {
            "object_id": "cell-2-5",
            "document_id": DOC_ID,
            "object_type": "cell",
            "locator": _locator_json(locator),
            "expected_extent": extent,
            "mapping_status": "complete",
            "source_sha256": _sha(source),
        }
    }
    payload = _formal_map(
        source,
        objects,
        {"chunk-1": (0, len(source), [_edge("cell-2-5", "cell", locator, extent)])},
    )
    corpus = _index(source, payload)
    evidence = GoldEvidence(
        evidence_id="gold-cell",
        document_id=DOC_ID,
        locator=locator,
        canonical_value=source,
    )
    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="evidence-set",
        evidence=[evidence],
        required_groups=[[evidence.evidence_id]],
    )
    bundle = SimpleNamespace(gold_evidence_sets={evidence_set.gold_evidence_set_id: evidence_set})
    question = Question(
        case_id="case-1",
        question="where is the expected value?",
        gold_answer_id="answer-1",
        gold_evidence_set_id=evidence_set.gold_evidence_set_id,
    )
    document = DocumentInput(
        document_id=DOC_ID,
        source_path="source.docx",
        sha256="a" * 64,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    validate_native_provenance_contract(
        bundle,
        [question],
        [document],
        corpus,
        ingestion_details={"canonical_provenance_documents": 1},
    )
