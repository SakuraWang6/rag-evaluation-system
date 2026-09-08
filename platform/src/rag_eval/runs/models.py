"""Immutable Artifact 2.0 contracts owned by Run / Orchestration."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.artifact_contract import artifact_digest
from rag_eval.contracts.canonical import canonical_json
from rag_eval.contracts.dataset import (
    GoldAnswer,
    GoldEvidenceSet,
    GoldSourceIdentity,
)
from rag_eval.contracts.observation import (
    AdapterRunResultV2,
    ObservationProfileIdentity,
    ObservationStatus,
    RuntimeProfileIdentity,
)
from rag_eval.evaluation.unified.models import (
    FORMAL_CORE_METRIC_IDS,
    UNIFIED_EVALUATION_SCHEMA_VERSION,
    UNIFIED_SCORER_ID,
    UNIFIED_SCORER_VERSION,
    EvaluationMetric,
    EvaluationMetricStatus,
    FailureKind,
    PipelineDelta,
    ProofGatedFailure,
    StageLocalization,
    UnifiedEvaluationResult,
)

ARTIFACT_V2_SCHEMA_VERSION = "2.0"
ARTIFACT_V2_DIRECTORY = "artifact-v2"
ARTIFACT_V2_MANIFEST = "artifact.json"
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _digest_payload(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_json(_jsonable(value)).encode("utf-8")
    ).hexdigest()


class ArtifactV2Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArtifactAnswerStatus(StrEnum):
    OBSERVED = "observed"
    NEEDS_REVIEW = "needs_review"
    UNAVAILABLE = "unavailable"


class ArtifactEvidenceStatus(StrEnum):
    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"


class ArtifactAnswerJudgment(ArtifactV2Model):
    status: ArtifactAnswerStatus
    value: Literal["correct", "incorrect"] | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_value(self) -> ArtifactAnswerJudgment:
        if self.status == ArtifactAnswerStatus.OBSERVED and self.value is None:
            raise ValueError("observed answer judgment requires a value")
        if self.status != ArtifactAnswerStatus.OBSERVED and self.value is not None:
            raise ValueError("non-observed answer judgment cannot carry a value")
        return self


class ArtifactEvidenceJudgment(ArtifactV2Model):
    status: ArtifactEvidenceStatus
    value: Literal["complete", "partial", "missing"] | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_value(self) -> ArtifactEvidenceJudgment:
        if self.status == ArtifactEvidenceStatus.OBSERVED and self.value is None:
            raise ValueError("observed evidence judgment requires a value")
        if self.status != ArtifactEvidenceStatus.OBSERVED and self.value is not None:
            raise ValueError("unavailable evidence judgment cannot carry a value")
        return self


class BenchmarkCaseSnapshotV2(ArtifactV2Model):
    case_id: str = Field(pattern=_SAFE_ID.pattern)
    question: str = Field(min_length=1)
    gold_answer: GoldAnswer
    gold_evidence_set: GoldEvidenceSet


class BenchmarkIdentityV2(ArtifactV2Model):
    dataset_release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    dataset_release_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_selection_id: str = Field(min_length=1)
    benchmark_snapshot_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_identities: tuple[GoldSourceIdentity, ...] = Field(min_length=1)

    @classmethod
    def build(
        cls,
        *,
        dataset_release_id: str,
        dataset_release_digest: str,
        bundle_id: str,
        case_selection_id: str,
        cases: tuple[BenchmarkCaseSnapshotV2, ...],
    ) -> BenchmarkIdentityV2:
        if not cases:
            raise ValueError("Artifact 2.0 benchmark requires at least one case")
        unique_cases = {item.case_id: item for item in cases}
        if len(unique_cases) != len(cases):
            raise ValueError("Artifact 2.0 benchmark repeats case IDs")
        sources = {
            source.document_id: source
            for case in cases
            for source in case.gold_evidence_set.source_identities
        }
        for case in cases:
            for source in case.gold_evidence_set.source_identities:
                if sources[source.document_id] != source:
                    raise ValueError(
                        "Artifact 2.0 benchmark has conflicting source identities"
                    )
        if not sources:
            raise ValueError("Artifact 2.0 benchmark requires pinned source identities")
        snapshot = tuple(
            unique_cases[case_id].model_dump(mode="json")
            for case_id in sorted(unique_cases)
        )
        return cls(
            dataset_release_id=dataset_release_id,
            dataset_release_digest=dataset_release_digest,
            bundle_id=bundle_id,
            case_selection_id=case_selection_id,
            benchmark_snapshot_digest=_digest_payload(snapshot),
            source_identities=tuple(sources[key] for key in sorted(sources)),
        )


class TraceValidationRecordV2(ArtifactV2Model):
    status: ObservationStatus
    reason: str | None = None
    adapter_result_digest: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    wire_shadow_verified: bool = False

    @model_validator(mode="after")
    def validate_observed(self) -> TraceValidationRecordV2:
        if self.status == ObservationStatus.OBSERVED:
            if self.adapter_result_digest is None:
                raise ValueError("observed trace validation requires a result digest")
            if self.reason is not None:
                raise ValueError("observed trace validation cannot carry a failure reason")
        elif not (self.reason or "").strip():
            raise ValueError("non-observed trace validation requires a reason")
        return self


class PersistedEvaluationV2(ArtifactV2Model):
    schema_version: Literal[UNIFIED_EVALUATION_SCHEMA_VERSION] = (
        UNIFIED_EVALUATION_SCHEMA_VERSION
    )
    scorer_id: Literal[UNIFIED_SCORER_ID] = UNIFIED_SCORER_ID
    scorer_version: Literal[UNIFIED_SCORER_VERSION] = UNIFIED_SCORER_VERSION
    scorer_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    trace_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    gold_evidence_set_id: str = Field(min_length=1)
    metrics: tuple[EvaluationMetric, ...]
    localizations: tuple[StageLocalization, ...] = ()
    pipeline_deltas: tuple[PipelineDelta, ...] = ()
    failure: ProofGatedFailure | None = None

    @model_validator(mode="after")
    def validate_metrics(self) -> PersistedEvaluationV2:
        metric_ids = [item.metric_id for item in self.metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("persisted evaluation repeats metric IDs")
        if any(
            item.descriptor.scorer_id != self.scorer_id
            or item.descriptor.scorer_version != self.scorer_version
            or item.descriptor.scorer_digest != self.scorer_digest
            for item in self.metrics
        ):
            raise ValueError("metric descriptor differs from evaluation identity")
        return self

    @classmethod
    def from_unified(
        cls, value: UnifiedEvaluationResult
    ) -> PersistedEvaluationV2:
        return cls(**value.model_dump(mode="python"))

    def metric(self, metric_id: str) -> EvaluationMetric:
        for item in self.metrics:
            if item.metric_id == metric_id:
                return item
        raise KeyError(metric_id)

    @property
    def core_metrics_available(self) -> bool:
        by_id = {item.metric_id: item for item in self.metrics}
        return all(
            metric_id in by_id
            and by_id[metric_id].status == EvaluationMetricStatus.OBSERVED
            for metric_id in FORMAL_CORE_METRIC_IDS
        )


class ArtifactCaseErrorV2(ArtifactV2Model):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False


class RunArtifactCaseV2(ArtifactV2Model):
    schema_version: Literal[ARTIFACT_V2_SCHEMA_VERSION] = ARTIFACT_V2_SCHEMA_VERSION
    case_id: str = Field(pattern=_SAFE_ID.pattern)
    repetition: int = Field(ge=1)
    seed: int
    status: Literal["completed", "timeout", "system_error", "cancelled"]
    question: str = Field(min_length=1)
    gold_answer: GoldAnswer
    gold_evidence_set: GoldEvidenceSet
    trace_validation: TraceValidationRecordV2
    adapter_result: AdapterRunResultV2 | None = None
    evaluation: PersistedEvaluationV2
    answer_judgment: ArtifactAnswerJudgment
    evidence_judgment: ArtifactEvidenceJudgment
    error: ArtifactCaseErrorV2 | None = None
    started_at: datetime
    completed_at: datetime
    case_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @property
    def observation_status(self) -> ObservationStatus:
        return self.trace_validation.status

    @model_validator(mode="after")
    def validate_case(self) -> RunArtifactCaseV2:
        observed = self.trace_validation.status == ObservationStatus.OBSERVED
        if observed != (self.adapter_result is not None):
            raise ValueError("observed trace status and Adapter result must agree")
        if observed:
            assert self.adapter_result is not None
            if self.adapter_result.trace.case_id != self.case_id:
                raise ValueError("Artifact case and Unified Trace IDs differ")
            if self.evaluation.trace_digest != self.adapter_result.trace.trace_digest:
                raise ValueError("persisted evaluation references another trace")
            if self.trace_validation.adapter_result_digest != artifact_digest(
                self.adapter_result
            ):
                raise ValueError("trace validation digest differs from Adapter result")
        elif self.evaluation.trace_digest is not None:
            raise ValueError("unobserved evaluation cannot claim a trace digest")
        if not observed and any(
            metric.status == EvaluationMetricStatus.OBSERVED
            for metric in self.evaluation.metrics
        ):
            raise ValueError("unobserved trace cannot produce observed metrics")
        if not observed and (
            self.evaluation.localizations or self.evaluation.pipeline_deltas
        ):
            raise ValueError("unobserved trace cannot produce localization facts")
        if not observed and (
            self.evaluation.failure is None
            or self.evaluation.failure.kind != FailureKind.UNOBSERVABLE
        ):
            raise ValueError("unobserved trace requires UNOBSERVABLE attribution")
        if not observed and (
            self.answer_judgment.status != ArtifactAnswerStatus.UNAVAILABLE
            or self.evidence_judgment.status != ArtifactEvidenceStatus.UNAVAILABLE
        ):
            raise ValueError("unobserved trace cannot produce observed judgments")
        if self.status == "completed" and self.error is not None:
            raise ValueError("completed Artifact case cannot carry an execution error")
        if self.status != "completed" and self.error is None:
            raise ValueError("failed Artifact case requires an execution error")
        if self.evaluation.gold_evidence_set_id != (
            self.gold_evidence_set.gold_evidence_set_id
        ):
            raise ValueError("persisted evaluation references another Gold set")
        if self.completed_at < self.started_at:
            raise ValueError("Artifact case completion precedes its start")
        expected = _digest_payload(
            self.model_dump(
                mode="json", exclude={"case_digest"}, exclude_none=True
            )
        )
        if self.case_digest != expected:
            raise ValueError("Artifact case digest does not match its content")
        return self

    @classmethod
    def build(cls, **values: Any) -> RunArtifactCaseV2:
        normalized = cls.model_construct(
            **values,
            case_digest="sha256:" + "0" * 64,
        )
        digest = _digest_payload(
            normalized.model_dump(
                mode="json", exclude={"case_digest"}, exclude_none=True
            )
        )
        return cls(**values, case_digest=digest)


class AggregateMetricV2(ArtifactV2Model):
    metric_id: str = Field(min_length=1)
    status: EvaluationMetricStatus
    value: float | None = Field(default=None, ge=0)
    case_count: int = Field(ge=1)
    observed_case_count: int = Field(ge=0)
    unavailable_case_count: int = Field(ge=0)
    descriptor_digests: tuple[str, ...]
    reason: str | None = None

    @model_validator(mode="after")
    def validate_aggregate(self) -> AggregateMetricV2:
        if self.observed_case_count + self.unavailable_case_count != self.case_count:
            raise ValueError("aggregate metric status counts do not cover all cases")
        if self.status == EvaluationMetricStatus.OBSERVED and self.value is None:
            raise ValueError("observed aggregate metric requires a value")
        if self.status != EvaluationMetricStatus.OBSERVED and self.value is not None:
            raise ValueError("unavailable aggregate metric cannot carry a value")
        return self


class LeaderboardEligibilityV2(ArtifactV2Model):
    eligible: bool
    case_count: int = Field(ge=1)
    required_metric_ids: tuple[str, ...] = FORMAL_CORE_METRIC_IDS
    descriptor_digests: dict[str, str] = Field(default_factory=dict)
    reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_eligibility(self) -> LeaderboardEligibilityV2:
        required = set(self.required_metric_ids)
        if self.eligible:
            if self.reasons:
                raise ValueError("eligible run cannot carry ineligibility reasons")
            if set(self.descriptor_digests) != required:
                raise ValueError("eligible run requires every core descriptor digest")
        elif not self.reasons:
            raise ValueError("ineligible run requires at least one reason")
        return self


class RunArtifactSummaryV2(ArtifactV2Model):
    schema_version: Literal[ARTIFACT_V2_SCHEMA_VERSION] = ARTIFACT_V2_SCHEMA_VERSION
    case_count: int = Field(ge=1)
    execution_status_counts: dict[str, int]
    metrics: tuple[AggregateMetricV2, ...]
    leaderboard_eligibility: LeaderboardEligibilityV2


class ArtifactCaseIndexEntryV2(ArtifactV2Model):
    case_id: str = Field(pattern=_SAFE_ID.pattern)
    repetition: int = Field(ge=1)
    seed: int
    status: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer_judgment: ArtifactAnswerJudgment
    evidence_judgment: ArtifactEvidenceJudgment
    core_metrics_available: bool
    failure_kind: str | None = None
    artifact_path: str = Field(min_length=1)


class ArtifactCaseIndexV2(ArtifactV2Model):
    schema_version: Literal[ARTIFACT_V2_SCHEMA_VERSION] = ARTIFACT_V2_SCHEMA_VERSION
    cases: tuple[ArtifactCaseIndexEntryV2, ...]


class ArtifactMemberV2(ArtifactV2Model):
    member_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    depends_on: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_path(self) -> ArtifactMemberV2:
        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts or str(path) != self.path:
            raise ValueError("Artifact member path must be safe and canonical")
        return self


class ArtifactChecksumGraphV2(ArtifactV2Model):
    nodes: tuple[ArtifactMemberV2, ...] = Field(min_length=1)
    graph_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_graph(self) -> ArtifactChecksumGraphV2:
        ids = [item.member_id for item in self.nodes]
        paths = [item.path for item in self.nodes]
        if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
            raise ValueError("Artifact checksum graph repeats IDs or paths")
        known = set(ids)
        if unknown := {
            dependency
            for item in self.nodes
            for dependency in item.depends_on
            if dependency not in known
        }:
            raise ValueError(f"Artifact checksum graph has unknown dependencies: {unknown}")
        dependencies = {item.member_id: set(item.depends_on) for item in self.nodes}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise ValueError("Artifact checksum graph contains a cycle")
            if node_id in visited:
                return
            visiting.add(node_id)
            for dependency in dependencies[node_id]:
                visit(dependency)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in ids:
            visit(node_id)
        expected = _digest_payload(
            tuple(
                item.model_dump(mode="json")
                for item in sorted(self.nodes, key=lambda value: value.member_id)
            )
        )
        if self.graph_digest != expected:
            raise ValueError("Artifact checksum graph digest does not match its nodes")
        return self

    @classmethod
    def build(
        cls, nodes: tuple[ArtifactMemberV2, ...]
    ) -> ArtifactChecksumGraphV2:
        digest = _digest_payload(
            tuple(
                item.model_dump(mode="json")
                for item in sorted(nodes, key=lambda value: value.member_id)
            )
        )
        return cls(nodes=nodes, graph_digest=digest)


class ArtifactCaseReferenceV2(ArtifactV2Model):
    case_id: str = Field(pattern=_SAFE_ID.pattern)
    repetition: int = Field(ge=1)
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RunArtifactManifestV2(ArtifactV2Model):
    schema_version: Literal[ARTIFACT_V2_SCHEMA_VERSION] = ARTIFACT_V2_SCHEMA_VERSION
    artifact_contract_version: Literal[ARTIFACT_V2_SCHEMA_VERSION] = (
        ARTIFACT_V2_SCHEMA_VERSION
    )
    producer: Literal["rag_eval_platform"] = "rag_eval_platform"
    run_id: str = Field(pattern=_SAFE_ID.pattern)
    experiment_id: str = Field(pattern=_SAFE_ID.pattern)
    status: Literal["completed"] = "completed"
    benchmark_identity: BenchmarkIdentityV2
    runtime_profiles: tuple[RuntimeProfileIdentity, ...] = ()
    observation_profiles: tuple[ObservationProfileIdentity, ...] = ()
    cases: tuple[ArtifactCaseReferenceV2, ...] = Field(min_length=1)
    case_index_path: Literal["case-index.json"] = "case-index.json"
    summary_path: Literal["summary.json"] = "summary.json"
    checksum_graph: ArtifactChecksumGraphV2
    started_at: datetime
    completed_at: datetime
    artifact_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_manifest(self) -> RunArtifactManifestV2:
        case_keys = [(item.case_id, item.repetition) for item in self.cases]
        if len(case_keys) != len(set(case_keys)):
            raise ValueError("Artifact manifest repeats case executions")
        if len(self.runtime_profiles) != len(
            {
                (item.profile_id, item.configuration_digest)
                for item in self.runtime_profiles
            }
        ):
            raise ValueError("Artifact manifest repeats runtime profiles")
        if len(self.observation_profiles) != len(
            {item.profile_digest for item in self.observation_profiles}
        ):
            raise ValueError("Artifact manifest repeats observation profiles")
        if any(
            item.path != case_artifact_path(item.case_id, item.repetition)
            for item in self.cases
        ):
            raise ValueError("Artifact manifest case path is not canonical")
        nodes = {item.path: item.sha256 for item in self.checksum_graph.nodes}
        expected_members = {
            item.path: item.sha256 for item in self.cases
        } | {self.case_index_path: nodes.get(self.case_index_path, "")} | {
            self.summary_path: nodes.get(self.summary_path, "")
        }
        if any(nodes.get(path) != digest for path, digest in expected_members.items()):
            raise ValueError("Artifact manifest references differ from checksum graph")
        if set(nodes) != set(expected_members):
            raise ValueError("checksum graph must enumerate every authoritative member")
        nodes_by_path = {
            item.path: item for item in self.checksum_graph.nodes
        }
        case_node_ids = {
            nodes_by_path[item.path].member_id for item in self.cases
        }
        if any(nodes_by_path[item.path].depends_on for item in self.cases):
            raise ValueError("Artifact case checksum nodes must be graph leaves")
        if set(nodes_by_path[self.case_index_path].depends_on) != case_node_ids:
            raise ValueError("case index checksum must depend on every case")
        if set(nodes_by_path[self.summary_path].depends_on) != case_node_ids:
            raise ValueError("summary checksum must depend on every case")
        if self.completed_at < self.started_at:
            raise ValueError("Artifact completion precedes its start")
        expected = _digest_payload(
            self.model_dump(
                mode="json", exclude={"artifact_digest"}, exclude_none=True
            )
        )
        if self.artifact_digest != expected:
            raise ValueError("Artifact manifest digest does not match its content")
        return self

    @classmethod
    def build(cls, **values: Any) -> RunArtifactManifestV2:
        normalized = cls.model_construct(
            **values,
            artifact_digest="sha256:" + "0" * 64,
        )
        digest = _digest_payload(
            normalized.model_dump(
                mode="json", exclude={"artifact_digest"}, exclude_none=True
            )
        )
        return cls(**values, artifact_digest=digest)


def descriptor_digest(metric: EvaluationMetric) -> str:
    return _digest_payload(metric.descriptor.model_dump(mode="json"))


def case_artifact_path(case_id: str, repetition: int) -> str:
    if not _SAFE_ID.fullmatch(case_id):
        raise ValueError(f"unsafe Artifact 2.0 case ID: {case_id!r}")
    if repetition < 1:
        raise ValueError("Artifact 2.0 repetition must be positive")
    return f"cases/rep-{repetition:04d}-{case_id}.json"


__all__ = [
    "ARTIFACT_V2_DIRECTORY",
    "ARTIFACT_V2_MANIFEST",
    "AggregateMetricV2",
    "ArtifactAnswerJudgment",
    "ArtifactAnswerStatus",
    "ArtifactCaseErrorV2",
    "ArtifactCaseIndexEntryV2",
    "ArtifactCaseIndexV2",
    "ArtifactCaseReferenceV2",
    "ArtifactChecksumGraphV2",
    "ArtifactEvidenceJudgment",
    "ArtifactEvidenceStatus",
    "ArtifactMemberV2",
    "BenchmarkCaseSnapshotV2",
    "BenchmarkIdentityV2",
    "LeaderboardEligibilityV2",
    "PersistedEvaluationV2",
    "RunArtifactCaseV2",
    "RunArtifactManifestV2",
    "RunArtifactSummaryV2",
    "TraceValidationRecordV2",
    "case_artifact_path",
    "descriptor_digest",
]
