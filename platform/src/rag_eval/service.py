"""Composition root for the local standalone platform."""

from __future__ import annotations

import os

from rag_eval.datasets.bundle import DatasetBundleStore
from rag_eval.datasets.bundle_v3 import BundleV3Store
from rag_eval.datasets.registry import DatasetRegistry
from rag_eval.execution import RunExecutor
from rag_eval.jobs import JobStore
from rag_eval.storage.experiments import ExperimentStore
from rag_eval.storage.layout import PlatformPaths
from rag_eval.storage.runs import RunStore
from rag_eval.supervisor import JobSupervisor
from rag_eval.systems import SystemRegistry
from rag_eval.systems import SystemResolver
from rag_eval.products import ProductResources, SystemConnection
from rag_eval.datasets.drafts import DatasetDraftStore
from rag_eval.secrets import DeferredSecretStore, create_secret_store
from rag_eval.execution_provider import ExecutionProviderRegistry
from rag_eval.authoring import AuthoringService
from rag_eval.datasets.formal import FormalDatasetReleaseService
from rag_eval.datasets.portfolio import BenchmarkPortfolioService
from rag_eval.datasets.admission import BenchmarkAdmissionService
from rag_eval.run_history import RunHistory
from rag_eval.run_presentations import RunPresentationStore
from rag_eval.llm import LLMConfigurationService
from rag_eval.reviews import (
    AnswerSupportReviewStore,
    CaseReviewStore,
    SemanticAnswerReviewer,
    SemanticAnswerSupportReviewer,
    SemanticReviewCoordinator,
)


