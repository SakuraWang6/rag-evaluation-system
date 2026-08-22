"""Deterministic, source-only adapter used by the contract test kit."""

from __future__ import annotations

import asyncio
import hashlib
import re
from time import monotonic
from typing import Any

from rag_eval.contracts.adapter import (
    AdapterCapabilities,
    DocumentInput,
    HealthReport,
    IngestionResult,
    PrepareContext,
    PreparedSystem,
    RAGEvidenceItem,
    RAGQuery,
    RAGResult,
    ResetResult,
)
from rag_eval.contracts.dataset import TextSpanLocator
from rag_eval.contracts.wire import HandshakeResponse
from rag_eval.worker.app import WorkerDefinition

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


class FakeAdapter:
    """Small honest RAG implementation with no access to evaluation Gold."""

    def __init__(self, *, capabilities: AdapterCapabilities | None = None) -> None:
        self.capabilities = capabilities or AdapterCapabilities(
            answer=True,
            raw_retrieval=True,
            ranked_retrieval=True,
            final_context=True,
            object_provenance=True,
            latency_breakdown=True,
            token_usage=True,
            reset=True,
        )
        self._config: dict[str, Any] = {}
        self._documents: list[DocumentInput] = []
        self._prepared = False
        self._closed = False

    async def prepare(
        self, context: PrepareContext, config: dict[str, Any]
    ) -> PreparedSystem:
        if self._closed:
            raise RuntimeError("adapter is closed")
        self._config = {
            "final_context_k": int(config.get("final_context_k", 3)),
            "delay_seconds": float(config.get("delay_seconds", 0)),
            "answer_mode": str(config.get("answer_mode", "first_context")),
        }
        self._prepared = True
        return PreparedSystem(
            effective_config=self._config,
            capabilities=self.capabilities,
            system_version="fake-rag-1",
        )

    async def health(self) -> HealthReport:
        return HealthReport(
            status="ready" if not self._closed else "closed",
            ready=not self._closed,
            details={"prepared": self._prepared},
        )

    async def ingest(self, documents: list[DocumentInput]) -> IngestionResult:
        if not self._prepared:
            raise RuntimeError("adapter is not prepared")
        self._documents = list(documents)
        digest = hashlib.sha256()
        for document in self._documents:
            if document.content is None:
                raise ValueError("FakeAdapter only supports inline text documents")
            digest.update(document.document_id.encode())
            digest.update(b"\0")
            digest.update(document.content.encode())
            digest.update(b"\0")
        return IngestionResult(
            ingested_documents=len(documents),
            index_fingerprint=digest.hexdigest(),
        )

    async def query(self, request: RAGQuery) -> RAGResult:
        if not self._prepared:
            raise RuntimeError("adapter is not prepared")
        delay = self._config.get("delay_seconds", 0)
        if delay:
            await asyncio.sleep(delay)
        started = monotonic()
        query_tokens = {token.casefold() for token in _TOKEN_RE.findall(request.question)}
        scored: list[tuple[int, int, DocumentInput]] = []
        for index, document in enumerate(self._documents):
            if document.content is None:
                raise ValueError("FakeAdapter only supports inline text documents")
            document_tokens = {
                token.casefold() for token in _TOKEN_RE.findall(document.content)
            }
            scored.append((len(query_tokens & document_tokens), index, document))

        raw_items = [
            self._item(document, rank=index + 1, score=float(score))
            for index, (score, _original, document) in enumerate(scored)
        ]
        ranked_rows = sorted(scored, key=lambda row: (-row[0], row[1]))
        ranked_items = [
            self._item(document, rank=index + 1, score=float(score))
            for index, (score, _original, document) in enumerate(ranked_rows)
        ]
        candidate_k = request.retrieval_candidate_k or len(ranked_items)
        ranked_items = ranked_items[:candidate_k]
        context_k = request.final_context_k or self._config["final_context_k"]
        final_items = ranked_items[:context_k]
        answer = None
        if request.generate_answer and self.capabilities.answer:
            answer = final_items[0].content if final_items else ""
        elapsed = monotonic() - started
        return RAGResult(
            answer=answer,
            raw_retrieval=raw_items if self.capabilities.raw_retrieval else None,
            ranked_retrieval=(
                ranked_items if self.capabilities.ranked_retrieval else None
            ),
            final_context=final_items if self.capabilities.final_context else None,
            latency={"query_seconds": elapsed}
            if self.capabilities.latency_breakdown
            else None,
            token_usage={"context_characters": sum(len(item.content) for item in final_items)}
            if self.capabilities.token_usage
            else None,
            native_metadata={"fake": True},
        )

    def _item(
        self, document: DocumentInput, *, rank: int, score: float
    ) -> RAGEvidenceItem:
        if document.content is None:
            raise ValueError("FakeAdapter only supports inline text documents")
        return RAGEvidenceItem(
            item_id=f"{document.document_id}:{rank}",
            rank=rank,
            content=document.content,
            document_id=document.document_id,
            locator=TextSpanLocator(start=0, end=max(1, len(document.content)))
            if document.content
            else None,
            score=score,
            native_id=document.document_id,
        )

    async def reset(self) -> ResetResult:
        if not self.capabilities.reset:
            return ResetResult(supported=False, reset=False)
        self._documents = []
        return ResetResult(supported=True, reset=True)

    async def close(self) -> None:
        self._closed = True
        self._documents = []


def create_worker_definition() -> WorkerDefinition:
    capabilities = AdapterCapabilities(
        answer=True,
        raw_retrieval=True,
        ranked_retrieval=True,
        final_context=True,
        object_provenance=True,
        latency_breakdown=True,
        token_usage=True,
        reset=True,
    )
    return WorkerDefinition(
        adapter=FakeAdapter(capabilities=capabilities),
        handshake=HandshakeResponse(
            adapter_id="fake",
            adapter_version="0.1.0",
            system_id="fake-rag",
            system_version="fake-rag-1",
            capabilities=capabilities,
        ),
    )
