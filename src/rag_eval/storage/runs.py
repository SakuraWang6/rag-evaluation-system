"""Schema-v2-only run artifact store."""

from __future__ import annotations

import logging
from pathlib import Path

from rag_eval.contracts.run import CaseResult, ExperimentSpec, RunManifest
from rag_eval.storage.atomic import atomic_write_json

logger = logging.getLogger(__name__)


class RunStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def create(
        self, manifest: RunManifest, experiment: ExperimentSpec
    ) -> Path:
        run_dir = self.root / safe_id(manifest.run_id)
        try:
            run_dir.mkdir(parents=False)
        except FileExistsError as exc:
            raise ValueError(f"run already exists: {manifest.run_id}") from exc
        (run_dir / "cases").mkdir()
        (run_dir / "worker").mkdir()
        (run_dir / "source").mkdir()
        atomic_write_json(
            run_dir / "experiment.json", experiment.model_dump(mode="json")
        )
        self.write_manifest(manifest)
        return run_dir

    def write_manifest(self, manifest: RunManifest) -> None:
        atomic_write_json(
            self.root / safe_id(manifest.run_id) / "run.json",
            manifest.model_dump(mode="json"),
        )

    def write_case(self, run_id: str, result: CaseResult) -> Path:
        path = self.root / safe_id(run_id) / "cases" / f"{safe_id(result.case_id)}.json"
        atomic_write_json(path, result.model_dump(mode="json"))
        return path

    def get(self, run_id: str) -> RunManifest:
        path = self.root / safe_id(run_id) / "run.json"
        manifest = RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
        if manifest.schema_version != 2 or manifest.producer != "rag_eval_platform":
            raise ValueError("run is not a schema-v2 platform run")
        return manifest

    def cases(self, run_id: str) -> list[CaseResult]:
        cases_dir = self.root / safe_id(run_id) / "cases"
        return [
            CaseResult.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(cases_dir.glob("*.json"))
        ]

    def list(self) -> list[RunManifest]:
        manifests: list[RunManifest] = []
        for path in sorted(self.root.glob("*/run.json")):
            try:
                manifest = RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                logger.debug("ignoring non-platform run manifest %s: %s", path, exc)
                continue
            if manifest.schema_version == 2 and manifest.producer == "rag_eval_platform":
                manifests.append(manifest)
        return manifests


def safe_id(value: str) -> str:
    if not value or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in value):
        raise ValueError(f"unsafe identifier: {value!r}")
    return value
