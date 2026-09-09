"""Native v2 experiment and comparison contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.artifact_contract import artifact_digest
from rag_eval.contracts.research import (
    AnalysisContract,
    ComparisonSpec,
    LatencyProtocol,
    ModelArtifactIdentity,
    ModelLock,
)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ComparisonTier(StrEnum):
    TASK_COMPARABLE = "task_comparable"
    STRICT_CONTROLLED = "strict_controlled"
    EXPLORATORY = "exploratory"


class ExperimentSpec(ContractModel):
    experiment_id: str = Field(min_length=1)
    # A human-facing label is frozen with newly created experiments but never
    # changes the evaluation semantics or research identifiers.
    display_name: str | None = Field(default=None, max_length=160)
    bundle_id: str = Field(min_length=1)
    dataset_release_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$")
    system_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    adapter_config: dict[str, Any] = Field(default_factory=dict)
    query_config: dict[str, Any] = Field(default_factory=dict)
    metric_config: dict[str, Any] = Field(default_factory=dict)
    case_ids: list[str] | None = None
    case_selection_id: str = Field(min_length=1)
    seed: int = 0
    repetitions: int = Field(default=1, ge=1)
    # Formal experiments must be frozen against immutable, verified artifacts.
    formal: bool = False
    model_lock_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    model_artifacts: dict[str, ModelArtifactIdentity] = Field(default_factory=dict)
    comparison_spec_digest: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    analysis_contract_digest: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    latency_protocol_digest: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    # Full frozen content is retained with a formal ExperimentSpec so the
    # runner can enforce its warmup/cache lifecycle instead of trusting a hash
    # label alone.
    analysis_contract: AnalysisContract | None = None
    latency_protocol: LatencyProtocol | None = None
    comparison_spec: ComparisonSpec | None = None

    @model_validator(mode="after")
    def validate_formal_model_lock(self) -> ExperimentSpec:
        if not self.formal:
            return self
        if not self.model_lock_digest:
            raise ValueError("formal experiment requires model_lock_digest")
        if not self.comparison_spec_digest:
            raise ValueError("formal experiment requires comparison_spec_digest")
        if not self.analysis_contract_digest:
            raise ValueError("formal experiment requires analysis_contract_digest")
        if not self.latency_protocol_digest:
            raise ValueError("formal experiment requires latency_protocol_digest")
        if not self.model_artifacts:
            raise ValueError("formal experiment requires model_artifacts")
        unverified = [
            name for name, model in self.model_artifacts.items() if not model.verified
        ]
        if unverified:
            raise ValueError(
                f"formal experiment has unverified models: {sorted(unverified)}"
            )
        expected_lock_digest = artifact_digest(ModelLock(models=self.model_artifacts))
        if self.model_lock_digest != expected_lock_digest:
            raise ValueError("model_lock_digest does not match model_artifacts")
        if self.analysis_contract is None:
            raise ValueError("formal experiment requires analysis_contract content")
        if self.analysis_contract_digest != artifact_digest(self.analysis_contract):
            raise ValueError("analysis_contract_digest does not match analysis_contract")
        if self.latency_protocol is None:
            raise ValueError("formal experiment requires latency_protocol content")
        if self.latency_protocol_digest != artifact_digest(self.latency_protocol):
            raise ValueError("latency_protocol_digest does not match latency_protocol")
        if self.comparison_spec is None:
            raise ValueError("formal experiment requires comparison_spec content")
        if self.comparison_spec_digest != artifact_digest(self.comparison_spec):
            raise ValueError("comparison_spec_digest does not match comparison_spec")
        return self
