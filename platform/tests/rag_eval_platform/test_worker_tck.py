from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from rag_eval.adapters.fake import FakeAdapter, create_worker_definition
from rag_eval.contracts.native import (
    NativeQueryV2,
    PreparedSystemV2,
    ResolvedAdapterConfigV2,
)
from rag_eval.contracts.observation import ObservationStatus
from rag_eval.runs.plans import digest_json
from rag_eval.worker.app import WorkerDefinition, create_worker_app
from rag_eval.worker.client import WorkerClient, WorkerProtocolError

from .native_worker_fixtures import native_query, stage_native_worker_input

RUN_ID = "tck-run"
TOKEN = "tck-secret"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def envelope(payload: dict[str, Any] | None = None, **overrides: Any) -> dict[str, Any]:
    body = {
        "protocol_version": "2.0",
        "request_id": "request-1",
        "run_id": RUN_ID,
        "payload": payload or {},
    }
    body.update(overrides)
    return body


def build_client() -> TestClient:
    return TestClient(
        create_worker_app(create_worker_definition(), token=TOKEN, run_id=RUN_ID)
    )


def prepare_worker(client: TestClient, root: Path) -> PreparedSystemV2:
    original, resolved = stage_native_worker_input(root, run_id=RUN_ID)
    response = client.post(
        "/prepare",
        headers=HEADERS,
        json=envelope(
            {
                "original_docx": original.model_dump(mode="json"),
                "resolved_config": resolved.model_dump(mode="json"),
            }
        ),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    return PreparedSystemV2.model_validate(response.json()["payload"])


def test_worker_requires_token() -> None:
    response = build_client().get("/health")
    assert response.status_code == 401


def test_worker_exposes_only_direct_v2_lifecycle(tmp_path: Path) -> None:
    client = build_client()
    health = client.get("/health", headers=HEADERS)
    assert health.status_code == 200
    assert health.json()["protocol_version"] == "2.0"
    assert health.json()["identity"]["adapter_id"] == "fake"
    assert client.get("/handshake", headers=HEADERS).status_code == 404
    assert client.post("/ingest", headers=HEADERS, json=envelope()).status_code == 404
    assert client.post("/reset", headers=HEADERS, json=envelope()).status_code == 404

    before_prepare = client.post(
        "/query",
        headers=HEADERS,
        json=envelope(
            {
                "prepared_system": {},
                "query": native_query().model_dump(mode="json"),
            }
        ),
    )
    assert before_prepare.json()["error"]["code"] == "not_prepared"

    prepared = prepare_worker(client, tmp_path)
    assert prepared.ingestion_receipt.ingested_documents == 1
    assert prepared.source_identity.document_id == "doc-1"

    queried = client.post(
        "/query",
        headers=HEADERS,
        json=envelope(
            {
                "prepared_system": prepared.model_dump(mode="json"),
                "query": native_query().model_dump(mode="json"),
            }
        ),
    )
    assert queried.status_code == 200
    result = queried.json()["payload"]
    assert result["protocol_version"] == "2.0"
    assert result["trace"]["case_id"] == "case-1"
    assert result["telemetry"]["native_query_executions"] == 1
    assert result["trace"]["ranked_retrieval"]["observation_status"] == "observed"
    assert len(result["trace"]["final_context"]["items"]) == 1

    close = client.post("/close", headers=HEADERS, json=envelope())
    close_again = client.post("/close", headers=HEADERS, json=envelope())
    assert close.json()["payload"]["closed"] is True
    assert close_again.json()["payload"]["closed"] is True


def test_prepare_is_single_native_ingestion_operation(tmp_path: Path) -> None:
    client = build_client()
    prepare_worker(client, tmp_path)
    original, resolved = stage_native_worker_input(tmp_path, run_id=RUN_ID)
    response = client.post(
        "/prepare",
        headers=HEADERS,
        json=envelope(
            {
                "original_docx": original.model_dump(mode="json"),
                "resolved_config": resolved.model_dump(mode="json"),
            }
        ),
    )
    assert response.json()["error"]["code"] == "already_prepared"


def test_protocol_and_run_mismatch_fail_before_adapter_call() -> None:
    client = build_client()
    protocol = client.post(
        "/prepare",
        headers=HEADERS,
        json=envelope(protocol_version="1.0"),
    )
    wrong_run = client.post(
        "/prepare",
        headers=HEADERS,
        json=envelope(run_id="other-run"),
    )
    assert protocol.json()["error"]["code"] == "invalid_request"
    assert wrong_run.json()["error"]["code"] == "run_mismatch"


def test_direct_config_rejects_corpus_route_selector(tmp_path: Path) -> None:
    _original, resolved = stage_native_worker_input(tmp_path, run_id=RUN_ID)
    config = {**resolved.adapter_config, "evaluation_corpus": "canonical_segments"}
    payload = resolved.model_dump(mode="json")
    payload.update(
        adapter_config=config,
        adapter_config_digest=digest_json(config),
    )
    with pytest.raises(ValidationError, match="corpus-route selector"):
        ResolvedAdapterConfigV2.model_validate(payload)


def test_tampered_original_docx_fails_closed(tmp_path: Path) -> None:
    client = build_client()
    original, resolved = stage_native_worker_input(tmp_path, run_id=RUN_ID)
    (Path(resolved.source_dir) / original.source_path).write_bytes(b"tampered")
    response = client.post(
        "/prepare",
        headers=HEADERS,
        json=envelope(
            {
                "original_docx": original.model_dump(mode="json"),
                "resolved_config": resolved.model_dump(mode="json"),
            }
        ),
    )
    assert response.json()["error"]["code"] == "source_identity_mismatch"


def test_tampered_canonical_catalog_fails_closed(tmp_path: Path) -> None:
    client = build_client()
    original, resolved = stage_native_worker_input(tmp_path, run_id=RUN_ID)
    (Path(resolved.source_dir) / original.canonical_catalog_path).write_text(
        "tampered\n",
        encoding="utf-8",
    )
    response = client.post(
        "/prepare",
        headers=HEADERS,
        json=envelope(
            {
                "original_docx": original.model_dump(mode="json"),
                "resolved_config": resolved.model_dump(mode="json"),
            }
        ),
    )
    assert response.json()["error"]["code"] == "source_identity_mismatch"


@pytest.mark.asyncio
async def test_timeout_adapter_is_cancellable(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    original, resolved = stage_native_worker_input(
        tmp_path,
        run_id=RUN_ID,
        adapter_config={"delay_seconds": 1, "final_context_k": 1},
    )
    prepared = await adapter.prepare(original, resolved)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            adapter.query(prepared, native_query()),
            timeout=0.01,
        )


def test_adapter_crash_is_a_structured_wire_error(tmp_path: Path) -> None:
    class CrashAdapter(FakeAdapter):
        async def query(
            self,
            prepared_system: PreparedSystemV2,
            request: NativeQueryV2,
        ):
            raise RuntimeError("intentional crash")

    identity = create_worker_definition().identity
    definition = WorkerDefinition(adapter=CrashAdapter(), identity=identity)
    client = TestClient(create_worker_app(definition, token=TOKEN, run_id=RUN_ID))
    prepared = prepare_worker(client, tmp_path)
    response = client.post(
        "/query",
        headers=HEADERS,
        json=envelope(
            {
                "prepared_system": prepared.model_dump(mode="json"),
                "query": native_query().model_dump(mode="json"),
            }
        ),
    )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "adapter_error"


def test_malformed_worker_response_is_never_silently_accepted() -> None:
    client = WorkerClient("http://worker.invalid", token=TOKEN, run_id=RUN_ID)
    response = httpx.Response(200, json={"unexpected": True})
    with pytest.raises(WorkerProtocolError, match="malformed"):
        client._parse(response, "request-1", None)

    malformed_payload = httpx.Response(
        200,
        json={
            "protocol_version": "2.0",
            "request_id": "request-1",
            "run_id": RUN_ID,
            "status": "ok",
            "payload": {"unexpected": True},
            "error": None,
        },
    )
    with pytest.raises(WorkerProtocolError, match="malformed V2 payload"):
        client._parse(malformed_payload, "request-1", PreparedSystemV2)
    client.close()


@pytest.mark.asyncio
async def test_fake_adapter_observes_native_result_without_legacy_wrapper(
    tmp_path: Path,
) -> None:
    adapter = FakeAdapter()
    original, resolved = stage_native_worker_input(tmp_path, run_id=RUN_ID)
    prepared = await adapter.prepare(original, resolved)
    result = await adapter.query(prepared, native_query())

    assert result.protocol_version == "2.0"
    assert result.trace.raw_retrieval.observation_status == (
        ObservationStatus.OBSERVED
    )
    assert result.telemetry["native_query_executions"] == 1
