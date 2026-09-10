"""Platform-owned Native v2 Benchmark contracts.

These models preserve the immutable Case and Gold semantics published by a
Benchmark Release.  They deliberately contain no Adapter, retrieval, or
runtime-chunk concepts.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.contracts.canonical import (
    CanonicalDocument,
    CanonicalObjectType,
    RepresentationStatus,
    SourceSpan,
)
from rag_eval.contracts.native import DOCX_MEDIA_TYPE

NATIVE_BENCHMARK_SCHEMA_VERSION = "2.0"


class BenchmarkContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BenchmarkAnswerKindV2(StrEnum):
    TEXT = "text"
    NUMERIC = "numeric"
    FORMULA = "formula"
    SET = "set"
    ABSTAIN = "abstain"


class BenchmarkEvidenceRoleV2(StrEnum):
    REQUIRED = "required"
    SUPPORTING = "supporting"
    CONFLICTING = "conflicting"
    NEAR_MISS = "near_miss"
    NEGATIVE_SCOPE = "negative_scope"


class BenchmarkAnswerV2(BenchmarkContractModel):
    kind: BenchmarkAnswerKindV2
    canonical: str | tuple[str, ...] | None = None
    accepted_values: tuple[str, ...] = ()
    locale: str | None = None
    unit: str | None = None
    tolerance: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_answer(self) -> BenchmarkAnswerV2:
        if self.kind == BenchmarkAnswerKindV2.ABSTAIN:
            if self.canonical not in (None, "", ()):
                raise ValueError("abstention cannot contain a canonical answer")
        elif self.canonical in (None, "", ()):
            raise ValueError("non-abstain Gold requires a canonical answer")
        if self.kind != BenchmarkAnswerKindV2.NUMERIC and self.tolerance is not None:
            raise ValueError("tolerance is valid only for numeric answers")
        return self


class BenchmarkSourceIdentityV2(BenchmarkContractModel):
    document_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: Literal[
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ] = DOCX_MEDIA_TYPE
    coordinate_system_version: Literal["ooxml-structural-v1"] = (
        "ooxml-structural-v1"
    )
    canonical_schema_version: str = Field(min_length=1)
    canonical_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_identity: str = Field(min_length=1)
    canonicalizer_identity: str = Field(min_length=1)
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class BenchmarkEvidenceV2(BenchmarkContractModel):
    evidence_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    document_id: str = Field(min_length=1)
    canonical_object_id: str = Field(min_length=1)
    role: BenchmarkEvidenceRoleV2
    rationale: str | None = None
    canonical_object_type: CanonicalObjectType
    representation_status: Literal[RepresentationStatus.COMPLETE] = (
        RepresentationStatus.COMPLETE
    )
    source_spans: tuple[SourceSpan, ...] = Field(min_length=1)
    canonical_value: str = Field(min_length=1)
    canonical_witness_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_witness(self) -> BenchmarkEvidenceV2:
        expected = hashlib.sha256(self.canonical_value.encode("utf-8")).hexdigest()
        if self.canonical_witness_sha256 != expected:
            raise ValueError("canonical witness digest does not match evidence content")
        return self


class BenchmarkMsesClauseV2(BenchmarkContractModel):
    clause_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    alternatives: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_alternatives(self) -> BenchmarkMsesClauseV2:
        if len(self.alternatives) != len(set(self.alternatives)):
            raise ValueError("MSES alternatives must be unique")
        return self


class BenchmarkMsesPathV2(BenchmarkContractModel):
    path_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    clauses: tuple[BenchmarkMsesClauseV2, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_clauses(self) -> BenchmarkMsesPathV2:
        clause_ids = [item.clause_id for item in self.clauses]
        if len(clause_ids) != len(set(clause_ids)):
            raise ValueError("MSES clause IDs must be unique within a path")
        return self


class BenchmarkEvidenceDependencyV2(BenchmarkContractModel):
    dependency_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    depends_on: tuple[str, ...] = ()
    description: str = Field(min_length=1)


class BenchmarkGoldV2(BenchmarkContractModel):
    gold_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    gold_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    case_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    source_identity: BenchmarkSourceIdentityV2
    answer: BenchmarkAnswerV2
    evidence: tuple[BenchmarkEvidenceV2, ...] = ()
    mses_paths: tuple[BenchmarkMsesPathV2, ...] = ()
    dependencies: tuple[BenchmarkEvidenceDependencyV2, ...] = ()
    negative_scope_object_ids: tuple[str, ...] = ()
    negative_rationale: str | None = None

    @model_validator(mode="after")
    def validate_gold_semantics(self) -> BenchmarkGoldV2:
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Gold evidence IDs must be unique")
        if any(
            item.document_id != self.source_identity.document_id
            for item in self.evidence
        ):
            raise ValueError("Gold evidence must use the pinned source document")

        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        path_ids = [item.path_id for item in self.mses_paths]
        if len(path_ids) != len(set(path_ids)):
            raise ValueError("MSES path IDs must be unique")
        for path in self.mses_paths:
            for clause in path.clauses:
                for evidence_id in clause.alternatives:
                    evidence = evidence_by_id.get(evidence_id)
                    if evidence is None:
                        raise ValueError("MSES cites unknown evidence")
                    if evidence.role != BenchmarkEvidenceRoleV2.REQUIRED:
                        raise ValueError("MSES can contain required evidence only")

        dependency_ids = {item.dependency_id for item in self.dependencies}
        for dependency in self.dependencies:
            if dependency.dependency_id in dependency.depends_on:
                raise ValueError("an evidence dependency cannot depend on itself")
            if set(dependency.depends_on).difference(dependency_ids):
                raise ValueError("evidence dependency cites an unknown dependency")

        if self.answer.kind == BenchmarkAnswerKindV2.ABSTAIN:
            if self.mses_paths:
                raise ValueError("abstention Gold cannot contain answer MSES paths")
            if not self.negative_scope_object_ids or not (
                self.negative_rationale or ""
            ).strip():
                raise ValueError("abstention Gold requires an explicit negative scope")
            if len(self.negative_scope_object_ids) != len(
                set(self.negative_scope_object_ids)
            ):
                raise ValueError("negative-scope object IDs must be unique")
            covered = {
                item.canonical_object_id
                for item in self.evidence
                if item.role == BenchmarkEvidenceRoleV2.NEGATIVE_SCOPE
            }
            missing = set(self.negative_scope_object_ids).difference(covered)
            if missing:
                raise ValueError(
                    f"negative scope lacks typed evidence: {sorted(missing)}"
                )
        else:
            if not self.mses_paths:
                raise ValueError("answerable Gold requires at least one MSES path")
            if self.negative_scope_object_ids or self.negative_rationale is not None:
                raise ValueError("answerable Gold cannot claim an abstention scope")
        return self

    def scoring_paths(self) -> tuple[BenchmarkMsesPathV2, ...]:
        """Return exact answer MSES or the conjunctive abstention obligations."""

        if self.answer.kind != BenchmarkAnswerKindV2.ABSTAIN:
            return self.mses_paths
        evidence_by_object: dict[str, list[str]] = {}
        for item in self.evidence:
            if item.role == BenchmarkEvidenceRoleV2.NEGATIVE_SCOPE:
                evidence_by_object.setdefault(item.canonical_object_id, []).append(
                    item.evidence_id
                )
        return (
            BenchmarkMsesPathV2(
                path_id=f"negative-scope-{self.gold_id}",
                clauses=tuple(
                    BenchmarkMsesClauseV2(
                        clause_id=f"negative-scope-{index}",
                        alternatives=tuple(sorted(evidence_by_object[object_id])),
                    )
                    for index, object_id in enumerate(
                        self.negative_scope_object_ids, start=1
                    )
                ),
            ),
        )


class BenchmarkCaseV2(BenchmarkContractModel):
    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    case_revision_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    target_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    question: str = Field(min_length=1)
    language: str = Field(min_length=1)
    source_object_ids: tuple[str, ...] = Field(min_length=1)
    gold: BenchmarkGoldV2

    @model_validator(mode="after")
    def validate_gold_binding(self) -> BenchmarkCaseV2:
        if (
            self.gold.case_id != self.case_id
            or self.gold.case_revision_id != self.case_revision_id
        ):
            raise ValueError("Benchmark Case and Gold revision identities differ")
        return self


class NativeBenchmarkReleaseV2(BenchmarkContractModel):
    """Verified, host-local execution snapshot of one immutable Release."""

    schema_version: Literal["2.0"] = NATIVE_BENCHMARK_SCHEMA_VERSION
    release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    release_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    release_version: str = Field(min_length=1)
    source_identity: BenchmarkSourceIdentityV2
    original_docx_path: Path
    canonical_snapshot: CanonicalDocument
    cases: tuple[BenchmarkCaseV2, ...] = Field(min_length=1)
    case_ids: tuple[str, ...] = Field(min_length=1)
    case_selection_policy: Literal["all", "explicit"]
    case_selection_seed: int
    case_selection_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_snapshot(self) -> NativeBenchmarkReleaseV2:
        if tuple(sorted(set(self.case_ids))) != self.case_ids:
            raise ValueError("selected case IDs must be unique and sorted")
        if tuple(item.case_id for item in self.cases) != self.case_ids:
            raise ValueError("Benchmark Cases must match selected case IDs in order")
        if benchmark_case_selection_id(
            self.case_ids,
            policy=self.case_selection_policy,
            seed=self.case_selection_seed,
        ) != self.case_selection_id:
            raise ValueError("case selection ID does not match its inputs")
        manifest = self.canonical_snapshot.manifest
        if (
            manifest.document_id != self.source_identity.document_id
            or manifest.source_sha256 != self.source_identity.source_sha256
            or manifest.canonical_digest != self.source_identity.canonical_digest
            or manifest.parser_identity != self.source_identity.parser_identity
            or manifest.canonicalizer_identity
            != self.source_identity.canonicalizer_identity
            or manifest.configuration_digest
            != self.source_identity.configuration_digest
        ):
            raise ValueError("Canonical snapshot differs from the pinned source identity")
        if any(
            item.gold.source_identity != self.source_identity for item in self.cases
        ):
            raise ValueError("Benchmark Gold source identities differ from the Release")
        expected = native_benchmark_snapshot_digest(
            release_id=self.release_id,
            release_digest=self.release_digest,
            validation_report_digest=self.validation_report_digest,
            payload_snapshot_digest=self.payload_snapshot_digest,
            dataset_id=self.dataset_id,
            release_version=self.release_version,
            source_identity=self.source_identity,
            cases=self.cases,
            case_selection_policy=self.case_selection_policy,
            case_selection_seed=self.case_selection_seed,
            case_selection_id=self.case_selection_id,
        )
        if self.snapshot_digest != expected:
            raise ValueError("Native Benchmark snapshot digest does not match its content")
        return self


def benchmark_case_selection_id(
    case_ids: tuple[str, ...] | list[str], *, policy: str, seed: int
) -> str:
    payload = json.dumps(
        {"case_ids": sorted(case_ids), "policy": policy, "seed": seed},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def native_canonical_catalog_bytes(canonical: CanonicalDocument) -> bytes:
    """Render the deterministic observation sidecar for one Canonical snapshot.

    The sidecar is an adjacent coordinate/proof artifact supplied to an
    Adapter.  It is never an ingestion corpus and contains no question or
    Gold-selection information.
    """

    records: list[dict[str, object]] = []
    for item in canonical.objects:
        record = item.model_dump(mode="json")
        # Preserve the full structural payload: physical/logical cell links,
        # merge origins and spans are required to prove table coverage.  A
        # few locator keys are also mirrored at the top level for adapters
        # whose native provenance bridge consumes that compact shape.
        attributes = record.get("attributes", {})
        if isinstance(attributes, dict):
            for key in (
                "table_id",
                "row",
                "column",
                "page",
                "x0",
                "y0",
                "x1",
                "y1",
            ):
                if key in attributes:
                    record[key] = attributes[key]
        value = record.get("canonical_value")
        if isinstance(value, str):
            record["canonical_value"] = " ".join(value.split())
        records.append(record)
    return b"".join(
        (
            json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        for record in records
    )


def native_benchmark_snapshot_digest(
    *,
    release_id: str,
    release_digest: str,
    validation_report_digest: str,
    payload_snapshot_digest: str,
    dataset_id: str,
    release_version: str,
    source_identity: BenchmarkSourceIdentityV2,
    cases: tuple[BenchmarkCaseV2, ...],
    case_selection_policy: str,
    case_selection_seed: int,
    case_selection_id: str,
) -> str:
    value = {
        "schema_version": NATIVE_BENCHMARK_SCHEMA_VERSION,
        "release_id": release_id,
        "release_digest": release_digest,
        "validation_report_digest": validation_report_digest,
        "payload_snapshot_digest": payload_snapshot_digest,
        "dataset_id": dataset_id,
        "release_version": release_version,
        "source_identity": source_identity.model_dump(mode="json"),
        "cases": [item.model_dump(mode="json") for item in cases],
        "case_selection_policy": case_selection_policy,
        "case_selection_seed": case_selection_seed,
        "case_selection_id": case_selection_id,
    }
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "BenchmarkAnswerKindV2",
    "BenchmarkAnswerV2",
    "BenchmarkCaseV2",
    "BenchmarkEvidenceDependencyV2",
    "BenchmarkEvidenceRoleV2",
    "BenchmarkEvidenceV2",
    "BenchmarkGoldV2",
    "BenchmarkMsesClauseV2",
    "BenchmarkMsesPathV2",
    "BenchmarkSourceIdentityV2",
    "NativeBenchmarkReleaseV2",
    "benchmark_case_selection_id",
    "native_benchmark_snapshot_digest",
    "native_canonical_catalog_bytes",
]
