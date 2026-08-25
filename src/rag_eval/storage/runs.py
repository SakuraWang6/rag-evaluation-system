"""Schema-v2-only run artifact store."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
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
        if run_dir.exists() and (run_dir / "run.json").exists():
            raise ValueError(f"run already exists: {manifest.run_id}")
        self.prepare_execution_layout(manifest.run_id)
        atomic_write_json(
            run_dir / "experiment.json", experiment.model_dump(mode="json")
        )
        self.write_manifest(manifest)
        return run_dir

    def prepare_execution_layout(self, run_id: str) -> Path:
        """Create an empty run-scoped mount layout before a Provider starts.

        This allows Docker to receive only source/work bind mounts while keeping
        normal LocalProcess behavior unchanged.  No immutable artifact is
        written until ``create`` receives a validated worker handshake.
        """
        run_dir = self.root / safe_id(run_id)
        if run_dir.exists() and (run_dir / "run.json").exists():
            raise ValueError(f"run already exists: {run_id}")
        run_dir.mkdir(parents=False, exist_ok=True)
        for name in ("cases", "worker", "source", "work"):
            (run_dir / name).mkdir(exist_ok=True)
        return run_dir

    def write_manifest(self, manifest: RunManifest) -> None:
        atomic_write_json(
            self.root / safe_id(manifest.run_id) / "run.json",
            manifest.model_dump(mode="json"),
        )

    def write_case(self, run_id: str, result: CaseResult) -> Path:
        path = (
            self.root
            / safe_id(run_id)
            / "cases"
            / f"rep-{result.repetition:04d}-{safe_id(result.case_id)}.json"
        )
        atomic_write_json(path, result.model_dump(mode="json"))
        return path

    def experiment(self, run_id: str) -> ExperimentSpec:
        path = self.root / safe_id(run_id) / "experiment.json"
        return ExperimentSpec.model_validate_json(path.read_text(encoding="utf-8"))

    def artifact_hashes(self, run_id: str) -> dict[str, str]:
        return artifact_file_hashes(self.root / safe_id(run_id))

    def verify_artifacts(self, run_id: str) -> ArtifactVerification:
        manifest = self.get(run_id)
        actual = self.artifact_hashes(run_id)
        expected = manifest.artifact_checksums
        missing = tuple(sorted(set(expected) - set(actual)))
        unexpected = tuple(sorted(set(actual) - set(expected)))
        mismatched = tuple(
            sorted(
                path
                for path in set(expected).intersection(actual)
                if expected[path] != actual[path]
            )
        )
        return ArtifactVerification(
            valid=not missing and not unexpected and not mismatched,
            missing=missing,
            unexpected=unexpected,
            mismatched=mismatched,
        )

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


@dataclass(frozen=True, slots=True)
class ArtifactVerification:
    valid: bool
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]
    mismatched: tuple[str, ...]


def artifact_file_hashes(run_dir: Path) -> dict[str, str]:
    """Hash immutable run artifacts, excluding mutable manifest and work index."""
    hashes: dict[str, str] = {}
    if not run_dir.is_dir():
        raise FileNotFoundError(run_dir)
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(run_dir).as_posix()
        if relative == "run.json" or relative.startswith("work/"):
            continue
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes
