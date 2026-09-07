"""Immutable, append-only SHA-256 baselines for historical run trees.

This module has intentionally small dependencies and does not import the
platform's existing run-history or evaluation code.  A baseline is a manifest
of the exact regular files under a run directory.  It is written outside the
run and is created with exclusive filesystem operations, so a second capture
cannot silently overwrite the first one.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "historical-immutable-baseline/1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: Any) -> bytes:
    """Encode JSON in the stable form used for all derived digests."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_files(run_dir: Path) -> list[tuple[str, Path]]:
    """Return all regular files, rejecting symlinks in a historical tree."""

    root = run_dir.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)

    files: list[tuple[str, Path]] = []
    for current, dir_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        # A symlinked directory is not followed by os.walk, but accepting it
        # would make the captured tree ambiguous.  Reject it explicitly.
        for directory in dir_names:
            candidate = current_path / directory
            if candidate.is_symlink():
                raise ValueError(f"symlink is not allowed in baseline tree: {candidate}")
        for filename in file_names:
            candidate = current_path / filename
            if candidate.is_symlink():
                raise ValueError(f"symlink is not allowed in baseline tree: {candidate}")
            if not candidate.is_file():
                raise ValueError(f"non-regular file is not allowed in baseline tree: {candidate}")
            relative = candidate.relative_to(root).as_posix()
            files.append((relative, candidate))

    files.sort(key=lambda item: item[0])
    return files


def _entry_payload(run_dir: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for relative, path in _relative_files(run_dir)
    ]


def _manifest_payload(
    *,
    run_id: str,
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    # Do not include a wall-clock value in the integrity payload.  This keeps
    # repeated captures of an unchanged tree comparable and reproducible.
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "file_count": len(files),
        "files": files,
    }
    payload["entries_sha256"] = _sha256_bytes(_canonical_json(files))
    payload["manifest_sha256"] = _sha256_bytes(_canonical_json(payload))
    return payload


def _validate_entries(files: Any, declared_count: Any) -> list[dict[str, Any]]:
    """Validate and normalize manifest entries before comparing bytes."""

    if not isinstance(files, list):
        raise ValueError("baseline manifest files must be a list")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("baseline file entry must be an object")
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError(f"baseline path is not relative: {relative!r}")
        if relative in seen or "\\" in relative:
            raise ValueError(f"baseline path is duplicated or non-portable: {relative!r}")
        parts = Path(relative).parts
        if ".." in parts or "." in parts:
            raise ValueError(f"baseline path contains traversal/dot segment: {relative!r}")
        size = entry.get("size_bytes")
        sha = entry.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError(f"invalid baseline size for {relative!r}: {size!r}")
        if not isinstance(sha, str) or not _SHA256_RE.fullmatch(sha):
            raise ValueError(f"invalid baseline SHA256 for {relative!r}")
        seen.add(relative)
        normalized.append({"path": relative, "size_bytes": size, "sha256": sha})
    if not isinstance(declared_count, int) or isinstance(declared_count, bool):
        raise ValueError("baseline file_count must be an integer")
    if declared_count != len(normalized):
        raise ValueError(
            f"baseline file_count mismatch: declared {declared_count}, entries {len(normalized)}"
        )
    return normalized


@dataclass(frozen=True)
class BaselineManifest:
    """Loaded baseline manifest with its path and integrity status."""

    path: Path
    payload: Mapping[str, Any]

    @property
    def run_id(self) -> str:
        return str(self.payload["run_id"])

    @property
    def file_count(self) -> int:
        return int(self.payload["file_count"])

    @property
    def manifest_sha256(self) -> str:
        return str(self.payload["manifest_sha256"])


@dataclass(frozen=True)
class BaselineVerification:
    """Byte-level comparison result for a run against a baseline."""

    ok: bool
    manifest_path: Path
    expected_file_count: int
    actual_file_count: int
    mismatches: tuple[dict[str, Any], ...]
    manifest_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "manifest_path": str(self.manifest_path),
            "expected_file_count": self.expected_file_count,
            "actual_file_count": self.actual_file_count,
            "mismatches": list(self.mismatches),
            "manifest_sha256": self.manifest_sha256,
        }


