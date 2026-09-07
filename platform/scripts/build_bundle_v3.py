#!/usr/bin/env python3
"""Materialize an immutable Bundle 3.0 from one frozen Dataset Release.

This is deliberately a one-way delivery command: it only reads formal release
snapshots and Authoring/Portfolio records, then writes a content-addressed
Bundle 3.0 and, optionally, its isolated runtime view.  It cannot import or
modify Canonical, Ledger, Gold, Release, or Bundle 2.0 data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-home", required=True, type=Path)
    parser.add_argument("--release-id", required=True)
    parser.add_argument(
        "--export-runtime",
        action="store_true",
        help="also create the separately content-addressed runtime-only view",
    )
    arguments = parser.parse_args()

    platform = PlatformService(PlatformPaths(arguments.platform_home), product_enabled=True)
    if platform.bundles_v3 is None:
        raise RuntimeError("Bundle 3.0 needs the enabled Authoring, Release, and Portfolio services")

    bundle = platform.bundles_v3.build_from_release(arguments.release_id)
    result: dict[str, object] = {
        "bundle_id": bundle.bundle_id,
        "bundle_root": str(bundle.root),
        "target_release_id": bundle.manifest.target_release_id,
        "release_chain": [item.release_id for item in bundle.manifest.release_chain],
        "case_count": bundle.manifest.case_count,
        "gold_count": bundle.manifest.gold_count,
        "evidence_count": bundle.manifest.evidence_count,
    }
    if arguments.export_runtime:
        runtime = platform.bundles_v3.export_runtime_view(
            bundle.bundle_id,
            platform.paths.dataset_bundles_v3_runtime,
        )
        result["runtime_bundle_id"] = runtime.runtime_bundle_id
        result["runtime_root"] = str(runtime.root)
        result["runtime_question_count"] = len(runtime.questions)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
