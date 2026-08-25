from __future__ import annotations

import io
import base64
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_eval.api import create_app
from rag_eval.datasets.drafts import DatasetDraft, DatasetDraftStore, DraftCase, DraftDocument
from rag_eval.products import EvaluationDraft, SystemConnection, canonical_experiment
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths
from rag_eval.systems import SystemRegistration
from rag_eval.reproducibility import safe_environment
from rag_eval.secrets import EncryptedDevFileSecretStore
from tests.rag_eval_platform.test_bundle_store import write_bundle


def test_dataset_draft_text_span_validates_and_seals(tmp_path: Path) -> None:
    store = DatasetDraftStore(tmp_path / "drafts", tmp_path / "staging")
    bundle_store = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=False).datasets
    content = "The capital of France is Paris."
    draft = DatasetDraft(
        name="manual",
        version="1.0.0",
        documents=[DraftDocument(document_id="doc-1", filename="source.md", content=content)],
        cases=[
            DraftCase(
                case_id="case-1",
                question="What is the capital of France?",
                gold_answer="Paris",
                document_id="doc-1",
                span_start=25,
                span_end=30,
            )
        ],
    )
    stored = store.save(draft)
    store.validate(stored)
    bundle = store.seal(stored, bundle_store)
    evidence = bundle.gold_evidence_sets["evidence-set-case-1"].evidence[0]
    assert evidence.locator.type == "text_span"
    assert evidence.locator.start == 25
    assert evidence.canonical_value == "Paris"


