"""Root acceptance receipts for externally derived historical re-scores.

The old run and the offline rescore both remain immutable.  A separate
receipt is the only mechanism that allows a validated derivative to appear in
the product projection.  Acceptance deliberately means *the pinned offline
projection is fit to display*; it never upgrades the old worker execution to
a fresh, comparable benchmark run.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .baseline import verify_immutable_baseline
from .reconstruction import write_derived_json


PROJECTION_ACCEPTANCE_SCHEMA_VERSION = "historical-rescore-projection-acceptance/1"
PROJECTION_ACCEPTANCE_STATUS = "ACCEPTED_FOR_PRODUCT_PROJECTION"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return value


def _rescore_inputs_are_complete(value: Mapping[str, Any]) -> bool:
    inputs = value.get("inputs")
    if not isinstance(inputs, Mapping):
        return False
    source = inputs.get("source")
    mapping = inputs.get("map")
    cases = inputs.get("cases")
    baseline = value.get("baseline_verification")
    return bool(
        isinstance(source, Mapping)
        and isinstance(source.get("source_docx"), Mapping)
        and isinstance(source.get("canonical_jsonl"), Mapping)
        and isinstance(mapping, Mapping)
        and isinstance(mapping.get("file_sha256"), str)
        and isinstance(cases, Mapping)
        and isinstance(cases.get("files"), Mapping)
        and isinstance(baseline, Mapping)
        and isinstance(baseline.get("manifest_path"), str)
        and isinstance(baseline.get("manifest_sha256"), str)
    )


def _validate_rescore_for_acceptance(run: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema_version") != "historical-rescore/1":
        raise ValueError("unsupported historical rescore schema")
    if value.get("run_id") != run.name:
        raise ValueError("historical rescore run_id does not match source run")
    if not isinstance(value.get("rescore_identity"), str) or not value["rescore_identity"]:
        raise ValueError("historical rescore has no identity")
    if not _rescore_inputs_are_complete(value):
        raise ValueError("historical rescore does not contain complete pinned inputs")

    baseline = value["baseline_verification"]
    assert isinstance(baseline, Mapping)
    baseline_path = Path(str(baseline["manifest_path"])).resolve(strict=True)
    current_baseline = verify_immutable_baseline(run, baseline_path).as_dict()
    if not current_baseline["ok"]:
        raise ValueError("source run no longer matches the pinned immutable baseline")
    if current_baseline["manifest_sha256"] != baseline.get("manifest_sha256"):
        raise ValueError("historical rescore baseline hash does not match current baseline")

    index = value.get("production_index")
    if not isinstance(index, Mapping) or not all(
        index.get(key) is True
        for key in ("catalog_verified", "map_digest_verified", "source_pins_verified")
    ):
        raise ValueError("historical rescore provenance index is not fully verified")
    execution_scope = value.get("execution_scope")
    if not isinstance(execution_scope, Mapping):
        raise ValueError("historical rescore has no execution scope")
    return {
        "baseline_verification": current_baseline,
        "production_index": dict(index),
        "execution_scope": dict(execution_scope),
    }


def accept_historical_rescore_projection(
    run_dir: str | Path,
    rescore_path: str | Path,
    *,
    reviewer: str,
    note: str,
) -> dict[str, Any]:
    """Write one immutable acceptance receipt for a pinned offline rescore.

    The receipt itself is append-only (the destination is opened exclusively),
    and all checks happen before the write.  It is deliberately impossible to
    mark the underlying source run as rerun or Worker-verified here.
    """

    run = Path(run_dir).resolve(strict=True)
    rescore = Path(rescore_path).resolve(strict=True)
    if run == rescore or run in rescore.parents:
        raise ValueError("historical rescore must live outside the source run")
    reviewer = reviewer.strip()
    note = note.strip()
    if not reviewer:
        raise ValueError("reviewer must not be blank")
    if not note:
        raise ValueError("acceptance note must not be blank")

    value = _load_object(rescore)
    validation = _validate_rescore_for_acceptance(run, value)
    return {
        "schema_version": PROJECTION_ACCEPTANCE_SCHEMA_VERSION,
        "status": PROJECTION_ACCEPTANCE_STATUS,
        "run_id": run.name,
        "reviewer": reviewer,
        "reviewed_at": datetime.now(UTC).isoformat(),
        "note": note,
        "rescore": {
            "path": str(rescore),
            "file_sha256": _sha256_file(rescore),
            "rescore_identity": value["rescore_identity"],
            "source_status": value.get("status"),
        },
        "baseline_verification": validation["baseline_verification"],
        "production_index": validation["production_index"],
        "execution_scope": validation["execution_scope"],
        "scope": {
            "original_run_rewritten": False,
            "retrieval_rerun": False,
            "answer_generation_rerun": False,
            "worker_runtime_verified": False,
            "comparable_to_benchmark_contract_v1": False,
            "limitations": [
                "This receipt accepts only the pinned offline product projection.",
                "It does not make the historical DOCX worker run comparable to segment-native benchmark-contract/v1 results.",
                "It does not replace a fresh Worker execution or prove original runtime liveness.",
            ],
        },
    }


def write_historical_rescore_projection_acceptance(
    run_dir: str | Path,
    rescore_path: str | Path,
    output_path: str | Path,
    *,
    reviewer: str,
    note: str,
) -> Path:
    """Validate and atomically append an acceptance receipt outside ``runs/``."""

    run = Path(run_dir).resolve(strict=True)
    receipt = accept_historical_rescore_projection(
        run,
        rescore_path,
        reviewer=reviewer,
        note=note,
    )
    return write_derived_json(run, output_path, receipt)


def accepted_projection_receipt(
    receipt_path: str | Path,
    *,
    run_dir: str | Path,
    run_id: str,
    rescore_path: str | Path,
    rescore_identity: str,
) -> dict[str, Any] | None:
    """Return a receipt only when it still pins this exact rescore byte."""

    try:
        receipt = _load_object(Path(receipt_path).resolve(strict=True))
        rescore = Path(rescore_path).resolve(strict=True)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if (
        receipt.get("schema_version") != PROJECTION_ACCEPTANCE_SCHEMA_VERSION
        or receipt.get("status") != PROJECTION_ACCEPTANCE_STATUS
        or receipt.get("run_id") != run_id
    ):
        return None
    pinned = receipt.get("rescore")
    if not isinstance(pinned, Mapping):
        return None
    try:
        same_path = Path(str(pinned.get("path"))).resolve(strict=True) == rescore
    except (OSError, ValueError):
        return None
    if (
        not same_path
        or pinned.get("rescore_identity") != rescore_identity
        or pinned.get("file_sha256") != _sha256_file(rescore)
    ):
        return None
    baseline = receipt.get("baseline_verification")
    index = receipt.get("production_index")
    if not isinstance(baseline, Mapping) or baseline.get("ok") is not True:
        return None
    try:
        current_baseline = verify_immutable_baseline(
            Path(run_dir).resolve(strict=True),
            Path(str(baseline.get("manifest_path"))).resolve(strict=True),
        ).as_dict()
    except (OSError, ValueError):
        return None
    if (
        current_baseline.get("ok") is not True
        or current_baseline.get("manifest_sha256") != baseline.get("manifest_sha256")
    ):
        return None
    if not isinstance(index, Mapping) or not all(
        index.get(key) is True
        for key in ("catalog_verified", "map_digest_verified", "source_pins_verified")
    ):
        return None
    return receipt


__all__ = [
    "PROJECTION_ACCEPTANCE_SCHEMA_VERSION",
    "PROJECTION_ACCEPTANCE_STATUS",
    "accept_historical_rescore_projection",
    "accepted_projection_receipt",
    "write_historical_rescore_projection_acceptance",
]
