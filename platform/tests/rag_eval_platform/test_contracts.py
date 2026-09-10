from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_eval.artifact_contract import artifact_digest
from rag_eval.contracts.benchmark import (
    BenchmarkAnswerKindV2,
    BenchmarkAnswerV2,
    BenchmarkGoldV2,
    BenchmarkMsesClauseV2,
    BenchmarkMsesPathV2,
)
from rag_eval.contracts.research import (
    AnalysisContract,
    ComparisonSpec,
    LatencyProtocol,
    ModelArtifactIdentity,
    ModelLock,
)
from rag_eval.contracts.run import ExperimentSpec
from rag_eval.contracts.schema import PUBLIC_MODELS
from rag_eval.execution import (
    run_latency_warmup,
    validate_latency_runtime,
    validate_prepared_v2,
)
from tests.rag_eval_platform.test_run_artifact_v2 import (
    _observed_fixture,
    _prepared_fixture,
)
from tests.rag_eval_platform.test_unified_evaluation_v2 import _gold

EXAMPLES_ROOT = Path(__file__).resolve().parents[2] / "examples"


def test_evidence_groups_are_non_empty_and_reference_known_ids() -> None:
    valid = _gold(("e-1",))
    assert valid.mses_paths[0].clauses[0].alternatives == ("e-1",)

    with pytest.raises(ValidationError, match="unknown evidence"):
        BenchmarkGoldV2.model_validate(
            valid.model_dump(mode="json")
            | {
                "mses_paths": [
                    {
                        "path_id": "path-1",
                        "clauses": [
                            {"clause_id": "clause-1", "alternatives": ["missing"]}
                        ],
                    }
                ]
            }
        )


def test_mses_rejects_duplicate_clause_identity() -> None:
    with pytest.raises(ValidationError, match="clause IDs"):
        BenchmarkMsesPathV2(
            path_id="path-1",
            clauses=(
                BenchmarkMsesClauseV2(
                    clause_id="clause-1", alternatives=("e-1",)
                ),
                BenchmarkMsesClauseV2(
                    clause_id="clause-1", alternatives=("e-2",)
                ),
            ),
        )


def test_gold_evidence_rejects_blank_witnesses() -> None:
    payload = _gold(("e-1",)).model_dump(mode="json")
    payload["evidence"][0]["canonical_value"] = ""
    with pytest.raises(ValidationError, match="at least 1 character"):
        BenchmarkGoldV2.model_validate(payload)


def test_non_abstain_answer_requires_canonical_value() -> None:
    with pytest.raises(ValidationError, match="canonical"):
        BenchmarkAnswerV2(kind=BenchmarkAnswerKindV2.TEXT)


def test_all_public_contracts_emit_json_schema() -> None:
    for name, model in PUBLIC_MODELS.items():
        schema = model.model_json_schema()
        assert schema["title"]
        json.dumps(schema)
        assert name


def test_platform_source_has_no_lightrag_or_raganything_imports() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src"
    forbidden = ("lightrag", "raganything", "rag_anything")
    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert all(not name.startswith(forbidden) for name in names), path


def test_contract_does_not_define_hallucination_metric() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src"
    for path in source_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert 'metric_id="hallucination_rate"' not in text


def test_formal_experiment_requires_verified_immutable_model_identity() -> None:
    base = {
        "experiment_id": "formal",
        "dataset_release_id": "release",
        "system_id": "system",
        "adapter_id": "adapter",
        "case_selection_id": "selection",
        "formal": True,
        "model_lock_digest": "sha256:" + "d" * 64,
        "comparison_spec_digest": "sha256:" + "a" * 64,
        "analysis_contract_digest": "sha256:" + "b" * 64,
        "latency_protocol_digest": "sha256:" + "c" * 64,
    }
    with pytest.raises(ValidationError, match="model_artifacts"):
        ExperimentSpec(**base)
    artifact = ModelArtifactIdentity(
        display_name="model",
        requested_ref="model:latest",
        resolved_digest="sha256:" + "b" * 64,
        resolver="test",
        resolved_at="2026-08-24T00:00:00Z",
        verified=True,
    )
    with pytest.raises(ValidationError, match="model_lock_digest"):
        ExperimentSpec(
            **{**base, "model_lock_digest": "sha256:" + "e" * 64},
            model_artifacts={"llm": artifact},
        )
    analysis_contract = AnalysisContract(analysis_seed=7)
    latency_protocol = LatencyProtocol()
    comparison_spec = ComparisonSpec(
        comparison_id="formal-comparison",
        experiment_ids=["formal", "other"],
        tier="strict_controlled",
        controlled_factors=["adapter.profile"],
        primary_metrics=["ranked_complete_evidence_recall@5"],
        model_lock_digest=artifact_digest(ModelLock(models={"llm": artifact})),
        latency_protocol_digest=artifact_digest(latency_protocol),
        analysis_contract_digest=artifact_digest(analysis_contract),
    )
    assert ExperimentSpec(
        **{
            **base,
            "model_lock_digest": artifact_digest(ModelLock(models={"llm": artifact})),
            "analysis_contract": analysis_contract,
            "analysis_contract_digest": artifact_digest(analysis_contract),
            "latency_protocol": latency_protocol,
            "latency_protocol_digest": artifact_digest(latency_protocol),
            "comparison_spec": comparison_spec,
            "comparison_spec_digest": artifact_digest(comparison_spec),
            "model_artifacts": {"llm": artifact},
        }
    ).formal


