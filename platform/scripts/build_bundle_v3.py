#!/usr/bin/env python3
"""Materialize an immutable Bundle 3.0 from one frozen Dataset Release.

This is deliberately a one-way offline delivery command: it only reads formal
release snapshots and Authoring/Portfolio records, then writes a private,
content-addressed Bundle 3.0.  It cannot serve as a runtime evaluation input.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_eval.datasets.bundle_v3 import BundleV3Store
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-home", required=True, type=Path)
    parser.add_argument("--release-id", required=True)
    arguments = parser.parse_args()

    platform = PlatformService(PlatformPaths(arguments.platform_home), product_enabled=True)
    if platform.authoring is None or platform.formal_datasets is None or platform.portfolios is None:
        raise RuntimeError("Bundle 3.0 needs the enabled Authoring, Release, and Portfolio services")

    store = BundleV3Store(
        platform.paths.dataset_bundles_v3,
        releases=platform.formal_datasets.releases,
        authoring_store=platform.authoring.store,
        portfolios=platform.portfolios.store,
    )
    bundle = store.build_from_release(arguments.release_id)
    result: dict[str, object] = {
        "bundle_id": bundle.bundle_id,
        "bundle_root": str(bundle.root),
        "target_release_id": bundle.manifest.target_release_id,
        "release_chain": [item.release_id for item in bundle.manifest.release_chain],
        "case_count": bundle.manifest.case_count,
        "gold_count": bundle.manifest.gold_count,
        "evidence_count": bundle.manifest.evidence_count,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
