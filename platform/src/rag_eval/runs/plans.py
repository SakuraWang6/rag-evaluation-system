"""Immutable admission-time execution plans for native v2 Runs."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    ValidationError,
    model_validator,
)

from rag_eval.artifact_contract import artifact_digest, canonical_artifact_bytes
from rag_eval.contracts.observation import StageName
from rag_eval.contracts.run import ExperimentSpec
from rag_eval.evaluation.unified.models import (
    FORMAL_CORE_METRIC_IDS,
    EvaluationProfile,
    MetricDescriptor,
)
from rag_eval.evaluation.unified.scorer import scorer_source_digest
from rag_eval.storage.atomic import atomic_write_bytes

RESOLVED_RUN_PLAN_SCHEMA_VERSION = "2.0"
_SAFE_ID_PATTERN = r"^[A-Za-z0-9_-]+$"


class RunPlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NativeQueryConfigV2(RunPlanModel):
    """The complete Platform-owned query configuration for a native Run."""

    generate_answer: StrictBool
    retrieval_candidate_k: StrictInt = Field(ge=1)
    final_context_k: StrictInt = Field(ge=1)
    max_context_tokens: StrictInt = Field(ge=1)
    generation_options: dict[str, Any]

    @model_validator(mode="after")
    def validate_cutoff_order(self) -> NativeQueryConfigV2:
        if self.final_context_k > self.retrieval_candidate_k:
            raise ValueError(
                "final_context_k cannot exceed retrieval_candidate_k"
            )
        return self


class NativeMetricConfigV2(RunPlanModel):
    """The only formal metric window supported by Native v2."""

    k_values: tuple[StrictInt, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_formal_cutoffs(self) -> NativeMetricConfigV2:
        if self.k_values != (1, 3, 5):
            raise ValueError("metric_config k_values must be exactly [1, 3, 5]")
        return self


class BenchmarkReleaseIdentityV2(RunPlanModel):
    release_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    release_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_bundle_id: str = Field(pattern=r"^[0-9a-f]{64}$")


class OriginalDocumentIdentityV2(RunPlanModel):
    document_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_path: str = Field(min_length=1)
    mime_type: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_relative_path(self) -> OriginalDocumentIdentityV2:
        path = PurePosixPath(self.runtime_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("runtime_path must be a safe relative path")
        return self


class ResolvedSystemIdentityV2(RunPlanModel):
    """Secret-free identity of the exact system/worker profile admitted."""

    system_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    adapter_factory: str = Field(pattern=r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")
    worker_profile_kind: Literal["product_profile", "registered_system"]
    worker_profile_id: str = Field(min_length=1)
    worker_profile_version: str = Field(min_length=1)
    worker_profile_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    system_config_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    execution_provider: str = Field(min_length=1)
    worker_request_timeout_seconds: float = Field(gt=0)


class ResolvedResourceLimitsV2(RunPlanModel):
    worker_request_timeout_seconds: float = Field(gt=0)
    max_context_tokens: StrictInt = Field(ge=1)


class ResolvedRunPlanV2(RunPlanModel):
    """Content-addressed snapshot required before a native Run is queued."""

    schema_version: Literal["2.0"] = RESOLVED_RUN_PLAN_SCHEMA_VERSION
    execution_contract: Literal["native-document/v2"] = "native-document/v2"
    experiment_id: str = Field(pattern=_SAFE_ID_PATTERN)
    experiment_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    benchmark_release: BenchmarkReleaseIdentityV2
    original_document: OriginalDocumentIdentityV2
    system: ResolvedSystemIdentityV2
    adapter_config_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    query_config: NativeQueryConfigV2
    metric_config: NativeMetricConfigV2
    evaluation_profile: EvaluationProfile
    metric_descriptors: tuple[MetricDescriptor, ...]
    case_ids: tuple[str, ...] = Field(min_length=1)
    case_selection_id: str = Field(min_length=1)
    seed: int
    repetitions: int = Field(ge=1)
    resource_limits: ResolvedResourceLimitsV2

    @model_validator(mode="after")
    def validate_internal_consistency(self) -> ResolvedRunPlanV2:
        if tuple(sorted(set(self.case_ids))) != self.case_ids:
            raise ValueError("resolved case_ids must be unique and sorted")
        profile = self.evaluation_profile
        if profile.candidate_cutoff != self.query_config.retrieval_candidate_k:
            raise ValueError("evaluation candidate cutoff must match query config")
        if profile.context_budget != self.query_config.max_context_tokens:
            raise ValueError("evaluation context budget must match query config")
        if (
            self.resource_limits.max_context_tokens
            != self.query_config.max_context_tokens
        ):
            raise ValueError("resource context budget must match query config")
        if (
            self.resource_limits.worker_request_timeout_seconds
            != self.system.worker_request_timeout_seconds
        ):
            raise ValueError("resource timeout must match the worker profile")
        descriptors = {item.metric_id: item for item in self.metric_descriptors}
        if (
            tuple(item.metric_id for item in self.metric_descriptors)
            != FORMAL_CORE_METRIC_IDS
        ):
            raise ValueError(
                "resolved plan must bind every formal core metric in canonical order"
            )
        for metric_id, descriptor in descriptors.items():
            cutoff = int(metric_id.rsplit("@", 1)[1])
            if (
                descriptor.stage != StageName.RANKED
                or descriptor.cutoff != cutoff
                or descriptor.candidate_cutoff != profile.candidate_cutoff
                or descriptor.ranked_cutoff != cutoff
                or descriptor.context_budget != profile.context_budget
            ):
                raise ValueError(
                    f"metric descriptor does not match evaluation profile: {metric_id}"
                )
        return self

    def matches_experiment(self, experiment: ExperimentSpec) -> bool:
        try:
            query_config = NativeQueryConfigV2.model_validate(
                experiment.query_config
            )
            metric_config = NativeMetricConfigV2.model_validate(
                experiment.metric_config
            )
        except ValidationError:
            return False
        return (
            self.experiment_id == experiment.experiment_id
            and self.experiment_digest == artifact_digest(experiment)
            and self.benchmark_release.release_id == experiment.dataset_release_id
            and self.benchmark_release.runtime_bundle_id == experiment.bundle_id
            and self.system.system_id == experiment.system_id
            and self.system.adapter_id == experiment.adapter_id
            and self.adapter_config_digest == digest_json(experiment.adapter_config)
            and self.query_config == query_config
            and self.metric_config == metric_config
            and (
                experiment.case_ids is None
                or self.case_ids == tuple(sorted(experiment.case_ids))
            )
            and self.case_selection_id == experiment.case_selection_id
            and self.seed == experiment.seed
            and self.repetitions == experiment.repetitions
        )


class ResolvedRunPlanReferenceV2(RunPlanModel):
    path: str = Field(min_length=1)
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def digest_json(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def formal_metric_descriptors(
    profile: EvaluationProfile,
) -> tuple[MetricDescriptor, ...]:
    """Bind every formal metric to the scorer and exact admission-time windows."""

    scorer_digest = scorer_source_digest()
    return tuple(
        MetricDescriptor(
            metric_id=metric_id,
            scorer_digest=scorer_digest,
            aggregation="mses_clause_equal_weight",
            stage=StageName.RANKED,
            cutoff=int(metric_id.rsplit("@", 1)[1]),
            candidate_cutoff=profile.candidate_cutoff,
            ranked_cutoff=int(metric_id.rsplit("@", 1)[1]),
            context_budget=profile.context_budget,
        )
        for metric_id in FORMAL_CORE_METRIC_IDS
    )


class ResolvedRunPlanStore:
    """Write-once plan snapshots, bound one-to-one to Experiment IDs."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def create(self, plan: ResolvedRunPlanV2) -> ResolvedRunPlanReferenceV2:
        filename = f"{plan.experiment_id}.json"
        path = self.root / filename
        payload = canonical_artifact_bytes(plan)
        with self._lock:
            if path.exists():
                if path.read_bytes() != payload:
                    raise ValueError(
                        "experiment ID already has a different immutable resolved plan"
                    )
            else:
                atomic_write_bytes(path, payload)
        return ResolvedRunPlanReferenceV2(
            path=(PurePosixPath(self.root.name) / filename).as_posix(),
            digest=artifact_digest(plan),
        )

    def get(self, reference: ResolvedRunPlanReferenceV2) -> ResolvedRunPlanV2:
        relative = PurePosixPath(reference.path)
        if (
            relative.is_absolute()
            or len(relative.parts) != 2
            or relative.parts[0] != self.root.name
        ):
            raise ValueError("resolved plan reference is outside the plan store")
        path = self.root / relative.name
        with self._lock:
            payload = path.read_text(encoding="utf-8")
        plan = ResolvedRunPlanV2.model_validate_json(payload)
        if path.name != f"{plan.experiment_id}.json":
            raise ValueError("resolved plan path does not match its Experiment ID")
        if artifact_digest(plan) != reference.digest:
            raise ValueError("resolved plan digest mismatch")
        return plan

    def list(self) -> list[ResolvedRunPlanV2]:
        with self._lock:
            payloads = [
                path.read_text(encoding="utf-8")
                for path in sorted(self.root.glob("*.json"))
            ]
        return [ResolvedRunPlanV2.model_validate_json(item) for item in payloads]


__all__ = [
    "RESOLVED_RUN_PLAN_SCHEMA_VERSION",
    "BenchmarkReleaseIdentityV2",
    "NativeMetricConfigV2",
    "NativeQueryConfigV2",
    "OriginalDocumentIdentityV2",
    "ResolvedResourceLimitsV2",
    "ResolvedRunPlanReferenceV2",
    "ResolvedRunPlanStore",
    "ResolvedRunPlanV2",
    "ResolvedSystemIdentityV2",
    "digest_json",
    "formal_metric_descriptors",
]
