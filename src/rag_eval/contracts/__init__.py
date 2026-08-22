"""Versioned public contracts shared by the platform and adapter workers."""

from rag_eval.contracts.adapter import (
    AdapterCapabilities,
    DocumentInput,
    HealthReport,
    IngestionResult,
    PrepareContext,
    PreparedSystem,
    RAGAdapter,
    RAGEvidenceItem,
    RAGQuery,
    RAGResult,
    ResetResult,
)
from rag_eval.contracts.dataset import (
    DatasetBundleManifest,
    DocumentManifest,
    GoldAnswer,
    GoldAnswerKind,
    GoldEvidence,
    GoldEvidenceSet,
    ObjectLocator,
    PageRegionLocator,
    Question,
    TableCellLocator,
    TextSpanLocator,
)
from rag_eval.contracts.run import (
    CaseResult,
    ComparisonTier,
    ExperimentSpec,
    MetricResult,
    MetricStatus,
    RunManifest,
    RunStatus,
)
from rag_eval.contracts.wire import (
    HandshakeResponse,
    WireError,
    WireRequest,
    WireResponse,
)

PROTOCOL_VERSION = "0.1"
SCHEMA_VERSION = 2
PRODUCER = "rag_eval_platform"

__all__ = [
    "PRODUCER",
    "PROTOCOL_VERSION",
    "SCHEMA_VERSION",
    "AdapterCapabilities",
    "CaseResult",
    "ComparisonTier",
    "DatasetBundleManifest",
    "DocumentInput",
    "DocumentManifest",
    "ExperimentSpec",
    "GoldAnswer",
    "GoldAnswerKind",
    "GoldEvidence",
    "GoldEvidenceSet",
    "HandshakeResponse",
    "HealthReport",
    "IngestionResult",
    "MetricResult",
    "MetricStatus",
    "ObjectLocator",
    "PageRegionLocator",
    "PrepareContext",
    "PreparedSystem",
    "Question",
    "RAGAdapter",
    "RAGEvidenceItem",
    "RAGQuery",
    "RAGResult",
    "ResetResult",
    "RunManifest",
    "RunStatus",
    "TableCellLocator",
    "TextSpanLocator",
    "WireError",
    "WireRequest",
    "WireResponse",
]
