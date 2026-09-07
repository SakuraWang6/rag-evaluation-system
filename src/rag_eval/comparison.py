"""Fail-closed, per-metric comparison compatibility validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag_eval.artifact_contract import artifact_digest
from rag_eval.contracts.research import ComparisonSpec
from rag_eval.contracts.run import ComparisonTier, RunManifest, RunStatus


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
    reasons = _base_reasons(runs)
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


def _base_reasons(runs: list[RunManifest]) -> list[str]:
    reasons: list[str] = []
    for run in runs:
        if run.schema_version != 2 or run.producer != "rag_eval_platform":
            reasons.append(f"{run.run_id} is not a schema-v2 platform run")
        if run.status != RunStatus.COMPLETED:
            reasons.append(f"{run.run_id} is not a completed run")
        if run.diagnostic_only or run.execution_view == "native-docx":
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
    runs: list[RunManifest],
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
    decisions: list[MetricComparisonDecision] = []
    for metric_id in metric_ids:
        reasons: list[str] = []
        coverage: dict[str, float] = {}
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
            if status != "observed" or value is None:
                reasons.append(f"{run.run_id}: metric status is {status}")
            elif coverage[run.run_id] < required_coverage:
                reasons.append(
                    f"{run.run_id}: metric coverage {coverage[run.run_id]:.3f} is below {required_coverage:.3f}"
                )
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
