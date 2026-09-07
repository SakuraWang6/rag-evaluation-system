"""Immutable segment-native RAG benchmark contracts.

This contract is deliberately separate from Dataset Bundle 2.0 and Bundle 3.0.
Those formats remain readable historical artifacts, while a
``rag-benchmark-contract/1`` package is the primary retrieval-scoring input for
new cross-system benchmark runs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.contracts.adapter import SegmentTraceStatus
from rag_eval.contracts.dataset import GoldAnswer, GoldAnswerKind


BENCHMARK_CONTRACT_SCHEMA_VERSION = "rag-benchmark-contract/1"
BENCHMARK_SEGMENTATION_POLICY_VERSION = "benchmark-segmentation/1"
MAX_ENVELOPED_SEGMENT_CHARACTERS = 600


class BenchmarkContractError(ValueError):
    """A segment-native benchmark package is invalid or cannot be published."""


class BenchmarkContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def benchmark_json(value: object) -> str:
    """Return a stable JSON representation used by immutable IDs and digests."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def benchmark_sha256(value: str | bytes) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()


def segment_mapping_receipt(
    benchmark_contract_digest: str,
    native_chunk_id: str,
    source_segment_ids: tuple[str, ...] | list[str],
) -> str:
    """Return the deterministic receipt required for a native chunk mapping."""

    return benchmark_sha256(
        "\0".join(
            (
                BENCHMARK_CONTRACT_SCHEMA_VERSION,
                benchmark_contract_digest,
                native_chunk_id,
                *source_segment_ids,
            )
        )
    )


class BenchmarkSegmentationPolicy(BenchmarkContractModel):
    """The data-set-level policy; it must never vary by Adapter."""

    schema_version: Literal[BENCHMARK_SEGMENTATION_POLICY_VERSION] = (
        BENCHMARK_SEGMENTATION_POLICY_VERSION
    )
    max_enveloped_characters: Literal[MAX_ENVELOPED_SEGMENT_CHARACTERS] = (
        MAX_ENVELOPED_SEGMENT_CHARACTERS
    )
    unicode_normalization: Literal["unicode-nfc-v1"] = "unicode-nfc-v1"
    renderer: Literal["rag-benchmark-segment-envelope/1"] = (
        "rag-benchmark-segment-envelope/1"
    )
    split_strategy: Literal["structural-then-boundary/1"] = (
        "structural-then-boundary/1"
    )

    @property
    def digest(self) -> str:
        return benchmark_sha256(benchmark_json(self))


class BenchmarkPresentationLocation(BenchmarkContractModel):
    """A source location retained solely for presentation and human audit."""

    coordinate_system: str = Field(min_length=1)
    coordinates: dict[str, str | int | float | bool] = Field(default_factory=dict)


class BenchmarkSegment(BenchmarkContractModel):
    """One strict-comparison retrieval leaf.

    ``parent_segment_id`` identifies the logical pre-split source segment. It
    may be absent from ``segments.jsonl`` because parent nodes are lineage
    records, not retrievable corpus leaves.
    """

    segment_id: str = Field(min_length=1)
    parent_segment_id: str | None = None
    document_id: str = Field(min_length=1)
    root_object_id: str = Field(min_length=1)
    structure_type: str = Field(min_length=1)
    source_object_ids: tuple[str, ...] = Field(min_length=1)
    ordinal: int = Field(ge=0)
    content: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    lineage: dict[str, Any] = Field(default_factory=dict)
    presentation_locations: tuple[BenchmarkPresentationLocation, ...] = ()

    @model_validator(mode="after")
    def validate_segment(self) -> "BenchmarkSegment":
        if benchmark_sha256(self.content) != self.content_sha256:
            raise ValueError("benchmark segment content digest does not match content")
        if len(set(self.source_object_ids)) != len(self.source_object_ids):
            raise ValueError("benchmark segment repeats a source object ID")
        if self.parent_segment_id == self.segment_id:
            raise ValueError("benchmark segment cannot be its own parent")
        if len(render_benchmark_segment(self)) > MAX_ENVELOPED_SEGMENT_CHARACTERS:
            raise ValueError(
                "benchmark segment exceeds the immutable enveloped character limit"
            )
        return self


def render_benchmark_segment(segment: BenchmarkSegment) -> str:
    """Render the exact Adapter input envelope for one strict leaf segment."""

    return f"[[RAG_BENCHMARK_SEGMENT id={segment.segment_id}]]\n{segment.content}"


class BenchmarkQuestion(BenchmarkContractModel):
    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    gold_id: str = Field(min_length=1)
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkGold(BenchmarkContractModel):
    """Gold answer and segment-native MSES evidence semantics.

    ``evidence_paths`` follows OR(paths) -> AND(clauses) -> OR(segment IDs).
    Every segment ID in a positive Gold path is a leaf retrieval unit.
    """

    gold_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    answer: GoldAnswer
    evidence_paths: tuple[tuple[tuple[str, ...], ...], ...] = ()
    source_evidence_segment_ids: dict[str, tuple[str, ...]] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_evidence_paths(self) -> "BenchmarkGold":
        if self.answer.kind != GoldAnswerKind.ABSTAIN and not self.evidence_paths:
            raise ValueError("answerable benchmark Gold requires evidence paths")
        if self.answer.kind == GoldAnswerKind.ABSTAIN and self.evidence_paths:
            raise ValueError("abstain benchmark Gold cannot claim positive evidence paths")
        for path in self.evidence_paths:
            if not path or any(not clause for clause in path):
                raise ValueError("benchmark evidence paths require non-empty paths and clauses")
            for clause in path:
                if len(set(clause)) != len(clause):
                    raise ValueError("benchmark evidence alternatives must be unique")
        for evidence_id, segment_ids in self.source_evidence_segment_ids.items():
            if not evidence_id or not segment_ids or len(set(segment_ids)) != len(segment_ids):
                raise ValueError("source evidence mappings must contain unique leaf segment IDs")
        return self


