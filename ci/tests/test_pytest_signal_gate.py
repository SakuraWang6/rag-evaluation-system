from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "pytest_signal_gate.py"
SPEC = importlib.util.spec_from_file_location("pytest_signal_gate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
OutcomeRecorder = MODULE.OutcomeRecorder
validate_outcomes = MODULE.validate_outcomes


def recorder(outcomes: dict[str, str]):
    value = OutcomeRecorder()
    value.collected = set(outcomes)
    value.outcomes = outcomes
    return value


def adapter_config() -> dict[str, object]:
    return {
        "expected_passed": 2,
        "exact_failed_node_ids": [
            {"node_id": "test_gate.py::test_known", "classification": "BASELINE"}
        ],
    }


def test_adapter_gate_accepts_only_the_exact_failure_set() -> None:
    outcomes = {
        "test_gate.py::test_one": "passed",
        "test_gate.py::test_two": "passed",
        "test_gate.py::test_known": "failed",
    }
    assert (
        validate_outcomes(
            "adapter_pytest", adapter_config(), recorder(outcomes), profile="ci"
        )
        == []
    )


def test_adapter_gate_rejects_unexpected_green_and_additional_failure() -> None:
    outcomes = {
        "test_gate.py::test_one": "failed",
        "test_gate.py::test_two": "passed",
        "test_gate.py::test_known": "passed",
    }
    errors = validate_outcomes(
        "adapter_pytest", adapter_config(), recorder(outcomes), profile="ci"
    )
    assert any("additional failures" in error for error in errors)
    assert any("unexpectedly passed" in error for error in errors)


def test_adapter_gate_rejects_skip_and_xfail() -> None:
    outcomes = {
        "test_gate.py::test_one": "skipped",
        "test_gate.py::test_two": "xfail",
        "test_gate.py::test_known": "failed",
    }
    errors = validate_outcomes(
        "adapter_pytest", adapter_config(), recorder(outcomes), profile="ci"
    )
    assert any("forbidden skipped" in error for error in errors)
    assert any("forbidden xfail" in error for error in errors)


def test_adapter_gate_accepts_all_green_and_requires_named_contract_nodes() -> None:
    config = {
        "expected_passed": 2,
        "exact_failed_node_ids": [],
        "required_passed_node_ids": ["test_gate.py::test_contract"],
    }
    outcomes = {
        "test_gate.py::test_contract": "passed",
        "test_gate.py::test_other": "passed",
    }
    assert (
        validate_outcomes(
            "adapter_pytest", config, recorder(outcomes), profile="ci"
        )
        == []
    )

    missing = recorder({"test_gate.py::test_replacement": "passed"})
    missing.outcomes["test_gate.py::test_other"] = "passed"
    missing.collected.add("test_gate.py::test_other")
    errors = validate_outcomes("adapter_pytest", config, missing, profile="ci")
    assert any("required nodes did not pass" in error for error in errors)


def test_named_adapter_section_can_reuse_exact_adapter_policy() -> None:
    config = {
        "gate_kind": "adapter_pytest",
        "expected_passed": 1,
        "exact_failed_node_ids": [],
        "required_passed_node_ids": ["test_gate.py::test_contract"],
    }

    assert (
        validate_outcomes(
            "third_adapter_observation",
            config,
            recorder({"test_gate.py::test_contract": "passed"}),
            profile="ci",
        )
        == []
    )


def test_platform_gate_requires_named_nodes_and_rejects_ci_skips() -> None:
    config = {
        "minimum_passed_ci": 2,
        "minimum_passed_local": 1,
        "required_passed_node_ids": ["test_gate.py::test_required"],
        "required_passed_node_ids_ci": ["test_gate.py::test_sandbox"],
        "allowed_local_skipped_node_ids": ["test_gate.py::test_sandbox"],
    }
    outcomes = {
        "test_gate.py::test_required": "passed",
        "test_gate.py::test_other": "passed",
        "test_gate.py::test_sandbox": "skipped",
    }
    errors = validate_outcomes(
        "platform_pytest", config, recorder(outcomes), profile="ci"
    )
    assert any("unexpected skips" in error for error in errors)
    assert any("required nodes did not pass" in error for error in errors)
    assert (
        validate_outcomes(
            "platform_pytest", config, recorder(outcomes), profile="local"
        )
        == []
    )


def test_gate_rejects_collected_node_without_outcome() -> None:
    value = recorder({"test_gate.py::test_one": "passed"})
    value.collected.add("test_gate.py::test_missing")
    errors = validate_outcomes(
        "adapter_dirty_tests",
        {"expected_passed": 1},
        value,
        profile="ci",
    )
    assert any("without outcomes" in error for error in errors)
