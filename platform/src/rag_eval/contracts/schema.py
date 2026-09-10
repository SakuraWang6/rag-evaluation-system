"""JSON Schema export for the Native v2 public contract surface."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from rag_eval.contracts.benchmark import (
    BenchmarkCaseV2,
    BenchmarkEvidenceV2,
    BenchmarkGoldV2,
    BenchmarkSourceIdentityV2,
    NativeBenchmarkReleaseV2,
)
from rag_eval.contracts.canonical import CanonicalConformanceReport, CanonicalDocument
from rag_eval.contracts.native import (
    IngestionReceiptV2,
    NativeHealthReportV2,
    NativeQueryV2,
    OriginalDocumentV2,
    PreparedSystemV2,
    ResolvedAdapterConfigV2,
)
from rag_eval.contracts.observation import (
    AdapterCapabilitiesV2,
    AdapterRunResultV2,
    UnifiedTrace,
)
from rag_eval.contracts.research import (
    AnalysisContract,
    BlindProtocol,
    ComparisonSpec,
    LatencyProtocol,
    ModelArtifactIdentity,
    ModelLock,
)
from rag_eval.contracts.run import ExperimentSpec
from rag_eval.contracts.wire import (
    WireRequestV2,
    WireResponseV2,
    WorkerHealthV2,
    WorkerIdentityV2,
)
from rag_eval.runs.models import (
    ArtifactCaseIndexV2,
    RunArtifactCaseV2,
    RunArtifactManifestV2,
    RunArtifactSummaryV2,
)
from rag_eval.runs.records import RunRecordV2
from rag_eval.runs.plans import ResolvedRunPlanV2
from rag_eval.runs.views import (
    RunArtifactCaseCollectionView,
    RunArtifactCaseIndexView,
    RunArtifactCaseView,
    RunArtifactOverviewView,
    RunRecordViewV2,
)

PUBLIC_MODELS: dict[str, type[BaseModel]] = {
    "canonical-document": CanonicalDocument,
    "canonical-conformance": CanonicalConformanceReport,
    "benchmark-source-identity-v2": BenchmarkSourceIdentityV2,
    "benchmark-evidence-v2": BenchmarkEvidenceV2,
    "benchmark-gold-v2": BenchmarkGoldV2,
    "benchmark-case-v2": BenchmarkCaseV2,
    "native-benchmark-release-v2": NativeBenchmarkReleaseV2,
    "adapter-capabilities-v2": AdapterCapabilitiesV2,
    "unified-trace-v2": UnifiedTrace,
    "adapter-run-result-v2": AdapterRunResultV2,
    "original-document-v2": OriginalDocumentV2,
    "resolved-adapter-config-v2": ResolvedAdapterConfigV2,
    "ingestion-receipt-v2": IngestionReceiptV2,
    "prepared-system-v2": PreparedSystemV2,
    "native-query-v2": NativeQueryV2,
    "native-health-report-v2": NativeHealthReportV2,
    "experiment-spec": ExperimentSpec,
    "resolved-run-plan-v2": ResolvedRunPlanV2,
    "run-artifact-v2": RunArtifactManifestV2,
    "run-artifact-case-v2": RunArtifactCaseV2,
    "run-artifact-summary-v2": RunArtifactSummaryV2,
    "run-artifact-case-index-v2": ArtifactCaseIndexV2,
    "run-record-v2": RunRecordV2,
    "run-record-view-v2": RunRecordViewV2,
    "run-artifact-overview-view-v2": RunArtifactOverviewView,
    "run-artifact-case-index-view-v2": RunArtifactCaseIndexView,
    "run-artifact-case-view-v2": RunArtifactCaseView,
    "run-artifact-case-collection-view-v2": RunArtifactCaseCollectionView,
    "comparison-spec": ComparisonSpec,
    "analysis-contract": AnalysisContract,
    "blind-protocol": BlindProtocol,
    "model-artifact-identity": ModelArtifactIdentity,
    "model-lock": ModelLock,
    "latency-protocol": LatencyProtocol,
    "worker-identity-v2": WorkerIdentityV2,
    "worker-health-v2": WorkerHealthV2,
    "wire-request-v2": WireRequestV2,
    "wire-response-v2": WireResponseV2,
}


def export_json_schemas(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, model in PUBLIC_MODELS.items():
        path = output_dir / f"{name}.schema.json"
        path.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return paths
