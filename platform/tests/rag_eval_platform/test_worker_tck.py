from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from rag_eval.adapters.fake import FakeAdapter
from rag_eval.contracts.adapter import AdapterCapabilities, PrepareContext, RAGQuery
from rag_eval.contracts.wire import HandshakeResponse
from rag_eval.worker.app import WorkerDefinition, create_worker_app
from rag_eval.worker.client import WorkerClient, WorkerProtocolError

RUN_ID = "tck-run"
TOKEN = "tck-secret"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def envelope(payload: dict[str, Any] | None = None, **overrides: Any) -> dict[str, Any]:
    body = {
        "protocol_version": "1.0",
        "request_id": "request-1",
        "run_id": RUN_ID,
        "payload": payload or {},
    }
    body.update(overrides)
    return body


def build_client(capabilities: AdapterCapabilities | None = None) -> TestClient:
    capabilities = capabilities or AdapterCapabilities(
        answer=True,
        raw_retrieval=True,
        ranked_retrieval=True,
        final_context=True,
        object_provenance=True,
        latency_breakdown=True,
        token_usage=True,
        reset=True,
    )
    definition = WorkerDefinition(
        adapter=FakeAdapter(capabilities=capabilities),
        handshake=HandshakeResponse(
            adapter_id="fake",
            adapter_version="0.1.0",
            system_id="fake-rag",
            system_version="fake-rag-1",
            capabilities=capabilities,
        ),
    )
    return TestClient(create_worker_app(definition, token=TOKEN, run_id=RUN_ID))


def test_worker_requires_token() -> None:
    response = build_client().get("/handshake")
    assert response.status_code == 401


def test_worker_lifecycle_and_stage_semantics(tmp_path) -> None:
    client = build_client()
    handshake = client.get("/handshake", headers=HEADERS)
    assert handshake.status_code == 200
    assert handshake.json()["protocol_version"] == "1.0"

    before_prepare = client.post(
        "/query",
        headers=HEADERS,
        json=envelope({"case_id": "c-1", "question": "value?"}),
    )
    assert before_prepare.json()["error"]["code"] == "not_prepared"

    prepared = client.post(
        "/prepare",
        headers=HEADERS,
        json=envelope(
            {
                "context": {
                    "run_id": RUN_ID,
                    "work_dir": str(tmp_path / "work"),
                    "source_dir": str(tmp_path / "source"),
                    "platform_version": "0.1.0",
                },
                "config": {"final_context_k": 1},
            }
        ),
    )
    assert prepared.json()["status"] == "ok"

    ingested = client.post(
        "/ingest",
        headers=HEADERS,
        json=envelope(
            {
                "documents": [
                    {
                        "document_id": "doc-1",
                        "content": "alpha value 42",
                        "mime_type": "text/plain",
                        "metadata": {},
                    },
                    {
                        "document_id": "doc-2",
                        "content": "unrelated",
                        "mime_type": "text/plain",
                        "metadata": {},
                    },
                ]
            }
        ),
    )
    assert ingested.json()["payload"]["ingested_documents"] == 2

    queried = client.post(
        "/query",
        headers=HEADERS,
        json=envelope(
            {
                "case_id": "c-1",
                "question": "alpha value",
                "generate_answer": True,
                "final_context_k": 1,
                "generation_options": {},
            }
        ),
    )
    result = queried.json()["payload"]
    assert result["raw_retrieval"] is not None
    assert result["ranked_retrieval"][0]["document_id"] == "doc-1"
    assert len(result["final_context"]) == 1

    close = client.post("/close", headers=HEADERS, json=envelope())
    close_again = client.post("/close", headers=HEADERS, json=envelope())
    assert close.json()["payload"]["closed"] is True
    assert close_again.json()["payload"]["closed"] is True


def test_partial_capability_returns_none_not_empty(tmp_path) -> None:
    capabilities = AdapterCapabilities(answer=False, ranked_retrieval=True)
    client = build_client(capabilities)
    client.post(
        "/prepare",
        headers=HEADERS,
        json=envelope(
            {
                "context": {
                    "run_id": RUN_ID,
                    "work_dir": str(tmp_path / "work"),
                    "source_dir": str(tmp_path / "source"),
                    "platform_version": "0.1.0",
                },
                "config": {},
            }
        ),
    )
    client.post("/ingest", headers=HEADERS, json=envelope({"documents": []}))
    response = client.post(
        "/query",
        headers=HEADERS,
        json=envelope(
            {
                "case_id": "c-1",
                "question": "anything",
                "generate_answer": True,
                "generation_options": {},
            }
        ),
    )
    result = response.json()["payload"]
    assert result["answer"] is None
    assert result["raw_retrieval"] is None
    assert result["ranked_retrieval"] == []
    assert result["final_context"] is None


def test_protocol_and_run_mismatch_fail_before_adapter_call() -> None:
    client = build_client()
    protocol = client.post(
        "/prepare",
        headers=HEADERS,
        json=envelope(protocol_version="0.2"),
    )
    wrong_run = client.post(
        "/prepare",
        headers=HEADERS,
        json=envelope(run_id="other-run"),
    )
    assert protocol.json()["error"]["code"] == "protocol_incompatible"
    assert wrong_run.json()["error"]["code"] == "run_mismatch"


@pytest.mark.asyncio
async def test_timeout_adapter_is_cancellable(tmp_path) -> None:
    adapter = FakeAdapter()
    await adapter.prepare(
        context=PrepareContext(
            run_id=RUN_ID,
            work_dir=str(tmp_path / "work"),
            source_dir=str(tmp_path / "source"),
            platform_version="0.1.0",
        ),
        config={"delay_seconds": 1},
    )
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            adapter.query(RAGQuery(case_id="c-1", question="slow")),
            timeout=0.01,
        )


def test_adapter_crash_is_a_structured_wire_error(tmp_path) -> None:
    class CrashAdapter(FakeAdapter):
        async def query(self, request):
            raise RuntimeError("intentional crash")

    capabilities = AdapterCapabilities(answer=True)
    definition = WorkerDefinition(
        adapter=CrashAdapter(capabilities=capabilities),
        handshake=HandshakeResponse(
            adapter_id="crash",
            adapter_version="0.1.0",
            system_id="crash",
            system_version="1",
            capabilities=capabilities,
        ),
    )
    client = TestClient(create_worker_app(definition, token=TOKEN, run_id=RUN_ID))
    client.post(
        "/prepare",
        headers=HEADERS,
        json=envelope(
            {
                "context": {
                    "run_id": RUN_ID,
                    "work_dir": str(tmp_path / "work"),
                    "source_dir": str(tmp_path / "source"),
                    "platform_version": "0.1.0",
                },
                "config": {},
            }
        ),
    )
    response = client.post(
        "/query",
        headers=HEADERS,
        json=envelope(
            {
                "case_id": "c-1",
                "question": "crash",
                "generation_options": {},
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
    client.close()