class SegmentEvaluationOutcome(StrEnum):
    COMPLETE = "complete"
    RETRIEVAL_MISSING = "retrieval_missing"
    PARTIAL_COVERAGE = "partial_coverage"
    UNSUPPORTED_STAGE = "unsupported_stage"
    RUNTIME_ERROR = "runtime_error"
    MAPPING_CORRUPTED = "mapping_corrupted"
    NOT_APPLICABLE = "not_applicable"


class SegmentClauseMatrix(BenchmarkContractModel):
    path_index: int = Field(ge=0)
    clause_index: int = Field(ge=0)
    alternatives: tuple[str, ...] = Field(min_length=1)
    matched_segment_ids: tuple[str, ...] = ()
    earliest_rank: int | None = Field(default=None, ge=1)


class SegmentEvaluationStage(BenchmarkContractModel):
    stage: Literal["raw", "ranked", "context"]
    status: SegmentTraceStatus
    outcome: SegmentEvaluationOutcome
    strict_rankable: bool
    clause_matrix: tuple[SegmentClauseMatrix, ...] = ()
    complete_path_indices: tuple[int, ...] = ()
    reason: str | None = None


class SegmentEvaluationTrace(BenchmarkContractModel):
    benchmark_contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw: SegmentEvaluationStage
    ranked: SegmentEvaluationStage
    context: SegmentEvaluationStage

    @model_validator(mode="after")
    def validate_stages(self) -> "SegmentEvaluationTrace":
        expected = {"raw": self.raw, "ranked": self.ranked, "context": self.context}
        if any(stage.stage != name for name, stage in expected.items()):
            raise ValueError("segment evaluation trace stage names must agree")
        return self


class BenchmarkManifest(BenchmarkContractModel):
    schema_version: Literal[BENCHMARK_CONTRACT_SCHEMA_VERSION] = (
        BENCHMARK_CONTRACT_SCHEMA_VERSION
    )
    dataset_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source_release_id: str | None = None
    source_release_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    segmentation_policy: BenchmarkSegmentationPolicy = Field(
        default_factory=BenchmarkSegmentationPolicy
    )
    file_checksums: dict[str, str] = Field(default_factory=dict)
    segment_count: int = Field(ge=1)
    case_count: int = Field(ge=1)
    contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_manifest(self) -> "BenchmarkManifest":
        if set(self.file_checksums) != {"segments.jsonl", "questions.jsonl", "gold.jsonl"}:
            raise ValueError("benchmark manifest must checksum every contract JSONL file")
        if any(
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
            for value in self.file_checksums.values()
        ):
            raise ValueError("benchmark manifest contains an invalid file checksum")
        if self.contract_digest != benchmark_sha256(benchmark_json(self.digest_payload())):
            raise ValueError("benchmark manifest digest does not match content")
        return self

    def digest_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "name": self.name,
            "version": self.version,
            "source_release_id": self.source_release_id,
            "source_release_digest": self.source_release_digest,
            "corpus_digest": self.corpus_digest,
            "segmentation_policy": self.segmentation_policy.model_dump(mode="json"),
            "file_checksums": dict(sorted(self.file_checksums.items())),
            "segment_count": self.segment_count,
            "case_count": self.case_count,
        }

    @classmethod
    def build(
        cls,
        *,
        dataset_id: str,
        name: str,
        version: str,
        source_release_id: str | None,
        source_release_digest: str | None,
        corpus_digest: str,
        segmentation_policy: BenchmarkSegmentationPolicy,
        file_checksums: dict[str, str],
        segment_count: int,
        case_count: int,
    ) -> "BenchmarkManifest":
        payload = {
            "schema_version": BENCHMARK_CONTRACT_SCHEMA_VERSION,
            "dataset_id": dataset_id,
            "name": name,
            "version": version,
            "source_release_id": source_release_id,
            "source_release_digest": source_release_digest,
            "corpus_digest": corpus_digest,
            "segmentation_policy": segmentation_policy.model_dump(mode="json"),
            "file_checksums": dict(sorted(file_checksums.items())),
            "segment_count": segment_count,
            "case_count": case_count,
        }
        return cls(
            **payload,
            contract_digest=benchmark_sha256(benchmark_json(payload)),
        )


@dataclass(frozen=True, slots=True)
class BenchmarkDataset:
    root: Path
    manifest: BenchmarkManifest
    segments: tuple[BenchmarkSegment, ...]
    questions: tuple[BenchmarkQuestion, ...]
    gold: tuple[BenchmarkGold, ...]

    @property
    def segments_by_id(self) -> dict[str, BenchmarkSegment]:
        return {segment.segment_id: segment for segment in self.segments}

    @property
    def gold_by_id(self) -> dict[str, BenchmarkGold]:
        return {item.gold_id: item for item in self.gold}

    @property
    def gold_by_case_id(self) -> dict[str, BenchmarkGold]:
        return {item.case_id: item for item in self.gold}
