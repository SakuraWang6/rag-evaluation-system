#!/usr/bin/env python3
"""Produce an append-only, versioned production re-score of a retained run.

The command reuses the retained source/case artifacts and the externally
pinned historical provenance map.  It invokes deterministic production
``evaluate_case`` only; it never starts an adapter, an LLM, LightRAG, or a
retrieval worker, and it refuses destinations inside the retained run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT / "src"))

from rag_eval.history_provenance.rescore import (  # noqa: E402
    rescore_historical_run,
    write_historical_rescore,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--map", dest="map_path", type=Path, required=True)
    parser.add_argument("--map-acceptance", type=Path, required=True)
    parser.add_argument("--matrix", dest="matrix_path", type=Path, default=None)
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rescore-name", default="historical-rescore-v1.json")
    parser.add_argument("--markdown-name", default="historical-rescore-v1.md")
    parser.add_argument(
        "--acceptance-name", default="historical-rescore-v1-acceptance.json"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    value = rescore_historical_run(
        args.run_dir,
        args.map_path,
        map_acceptance_path=args.map_acceptance,
        matrix_path=args.matrix_path,
        baseline_path=args.baseline,
    )
    paths = write_historical_rescore(
        args.run_dir,
        args.output_dir,
        value,
        rescore_filename=args.rescore_name,
        markdown_filename=args.markdown_name,
        acceptance_filename=args.acceptance_name,
    )
    print(
        json.dumps(
            {
                "status": value["status"],
                "rescore": paths["rescore"],
                "markdown": paths["markdown"],
                "acceptance": paths["acceptance"],
                "case_count": value["case_count"],
                "after_summary": value["after_summary"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
