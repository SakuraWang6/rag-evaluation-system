from __future__ import annotations

import json
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


def test_local_launcher_does_not_enable_retired_run_or_host_profiles() -> None:
    launcher = (
        REPOSITORY_ROOT / "platform" / "scripts" / "start-local.sh"
    ).read_text(encoding="utf-8")

    retired_fragments = {
        ".rag-eval-e2e-rehearsal",
        "/Users/",
        "Historical runs:",
        "RAG_EVAL_BOOTSTRAP_LOCAL_SYSTEM",
        "RAG_EVAL_RUN_ARCHIVES",
    }
    assert not any(fragment in launcher for fragment in retired_fragments)


def test_one_off_audit_recipes_are_not_supported_operator_scripts() -> None:
    scripts_root = REPOSITORY_ROOT / "platform" / "scripts"
    retired_scripts = {
        "audit_docx_rich_content.py",
        "run_complex_table_canonical_audit.py",
        "run_development_benchmark_48_authoring.py",
        "run_real_benchmark_authoring_pilot.py",
    }

    assert not any((scripts_root / name).exists() for name in retired_scripts)


def test_webui_authoring_catalog_has_no_retired_presegmented_actions() -> None:
    locale_root = REPOSITORY_ROOT / "webui" / "src" / "i18n"
    retired_keys = {
        "product.authoring.canonicalRegistered",
        "product.authoring.compatibilityExport",
        "product.authoring.exported",
        "product.authoring.exportHint",
        "product.authoring.exportRegister",
        "product.authoring.exportViews",
        "product.authoring.nativeRegistered",
        "product.authoring.registerCanonical",
        "product.authoring.registerNative",
    }

    for locale_name in ("en-US.json", "zh-CN.json"):
        messages = json.loads((locale_root / locale_name).read_text(encoding="utf-8"))
        assert retired_keys.isdisjoint(messages)
