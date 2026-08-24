"""Blind-Benchmark role and public/sealed directory validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from rag_eval.contracts.research import BlindProtocol


class BlindProtocolError(ValueError):
    """A public/sealed boundary or frozen timeline is invalid."""


@dataclass(frozen=True, slots=True)
class BlindLayoutReport:
    public_root: Path
    sealed_root: Path
    protocol: BlindProtocol


PUBLIC_REQUIREMENTS = ("source_public", "questions_public", "public_manifest.json")
SEALED_REQUIREMENTS = (
    "gold_answers.jsonl",
    "gold_evidence.jsonl",
    "canonical",
    "checksums.json",
    "blind_protocol.json",
)


def validate_blind_layout(public_root: Path, sealed_root: Path) -> BlindLayoutReport:
    """Validate the minimum role boundary without reading public Gold content."""

    public_root = public_root.resolve()
    sealed_root = sealed_root.resolve()
    if public_root == sealed_root or sealed_root.is_relative_to(public_root):
        raise BlindProtocolError("sealed directory must not be inside the public tree")
    _validate_required(public_root, PUBLIC_REQUIREMENTS, public=True)
    _validate_required(sealed_root, SEALED_REQUIREMENTS, public=False)
    leaked = [
        path.relative_to(public_root).as_posix()
        for path in public_root.rglob("*")
        if path.is_file() and "gold" in path.name.casefold()
    ]
    if leaked:
        raise BlindProtocolError(f"public blind tree exposes Gold-named files: {sorted(leaked)}")
    manifest = json.loads((public_root / "public_manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise BlindProtocolError("public_manifest.json must contain an object")
    forbidden_keys = {"gold_answers", "gold_evidence", "canonical"}
    if forbidden_keys.intersection(manifest):
        raise BlindProtocolError("public manifest must not expose Gold or canonical entries")
    protocol = BlindProtocol.model_validate_json(
        (sealed_root / "blind_protocol.json").read_text(encoding="utf-8")
    )
    sealed_digest = "sha256:" + hashlib.sha256(
        (sealed_root / "checksums.json").read_bytes()
    ).hexdigest()
    if protocol.sealed_bundle_digest != sealed_digest:
        raise BlindProtocolError("sealed_bundle_digest does not match sealed checksums.json")
    return BlindLayoutReport(public_root, sealed_root, protocol)


def _validate_required(root: Path, required: tuple[str, ...], *, public: bool) -> None:
    if not root.is_dir():
        raise BlindProtocolError(f"{'public' if public else 'sealed'} root is not a directory")
    for name in required:
        path = root / name
        expected_directory = name in {"source_public", "questions_public", "canonical"}
        if expected_directory and not path.is_dir():
            raise BlindProtocolError(f"missing required directory: {name}")
        if not expected_directory and not path.is_file():
            raise BlindProtocolError(f"missing required file: {name}")
        if path.is_symlink():
            raise BlindProtocolError(f"required path must not be a symlink: {name}")
