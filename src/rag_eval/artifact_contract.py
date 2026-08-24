"""Canonical immutable artifacts used by formal experiments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel


def canonical_artifact_bytes(model: BaseModel) -> bytes:
    return (
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def artifact_digest(model: BaseModel) -> str:
    return "sha256:" + hashlib.sha256(canonical_artifact_bytes(model)).hexdigest()


def freeze_artifact(model: BaseModel, destination: Path) -> str:
    """Write canonical JSON once; replacing different content is forbidden."""

    # Keep the Contract import graph independent of storage.  The write path is
    # only needed by the CLI after contracts have already been loaded.
    from rag_eval.storage.atomic import atomic_write_bytes

    payload = canonical_artifact_bytes(model)
    digest = artifact_digest(model)
    if destination.exists():
        existing = destination.read_bytes()
        if existing != payload:
            raise FileExistsError(f"immutable artifact already exists: {destination}")
        return digest
    atomic_write_bytes(destination, payload)
    return digest
