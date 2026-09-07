"""Structured proposal providers for Authoring; never browser-secret clients."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol

import httpx


DEFAULT_OLLAMA_MODEL = "qwen3:4b-instruct"


class ProposalProviderError(RuntimeError):
    pass


class StructuredProposalProvider(Protocol):
    provider_id: str
    model: str

    def propose(self, *, task: str, source: list[dict[str, Any]], prompt: str, seed: int) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class LocalOllamaProvider:
    """Local-only Ollama structured output provider.

    The service endpoint and model are server configuration.  There is no UI
    field for a token because local Ollama does not need one.
    """

    endpoint: str = os.environ.get("RAG_EVAL_AUTHORING_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
    model: str = os.environ.get("RAG_EVAL_AUTHORING_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    provider_id: str = "ollama-local"
    # Question and answer proposal calls retain the normal 60-second timeout.
    # Durable target-discovery jobs explicitly use ``None``: they run outside
    # the request lifecycle and may legitimately need longer on a local model.
    timeout_seconds: float | None = 60.0

    def propose(self, *, task: str, source: list[dict[str, Any]], prompt: str, seed: int) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"seed": seed, "temperature": 0},
            "prompt": prompt + "\n\nSOURCE JSON:\n" + json.dumps(source, ensure_ascii=False, sort_keys=True),
        }
        try:
            # Do not inherit desktop-shell proxy settings for a loopback-only
            # provider. They can make a local Ollama request hang even when
            # the model service is healthy.
            response = httpx.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout_seconds,
                trust_env=False,
            )
            response.raise_for_status()
            body = response.json()
            value = json.loads(str(body["response"]))
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProposalProviderError(f"local Ollama proposal failed: {exc}") from exc
        if not isinstance(value, dict):
            raise ProposalProviderError("local Ollama response must be a JSON object")
        return value


@dataclass(frozen=True, slots=True)
class ConfiguredRemoteProvider:
    """Server-configured advanced provider; browser-held secrets are impossible here."""

    endpoint: str
    model: str
    authorization: str | None = None
    provider_id: str = "remote-configured"

    @classmethod
    def from_environment(cls) -> ConfiguredRemoteProvider:
        endpoint = os.environ.get("RAG_EVAL_AUTHORING_REMOTE_URL", "")
        model = os.environ.get("RAG_EVAL_AUTHORING_REMOTE_MODEL", "")
        if not endpoint or not model:
            raise ProposalProviderError("remote authoring provider is not server-configured")
        return cls(endpoint=endpoint, model=model, authorization=os.environ.get("RAG_EVAL_AUTHORING_REMOTE_AUTH"))

    def propose(self, *, task: str, source: list[dict[str, Any]], prompt: str, seed: int) -> dict[str, Any]:
        headers = {"Authorization": self.authorization} if self.authorization else {}
        payload = {"task": task, "model": self.model, "seed": seed, "prompt": prompt, "source": source}
        try:
            response = httpx.post(self.endpoint, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            value = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProposalProviderError(f"configured remote proposal failed: {exc}") from exc
        if not isinstance(value, dict):
            raise ProposalProviderError("configured remote response must be a JSON object")
        return value


def provider_metadata(provider: StructuredProposalProvider, *, prompt: str, seed: int) -> dict[str, Any]:
    return {
        "provider": provider.provider_id,
        "model": provider.model,
        "prompt_digest": sha256(prompt.encode("utf-8")).hexdigest(),
        "seed": seed,
    }
