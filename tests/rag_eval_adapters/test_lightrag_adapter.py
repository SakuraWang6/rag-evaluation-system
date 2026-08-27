from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from rag_eval.contracts.adapter import PrepareContext
from rag_eval_lightrag_adapter.adapter import (
    CAPABILITIES,
    LightRAGAdapter,
    build_server_environment,
    exact_ollama_model_digest,
    exception_diagnostic,
    ingestion_identity,
    normalize_ollama_digest,
    redact_runtime_endpoints_in_logs,
    resolve_config,
    safe_runtime_identity,
    safe_source_name,
)


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"track_id": "track-1"}


class CapturingClient:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def post(self, path: str, **kwargs):
        self.requests.append({"path": path, **kwargs})
        return FakeResponse()


def test_ollama_bare_digest_is_normalized_for_formal_model_lock() -> None:
    bare = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"

    assert normalize_ollama_digest(bare) == f"sha256:{bare}"
    assert normalize_ollama_digest(f"sha256:{bare}") == f"sha256:{bare}"
    assert normalize_ollama_digest("not-a-digest") is None


def test_message_less_transport_error_is_never_reported_as_empty() -> None:
    class ReadTimeout(Exception):
        pass

    assert exception_diagnostic(ReadTimeout()) == "ReadTimeout: <no message>"


def test_ollama_resolver_requires_an_exact_requested_tag() -> None:
    rows = [
        {"name": "qwen3:8b", "digest": "eight"},
        {"name": "qwen3:4b-instruct", "digest": "four"},
    ]

    assert exact_ollama_model_digest(rows, "qwen3:4b-instruct") == "four"
    assert exact_ollama_model_digest(rows, "qwen3") is None


def test_legacy_profile_preserves_original_defaults(tmp_path) -> None:
    config = resolve_config({})
    environment = build_server_environment(config, tmp_path)

    assert config.profile == "legacy"
    assert config.ranking_strategy == "none"
    assert config.exact_id_types == []
    assert environment["LIGHTRAG_EXACT_ID_TYPES"] == ""
    assert environment["LIGHTRAG_RANKING_STRATEGY"] == "none"
    assert environment["LIGHTRAG_TABLE_PRECEDING_CONTEXT"] == "0"
    assert environment["ENTITY_EXTRACTION_INSTRUCTION_PROFILE"] == "legacy"
    assert environment["LIGHTRAG_KV_STORAGE"] == "JsonKVStorage"
    assert environment["LIGHTRAG_VECTOR_STORAGE"] == "NanoVectorDBStorage"
    assert environment["RERANK_BINDING"] == "null"
    assert environment["OLLAMA_LLM_NUM_CTX"] == "32768"
    assert environment["QUERY_OLLAMA_LLM_NUM_CTX"] == "32768"


def test_structured_profile_is_explicit_and_effective(tmp_path) -> None:
    config = resolve_config({"profile": "structured"})
    environment = build_server_environment(config, tmp_path)

    assert config.ranking_strategy == "structured"
    assert config.exact_id_types == ["FACT", "EQ", "REF"]
    assert environment["LIGHTRAG_TABLE_PRECEDING_CONTEXT"] == "1"
    assert environment["ENTITY_EXTRACTION_INSTRUCTION_PROFILE"] == "structured_fidelity"


def test_explicit_values_override_profile_defaults() -> None:
    config = resolve_config(
        {
            "profile": "structured",
            "ranking_strategy": "none",
            "exact_id_types": [],
            "table_preceding_context": False,
        }
    )
    assert config.ranking_strategy == "none"
    assert config.exact_id_types == []
    assert config.table_preceding_context is False


def test_capabilities_claim_object_provenance_but_not_prompt_trace() -> None:
    assert CAPABILITIES.raw_retrieval
    assert CAPABILITIES.ranked_retrieval
    assert CAPABILITIES.final_context
    assert not CAPABILITIES.prompt_trace
    assert CAPABILITIES.object_provenance


