#!/usr/bin/env python3
"""Reject new normalized Platform Ruff diagnostics relative to a pinned baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

Diagnostic = tuple[str, str, str]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_filename(filename: str, platform_root: Path) -> str:
    value = filename.replace("\\", "/")
    current_root = platform_root.resolve().as_posix().rstrip("/") + "/"
    if value.startswith(current_root):
        value = value[len(current_root) :]
    else:
        for marker in ("/rag-eval-platform/", "/evaluation-system/platform/"):
            if marker in value:
                value = value.split(marker, 1)[1]
                break
        else:
            value = value.removeprefix("./").removeprefix("platform/")
    normalized = PurePosixPath(value).as_posix()
    if normalized.startswith(("../", "/")):
        raise ValueError(f"diagnostic path is outside Platform: {filename}")
    return normalized


def normalized_diagnostics(
    values: Iterable[Mapping[str, Any]], platform_root: Path
) -> Counter[Diagnostic]:
    return Counter(
        (
            normalize_filename(str(value["filename"]), platform_root),
            str(value["code"]),
            str(value["message"]),
        )
        for value in values
    )


def additions(
    baseline: Iterable[Mapping[str, Any]],
    current: Iterable[Mapping[str, Any]],
    platform_root: Path,
) -> Counter[Diagnostic]:
    return normalized_diagnostics(current, platform_root) - normalized_diagnostics(
        baseline, platform_root
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-config",
        type=Path,
        default=Path(__file__).with_name("known-baseline.yaml"),
    )
    parser.add_argument(
        "--platform-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "platform",
    )
    parser.add_argument("--ruff", default="ruff")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = yaml.safe_load(args.baseline_config.read_text(encoding="utf-8"))[
        "platform_ruff"
    ]
    baseline_path = args.baseline_config.parent.parent / config["raw_baseline"]
    actual_sha = sha256_file(baseline_path)
    if actual_sha != config["raw_baseline_sha256"]:
        print(f"baseline SHA-256 mismatch: {actual_sha}")
        return 2

    version = subprocess.run(
        [args.ruff, "--version"], capture_output=True, text=True, check=False
    )
    if version.returncode != 0 or version.stdout.strip() != config["tool"]:
        print(
            f"unexpected Ruff version: {version.stdout.strip() or version.stderr.strip()}"
        )
        return 2
    result = subprocess.run(
        [args.ruff, "check", ".", "--output-format=json"],
        cwd=args.platform_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in {0, 1}:
        print(result.stderr)
        return 2
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        current = json.loads(result.stdout)
    except (json.JSONDecodeError, OSError) as error:
        print(f"cannot read Ruff diagnostics: {error}")
        return 2
    if len(baseline) != int(config["expected_before_diagnostics"]):
        print(f"unexpected baseline diagnostic count: {len(baseline)}")
        return 2
    fixable = sum(
        (item.get("fix") or {}).get("applicability") == "safe" for item in baseline
    )
    if fixable != int(config["expected_before_fixable"]):
        print(f"unexpected baseline fixable count: {fixable}")
        return 2

    new = additions(baseline, current, args.platform_root)
    summary = {
        "baseline_count": len(baseline),
        "current_count": len(current),
        "removed_count": sum(
            (
                normalized_diagnostics(baseline, args.platform_root)
                - normalized_diagnostics(current, args.platform_root)
            ).values()
        ),
        "added_count": sum(new.values()),
        "added": [
            {"path": path, "code": code, "message": message, "count": count}
            for (path, code, message), count in sorted(new.items())
        ],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if new else 0


if __name__ == "__main__":
    raise SystemExit(main())
