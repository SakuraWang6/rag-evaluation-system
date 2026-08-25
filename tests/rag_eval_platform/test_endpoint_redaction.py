from __future__ import annotations

from rag_eval.execution import redact_runtime_endpoints


def test_resolved_runtime_endpoints_are_redacted_from_persisted_effective_config() -> None:
    value = redact_runtime_endpoints(
        {
            "adapter": {
                "runtime": {
                    "ollama_host": "http://private-host:11434",
                    "host": "http://another-private-host:11434",
                    "llm_model": "qwen3:4b-instruct",
                }
            }
        }
    )
    runtime = value["adapter"]["runtime"]  # type: ignore[index]
    assert runtime["ollama_host"]["redacted"] is True  # type: ignore[index]
    assert runtime["ollama_host"]["endpoint_identity_digest"].startswith("sha256:")  # type: ignore[index]
    assert runtime["host"]["redacted"] is True  # type: ignore[index]
    assert "private-host" not in repr(value)
