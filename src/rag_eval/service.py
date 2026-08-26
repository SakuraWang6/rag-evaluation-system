"""Composition root for the local standalone platform."""

from __future__ import annotations

import os

from rag_eval.datasets.bundle import DatasetBundleStore
from rag_eval.execution import RunExecutor
from rag_eval.jobs import JobStore
from rag_eval.storage.experiments import ExperimentStore
from rag_eval.storage.layout import PlatformPaths
from rag_eval.storage.runs import RunStore
from rag_eval.supervisor import JobSupervisor
from rag_eval.systems import SystemRegistry
from rag_eval.systems import SystemResolver
from rag_eval.products import ProductResources
from rag_eval.datasets.drafts import DatasetDraftStore
from rag_eval.secrets import DeferredSecretStore, create_secret_store
from rag_eval.execution_provider import ExecutionProviderRegistry
from rag_eval.authoring import AuthoringService


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
        self.runs = RunStore(paths.runs)
        self.jobs = JobStore(paths.jobs)
        self.experiments = ExperimentStore(paths.experiments)
        self.systems = SystemRegistry(paths.systems)
        self.providers = ExecutionProviderRegistry()
        self.executor = RunExecutor(self.datasets, self.runs)
        self.products = ProductResources(
            drafts=paths.evaluation_drafts,
            connections=paths.system_connections,
        ) if self.product_enabled else None
        self.dataset_drafts = DatasetDraftStore(paths.dataset_drafts, paths.product_uploads) if self.product_enabled else None
        self.authoring = AuthoringService(paths.authoring_datasets) if self.product_enabled else None
        self.secrets = (
            DeferredSecretStore(lambda: create_secret_store(paths.dev_secrets))
            if self.product_enabled
            else None
        )
        self.system_resolver = SystemResolver(self.systems, self.products, self.secrets)
        self.supervisor = JobSupervisor(
            self.jobs,
            self.system_resolver,
            self.executor,
            self.providers,
        )

    def standard_worker_python(self, profile_id: str, fallback: str) -> str:
        """Resolve a local standard-adapter runtime without exposing it in Basic UI."""
        environment_key = "RAG_EVAL_" + profile_id.upper().replace("-", "_") + "_WORKER_PYTHON"
        return os.environ.get(environment_key, fallback)
