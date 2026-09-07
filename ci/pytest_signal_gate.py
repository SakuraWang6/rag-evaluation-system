#!/usr/bin/env python3
"""Run pytest and validate outcomes against an executable engineering baseline."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform as python_platform
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml


class OutcomeRecorder:
    """Collect pytest outcomes through hooks instead of terminal-text parsing."""

    def __init__(self) -> None:
        self.collected: set[str] = set()
        self.outcomes: dict[str, str] = {}
        self.collection_errors: list[str] = []

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.collected = {item.nodeid for item in session.items}

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.failed:
            self.collection_errors.append(f"{report.nodeid}: {report.longrepr}")

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        node_id = report.nodeid
        was_xfail = getattr(report, "wasxfail", None)
        if report.when == "setup":
            if report.failed:
                self.outcomes[node_id] = "failed"
            elif report.skipped:
                self.outcomes[node_id] = "xfail" if was_xfail else "skipped"
            return
        if report.when == "call":
            if was_xfail:
                self.outcomes[node_id] = "xpass" if report.passed else "xfail"
            else:
                self.outcomes[node_id] = report.outcome
            return
        if report.when == "teardown" and report.failed:
            self.outcomes[node_id] = "failed"


def _expected_failed(config: Mapping[str, Any]) -> set[str]:
    return {
        str(item["node_id"])
        for item in config.get("exact_failed_node_ids", [])
        if isinstance(item, Mapping)
    }


def validate_outcomes(
    section: str,
    config: Mapping[str, Any],
    recorder: OutcomeRecorder,
    *,
    profile: str,
) -> list[str]:
    errors = list(recorder.collection_errors)
    missing_outcomes = recorder.collected - recorder.outcomes.keys()
    unexpected_outcomes = recorder.outcomes.keys() - recorder.collected
    if missing_outcomes:
        errors.append(f"collected nodes without outcomes: {sorted(missing_outcomes)}")
    if unexpected_outcomes:
        errors.append(f"outcomes for uncollected nodes: {sorted(unexpected_outcomes)}")

    by_outcome: dict[str, set[str]] = {}
    for node_id, outcome in recorder.outcomes.items():
        by_outcome.setdefault(outcome, set()).add(node_id)

    if section == "adapter_pytest":
        expected_failed = _expected_failed(config)
        actual_failed = by_outcome.get("failed", set())
        missing_failed = expected_failed - actual_failed
        additional_failed = actual_failed - expected_failed
        unexpected_green = expected_failed & by_outcome.get("passed", set())
        if missing_failed:
            errors.append(f"missing known failures: {sorted(missing_failed)}")
        if additional_failed:
            errors.append(f"additional failures: {sorted(additional_failed)}")
        if unexpected_green:
            errors.append(
                f"known failures unexpectedly passed: {sorted(unexpected_green)}"
            )
        passed = len(by_outcome.get("passed", set()))
        if passed != int(config["expected_passed"]):
            errors.append(f"passed count {passed} != {config['expected_passed']}")
        for forbidden in ("skipped", "xfail", "xpass"):
            if by_outcome.get(forbidden):
                errors.append(
                    f"forbidden {forbidden} outcomes: {sorted(by_outcome[forbidden])}"
                )
    elif section == "adapter_dirty_tests":
        passed = len(by_outcome.get("passed", set()))
        if passed != int(config["expected_passed"]):
            errors.append(f"passed count {passed} != {config['expected_passed']}")
        non_passed = {
            node_id: outcome
            for node_id, outcome in recorder.outcomes.items()
            if outcome != "passed"
        }
        if non_passed:
            errors.append(f"non-passing outcomes: {non_passed}")
    elif section == "platform_pytest":
        minimum_key = "minimum_passed_ci" if profile == "ci" else "minimum_passed_local"
        minimum_passed = int(config[minimum_key])
        passed = len(by_outcome.get("passed", set()))
        if passed < minimum_passed:
            errors.append(f"passed count {passed} < {minimum_passed}")
        required = {str(value) for value in config["required_passed_node_ids"]}
        not_passed = {
            node_id: recorder.outcomes.get(node_id, "missing")
            for node_id in required
            if recorder.outcomes.get(node_id) != "passed"
        }
        if not_passed:
            errors.append(f"required nodes did not pass: {not_passed}")
        allowed_skips = (
            set()
            if profile == "ci"
            else {str(value) for value in config["allowed_local_skipped_node_ids"]}
        )
        actual_skips = by_outcome.get("skipped", set())
        if actual_skips - allowed_skips:
            errors.append(f"unexpected skips: {sorted(actual_skips - allowed_skips)}")
        forbidden = {
            node_id: outcome
            for node_id, outcome in recorder.outcomes.items()
            if outcome in {"failed", "xfail", "xpass"}
        }
        if forbidden:
            errors.append(f"forbidden outcomes: {forbidden}")
    else:
        errors.append(f"unsupported baseline section: {section}")
    return errors


def run_pytest(paths: Sequence[str]) -> tuple[int, OutcomeRecorder]:
    recorder = OutcomeRecorder()
    exit_code = pytest.main(
        ["-q", "--tb=short", "-p", "no:cacheprovider", *paths],
        plugins=[recorder],
    )
    return int(exit_code), recorder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(__file__).with_name("known-baseline.yaml"),
    )
    parser.add_argument(
        "--section",
        choices=("adapter_pytest", "adapter_dirty_tests", "platform_pytest"),
        required=True,
    )
    parser.add_argument("--profile", choices=("ci", "local"), default="ci")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    baseline = yaml.safe_load(args.baseline.read_text(encoding="utf-8"))
    config = baseline[args.section]
    pytest_exit, recorder = run_pytest([str(value) for value in config["test_paths"]])
    errors = validate_outcomes(args.section, config, recorder, profile=args.profile)
    if (expected_python := config.get("python")) and (
        python_platform.python_version() != str(expected_python)
    ):
        errors.append(f"Python {python_platform.python_version()} != {expected_python}")
    if (expected_pytest := config.get("pytest")) and (
        pytest.__version__ != str(expected_pytest)
    ):
        errors.append(f"pytest {pytest.__version__} != {expected_pytest}")
    if expected_asyncio := config.get("pytest_asyncio"):
        try:
            actual_asyncio = importlib.metadata.version("pytest-asyncio")
        except importlib.metadata.PackageNotFoundError:
            actual_asyncio = "not installed"
        if actual_asyncio != str(expected_asyncio):
            errors.append(f"pytest-asyncio {actual_asyncio} != {expected_asyncio}")
    summary = {
        "section": args.section,
        "profile": args.profile,
        "pytest_exit_code": pytest_exit,
        "collected": len(recorder.collected),
        "outcome_counts": {
            outcome: sum(value == outcome for value in recorder.outcomes.values())
            for outcome in sorted(set(recorder.outcomes.values()))
        },
        "failed_node_ids": sorted(
            node_id
            for node_id, outcome in recorder.outcomes.items()
            if outcome == "failed"
        ),
        "errors": errors,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
