"""Adapter Worker transport envelopes.

Only the V2 models are used by the runtime.  The V1 model definitions remain
temporarily importable until the dedicated contract-removal phase.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from rag_eval.contracts.adapter import AdapterCapabilities
from rag_eval.contracts.native import NATIVE_ADAPTER_PROTOCOL_VERSION


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HandshakeResponse(WireModel):
    protocol_version: Literal["1.0"] = "1.0"
    adapter_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    system_id: str = Field(min_length=1)
    system_version: str = Field(min_length=1)
    capabilities: AdapterCapabilities


class WireError(WireModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False


class WireRequest(WireModel):
    protocol_version: str = Field(default="1.0", min_length=1)
    request_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class WireResponse(WireModel):
    protocol_version: Literal["1.0"] = "1.0"
    request_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: Literal["ok", "error"]
    payload: dict[str, Any] | None = None
    error: WireError | None = None

    @model_validator(mode="after")
    def validate_body(self) -> WireResponse:
        if self.status == "ok" and self.error is not None:
            raise ValueError("successful response must not contain error")
        if self.status == "error" and self.error is None:
            raise ValueError("error response requires error details")
        return self


class WorkerIdentityV2(WireModel):
    protocol_version: Literal["2.0"] = NATIVE_ADAPTER_PROTOCOL_VERSION
    adapter_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    system_id: str = Field(min_length=1)
    system_version: str = Field(min_length=1)


class WorkerHealthV2(WireModel):
    protocol_version: Literal["2.0"] = NATIVE_ADAPTER_PROTOCOL_VERSION
    identity: WorkerIdentityV2
    status: str = Field(min_length=1)
    ready: StrictBool
    details: dict[str, Any] = Field(default_factory=dict)


class WireRequestV2(WireModel):
    protocol_version: Literal["2.0"] = NATIVE_ADAPTER_PROTOCOL_VERSION
    request_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class WireResponseV2(WireModel):
    protocol_version: Literal["2.0"] = NATIVE_ADAPTER_PROTOCOL_VERSION
    request_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: Literal["ok", "error"]
    payload: dict[str, Any] | None = None
    error: WireError | None = None

    @model_validator(mode="after")
    def validate_body(self) -> WireResponseV2:
        if self.status == "ok" and self.error is not None:
            raise ValueError("successful response must not contain error")
        if self.status == "error" and self.error is None:
            raise ValueError("error response requires error details")
        return self
