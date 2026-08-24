from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from rag_eval.contracts.adapter import PrepareContext
from rag_eval_lightrag_adapter.adapter import (
    CAPABILITIES,
    LightRAGAdapter,
    build_server_environment,
    ingestion_identity,
    normalize_ollama_digest,
    resolve_config,
    safe_runtime_identity,
    safe_source_name,
)


def test_ollama_bare_digest_is_normalized_for_formal_model_lock() -> None:
    bare = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"

    assert normalize_ollama_digest(bare) == f"sha256:{bare}"
    assert normalize_ollama_digest(f"sha256:{bare}") == f"sha256:{bare}"
    assert normalize_ollama_digest("not-a-digest") is None


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


def test_capabilities_do_not_claim_prompt_or_object_provenance() -> None:
    assert CAPABILITIES.raw_retrieval
    assert CAPABILITIES.ranked_retrieval
    assert CAPABILITIES.final_context
    assert not CAPABILITIES.prompt_trace
    assert not CAPABILITIES.object_provenance


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
