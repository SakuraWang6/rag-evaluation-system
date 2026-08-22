"""Tiered comparison compatibility validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag_eval.contracts.run import ComparisonTier, RunManifest


@dataclass(frozen=True, slots=True)
class ComparisonDecision:
    tier: ComparisonTier
    compatible: bool
    reasons: tuple[str, ...]
    may_declare_winner: bool


def validate_comparison(
    runs: list[RunManifest], requested: ComparisonTier
) -> ComparisonDecision:
    if len(runs) < 2:
        return ComparisonDecision(requested, False, ("at least two runs are required",), False)
    reasons: list[str] = []
    for run in runs:
        if run.schema_version != 2 or run.producer != "rag_eval_platform":
            reasons.append(f"{run.run_id} is not a schema-v2 platform run")
    task_fields = (
        "bundle_id",
        "case_selection_id",
        "scorer_id",
        "scorer_version",
        "scorer_digest",
        "repetitions",
    )
    for field in task_fields:
        values = {serialized(getattr(run, field)) for run in runs}
        if len(values) > 1:
            reasons.append(f"task contract differs: {field}")
    if requested == ComparisonTier.STRICT_CONTROLLED:
        controlled = [controlled_config(run.effective_config) for run in runs]
        if any(value != controlled[0] for value in controlled[1:]):
            reasons.append("controlled model/query/generation configuration differs")
    if requested == ComparisonTier.EXPLORATORY:
        return ComparisonDecision(requested, True, tuple(reasons), False)
    return ComparisonDecision(requested, not reasons, tuple(reasons), not reasons)


def controlled_config(config: dict[str, Any]) -> dict[str, Any]:
    selected_keys = {
        "embedding",
        "embedding_model",
        "llm",
        "llm_model",
        "generation",
        "generation_options",
        "retrieval_candidate_k",
        "final_context_k",
        "max_context_tokens",
        "top_k",
        "chunk_top_k",
    }

    def select(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: select(item)
                for key, item in sorted(value.items())
                if key in selected_keys or isinstance(item, dict)
            }
        if isinstance(value, list):
            return [select(item) for item in value]
        return value

    return select(config)


def serialized(value: Any) -> str:
    return repr(value)
