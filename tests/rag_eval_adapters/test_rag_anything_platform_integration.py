from __future__ import annotations

import os
from pathlib import Path

import pytest
from rag_eval.contracts.run import ExperimentSpec, MetricStatus, RunStatus
from rag_eval.datasets.bundle import DatasetBundleStore, case_selection_id
from rag_eval.execution import RunExecutor
from rag_eval.storage.runs import RunStore
from rag_eval.worker.process import WorkerCommand

from tests.rag_eval_adapters.bundle_fixture import write_bundle


@pytest.mark.integration
def test_platform_executes_rag_anything_in_independent_venv(tmp_path: Path) -> None:
    worker_python = os.environ.get("RAG_ANYTHING_WORKER_PYTHON")
    if not worker_python or not Path(worker_python).is_file():
        pytest.skip("set RAG_ANYTHING_WORKER_PYTHON to the dedicated worker venv")
    source = tmp_path / "bundle"
    source.mkdir()
    write_bundle(source)
    dataset_store = DatasetBundleStore(tmp_path / "platform" / "datasets")
    bundle = dataset_store.register(source)
    run_store = RunStore(tmp_path / "platform" / "runs")
    executor = RunExecutor(dataset_store, run_store)
    command = WorkerCommand(
        adapter_id="rag-anything",
        adapter_factory=(
            "rag_eval_rag_anything_adapter:create_worker_definition"
        ),
        python_executable=worker_python,
        request_timeout_seconds=240,
    )
    spec = ExperimentSpec(
        experiment_id="rag-anything-platform-e2e",
        bundle_id=bundle.bundle_id,
        system_id="rag-anything",
        adapter_id="rag-anything",
        adapter_config={
            "query_mode": "naive",
            "chunking": {
                "chunk_token_size": 120,
                "chunk_overlap_token_size": 20,
            },
            "model": {
                "binding": "ollama",
                "host": "http://127.0.0.1:11434",
                "llm_model": "qwen3:4b-instruct",
                "embedding_model": "bge-m3:latest",
                "embedding_dim": 1024,
                "embedding_max_tokens": 8192,
                "request_timeout_seconds": 180,
            },
            "top_k": 3,
            "chunk_top_k": 1,
            "max_context_tokens": 2000,
            "enable_image_processing": False,
            "enable_table_processing": False,
            "enable_equation_processing": False,
        },
        query_config={
            "generate_answer": True,
            "retrieval_candidate_k": 3,
            "final_context_k": 1,
            "max_context_tokens": 2000,
        },
        metric_config={"k_values": [1, 3]},
        case_selection_id=case_selection_id(["case-1"], policy="all", seed=0),
    )

    manifest = executor.execute(spec, command, run_id="rag-anything-platform-run")

    assert manifest.status == RunStatus.COMPLETED
    assert manifest.adapter_id == "rag-anything"
    assert manifest.system_version == "1.3.1"
    assert manifest.effective_config["adapter"]["runtime"][
        "lightrag_version"
    ].startswith("1.4.")
    assert manifest.reproducibility is not None
    assert manifest.reproducibility.model_digests
    assert manifest.reproducibility.prompt_digests
    assert run_store.verify_artifacts(manifest.run_id).valid
    case = run_store.cases(manifest.run_id)[0]
    assert case.status == "completed"
    assert case.rag_result is not None
    assert case.rag_result.raw_retrieval is None
    assert case.rag_result.ranked_retrieval is None
    assert case.rag_result.final_context is None
    metrics = {metric.metric_id: metric for metric in case.metrics}
    # A real model may give a score or a deliberately review-required typed
    # answer; execution validity and unavailable retrieval semantics remain
    # the integration contract.
    assert metrics["answer_accuracy"].status in {MetricStatus.OBSERVED, MetricStatus.NEEDS_REVIEW}
    assert metrics["raw_recall@1"].status == MetricStatus.UNAVAILABLE
    assert metrics["ranked_recall@1"].status == MetricStatus.UNAVAILABLE
    assert metrics["context_recall@1"].status == MetricStatus.UNAVAILABLE
    assert metrics["answer_groundedness"].status == MetricStatus.UNAVAILABLE
