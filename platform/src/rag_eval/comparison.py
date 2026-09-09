"""Fail-closed, per-metric comparison compatibility validation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from rag_eval.artifact_contract import artifact_digest
from rag_eval.contracts.research import ComparisonSpec
from rag_eval.contracts.run import ComparisonTier, RunManifest, RunStatus
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
    metric_decisions: tuple[MetricComparisonDecision, ...] = field(default_factory=tuple)


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
            requested, False, ("at least two runs are required",), False
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
                    run.plan.benchmark_release.runtime_bundle_id,
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
        plan_configs = [_v2_comparison_config(run.plan) for run in runs]
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
                    if baseline.get(path, _MISSING) == flattened.get(path, _MISSING):
                        continue
                    if any(
                        path == factor or path.startswith(f"{factor}.")
                        for factor in allowed
                    ):
                        continue
                    reasons.append(f"undeclared treatment/config drift: {path}")

    metric_decisions = _metric_decisions(runs, requested, summaries, spec, reasons)
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
    eligible = [item for item in metric_decisions if item.metric_id in primary]
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


def _v2_comparison_config(plan: ResolvedRunPlanV2) -> dict[str, Any]:
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


def validate_comparison(
    runs: list[RunManifest],
    requested: ComparisonTier,
    *,
    summaries: dict[str, dict[str, Any]] | None = None,
    spec: ComparisonSpec | None = None,
) -> ComparisonDecision:
    """Validate global and metric-local contracts separately.

    An unavailable retrieval trace for one system does not make answer accuracy
    unavailable for every system.  It does prevent a winner declaration for
    that retrieval metric.
    """

    if len(runs) < 2:
        return ComparisonDecision(requested, False, ("at least two runs are required",), False)
    reasons = _base_reasons(runs, summaries)
    if spec is not None:
        reasons.extend(_spec_reasons(runs, requested, spec))
    elif requested == ComparisonTier.STRICT_CONTROLLED:
        reasons.append("strict controlled comparison requires a preregistered ComparisonSpec")
    metric_decisions = _metric_decisions(runs, requested, summaries, spec, reasons)
    if requested == ComparisonTier.EXPLORATORY:
        return ComparisonDecision(
            requested, True, tuple(dict.fromkeys(reasons)), False, metric_decisions
        )
    compatible = not reasons
    primary = set(spec.primary_metrics) if spec is not None else set()
    eligible = [item for item in metric_decisions if item.metric_id in primary]
    may_declare_winner = bool(
        compatible
        and requested == ComparisonTier.STRICT_CONTROLLED
        and eligible
        and all(item.winner_eligible for item in eligible)
    )
    return ComparisonDecision(
        requested,
        compatible,
        tuple(dict.fromkeys(reasons)),
        may_declare_winner,
        metric_decisions,
    )


def _base_reasons(
    runs: list[RunManifest],
    summaries: dict[str, dict[str, Any]] | None,
) -> list[str]:
    reasons: list[str] = []
    for run in runs:
        if run.schema_version != 2 or run.producer != "rag_eval_platform":
            reasons.append(f"{run.run_id} is not a schema-v2 platform run")
        if run.status != RunStatus.COMPLETED:
            reasons.append(f"{run.run_id} is not a completed run")
        summary = summaries.get(run.run_id, {}) if summaries is not None else {}
        declares_artifact_v2 = summary.get("artifact_contract_version") == "2.0"
        artifact_v2 = (
            declares_artifact_v2
            and summary.get("availability") == "available"
        )
        if declares_artifact_v2 and not artifact_v2:
            reasons.append(f"{run.run_id} Artifact 2.0 is not verified and available")
        if not artifact_v2 and (
            run.diagnostic_only or run.execution_view == "native-docx"
        ):
            reasons.append(
                f"{run.run_id} uses native DOCX diagnostic execution and cannot declare a comparison winner"
            )
    for field_name in (
        "bundle_id",
        "case_selection_id",
        "repetitions",
        "scorer_id",
        "scorer_version",
        "scorer_digest",
        "metric_scorers",
    ):
        if len({serialized(getattr(run, field_name)) for run in runs}) > 1:
            reasons.append(f"task contract differs: {field_name}")
    return reasons


def _spec_reasons(
    runs: list[RunManifest], requested: ComparisonTier, spec: ComparisonSpec
) -> list[str]:
    reasons: list[str] = []
    if spec.tier != requested.value:
        reasons.append("ComparisonSpec tier does not match requested tier")
    if requested == ComparisonTier.STRICT_CONTROLLED:
        spec_digest = artifact_digest(spec)
        if any(
            run.declared_config.get("comparison_spec_digest") != spec_digest
            for run in runs
        ):
            reasons.append("run ComparisonSpec digest does not match the supplied spec")
    if set(spec.experiment_ids) != {run.experiment_id for run in runs}:
        reasons.append("ComparisonSpec experiment IDs do not match selected runs")
    for factor in spec.controlled_factors:
        values = [lookup_factor(run.effective_config, factor) for run in runs]
        if any(value is _MISSING for value in values):
            reasons.append(f"controlled factor is missing: {factor}")
        elif len({serialized(value) for value in values}) > 1:
            reasons.append(f"controlled factor differs: {factor}")
    if requested == ComparisonTier.STRICT_CONTROLLED:
        reasons.extend(_undeclared_treatment_reasons(runs, spec))
    if requested != ComparisonTier.STRICT_CONTROLLED:
        return reasons
    if any(run.reproducibility is None for run in runs):
        reasons.append("full reproducibility metadata is missing")
    for run in runs:
        if not run.model_artifacts:
            reasons.append(f"{run.run_id} is missing model artifact identities")
        elif any(not artifact.verified for artifact in run.model_artifacts.values()):
            reasons.append(f"{run.run_id} contains an unverified model artifact")
    # Only immutable artifact identities participate in equivalence.  A display
    # name, requested tag, resolver timestamp, or resolver implementation must
    # not turn identical weights into a false drift signal.
    if len({serialized(model_identity_map(run)) for run in runs}) > 1:
        reasons.append("controlled model artifact identities differ")
    if spec.model_lock_digest and any(
        run.declared_config.get("model_lock_digest") != spec.model_lock_digest
        for run in runs
    ):
        reasons.append("model lock digest differs from ComparisonSpec")
    if spec.latency_protocol_digest and any(
        run.latency_protocol_digest != spec.latency_protocol_digest for run in runs
    ):
        reasons.append("latency protocol digest differs from ComparisonSpec")
    if spec.analysis_contract_digest and any(
        run.declared_config.get("analysis_contract_digest") != spec.analysis_contract_digest
        for run in runs
    ):
        reasons.append("analysis contract digest differs from ComparisonSpec")
    if len({run.system_id for run in runs}) == 1:
        for field_name in ("adapter_version", "system_version", "platform_version"):
            if len({serialized(getattr(run, field_name)) for run in runs}) > 1:
                reasons.append(f"same-system replay differs: {field_name}")
        reproducibility = [run.reproducibility for run in runs if run.reproducibility]
        if len({record.dependency_lock_digest for record in reproducibility}) > 1:
            reasons.append("same-system dependency locks differ")
        if len({serialized(record.prompt_digests) for record in reproducibility}) > 1:
            reasons.append("same-system prompt digests differ")
        if len({serialized(record.source_identities) for record in reproducibility}) > 1:
            reasons.append("same-system source identities differ")
    return reasons


_MISSING = object()


def _undeclared_treatment_reasons(
    runs: list[RunManifest], spec: ComparisonSpec
) -> list[str]:
    """Reject strict config drift outside pre-registered treatment factors.

    ``effective_config`` proves that declared controls were applied.  This
    check works over the immutable declared experiment inputs, where dynamic
    diagnostics such as resolver timestamps cannot mask an unregistered
    chunk/query/parser/generation change.
    """

    allowed = tuple(spec.treatment_factors)
    baseline = flatten_config(runs[0].declared_config)
    reasons: list[str] = []
    for run in runs[1:]:
        candidate = flatten_config(run.declared_config)
        for path in sorted(set(baseline).union(candidate)):
            if baseline.get(path, _MISSING) == candidate.get(path, _MISSING):
                continue
            if any(path == factor or path.startswith(f"{factor}.") for factor in allowed):
                continue
            reasons.append(f"undeclared treatment/config drift: {path}")
    return reasons


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
    summaries: dict[str, dict[str, Any]] | None,
    spec: ComparisonSpec | None,
    global_reasons: list[str],
) -> tuple[MetricComparisonDecision, ...]:
    if summaries is None:
        return ()
    metric_ids = sorted(
        {
            metric_id
            for run in runs
            for metric_id in summaries.get(run.run_id, {}).get("metrics", {})
        }
    )
    required_coverage = spec.minimum_metric_coverage if spec else 1.0
    descriptors_required = any(
        summaries.get(run.run_id, {}).get("artifact_contract_version") == "2.0"
        for run in runs
    )
    decisions: list[MetricComparisonDecision] = []
    for metric_id in metric_ids:
        reasons: list[str] = []
        coverage: dict[str, float] = {}
        descriptor_digests: dict[str, tuple[str, ...]] = {}
        for run in runs:
            metric = summaries.get(run.run_id, {}).get("metrics", {}).get(metric_id)
            if not isinstance(metric, dict):
                coverage[run.run_id] = 0.0
                reasons.append(f"{run.run_id}: metric is absent")
                continue
            status = metric.get("status")
            value = metric.get("value")
            raw_coverage = metric.get("coverage", 0.0)
            coverage[run.run_id] = float(raw_coverage) if isinstance(raw_coverage, (int, float)) else 0.0
            raw_descriptors = metric.get("descriptor_digests")
            if isinstance(raw_descriptors, (list, tuple)) and all(
                isinstance(item, str) for item in raw_descriptors
            ):
                descriptor_digests[run.run_id] = tuple(sorted(set(raw_descriptors)))
            elif descriptors_required:
                descriptor_digests[run.run_id] = ()
                reasons.append(f"{run.run_id}: metric descriptor is absent")
            if status != "observed" or value is None:
                reasons.append(f"{run.run_id}: metric status is {status}")
            elif coverage[run.run_id] < required_coverage:
                reasons.append(
                    f"{run.run_id}: metric coverage {coverage[run.run_id]:.3f} is below {required_coverage:.3f}"
                )
        if descriptors_required and len(set(descriptor_digests.values())) > 1:
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


def controlled_config(config: dict[str, Any]) -> dict[str, Any]:
    """Compatibility shim; ComparisonSpec now owns control-factor selection."""

    return config


def serialized(value: Any) -> str:
    return repr(value)


def model_identity_map(run: RunManifest) -> dict[str, str | None]:
    return {name: artifact.identity for name, artifact in sorted(run.model_artifacts.items())}
