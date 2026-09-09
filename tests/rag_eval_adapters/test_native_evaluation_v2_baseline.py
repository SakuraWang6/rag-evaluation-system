"""Characterization guard for the Native Evaluation v2 migration boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rag_eval_lightrag_adapter.adapter import (
    CAPABILITIES as LIGHTRAG_CAPABILITIES,
)
from rag_eval_lightrag_adapter.adapter import resolve_config as resolve_lightrag_config
from rag_eval_rag_anything_adapter.adapter import (
    CAPABILITIES as RAG_ANYTHING_CAPABILITIES,
)
from rag_eval_rag_anything_adapter.adapter import (
    resolve_config as resolve_rag_anything_config,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "native_evaluation_v2"
    / "behavior-baseline.json"
)


def _baseline() -> dict[str, object]:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _assert_partial_mapping(
    actual: dict[str, object], expected: dict[str, object]
) -> None:
    for key, value in expected.items():
        assert actual[key] == value


def test_v2_baseline_pins_native_contract_and_offline_artifacts() -> None:
    baseline = _baseline()

    assert baseline["schema_version"] == "native-v2-input-baseline/1"
    assert baseline["baseline_revision"] == "adbad6c"
    assert baseline["contract_baseline"] == {
        "artifact_contract": "2.0",
        "input_contract": "native-document/v2",
        "wire_protocol": "2.0",
    }
    assert "legacy_corpus_modes" not in baseline
    for resolver in (resolve_lightrag_config, resolve_rag_anything_config):
        with pytest.raises(ValueError):
            resolver({"evaluation_corpus": "source_document"})

    for pinned in baseline["offline_artifacts"]:
        artifact = REPOSITORY_ROOT / pinned["path"]
        payload = artifact.read_bytes()
        assert len(payload) == pinned["size_bytes"]
        assert hashlib.sha256(payload).hexdigest() == pinned["sha256"]


def test_v2_baseline_characterization_nodes_still_exist() -> None:
    baseline = _baseline()

    assert set(baseline["characterization_nodes"]) == {
        "source_document",
        "rag-anything_answer_only",
        "artifact_v2_authority",
        "p0_unobservable_semantics",
    }
    for node_ids in baseline["characterization_nodes"].values():
        assert node_ids
        for node_id in node_ids:
            relative_path, function_name = node_id.split("::", maxsplit=1)
            source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
            assert f"def {function_name}(" in source


def test_v2_baseline_separates_runtime_and_observation_profiles() -> None:
    profiles = _baseline()["adapter_profiles"]

    lightrag = profiles["lightrag"]
    _assert_partial_mapping(
        resolve_lightrag_config({}).model_dump(mode="json"),
        lightrag["runtime_profile"],
    )
    assert LIGHTRAG_CAPABILITIES.model_dump(mode="json") == lightrag[
        "observation_profile"
    ]

    rag_anything = profiles["rag-anything"]
    _assert_partial_mapping(
        resolve_rag_anything_config({}).model_dump(mode="json"),
        rag_anything["runtime_profile"],
    )
    assert RAG_ANYTHING_CAPABILITIES.model_dump(mode="json") == rag_anything[
        "observation_profile"
    ]
