"""Composition root for the local standalone platform."""

from __future__ import annotations

from rag_eval.datasets.bundle import DatasetBundleStore
from rag_eval.execution import RunExecutor
from rag_eval.jobs import JobStore
from rag_eval.storage.experiments import ExperimentStore
from rag_eval.storage.layout import PlatformPaths
from rag_eval.storage.runs import RunStore
from rag_eval.supervisor import JobSupervisor
from rag_eval.systems import SystemRegistry


class PlatformService:
    def __init__(self, paths: PlatformPaths) -> None:
        paths.initialize()
        self.paths = paths
        self.datasets = DatasetBundleStore(paths.datasets)
        self.runs = RunStore(paths.runs)
        self.jobs = JobStore(paths.jobs)
        self.experiments = ExperimentStore(paths.experiments)
        self.systems = SystemRegistry(paths.systems)
        self.executor = RunExecutor(self.datasets, self.runs)
        self.supervisor = JobSupervisor(self.jobs, self.systems, self.executor)
