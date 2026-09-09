"""Scorer-free presentation models backed exclusively by Artifact 2.0."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rag_eval.evaluation.unified.models import MetricDescriptor
from rag_eval.runs.artifacts import ArtifactV2Reader, ArtifactV2Verification
from rag_eval.runs.models import (
    ARTIFACT_V2_DIRECTORY,
    ArtifactAnswerJudgment,
    ArtifactEvidenceJudgment,
    RunArtifactCaseV2,
    RunArtifactManifestV2,
    RunArtifactSummaryV2,
    descriptor_digest,
)
from rag_eval.runs.plans import ResolvedRunPlanV2
from rag_eval.runs.records import (
    RunRecordStateV2,
    artifact_plan_binding_errors,
)

ARTIFACT_PRESENTATION_SCHEMA_VERSION = "2.0"
CORRUPTED_REASON = (
    "Artifact 2.0 integrity or RunRecord binding validation failed; persisted "
    "result content is withheld from scoring and presentation."
)


class ArtifactPresentationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArtifactViewAvailability(StrEnum):
    AVAILABLE = "available"
    CORRUPTED = "corrupted"


class ArtifactVerificationView(ArtifactPresentationModel):
    valid: bool
    missing: tuple[str, ...] = ()
    unexpected: tuple[str, ...] = ()
    mismatched: tuple[str, ...] = ()
    invalid_models: tuple[str, ...] = ()

    @classmethod
    def from_v2(cls, value: ArtifactV2Verification) -> ArtifactVerificationView:
        return cls(
            valid=value.valid,
            missing=value.missing,
            unexpected=value.unexpected,
            mismatched=value.mismatched,
            invalid_models=value.invalid_models,
        )


class RunRecordViewV2(ArtifactPresentationModel):
    """Public orchestration view joined with immutable plan identity only."""

    schema_version: Literal["2.0"] = ARTIFACT_PRESENTATION_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    state: RunRecordStateV2
    resolved_plan_path: str = Field(min_length=1)
    resolved_plan_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    benchmark_release_id: str = Field(min_length=1)
    system_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    worker_profile_id: str = Field(min_length=1)
    worker_profile_version: str = Field(min_length=1)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    execution_error: str | None = None
    artifact_path: str | None = None
    artifact_digest: str | None = None
    display_name: str = Field(min_length=1)
    display_name_source: Literal["override", "generated"]


class MetricDescriptorBindingView(ArtifactPresentationModel):
    metric_id: str = Field(min_length=1)
    descriptor_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    descriptor: MetricDescriptor


class RunArtifactViewEnvelope(ArtifactPresentationModel):
    schema_version: Literal["2.0"] = ARTIFACT_PRESENTATION_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    artifact_contract_version: Literal["2.0"] = "2.0"
    availability: ArtifactViewAvailability
    reason: str | None = None
    verification: ArtifactVerificationView


class RunArtifactOverviewView(RunArtifactViewEnvelope):
    manifest: RunArtifactManifestV2 | None = None
    summary: RunArtifactSummaryV2 | None = None
    metric_descriptors: tuple[MetricDescriptorBindingView, ...] = ()


class RunCaseIndexEntryView(ArtifactPresentationModel):
    case_id: str = Field(min_length=1)
    repetition: int = Field(ge=1)
    seed: int
    status: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer_judgment: ArtifactAnswerJudgment
    evidence_judgment: ArtifactEvidenceJudgment
    core_metrics_available: bool = False
    failure_kind: str | None = None


class RunArtifactCaseIndexView(RunArtifactViewEnvelope):
    cases: tuple[RunCaseIndexEntryView, ...] = ()


class RunArtifactCaseView(RunArtifactViewEnvelope):
    artifact_case: RunArtifactCaseV2 | None = None


class RunArtifactCaseCollectionView(RunArtifactViewEnvelope):
    cases: tuple[RunArtifactCaseView, ...] = ()


class ArtifactPresentationReader:
    """Expose only a verified Artifact 2.0 bound to its RunRecordV2."""

    def __init__(
        self,
        run_directory: Path,
        *,
        run_id: str,
        expected_experiment_id: str | None = None,
        expected_artifact_digest: str | None = None,
        expected_benchmark_release_id: str | None = None,
        expected_benchmark_release_digest: str | None = None,
        expected_bundle_id: str | None = None,
        expected_case_selection_id: str | None = None,
        expected_plan: ResolvedRunPlanV2 | None = None,
    ) -> None:
        self.run_directory = run_directory
        self.run_id = run_id
        self.expected_experiment_id = expected_experiment_id
        self.expected_artifact_digest = expected_artifact_digest
        self.expected_benchmark_release_id = expected_benchmark_release_id
        self.expected_benchmark_release_digest = expected_benchmark_release_digest
        self.expected_bundle_id = expected_bundle_id
        self.expected_case_selection_id = expected_case_selection_id
        self.expected_plan = expected_plan

    @property
    def artifact_root(self) -> Path:
        return self.run_directory / ARTIFACT_V2_DIRECTORY

    def overview(self) -> RunArtifactOverviewView:
        state, verification = self._state()
        if state == ArtifactViewAvailability.CORRUPTED:
            return RunArtifactOverviewView(**self._envelope(state, verification))
        reader = ArtifactV2Reader(self.artifact_root)
        cases = reader.cases()
        bindings: dict[tuple[str, str], MetricDescriptorBindingView] = {}
        for case in cases:
            for metric in case.evaluation.metrics:
                digest = descriptor_digest(metric)
                bindings[(metric.metric_id, digest)] = MetricDescriptorBindingView(
                    metric_id=metric.metric_id,
                    descriptor_digest=digest,
                    descriptor=metric.descriptor,
                )
        return RunArtifactOverviewView(
            **self._envelope(state, verification),
            manifest=reader.manifest(),
            summary=reader.summary(),
            metric_descriptors=tuple(bindings[key] for key in sorted(bindings)),
        )

    def case_index(self) -> RunArtifactCaseIndexView:
        state, verification = self._state()
        if state == ArtifactViewAvailability.CORRUPTED:
            return RunArtifactCaseIndexView(**self._envelope(state, verification))
        entries = tuple(
            RunCaseIndexEntryView(
                case_id=item.case_id,
                repetition=item.repetition,
                seed=item.seed,
                status=item.status,
                question=item.question,
                answer_judgment=item.answer_judgment,
                evidence_judgment=item.evidence_judgment,
                core_metrics_available=item.core_metrics_available,
                failure_kind=item.failure_kind,
            )
            for item in ArtifactV2Reader(self.artifact_root).case_index().cases
        )
        return RunArtifactCaseIndexView(
            **self._envelope(state, verification), cases=entries
        )

    def case(self, case_id: str, *, repetition: int = 1) -> RunArtifactCaseView:
        state, verification = self._state()
        envelope = self._envelope(state, verification)
        if state == ArtifactViewAvailability.CORRUPTED:
            return RunArtifactCaseView(**envelope)
        return RunArtifactCaseView(
            **envelope,
            artifact_case=ArtifactV2Reader(self.artifact_root).case(
                case_id, repetition=repetition
            ),
        )

    def case_model(self, case_id: str, *, repetition: int = 1) -> RunArtifactCaseV2:
        state, _verification = self._state()
        if state != ArtifactViewAvailability.AVAILABLE:
            raise ValueError("corrupted Artifact 2.0 cannot provide a review subject")
        return ArtifactV2Reader(self.artifact_root).case(
            case_id, repetition=repetition
        )

    def case_models(self) -> tuple[RunArtifactCaseV2, ...]:
        state, _verification = self._state()
        if state != ArtifactViewAvailability.AVAILABLE:
            raise ValueError("corrupted Artifact 2.0 cannot provide cases")
        return ArtifactV2Reader(self.artifact_root).cases()

    def cases(self) -> RunArtifactCaseCollectionView:
        state, verification = self._state()
        envelope = self._envelope(state, verification)
        if state == ArtifactViewAvailability.CORRUPTED:
            return RunArtifactCaseCollectionView(**envelope)
        values = tuple(
            RunArtifactCaseView(**envelope, artifact_case=item)
            for item in ArtifactV2Reader(self.artifact_root).cases()
        )
        return RunArtifactCaseCollectionView(**envelope, cases=values)

    def comparison_summary(self) -> dict[str, Any]:
        """Adapt persisted aggregates to the comparison validator's read shape."""

        overview = self.overview()
        if overview.summary is None:
            return {
                "artifact_contract_version": "2.0",
                "availability": overview.availability.value,
                "metrics": {},
            }
        return {
            "artifact_contract_version": "2.0",
            "availability": overview.availability.value,
            "metrics": {
                metric.metric_id: {
                    "status": metric.status.value,
                    "value": metric.value,
                    "coverage": metric.observed_case_count / metric.case_count,
                    "descriptor_digests": list(metric.descriptor_digests),
                }
                for metric in overview.summary.metrics
            },
        }

    def _state(
        self,
    ) -> tuple[ArtifactViewAvailability, ArtifactVerificationView]:
        reader = ArtifactV2Reader(self.artifact_root)
        verification = reader.verify()
        invalid_models = list(verification.invalid_models)
        if verification.valid:
            manifest = reader.manifest()
            if manifest.run_id != self.run_id:
                invalid_models.append("run-record:run-id")
            if (
                self.expected_experiment_id is not None
                and manifest.experiment_id != self.expected_experiment_id
            ):
                invalid_models.append("run-record:experiment-id")
            if (
                self.expected_artifact_digest is not None
                and manifest.artifact_digest != self.expected_artifact_digest
            ):
                invalid_models.append("run-record:artifact-digest")
            benchmark = manifest.benchmark_identity
            if (
                self.expected_benchmark_release_id is not None
                and benchmark.dataset_release_id
                != self.expected_benchmark_release_id
            ):
                invalid_models.append("resolved-plan:benchmark-release-id")
            if (
                self.expected_benchmark_release_digest is not None
                and benchmark.dataset_release_digest
                != self.expected_benchmark_release_digest
            ):
                invalid_models.append("resolved-plan:benchmark-release-digest")
            if (
                self.expected_bundle_id is not None
                and benchmark.bundle_id != self.expected_bundle_id
            ):
                invalid_models.append("resolved-plan:runtime-bundle-id")
            if (
                self.expected_case_selection_id is not None
                and benchmark.case_selection_id != self.expected_case_selection_id
            ):
                invalid_models.append("resolved-plan:case-selection-id")
            if self.expected_plan is not None:
                invalid_models.extend(
                    artifact_plan_binding_errors(reader, self.expected_plan)
                )
        if invalid_models:
            verification = ArtifactV2Verification(
                valid=False,
                missing=verification.missing,
                unexpected=verification.unexpected,
                mismatched=verification.mismatched,
                invalid_models=tuple(sorted(set(invalid_models))),
            )
        view = ArtifactVerificationView.from_v2(verification)
        return (
            ArtifactViewAvailability.AVAILABLE
            if verification.valid
            else ArtifactViewAvailability.CORRUPTED,
            view,
        )

    def _envelope(
        self,
        state: ArtifactViewAvailability,
        verification: ArtifactVerificationView,
    ) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "availability": state,
            "reason": (
                None
                if state == ArtifactViewAvailability.AVAILABLE
                else CORRUPTED_REASON
            ),
            "verification": verification,
        }


__all__ = [
    "ARTIFACT_PRESENTATION_SCHEMA_VERSION",
    "ArtifactPresentationReader",
    "ArtifactVerificationView",
    "ArtifactViewAvailability",
    "MetricDescriptorBindingView",
    "RunArtifactCaseCollectionView",
    "RunArtifactCaseIndexView",
    "RunArtifactCaseView",
    "RunArtifactOverviewView",
    "RunCaseIndexEntryView",
    "RunRecordViewV2",
]
