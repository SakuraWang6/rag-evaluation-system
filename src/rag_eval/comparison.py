"""Tiered comparison compatibility validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag_eval.contracts.run import ComparisonTier, RunManifest, RunStatus


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
        if run.status != RunStatus.COMPLETED:
            reasons.append(f"{run.run_id} is not a completed run")
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
        reproducibility = [run.reproducibility for run in runs]
        if any(record is None for record in reproducibility):
            reasons.append("full reproducibility metadata is missing")
        else:
            model_digests = {
                serialized(record.model_digests)
                for record in reproducibility
                if record is not None
            }
            if len(model_digests) > 1:
                reasons.append("controlled model digests differ")
            same_system = len({run.system_id for run in runs}) == 1
            if same_system:
                replay_fields = (
                    "adapter_version",
                    "system_version",
                    "platform_version",
                )
                for field in replay_fields:
                    if len({serialized(getattr(run, field)) for run in runs}) > 1:
                        reasons.append(f"same-system replay differs: {field}")
                locks = {
                    record.dependency_lock_digest
                    for record in reproducibility
                    if record is not None
                }
                prompts = {
                    serialized(record.prompt_digests)
                    for record in reproducibility
                    if record is not None
                }
                if len(locks) > 1:
                    reasons.append("same-system dependency locks differ")
                if len(prompts) > 1:
                    reasons.append("same-system prompt digests differ")
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
