from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from rag_eval.api import create_app
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths


def _client(tmp_path: Path) -> tuple[PlatformService, TestClient]:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    return service, TestClient(create_app(service, start_supervisor=False))


def test_llm_configuration_bootstraps_typed_stages_and_sanitizes_secrets(tmp_path: Path) -> None:
    _service, client = _client(tmp_path)
    response = client.get("/api/v1/product/llm/config")
    assert response.status_code == 200
    value = response.json()
    assert value["config_version"] == 1
    assert value["providers"][0]["provider_id"] == "ollama-local"
    assert len(value["bindings"]) == 7
    assert "api_key_ref" not in response.text


def test_llm_configuration_write_is_cors_compatible_for_webui(tmp_path: Path) -> None:
    _service, client = _client(tmp_path)
    response = client.options(
        "/api/v1/product/llm/config",
        headers={
            "Origin": "http://127.0.0.1:4178",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert "PUT" in response.headers.get("access-control-allow-methods", "")


def test_llm_configuration_is_revisioned_and_unknown_bindings_fail_closed(tmp_path: Path) -> None:
    _service, client = _client(tmp_path)
    current = client.get("/api/v1/product/llm/config").json()
    payload = {
        "providers": [
            {
                "provider_id": "ollama-local",
                "display_name": "Local Ollama",
                "kind": "ollama",
                "endpoint": "http://127.0.0.1:11434",
                "model": "qwen3:8b",
                "embedding_model": "bge-m3:latest",
                "enabled": True,
            }
        ],
        "bindings": current["bindings"],
        "actor": "reviewer",
        "reason": "switch authoring model",
    }
    saved = client.put("/api/v1/product/llm/config", json=payload)
    assert saved.status_code == 200
    assert saved.json()["config_version"] == 2
    assert saved.json()["parent_revision_id"] == current["revision_id"]
    revisions = client.get("/api/v1/product/llm/config/revisions")
    assert revisions.status_code == 200
    assert [item["config_version"] for item in revisions.json()] == [2, 1]

    invalid = {**payload, "bindings": [{**current["bindings"][0], "provider_id": "missing"}] + current["bindings"][1:]}
    rejected = client.put("/api/v1/product/llm/config", json=invalid)
    assert rejected.status_code == 400


def test_llm_remote_key_is_stored_by_reference_only(tmp_path: Path) -> None:
    service, client = _client(tmp_path)

    class FakeSecrets:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}

        def set(self, value: str) -> str:
            ref = f"secret://local/{len(self.values) + 1}"
            self.values[ref] = value
            return ref

        def get(self, reference: str) -> str:
            return self.values[reference]

        def delete(self, reference: str) -> None:
            self.values.pop(reference, None)

    service.secrets = FakeSecrets()  # type: ignore[assignment]
    current = client.get("/api/v1/product/llm/config").json()
    body = {
        "providers": [
            {key: value for key, value in current["providers"][0].items() if key in {"provider_id", "display_name", "kind", "endpoint", "model", "embedding_model", "enabled"}},
            {
                "provider_id": "remote-openai",
                "display_name": "Remote",
                "kind": "openai_compatible",
                "endpoint": "https://example.test/v1/chat/completions",
                "model": "gpt-test",
                "embedding_model": None,
                "enabled": True,
            },
        ],
        "bindings": current["bindings"],
        "secrets": {"remote-openai": "top-secret"},
    }
    saved = client.put("/api/v1/product/llm/config", json=body)
    assert saved.status_code == 200
    assert "top-secret" not in saved.text
    assert saved.json()["providers"][-1]["api_key_configured"] is True
    assert "top-secret" not in client.get("/api/v1/product/llm/config/revisions").text


def test_llm_external_provider_requires_an_api_key(tmp_path: Path) -> None:
    _service, client = _client(tmp_path)
    current = client.get("/api/v1/product/llm/config").json()
    existing = {
        key: value
        for key, value in current["providers"][0].items()
        if key in {"provider_id", "display_name", "kind", "endpoint", "model", "embedding_model", "enabled"}
    }
    response = client.put(
        "/api/v1/product/llm/config",
        json={
            "providers": [
                existing,
                {
                    "provider_id": "remote-openai",
                    "display_name": "Remote",
                    "kind": "openai_compatible",
                    "endpoint": "https://example.test/v1/chat/completions",
                    "model": "",
                    "embedding_model": None,
                    "enabled": True,
                },
            ],
            "bindings": current["bindings"],
        },
    )
    assert response.status_code == 400
    assert "requires an API key" in response.text


def test_llm_provider_health_reports_model_catalog_without_sending_content(tmp_path: Path, monkeypatch) -> None:
    _service, client = _client(tmp_path)

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "models": [
                    {"name": "qwen3:4b-instruct", "capabilities": ["completion"]},
                    {"name": "bge-m3:latest", "capabilities": ["embedding"]},
                ]
            }

    calls: list[tuple[str, dict[str, str], float, bool]] = []

    def fake_get(url: str, *, headers: dict[str, str], timeout: float, trust_env: bool) -> FakeResponse:
        calls.append((url, headers, timeout, trust_env))
        return FakeResponse()

    monkeypatch.setattr("rag_eval.llm.httpx.get", fake_get)
    checked = client.post("/api/v1/product/llm/providers/ollama-local/health")
    assert checked.status_code == 200
    assert checked.json()["health_status"] == "healthy"
    assert checked.json()["available_chat_models"] == ["qwen3:4b-instruct"]
    assert checked.json()["available_embedding_models"] == ["bge-m3:latest"]
    assert calls == [("http://127.0.0.1:11434/api/tags", {}, 8, False)]
    assert "question" not in checked.text


