from __future__ import annotations

import os
from pathlib import Path

import pytest
from rag_eval.contracts.adapter import DocumentInput, PrepareContext, RAGQuery
from rag_eval.worker.process import WorkerCommand, WorkerProcess


def lightrag_worker_command() -> tuple[str, str]:
    worker_python = os.environ.get("RAG_EVAL_LIGHTRAG_WORKER_PYTHON")
    if not worker_python or not Path(worker_python).is_file():
        pytest.skip("set RAG_EVAL_LIGHTRAG_WORKER_PYTHON to the dedicated LightRAG worker venv")
    monorepo = Path(__file__).resolve().parents[2]
    python_path = os.pathsep.join(
        [
            str(monorepo / "platform" / "src"),
            str(monorepo / "adapters" / "lightrag" / "src"),
            os.environ.get("PYTHONPATH", ""),
        ]
    )
    return worker_python, python_path


@pytest.mark.integration
def test_real_lightrag_worker_handshake_prepare_and_close(tmp_path: Path) -> None:
    worker_python, python_path = lightrag_worker_command()
    process = WorkerProcess(
        WorkerCommand(
            adapter_id="lightrag",
            adapter_factory="rag_eval_lightrag_adapter:create_worker_definition",
            python_executable=worker_python,
            environment={"PYTHONPATH": python_path},
            request_timeout_seconds=30,
        ),
        run_id="lightrag-worker-smoke",
        log_path=tmp_path / "worker.log",
    )
    try:
        client = process.start(handshake_timeout=20)
        handshake = client.handshake()
        assert handshake.adapter_id == "lightrag"
        prepared = client.prepare(
            PrepareContext(
                run_id="lightrag-worker-smoke",
                work_dir=str(tmp_path / "work"),
                source_dir=str(tmp_path / "source"),
                platform_version="0.1.0",
            ),
            {
                "profile": "legacy",
                "server_start_timeout_seconds": 20,
            },
        )
        assert prepared.capabilities == handshake.capabilities
        assert prepared.effective_config["profile"] == "legacy"
        assert client.health().ready
    finally:
        process.stop()


@pytest.mark.integration
def test_real_lightrag_worker_retrieval_and_e2e_share_one_contract(
    tmp_path: Path,
) -> None:
    worker_python, python_path = lightrag_worker_command()
    process = WorkerProcess(
        WorkerCommand(
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
        ),
        run_id="lightrag-worker-query-smoke",
        log_path=tmp_path / "worker.log",
    )
    try:
        client = process.start(handshake_timeout=20)
        client.prepare(
            PrepareContext(
                run_id="lightrag-worker-query-smoke",
                work_dir=str(tmp_path / "work"),
                source_dir=str(tmp_path / "source"),
                platform_version="0.1.0",
            ),
            {
                "profile": "legacy",
                "chunking": {
                    "chunk_token_size": 120,
                    "chunk_overlap_token_size": 20,
                },
                "retrieval_candidate_k": 2,
                "final_context_k": 1,
                "max_context_tokens": 2000,
                "server_start_timeout_seconds": 20,
            },
        )
        ingestion = client.ingest(
            [
                DocumentInput(
                    document_id="aurora",
                    content=(
                        "Project Aurora is owned by Lin Lan. "
                        "Stable marker AURORA_OWNER_LIN_LAN."
                    ),
                ),
                DocumentInput(
                    document_id="borealis",
                    content=(
                        "Project Borealis is owned by Mei Chen. "
                        "Stable marker BOREALIS_OWNER_MEI_CHEN."
                    ),
                ),
            ]
        )
        assert ingestion.ingested_documents == 2
        assert ingestion.index_fingerprint

        retrieval = client.query(
            RAGQuery(
                case_id="retrieval",
                question="Who owns Project Aurora?",
                generate_answer=False,
                retrieval_candidate_k=2,
                final_context_k=1,
            )
        )
        assert retrieval.answer is None
        assert retrieval.raw_retrieval is not None
        assert retrieval.ranked_retrieval is not None
        assert retrieval.final_context is not None
        assert retrieval.final_context
        assert retrieval.final_context[0].document_id == "aurora"

        e2e = client.query(
            RAGQuery(
                case_id="e2e",
                question="Who owns Project Aurora?",
                generate_answer=True,
                retrieval_candidate_k=2,
                final_context_k=1,
            )
        )
        assert isinstance(e2e.answer, str) and e2e.answer.strip()
        assert e2e.final_context is not None
        assert e2e.final_context[0].document_id == "aurora"
    finally:
        process.stop()
