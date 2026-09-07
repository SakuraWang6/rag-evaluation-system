"""Immutable experiment specification store."""

from __future__ import annotations

from pathlib import Path

from rag_eval.contracts.run import ExperimentSpec
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.runs import safe_id


class ExperimentStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, experiment: ExperimentSpec) -> Path:
        path = self.root / f"{safe_id(experiment.experiment_id)}.json"
        if path.exists():
            existing = self.get(experiment.experiment_id)
            if existing != experiment:
                raise ValueError("experiment ID already exists with different content")
            return path
        atomic_write_json(path, experiment.model_dump(mode="json"))
        return path

    def get(self, experiment_id: str) -> ExperimentSpec:
        path = self.root / f"{safe_id(experiment_id)}.json"
        return ExperimentSpec.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[ExperimentSpec]:
        return [
            ExperimentSpec.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.root.glob("*.json"))
        ]
