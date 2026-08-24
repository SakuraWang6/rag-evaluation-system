from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_eval.artifact_contract import artifact_digest
from rag_eval.contracts.adapter import (
    AdapterCapabilities,
    DocumentInput,
    PreparedSystem,
    RAGEvidenceItem,
    RAGResult,
)
from rag_eval.contracts.dataset import (
    GoldAnswer,
    GoldAnswerKind,
    GoldEvidence,
    GoldEvidenceSet,
    ObjectLocator,
)
from rag_eval.contracts.research import (
    AnalysisContract,
    ComparisonSpec,
    LatencyProtocol,
    ModelArtifactIdentity,
    ModelLock,
)
from rag_eval.contracts.run import ExperimentSpec, MetricResult, MetricStatus
from rag_eval.contracts.schema import PUBLIC_MODELS
from rag_eval.execution import (
    run_latency_warmup,
    validate_latency_runtime,
    validate_prepared,
)


def test_none_and_empty_retrieval_round_trip_have_distinct_meanings() -> None:
    unavailable = RAGResult(raw_retrieval=None)
    observed_empty = RAGResult(raw_retrieval=[])

    unavailable_round_trip = RAGResult.model_validate_json(
        unavailable.model_dump_json()
    )
    empty_round_trip = RAGResult.model_validate_json(
        observed_empty.model_dump_json()
    )

    assert unavailable_round_trip.raw_retrieval is None
    assert empty_round_trip.raw_retrieval == []


def test_evidence_groups_are_non_empty_and_reference_known_ids() -> None:
    evidence = GoldEvidence(
        evidence_id="e-1",
        document_id="doc-1",
        locator=ObjectLocator(object_type="fact", object_id="FACT-1"),
        canonical_value="42",
    )
    valid = GoldEvidenceSet(
        gold_evidence_set_id="set-1",
        evidence=[evidence],
        required_groups=[["e-1"]],
    )
    assert valid.required_groups == [["e-1"]]

    with pytest.raises(ValidationError, match="unknown evidence"):
        GoldEvidenceSet(
            gold_evidence_set_id="set-1",
            evidence=[evidence],
            required_groups=[["missing"]],
        )


def test_evidence_cannot_inflate_multiple_required_groups() -> None:
    evidence = GoldEvidence(
        evidence_id="e-1",
        document_id="doc-1",
        locator=ObjectLocator(object_type="fact", object_id="FACT-1"),
        canonical_value="42",
    )
    with pytest.raises(ValidationError, match="only one required group"):
        GoldEvidenceSet(
            gold_evidence_set_id="set-1",
            evidence=[evidence],
            required_groups=[["e-1"], ["e-1"]],
        )


def test_gold_evidence_rejects_blank_witnesses() -> None:
    with pytest.raises(ValidationError, match="requires canonical_value"):
        GoldEvidence(
            evidence_id="e-1",
            document_id="doc-1",
            locator=ObjectLocator(object_type="fact", object_id="FACT-1"),
            canonical_value=" ",
            quote_anchor="\t",
        )


def test_non_abstain_answer_requires_canonical_value() -> None:
    with pytest.raises(ValidationError, match="canonical"):
        GoldAnswer(gold_answer_id="a-1", kind=GoldAnswerKind.TEXT)


def test_metric_status_never_conflates_unavailable_with_zero() -> None:
    unavailable = MetricResult(
        metric_id="raw_recall@5",
        status=MetricStatus.UNAVAILABLE,
        scorer_id="retrieval-groups",
        scorer_version="1.0",
        scorer_digest="sha256:test",
        reason="raw retrieval is not observable",
    )
    zero = MetricResult(
        metric_id="raw_recall@5",
        status=MetricStatus.OBSERVED,
        value=0.0,
        numerator=0,
        denominator=1,
        scorer_id="retrieval-groups",
        scorer_version="1.0",
        scorer_digest="sha256:test",
    )
    assert unavailable.value is None
    assert zero.value == 0.0


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


def test_evidence_item_requires_positive_rank() -> None:
    with pytest.raises(ValidationError):
        RAGEvidenceItem(item_id="x", rank=0, content="")


def test_contract_does_not_define_hallucination_metric() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src"
    for path in source_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert 'metric_id="hallucination_rate"' not in text


def test_formal_experiment_requires_verified_immutable_model_identity() -> None:
    base = {
        "experiment_id": "formal",
        "bundle_id": "bundle",
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
        primary_metrics=["context_recall@5"],
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
        primary_metrics=["context_recall@5"],
        model_lock_digest=artifact_digest(ModelLock(models={"llm": artifact})),
        latency_protocol_digest=artifact_digest(latency_protocol),
        analysis_contract_digest=artifact_digest(analysis_contract),
    )
    experiment = ExperimentSpec(
        experiment_id="formal",
        bundle_id="bundle",
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
    prepared = PreparedSystem(
        effective_config={}, capabilities=AdapterCapabilities(answer=True), system_version="1"
    )
    with pytest.raises(ValueError, match="lacks model artifact"):
        validate_prepared(prepared, experiment, None)


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

        def query(self, request):
            self.requests.append(request)
            return RAGResult(
                raw_retrieval=[],
                ranked_retrieval=[],
                final_context=[],
                latency={"native_query_latency": 0.0},
            )

    client = WarmupClient()
    experiment = ExperimentSpec(
        experiment_id="latency",
        bundle_id="bundle",
        system_id="system",
        adapter_id="adapter",
        case_selection_id="selection",
        latency_protocol=protocol,
    )
    run_latency_warmup(
        client,
        AdapterCapabilities(
            answer=True,
            raw_retrieval=True,
            ranked_retrieval=True,
            final_context=True,
            latency_breakdown=True,
        ),
        experiment,
    )
    assert len(client.requests) == 1
    assert client.requests[0].generate_answer is False


def test_binary_document_uses_safe_source_only_reference() -> None:
    document = DocumentInput(
        document_id="pdf-1",
        source_path="source-00000.pdf",
        mime_type="application/pdf",
    )
    assert document.content is None
    with pytest.raises(ValidationError, match="safe relative"):
        DocumentInput(
            document_id="pdf-1",
            source_path="../gold_answers.jsonl",
            mime_type="application/pdf",
        )
