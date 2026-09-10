"""Fail-closed Artifact 2.0 metric comparison validation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from rag_eval.contracts.research import ComparisonSpec
from rag_eval.contracts.run import ComparisonTier
from rag_eval.runs.plans import ResolvedRunPlanV2
from rag_eval.runs.records import RunRecordStateV2, RunRecordV2


@dataclass(frozen=True, slots=True)
class MetricComparisonDecision:
    metric_id: str
    comparable: bool
    reasons: tuple[str, ...]
    coverage_by_run: dict[str, float]
    winner_eligible: bool


@dataclass(frozen=True, slots=True)
class ComparisonDecision:
    tier: ComparisonTier
    compatible: bool
    reasons: tuple[str, ...]
    may_declare_winner: bool
    metric_decisions: tuple[MetricComparisonDecision, ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True, slots=True)
class ArtifactComparisonRunV2:
    """The non-evaluation inputs needed to compare two Artifact 2.0 Runs."""

    record: RunRecordV2
    plan: ResolvedRunPlanV2

    @property
    def run_id(self) -> str:
        return self.record.run_id


class _RunIdentity(Protocol):
    @property
    def run_id(self) -> str: ...


def validate_artifact_comparison_v2(
    runs: list[ArtifactComparisonRunV2],
    requested: ComparisonTier,
    *,
    summaries: dict[str, dict[str, Any]],
    spec: ComparisonSpec | None = None,
) -> ComparisonDecision:
    """Compare only immutable plans and persisted Artifact 2.0 summaries."""

    if len(runs) < 2:
        return ComparisonDecision(
            requested,
            False,
            ("at least two runs are required",),
            False,
        )
    reasons: list[str] = []
    for run in runs:
        if run.record.state != RunRecordStateV2.COMPLETED:
            reasons.append(f"{run.run_id} is not a completed RunRecordV2")
        summary = summaries.get(run.run_id, {})
        if (
            summary.get("artifact_contract_version") != "2.0"
            or summary.get("availability") != "available"
        ):
            reasons.append(
                f"{run.run_id} Artifact 2.0 is not verified and available"
            )
    for label, values in (
        (
            "Benchmark Release",
            {
                (
                    run.plan.benchmark_release.release_id,
                    run.plan.benchmark_release.release_digest,
                    run.plan.benchmark_release.benchmark_snapshot_digest,
                )
                for run in runs
            },
        ),
        ("case selection", {run.plan.case_selection_id for run in runs}),
        ("selected cases", {run.plan.case_ids for run in runs}),
        ("repetitions", {run.plan.repetitions for run in runs}),
        ("seed", {run.plan.seed for run in runs}),
    ):
        if len(values) > 1:
            reasons.append(f"task contract differs: {label}")

    if spec is None:
        if requested == ComparisonTier.STRICT_CONTROLLED:
            reasons.append(
                "strict controlled comparison requires a preregistered ComparisonSpec"
            )
    else:
        if spec.tier != requested.value:
            reasons.append("ComparisonSpec tier does not match requested tier")
        if set(spec.experiment_ids) != {
            run.record.experiment_id for run in runs
        }:
            reasons.append(
                "ComparisonSpec experiment IDs do not match selected runs"
            )
        plan_configs = [_comparison_config(run.plan) for run in runs]
        for factor in spec.controlled_factors:
            values = [lookup_factor(config, factor) for config in plan_configs]
            if any(value is _MISSING for value in values):
                reasons.append(f"controlled factor is missing: {factor}")
            elif len({serialized(value) for value in values}) > 1:
                reasons.append(f"controlled factor differs: {factor}")
        if requested == ComparisonTier.STRICT_CONTROLLED:
            baseline = flatten_config(plan_configs[0])
            allowed = tuple(spec.treatment_factors)
            for candidate in plan_configs[1:]:
                flattened = flatten_config(candidate)
                for path in sorted(set(baseline).union(flattened)):
                    if baseline.get(path, _MISSING) == flattened.get(
                        path, _MISSING
                    ):
                        continue
                    if any(
                        path == factor or path.startswith(f"{factor}.")
                        for factor in allowed
                    ):
                        continue
                    reasons.append(f"undeclared treatment/config drift: {path}")

    metric_decisions = _metric_decisions(
        runs,
        requested,
        summaries,
        spec,
        reasons,
    )
    if requested == ComparisonTier.EXPLORATORY:
        return ComparisonDecision(
            requested,
            True,
            tuple(dict.fromkeys(reasons)),
            False,
            metric_decisions,
        )
    compatible = not reasons
    primary = set(spec.primary_metrics) if spec is not None else set()
    eligible = [
        item for item in metric_decisions if item.metric_id in primary
    ]
    return ComparisonDecision(
        requested,
        compatible,
        tuple(dict.fromkeys(reasons)),
        bool(
            compatible
            and requested == ComparisonTier.STRICT_CONTROLLED
            and eligible
            and all(item.winner_eligible for item in eligible)
        ),
        metric_decisions,
    )


def _comparison_config(plan: ResolvedRunPlanV2) -> dict[str, Any]:
    """Expose only frozen plan fields to ComparisonSpec factor paths."""

    return {
        "benchmark": plan.benchmark_release.model_dump(mode="json"),
        "document": plan.original_document.model_dump(mode="json"),
        "system": plan.system.model_dump(mode="json"),
        "adapter": {"configuration_digest": plan.adapter_config_digest},
        "query": plan.query_config.model_dump(mode="json"),
        "metrics": plan.metric_config.model_dump(mode="json"),
        "evaluation": plan.evaluation_profile.model_dump(mode="json"),
        "resources": plan.resource_limits.model_dump(mode="json"),
        "case_ids": list(plan.case_ids),
        "case_selection_id": plan.case_selection_id,
        "seed": plan.seed,
        "repetitions": plan.repetitions,
    }


_MISSING = object()


def flatten_config(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        flattened: dict[str, Any] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten_config(child, child_prefix))
        return flattened or {prefix: {}}
    if isinstance(value, list):
        flattened = {}
        for index, child in enumerate(value):
            child_prefix = f"{prefix}.{index}" if prefix else str(index)
            flattened.update(flatten_config(child, child_prefix))
        return flattened or {prefix: []}
    return {prefix: value}


def lookup_factor(config: dict[str, Any], path: str) -> Any:
    current: Any = config
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _metric_decisions(
    runs: Sequence[_RunIdentity],
    requested: ComparisonTier,
    summaries: dict[str, dict[str, Any]],
    spec: ComparisonSpec | None,
    global_reasons: list[str],
) -> tuple[MetricComparisonDecision, ...]:
    metric_ids = sorted(
        {
            metric_id
            for run in runs
            for metric_id in summaries.get(run.run_id, {}).get("metrics", {})
        }
    )
    required_coverage = spec.minimum_metric_coverage if spec else 1.0
    decisions: list[MetricComparisonDecision] = []
    for metric_id in metric_ids:
        reasons: list[str] = []
        coverage: dict[str, float] = {}
        descriptor_digests: dict[str, tuple[str, ...]] = {}
        for run in runs:
            metric = summaries.get(run.run_id, {}).get("metrics", {}).get(
                metric_id
            )
            if not isinstance(metric, dict):
                coverage[run.run_id] = 0.0
                reasons.append(f"{run.run_id}: metric is absent")
                continue
            status = metric.get("status")
            value = metric.get("value")
            raw_coverage = metric.get("coverage", 0.0)
            coverage[run.run_id] = (
                float(raw_coverage)
                if isinstance(raw_coverage, (int, float))
                else 0.0
            )
            raw_descriptors = metric.get("descriptor_digests")
            if isinstance(raw_descriptors, (list, tuple)) and all(
                isinstance(item, str) for item in raw_descriptors
            ):
                descriptor_digests[run.run_id] = tuple(
                    sorted(set(raw_descriptors))
                )
            else:
                descriptor_digests[run.run_id] = ()
                reasons.append(f"{run.run_id}: metric descriptor is absent")
            if status != "observed" or value is None:
                reasons.append(f"{run.run_id}: metric status is {status}")
            elif coverage[run.run_id] < required_coverage:
                reasons.append(
                    f"{run.run_id}: metric coverage "
                    f"{coverage[run.run_id]:.3f} is below "
                    f"{required_coverage:.3f}"
                )
        if len(set(descriptor_digests.values())) > 1:
            reasons.append("metric descriptor differs across Runs")
        comparable = not reasons and not global_reasons
        decisions.append(
            MetricComparisonDecision(
                metric_id=metric_id,
                comparable=comparable,
                reasons=tuple(dict.fromkeys(reasons)),
                coverage_by_run=coverage,
                winner_eligible=(
                    comparable
                    and requested == ComparisonTier.STRICT_CONTROLLED
                    and spec is not None
                    and metric_id in spec.primary_metrics
                ),
            )
        )
    return tuple(decisions)


def serialized(value: Any) -> str:
    return repr(value)


__all__ = [
    "ArtifactComparisonRunV2",
    "ComparisonDecision",
    "MetricComparisonDecision",
    "flatten_config",
    "lookup_factor",
    "validate_artifact_comparison_v2",
]
