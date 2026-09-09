"""RAG-neutral helpers for honest Direct Wire 2.0 unavailability."""

from __future__ import annotations

from typing import Any

from rag_eval.contracts.native import NativeQueryV2, PreparedSystemV2
from rag_eval.contracts.observation import (
    AdapterRunResultV2,
    ContentObservation,
    IngestionCatalogObservation,
    ObservationCompleteness,
    ObservationStatus,
    StageName,
    StageObservation,
    UnifiedTrace,
)


def unavailable_native_result(
    *,
    prepared: PreparedSystemV2,
    query: NativeQueryV2,
    status: ObservationStatus,
    reason: str,
    answer: str | None,
    telemetry: dict[str, Any] | None = None,
) -> AdapterRunResultV2:
    """Return a typed trace without inventing catalog, stage, or provenance facts."""

    if status == ObservationStatus.OBSERVED:
        raise ValueError("unavailable native result cannot use observed status")
    capabilities = prepared.observation_profile.capabilities

    def capability_status(supported: bool) -> ObservationStatus:
        if status == ObservationStatus.CORRUPTED:
            return status
        return status if supported else ObservationStatus.UNSUPPORTED

    def stage(name: StageName, supported: bool, cutoff: int | None) -> StageObservation:
        observed_status = capability_status(supported)
        return StageObservation(
            stage=name,
            observation_status=observed_status,
            completeness=ObservationCompleteness.UNKNOWN,
            configured_cutoff=cutoff,
            items=(),
            reason=reason,
        )

    catalog_status = capability_status(capabilities.ingestion_catalog)
    catalog = IngestionCatalogObservation(
        observation_status=catalog_status,
        completeness=ObservationCompleteness.UNKNOWN,
        items=(),
        reason=reason,
    )
    if not query.generate_answer:
        answer_observation = ContentObservation(
            observation_status=(
                ObservationStatus.UNOBSERVED
                if capabilities.answer
                else ObservationStatus.UNSUPPORTED
            ),
            completeness=ObservationCompleteness.UNKNOWN,
            reason=(
                "answer generation was not requested"
                if capabilities.answer
                else "answer capability is unsupported"
            ),
        )
    elif isinstance(answer, str) and capabilities.answer:
        answer_observation = ContentObservation.observed(answer)
    elif capabilities.answer:
        answer_observation = ContentObservation(
            observation_status=ObservationStatus.FAILED,
            completeness=ObservationCompleteness.UNKNOWN,
            reason="native answer is not available",
        )
    else:
        answer_observation = ContentObservation(
            observation_status=ObservationStatus.UNSUPPORTED,
            completeness=ObservationCompleteness.UNKNOWN,
            reason="answer capability is unsupported",
        )
    prompt_status = capability_status(capabilities.prompt_trace)
    prompt = ContentObservation(
        observation_status=prompt_status,
        completeness=ObservationCompleteness.UNKNOWN,
        reason=reason,
    )
    trace = UnifiedTrace.build(
        case_id=query.case_id,
        source_identity=prepared.source_identity,
        runtime_profile=prepared.runtime_profile,
        observation_profile=prepared.observation_profile,
        ingestion_catalog=catalog,
        provenance_edges=(),
        canonical_mapping_records=(),
        mapping_diagnostics=(),
        raw_retrieval=stage(
            StageName.CANDIDATE,
            capabilities.candidate_retrieval,
            query.retrieval_candidate_k,
        ),
        ranked_retrieval=stage(
            StageName.RANKED,
            capabilities.ranked_retrieval,
            query.retrieval_candidate_k,
        ),
        final_context=stage(
            StageName.CONTEXT,
            capabilities.final_context,
            query.final_context_k,
        ),
        transformations=(),
        prompt_trace=prompt,
        answer=answer_observation,
        validation_receipts=(),
    )
    return AdapterRunResultV2(
        adapter_id=prepared.observation_profile.adapter_id,
        adapter_version=prepared.observation_profile.adapter_version,
        system_id=prepared.runtime_profile.system_id,
        system_version=prepared.runtime_profile.system_version,
        trace=trace,
        telemetry=dict(telemetry or {}),
    )


__all__ = ["unavailable_native_result"]
