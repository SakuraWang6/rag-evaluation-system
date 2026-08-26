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

    @property
    def product(self) -> Path:
        """Editable product-layer state, deliberately separate from artifacts."""
        return self.home / "product"

    @property
    def dataset_drafts(self) -> Path:
        return self.product / "dataset-drafts"

    @property
    def evaluation_drafts(self) -> Path:
        return self.product / "evaluation-drafts"

    @property
    def system_connections(self) -> Path:
        return self.product / "system-connections"

    @property
    def product_uploads(self) -> Path:
        return self.product / "uploads"

    @property
    def authoring_datasets(self) -> Path:
        """Private, editable document-authoring workspaces (never Bundle storage)."""
        return self.product / "authoring" / "datasets"

    @property
    def dev_secrets(self) -> Path:
        return self.product / "dev-secrets.enc"

    def initialize(self, *, product_enabled: bool = True) -> None:
        paths = [
            self.datasets,
            self.runs,
            self.jobs,
            self.experiments,
            self.systems,
        ]
        if product_enabled:
            paths.extend(
                (
                    self.dataset_drafts,
                    self.evaluation_drafts,
                    self.system_connections,
                    self.product_uploads,
                    self.authoring_datasets,
                )
            )
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)
