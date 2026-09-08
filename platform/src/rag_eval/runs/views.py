"""Persisted-only API read models for Run Artifact 2.0 and legacy archives.

This module is intentionally below the Platform API and beside Artifact 2.0.
It does not import an Adapter, provenance mapper, or scorer.  A legacy artifact
can expose its persisted execution facts, but missing v2 observations and
metrics remain explicitly unavailable instead of being reconstructed with the
currently installed evaluation code.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rag_eval.evaluation.unified.models import MetricDescriptor
from rag_eval.runs.artifacts import ArtifactV2Reader, ArtifactV2Verification
from rag_eval.runs.models import (
    ARTIFACT_V2_DIRECTORY,
    ArtifactAnswerJudgment,
    ArtifactAnswerStatus,
    ArtifactEvidenceJudgment,
    ArtifactEvidenceStatus,
    RunArtifactCaseV2,
    RunArtifactManifestV2,
    RunArtifactSummaryV2,
    descriptor_digest,
)

ARTIFACT_PRESENTATION_SCHEMA_VERSION = "1.0"
LEGACY_UNAVAILABLE_REASON = (
    "Artifact 2.0 observations, metric descriptors, and scores were not persisted "
    "for this Run; legacy execution facts are available without read-time rescoring."
)
CORRUPTED_REASON = (
    "Artifact 2.0 integrity validation failed; persisted result content is withheld "
    "from scoring and presentation."
)


class ArtifactPresentationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArtifactViewAvailability(StrEnum):
    AVAILABLE = "available"
    LEGACY_UNAVAILABLE = "legacy_unavailable"
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


class MetricDescriptorBindingView(ArtifactPresentationModel):
    metric_id: str = Field(min_length=1)
    descriptor_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    descriptor: MetricDescriptor


class RunArtifactViewEnvelope(ArtifactPresentationModel):
    schema_version: Literal["1.0"] = ARTIFACT_PRESENTATION_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    artifact_contract_version: Literal["2.0", "1.2"]
    availability: ArtifactViewAvailability
    reason: str | None = None
    verification: ArtifactVerificationView | None = None


class RunArtifactOverviewView(RunArtifactViewEnvelope):
    manifest: RunArtifactManifestV2 | None = None
    summary: RunArtifactSummaryV2 | None = None
    metric_descriptors: tuple[MetricDescriptorBindingView, ...] = ()


class RunCaseIndexEntryView(ArtifactPresentationModel):
    case_id: str = Field(min_length=1)
    repetition: int = Field(ge=1)
    seed: int | None = None
    status: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer_judgment: ArtifactAnswerJudgment
    evidence_judgment: ArtifactEvidenceJudgment
    core_metrics_available: bool = False
    failure_kind: str | None = None


class RunArtifactCaseIndexView(RunArtifactViewEnvelope):
    cases: tuple[RunCaseIndexEntryView, ...] = ()


class LegacyRunCaseView(ArtifactPresentationModel):
    case_id: str = Field(min_length=1)
    repetition: int = Field(ge=1)
    seed: int | None = None
    status: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer: str | None = None
    error: dict[str, Any] | None = None


class RunArtifactCaseView(RunArtifactViewEnvelope):
    artifact_case: RunArtifactCaseV2 | None = None
    legacy_case: LegacyRunCaseView | None = None


class RunArtifactCaseCollectionView(RunArtifactViewEnvelope):
    cases: tuple[RunArtifactCaseView, ...] = ()


class ArtifactPresentationReader:
    """Expose only verified, already-persisted Run result facts."""

    def __init__(self, run_directory: Path, *, run_id: str) -> None:
        self.run_directory = run_directory
        self.run_id = run_id

    @property
    def artifact_root(self) -> Path:
        return self.run_directory / ARTIFACT_V2_DIRECTORY

    @property
    def has_artifact_v2(self) -> bool:
        return self.artifact_root.exists()

    def overview(self) -> RunArtifactOverviewView:
        state, verification = self._state()
        if state != ArtifactViewAvailability.AVAILABLE:
            return RunArtifactOverviewView(
                **self._envelope(state, verification),
            )
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
        if state == ArtifactViewAvailability.LEGACY_UNAVAILABLE:
            entries = tuple(self._legacy_index_entry(item) for item in self._legacy_cases())
            return RunArtifactCaseIndexView(
                **self._envelope(state, verification), cases=entries
            )
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
        if state == ArtifactViewAvailability.AVAILABLE:
            return RunArtifactCaseView(
                **envelope,
                artifact_case=ArtifactV2Reader(self.artifact_root).case(
                    case_id, repetition=repetition
                ),
            )
        legacy = next(
            (
                item
                for item in self._legacy_cases()
                if item.case_id == case_id and item.repetition == repetition
            ),
            None,
        )
        if legacy is None:
            raise FileNotFoundError(case_id)
        return RunArtifactCaseView(**envelope, legacy_case=legacy)

    def cases(self) -> RunArtifactCaseCollectionView:
        state, verification = self._state()
        envelope = self._envelope(state, verification)
        if state == ArtifactViewAvailability.CORRUPTED:
            return RunArtifactCaseCollectionView(**envelope)
        if state == ArtifactViewAvailability.AVAILABLE:
            values = tuple(
                RunArtifactCaseView(**envelope, artifact_case=item)
                for item in ArtifactV2Reader(self.artifact_root).cases()
            )
        else:
            values = tuple(
                RunArtifactCaseView(**envelope, legacy_case=item)
                for item in self._legacy_cases()
            )
        return RunArtifactCaseCollectionView(
            **envelope, cases=values
        )

    def comparison_summary(self) -> dict[str, Any]:
        """Adapt persisted aggregates to the comparison validator's read shape."""

        overview = self.overview()
        if overview.summary is None:
            return {
                "artifact_contract_version": overview.artifact_contract_version,
                "availability": overview.availability.value,
                "metrics": {},
            }
        return {
            "artifact_contract_version": overview.artifact_contract_version,
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
    ) -> tuple[ArtifactViewAvailability, ArtifactVerificationView | None]:
        if not self.has_artifact_v2:
            return ArtifactViewAvailability.LEGACY_UNAVAILABLE, None
        verification = ArtifactVerificationView.from_v2(
            ArtifactV2Reader(self.artifact_root).verify()
        )
        return (
            ArtifactViewAvailability.AVAILABLE
            if verification.valid
            else ArtifactViewAvailability.CORRUPTED,
            verification,
        )

    def _envelope(
        self,
        state: ArtifactViewAvailability,
        verification: ArtifactVerificationView | None,
    ) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "artifact_contract_version": (
                "2.0" if self.has_artifact_v2 else "1.2"
            ),
            "availability": state,
            "reason": (
                None
                if state == ArtifactViewAvailability.AVAILABLE
                else CORRUPTED_REASON
                if state == ArtifactViewAvailability.CORRUPTED
                else LEGACY_UNAVAILABLE_REASON
            ),
            "verification": verification,
        }

    def _legacy_cases(self) -> tuple[LegacyRunCaseView, ...]:
        cases_directory = self.run_directory / "cases"
        if cases_directory.is_dir():
            payloads = tuple(
                self._read_object(path)
                for path in sorted(cases_directory.glob("*.json"))
            )
        else:
            execution = (
                self.run_directory
                / "private-evaluation"
                / "case-execution.jsonl"
            )
            if not execution.is_file():
                return ()
            payloads = tuple(self._read_jsonl(execution))
        return tuple(self._legacy_case(payload) for payload in payloads)

    @staticmethod
    def _legacy_case(payload: dict[str, Any]) -> LegacyRunCaseView:
        case_id = payload.get("case_id")
        question = payload.get("question")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("legacy case artifact has no case_id")
        if not isinstance(question, str) or not question:
            question = "[question unavailable]"
        repetition = payload.get("repetition")
        seed = payload.get("seed")
        status = payload.get("status")
        rag_result = payload.get("rag_result")
        answer = rag_result.get("answer") if isinstance(rag_result, dict) else None
        error = payload.get("error")
        return LegacyRunCaseView(
            case_id=case_id,
            repetition=repetition if isinstance(repetition, int) and repetition > 0 else 1,
            seed=seed if isinstance(seed, int) else None,
            status=status if isinstance(status, str) and status else "system_error",
            question=question,
            answer=answer if isinstance(answer, str) else None,
            error=error if isinstance(error, dict) else None,
        )

    @staticmethod
    def _legacy_index_entry(item: LegacyRunCaseView) -> RunCaseIndexEntryView:
        return RunCaseIndexEntryView(
            case_id=item.case_id,
            repetition=item.repetition,
            seed=item.seed,
            status=item.status,
            question=item.question,
            answer_judgment=ArtifactAnswerJudgment(
                status=ArtifactAnswerStatus.UNAVAILABLE,
                reason=LEGACY_UNAVAILABLE_REASON,
            ),
            evidence_judgment=ArtifactEvidenceJudgment(
                status=ArtifactEvidenceStatus.UNAVAILABLE,
                reason=LEGACY_UNAVAILABLE_REASON,
            ),
        )

    @staticmethod
    def _read_object(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TypeError(f"{path.name} is malformed")
        return value

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"{path.name}:{line_number} is malformed")
            values.append(value)
        return values


__all__ = [
    "ARTIFACT_PRESENTATION_SCHEMA_VERSION",
    "ArtifactPresentationReader",
    "ArtifactVerificationView",
    "ArtifactViewAvailability",
    "LegacyRunCaseView",
    "MetricDescriptorBindingView",
    "RunArtifactCaseCollectionView",
    "RunArtifactCaseIndexView",
    "RunArtifactCaseView",
    "RunArtifactOverviewView",
    "RunCaseIndexEntryView",
]
