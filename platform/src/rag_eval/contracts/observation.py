"""RAG-neutral Wire 2.0 observation and provenance contracts.

These models describe what a runtime exposed and what an Adapter proved. They
do not import Benchmark Gold, scoring policy, or a concrete RAG integration.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.contracts.canonical import SourceSpan, canonical_json

OBSERVATION_SCHEMA_VERSION = "2.0"


class ObservationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ObservationStatus(StrEnum):
    OBSERVED = "observed"
    UNSUPPORTED = "unsupported"
    UNOBSERVED = "unobserved"
    FAILED = "failed"
    CORRUPTED = "corrupted"


class ObservationCompleteness(StrEnum):
    COMPLETE = "complete"
    TRUNCATED = "truncated"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class StageName(StrEnum):
    CANDIDATE = "candidate"
    RANKED = "ranked"
    CONTEXT = "context"


class StageTransitionMode(StrEnum):
    IDENTITY_SUBSET = "identity_subset"
    VERIFIED_DERIVATION = "verified_derivation"
    UNOBSERVABLE = "unobservable"


class MappingTier(StrEnum):
    NATIVE_LINEAGE = "native_lineage"
    DETERMINISTIC_CROSSWALK = "deterministic_crosswalk"
    TEXT_UNIQUE_EXACT = "text_unique_exact"


class ProvenanceCoverageStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class ReverseMappingStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"


class MappingDiagnosticStatus(StrEnum):
    MISSING = "missing"
    CORRUPTED = "corrupted"
    UNSUPPORTED = "unsupported"


class LineageIntegrityStatus(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ReceiptStatus(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"


def _digest(value: object) -> str:
    return hashlib.sha256(
        canonical_json(_json_ready(value)).encode("utf-8")
    ).hexdigest()


def _json_ready(value: Any) -> Any:
    """Recursively convert contract values into canonical-JSON-compatible data."""

    if isinstance(value, BaseModel):
        return _json_ready(value.model_dump(mode="json", exclude_none=True))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _content_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SourceIdentity(ObservationModel):
    """Identity of the original document and its Canonical Catalog."""

    document_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str = Field(min_length=1)
    source_coordinate_schema: str = Field(min_length=1)
    canonical_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RuntimeProfileIdentity(ObservationModel):
    """Opaque RAG-owned runtime configuration identity."""

    profile_id: str = Field(min_length=1)
    system_id: str = Field(min_length=1)
    system_version: str = Field(min_length=1)
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class StageTransitionDeclaration(ObservationModel):
    source_stage: StageName
    target_stage: StageName
    mode: StageTransitionMode

    @model_validator(mode="after")
    def validate_direction(self) -> StageTransitionDeclaration:
        valid = {
            (StageName.CANDIDATE, StageName.RANKED),
            (StageName.RANKED, StageName.CONTEXT),
        }
        if (self.source_stage, self.target_stage) not in valid:
            raise ValueError(
                "stage transition must follow candidate -> ranked -> context"
            )
        return self


def _default_transitions() -> tuple[StageTransitionDeclaration, ...]:
    return (
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
    )


class AdapterCapabilitiesV2(ObservationModel):
    """Adapter observation capabilities, independent of runtime behavior."""

    schema_version: Literal["2.0"] = OBSERVATION_SCHEMA_VERSION
    ingestion_catalog: bool = False
    candidate_retrieval: bool = False
    ranked_retrieval: bool = False
    final_context: bool = False
    prompt_trace: bool = False
    answer: bool = False
    provenance: bool = False
    transformation_lineage: bool = False
    latency_breakdown: bool = False
    token_usage: bool = False
    transitions: tuple[StageTransitionDeclaration, ...] = Field(
        default_factory=_default_transitions
    )

    @model_validator(mode="after")
    def validate_transition_profile(self) -> AdapterCapabilitiesV2:
        pairs = [(item.source_stage, item.target_stage) for item in self.transitions]
        expected = {
            (StageName.CANDIDATE, StageName.RANKED),
            (StageName.RANKED, StageName.CONTEXT),
        }
        if len(pairs) != len(set(pairs)) or set(pairs) != expected:
            raise ValueError(
                "capabilities must declare each candidate-to-context transition once"
            )
        if (
            any(
                item.mode == StageTransitionMode.VERIFIED_DERIVATION
                for item in self.transitions
            )
            and not self.transformation_lineage
        ):
            raise ValueError(
                "verified_derivation requires transformation_lineage capability"
            )
        return self

    def transition(
        self, source: StageName, target: StageName
    ) -> StageTransitionDeclaration:
        for item in self.transitions:
            if item.source_stage == source and item.target_stage == target:
                return item
        raise KeyError((source, target))


def _observation_profile_digest(
    *,
    profile_id: str,
    adapter_id: str,
    adapter_version: str,
    capabilities: AdapterCapabilitiesV2,
) -> str:
    return _digest(
        {
            "profile_id": profile_id,
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "capabilities": capabilities,
        }
    )


class ObservationProfileIdentity(ObservationModel):
    profile_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    capabilities: AdapterCapabilitiesV2
    profile_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_digest(self) -> ObservationProfileIdentity:
        expected = _observation_profile_digest(
            profile_id=self.profile_id,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            capabilities=self.capabilities,
        )
        if self.profile_digest != expected:
            raise ValueError(
                "observation profile digest does not match its capabilities"
            )
        return self

    @classmethod
    def build(
        cls,
        *,
        profile_id: str,
        adapter_id: str,
        adapter_version: str,
        capabilities: AdapterCapabilitiesV2,
    ) -> ObservationProfileIdentity:
        return cls(
            profile_id=profile_id,
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            capabilities=capabilities,
            profile_digest=_observation_profile_digest(
                profile_id=profile_id,
                adapter_id=adapter_id,
                adapter_version=adapter_version,
                capabilities=capabilities,
            ),
        )


class NativeSpan(ObservationModel):
    schema_version: str = Field(min_length=1)
    coordinate_system: str = Field(min_length=1)
    coordinates: dict[str, str | int | float | bool] = Field(min_length=1)


def _native_lineage_digest(
    *, schema_version: str, source_sha256: str, payload: dict[str, Any]
) -> str:
    return _digest(
        {
            "schema_version": schema_version,
            "source_sha256": source_sha256,
            "payload": payload,
        }
    )


class NativeLineage(ObservationModel):
    schema_version: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload: dict[str, Any]
    lineage_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_digest(self) -> NativeLineage:
        expected = _native_lineage_digest(
            schema_version=self.schema_version,
            source_sha256=self.source_sha256,
            payload=self.payload,
        )
        if self.lineage_sha256 != expected:
            raise ValueError("native lineage digest does not match its payload")
        return self

    @classmethod
    def build(
        cls,
        *,
        schema_version: str,
        source_sha256: str,
        payload: dict[str, Any],
    ) -> NativeLineage:
        return cls(
            schema_version=schema_version,
            source_sha256=source_sha256,
            payload=payload,
            lineage_sha256=_native_lineage_digest(
                schema_version=schema_version,
                source_sha256=source_sha256,
                payload=payload,
            ),
        )


class RuntimeChunkRecord(ObservationModel):
    native_document_id: str = Field(min_length=1)
    native_chunk_id: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content: str | None = None
    native_span: NativeSpan | None = None
    native_lineage: NativeLineage | None = None
    parser_identity: str = Field(min_length=1)
    chunker_identity: str = Field(min_length=1)
    persisted_metadata_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_content(self) -> RuntimeChunkRecord:
        if (
            self.content is not None
            and _content_digest(self.content) != self.content_sha256
        ):
            raise ValueError("runtime chunk content hash mismatch")
        return self


class ExtentUnit(ObservationModel):
    """One canonical scoring atom or a verified range within that atom."""

    unit_id: str = Field(min_length=1)
    coordinate_system: str = Field(min_length=1)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=1)
    coordinates: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_range(self) -> ExtentUnit:
        if (self.start is None) != (self.end is None):
            raise ValueError("extent unit start and end must be supplied together")
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("extent unit end must be greater than start")
        return self


def _extent_unit_key(item: ExtentUnit) -> tuple[str, str, int, int, str]:
    return (
        item.unit_id,
        item.coordinate_system,
        item.start if item.start is not None else -1,
        item.end if item.end is not None else -1,
        canonical_json(item.coordinates),
    )


def _extent_digest(extent_kind: str, units: tuple[ExtentUnit, ...]) -> str:
    return _digest(
        {
            "extent_kind": extent_kind,
            "units": sorted(units, key=_extent_unit_key),
        }
    )


class CanonicalExtent(ObservationModel):
    extent_kind: str = Field(min_length=1)
    units: tuple[ExtentUnit, ...] = Field(min_length=1)
    extent_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_extent(self) -> CanonicalExtent:
        identities = [
            (
                item.unit_id,
                item.coordinate_system,
                item.start,
                item.end,
                canonical_json(item.coordinates),
            )
            for item in self.units
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("canonical extent repeats units")
        if tuple(sorted(self.units, key=_extent_unit_key)) != self.units:
            raise ValueError("canonical extent units must use canonical order")
        if self.extent_digest != _extent_digest(self.extent_kind, self.units):
            raise ValueError("canonical extent digest does not match its units")
        return self

    @classmethod
    def build(
        cls, *, extent_kind: str, units: tuple[ExtentUnit, ...]
    ) -> CanonicalExtent:
        ordered = tuple(sorted(units, key=_extent_unit_key))
        return cls(
            extent_kind=extent_kind,
            units=ordered,
            extent_digest=_extent_digest(extent_kind, ordered),
        )


def _unit_contains(expected: ExtentUnit, covered: ExtentUnit) -> bool:
    if (
        expected.unit_id != covered.unit_id
        or expected.coordinate_system != covered.coordinate_system
        or expected.coordinates != covered.coordinates
    ):
        return False
    if expected.start is None:
        return True
    if covered.start is None:
        return False
    assert expected.end is not None and covered.end is not None
    return expected.start <= covered.start and covered.end <= expected.end


def _extent_contains(expected: CanonicalExtent, covered: CanonicalExtent) -> bool:
    return expected.extent_kind == covered.extent_kind and all(
        any(
            _unit_contains(expected_unit, covered_unit)
            for expected_unit in expected.units
        )
        for covered_unit in covered.units
    )


class PhysicalCellFootprint(ObservationModel):
    physical_cell_id: str = Field(min_length=1)
    table_id: str = Field(min_length=1)
    row: int = Field(ge=1)
    column: int = Field(ge=1)
    grid_span: int = Field(default=1, ge=1)
    v_merge: Literal["none", "restart", "continue"] = "none"
    merge_origin_physical_cell_id: str | None = None

    @model_validator(mode="after")
    def validate_merge_origin(self) -> PhysicalCellFootprint:
        if self.v_merge == "continue" and self.merge_origin_physical_cell_id is None:
            raise ValueError("continued vertical merge requires its physical origin")
        if self.v_merge == "none" and self.merge_origin_physical_cell_id is not None:
            raise ValueError("unmerged physical cell cannot claim a merge origin")
        return self


def _provenance_receipt_payload(
    *,
    native_chunk_id: str,
    canonical_object_id: str,
    canonical_locator: SourceSpan,
    mapping_tier: MappingTier,
    coverage_status: ProvenanceCoverageStatus,
    expected_extent: CanonicalExtent,
    covered_extent: CanonicalExtent,
    physical_cell_footprint: tuple[PhysicalCellFootprint, ...],
    source_sha256: str,
    native_content_sha256: str,
    native_lineage_sha256: str | None,
    canonical_value_sha256: str,
    reason_code: str,
) -> dict[str, Any]:
    return {
        "native_chunk_id": native_chunk_id,
        "canonical_object_id": canonical_object_id,
        "canonical_locator": canonical_locator,
        "mapping_tier": mapping_tier,
        "coverage_status": coverage_status,
        "expected_extent": expected_extent,
        "covered_extent": covered_extent,
        "physical_cell_footprint": physical_cell_footprint,
        "source_sha256": source_sha256,
        "native_content_sha256": native_content_sha256,
        "native_lineage_sha256": native_lineage_sha256,
        "canonical_value_sha256": canonical_value_sha256,
        "reason_code": reason_code,
    }


class ProvenanceEdge(ObservationModel):
    """A receipt-backed, positive runtime-to-canonical coverage claim."""

    edge_id: str = Field(min_length=1)
    native_chunk_id: str = Field(min_length=1)
    canonical_object_id: str = Field(min_length=1)
    canonical_locator: SourceSpan
    mapping_tier: MappingTier
    coverage_status: ProvenanceCoverageStatus
    expected_extent: CanonicalExtent
    covered_extent: CanonicalExtent
    physical_cell_footprint: tuple[PhysicalCellFootprint, ...] = ()
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    native_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    native_lineage_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    canonical_value_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason_code: str = Field(min_length=1)
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_receipt(self) -> ProvenanceEdge:
        if (
            self.mapping_tier == MappingTier.NATIVE_LINEAGE
            and self.native_lineage_sha256 is None
        ):
            raise ValueError("native_lineage mapping requires native lineage identity")
        if not _extent_contains(self.expected_extent, self.covered_extent):
            raise ValueError("covered provenance extent is outside the expected extent")
        if (
            self.coverage_status == ProvenanceCoverageStatus.COMPLETE
            and self.expected_extent.extent_digest != self.covered_extent.extent_digest
        ):
            raise ValueError("complete provenance must cover the expected extent")
        payload = _provenance_receipt_payload(
            native_chunk_id=self.native_chunk_id,
            canonical_object_id=self.canonical_object_id,
            canonical_locator=self.canonical_locator,
            mapping_tier=self.mapping_tier,
            coverage_status=self.coverage_status,
            expected_extent=self.expected_extent,
            covered_extent=self.covered_extent,
            physical_cell_footprint=self.physical_cell_footprint,
            source_sha256=self.source_sha256,
            native_content_sha256=self.native_content_sha256,
            native_lineage_sha256=self.native_lineage_sha256,
            canonical_value_sha256=self.canonical_value_sha256,
            reason_code=self.reason_code,
        )
        expected_receipt = _digest(payload)
        expected_id = f"provenance:{expected_receipt}"
        if self.receipt_sha256 != expected_receipt or self.edge_id != expected_id:
            raise ValueError("provenance receipt does not match the edge claim")
        return self

    @classmethod
    def build(
        cls,
        *,
        native_chunk_id: str,
        canonical_object_id: str,
        canonical_locator: SourceSpan,
        mapping_tier: MappingTier,
        coverage_status: ProvenanceCoverageStatus,
        expected_extent: CanonicalExtent,
        covered_extent: CanonicalExtent,
        source_sha256: str,
        native_content_sha256: str,
        canonical_value_sha256: str,
        reason_code: str,
        native_lineage_sha256: str | None = None,
        physical_cell_footprint: tuple[PhysicalCellFootprint, ...] = (),
    ) -> ProvenanceEdge:
        payload = _provenance_receipt_payload(
            native_chunk_id=native_chunk_id,
            canonical_object_id=canonical_object_id,
            canonical_locator=canonical_locator,
            mapping_tier=mapping_tier,
            coverage_status=coverage_status,
            expected_extent=expected_extent,
            covered_extent=covered_extent,
            physical_cell_footprint=physical_cell_footprint,
            source_sha256=source_sha256,
            native_content_sha256=native_content_sha256,
            native_lineage_sha256=native_lineage_sha256,
            canonical_value_sha256=canonical_value_sha256,
            reason_code=reason_code,
        )
        receipt = _digest(payload)
        return cls(
            edge_id=f"provenance:{receipt}",
            receipt_sha256=receipt,
            **payload,
        )


class MappingDiagnostic(ObservationModel):
    """A negative or unusable mapping result; never a coverage claim."""

    native_chunk_id: str | None = None
    canonical_object_id: str | None = None
    status: MappingDiagnosticStatus
    mapping_tier_attempted: MappingTier | None = None
    reason_code: str = Field(min_length=1)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_subject(self) -> MappingDiagnostic:
        if self.native_chunk_id is None and self.canonical_object_id is None:
            raise ValueError(
                "mapping diagnostic requires a native or canonical subject"
            )
        return self


def _reverse_mapping_receipt_payload(
    *,
    canonical_object_id: str,
    expected_extent: CanonicalExtent,
    reverse_mapping_status: ReverseMappingStatus,
    native_chunk_ids: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "canonical_object_id": canonical_object_id,
        "expected_extent": expected_extent,
        "reverse_mapping_status": reverse_mapping_status,
        "native_chunk_ids": tuple(sorted(native_chunk_ids)),
    }


class CanonicalMappingRecord(ObservationModel):
    """Reverse view used to prove mapping completeness for a canonical object."""

    canonical_object_id: str = Field(min_length=1)
    expected_extent: CanonicalExtent
    reverse_mapping_status: ReverseMappingStatus
    native_chunk_ids: tuple[str, ...] = ()
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_record(self) -> CanonicalMappingRecord:
        if len(self.native_chunk_ids) != len(set(self.native_chunk_ids)):
            raise ValueError("reverse mapping repeats native chunk IDs")
        if tuple(sorted(self.native_chunk_ids)) != self.native_chunk_ids:
            raise ValueError("reverse mapping native chunk IDs must be sorted")
        if (
            self.reverse_mapping_status
            in {
                ReverseMappingStatus.COMPLETE,
                ReverseMappingStatus.PARTIAL,
            }
            and not self.native_chunk_ids
        ):
            raise ValueError(
                "complete or partial reverse mapping requires native chunks"
            )
        if (
            self.reverse_mapping_status
            in {
                ReverseMappingStatus.MISSING,
                ReverseMappingStatus.UNSUPPORTED,
            }
            and self.native_chunk_ids
        ):
            raise ValueError(
                "missing or unsupported reverse mapping cannot claim chunks"
            )
        expected = _digest(
            _reverse_mapping_receipt_payload(
                canonical_object_id=self.canonical_object_id,
                expected_extent=self.expected_extent,
                reverse_mapping_status=self.reverse_mapping_status,
                native_chunk_ids=self.native_chunk_ids,
            )
        )
        if self.receipt_sha256 != expected:
            raise ValueError("reverse mapping receipt does not match the record")
        return self

    @classmethod
    def build(
        cls,
        *,
        canonical_object_id: str,
        expected_extent: CanonicalExtent,
        reverse_mapping_status: ReverseMappingStatus,
        native_chunk_ids: tuple[str, ...],
    ) -> CanonicalMappingRecord:
        ordered = tuple(sorted(native_chunk_ids))
        payload = _reverse_mapping_receipt_payload(
            canonical_object_id=canonical_object_id,
            expected_extent=expected_extent,
            reverse_mapping_status=reverse_mapping_status,
            native_chunk_ids=ordered,
        )
        return cls(**payload, receipt_sha256=_digest(payload))


class ObservedStageItem(ObservationModel):
    native_chunk_id: str = Field(min_length=1)
    native_rank: int = Field(ge=1)
    runtime_score: float | None = None
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content: str | None = None
    provenance_edge_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_item(self) -> ObservedStageItem:
        if (
            self.content is not None
            and _content_digest(self.content) != self.content_sha256
        ):
            raise ValueError("stage item content hash mismatch")
        if len(self.provenance_edge_ids) != len(set(self.provenance_edge_ids)):
            raise ValueError("stage item repeats provenance edge IDs")
        return self


class StageObservation(ObservationModel):
    stage: StageName
    observation_status: ObservationStatus
    completeness: ObservationCompleteness
    configured_cutoff: int | None = Field(default=None, ge=1)
    proven_prefix_depth: int | None = Field(default=None, ge=0)
    items: tuple[ObservedStageItem, ...]
    reason: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_observation(self) -> StageObservation:
        if self.observation_status != ObservationStatus.OBSERVED:
            if self.completeness != ObservationCompleteness.UNKNOWN:
                raise ValueError("non-observed stage completeness must be unknown")
            if self.observation_status != ObservationStatus.CORRUPTED and self.items:
                raise ValueError("non-observed stage cannot claim observed items")
            if not (self.reason or "").strip():
                raise ValueError("non-observed stage requires a reason")
            if self.proven_prefix_depth is not None:
                raise ValueError("non-observed stage cannot prove a prefix")
            return self

        identities = [item.native_chunk_id for item in self.items]
        ranks = [item.native_rank for item in self.items]
        if len(identities) != len(set(identities)):
            raise ValueError("observed stage repeats native item identities")
        if len(ranks) != len(set(ranks)):
            raise ValueError("observed stage repeats ranks")

        if self.completeness in {
            ObservationCompleteness.COMPLETE,
            ObservationCompleteness.TRUNCATED,
        }:
            expected_ranks = list(range(1, len(self.items) + 1))
            if ranks != expected_ranks:
                raise ValueError("verified stage prefix ranks must be contiguous")

        if self.completeness == ObservationCompleteness.TRUNCATED:
            if self.configured_cutoff is None or self.proven_prefix_depth is None:
                raise ValueError(
                    "truncated stage requires cutoff and proven prefix depth"
                )
            if self.proven_prefix_depth < 1:
                raise ValueError("truncated stage must prove a non-empty prefix")
            if self.proven_prefix_depth > self.configured_cutoff:
                raise ValueError("proven prefix exceeds configured cutoff")
            if self.proven_prefix_depth != len(self.items):
                raise ValueError("truncated stage items must equal proven prefix depth")
        elif self.proven_prefix_depth is not None:
            raise ValueError("only truncated observations declare proven prefix depth")
        return self

    def proves_prefix(self, cutoff: int) -> bool:
        if cutoff < 1 or self.observation_status != ObservationStatus.OBSERVED:
            return False
        if self.completeness == ObservationCompleteness.COMPLETE:
            return True
        return (
            self.completeness == ObservationCompleteness.TRUNCATED
            and self.proven_prefix_depth is not None
            and self.proven_prefix_depth >= cutoff
        )


class IngestionCatalogObservation(ObservationModel):
    observation_status: ObservationStatus
    completeness: ObservationCompleteness
    items: tuple[RuntimeChunkRecord, ...]
    reason: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_observation(self) -> IngestionCatalogObservation:
        if self.observation_status != ObservationStatus.OBSERVED:
            if self.completeness != ObservationCompleteness.UNKNOWN:
                raise ValueError("non-observed catalog completeness must be unknown")
            if self.observation_status != ObservationStatus.CORRUPTED and self.items:
                raise ValueError("non-observed catalog cannot claim observed items")
            if not (self.reason or "").strip():
                raise ValueError("non-observed catalog requires a reason")
            return self
        if self.completeness == ObservationCompleteness.TRUNCATED:
            raise ValueError("unordered ingestion catalog cannot be a verified prefix")
        identities = [item.native_chunk_id for item in self.items]
        if len(identities) != len(set(identities)):
            raise ValueError("ingestion catalog repeats native chunk identities")
        return self


class ContentObservation(ObservationModel):
    observation_status: ObservationStatus
    completeness: ObservationCompleteness
    content: str | None = None
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reason: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_observation(self) -> ContentObservation:
        if self.observation_status == ObservationStatus.OBSERVED:
            if self.content is None or self.content_sha256 is None:
                raise ValueError("observed content requires content and its hash")
            if _content_digest(self.content) != self.content_sha256:
                raise ValueError("observed content hash mismatch")
            return self
        if self.completeness != ObservationCompleteness.UNKNOWN:
            raise ValueError("non-observed content completeness must be unknown")
        if self.observation_status != ObservationStatus.CORRUPTED and (
            self.content is not None or self.content_sha256 is not None
        ):
            raise ValueError("non-observed content cannot claim verified content")
        if not (self.reason or "").strip():
            raise ValueError("non-observed content requires a reason")
        return self

    @classmethod
    def observed(cls, content: str) -> ContentObservation:
        return cls(
            observation_status=ObservationStatus.OBSERVED,
            completeness=ObservationCompleteness.COMPLETE,
            content=content,
            content_sha256=_content_digest(content),
        )


class StageItemReference(ObservationModel):
    stage: StageName
    native_chunk_id: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _transformation_payload(
    *,
    source_stage: StageName,
    target_stage: StageName,
    source_item_references: tuple[StageItemReference, ...],
    transformation_kind: str,
    output_native_chunk_id: str,
    output_content_sha256: str,
    lineage_integrity_status: LineageIntegrityStatus,
) -> dict[str, Any]:
    return {
        "source_stage": source_stage,
        "target_stage": target_stage,
        "source_item_references": source_item_references,
        "transformation_kind": transformation_kind,
        "output_native_chunk_id": output_native_chunk_id,
        "output_identity_sha256": _digest({"native_chunk_id": output_native_chunk_id}),
        "output_content_sha256": output_content_sha256,
        "lineage_integrity_status": lineage_integrity_status,
    }


class TransformationRecord(ObservationModel):
    transformation_id: str = Field(min_length=1)
    source_stage: StageName
    target_stage: StageName
    source_item_references: tuple[StageItemReference, ...] = Field(min_length=1)
    transformation_kind: str = Field(min_length=1)
    output_native_chunk_id: str = Field(min_length=1)
    output_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    lineage_integrity_status: LineageIntegrityStatus
    transformation_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_record(self) -> TransformationRecord:
        declaration = StageTransitionDeclaration(
            source_stage=self.source_stage,
            target_stage=self.target_stage,
            mode=StageTransitionMode.VERIFIED_DERIVATION,
        )
        del declaration
        if any(ref.stage != self.source_stage for ref in self.source_item_references):
            raise ValueError("transformation source references use the wrong stage")
        refs = [(ref.stage, ref.native_chunk_id) for ref in self.source_item_references]
        if len(refs) != len(set(refs)):
            raise ValueError("transformation repeats source references")
        payload = _transformation_payload(
            source_stage=self.source_stage,
            target_stage=self.target_stage,
            source_item_references=self.source_item_references,
            transformation_kind=self.transformation_kind,
            output_native_chunk_id=self.output_native_chunk_id,
            output_content_sha256=self.output_content_sha256,
            lineage_integrity_status=self.lineage_integrity_status,
        )
        receipt = _digest(payload)
        if self.output_identity_sha256 != payload["output_identity_sha256"]:
            raise ValueError("transformation output identity digest mismatch")
        if (
            self.transformation_receipt_sha256 != receipt
            or self.transformation_id != f"transformation:{receipt}"
        ):
            raise ValueError("transformation receipt does not match the record")
        return self

    @classmethod
    def build(
        cls,
        *,
        source_stage: StageName,
        target_stage: StageName,
        source_item_references: tuple[StageItemReference, ...],
        transformation_kind: str,
        output_native_chunk_id: str,
        output_content_sha256: str,
        lineage_integrity_status: LineageIntegrityStatus,
    ) -> TransformationRecord:
        payload = _transformation_payload(
            source_stage=source_stage,
            target_stage=target_stage,
            source_item_references=source_item_references,
            transformation_kind=transformation_kind,
            output_native_chunk_id=output_native_chunk_id,
            output_content_sha256=output_content_sha256,
            lineage_integrity_status=lineage_integrity_status,
        )
        receipt = _digest(payload)
        return cls(
            transformation_id=f"transformation:{receipt}",
            transformation_receipt_sha256=receipt,
            **payload,
        )


class ValidationReceipt(ObservationModel):
    receipt_kind: str = Field(min_length=1)
    status: ReceiptStatus
    subject_id: str = Field(min_length=1)
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    details: dict[str, Any] = Field(default_factory=dict)


def _provenance_map_digest(
    edges: tuple[ProvenanceEdge, ...], records: tuple[CanonicalMappingRecord, ...]
) -> str:
    return _digest(
        {
            "edges": sorted(edges, key=lambda item: item.edge_id),
            "reverse": sorted(records, key=lambda item: item.canonical_object_id),
        }
    )


class UnifiedTrace(ObservationModel):
    schema_version: Literal["2.0"] = OBSERVATION_SCHEMA_VERSION
    case_id: str = Field(min_length=1)
    source_identity: SourceIdentity
    runtime_profile: RuntimeProfileIdentity
    observation_profile: ObservationProfileIdentity
    ingestion_catalog: IngestionCatalogObservation
    provenance_edges: tuple[ProvenanceEdge, ...]
    canonical_mapping_records: tuple[CanonicalMappingRecord, ...]
    mapping_diagnostics: tuple[MappingDiagnostic, ...]
    provenance_map_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_retrieval: StageObservation
    ranked_retrieval: StageObservation
    final_context: StageObservation
    transformations: tuple[TransformationRecord, ...]
    prompt_trace: ContentObservation
    answer: ContentObservation
    validation_receipts: tuple[ValidationReceipt, ...]
    trace_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_trace(self) -> UnifiedTrace:
        stages = {
            StageName.CANDIDATE: self.raw_retrieval,
            StageName.RANKED: self.ranked_retrieval,
            StageName.CONTEXT: self.final_context,
        }
        if any(name != observation.stage for name, observation in stages.items()):
            raise ValueError("trace stage field and declared stage do not agree")

        capabilities = self.observation_profile.capabilities
        if not capabilities.provenance and (
            self.provenance_edges or self.canonical_mapping_records
        ):
            raise ValueError("provenance records require provenance capability")
        if not capabilities.transformation_lineage and self.transformations:
            raise ValueError(
                "transformation records require transformation lineage capability"
            )
        capability_statuses = (
            (capabilities.candidate_retrieval, self.raw_retrieval),
            (capabilities.ranked_retrieval, self.ranked_retrieval),
            (capabilities.final_context, self.final_context),
        )
        for supported, observation in capability_statuses:
            self._validate_capability_status(
                supported, observation.observation_status, "stage"
            )
        self._validate_content_capability(capabilities.prompt_trace, self.prompt_trace)
        self._validate_content_capability(capabilities.answer, self.answer)
        self._validate_capability_status(
            capabilities.ingestion_catalog,
            self.ingestion_catalog.observation_status,
            "ingestion catalog",
        )

        catalog = {item.native_chunk_id: item for item in self.ingestion_catalog.items}
        for item in catalog.values():
            if (
                item.native_lineage is not None
                and item.native_lineage.source_sha256
                != self.source_identity.source_sha256
            ):
                raise ValueError(
                    "runtime catalog lineage uses a different source identity"
                )
        edge_by_id = self._unique_by(
            self.provenance_edges, "edge_id", "provenance edge IDs"
        )
        mapping_by_id = self._unique_by(
            self.canonical_mapping_records,
            "canonical_object_id",
            "canonical reverse mapping records",
        )
        transformation_by_id = self._unique_by(
            self.transformations, "transformation_id", "transformation IDs"
        )
        del transformation_by_id
        outputs: dict[str, TransformationRecord] = {}
        for record in self.transformations:
            if (
                capabilities.transition(record.source_stage, record.target_stage).mode
                != StageTransitionMode.VERIFIED_DERIVATION
            ):
                raise ValueError(
                    "transformation record requires a verified_derivation transition"
                )
            if record.output_native_chunk_id in outputs:
                raise ValueError(
                    "multiple transformations claim the same output identity"
                )
            outputs[record.output_native_chunk_id] = record

        self._validate_transitions(stages, capabilities)
        stage_item_content: dict[str, str] = {}
        for observation in stages.values():
            if observation.observation_status != ObservationStatus.OBSERVED:
                continue
            for item in observation.items:
                previous = stage_item_content.setdefault(
                    item.native_chunk_id, item.content_sha256
                )
                if previous != item.content_sha256:
                    raise ValueError(
                        "native item identity has inconsistent content across stages"
                    )
        catalog_or_derived_items = set(catalog) | set(outputs)
        known_items = catalog_or_derived_items | set(stage_item_content)
        catalog_authoritative = (
            self.ingestion_catalog.observation_status == ObservationStatus.OBSERVED
            and self.ingestion_catalog.completeness == ObservationCompleteness.COMPLETE
        )
        for observation in stages.values():
            if observation.observation_status != ObservationStatus.OBSERVED:
                continue
            for item in observation.items:
                if (
                    catalog_authoritative
                    and item.native_chunk_id not in catalog_or_derived_items
                ):
                    raise ValueError(
                        "stage contains an unknown runtime or derived item"
                    )
                expected_content = catalog.get(item.native_chunk_id)
                if expected_content is not None:
                    if expected_content.content_sha256 != item.content_sha256:
                        raise ValueError(
                            "stage item content differs from runtime catalog"
                        )
                elif (
                    item.native_chunk_id in outputs
                    and outputs[item.native_chunk_id].output_content_sha256
                    != item.content_sha256
                ):
                    raise ValueError(
                        "stage item content differs from transformation output"
                    )
                for edge_id in item.provenance_edge_ids:
                    edge = edge_by_id.get(edge_id)
                    if edge is None or edge.native_chunk_id != item.native_chunk_id:
                        raise ValueError(
                            "stage item provenance edge reference is invalid"
                        )

        for edge in self.provenance_edges:
            if edge.source_sha256 != self.source_identity.source_sha256:
                raise ValueError("provenance edge uses a different source identity")
            if edge.native_chunk_id not in known_items:
                raise ValueError(
                    "provenance edge references an unknown runtime or derived item"
                )
            chunk = catalog.get(edge.native_chunk_id)
            if chunk is not None:
                if chunk.content_sha256 != edge.native_content_sha256:
                    raise ValueError(
                        "provenance content identity differs from runtime catalog"
                    )
                if edge.mapping_tier == MappingTier.NATIVE_LINEAGE and (
                    chunk.native_lineage is None
                    or chunk.native_lineage.lineage_sha256 != edge.native_lineage_sha256
                ):
                    raise ValueError("native lineage provenance does not match catalog")
            elif edge.native_chunk_id in outputs:
                transformation = outputs[edge.native_chunk_id]
                if transformation.output_content_sha256 != edge.native_content_sha256:
                    raise ValueError(
                        "provenance content identity differs from derived output"
                    )
                if (
                    transformation.lineage_integrity_status
                    != LineageIntegrityStatus.VERIFIED
                ):
                    raise ValueError(
                        "derived output provenance requires verified transformation lineage"
                    )
                if (
                    edge.mapping_tier == MappingTier.NATIVE_LINEAGE
                    and edge.native_lineage_sha256
                    != transformation.transformation_receipt_sha256
                ):
                    raise ValueError(
                        "derived native lineage provenance does not match transformation"
                    )
            else:
                if (
                    stage_item_content[edge.native_chunk_id]
                    != edge.native_content_sha256
                ):
                    raise ValueError(
                        "provenance content identity differs from observed stage item"
                    )
                if edge.mapping_tier == MappingTier.NATIVE_LINEAGE:
                    raise ValueError(
                        "native lineage provenance requires catalog or transformation lineage"
                    )

        forward: dict[str, set[str]] = {}
        for edge in self.provenance_edges:
            forward.setdefault(edge.canonical_object_id, set()).add(
                edge.native_chunk_id
            )
        all_canonical_ids = set(forward) | set(mapping_by_id)
        for canonical_id in all_canonical_ids:
            record = mapping_by_id.get(canonical_id)
            if record is None or set(record.native_chunk_ids) != forward.get(
                canonical_id, set()
            ):
                raise ValueError("forward/reverse provenance records do not round-trip")
            if any(
                edge.expected_extent.extent_digest
                != record.expected_extent.extent_digest
                for edge in self.provenance_edges
                if edge.canonical_object_id == canonical_id
            ):
                raise ValueError("forward/reverse provenance expected extents disagree")

        expected_map_digest = _provenance_map_digest(
            self.provenance_edges, self.canonical_mapping_records
        )
        if self.provenance_map_digest != expected_map_digest:
            raise ValueError("provenance map digest does not match its records")

        expected_trace_digest = _digest(
            self.model_dump(mode="json", exclude={"trace_digest"}, exclude_none=True)
        )
        if self.trace_digest != expected_trace_digest:
            raise ValueError("unified trace digest does not match its observations")
        return self

    @staticmethod
    def _validate_capability_status(
        supported: bool, status: ObservationStatus, label: str
    ) -> None:
        if supported and status == ObservationStatus.UNSUPPORTED:
            raise ValueError(
                f"supported {label} capability cannot be marked unsupported"
            )
        if not supported and status not in {
            ObservationStatus.UNSUPPORTED,
            ObservationStatus.CORRUPTED,
        }:
            raise ValueError(
                f"unsupported {label} capability must be unsupported or corrupted"
            )

    @staticmethod
    def _validate_content_capability(
        supported: bool, observation: ContentObservation
    ) -> None:
        UnifiedTrace._validate_capability_status(
            supported, observation.observation_status, "content"
        )

    @staticmethod
    def _unique_by(
        values: tuple[Any, ...], attribute: str, label: str
    ) -> dict[str, Any]:
        result = {str(getattr(item, attribute)): item for item in values}
        if len(result) != len(values):
            raise ValueError(f"trace repeats {label}")
        return result

    def _validate_transitions(
        self,
        stages: dict[StageName, StageObservation],
        capabilities: AdapterCapabilitiesV2,
    ) -> None:
        for declaration in capabilities.transitions:
            source = stages[declaration.source_stage]
            target = stages[declaration.target_stage]
            if (
                source.observation_status != ObservationStatus.OBSERVED
                or target.observation_status != ObservationStatus.OBSERVED
            ):
                continue
            if declaration.mode == StageTransitionMode.IDENTITY_SUBSET:
                if source.completeness != ObservationCompleteness.COMPLETE:
                    continue
                source_ids = {item.native_chunk_id for item in source.items}
                target_ids = {item.native_chunk_id for item in target.items}
                if not target_ids.issubset(source_ids):
                    raise ValueError(
                        "identity_subset transition introduced a new identity"
                    )
            elif declaration.mode == StageTransitionMode.VERIFIED_DERIVATION:
                source_items = {
                    item.native_chunk_id: item.content_sha256 for item in source.items
                }
                records = {
                    record.output_native_chunk_id: record
                    for record in self.transformations
                    if record.source_stage == declaration.source_stage
                    and record.target_stage == declaration.target_stage
                    and record.lineage_integrity_status
                    == LineageIntegrityStatus.VERIFIED
                }
                for item in target.items:
                    record = records.get(item.native_chunk_id)
                    if record is None:
                        raise ValueError(
                            "verified_derivation output lacks a verified receipt"
                        )
                    if any(
                        source_items.get(reference.native_chunk_id)
                        != reference.content_sha256
                        for reference in record.source_item_references
                    ):
                        raise ValueError(
                            "verified_derivation references an unobserved or changed source"
                        )

    @classmethod
    def build(
        cls,
        *,
        case_id: str,
        source_identity: SourceIdentity,
        runtime_profile: RuntimeProfileIdentity,
        observation_profile: ObservationProfileIdentity,
        ingestion_catalog: IngestionCatalogObservation,
        provenance_edges: tuple[ProvenanceEdge, ...],
        canonical_mapping_records: tuple[CanonicalMappingRecord, ...],
        mapping_diagnostics: tuple[MappingDiagnostic, ...],
        raw_retrieval: StageObservation,
        ranked_retrieval: StageObservation,
        final_context: StageObservation,
        transformations: tuple[TransformationRecord, ...],
        prompt_trace: ContentObservation,
        answer: ContentObservation,
        validation_receipts: tuple[ValidationReceipt, ...],
    ) -> UnifiedTrace:
        payload: dict[str, Any] = {
            "case_id": case_id,
            "source_identity": source_identity,
            "runtime_profile": runtime_profile,
            "observation_profile": observation_profile,
            "ingestion_catalog": ingestion_catalog,
            "provenance_edges": provenance_edges,
            "canonical_mapping_records": canonical_mapping_records,
            "mapping_diagnostics": mapping_diagnostics,
            "provenance_map_digest": _provenance_map_digest(
                provenance_edges, canonical_mapping_records
            ),
            "raw_retrieval": raw_retrieval,
            "ranked_retrieval": ranked_retrieval,
            "final_context": final_context,
            "transformations": transformations,
            "prompt_trace": prompt_trace,
            "answer": answer,
            "validation_receipts": validation_receipts,
        }
        trace_payload = {"schema_version": OBSERVATION_SCHEMA_VERSION, **payload}
        return cls(**payload, trace_digest=_digest(trace_payload))


class AdapterRunResultV2(ObservationModel):
    protocol_version: Literal["2.0"] = OBSERVATION_SCHEMA_VERSION
    adapter_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    system_id: str = Field(min_length=1)
    system_version: str = Field(min_length=1)
    trace: UnifiedTrace
    telemetry: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_identities(self) -> AdapterRunResultV2:
        observer = self.trace.observation_profile
        runtime = self.trace.runtime_profile
        if (self.adapter_id, self.adapter_version) != (
            observer.adapter_id,
            observer.adapter_version,
        ):
            raise ValueError("adapter result identity differs from observation profile")
        if (self.system_id, self.system_version) != (
            runtime.system_id,
            runtime.system_version,
        ):
            raise ValueError("adapter result identity differs from runtime profile")
        return self
