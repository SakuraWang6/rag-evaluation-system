#!/usr/bin/env python3
"""Run the sealed Bundle 3.0 → LightRAG → private-evaluation rehearsal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_eval.e2e_rehearsal import render_rehearsal_report, run_rehearsal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-bundle-root", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--worker-python", required=True)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_rehearsal(
        private_bundle_root=args.private_bundle_root,
        runtime_root=args.runtime_root,
        output_root=args.output_root,
        worker_python=args.worker_python,
    )
    args.report.write_text(render_rehearsal_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
