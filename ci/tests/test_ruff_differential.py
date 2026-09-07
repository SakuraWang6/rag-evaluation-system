from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "check_ruff_differential.py"
SPEC = importlib.util.spec_from_file_location("check_ruff_differential", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
additions = MODULE.additions
normalize_filename = MODULE.normalize_filename


def diagnostic(
    filename: str, code: str = "F401", message: str = "unused"
) -> dict[str, str]:
    return {"filename": filename, "code": code, "message": message}


def test_normalize_filename_maps_old_and_new_roots_to_same_path(tmp_path: Path) -> None:
    platform = tmp_path / "evaluation-system" / "platform"
    expected = "src/rag_eval/example.py"
    assert (
        normalize_filename(
            "/Users/example/RAG/rag-eval-platform/src/rag_eval/example.py", platform
        )
        == expected
    )
    assert (
        normalize_filename(str(platform / "src" / "rag_eval" / "example.py"), platform)
        == expected
    )
    assert normalize_filename("platform/src/rag_eval/example.py", platform) == expected


def test_normalize_filename_rejects_parent_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        normalize_filename("../outside.py", tmp_path / "platform")


def test_differential_allows_removal_and_line_movement(tmp_path: Path) -> None:
    platform = tmp_path / "platform"
    baseline = [
        {
            **diagnostic("/old/rag-eval-platform/a.py"),
            "location": {"row": 1},
        },
        diagnostic("/old/rag-eval-platform/removed.py", "E501", "too long"),
    ]
    current = [
        {
            **diagnostic(str(platform / "a.py")),
            "location": {"row": 999},
        }
    ]
    assert additions(baseline, current, platform) == {}


def test_differential_reports_new_normalized_diagnostic(tmp_path: Path) -> None:
    platform = tmp_path / "platform"
    new = additions([], [diagnostic(str(platform / "new.py"))], platform)
    assert new[("new.py", "F401", "unused")] == 1
