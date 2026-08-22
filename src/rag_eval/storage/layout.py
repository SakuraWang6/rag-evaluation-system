"""Platform-owned storage layout with no legacy-directory discovery."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PlatformPaths:
    home: Path

    @classmethod
    def from_environment(cls) -> PlatformPaths:
        configured = os.environ.get("RAG_EVAL_HOME")
        return cls(Path(configured).expanduser() if configured else Path.home() / ".rag_eval_platform")

    @property
    def datasets(self) -> Path:
        return self.home / "datasets"

    @property
    def runs(self) -> Path:
        return self.home / "runs"

    @property
    def jobs(self) -> Path:
        return self.home / "jobs"

    @property
    def experiments(self) -> Path:
        return self.home / "experiments"

    @property
    def systems(self) -> Path:
        return self.home / "systems"

    def initialize(self) -> None:
        for path in (
            self.datasets,
            self.runs,
            self.jobs,
            self.experiments,
            self.systems,
        ):
            path.mkdir(parents=True, exist_ok=True)
