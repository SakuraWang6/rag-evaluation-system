from __future__ import annotations

import pytest

from rag_eval.worker import main


def test_worker_rejects_non_loopback_host_without_container_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_EVAL_WORKER_TOKEN", "test-token")
    with pytest.raises(SystemExit, match="bind only"):
        main.main(
            [
                "--adapter-factory",
                "rag_eval.adapters.fake:create_worker_definition",
                "--run-id",
                "test",
                "--host",
                "0.0.0.0",
                "--port",
                "9000",
            ]
        )


def test_worker_allows_container_bind_only_with_explicit_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_EVAL_WORKER_TOKEN", "test-token")
    monkeypatch.setenv("RAG_EVAL_WORKER_ALLOW_CONTAINER_BIND", "1")
    with pytest.raises(ModuleNotFoundError, match="No module named"):
        main.main(
            [
                "--adapter-factory",
                "not_a_real_adapter:create_worker_definition",
                "--run-id",
                "test",
                "--host",
                "0.0.0.0",
                "--port",
                "9000",
            ]
        )
