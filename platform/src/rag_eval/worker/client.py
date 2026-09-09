"""Strict client for the direct Adapter Worker Wire 2.0."""

from __future__ import annotations

import time
import uuid
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from rag_eval.contracts import PROTOCOL_VERSION
from rag_eval.contracts.native import (
    NativeQueryV2,
    OriginalDocumentV2,
    PreparedSystemV2,
    ResolvedAdapterConfigV2,
)
from rag_eval.contracts.observation import AdapterRunResultV2
from rag_eval.contracts.wire import WireRequestV2, WireResponseV2, WorkerHealthV2

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
            # Worker endpoints are Platform-owned loopback/container ports.
            # Do not inherit developer proxy settings for these requests.
            trust_env=False,
        )
        self._health: WorkerHealthV2 | None = None

    def health(self) -> WorkerHealthV2:
        response = self._client.get("/health")
        response.raise_for_status()
        try:
            health = WorkerHealthV2.model_validate(response.json())
        except (TypeError, ValueError) as exc:
            raise WorkerProtocolError("worker returned malformed V2 health") from exc
        if health.protocol_version != PROTOCOL_VERSION:
            raise WorkerProtocolError("worker protocol version is incompatible")
        self._health = health
        return health

    def wait_until_ready(self, timeout: float = 10.0) -> WorkerHealthV2:
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                report = self.health()
                if report.ready:
                    return report
                last_error = WorkerProtocolError(
                    f"worker is not ready: {report.status}"
                )
            except (httpx.HTTPError, ValueError, WorkerProtocolError) as exc:
                last_error = exc
            time.sleep(0.05)
        raise WorkerProtocolError(f"worker readiness timed out: {last_error}")

    def prepare(
        self,
        original_docx: OriginalDocumentV2,
        resolved_config: ResolvedAdapterConfigV2,
        *,
        timeout: float | None = None,
    ) -> PreparedSystemV2:
        if self._health is None:
            raise WorkerProtocolError("worker readiness must be verified before prepare")
        prepared = self._send(
            "/prepare",
            {
                "original_docx": original_docx.model_dump(mode="json"),
                "resolved_config": resolved_config.model_dump(mode="json"),
            },
            PreparedSystemV2,
            timeout=timeout,
        )
        assert prepared is not None
        identity = self._health.identity
        if (
            prepared.observation_profile.adapter_id != identity.adapter_id
            or prepared.observation_profile.adapter_version != identity.adapter_version
            or prepared.runtime_profile.system_id != identity.system_id
            or prepared.runtime_profile.system_version != identity.system_version
        ):
            raise WorkerProtocolError("prepared identity differs from Worker identity")
        return prepared

    def query(
        self,
        prepared_system: PreparedSystemV2,
        query: NativeQueryV2,
    ) -> AdapterRunResultV2:
        result = self._send(
            "/query",
            {
                "prepared_system": prepared_system.model_dump(
                    mode="json", exclude_none=True
                ),
                "query": query.model_dump(mode="json"),
            },
            AdapterRunResultV2,
        )
        assert result is not None
        return result

    def close_adapter(self) -> None:
        self._send("/close", {}, None)

    def close(self) -> None:
        self._client.close()

    def _send(
        self,
        path: str,
        payload: dict[str, Any],
        model: type[ModelT] | None,
        *,
        timeout: float | None = None,
    ) -> ModelT | None:
        request_id = uuid.uuid4().hex
        envelope = WireRequestV2(
            request_id=request_id,
            run_id=self.run_id,
            payload=payload,
        )
        request_kwargs: dict[str, Any] = {"json": envelope.model_dump(mode="json")}
        if timeout is not None:
            request_kwargs["timeout"] = timeout
        response = self._client.post(path, **request_kwargs)
        return self._parse(response, request_id, model)

    def _parse(
        self,
        response: httpx.Response,
        request_id: str,
        model: type[ModelT] | None,
    ) -> ModelT | None:
        try:
            envelope = WireResponseV2.model_validate(response.json())
        except (ValueError, TypeError) as exc:
            raise WorkerProtocolError("worker returned a malformed V2 response") from exc
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
        try:
            return model.model_validate(envelope.payload)
        except (TypeError, ValueError) as exc:
            raise WorkerProtocolError(
                "worker returned a malformed V2 payload"
            ) from exc


class WorkerProtocolError(RuntimeError):
    pass


class WorkerRemoteError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


__all__ = ["WorkerClient", "WorkerProtocolError", "WorkerRemoteError"]
