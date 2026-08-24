from __future__ import annotations

from datetime import UTC, datetime

from rag_eval.artifact_contract import artifact_digest
from rag_eval.comparison import validate_comparison
from rag_eval.contracts.adapter import AdapterCapabilities
from rag_eval.contracts.research import (
    AnalysisContract,
    ComparisonSpec,
    LatencyProtocol,
    ModelArtifactIdentity,
    ModelLock,
)
from rag_eval.contracts.run import (
    ComparisonTier,
    ReproducibilityRecord,
    RunManifest,
    RunStatus,
)

MODEL_ARTIFACT = ModelArtifactIdentity(
    display_name="controlled",
    requested_ref="controlled:latest",
    resolved_digest="sha256:" + "a" * 64,
    resolver="test",
    resolved_at=datetime(2026, 8, 24, tzinfo=UTC),
    verified=True,
)
MODEL_LOCK_DIGEST = artifact_digest(ModelLock(models={"llm": MODEL_ARTIFACT}))
ANALYSIS_CONTRACT_DIGEST = artifact_digest(AnalysisContract(analysis_seed=7))
LATENCY_PROTOCOL_DIGEST = artifact_digest(LatencyProtocol())


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
        declared_config={
            "model_lock_digest": MODEL_LOCK_DIGEST,
            "comparison_spec_digest": artifact_digest(spec()),
            "analysis_contract_digest": ANALYSIS_CONTRACT_DIGEST,
            "latency_protocol_digest": LATENCY_PROTOCOL_DIGEST,
        },
        effective_config={
            "query": {"final_context_k": 5},
            "adapter": {"llm_model": "controlled"},
        },
        scorer_id="scorer",
        scorer_version="1.0",
        scorer_digest="sha256:one",
        model_artifacts={
            "llm": MODEL_ARTIFACT
        },
        latency_protocol_digest=LATENCY_PROTOCOL_DIGEST,
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


def spec() -> ComparisonSpec:
    return ComparisonSpec(
        comparison_id="comparison",
        experiment_ids=["experiment", "experiment-enhanced"],
        tier="strict_controlled",
        controlled_factors=["query.final_context_k", "adapter.llm_model"],
        primary_metrics=["answer_accuracy"],
        model_lock_digest=MODEL_LOCK_DIGEST,
        latency_protocol_digest=LATENCY_PROTOCOL_DIGEST,
        analysis_contract_digest=ANALYSIS_CONTRACT_DIGEST,
    )


def summaries() -> dict[str, dict]:
    return {
        "run-1": {"metrics": {"answer_accuracy": {"status": "observed", "value": 1.0, "coverage": 1.0}}},
        "run-2": {"metrics": {"answer_accuracy": {"status": "observed", "value": 1.0, "coverage": 1.0}}},
    }


def test_task_and_strict_comparison_contracts() -> None:
    first = manifest("run-1")
    second = manifest("run-2", experiment_id="experiment-enhanced")
    assert validate_comparison(
        [first, second], ComparisonTier.STRICT_CONTROLLED, spec=spec(), summaries=summaries()
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
        [first, different_model], ComparisonTier.STRICT_CONTROLLED, spec=spec()
    )
    assert decision.compatible is False
    assert decision.may_declare_winner is False


def test_exploratory_never_declares_a_winner() -> None:
    first = manifest("run-1")
    second = manifest("run-2", bundle_id="other", experiment_id="experiment-enhanced")
    decision = validate_comparison(
        [first, second], ComparisonTier.EXPLORATORY
    )
    assert decision.compatible is True
    assert decision.reasons
    assert decision.may_declare_winner is False


def test_strict_same_system_rejects_dependency_or_model_drift() -> None:
    first = manifest("run-1")
    second = manifest("run-2", experiment_id="experiment-enhanced")
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
        [first, drifted], ComparisonTier.STRICT_CONTROLLED, spec=spec()
    )

    assert not decision.compatible
    assert "same-system dependency locks differ" in decision.reasons


def test_per_metric_compatibility_does_not_turn_unavailable_into_zero() -> None:
    first = manifest("run-1")
    second = manifest("run-2", experiment_id="experiment-enhanced")
    result = validate_comparison(
        [first, second],
        ComparisonTier.STRICT_CONTROLLED,
        spec=spec(),
        summaries={
            "run-1": {
                "metrics": {
                    "answer_accuracy": {"status": "observed", "value": 1.0, "coverage": 1.0},
                    "raw_recall@5": {"status": "observed", "value": 1.0, "coverage": 1.0},
                }
            },
            "run-2": {
                "metrics": {
                    "answer_accuracy": {"status": "observed", "value": 1.0, "coverage": 1.0},
                    "raw_recall@5": {"status": "unavailable", "value": None, "coverage": 0.0},
                }
            },
        },
    )
    decisions = {decision.metric_id: decision for decision in result.metric_decisions}
    assert decisions["answer_accuracy"].comparable
    assert not decisions["raw_recall@5"].comparable
    assert "metric status is unavailable" in decisions["raw_recall@5"].reasons[0]
    assert decisions["answer_accuracy"].winner_eligible
    assert not decisions["raw_recall@5"].winner_eligible


def test_strict_comparison_rejects_unregistered_treatment_drift() -> None:
    first = manifest("run-1")
    second = manifest(
        "run-2",
        experiment_id="experiment-enhanced",
        declared_config={
            **first.declared_config,
            "adapter": {"unregistered_parser_mode": "changed"},
        },
    )

    decision = validate_comparison(
        [first, second], ComparisonTier.STRICT_CONTROLLED, spec=spec()
    )

    assert not decision.compatible
    assert "undeclared treatment/config drift: adapter.unregistered_parser_mode" in decision.reasons


def test_comparison_rejects_metric_scorer_drift() -> None:
    first = manifest("run-1", metric_scorers={"gold_evidence": {"scorer_digest": "one"}})
    second = manifest(
        "run-2",
        experiment_id="experiment-enhanced",
        metric_scorers={"gold_evidence": {"scorer_digest": "two"}},
    )

    decision = validate_comparison([first, second], ComparisonTier.TASK_COMPARABLE)

    assert not decision.compatible
    assert "task contract differs: metric_scorers" in decision.reasons
