#!/usr/bin/env python3
"""Write a versioned historical provenance map and 57-cell matrix.

The command is read-only with respect to ``--run-dir``.  Every destination
file is opened exclusively, so a prior derived result cannot be overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT / "src"))

from rag_eval.history_provenance.baseline import verify_immutable_baseline  # noqa: E402
from rag_eval.history_provenance.reconstruction import (  # noqa: E402
    build_historical_localization_matrix,
    build_production_localization_audit,
    matrix_markdown,
    reconstruct_historical_provenance,
    write_derived_json,
    write_derived_text,
    write_reconstructed_provenance,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _implementation_source_hashes() -> dict[str, str]:
    """Pin the code that can change the meaning of the derived decisions."""

    paths = {
        "history_provenance.reconstruction": SCRIPT_ROOT / "src/rag_eval/history_provenance/reconstruction.py",
        "history_provenance.baseline": SCRIPT_ROOT / "src/rag_eval/history_provenance/baseline.py",
        "evaluation.evidence": SCRIPT_ROOT / "src/rag_eval/evaluation/evidence.py",
        "evaluation.metrics": SCRIPT_ROOT / "src/rag_eval/evaluation/metrics.py",
        "evaluation.engine": SCRIPT_ROOT / "src/rag_eval/evaluation/engine.py",
    }
    return {
        name: _sha256_file(path.resolve(strict=True))
        for name, path in paths.items()
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--map-name", default="historical-provenance-v2.json")
    parser.add_argument("--matrix-name", default="historical-localization-matrix-v2.json")
    parser.add_argument("--markdown-name", default="historical-localization-matrix-v2.md")
    parser.add_argument("--acceptance-name", default="historical-recovery-v2-acceptance.json")
    parser.add_argument("--production-audit-name", default="production-localization-audit-v2.json")
    parser.add_argument("--strict", action="store_true", help="fail on source lineage integrity errors")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    run = args.run_dir.resolve(strict=True)
    output = args.output_dir.resolve(strict=False)
    reconstruction = reconstruct_historical_provenance(run, strict=args.strict)
    map_path = write_reconstructed_provenance(
        run,
        output,
        reconstruction=reconstruction,
        filename=args.map_name,
    )
    matrix = build_historical_localization_matrix(reconstruction, run)
    matrix_path = write_derived_json(run, output / args.matrix_name, matrix)
    markdown_path = write_derived_text(run, output / args.markdown_name, matrix_markdown(matrix))
    production_audit = build_production_localization_audit(
        reconstruction,
        run,
        helper_matrix=matrix,
    )
    production_audit_path = write_derived_json(
        run,
        output / args.production_audit_name,
        production_audit,
    )
    baseline_result = None
    if args.baseline is not None:
        baseline_result = verify_immutable_baseline(run, args.baseline).as_dict()
    artifact_hashes = {
        "map": _sha256_file(map_path),
        "matrix": _sha256_file(matrix_path),
        "matrix_markdown": _sha256_file(markdown_path),
        "production_localization_audit": _sha256_file(production_audit_path),
    }
    acceptance = {
        "schema_version": "historical-recovery-acceptance/2",
        "status": "UNVERIFIED",
        "run_id": run.name,
        "map": {
            "path": str(map_path),
            "file_sha256": artifact_hashes["map"],
            "logical_map_sha256": reconstruction.get("map_digest") or reconstruction.get("canonical_provenance_map_digest"),
        },
        "matrix": {
            "path": str(matrix_path),
            "markdown_path": str(markdown_path),
            "file_sha256": artifact_hashes["matrix"],
            "markdown_file_sha256": artifact_hashes["matrix_markdown"],
            "decision_count": matrix.get("decision_count"),
            "status_counts": matrix.get("status_counts"),
        },
        "production_localization_audit": {
            "path": str(production_audit_path),
            "file_sha256": artifact_hashes["production_localization_audit"],
            "decision_count": production_audit.get("decision_count"),
            "status_counts": production_audit.get("status_counts"),
            "difference_count": production_audit.get("difference_count"),
            "catalog_verified": production_audit.get("catalog_verified"),
            "map_digest_verified": production_audit.get("map_digest_verified"),
        },
        "artifact_hashes": artifact_hashes,
        "implementation_source_sha256": _implementation_source_hashes(),
        "baseline_verification": baseline_result,
        "input_proof": {
            "source_sha256": reconstruction.get("history_reconstruction", {}).get("source_doc_sha256"),
            "parsed_sha256": reconstruction.get("history_reconstruction", {}).get("parsed_doc_sha256"),
            "canonical_source_sha256": reconstruction.get("history_reconstruction", {}).get("canonical_source_sha256"),
            "original_map_sha256": reconstruction.get("history_reconstruction", {}).get("original_map_sha256"),
            "stream_exact": reconstruction.get("history_reconstruction", {}).get("stream_exact"),
            "lineage_integrity_ok": reconstruction.get("history_reconstruction", {}).get("lineage_integrity_ok"),
        },
        "unverified": [
            "formal worker/container rescore wiring is outside this CLI",
            "acceptance decision requires independent root review",
        ],
    }
    write_derived_json(run, output / args.acceptance_name, acceptance)
    print(json.dumps({
        "status": acceptance["status"],
        "map": str(map_path),
        "matrix": str(matrix_path),
        "production_audit": str(production_audit_path),
        "decisions": matrix.get("decision_count"),
        "status_counts": matrix.get("status_counts"),
        "production_status_counts": production_audit.get("status_counts"),
        "production_difference_count": production_audit.get("difference_count"),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
