"""Authenticated loopback implementation of the direct Worker Wire 2.0."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from rag_eval.contracts import PROTOCOL_VERSION
from rag_eval.contracts.native import (
    NativeQueryV2,
    NativeRAGAdapterV2,
    OriginalDocumentV2,
    PreparedSystemV2,
    ResolvedAdapterConfigV2,
)
from rag_eval.contracts.observation import AdapterRunResultV2
from rag_eval.contracts.wire import (
    WireError,
    WireRequestV2,
    WireResponseV2,
    WorkerHealthV2,
    WorkerIdentityV2,
)


@dataclass(slots=True)
class WorkerDefinition:
    adapter: NativeRAGAdapterV2
    identity: WorkerIdentityV2


def create_worker_app(
    definition: WorkerDefinition,
    *,
    token: str,
    run_id: str,
) -> FastAPI:
    if not token:
        raise ValueError("worker token must not be empty")
    app = FastAPI(title="RAG Adapter Worker", version=PROTOCOL_VERSION)
    state: dict[str, PreparedSystemV2 | bool | None] = {
        "prepared_system": None,
        "closed": False,
    }

    def authorize(authorization: str | None) -> None:
        expected = f"Bearer {token}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="invalid worker token")

    def parse_request(
        body: dict[str, Any], *, allow_closed: bool = False
    ) -> WireRequestV2:
        try:
            request = WireRequestV2.model_validate(body)
        except ValidationError as exc:
            raise WorkerRequestError("invalid_request", str(exc)) from exc
        if request.run_id != run_id:
            raise WorkerRequestError("run_mismatch", "request run_id is not this worker")
        if state["closed"] and not allow_closed:
            raise WorkerRequestError("worker_closed", "adapter worker is closed")
        return request

    def ok(
        request: WireRequestV2,
        payload: dict[str, Any] | None = None,
    ) -> JSONResponse:
        response = WireResponseV2(
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
        response = WireResponseV2(
            request_id=request_id or "unknown",
            run_id=run_id,
            status="error",
            error=WireError(code=code, message=message, retryable=retryable),
        )
        return JSONResponse(response.model_dump(mode="json"), status_code=status_code)

    async def invoke(
        body: dict[str, Any],
        authorization: str | None,
        operation: Callable[[WireRequestV2], Awaitable[dict[str, Any] | None]],
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
                request_id=request_id,
                code=exc.code,
                message=str(exc),
            )
        except ValidationError as exc:
            return error_response(
                request_id=request_id,
                code="invalid_payload",
                message=str(exc),
            )
        # Adapter code is an untrusted plugin boundary. Normalize ordinary
        # exceptions while allowing cancellation/crash BaseExceptions to end
        # the worker process.
        except Exception as exc:  # noqa: BLE001
            return error_response(
                request_id=request_id,
                code="adapter_error",
                message=str(exc) or type(exc).__name__,
                status_code=500,
            )

    @app.get("/health")
    async def health(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        authorize(authorization)
        report = await definition.adapter.health()
        return WorkerHealthV2(
            identity=definition.identity,
            status=report.status,
            ready=report.ready,
            details=report.details,
        ).model_dump(mode="json")

    @app.post("/prepare")
    async def prepare(
        body: Annotated[dict[str, Any], Body()],
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        async def operation(request: WireRequestV2) -> dict[str, Any]:
            if state["prepared_system"] is not None:
                raise WorkerRequestError(
                    "already_prepared",
                    "run-scoped worker may prepare exactly once",
                )
            original = OriginalDocumentV2.model_validate(
                request.payload.get("original_docx")
            )
            resolved = ResolvedAdapterConfigV2.model_validate(
                request.payload.get("resolved_config")
            )
            if resolved.run_id != run_id:
                raise WorkerRequestError(
                    "run_mismatch",
                    "resolved config run_id is not this worker",
                )
            _verify_original_document(original, resolved)
            prepared = await definition.adapter.prepare(original, resolved)
            _verify_prepared_system(
                prepared,
                original=original,
                identity=definition.identity,
            )
            state["prepared_system"] = prepared
            return prepared.model_dump(mode="json", exclude_none=True)

        return await invoke(body, authorization, operation)

    @app.post("/query")
    async def query(
        body: Annotated[dict[str, Any], Body()],
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        async def operation(request: WireRequestV2) -> dict[str, Any]:
            prepared = state["prepared_system"]
            if not isinstance(prepared, PreparedSystemV2):
                raise WorkerRequestError(
                    "not_prepared",
                    "prepare must complete before query",
                )
            supplied = PreparedSystemV2.model_validate(
                request.payload.get("prepared_system")
            )
            if supplied != prepared:
                raise WorkerRequestError(
                    "prepared_system_mismatch",
                    "query does not reference this Worker's prepared system",
                )
            native_query = NativeQueryV2.model_validate(request.payload.get("query"))
            result = await definition.adapter.query(prepared, native_query)
            _verify_adapter_result(
                result,
                prepared=prepared,
                identity=definition.identity,
                case_id=native_query.case_id,
            )
            return result.model_dump(mode="json", exclude_none=True)

        return await invoke(body, authorization, operation)

    @app.post("/close")
    async def close(
        body: Annotated[dict[str, Any], Body()],
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        async def operation(_request: WireRequestV2) -> dict[str, Any]:
            if not state["closed"]:
                await definition.adapter.close()
                state["closed"] = True
            return {"closed": True}

        return await invoke(body, authorization, operation, allow_closed=True)

    return app


def _verified_file(source_dir: str, relative_path: str, expected_sha256: str) -> None:
    root = Path(source_dir).resolve()
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise WorkerRequestError(
            "source_unavailable",
            "declared native source is outside or absent from the source sandbox",
        )
    if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected_sha256:
        raise WorkerRequestError(
            "source_identity_mismatch",
            "declared native source checksum does not match staged bytes",
        )


def _verify_original_document(
    original: OriginalDocumentV2,
    resolved: ResolvedAdapterConfigV2,
) -> None:
    _verified_file(resolved.source_dir, original.source_path, original.source_sha256)
    _verified_file(
        resolved.source_dir,
        original.canonical_catalog_path,
        original.canonical_catalog_sha256,
    )


def _verify_prepared_system(
    prepared: PreparedSystemV2,
    *,
    original: OriginalDocumentV2,
    identity: WorkerIdentityV2,
) -> None:
    source = prepared.source_identity
    if (
        source.document_id != original.document_id
        or source.source_sha256 != original.source_sha256
        or source.media_type != original.media_type
        or source.canonical_catalog_sha256
        != original.canonical_catalog_sha256
    ):
        raise WorkerRequestError(
            "prepared_identity_mismatch",
            "prepared system does not bind the declared original DOCX",
        )
    if (
        prepared.observation_profile.adapter_id != identity.adapter_id
        or prepared.observation_profile.adapter_version != identity.adapter_version
        or prepared.runtime_profile.system_id != identity.system_id
        or prepared.runtime_profile.system_version != identity.system_version
    ):
        raise WorkerRequestError(
            "prepared_identity_mismatch",
            "prepared runtime/observation identity differs from Worker identity",
        )


def _verify_adapter_result(
    result: AdapterRunResultV2,
    *,
    prepared: PreparedSystemV2,
    identity: WorkerIdentityV2,
    case_id: str,
) -> None:
    if result.normalization is not None:
        raise WorkerRequestError(
            "legacy_normalization_forbidden",
            "Direct Wire 2.0 results cannot contain compatibility normalization",
        )
    if (
        result.adapter_id != identity.adapter_id
        or result.adapter_version != identity.adapter_version
        or result.system_id != identity.system_id
        or result.system_version != identity.system_version
        or result.trace.case_id != case_id
        or result.trace.source_identity != prepared.source_identity
        or result.trace.runtime_profile != prepared.runtime_profile
        or result.trace.observation_profile != prepared.observation_profile
    ):
        raise WorkerRequestError(
            "result_identity_mismatch",
            "Adapter result differs from the prepared system or query identity",
        )


class WorkerRequestError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


__all__ = ["WorkerDefinition", "WorkerRequestError", "create_worker_app"]