def test_formal_prepare_fails_before_ingestion_when_model_identity_is_missing() -> None:
    artifact = ModelArtifactIdentity(
        display_name="model",
        requested_ref="model:latest",
        resolved_digest="sha256:" + "c" * 64,
        resolver="test",
        resolved_at="2026-08-24T00:00:00Z",
        verified=True,
    )
    analysis_contract = AnalysisContract(analysis_seed=7)
    latency_protocol = LatencyProtocol()
    comparison_spec = ComparisonSpec(
        comparison_id="formal-comparison",
        experiment_ids=["formal", "other"],
        tier="strict_controlled",
        controlled_factors=["adapter.profile"],
        primary_metrics=["ranked_complete_evidence_recall@5"],
        model_lock_digest=artifact_digest(ModelLock(models={"llm": artifact})),
        latency_protocol_digest=artifact_digest(latency_protocol),
        analysis_contract_digest=artifact_digest(analysis_contract),
    )
    experiment = ExperimentSpec(
        experiment_id="formal",
        dataset_release_id="release",
        system_id="system",
        adapter_id="adapter",
        case_selection_id="selection",
        formal=True,
        model_lock_digest=artifact_digest(ModelLock(models={"llm": artifact})),
        model_artifacts={"llm": artifact},
        comparison_spec=comparison_spec,
        comparison_spec_digest=artifact_digest(comparison_spec),
        analysis_contract=analysis_contract,
        analysis_contract_digest=artifact_digest(analysis_contract),
        latency_protocol=latency_protocol,
        latency_protocol_digest=artifact_digest(latency_protocol),
    )
    prepared = _prepared_fixture(_observed_fixture()[3]).model_copy(
        update={"effective_config": {}}
    )
    with pytest.raises(ValueError, match="lacks model artifact"):
        validate_prepared_v2(prepared, experiment, None)


def test_latency_protocol_requires_observed_cache_policy_and_warms_once() -> None:
    protocol = LatencyProtocol()
    with pytest.raises(TypeError, match="cache_policy"):
        validate_latency_runtime({}, protocol)
    with pytest.raises(ValueError, match="differs"):
        validate_latency_runtime(
            {"cache_policy": {"answer": True, "query": False, "llm": False}},
            protocol,
        )
    validate_latency_runtime(
        {"cache_policy": {"answer": False, "query": False, "llm": False}},
        protocol,
    )

    class WarmupClient:
        def __init__(self) -> None:
            self.requests = []

        def query(self, prepared, request):
            assert prepared == prepared_system
            self.requests.append(request)
            return _observed_fixture(request.case_id)[3]

    client = WarmupClient()
    prepared_system = _prepared_fixture(_observed_fixture()[3])
    experiment = ExperimentSpec(
        experiment_id="latency",
        dataset_release_id="release",
        system_id="system",
        adapter_id="adapter",
        case_selection_id="selection",
        query_config={
            "retrieval_candidate_k": 5,
            "final_context_k": 1,
            "max_context_tokens": 4096,
            "generation_options": {},
        },
        latency_protocol=protocol,
    )
    run_latency_warmup(
        client,
        prepared_system,
        experiment,
    )
    assert len(client.requests) == 1
    assert client.requests[0].generate_answer is False


def test_checked_in_research_examples_match_current_contracts() -> None:
    examples = {
        "comparison-spec.strict.example.json": ComparisonSpec,
        "latency-protocol.v1.json": LatencyProtocol,
        "model-lock.example.json": ModelLock,
    }
    for filename, model in examples.items():
        model.model_validate_json((EXAMPLES_ROOT / filename).read_text(encoding="utf-8"))

    assert not (EXAMPLES_ROOT / "query-request.json").exists()
    assert not (EXAMPLES_ROOT / "worker-handshake.json").exists()
