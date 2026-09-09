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
    def dataset_registry(self) -> Path:
        """External immutable Dataset classification records, never Bundle files."""
        return self.home / "dataset-registry"

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
    def resolved_run_plans(self) -> Path:
        return self.home / "resolved-run-plans"

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
    def formal_dataset_releases(self) -> Path:
        """Platform-wide immutable formal Dataset Release and validation artifacts."""
        return self.product / "formal-dataset-releases"

    @property
    def dataset_bundles_v3(self) -> Path:
        """Private, content-addressed Bundle 3.0 evaluation packages."""
        return self.product / "dataset-bundles-v3"

    @property
    def dataset_bundles_v3_runtime(self) -> Path:
        """Public runtime-only exports; this tree never contains Gold data."""
        return self.product / "dataset-bundles-v3-runtime"

    @property
    def benchmark_portfolios(self) -> Path:
        """Typed Blueprint Portfolio contracts and their append-only slot links."""
        return self.product / "benchmark-portfolios"

    @property
    def benchmark_admission(self) -> Path:
        """Versioned source/case admission policy records and calibration locks."""
        return self.product / "benchmark-admission"

    @property
    def llm_configuration(self) -> Path:
        """Editable, versioned model-provider and stage-binding configuration."""
        return self.product / "llm-configuration"

    @property
    def case_reviews(self) -> Path:
        """Append-only human/LLM adjudications, never run artifacts."""
        return self.product / "case-reviews"

    @property
    def answer_support_reviews(self) -> Path:
        """Append-only answer-support adjudications, separate from correctness."""
        return self.product / "answer-support-reviews"

    @property
    def run_presentations(self) -> Path:
        """Append-only UI labels for Runs; never a Run artifact directory."""
        return self.product / "run-presentations"

    @property
    def historical_rescores(self) -> Path:
        """Read-only projections derived from immutable historical Runs.

        These files live outside ``runs/`` so publishing a repaired
        provenance/re-score can never overwrite the original research record.
        """
        return self.product / "historical-rescores"

    @property
    def dev_secrets(self) -> Path:
        return self.product / "dev-secrets.enc"

    def initialize(self, *, product_enabled: bool = True) -> None:
        paths = [
            self.datasets,
            self.dataset_registry,
            self.runs,
            self.jobs,
            self.experiments,
            self.resolved_run_plans,
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
                    self.formal_dataset_releases,
                    self.dataset_bundles_v3,
                    self.dataset_bundles_v3_runtime,
                    self.benchmark_portfolios,
                    self.benchmark_admission,
                    self.llm_configuration,
                    self.case_reviews,
                    self.answer_support_reviews,
                    self.run_presentations,
                    self.historical_rescores,
                )
            )
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)
