"""Case-clustered paired analysis; seeds are repeated measurements, not cases."""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import fmean

from rag_eval.contracts.research import AnalysisContract


@dataclass(frozen=True, slots=True)
class ClusteredBootstrapResult:
    estimate: float
    lower: float
    upper: float
    n_cases: int
    matched_seeds_by_case: dict[str, tuple[int, ...]]
    case_deltas: dict[str, float]


def case_clustered_paired_bootstrap(
    legacy: Mapping[str, Mapping[int, float]],
    enhanced: Mapping[str, Mapping[int, float]],
    contract: AnalysisContract,
    *,
    strata: Mapping[str, str] | None = None,
    stratum_weights: Mapping[str, float] | None = None,
) -> ClusteredBootstrapResult:
    """Bootstrap independent cases while retaining all matched seed values.

    It is intentionally impossible to pass a flattened case×seed table.  The
    nested mapping makes the repeated-measurement relationship explicit.
    """

    deltas, matched = case_mean_deltas(legacy, enhanced)
    if not deltas:
        raise ValueError("no cases have a complete matched seed schedule")
    groups: dict[str, list[str]] = {}
    for case_id in sorted(deltas):
        groups.setdefault(strata.get(case_id, "__all__") if strata else "__all__", []).append(case_id)
    weights = normalized_weights(groups, stratum_weights)
    randomizer = random.Random(contract.analysis_seed)
    samples: list[float] = []
    for _ in range(contract.bootstrap_iterations):
        stratum_means: dict[str, float] = {}
        for name, case_ids in groups.items():
            sampled = [randomizer.choice(case_ids) for _ in case_ids]
            stratum_means[name] = fmean(deltas[case_id] for case_id in sampled)
        samples.append(sum(weights[name] * stratum_means[name] for name in groups))
    samples.sort()
    alpha = (1 - contract.confidence_level) / 2
    lower = percentile(samples, alpha)
    upper = percentile(samples, 1 - alpha)
    estimate = sum(weights[name] * fmean(deltas[case_id] for case_id in ids) for name, ids in groups.items())
    return ClusteredBootstrapResult(
        estimate=estimate,
        lower=lower,
        upper=upper,
        n_cases=len(deltas),
        matched_seeds_by_case=matched,
        case_deltas=deltas,
    )


def case_mean_deltas(
    legacy: Mapping[str, Mapping[int, float]], enhanced: Mapping[str, Mapping[int, float]]
) -> tuple[dict[str, float], dict[str, tuple[int, ...]]]:
    deltas: dict[str, float] = {}
    matched: dict[str, tuple[int, ...]] = {}
    if set(legacy) != set(enhanced):
        missing_from_legacy = sorted(set(enhanced).difference(legacy))
        missing_from_enhanced = sorted(set(legacy).difference(enhanced))
        raise ValueError(
            "formal run is operationally invalid: unmatched case IDs; "
            f"missing_from_legacy={missing_from_legacy}, "
            f"missing_from_enhanced={missing_from_enhanced}"
        )
    for case_id in sorted(legacy):
        legacy_seeds = legacy[case_id]
        enhanced_seeds = enhanced[case_id]
        if set(legacy_seeds) != set(enhanced_seeds) or not legacy_seeds:
            raise ValueError(
                f"case {case_id!r} lacks a complete matched seed schedule; "
                "the formal run is operationally invalid"
            )
        seeds = tuple(sorted(legacy_seeds))
        deltas[case_id] = fmean(enhanced_seeds[seed] for seed in seeds) - fmean(
            legacy_seeds[seed] for seed in seeds
        )
        matched[case_id] = seeds
    return deltas, matched


def normalized_weights(
    groups: Mapping[str, list[str]], weights: Mapping[str, float] | None
) -> dict[str, float]:
    if weights is None:
        total = sum(len(values) for values in groups.values())
        return {name: len(values) / total for name, values in groups.items()}
    unknown = set(weights).difference(groups)
    missing = set(groups).difference(weights)
    if unknown or missing:
        raise ValueError(f"stratum weights mismatch: unknown={sorted(unknown)}, missing={sorted(missing)}")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("stratum weights must sum to a positive value")
    return {name: value / total for name, value in weights.items()}


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    position = (len(values) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction
