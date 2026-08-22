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
    ReproducibilityRecord,
    RunManifest,
    RunStatus,
)
from rag_eval.contracts.wire import (
    HandshakeResponse,
    WireError,
    WireRequest,
    WireResponse,
)

CONTRACT_VERSION = "1.0"
PROTOCOL_VERSION = "1.0"
SCHEMA_VERSION = 2
PRODUCER = "rag_eval_platform"

__all__ = [
    "CONTRACT_VERSION",
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
    "ReproducibilityRecord",
    "ResetResult",
    "RunManifest",
    "RunStatus",
    "TableCellLocator",
    "TextSpanLocator",
    "WireError",
    "WireRequest",
    "WireResponse",
]
