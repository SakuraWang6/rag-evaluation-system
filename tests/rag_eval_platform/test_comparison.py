from __future__ import annotations

from datetime import UTC, datetime

from rag_eval.comparison import validate_comparison
from rag_eval.contracts.adapter import AdapterCapabilities
from rag_eval.contracts.run import (
    ComparisonTier,
    ReproducibilityRecord,
    RunManifest,
    RunStatus,
)


def manifest(run_id: str, **updates) -> RunManifest:
    value = RunManifest(
        run_id=run_id,
        experiment_id="experiment",
        status=RunStatus.COMPLETED,
        bundle_id="bundle",
        case_selection_id="selection",
        platform_version="0.1.0",
        adapter_id="fake",
        adapter_version="0.1.0",
        system_id="system",
        system_version="1",
        declared_config={},
        effective_config={
            "query": {"final_context_k": 5},
            "adapter": {"llm_model": "controlled"},
        },
        scorer_id="scorer",
        scorer_version="1.0",
        scorer_digest="sha256:one",
        declared_capabilities=AdapterCapabilities(),
        observed_capabilities=AdapterCapabilities(),
        seed=0,
        repetitions=1,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        reproducibility=ReproducibilityRecord(
            platform_git_commit="abc",
            platform_dirty=False,
            dependency_lock_digest="1" * 64,
            environment_digest="2" * 64,
            model_digests={"llm": "sha256:model"},
            prompt_digests={"system": "sha256:prompt"},
            dependency_lock_artifact="reproducibility/dependency-lock.txt",
            environment_artifact="reproducibility/environment.json",
        ),
    )
    return value.model_copy(update=updates)


def test_task_and_strict_comparison_contracts() -> None:
    first = manifest("run-1")
    second = manifest("run-2")
    assert validate_comparison(
        [first, second], ComparisonTier.STRICT_CONTROLLED
    ).may_declare_winner

    different_model = second.model_copy(
        update={
            "effective_config": {
                "query": {"final_context_k": 5},
                "adapter": {"llm_model": "different"},
            }
        }
    )
    decision = validate_comparison(
        [first, different_model], ComparisonTier.STRICT_CONTROLLED
    )
    assert decision.compatible is False
    assert decision.may_declare_winner is False


def test_exploratory_never_declares_a_winner() -> None:
    first = manifest("run-1")
    second = manifest("run-2", bundle_id="other")
    decision = validate_comparison(
        [first, second], ComparisonTier.EXPLORATORY
    )
    assert decision.compatible is True
    assert decision.reasons
    assert decision.may_declare_winner is False


def test_strict_same_system_rejects_dependency_or_model_drift() -> None:
    first = manifest("run-1")
    second = manifest("run-2")
    assert second.reproducibility is not None
    drifted = second.model_copy(
        update={
            "reproducibility": second.reproducibility.model_copy(
                update={
                    "dependency_lock_digest": "3" * 64,
                    "model_digests": {"llm": "sha256:different"},
                }
            )
        }
    )

    decision = validate_comparison(
        [first, drifted], ComparisonTier.STRICT_CONTROLLED
    )

    assert not decision.compatible
    assert "controlled model digests differ" in decision.reasons
    assert "same-system dependency locks differ" in decision.reasons