def _load_manifest(path: Path) -> BaselineManifest:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"baseline manifest must be an object: {path}")
    if payload.get("schema_version") == SCHEMA_VERSION:
        files = _validate_entries(payload.get("files"), payload.get("file_count"))
        payload = dict(payload)
        payload["files"] = files
        expected_manifest_sha = payload.get("manifest_sha256")
        if not isinstance(expected_manifest_sha, str):
            raise ValueError("baseline manifest has no manifest_sha256")
        unsigned = dict(payload)
        unsigned.pop("manifest_sha256", None)
        actual_manifest_sha = _sha256_bytes(_canonical_json(unsigned))
        if actual_manifest_sha != expected_manifest_sha:
            raise ValueError(
                f"baseline manifest integrity mismatch: expected {expected_manifest_sha}, "
                f"computed {actual_manifest_sha}"
            )
        entries_sha = _sha256_bytes(_canonical_json(files))
        if entries_sha != payload.get("entries_sha256"):
            raise ValueError("baseline entries_sha256 does not match files")
    elif payload.get("schema_version") in {
        "historical-run-baseline/v1",
        "evidence-repair-input-baseline/1",
    }:
        # The first audit pass intentionally used a compact mapping of
        # relative path -> {bytes, sha256}.  Read it as an immutable baseline
        # too, while keeping newly captured manifests on the stronger v1
        # append-only schema above.
        files = payload.get("files")
        if not isinstance(files, dict):
            raise ValueError("legacy baseline files must be an object")
        normalized = []
        for relative, entry in sorted(files.items()):
            if not isinstance(entry, dict):
                raise ValueError(f"legacy baseline entry is not an object: {relative}")
            normalized.append(
                {
                    "path": relative,
                    "size_bytes": int(entry["bytes"]),
                    "sha256": str(entry["sha256"]),
                }
            )
        payload = dict(payload)
        payload["files"] = _validate_entries(normalized, payload.get("file_count"))
        payload["schema_version"] = SCHEMA_VERSION
        # The legacy document has no integrity field of its own.  Its
        # integrity is still checked by hashing each source byte below.
        payload["manifest_sha256"] = _sha256_bytes(_canonical_json(normalized))
    else:
        raise ValueError(f"unsupported baseline schema: {payload.get('schema_version')!r}")
    return BaselineManifest(path=path, payload=payload)


def capture_immutable_baseline(
    run_dir: str | Path,
    output_dir: str | Path,
    *,
    run_id: str | None = None,
) -> BaselineManifest:
    """Capture a run tree into a new, external, immutable manifest directory.

    ``output_dir`` must not already exist.  The function creates exactly one
    ``manifest.json`` there and never copies or modifies anything under
    ``run_dir``.  The caller can use ``verify_immutable_baseline`` later to
    detect a changed, missing, or newly-added byte.
    """

    run_path = Path(run_dir).resolve(strict=True)
    destination = Path(output_dir).resolve(strict=False)
    # This guard must precede *any* destination mkdir.  It protects the
    # immutable source even when a caller accidentally passes a child path or
    # a symlinked parent inside the run.
    if destination == run_path or run_path in destination.parents:
        raise ValueError(
            f"baseline destination must be outside source run: {destination} under {run_path}"
        )
    files = _entry_payload(run_path)
    if not files:
        raise ValueError(f"cannot baseline an empty run directory: {run_path}")

    if destination.exists():
        raise FileExistsError(f"baseline destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # mkdir(exist_ok=False) is the append-only guard.  It also protects against
    # two workers capturing the same version concurrently.
    destination.mkdir(mode=0o755, exist_ok=False)

    resolved_run_id = run_id or run_path.name
    payload = _manifest_payload(run_id=resolved_run_id, files=files)
    manifest_path = destination / "manifest.json"
    try:
        with manifest_path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
    except Exception:
        # The destination was just created by this call; remove only this
        # empty/partial derived directory if manifest creation failed.  Never
        # touch the source run.  A successful manifest is never replaced.
        try:
            if manifest_path.exists():
                manifest_path.unlink()
            destination.rmdir()
        except OSError:
            pass
        raise
    return BaselineManifest(path=manifest_path, payload=payload)


def verify_immutable_baseline(
    run_dir: str | Path,
    manifest_path: str | Path,
) -> BaselineVerification:
    """Compare every baseline file and path against the current run tree."""

    manifest = _load_manifest(Path(manifest_path).resolve(strict=True))
    actual_entries = {
        relative: {
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for relative, path in _relative_files(Path(run_dir))
    }
    expected_entries = {
        str(entry["path"]): dict(entry)
        for entry in manifest.payload["files"]
        if isinstance(entry, dict) and "path" in entry
    }

    mismatches: list[dict[str, Any]] = []
    for relative in sorted(set(expected_entries) | set(actual_entries)):
        expected = expected_entries.get(relative)
        actual = actual_entries.get(relative)
        if expected is None:
            mismatches.append({"path": relative, "kind": "unexpected_file", "actual": actual})
        elif actual is None:
            mismatches.append({"path": relative, "kind": "missing_file", "expected": expected})
        elif expected != actual:
            mismatches.append(
                {
                    "path": relative,
                    "kind": "bytes_changed",
                    "expected": expected,
                    "actual": actual,
                }
            )

    return BaselineVerification(
        ok=not mismatches and len(expected_entries) == len(actual_entries),
        manifest_path=manifest.path,
        expected_file_count=len(expected_entries),
        actual_file_count=len(actual_entries),
        mismatches=tuple(mismatches),
        manifest_sha256=manifest.manifest_sha256,
    )