class PlatformService:
    def __init__(self, paths: PlatformPaths, *, product_enabled: bool | None = None) -> None:
        self.product_enabled = (
            os.environ.get("RAG_EVAL_PRODUCT_LAYER_ENABLED", "1") != "0"
            if product_enabled is None
            else product_enabled
        )
        paths.initialize(product_enabled=self.product_enabled)
        self.paths = paths
        self.datasets = DatasetBundleStore(paths.datasets)
        self.dataset_registry = DatasetRegistry(paths.dataset_registry)
        self.dataset_registry.bootstrap_reference_datasets()
        self.runs = RunStore(paths.runs)
        self.case_reviews = CaseReviewStore(paths.case_reviews) if self.product_enabled else None
        self.answer_support_reviews = (
            AnswerSupportReviewStore(paths.answer_support_reviews)
            if self.product_enabled
            else None
        )
        self.run_presentations = (
            RunPresentationStore(paths.run_presentations)
            if self.product_enabled
            else None
        )
        self.jobs = JobStore(paths.jobs)
        self.experiments = ExperimentStore(paths.experiments)
        self.systems = SystemRegistry(paths.systems)
        self.providers = ExecutionProviderRegistry()
        self.llm = LLMConfigurationService(paths.llm_configuration) if self.product_enabled else None
        self.semantic_reviewer = (
            SemanticAnswerReviewer(self.case_reviews, self.llm)
            if self.case_reviews is not None
            else None
        )
        self.semantic_support_reviewer = (
            SemanticAnswerSupportReviewer(self.answer_support_reviews, self.llm)
            if self.answer_support_reviews is not None
            else None
        )
        self.secrets = (
            DeferredSecretStore(lambda: create_secret_store(paths.dev_secrets))
            if self.product_enabled
            else None
        )
        self.products = ProductResources(
            drafts=paths.evaluation_drafts,
            connections=paths.system_connections,
        ) if self.product_enabled else None
        if self.products is not None and os.environ.get("RAG_EVAL_BOOTSTRAP_LOCAL_SYSTEM") == "1":
            self._bootstrap_local_system()
        self.dataset_drafts = DatasetDraftStore(paths.dataset_drafts, paths.product_uploads) if self.product_enabled else None
        self.authoring = (
            AuthoringService(
                paths.authoring_datasets,
                llm_configuration=self.llm,
                secret_store=self.secrets,
            )
            if self.product_enabled
            else None
        )
        self.formal_datasets = (
            FormalDatasetReleaseService(
                authoring_store=self.authoring.store,
                release_root=paths.formal_dataset_releases,
            )
            if self.authoring is not None
            else None
        )
        self.portfolios = (
            BenchmarkPortfolioService(
                paths.benchmark_portfolios,
                source_root=BenchmarkPortfolioService.default_source_root(),
                ledger=self.formal_datasets.ledger,
                releases=self.formal_datasets.releases,
            )
            if self.formal_datasets is not None
            else None
        )
        if self.portfolios is not None:
            # The checked-in Blueprint source is imported as an immutable planning
            # contract.  This never writes to the source CSV/Markdown nor creates
            # an Authoring Case/Gold or a Dataset Bundle.
            self.portfolios.bootstrap_v0_dry_run()
            self.portfolios.bootstrap_v0_held_out()
        self.bundles_v3 = (
            BundleV3Store(
                paths.dataset_bundles_v3,
                releases=self.formal_datasets.releases,
                authoring_store=self.authoring.store,
                portfolios=self.portfolios.store,
            )
            if self.authoring is not None and self.formal_datasets is not None and self.portfolios is not None
            else None
        )
        self.run_history = RunHistory(
            self.runs,
            reviews=self.case_reviews,
            answer_support_reviews=self.answer_support_reviews,
            presentations=self.run_presentations,
            dataset_store=self.datasets,
            dataset_releases=(
                self.formal_datasets.releases
                if self.formal_datasets is not None
                else None
            ),
            authoring_store=(
                self.authoring.store if self.authoring is not None else None
            ),
            historical_rescores_root=(
                paths.historical_rescores if self.product_enabled else None
            ),
        )
        self.benchmark_admission = (
            BenchmarkAdmissionService(paths.benchmark_admission, portfolios=self.portfolios)
            if self.portfolios is not None
            else None
        )
        if self.benchmark_admission is not None:
            self.benchmark_admission.bootstrap()
        self.executor = RunExecutor(
            self.datasets,
            self.runs,
            dataset_release_store=(
                self.formal_datasets.releases if self.formal_datasets is not None else None
            ),
        )
        self.semantic_review_coordinator = (
            SemanticReviewCoordinator(self.semantic_reviewer, self.runs.cases)
            if self.semantic_reviewer is not None
            else None
        )
        self.semantic_support_review_coordinator = (
            SemanticReviewCoordinator(self.semantic_support_reviewer, self.runs.cases)
            if self.semantic_support_reviewer is not None
            else None
        )
        self.system_resolver = SystemResolver(self.systems, self.products, self.secrets)
        self.supervisor = JobSupervisor(
            self.jobs,
            self.system_resolver,
            self.executor,
            self.providers,
            on_run_completed=(
                self._schedule_post_run_reviews
                if self.semantic_review_coordinator is not None
                or self.semantic_support_review_coordinator is not None
                else None
            ),
        )

    def _schedule_post_run_reviews(self, run_id: str) -> None:
        """Start independent answer-equivalence and answer-support proposals."""

        if self.semantic_review_coordinator is not None:
            self.semantic_review_coordinator.schedule(run_id)
        if self.semantic_support_review_coordinator is not None:
            self.semantic_support_review_coordinator.schedule(run_id)

    def standard_worker_python(self, profile_id: str, fallback: str) -> str:
        """Resolve a local standard-adapter runtime without exposing it in Basic UI."""
        environment_key = "RAG_EVAL_" + profile_id.upper().replace("-", "_") + "_WORKER_PYTHON"
        return os.environ.get(environment_key, fallback)

    def _bootstrap_local_system(self) -> None:
        """Create the local LightRAG connection once for the bundled launcher.

        This is configuration only: no Worker is launched during Platform
        startup.  The regular supervisor owns each Worker for one queued run
        and persists the resulting run through the normal RunStore.
        """
        assert self.products is not None
        try:
            self.products.get_connection("lightrag")
            return
        except FileNotFoundError:
            pass
        profile = self.products.profiles.get("lightrag", "1.0.1")
        self.products.save_connection(
            SystemConnection(
                system_id=profile.system_id,
                display_name="LightRAG (local)",
                profile_id=profile.profile_id,
                profile_version=profile.profile_version,
                execution_provider="local",
                logical_endpoint_ref="ollama.local",
                python_executable=self.standard_worker_python(profile.profile_id, os.sys.executable),
                request_timeout_seconds=600.0,
            )
        )
