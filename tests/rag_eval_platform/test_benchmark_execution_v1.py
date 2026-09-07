"""P0 execution helpers for segment-native benchmark runs."""

from __future__ import annotations

from rag_eval.contracts.adapter import (
    AdapterCapabilities,
    RAGResult,
    SegmentTraceItem,
    SegmentTraceSet,
    SegmentTraceStage,
    SegmentTraceStatus,
)
from rag_eval.contracts.benchmark import segment_mapping_receipt
from rag_eval.contracts.run import ExperimentSpec
from rag_eval.datasets.benchmark_contract import build_benchmark_dataset
from rag_eval.datasets.bundle import case_selection_id
from rag_eval.execution import (
    execute_benchmark_case,
    ingestion_rpc_timeout,
    select_benchmark_questions,
    validate_benchmark_ingestion_contract,
)
from rag_eval.worker.process import WorkerCommand

from tests.rag_eval_platform.test_benchmark_contract_v1 import _bundle


class _Client:
    def __init__(self, result: RAGResult) -> None:
        self.result = result

    def query(self, _query):
        return self.result


def _experiment(case_ids: list[str]) -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id="benchmark-p0-test",
        bundle_id="f" * 64,
        system_id="test-system",
        adapter_id="test-adapter",
        case_ids=case_ids,
        case_selection_id=case_selection_id(case_ids, policy="explicit", seed=0),
        query_config={"generate_answer": False},
        metric_config={"k_values": [1, 3, 5, 10]},
    )


def _result(dataset, case_id: str) -> RAGResult:
    gold = dataset.gold_by_case_id[case_id]
    segment_ids = tuple(clause[0] for clause in gold.evidence_paths[0])

    def stage(name: str) -> SegmentTraceStage:
        items = tuple(
            SegmentTraceItem(
                native_chunk_id=f"native-{index}",
                rank=index,
                source_segment_ids=(segment_id,),
                mapping_receipt_digest=segment_mapping_receipt(
                    dataset.manifest.contract_digest,
                    f"native-{index}",
                    (segment_id,),
                ),
            )
            for index, segment_id in enumerate(segment_ids, start=1)
        )
        return SegmentTraceStage(
            stage=name,  # type: ignore[arg-type]
            status=SegmentTraceStatus.OBSERVED,
            items=items,
            mapping_manifest_digest=dataset.manifest.contract_digest,
        )

    return RAGResult(
        raw_retrieval=[],
        ranked_retrieval=[],
        final_context=[],
        latency={},
        segment_traces=SegmentTraceSet(
            raw=stage("raw"), ranked=stage("ranked"), context=stage("context")
        ),
    )


def test_execute_benchmark_case_scores_segment_trace_not_legacy_provenance(tmp_path) -> None:
    dataset = build_benchmark_dataset(_bundle(tmp_path))
    case_id = "case-multi"
    question = select_benchmark_questions(dataset, _experiment([case_id]))[0]
    result = execute_benchmark_case(
        _Client(_result(dataset, case_id)),
        AdapterCapabilities(
            answer=True,
            raw_retrieval=True,
            ranked_retrieval=True,
            final_context=True,
            latency_breakdown=True,
            segment_traces=True,
            strict_segment_ranking=True,
        ),
        question,
        dataset,
        _experiment([case_id]),
        lambda: False,
        1,
        0,
    )

    assert result.status == "completed"
    assert result.gold_evidence_set is None
    assert result.segment_evaluation_trace is not None
    assert result.segment_evaluation_trace.raw.outcome.value == "complete"
    assert next(metric for metric in result.metrics if metric.metric_id == "segment_raw_recall@3").value == 1.0
    assert next(
        metric for metric in result.metrics if metric.metric_id == "answer_hallucination"
    ).status.value == "not_applicable"


def test_ingestion_contract_distinguishes_strict_and_answer_only_adapters(tmp_path) -> None:
    dataset = build_benchmark_dataset(_bundle(tmp_path))
    strict = {
        "benchmark_contract_schema_version": "rag-benchmark-contract/1",
        "benchmark_contract_digest": dataset.manifest.contract_digest,
        "benchmark_segment_mapping_status": "verified",
        "benchmark_segment_inputs": len(dataset.segments),
        "benchmark_segment_runtime_chunks": len(dataset.segments),
        "benchmark_segment_mapping_file_digest": "a" * 64,
    }
    validate_benchmark_ingestion_contract(
        strict, dataset, strict_segment_ranking=True
    )
    answer_only = {
        "benchmark_contract_schema_version": "rag-benchmark-contract/1",
        "benchmark_contract_digest": dataset.manifest.contract_digest,
        "benchmark_segment_mapping_status": "unsupported_stage",
        "benchmark_segment_inputs": len(dataset.segments),
    }
    validate_benchmark_ingestion_contract(
        answer_only, dataset, strict_segment_ranking=False
    )


def test_ingestion_rpc_timeout_does_not_undercut_adapter_budget() -> None:
    command = WorkerCommand(
        adapter_id="lightrag",
        adapter_factory="example:create",
        request_timeout_seconds=600,
    )

    assert ingestion_rpc_timeout(command, {}) == 600
    assert ingestion_rpc_timeout(command, {"ingestion_timeout_seconds": 120}) == 600
    assert ingestion_rpc_timeout(command, {"ingestion_timeout_seconds": 1800}) == 1830
    assert (
        ingestion_rpc_timeout(
            command,
            {
                "ingestion_timeout_seconds": 1800,
                "ingestion_run_timeout_seconds": 7200,
            },
        )
        == 7230
    )
