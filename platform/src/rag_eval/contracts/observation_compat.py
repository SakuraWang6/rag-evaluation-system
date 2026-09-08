"""Loss-aware normalization from authoritative Wire 1.0 results to Wire 2.0.

The normalizer pins observable identities and content. It intentionally does
not turn legacy locators or segment traces into verified canonical provenance.
"""

from __future__ import annotations

import hashlib

from rag_eval.contracts.adapter import (
    AdapterCapabilities,
    RAGEvidenceItem,
    RAGResult,
)
from rag_eval.contracts.canonical import canonical_json
from rag_eval.contracts.observation import (
    AdapterCapabilitiesV2,
    AdapterRunResultV2,
    CompatibilityNormalization,
    ContentObservation,
    IngestionCatalogObservation,
    MappingDiagnostic,
    MappingDiagnosticStatus,
    ObservationCompleteness,
    ObservationProfileIdentity,
    ObservationStatus,
    ObservedStageItem,
    RuntimeProfileIdentity,
    SourceIdentity,
    StageName,
    StageObservation,
    StageTransitionDeclaration,
    StageTransitionMode,
    UnifiedTrace,
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _unsupported_stage(stage: StageName, reason: str) -> StageObservation:
    return StageObservation(
        stage=stage,
        observation_status=ObservationStatus.UNSUPPORTED,
        completeness=ObservationCompleteness.UNKNOWN,
        items=(),
        reason=reason,
    )


def _unobserved_stage(stage: StageName, reason: str) -> StageObservation:
    return StageObservation(
        stage=stage,
        observation_status=ObservationStatus.UNOBSERVED,
        completeness=ObservationCompleteness.UNKNOWN,
        items=(),
        reason=reason,
    )


def _normalize_stage(
    *,
    stage: StageName,
    values: list[RAGEvidenceItem] | None,
    supported: bool,
) -> tuple[StageObservation, tuple[MappingDiagnostic, ...]]:
    if not supported:
        if values is not None:
            return (
                StageObservation(
                    stage=stage,
                    observation_status=ObservationStatus.CORRUPTED,
                    completeness=ObservationCompleteness.UNKNOWN,
                    items=(),
                    reason="Wire 1.0 result contradicts its capability profile",
                    diagnostics={"returned_item_count": len(values)},
                ),
                (),
            )
        return _unsupported_stage(stage, "Wire 1.0 capability is unsupported"), ()
    if values is None:
        return _unobserved_stage(
            stage, "Wire 1.0 result did not capture this stage"
        ), ()

    try:
        items = tuple(
            ObservedStageItem(
                native_chunk_id=value.native_id or value.item_id,
                native_rank=value.rank,
                runtime_score=value.score,
                content=value.content,
                content_sha256=_sha256_text(value.content),
                provenance_edge_ids=(),
                metadata={
                    "wire1_item_id": value.item_id,
                    "wire1_document_id": value.document_id or "",
                },
            )
            for value in values
        )
        observation = StageObservation(
            stage=stage,
            observation_status=ObservationStatus.OBSERVED,
            completeness=ObservationCompleteness.UNKNOWN,
            items=items,
            reason="Wire 1.0 does not prove stage completeness or prefix depth",
        )
    except ValueError as exc:
        return (
            StageObservation(
                stage=stage,
                observation_status=ObservationStatus.CORRUPTED,
                completeness=ObservationCompleteness.UNKNOWN,
                items=(),
                reason="Wire 1.0 stage could not satisfy Wire 2.0 identity constraints",
                diagnostics={"validation_error": str(exc)},
            ),
            (),
        )

    diagnostics = tuple(
        MappingDiagnostic(
            native_chunk_id=native_id,
            status=MappingDiagnosticStatus.UNSUPPORTED,
            reason_code="wire1_verified_provenance_unavailable",
            diagnostics={"stage": stage.value},
        )
        for native_id in sorted({item.native_chunk_id for item in items})
    )
    return observation, diagnostics


def _content_observation(
    value: str | None,
    *,
    supported: bool,
    name: str,
) -> ContentObservation:
    if value is not None and supported:
        return ContentObservation.observed(value)
    if value is not None:
        return ContentObservation(
            observation_status=ObservationStatus.CORRUPTED,
            completeness=ObservationCompleteness.UNKNOWN,
            content=value,
            content_sha256=_sha256_text(value),
            reason=f"Wire 1.0 returned {name} despite an unsupported capability",
        )
    status = (
        ObservationStatus.UNOBSERVED if supported else ObservationStatus.UNSUPPORTED
    )
    return ContentObservation(
        observation_status=status,
        completeness=ObservationCompleteness.UNKNOWN,
        reason=(
            f"Wire 1.0 did not capture {name}"
            if supported
            else f"Wire 1.0 capability does not expose {name}"
        ),
    )


def normalize_rag_result_v1(
    result: RAGResult,
    *,
    case_id: str,
    source_identity: SourceIdentity,
    runtime_profile: RuntimeProfileIdentity,
    legacy_capabilities: AdapterCapabilities,
    adapter_id: str,
    adapter_version: str,
) -> AdapterRunResultV2:
    """Normalize without promoting Wire 1.0 hints into Wire 2.0 proof."""

    capabilities = AdapterCapabilitiesV2(
        ingestion_catalog=False,
        candidate_retrieval=legacy_capabilities.raw_retrieval,
        ranked_retrieval=legacy_capabilities.ranked_retrieval,
        final_context=legacy_capabilities.final_context,
        prompt_trace=legacy_capabilities.prompt_trace,
        answer=legacy_capabilities.answer,
        provenance=False,
        transformation_lineage=False,
        latency_breakdown=legacy_capabilities.latency_breakdown,
        token_usage=legacy_capabilities.token_usage,
        transitions=(
            StageTransitionDeclaration(
                source_stage=StageName.CANDIDATE,
                target_stage=StageName.RANKED,
                mode=StageTransitionMode.UNOBSERVABLE,
            ),
            StageTransitionDeclaration(
                source_stage=StageName.RANKED,
                target_stage=StageName.CONTEXT,
                mode=StageTransitionMode.UNOBSERVABLE,
            ),
        ),
    )
    observation_profile = ObservationProfileIdentity.build(
        profile_id=f"wire1-compat:{adapter_id}",
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        capabilities=capabilities,
    )

    raw, raw_diagnostics = _normalize_stage(
        stage=StageName.CANDIDATE,
        values=result.raw_retrieval,
        supported=legacy_capabilities.raw_retrieval,
    )
    ranked, ranked_diagnostics = _normalize_stage(
        stage=StageName.RANKED,
        values=result.ranked_retrieval,
        supported=legacy_capabilities.ranked_retrieval,
    )
    context, context_diagnostics = _normalize_stage(
        stage=StageName.CONTEXT,
        values=result.final_context,
        supported=legacy_capabilities.final_context,
    )
    diagnostics_by_identity = {
        (diagnostic.native_chunk_id, diagnostic.diagnostics.get("stage")): diagnostic
        for diagnostic in raw_diagnostics + ranked_diagnostics + context_diagnostics
    }

    trace = UnifiedTrace.build(
        case_id=case_id,
        source_identity=source_identity,
        runtime_profile=runtime_profile,
        observation_profile=observation_profile,
        ingestion_catalog=IngestionCatalogObservation(
            observation_status=ObservationStatus.UNSUPPORTED,
            completeness=ObservationCompleteness.UNKNOWN,
            items=(),
            reason="Wire 1.0 does not expose a verified runtime ingestion catalog",
        ),
        provenance_edges=(),
        canonical_mapping_records=(),
        mapping_diagnostics=tuple(diagnostics_by_identity.values()),
        raw_retrieval=raw,
        ranked_retrieval=ranked,
        final_context=context,
        transformations=(),
        prompt_trace=_content_observation(
            None,
            supported=legacy_capabilities.prompt_trace,
            name="prompt trace",
        ),
        answer=_content_observation(
            result.answer,
            supported=legacy_capabilities.answer,
            name="answer",
        ),
        validation_receipts=(),
    )

    source_result_sha256 = _sha256_text(
        canonical_json(result.model_dump(mode="json", exclude_none=True))
    )
    return AdapterRunResultV2(
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        system_id=runtime_profile.system_id,
        system_version=runtime_profile.system_version,
        trace=trace,
        normalization=CompatibilityNormalization(
            source_result_sha256=source_result_sha256,
            limitations=(
                "RAGResult remains the execution authority during Phase 3",
                "stage completeness and verified Top-K prefixes are unknown",
                "legacy locators and segment traces are not provenance receipts",
                "runtime catalog and stage transformation lineage are unavailable",
            ),
        ),
    )
