"""Runtime-facing immutable Benchmark Release services.

The offline Bundle 3 implementation remains available only through the
explicit ``rag_eval.datasets.bundle_v3`` module.  Importing the production
package must not load an offline delivery format into the runtime graph.
"""

from rag_eval.datasets.admission import (
    BenchmarkAdmissionService,
    CalibrationReferenceProcess,
    DocumentSourceRecord,
)
from rag_eval.datasets.formal import (
    DatasetRelease,
    DatasetReleaseStore,
    FormalDatasetReleaseService,
    FormalDatasetValidator,
    FormalReleaseContent,
    ValidationReport,
)
from rag_eval.datasets.portfolio import (
    BenchmarkPortfolio,
    BenchmarkPortfolioService,
    PortfolioCoverageReport,
)

__all__ = [
    "BenchmarkAdmissionService",
    "BenchmarkPortfolio",
    "BenchmarkPortfolioService",
    "CalibrationReferenceProcess",
    "DatasetRelease",
    "DatasetReleaseStore",
    "DocumentSourceRecord",
    "FormalDatasetReleaseService",
    "FormalDatasetValidator",
    "FormalReleaseContent",
    "PortfolioCoverageReport",
    "ValidationReport",
]
