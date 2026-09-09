from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from rag_eval.adapters.observation_tck import assert_unified_observation_tck
from rag_eval.contracts.observation import (
    ObservationStatus,
    ProvenanceEdge,
    StageTransitionMode,
)

from .native_observation_tck_fixtures import (
    ADAPTER_ID,
    CASE_ID,
    SYSTEM_ID,
    derived_context_result,
    partial_stage_result,
    unobservable_transition_result,
)


def _assert_fixture(payload: object) -> None:
    assert_unified_observation_tck(
        payload,
        adapter_id=ADAPTER_ID,
        system_id=SYSTEM_ID,
        case_id=CASE_ID,
    )


def test_shared_tck_accepts_verified_derivation_and_truncated_prefix() -> None:
    result = derived_context_result()

    _assert_fixture(result)

    assert result.trace.ranked_retrieval.proves_prefix(2)
    assert result.trace.final_context.items[0].native_chunk_id == "context-merged"


def test_shared_tck_accepts_observed_partial_stages_with_rank_gaps() -> None:
    result = partial_stage_result()

    _assert_fixture(result)

    assert not result.trace.raw_retrieval.proves_prefix(1)
    assert [item.native_rank for item in result.trace.raw_retrieval.items] == [1, 3]


def test_shared_tck_accepts_unobserved_stages_and_unobservable_transitions() -> None:
    result = unobservable_transition_result()

    _assert_fixture(result)

    assert (
        result.trace.ranked_retrieval.observation_status
        == ObservationStatus.UNOBSERVED
    )
    transition = result.trace.observation_profile.capabilities.transition(
        result.trace.raw_retrieval.stage,
        result.trace.ranked_retrieval.stage,
    )
    assert transition.mode == StageTransitionMode.UNOBSERVABLE


def test_shared_tck_accepts_derived_output_without_claiming_coverage() -> None:
    result = derived_context_result(include_output_coverage_proof=False)

    _assert_fixture(result)

    assert result.trace.final_context.items[0].provenance_edge_ids == ()


def _without_transformation(payload: dict[str, object]) -> None:
    trace = payload["trace"]
    assert isinstance(trace, dict)
    trace["transformations"] = []


def _with_false_prefix(payload: dict[str, object]) -> None:
    trace = payload["trace"]
    assert isinstance(trace, dict)
    ranked = trace["ranked_retrieval"]
    assert isinstance(ranked, dict)
    items = ranked["items"]
    assert isinstance(items, list)
    assert isinstance(items[1], dict)
    items[1]["native_rank"] = 3


def _with_tampered_transformation_receipt(payload: dict[str, object]) -> None:
    trace = payload["trace"]
    assert isinstance(trace, dict)
    transformations = trace["transformations"]
    assert isinstance(transformations, list)
    assert isinstance(transformations[0], dict)
    transformations[0]["transformation_receipt_sha256"] = "0" * 64


def _with_false_output_coverage(payload: dict[str, object]) -> None:
    trace = payload["trace"]
    assert isinstance(trace, dict)
    edges = trace["provenance_edges"]
    assert isinstance(edges, list)
    original = edges[0]
    assert isinstance(original, dict)
    false_edge = ProvenanceEdge.build(
        native_chunk_id=str(original["native_chunk_id"]),
        canonical_object_id=str(original["canonical_object_id"]),
        canonical_locator=original["canonical_locator"],
        mapping_tier=original["mapping_tier"],
        coverage_status=original["coverage_status"],
        expected_extent=original["expected_extent"],
        covered_extent=original["covered_extent"],
        source_sha256=str(original["source_sha256"]),
        native_content_sha256="f" * 64,
        native_lineage_sha256=str(original["native_lineage_sha256"]),
        canonical_value_sha256=str(original["canonical_value_sha256"]),
        reason_code=str(original["reason_code"]),
    )
    edges[0] = false_edge.model_dump(mode="json")
    context = trace["final_context"]
    assert isinstance(context, dict)
    items = context["items"]
    assert isinstance(items, list)
    assert isinstance(items[0], dict)
    items[0]["provenance_edge_ids"] = [false_edge.edge_id]


def _assert_rejected(
    mutate: Callable[[dict[str, object]], None],
    message: str,
) -> None:
    payload = derived_context_result().model_dump(mode="json")
    mutate(payload)

    with pytest.raises(ValidationError, match=message):
        _assert_fixture(payload)


def test_shared_tck_rejects_missing_transformation_receipt() -> None:
    _assert_rejected(_without_transformation, "verified receipt")


def test_shared_tck_rejects_false_prefix_claim() -> None:
    _assert_rejected(_with_false_prefix, "contiguous")


def test_shared_tck_rejects_tampered_transformation_receipt() -> None:
    _assert_rejected(_with_tampered_transformation_receipt, "transformation receipt")


def test_shared_tck_rejects_false_output_coverage_proof() -> None:
    _assert_rejected(_with_false_output_coverage, "derived output")