def test_llm_provider_speed_only_records_latency_and_never_detects_models(tmp_path: Path, monkeypatch) -> None:
    _service, client = _client(tmp_path)

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    calls: list[tuple[str, dict[str, str], float, bool]] = []

    def fake_get(url: str, *, headers: dict[str, str], timeout: float, trust_env: bool) -> FakeResponse:
        calls.append((url, headers, timeout, trust_env))
        return FakeResponse()

    clock = iter((10.0, 10.037))
    monkeypatch.setattr("rag_eval.llm.httpx.get", fake_get)
    monkeypatch.setattr("rag_eval.llm.time", SimpleNamespace(perf_counter=lambda: next(clock)))
    measured = client.post("/api/v1/product/llm/providers/ollama-local/speed")

    assert measured.status_code == 200
    assert measured.json()["latency_status"] == "measured"
    assert measured.json()["latency_ms"] == 37
    assert measured.json()["available_models"] == []
    assert calls == [("http://127.0.0.1:11434/api/version", {}, 8, False)]


def test_llm_provider_speed_failures_return_a_typed_status_instead_of_http_500(tmp_path: Path, monkeypatch) -> None:
    _service, client = _client(tmp_path)

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("transport unavailable")

    monkeypatch.setattr("rag_eval.llm.httpx.get", unavailable)
    response = client.post("/api/v1/product/llm/providers/ollama-local/speed")
    assert response.status_code == 200
    assert response.json()["latency_status"] == "unreachable"
    assert response.json()["latency_ms"] is None


def test_llm_provider_can_be_added_before_catalogue_detection_but_not_bound_without_a_model(tmp_path: Path) -> None:
    _service, client = _client(tmp_path)
    current = client.get("/api/v1/product/llm/config").json()
    existing = {
        key: value
        for key, value in current["providers"][0].items()
        if key in {"provider_id", "display_name", "kind", "endpoint", "model", "embedding_model", "enabled"}
    }
    provider = {
        "provider_id": "new-ollama",
        "display_name": "New Ollama",
        "kind": "ollama",
        "endpoint": "http://127.0.0.1:11435",
        "model": "",
        "embedding_model": None,
        "enabled": True,
    }
    allowed = client.put(
        "/api/v1/product/llm/config",
        json={"providers": [existing, provider], "bindings": current["bindings"]},
    )
    assert allowed.status_code == 200

    invalid_bindings = [dict(item) for item in current["bindings"]]
    invalid_bindings[0].update({"provider_id": "new-ollama", "model": None})
    rejected = client.put(
        "/api/v1/product/llm/config",
        json={"providers": [existing, provider], "bindings": invalid_bindings},
    )
    assert rejected.status_code == 400
    assert "requires a selected model" in rejected.text


def test_llm_provider_health_failures_return_a_typed_status_instead_of_http_500(tmp_path: Path, monkeypatch) -> None:
    _service, client = _client(tmp_path)

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("transport unavailable")

    monkeypatch.setattr("rag_eval.llm.httpx.get", unavailable)
    response = client.post("/api/v1/product/llm/providers/ollama-local/health")
    assert response.status_code == 200
    assert response.json()["health_status"] == "unreachable"
    assert response.json()["health_message"] == "transport unavailable"