def test_source_name_is_safe_and_deterministic() -> None:
    first = safe_source_name(3, "../../gold.json")
    assert first == safe_source_name(3, "../../gold.json")
    assert "/" not in first
    assert first.endswith(".txt")


def test_index_identity_changes_with_chunk_or_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = ingestion_identity(resolve_config({}))
    chunked = ingestion_identity(
        resolve_config(
            {
                "chunking": {
                    "chunk_token_size": 600,
                    "chunk_overlap_token_size": 50,
                }
            }
        )
    )
    monkeypatch.setenv("EMBEDDING_MODEL", "different-embedding")
    embedded = ingestion_identity(resolve_config({}))

    assert baseline != chunked
    assert baseline != embedded


def test_server_environment_ignores_unregistered_experimental_shell_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("LIGHTRAG_EXACT_ID_TYPES", "TBL,FIG")
    monkeypatch.setenv("LIGHTRAG_TABLE_VIEW", "1")
    monkeypatch.setenv("LIGHTRAG_RANKING_STRATEGY", "structured")

    environment = build_server_environment(resolve_config({}), tmp_path)

    assert environment["LIGHTRAG_EXACT_ID_TYPES"] == ""
    assert environment["LIGHTRAG_TABLE_VIEW"] == "0"
    assert environment["LIGHTRAG_RANKING_STRATEGY"] == "none"
    assert environment["ENABLE_LLM_CACHE"] == "0"


def test_rerank_requires_an_explicit_model_and_never_uses_shell_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("RERANK_MODEL", "shell-controlled-model")

    with pytest.raises(ValueError, match="rerank_model"):
        resolve_config({"enable_rerank": True})

    environment = build_server_environment(
        resolve_config({"enable_rerank": True, "rerank_model": "explicit-model"}),
        tmp_path,
    )
    assert environment["RERANK_MODEL"] == "explicit-model"


def test_runtime_identity_preserves_the_resolved_ollama_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama.internal:11434")
    environment = build_server_environment(resolve_config({}), tmp_path)

    assert safe_runtime_identity(environment)["ollama_host"] == "http://ollama.internal:11434"


def test_runtime_endpoint_is_redacted_from_persisted_server_log(tmp_path) -> None:
    endpoint = "http://host.docker.internal:11434"
    log = tmp_path / "lightrag-server.log"
    log.write_text(f"Connected to {endpoint}\\n", encoding="utf-8")
    secondary_log = tmp_path / "lightrag.log"
    secondary_log.write_text(f"Runtime host: {endpoint}\\n", encoding="utf-8")

    redact_runtime_endpoints_in_logs(tmp_path, [endpoint])

    text = log.read_text(encoding="utf-8")
    assert endpoint not in text
    assert "[redacted endpoint sha256:" in text
    assert endpoint not in secondary_log.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_prepare_rejects_nonempty_workdir(tmp_path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / "stale-index.json").write_text("{}")
    adapter = LightRAGAdapter()
    adapter._start_server = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="stale index"):
        await adapter.prepare(
            PrepareContext(
                run_id="run-1",
                work_dir=str(work_dir),
                source_dir=str(tmp_path / "source"),
                platform_version="0.1.0",
            ),
            {},
        )
    adapter._start_server.assert_not_awaited()


@pytest.mark.asyncio
async def test_naive_document_upload_skips_unneeded_kg_extraction() -> None:
    adapter = LightRAGAdapter()
    adapter._config = resolve_config({})
    adapter._server = Mock()
    adapter._server.poll.return_value = None
    client = CapturingClient()
    adapter._client = client  # type: ignore[assignment]

    fixture = Path(__file__).parents[1] / "fixtures" / "canonical_naive_minimal.md"
    result = await adapter._post_document(
        "synthetic-source.txt", fixture.read_bytes(), "text/markdown"
    )

    assert result == {"track_id": "track-1"}
    assert client.requests[0]["data"] == {"process_options": "!"}
