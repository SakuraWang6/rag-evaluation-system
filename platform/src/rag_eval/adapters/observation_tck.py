"""Shared conformance checks for Adapter Wire 2.0 observations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rag_eval.contracts.observation import (
    AdapterRunResultV2,
    LineageIntegrityStatus,
    ObservationCompleteness,
    ObservationStatus,
    StageName,
    StageTransitionMode,
)


def assert_unified_observation_tck(
    result: AdapterRunResultV2 | Mapping[str, Any],
    *,
    adapter_id: str,
    system_id: str,
    case_id: str,
) -> AdapterRunResultV2:
    """Apply the same public-contract checks to every native Adapter."""

    payload = (
        result.model_dump(mode="json", exclude_none=True)
        if isinstance(result, AdapterRunResultV2)
        else result
    )
    round_tripped = AdapterRunResultV2.model_validate(payload)
    if isinstance(result, AdapterRunResultV2):
        assert round_tripped == result
    result = round_tripped
    assert result.adapter_id == adapter_id
    assert result.system_id == system_id
    assert result.trace.case_id == case_id
    assert result.trace.observation_profile.adapter_id == adapter_id
    assert result.trace.runtime_profile.system_id == system_id

    catalog = {
        item.native_chunk_id: item
        for item in result.trace.ingestion_catalog.items
    }
    stages = {
        StageName.CANDIDATE: result.trace.raw_retrieval,
        StageName.RANKED: result.trace.ranked_retrieval,
        StageName.CONTEXT: result.trace.final_context,
    }
    transformations = {
        (item.source_stage, item.target_stage, item.output_native_chunk_id): item
        for item in result.trace.transformations
    }
    transformed_outputs = {
        item.output_native_chunk_id: item for item in result.trace.transformations
    }
    catalog_is_authoritative = (
        result.trace.ingestion_catalog.observation_status
        == ObservationStatus.OBSERVED
        and result.trace.ingestion_catalog.completeness
        == ObservationCompleteness.COMPLETE
    )

    for stage in stages.values():
        if stage.observation_status != ObservationStatus.OBSERVED:
            continue
        ranks = [item.native_rank for item in stage.items]
        if stage.completeness in {
            ObservationCompleteness.COMPLETE,
            ObservationCompleteness.TRUNCATED,
        }:
            assert ranks == list(range(1, len(stage.items) + 1))
        else:
            assert len(ranks) == len(set(ranks))
        if stage.completeness == ObservationCompleteness.TRUNCATED:
            assert stage.proven_prefix_depth == len(stage.items)
            assert stage.proves_prefix(len(stage.items))
        for item in stage.items:
            catalog_item = catalog.get(item.native_chunk_id)
            derived_item = transformed_outputs.get(item.native_chunk_id)
            if catalog_item is not None:
                assert catalog_item.content_sha256 == item.content_sha256
            elif derived_item is not None:
                assert derived_item.output_content_sha256 == item.content_sha256
            elif catalog_is_authoritative:
                raise AssertionError(
                    "observed stage item is absent from the complete runtime catalog "
                    "and verified transformation outputs"
                )

    capabilities = result.trace.observation_profile.capabilities
    for declaration in capabilities.transitions:
        source = stages[declaration.source_stage]
        target = stages[declaration.target_stage]
        if (
            source.observation_status != ObservationStatus.OBSERVED
            or target.observation_status != ObservationStatus.OBSERVED
        ):
            continue
        source_items = {
            item.native_chunk_id: item.content_sha256 for item in source.items
        }
        if declaration.mode == StageTransitionMode.IDENTITY_SUBSET:
            if source.completeness == ObservationCompleteness.COMPLETE:
                assert {
                    item.native_chunk_id for item in target.items
                }.issubset(source_items)
            continue
        if declaration.mode == StageTransitionMode.UNOBSERVABLE:
            continue
        for item in target.items:
            transformation = transformations.get(
                (
                    declaration.source_stage,
                    declaration.target_stage,
                    item.native_chunk_id,
                )
            )
            assert transformation is not None
            assert (
                transformation.lineage_integrity_status
                == LineageIntegrityStatus.VERIFIED
            )
            assert transformation.output_content_sha256 == item.content_sha256
            assert all(
                source_items.get(reference.native_chunk_id)
                == reference.content_sha256
                for reference in transformation.source_item_references
            )

    return result


__all__ = ["assert_unified_observation_tck"]
