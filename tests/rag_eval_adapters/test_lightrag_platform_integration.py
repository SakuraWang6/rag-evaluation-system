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
def test_platform_executes_lightrag_e2e_without_importing_core(tmp_path: Path) -> None:
    worker_python = os.environ.get("RAG_EVAL_LIGHTRAG_WORKER_PYTHON")
    if not worker_python or not Path(worker_python).is_file():
        pytest.skip("set RAG_EVAL_LIGHTRAG_WORKER_PYTHON to the dedicated LightRAG worker venv")
    monorepo = Path(__file__).resolve().parents[2]
    source = tmp_path / "bundle"
    source.mkdir()
    write_bundle(source)
    dataset_store = DatasetBundleStore(tmp_path / "platform" / "datasets")
    bundle = dataset_store.register(source)
    run_store = RunStore(tmp_path / "platform" / "runs")
    executor = RunExecutor(dataset_store, run_store)
    python_path = os.pathsep.join(
        [
            str(monorepo / "platform" / "src"),
            str(monorepo / "adapters" / "lightrag" / "src"),
            os.environ.get("PYTHONPATH", ""),
        ]
    )
    command = WorkerCommand(
        adapter_id="lightrag",
        adapter_factory="rag_eval_lightrag_adapter:create_worker_definition",
        python_executable=worker_python,
        environment={
            "PYTHONPATH": python_path,
            "LLM_BINDING": "ollama",
            "LLM_MODEL": "qwen3:4b-instruct",
            "EMBEDDING_BINDING": "ollama",
            "EMBEDDING_MODEL": "bge-m3:latest",
        },
        request_timeout_seconds=180,
    )
    spec = ExperimentSpec(
        experiment_id="lightrag-platform-e2e",
        bundle_id=bundle.bundle_id,
        system_id="lightrag",
        adapter_id="lightrag",
        adapter_config={
            "profile": "legacy",
            "chunking": {
                "chunk_token_size": 120,
                "chunk_overlap_token_size": 20,
            },
            "retrieval_candidate_k": 3,
            "final_context_k": 1,
            "max_context_tokens": 2000,
            "server_start_timeout_seconds": 20,
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

    manifest = executor.execute(spec, command, run_id="lightrag-platform-run")

    assert manifest.status == RunStatus.COMPLETED
    assert manifest.schema_version == 2
    assert manifest.producer == "rag_eval_platform"
    assert manifest.effective_config["adapter"]["profile"] == "legacy"
    assert manifest.index_fingerprint
    assert manifest.reproducibility is not None
    assert manifest.reproducibility.model_digests
    assert manifest.reproducibility.prompt_digests
    assert run_store.verify_artifacts(manifest.run_id).valid
    case = run_store.cases(manifest.run_id)[0]
    assert case.status == "completed"
    assert case.rag_result is not None
    assert case.rag_result.raw_retrieval is not None
    assert case.rag_result.ranked_retrieval is not None
    assert case.rag_result.final_context is not None
    metrics = {metric.metric_id: metric for metric in case.metrics}
    assert metrics["raw_recall@1"].status == MetricStatus.OBSERVED
    assert metrics["ranked_recall@1"].status == MetricStatus.OBSERVED
    assert metrics["context_recall@1"].value == 1.0
    # This is a real-model integration test.  Retrieval evidence is
    # deterministic here, but typed numeric-answer assessment may correctly
    # require review when the model emits additional numeric text.
    assert metrics["answer_accuracy"].status in {MetricStatus.OBSERVED, MetricStatus.NEEDS_REVIEW}
    assert metrics["answer_groundedness"].status in {MetricStatus.OBSERVED, MetricStatus.NEEDS_REVIEW}
    source_files = sorted(
        path.name for path in (run_store.root / manifest.run_id / "source").iterdir()
    )
    assert len(source_files) == 1
    assert source_files[0].startswith("source-00000-")
    assert source_files[0].endswith(".txt")
