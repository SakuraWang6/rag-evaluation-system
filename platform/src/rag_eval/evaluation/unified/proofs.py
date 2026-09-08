"""Canonical Gold localization and availability-bound proofs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from rag_eval.contracts.dataset import (
    GoldEvidence,
    GoldEvidenceSet,
    GoldSourceIdentity,
    ObjectLocator,
)
from rag_eval.contracts.observation import (
    CanonicalMappingRecord,
    MappingDiagnosticStatus,
    ObservationCompleteness,
    ObservationStatus,
    ObservedStageItem,
    ProvenanceEdge,
    ReverseMappingStatus,
    StageName,
    StageObservation,
    UnifiedTrace,
)
from rag_eval.evaluation.unified.extent import ExtentCoverage, extent_coverage
from rag_eval.evaluation.unified.models import (
    EvaluationMetricStatus,
    EvidenceLocalization,
    StageLocalization,
)

EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class EvidenceProof:
    evidence_id: str
    canonical_object_id: str | None
    coverage: ExtentCoverage | None
    exact: bool
    reason: str | None

    @property
    def lower(self) -> float:
        return self.coverage.fraction if self.coverage is not None else 0.0

    @property
    def upper(self) -> float:
        return self.lower if self.exact else 1.0


@dataclass(frozen=True, slots=True)
class StageProof:
    public: StageLocalization
    evidence: dict[str, EvidenceProof]
    items: tuple[ObservedStageItem, ...]


def canonical_object_id(evidence: GoldEvidence) -> str | None:
    if evidence.canonical_object_id is not None:
        return evidence.canonical_object_id
    if isinstance(evidence.locator, ObjectLocator):
        return evidence.locator.object_id
    return None


def stage_proof(
    gold: GoldEvidenceSet,
    trace: UnifiedTrace,
    observation: StageObservation,
    *,
    cutoff: int | None,
) -> StageProof:
    if cutoff is None:
        boundary_proved = (
            observation.observation_status == ObservationStatus.OBSERVED
            and observation.completeness == ObservationCompleteness.COMPLETE
        )
    else:
        boundary_proved = observation.proves_prefix(cutoff)
    items = tuple(
        item
        for item in observation.items
        if cutoff is None or item.native_rank <= cutoff
    )
    if not boundary_proved:
        reason = _stage_unavailability_reason(observation, cutoff)
        return _unknown_stage(gold, observation.stage, cutoff, reason, items)
    return _selected_proof(gold, trace, observation.stage, cutoff, items)


def ingestion_proof(gold: GoldEvidenceSet, trace: UnifiedTrace) -> StageProof:
    catalog = trace.ingestion_catalog
    if not (
        catalog.observation_status == ObservationStatus.OBSERVED
        and catalog.completeness == ObservationCompleteness.COMPLETE
    ):
        return _unknown_stage(
            gold,
            "ingestion",
            None,
            "ingestion catalog is not completely observed",
            (),
        )
    edge_ids_by_chunk: dict[str, tuple[str, ...]] = {}
    for edge in trace.provenance_edges:
        edge_ids_by_chunk.setdefault(edge.native_chunk_id, ())
        edge_ids_by_chunk[edge.native_chunk_id] += (edge.edge_id,)
    items = tuple(
        ObservedStageItem(
            native_chunk_id=chunk.native_chunk_id,
            native_rank=rank,
            content_sha256=chunk.content_sha256,
            content=chunk.content,
            provenance_edge_ids=edge_ids_by_chunk.get(chunk.native_chunk_id, ()),
        )
        for rank, chunk in enumerate(catalog.items, start=1)
    )
    return _selected_proof(gold, trace, "ingestion", None, items)


def _selected_proof(
    gold: GoldEvidenceSet,
    trace: UnifiedTrace,
    stage: StageName | str,
    cutoff: int | None,
    items: tuple[ObservedStageItem, ...],
) -> StageProof:
    records = {
        record.canonical_object_id: record
        for record in trace.canonical_mapping_records
    }
    edge_by_id = {edge.edge_id: edge for edge in trace.provenance_edges}
    all_edges_by_object: dict[str, list[ProvenanceEdge]] = {}
    for edge in trace.provenance_edges:
        all_edges_by_object.setdefault(edge.canonical_object_id, []).append(edge)
    selected_edge_ids = {
        edge_id for item in items for edge_id in item.provenance_edge_ids
    }
    selected_chunks = {item.native_chunk_id for item in items}
    derived_chunks = {
        item.output_native_chunk_id for item in trace.transformations
    }
    selected_edges_by_object: dict[str, list[ProvenanceEdge]] = {}
    for edge_id in selected_edge_ids:
        edge = edge_by_id[edge_id]
        selected_edges_by_object.setdefault(edge.canonical_object_id, []).append(edge)
    source_pins = {item.document_id: item for item in gold.source_identities}

    proofs: dict[str, EvidenceProof] = {}
    for evidence in gold.evidence:
        object_id = canonical_object_id(evidence)
        proof = _evidence_proof(
            evidence=evidence,
            object_id=object_id,
            source_pin=source_pins.get(evidence.document_id),
            trace=trace,
            record=records.get(object_id) if object_id else None,
            all_edges=all_edges_by_object.get(object_id or "", []),
            selected_edges=selected_edges_by_object.get(object_id or "", []),
            selected_edge_ids=selected_edge_ids,
            selected_chunks=selected_chunks,
            derived_chunks=derived_chunks,
        )
        proofs[evidence.evidence_id] = proof
    coverage_lower, coverage_upper = aggregate_bounds(gold, proofs, complete=False)
    recall_lower, recall_upper = aggregate_bounds(gold, proofs, complete=True)
    exact = same(coverage_lower, coverage_upper) and same(
        recall_lower, recall_upper
    )
    reason = None if exact else _proof_reason(proofs.values())
    public = StageLocalization(
        stage=stage,
        cutoff=cutoff,
        status=(
            EvaluationMetricStatus.OBSERVED
            if exact
            else EvaluationMetricStatus.UNAVAILABLE
        ),
        evidence=tuple(
            EvidenceLocalization(
                evidence_id=proof.evidence_id,
                canonical_object_id=proof.canonical_object_id,
                lower_coverage=proof.lower,
                upper_coverage=proof.upper,
                exact=proof.exact,
                reason=proof.reason,
            )
            for proof in proofs.values()
        ),
        coverage_lower=coverage_lower,
        coverage_upper=coverage_upper,
        complete_recall_lower=recall_lower,
        complete_recall_upper=recall_upper,
        reason=reason,
    )
    return StageProof(public=public, evidence=proofs, items=items)


def _evidence_proof(
    *,
    evidence: GoldEvidence,
    object_id: str | None,
    source_pin: GoldSourceIdentity | None,
    trace: UnifiedTrace,
    record: CanonicalMappingRecord | None,
    all_edges: list[ProvenanceEdge],
    selected_edges: list[ProvenanceEdge],
    selected_edge_ids: set[str],
    selected_chunks: set[str],
    derived_chunks: set[str],
) -> EvidenceProof:
    if source_pin is None:
        return _unknown_evidence(
            evidence, object_id, "Canonical Gold has no pinned source identity"
        )
    if (
        source_pin.source_sha256 != trace.source_identity.source_sha256
        or source_pin.source_coordinate_schema
        != trace.source_identity.source_coordinate_schema
        or source_pin.canonical_catalog_sha256
        != trace.source_identity.canonical_catalog_sha256
    ):
        return _unknown_evidence(
            evidence,
            object_id,
            "Canonical Gold source or catalog identity differs from the trace",
        )
    if evidence.document_id != trace.source_identity.document_id:
        return _unknown_evidence(
            evidence, object_id, "Gold document identity differs from trace source"
        )
    if object_id is None:
        return _unknown_evidence(
            evidence,
            None,
            "Gold locator has no pinned canonical object identity",
        )
    if record is None:
        return _unknown_evidence(
            evidence, object_id, "canonical reverse mapping record is absent"
        )
    if any(
        edge.expected_extent.extent_digest != record.expected_extent.extent_digest
        for edge in all_edges
    ):
        return _unknown_evidence(
            evidence, object_id, "provenance expected extents disagree"
        )
    object_corrupted = any(
        diagnostic.status == MappingDiagnosticStatus.CORRUPTED
        and (
            diagnostic.canonical_object_id == object_id
            or (
                diagnostic.canonical_object_id is None
                and diagnostic.native_chunk_id in selected_chunks
            )
        )
        for diagnostic in trace.mapping_diagnostics
    )
    referenced_object_edges = {
        edge.edge_id
        for edge in all_edges
        if edge.native_chunk_id in selected_chunks
    }
    reference_complete = referenced_object_edges.issubset(selected_edge_ids)
    try:
        coverage = extent_coverage(
            record.expected_extent,
            selected_edges,
            all_object_edges=all_edges,
        )
        catalog_coverage = extent_coverage(
            record.expected_extent,
            all_edges,
            all_object_edges=all_edges,
        )
    except ValueError as exc:
        return _unknown_evidence(evidence, object_id, str(exc))

    if object_corrupted:
        return EvidenceProof(
            evidence_id=evidence.evidence_id,
            canonical_object_id=object_id,
            coverage=None,
            exact=False,
            reason="mapping corruption affects this Gold evidence",
        )
    if not reference_complete:
        return EvidenceProof(
            evidence_id=evidence.evidence_id,
            canonical_object_id=object_id,
            coverage=coverage,
            exact=False,
            reason="stage item omitted a required provenance edge",
        )
    if coverage.fraction >= 1 - EPSILON:
        return EvidenceProof(
            evidence_id=evidence.evidence_id,
            canonical_object_id=object_id,
            coverage=coverage,
            exact=True,
            reason=None,
        )
    derived_without_output_proof = any(
        chunk_id in derived_chunks
        and not any(edge.native_chunk_id == chunk_id for edge in all_edges)
        for chunk_id in selected_chunks
    )
    if derived_without_output_proof:
        return EvidenceProof(
            evidence_id=evidence.evidence_id,
            canonical_object_id=object_id,
            coverage=coverage,
            exact=False,
            reason="derived output lacks its own canonical coverage proof",
        )
    if record.reverse_mapping_status == ReverseMappingStatus.COMPLETE:
        if catalog_coverage.fraction < 1 - EPSILON:
            return EvidenceProof(
                evidence_id=evidence.evidence_id,
                canonical_object_id=object_id,
                coverage=coverage,
                exact=False,
                reason="complete reverse mapping does not cover its expected extent",
            )
        return EvidenceProof(
            evidence_id=evidence.evidence_id,
            canonical_object_id=object_id,
            coverage=coverage,
            exact=True,
            reason=None,
        )
    if record.reverse_mapping_status == ReverseMappingStatus.MISSING:
        catalog_complete = (
            trace.ingestion_catalog.observation_status == ObservationStatus.OBSERVED
            and trace.ingestion_catalog.completeness
            == ObservationCompleteness.COMPLETE
        )
        return EvidenceProof(
            evidence_id=evidence.evidence_id,
            canonical_object_id=object_id,
            coverage=coverage,
            exact=catalog_complete,
            reason=(
                None
                if catalog_complete
                else "missing mapping lacks a complete ingestion boundary"
            ),
        )
    return EvidenceProof(
        evidence_id=evidence.evidence_id,
        canonical_object_id=object_id,
        coverage=coverage,
        exact=False,
        reason=(
            "canonical provenance is partial"
            if record.reverse_mapping_status == ReverseMappingStatus.PARTIAL
            else "canonical provenance is unsupported"
        ),
    )


def _unknown_evidence(
    evidence: GoldEvidence, object_id: str | None, reason: str
) -> EvidenceProof:
    return EvidenceProof(
        evidence_id=evidence.evidence_id,
        canonical_object_id=object_id,
        coverage=None,
        exact=False,
        reason=reason,
    )


def _unknown_stage(
    gold: GoldEvidenceSet,
    stage: StageName | str,
    cutoff: int | None,
    reason: str,
    items: tuple[ObservedStageItem, ...],
) -> StageProof:
    proofs = {
        evidence.evidence_id: _unknown_evidence(
            evidence, canonical_object_id(evidence), reason
        )
        for evidence in gold.evidence
    }
    return StageProof(
        public=StageLocalization(
            stage=stage,
            cutoff=cutoff,
            status=EvaluationMetricStatus.UNAVAILABLE,
            evidence=tuple(
                EvidenceLocalization(
                    evidence_id=item.evidence_id,
                    canonical_object_id=item.canonical_object_id,
                    lower_coverage=0,
                    upper_coverage=1,
                    exact=False,
                    reason=reason,
                )
                for item in proofs.values()
            ),
            coverage_lower=0,
            coverage_upper=1,
            complete_recall_lower=0,
            complete_recall_upper=1,
            reason=reason,
        ),
        evidence=proofs,
        items=items,
    )


def paths(gold: GoldEvidenceSet) -> list[list[list[str]]]:
    return gold.mses_paths or [gold.required_groups]


def aggregate_bounds(
    gold: GoldEvidenceSet,
    proofs: dict[str, EvidenceProof],
    *,
    complete: bool,
) -> tuple[float, float]:
    path_bounds: list[tuple[float, float]] = []
    for path in paths(gold):
        clause_bounds: list[tuple[float, float]] = []
        for clause in path:
            values = [proofs[evidence_id] for evidence_id in clause]
            if complete:
                lower = max(
                    1.0 if value.lower >= 1 - EPSILON else 0.0
                    for value in values
                )
                upper = max(
                    1.0 if value.upper >= 1 - EPSILON else 0.0
                    for value in values
                )
            else:
                lower = max(value.lower for value in values)
                upper = max(value.upper for value in values)
            clause_bounds.append((lower, upper))
        denominator = len(clause_bounds)
        path_bounds.append(
            (
                sum(value[0] for value in clause_bounds) / denominator,
                sum(value[1] for value in clause_bounds) / denominator,
            )
        )
    return (
        max(value[0] for value in path_bounds),
        max(value[1] for value in path_bounds),
    )


def required_object_ids(gold: GoldEvidenceSet) -> set[str]:
    required_evidence = {
        evidence_id
        for path in paths(gold)
        for clause in path
        for evidence_id in clause
    }
    return {
        object_id
        for evidence in gold.evidence
        if evidence.evidence_id in required_evidence
        if (object_id := canonical_object_id(evidence)) is not None
    }


def same(left: float, right: float) -> bool:
    return abs(left - right) <= EPSILON


def _stage_unavailability_reason(
    observation: StageObservation, cutoff: int | None
) -> str:
    if observation.observation_status != ObservationStatus.OBSERVED:
        return (
            f"{observation.stage.value} observation is "
            f"{observation.observation_status.value}"
        )
    if cutoff is None:
        return f"{observation.stage.value} boundary is not completely observed"
    return f"{observation.stage.value} does not prove ordered Top-{cutoff}"


def _proof_reason(values: Iterable[EvidenceProof]) -> str:
    reasons = sorted({value.reason for value in values if value.reason})
    return "; ".join(reasons) or "canonical evidence coverage is not fully provable"
