"""Strict client for Adapter Worker Wire Protocol 1.0."""

from __future__ import annotations

import time
import uuid
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from rag_eval.contracts import PROTOCOL_VERSION
from rag_eval.contracts.adapter import (
    DocumentInput,
    HealthReport,
    IngestionResult,
    PrepareContext,
    PreparedSystem,
    RAGQuery,
    RAGResult,
    ResetResult,
)
from rag_eval.contracts.wire import HandshakeResponse, WireRequest, WireResponse

ModelT = TypeVar("ModelT", bound=BaseModel)


class WorkerClient:
    def __init__(
        self,
        base_url: str,
        *,
        token: str,
        run_id: str,
        timeout: float = 180.0,
    ) -> None:
        self.run_id = run_id
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        self._handshake: HandshakeResponse | None = None

    def handshake(self) -> HandshakeResponse:
        response = self._client.get("/handshake")
        response.raise_for_status()
        handshake = HandshakeResponse.model_validate(response.json())
        if handshake.protocol_version != PROTOCOL_VERSION:
            raise WorkerProtocolError("worker protocol version is incompatible")
        self._handshake = handshake
        return handshake

    def wait_for_handshake(self, timeout: float = 10.0) -> HandshakeResponse:
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                return self.handshake()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                time.sleep(0.05)
        raise WorkerProtocolError(f"worker handshake timed out: {last_error}")

    def health(self) -> HealthReport:
        request_id = uuid.uuid4().hex
        response = self._client.get(
            "/health",
            params={
                "protocol_version": PROTOCOL_VERSION,
                "request_id": request_id,
                "run_id": self.run_id,
            },
        )
        return self._parse(response, request_id, HealthReport)

    def prepare(
        self, context: PrepareContext, config: dict[str, Any]
    ) -> PreparedSystem:
        prepared = self._send(
            "/prepare",
            {"context": context.model_dump(mode="json"), "config": config},
            PreparedSystem,
        )
        if self._handshake is None:
            raise WorkerProtocolError("handshake must complete before prepare")
        if prepared.capabilities != self._handshake.capabilities:
            raise WorkerProtocolError("declared and observed capabilities differ")
        return prepared

    def ingest(self, documents: list[DocumentInput]) -> IngestionResult:
        return self._send(
            "/ingest",
            {"documents": [item.model_dump(mode="json") for item in documents]},
            IngestionResult,
        )

    def query(self, query: RAGQuery) -> RAGResult:
        return self._send("/query", query.model_dump(mode="json"), RAGResult)

    def reset(self) -> ResetResult:
        return self._send("/reset", {}, ResetResult)

    def close_adapter(self) -> None:
        self._send("/close", {}, None)

    def close(self) -> None:
        self._client.close()

    def _send(
        self,
        path: str,
        payload: dict[str, Any],
        model: type[ModelT] | None,
    ) -> ModelT | None:
        request_id = uuid.uuid4().hex
        envelope = WireRequest(
            request_id=request_id, run_id=self.run_id, payload=payload
        )
        response = self._client.post(path, json=envelope.model_dump(mode="json"))
        return self._parse(response, request_id, model)

    def _parse(
        self,
        response: httpx.Response,
        request_id: str,
        model: type[ModelT] | None,
    ) -> ModelT | None:
        try:
            envelope = WireResponse.model_validate(response.json())
        except (ValueError, TypeError) as exc:
            raise WorkerProtocolError("worker returned a malformed response") from exc
        if envelope.request_id != request_id or envelope.run_id != self.run_id:
            raise WorkerProtocolError("worker response correlation mismatch")
        if envelope.status == "error":
            assert envelope.error is not None
            raise WorkerRemoteError(
                envelope.error.code,
                envelope.error.message,
                retryable=envelope.error.retryable,
            )
        if not response.is_success:
            raise WorkerProtocolError(f"worker returned HTTP {response.status_code}")
        if model is None:
            return None
        return model.model_validate(envelope.payload)


class WorkerProtocolError(RuntimeError):
    pass


class WorkerRemoteError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
