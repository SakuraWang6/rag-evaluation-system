"""Authenticated loopback implementation of Wire Protocol 1.0."""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Body, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from rag_eval.contracts import PROTOCOL_VERSION
from rag_eval.contracts.adapter import (
    DocumentInput,
    PrepareContext,
    RAGAdapter,
    RAGQuery,
)
from rag_eval.contracts.wire import (
    HandshakeResponse,
    WireError,
    WireRequest,
    WireResponse,
)


@dataclass(slots=True)
class WorkerDefinition:
    adapter: RAGAdapter
    handshake: HandshakeResponse


def create_worker_app(
    definition: WorkerDefinition,
    *,
    token: str,
    run_id: str,
) -> FastAPI:
    if not token:
        raise ValueError("worker token must not be empty")
    app = FastAPI(title="RAG Adapter Worker", version=PROTOCOL_VERSION)
    state = {"prepared": False, "closed": False}

    def authorize(authorization: str | None) -> None:
        expected = f"Bearer {token}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="invalid worker token")

    def parse_request(
        body: dict[str, Any], *, allow_closed: bool = False
    ) -> WireRequest:
        try:
            request = WireRequest.model_validate(body)
        except ValidationError as exc:
            raise WorkerRequestError("invalid_request", str(exc)) from exc
        if request.protocol_version != PROTOCOL_VERSION:
            raise WorkerRequestError("protocol_incompatible", "protocol mismatch")
        if request.run_id != run_id:
            raise WorkerRequestError("run_mismatch", "request run_id is not this worker")
        if state["closed"] and not allow_closed:
            raise WorkerRequestError("worker_closed", "adapter worker is closed")
        return request

    def ok(request: WireRequest, payload: dict[str, Any] | None = None) -> JSONResponse:
        response = WireResponse(
            request_id=request.request_id,
            run_id=request.run_id,
            status="ok",
            payload=payload or {},
        )
        return JSONResponse(response.model_dump(mode="json"))

    def error_response(
        *,
        request_id: str,
        code: str,
        message: str,
        status_code: int = 400,
        retryable: bool = False,
    ) -> JSONResponse:
        response = WireResponse(
            request_id=request_id or "unknown",
            run_id=run_id,
            status="error",
            error=WireError(code=code, message=message, retryable=retryable),
        )
        return JSONResponse(response.model_dump(mode="json"), status_code=status_code)

    async def invoke(
        body: dict[str, Any],
        authorization: str | None,
        operation: Callable[[WireRequest], Awaitable[dict[str, Any] | None]],
        *,
        allow_closed: bool = False,
    ) -> JSONResponse:
        authorize(authorization)
        request_id = str(body.get("request_id") or "unknown")
        try:
            request = parse_request(body, allow_closed=allow_closed)
            return ok(request, await operation(request))
        except WorkerRequestError as exc:
            return error_response(
                request_id=request_id, code=exc.code, message=str(exc)
            )
        except ValidationError as exc:
            return error_response(
                request_id=request_id, code="invalid_payload", message=str(exc)
            )
        # Adapter code is an untrusted plugin boundary. Normalize any ordinary
        # adapter exception while allowing BaseException cancellation/crash
        # signals to terminate the worker process.
        except Exception as exc:  # noqa: BLE001
            return error_response(
                request_id=request_id,
                code="adapter_error",
                message=str(exc) or type(exc).__name__,
                status_code=500,
            )

    @app.get("/handshake")
    async def handshake(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        authorize(authorization)
        return definition.handshake.model_dump(mode="json")

    @app.get("/health")
    async def health(
        protocol_version: str = Query(),
        request_id: str = Query(),
        requested_run_id: str = Query(alias="run_id"),
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        body = {
            "protocol_version": protocol_version,
            "request_id": request_id,
            "run_id": requested_run_id,
            "payload": {},
        }

        async def operation(_request: WireRequest) -> dict[str, Any]:
            return (await definition.adapter.health()).model_dump(mode="json")

        return await invoke(body, authorization, operation)

    @app.post("/prepare")
    async def prepare(
        body: Annotated[dict[str, Any], Body()],
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        async def operation(request: WireRequest) -> dict[str, Any]:
            context = PrepareContext.model_validate(request.payload.get("context"))
            config = request.payload.get("config")
            if not isinstance(config, dict):
                raise WorkerRequestError("invalid_payload", "prepare config must be an object")
            prepared = await definition.adapter.prepare(context, config)
            if prepared.capabilities != definition.handshake.capabilities:
                raise WorkerRequestError(
                    "capability_mismatch",
                    "prepared capabilities differ from handshake declaration",
                )
            state["prepared"] = True
            return prepared.model_dump(mode="json")

        return await invoke(body, authorization, operation)

    @app.post("/ingest")
    async def ingest(
        body: Annotated[dict[str, Any], Body()],
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        async def operation(request: WireRequest) -> dict[str, Any]:
            require_prepared(state)
            raw_documents = request.payload.get("documents")
            if not isinstance(raw_documents, list):
                raise WorkerRequestError("invalid_payload", "documents must be an array")
            documents = [DocumentInput.model_validate(item) for item in raw_documents]
            result = await definition.adapter.ingest(documents)
            return result.model_dump(mode="json")

        return await invoke(body, authorization, operation)

    @app.post("/query")
    async def query(
        body: Annotated[dict[str, Any], Body()],
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        async def operation(request: WireRequest) -> dict[str, Any]:
            require_prepared(state)
            query_request = RAGQuery.model_validate(request.payload)
            result = await definition.adapter.query(query_request)
            return result.model_dump(mode="json")

        return await invoke(body, authorization, operation)

    @app.post("/reset")
    async def reset(
        body: Annotated[dict[str, Any], Body()],
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        async def operation(_request: WireRequest) -> dict[str, Any]:
            require_prepared(state)
            result = await definition.adapter.reset()
            return result.model_dump(mode="json")

        return await invoke(body, authorization, operation)

    @app.post("/close")
    async def close(
        body: Annotated[dict[str, Any], Body()],
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        async def operation(_request: WireRequest) -> dict[str, Any]:
            if not state["closed"]:
                await definition.adapter.close()
                state["closed"] = True
            return {"closed": True}

        return await invoke(body, authorization, operation, allow_closed=True)

    return app


class WorkerRequestError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def require_prepared(state: dict[str, bool]) -> None:
    if not state["prepared"]:
        raise WorkerRequestError("not_prepared", "prepare must complete first")
