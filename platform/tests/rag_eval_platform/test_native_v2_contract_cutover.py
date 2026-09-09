from __future__ import annotations

from pathlib import Path

from rag_eval import contracts
from rag_eval.contracts.schema import PUBLIC_MODELS
from rag_eval.runs.models import TraceValidationRecordV2

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_retired_runtime_contracts_are_not_public() -> None:
    retired = {
        "AdapterCapabilities",
        "BenchmarkGold",
        "CaseResult",
        "CompatibilityNormalization",
        "DocumentInput",
        "HandshakeResponse",
        "MetricResult",
        "MetricStatus",
        "RAGAdapter",
        "RAGEvidenceItem",
        "RAGQuery",
        "RAGResult",
        "RunManifest",
        "SegmentTraceItem",
        "SegmentTraceSet",
        "SegmentTraceStage",
        "SegmentTraceStatus",
        "WireRequest",
        "WireResponse",
    }

    exported = set(contracts.__all__)
    assert retired.isdisjoint(exported)
    assert all(not hasattr(contracts, name) for name in retired)
    assert "wire_shadow_verified" not in TraceValidationRecordV2.model_fields


def test_retired_contract_owners_are_removed() -> None:
    contracts_root = REPOSITORY_ROOT / "platform" / "src" / "rag_eval" / "contracts"
    assert not (contracts_root / "adapter.py").exists()
    assert not (contracts_root / "benchmark.py").exists()
    assert not (contracts_root / "observation_compat.py").exists()


def test_checked_in_public_schemas_are_v2_only() -> None:
    schema_root = REPOSITORY_ROOT / "platform" / "schemas"
    schema_directories = sorted(
        path.name for path in schema_root.iterdir() if path.is_dir()
    )
    assert schema_directories == ["2.0"]

    retired_keys = {
        "benchmark-gold",
        "benchmark-manifest",
        "benchmark-question",
        "benchmark-segment",
        "case-result",
        "rag-query",
        "rag-result",
        "run-manifest",
        "wire-request",
        "wire-response",
        "worker-handshake",
    }
    assert retired_keys.isdisjoint(PUBLIC_MODELS)
    assert {
        "resolved-run-plan-v2",
        "run-artifact-overview-view-v2",
        "run-artifact-case-index-view-v2",
        "run-artifact-case-view-v2",
        "run-artifact-case-collection-view-v2",
    }.issubset(PUBLIC_MODELS)
    assert not any(name.endswith("-view-v1") for name in PUBLIC_MODELS)

    expected_files = {f"{name}.schema.json" for name in PUBLIC_MODELS}
    actual_files = {
        path.name for path in (schema_root / "2.0").glob("*.schema.json")
    }
    assert actual_files == expected_files
