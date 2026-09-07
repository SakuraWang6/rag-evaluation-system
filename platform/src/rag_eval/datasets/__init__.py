"""Immutable Dataset Bundle 2.0 loading and registration."""

from rag_eval.datasets.bundle import DatasetBundle, DatasetBundleStore
from rag_eval.datasets.bundle_v3 import (
    BundleV3IntegrityError,
    BundleV3Store,
    DatasetBundleV3,
    DatasetBundleV3Runtime,
    load_bundle_v3,
    load_bundle_v3_runtime,
)
from rag_eval.datasets.registry import DatasetRegistry, DatasetRegistryRecord
from rag_eval.datasets.formal import (
    DatasetRelease,
    DatasetReleaseStore,
    FormalReleaseContent,
    FormalDatasetReleaseService,
    FormalDatasetValidator,
    ValidationReport,
)
from rag_eval.datasets.portfolio import (
    BenchmarkPortfolio,
    BenchmarkPortfolioService,
    PortfolioCoverageReport,
)
from rag_eval.datasets.admission import (
    BenchmarkAdmissionService,
    CalibrationReferenceProcess,
    DocumentSourceRecord,
)
from rag_eval.datasets.benchmark_contract import (
    BENCHMARK_GOLD_NAME,
    BENCHMARK_MANIFEST_NAME,
    BENCHMARK_QUESTIONS_NAME,
    BENCHMARK_RUNTIME_REFERENCE_NAME,
    BENCHMARK_SEGMENTS_NAME,
    build_benchmark_dataset,
    formal_release_benchmark_contract_path,
    load_benchmark_dataset,
    materialize_benchmark_segment_documents,
    publish_benchmark_dataset,
)

__all__ = [
    "DatasetBundle",
    "DatasetBundleStore",
    "BundleV3IntegrityError",
    "BundleV3Store",
    "DatasetBundleV3",
    "DatasetBundleV3Runtime",
    "load_bundle_v3",
    "load_bundle_v3_runtime",
    "DatasetRegistry",
    "DatasetRegistryRecord",
    "DatasetRelease",
    "DatasetReleaseStore",
    "FormalReleaseContent",
    "FormalDatasetReleaseService",
    "FormalDatasetValidator",
    "ValidationReport",
    "BenchmarkPortfolio",
    "BenchmarkPortfolioService",
    "PortfolioCoverageReport",
    "BenchmarkAdmissionService",
    "CalibrationReferenceProcess",
    "DocumentSourceRecord",
    "BENCHMARK_GOLD_NAME",
    "BENCHMARK_MANIFEST_NAME",
    "BENCHMARK_QUESTIONS_NAME",
    "BENCHMARK_RUNTIME_REFERENCE_NAME",
    "BENCHMARK_SEGMENTS_NAME",
    "build_benchmark_dataset",
    "formal_release_benchmark_contract_path",
    "load_benchmark_dataset",
    "materialize_benchmark_segment_documents",
    "publish_benchmark_dataset",
]