def test_versioned_profile_defaults_are_expanded_not_runtime_lookups(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    assert service.products is not None
    profile = service.products.profiles.get("lightrag", "1.0.1")
    connection = service.products.save_connection(
        SystemConnection(
            system_id="lightrag",
            display_name="My LightRAG",
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            python_executable=sys.executable,
        )
    )
    draft = EvaluationDraft(
        bundle_id="a" * 64,
        system_id="lightrag",
        profile_id="lightrag",
        profile_version="1.0.1",
        display_name="basic",
    )
    spec = canonical_experiment(draft, connection, profile, case_ids=["case-1"])
    assert spec.adapter_config["retrieval_candidate_k"] == 20
    assert spec.adapter_config["final_context_k"] == 5
    assert spec.query_config["retrieval_candidate_k"] == 20
    assert spec.metric_config == {"k_values": [1, 3, 5]}
    assert "profile_version" not in spec.adapter_config
    assert spec.adapter_config["model"] == {
        "llm_binding": "ollama",
        "embedding_binding": "ollama",
        "llm_model": "qwen3:4b-instruct",
        "embedding_model": "bge-m3:latest",
    }


def test_legacy_profile_without_model_identity_fails_before_execution(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    assert service.products is not None
    profile = service.products.profiles.get("lightrag", "1.0.0")
    connection = service.products.save_connection(
        SystemConnection(
            system_id="lightrag",
            display_name="Legacy LightRAG",
            profile_id="lightrag",
            profile_version="1.0.0",
            python_executable=sys.executable,
        )
    )
    draft = EvaluationDraft(
        bundle_id="a" * 64,
        system_id="lightrag",
        profile_id="lightrag",
        profile_version="1.0.0",
        display_name="legacy-basic",
    )
    with pytest.raises(ValueError, match="generation model, embedding model"):
        canonical_experiment(draft, connection, profile, case_ids=["case-1"])


def test_basic_and_advanced_compile_to_the_same_explicit_spec(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    assert service.products is not None
    profile = service.products.profiles.get("lightrag", "1.0.1")
    connection = service.products.save_connection(
        SystemConnection(
            system_id="lightrag",
            display_name="LightRAG",
            profile_id="lightrag",
            profile_version="1.0.1",
            python_executable=sys.executable,
        )
    )
    fields = dict(
        bundle_id="a" * 64,
        system_id="lightrag",
        profile_id="lightrag",
        profile_version="1.0.1",
        display_name="same-input",
        adapter_overrides={"model": {"llm_model": "qwen3:4b-instruct", "embedding_model": "bge-m3:latest"}},
        query_overrides={"retrieval_candidate_k": 20, "final_context_k": 5},
    )
    basic = canonical_experiment(EvaluationDraft(mode="basic", **fields), connection, profile, case_ids=["case-1"])
    advanced = canonical_experiment(EvaluationDraft(mode="advanced", **fields), connection, profile, case_ids=["case-1"])
    assert basic.model_dump(mode="json") == advanced.model_dump(mode="json")


def test_text_safe_rag_anything_profile_is_versioned_and_fully_expanded(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    assert service.products is not None
    legacy = service.products.profiles.get("rag-anything", "1.0.0")
    profile = service.products.profiles.get("rag-anything", "1.0.1")
    assert "enable_image_processing" not in legacy.defaults["adapter_config"]
    assert profile.defaults["adapter_config"]["enable_image_processing"] is False
    connection = service.products.save_connection(
        SystemConnection(
            system_id="rag-anything",
            display_name="RAG-Anything",
            profile_id="rag-anything",
            profile_version="1.0.1",
            python_executable=sys.executable,
        )
    )
    spec = canonical_experiment(
        EvaluationDraft(
            bundle_id="a" * 64,
            system_id="rag-anything",
            profile_id="rag-anything",
            profile_version="1.0.1",
            display_name="text-only",
        ),
        connection,
        profile,
        case_ids=["case-1"],
    )
    assert spec.adapter_config["enable_table_processing"] is False
    assert spec.query_config["retrieval_candidate_k"] == 3


def test_basic_system_uses_profile_runtime_configuration_without_exposing_a_path(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("RAG_EVAL_LIGHTRAG_WORKER_PYTHON", "/managed/lightrag/python")
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    client = TestClient(create_app(service, start_supervisor=False))
    response = client.post(
        "/api/v1/product/systems",
        json={
            "connection": {
                "system_id": "lightrag",
                "display_name": "LightRAG",
                "profile_id": "lightrag",
                "profile_version": "1.0.1",
            }
        },
    )
    assert response.status_code == 200
    assert "python_executable" not in response.text
    assert service.products is not None
    assert service.products.get_connection("lightrag").python_executable == "/managed/lightrag/python"


def test_product_disabled_preserves_legacy_only_api(tmp_path: Path) -> None:
    source = tmp_path / "bundle"
    source.mkdir()
    write_bundle(source)
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=False)
    assert not service.paths.product.exists()
    service.datasets.register(source)
    service.systems.register(
        SystemRegistration(
            system_id="fake-rag",
            adapter_id="fake",
            adapter_factory="rag_eval.adapters.fake:create_worker_definition",
            python_executable=sys.executable,
        )
    )
    client = TestClient(create_app(service, start_supervisor=False))
    assert client.get("/api/v1/product/profiles").status_code == 404
    assert client.get("/api/v1/datasets").status_code == 200
    assert client.get("/api/v1/systems").json()[0]["system_id"] == "fake-rag"


def test_product_zip_upload_and_system_api_never_return_secret_values(tmp_path: Path) -> None:
    source = tmp_path / "bundle"
    source.mkdir()
    write_bundle(source)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as value:
        for path in source.rglob("*"):
            if path.is_file():
                value.writestr(path.relative_to(source).as_posix(), path.read_bytes())
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)

    class FakeSecrets:
        def set(self, value: str) -> str:
            assert value == "super-secret"
            return "secret://local/redacted"
        def get(self, reference: str) -> str:
            raise AssertionError("launch not expected")
        def delete(self, reference: str) -> None:
            return None

    service.secrets = FakeSecrets()  # type: ignore[assignment]
    client = TestClient(create_app(service, start_supervisor=False))
    profiles = client.get("/api/v1/product/profiles")
    assert profiles.status_code == 200
    assert "adapter_factory" not in profiles.text
    assert "defaults" not in profiles.text
    uploaded = client.post(
        "/api/v1/product/datasets/upload",
        content=archive.getvalue(),
        headers={"content-type": "application/zip", "x-rag-eval-filename": "bundle.zip"},
    )
    assert uploaded.status_code == 200
    response = client.post(
        "/api/v1/product/systems",
        json={
            "connection": {
                "system_id": "lightrag",
                "display_name": "LightRAG",
                "profile_id": "lightrag",
                "profile_version": "1.0.1",
                "python_executable": sys.executable,
            },
            "secrets": {"API_TOKEN": "super-secret"},
        },
    )
    assert response.status_code == 200
    assert response.json()["secret_keys"] == ["API_TOKEN"]
    assert response.json()["connection_test_status"] == "not_tested"
    assert "super-secret" not in response.text
    assert "super-secret" not in client.get("/api/v1/product/systems").text


def test_product_secret_rotation_and_removal_keep_values_out_of_api(tmp_path: Path) -> None:
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)

    class FakeSecrets:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}
            self.removed: list[str] = []
        def set(self, value: str) -> str:
            reference = f"secret://local/ref-{len(self.values) + 1}"
            self.values[reference] = value
            return reference
        def get(self, reference: str) -> str:
            return self.values[reference]
        def delete(self, reference: str) -> None:
            self.removed.append(reference)
            self.values.pop(reference, None)

    secrets = FakeSecrets()
    service.secrets = secrets  # type: ignore[assignment]
    client = TestClient(create_app(service, start_supervisor=False))
    connection = {
        "system_id": "lightrag",
        "display_name": "LightRAG",
        "profile_id": "lightrag",
        "profile_version": "1.0.1",
        "python_executable": sys.executable,
    }
    first = client.post("/api/v1/product/systems", json={"connection": connection, "secrets": {"API_TOKEN": "first-value"}})
    assert first.status_code == 200
    rotated = client.post("/api/v1/product/systems", json={"connection": connection, "secrets": {"API_TOKEN": "second-value"}})
    assert rotated.status_code == 200
    assert rotated.json()["secret_keys"] == ["API_TOKEN"]
    assert "first-value" not in rotated.text and "second-value" not in rotated.text
    assert secrets.removed == ["secret://local/ref-1"]
    removed = client.delete("/api/v1/product/systems/lightrag/secrets/API_TOKEN")
    assert removed.status_code == 200
    assert removed.json()["secret_keys"] == []
    assert secrets.removed == ["secret://local/ref-1", "secret://local/ref-2"]


def test_runtime_endpoint_is_not_serialized_by_reproducibility_environment() -> None:
    assert "OLLAMA_HOST" not in safe_environment({"OLLAMA_HOST": "http://private-host:11434"})


def test_explicit_development_secret_store_encrypts_without_serializing_value(tmp_path: Path) -> None:
    key = base64.urlsafe_b64encode(b"x" * 32).decode("ascii")
    path = tmp_path / "secrets.enc"
    store = EncryptedDevFileSecretStore(path, key)
    reference = store.set("super-secret")
    assert store.get(reference) == "super-secret"
    assert "super-secret" not in path.read_text(encoding="utf-8")
    assert path.stat().st_mode & 0o777 == 0o600
    store.delete(reference)


def test_wizard_draft_compiles_to_existing_experiment_and_job_store(tmp_path: Path) -> None:
    source = tmp_path / "bundle"
    source.mkdir()
    write_bundle(source)
    service = PlatformService(PlatformPaths(tmp_path / "platform"), product_enabled=True)
    bundle = service.datasets.register(source)
    client = TestClient(create_app(service, start_supervisor=False))
    connection = client.post(
        "/api/v1/product/systems",
        json={
            "connection": {
                "system_id": "lightrag",
                "display_name": "LightRAG",
                "profile_id": "lightrag",
                "profile_version": "1.0.1",
                "python_executable": sys.executable,
            }
        },
    )
    assert connection.status_code == 200
    created = client.post(
        "/api/v1/product/evaluation-drafts",
        json={
            "mode": "basic",
            "bundle_id": bundle.bundle_id,
            "system_id": "lightrag",
            "profile_id": "lightrag",
            "profile_version": "1.0.1",
            "display_name": "guided-run",
            "adapter_overrides": {},
            "query_overrides": {},
            "metric_overrides": {},
            "case_ids": None,
            "seed": 0,
            "repetitions": 1,
            "formal": False,
        },
    )
    assert created.status_code == 200
    draft_id = created.json()["draft_id"]
    preview = client.get(f"/api/v1/product/evaluation-drafts/{draft_id}/preview")
    assert preview.status_code == 200
    assert preview.json()["query_config"]["retrieval_candidate_k"] == 20
    finalized = client.post(f"/api/v1/product/evaluation-drafts/{draft_id}/finalize")
    assert finalized.status_code == 200
    assert finalized.json()["job"]["execution_provider"] == "local"
    assert service.jobs.list()[0].experiment.experiment_id == finalized.json()["experiment"]["experiment_id"]
