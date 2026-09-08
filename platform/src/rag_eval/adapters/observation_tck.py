"""Shared compatibility checks for Adapter Wire 2.0 observations."""

from __future__ import annotations

from rag_eval.contracts.observation import AdapterRunResultV2, ObservationStatus


def assert_unified_observation_tck(
    result: AdapterRunResultV2,
    *,
    adapter_id: str,
    system_id: str,
    case_id: str,
) -> None:
    """Apply the same public-contract checks to every native Adapter."""

    round_tripped = AdapterRunResultV2.model_validate(
        result.model_dump(mode="json", exclude_none=True)
    )
    assert round_tripped == result
    assert result.adapter_id == adapter_id
    assert result.system_id == system_id
    assert result.trace.case_id == case_id
    assert result.trace.observation_profile.adapter_id == adapter_id
    assert result.trace.runtime_profile.system_id == system_id

    catalog = {
        item.native_chunk_id: item.content_sha256
        for item in result.trace.ingestion_catalog.items
    }
    for stage in (
        result.trace.raw_retrieval,
        result.trace.ranked_retrieval,
        result.trace.final_context,
    ):
        if stage.observation_status != ObservationStatus.OBSERVED:
            continue
        assert [item.native_rank for item in stage.items] == list(
            range(1, len(stage.items) + 1)
        )
        for item in stage.items:
            assert catalog[item.native_chunk_id] == item.content_sha256


__all__ = ["assert_unified_observation_tck"]
