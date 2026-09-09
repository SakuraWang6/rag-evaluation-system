from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from rag_eval.comparison import (
    ArtifactComparisonRunV2,
    validate_artifact_comparison_v2,
)
from rag_eval.contracts.research import ComparisonSpec
from rag_eval.contracts.run import ComparisonTier
from rag_eval.runs.plans import ResolvedRunPlanV2
from rag_eval.runs.records import RunRecordStateV2, RunRecordV2
from tests.rag_eval_platform.test_run_record_v2 import _record_plan_store


def _run(
    plan: ResolvedRunPlanV2,
    run_id: str,
    experiment_id: str,
) -> ArtifactComparisonRunV2:
    now = datetime(2026, 9, 9, tzinfo=UTC)
    return ArtifactComparisonRunV2(
        record=RunRecordV2(
            run_id=run_id,
            experiment_id=experiment_id,
            resolved_plan_path=f"resolved-run-plans/{experiment_id}.json",
            resolved_plan_digest="sha256:" + "a" * 64,
            state=RunRecordStateV2.COMPLETED,
            created_at=now,
            started_at=now,
            completed_at=now,
            artifact_path="artifact-v2/artifact.json",
            artifact_digest="sha256:" + ("b" if run_id == "run-1" else "c") * 64,
        ),
        plan=plan.model_copy(update={"experiment_id": experiment_id}),
    )


def _runs(tmp_path: Path) -> list[ArtifactComparisonRunV2]:
    store, reference = _record_plan_store(tmp_path)
    plan = store.get(reference)
    return [
        _run(plan, "run-1", "experiment-1"),
        _run(plan, "run-2", "experiment-2"),
    ]


def _summary(
    *,
    status: str = "observed",
    value: float | None = 1.0,
    descriptor: str = "sha256:shared",
) -> dict[str, object]:
    return {
        "artifact_contract_version": "2.0",
        "availability": "available",
        "metrics": {
            "ranked_evidence_coverage@5": {
                "status": status,
                "value": value,
                "coverage": 1.0 if status == "observed" else 0.0,
                "descriptor_digests": [descriptor],
            }
        },
    }


def test_artifact_v2_runs_compare_without_any_legacy_route_projection(
    tmp_path: Path,
) -> None:
    runs = _runs(tmp_path)
    decision = validate_artifact_comparison_v2(
        runs,
        ComparisonTier.TASK_COMPARABLE,
        summaries={run.run_id: _summary() for run in runs},
    )

    assert decision.compatible is True
    assert decision.reasons == ()
    assert decision.metric_decisions[0].comparable is True


def test_artifact_v2_comparison_requires_identical_metric_descriptors(
    tmp_path: Path,
) -> None:
    runs = _runs(tmp_path)
    decision = validate_artifact_comparison_v2(
        runs,
        ComparisonTier.TASK_COMPARABLE,
        summaries={
            "run-1": _summary(descriptor="sha256:first"),
            "run-2": _summary(descriptor="sha256:second"),
        },
    )

    metric = decision.metric_decisions[0]
    assert not metric.comparable
    assert "metric descriptor differs across Runs" in metric.reasons


def test_artifact_v2_comparison_never_turns_unavailable_into_zero(
    tmp_path: Path,
) -> None:
    runs = _runs(tmp_path)
    decision = validate_artifact_comparison_v2(
        runs,
        ComparisonTier.TASK_COMPARABLE,
        summaries={
            "run-1": _summary(),
            "run-2": _summary(status="unavailable", value=None),
        },
    )

    metric = decision.metric_decisions[0]
    assert not metric.comparable
    assert any("status is unavailable" in reason for reason in metric.reasons)


def test_strict_artifact_v2_comparison_uses_only_resolved_plan_controls(
    tmp_path: Path,
) -> None:
    runs = _runs(tmp_path)
    spec = ComparisonSpec(
        comparison_id="comparison-v2",
        experiment_ids=["experiment-1", "experiment-2"],
        tier="strict_controlled",
        controlled_factors=["query.final_context_k"],
        primary_metrics=["ranked_evidence_coverage@5"],
        model_lock_digest="sha256:" + "d" * 64,
        latency_protocol_digest="sha256:" + "e" * 64,
        analysis_contract_digest="sha256:" + "f" * 64,
    )
    decision = validate_artifact_comparison_v2(
        runs,
        ComparisonTier.STRICT_CONTROLLED,
        summaries={run.run_id: _summary() for run in runs},
        spec=spec,
    )

    assert decision.compatible is True
    assert decision.may_declare_winner is True


def test_corrupted_artifact_v2_is_not_comparable(tmp_path: Path) -> None:
    runs = _runs(tmp_path)
    corrupted = _summary()
    corrupted["availability"] = "corrupted"
    decision = validate_artifact_comparison_v2(
        runs,
        ComparisonTier.TASK_COMPARABLE,
        summaries={"run-1": _summary(), "run-2": corrupted},
    )

    assert decision.compatible is False
    assert any("not verified and available" in reason for reason in decision.reasons)
