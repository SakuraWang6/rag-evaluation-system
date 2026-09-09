"""Native v2 Run read authority.

This service exposes orchestration state from :class:`RunRecordV2`, resolves
immutable plan identity, and reads evaluation facts only from Artifact 2.0.
It intentionally has no archive discovery or legacy projection fallback.
"""

from __future__ import annotations

from rag_eval.report import artifact_v2_markdown_report
from rag_eval.run_presentations import RunPresentationStore
from rag_eval.runs.artifacts import ArtifactV2Reader
from rag_eval.runs.models import ARTIFACT_V2_DIRECTORY, RunArtifactCaseV2
from rag_eval.runs.plans import (
    ResolvedRunPlanReferenceV2,
    ResolvedRunPlanStore,
    ResolvedRunPlanV2,
)
from rag_eval.runs.records import (
    ARTIFACT_V2_REFERENCE,
    RunRecordStateV2,
    RunRecordStoreV2,
    RunRecordV2,
)
from rag_eval.runs.views import (
    ArtifactPresentationReader,
    RunArtifactCaseCollectionView,
    RunArtifactCaseIndexView,
    RunArtifactCaseView,
    RunArtifactOverviewView,
    RunRecordViewV2,
)


class RunArtifactHistory:
    """Join RunRecord/Plan identity without creating a second result source."""

    def __init__(
        self,
        records: RunRecordStoreV2,
        plans: ResolvedRunPlanStore,
        *,
        presentations: RunPresentationStore | None = None,
    ) -> None:
        self.records = records
        self.plans = plans
        self.presentations = presentations

    def list(self) -> list[RunRecordV2]:
        return self.records.list()

    def get(self, run_id: str) -> RunRecordV2:
        return self.records.get(run_id)

    def plan(self, run_id: str) -> ResolvedRunPlanV2:
        record = self.get(run_id)
        plan = self.plans.get(
            ResolvedRunPlanReferenceV2(
                path=record.resolved_plan_path,
                digest=record.resolved_plan_digest,
            )
        )
        if plan.experiment_id != record.experiment_id:
            raise ValueError("RunRecordV2 references another Experiment's plan")
        return plan

    def list_views(self) -> list[RunRecordViewV2]:
        return [self.run_view(item.run_id) for item in self.list()]

    def run_view(self, run_id: str) -> RunRecordViewV2:
        record = self.get(run_id)
        plan = self.plan(run_id)
        display_name = ""
        source = "generated"
        if self.presentations is not None:
            presentation = self.presentations.get(run_id)
            if presentation.latest is not None:
                display_name = presentation.latest.display_name
                source = "override"
        if not display_name:
            display_name = (
                f"{plan.system.system_id} · "
                f"{record.created_at.strftime('%Y-%m-%d %H:%M UTC')} · "
                f"{record.run_id[:8]}"
            )
        return RunRecordViewV2(
            **record.model_dump(mode="python"),
            benchmark_release_id=plan.benchmark_release.release_id,
            system_id=plan.system.system_id,
            adapter_id=plan.system.adapter_id,
            worker_profile_id=plan.system.worker_profile_id,
            worker_profile_version=plan.system.worker_profile_version,
            display_name=display_name,
            display_name_source=source,
        )

    def artifact_presentation(self, run_id: str) -> ArtifactPresentationReader:
        record = self.get(run_id)
        if (
            record.state != RunRecordStateV2.COMPLETED
            or record.artifact_path != ARTIFACT_V2_REFERENCE
            or record.artifact_digest is None
        ):
            raise FileNotFoundError(
                f"Run {run_id} has no completed Artifact 2.0 result"
            )
        plan = self.plan(run_id)
        return ArtifactPresentationReader(
            self.records.root / record.run_id,
            run_id=record.run_id,
            expected_experiment_id=record.experiment_id,
            expected_artifact_digest=record.artifact_digest,
            expected_benchmark_release_id=plan.benchmark_release.release_id,
            expected_benchmark_release_digest=plan.benchmark_release.release_digest,
            expected_bundle_id=plan.benchmark_release.runtime_bundle_id,
            expected_case_selection_id=plan.case_selection_id,
            expected_plan=plan,
        )

    def artifact_reader(self, run_id: str) -> ArtifactV2Reader:
        presentation = self.artifact_presentation(run_id)
        overview = presentation.overview()
        if overview.availability != "available":
            raise ValueError(overview.reason or "Artifact 2.0 is corrupted")
        return ArtifactV2Reader(
            self.records.root / run_id / ARTIFACT_V2_DIRECTORY
        )

    def artifact_overview(self, run_id: str) -> RunArtifactOverviewView:
        return self.artifact_presentation(run_id).overview()

    def artifact_case_index(self, run_id: str) -> RunArtifactCaseIndexView:
        return self.artifact_presentation(run_id).case_index()

    def artifact_case(
        self, run_id: str, case_id: str, *, repetition: int = 1
    ) -> RunArtifactCaseView:
        return self.artifact_presentation(run_id).case(
            case_id, repetition=repetition
        )

    def artifact_case_model(
        self, run_id: str, case_id: str, *, repetition: int = 1
    ) -> RunArtifactCaseV2:
        return self.artifact_presentation(run_id).case_model(
            case_id, repetition=repetition
        )

    def artifact_case_models(self, run_id: str) -> list[RunArtifactCaseV2]:
        return list(self.artifact_presentation(run_id).case_models())

    def artifact_cases(self, run_id: str) -> RunArtifactCaseCollectionView:
        return self.artifact_presentation(run_id).cases()

    def artifact_comparison_summary(self, run_id: str) -> dict[str, object]:
        return self.artifact_presentation(run_id).comparison_summary()

    def report(self, run_id: str) -> str:
        return artifact_v2_markdown_report(self.artifact_reader(run_id))


__all__ = ["RunArtifactHistory"]
