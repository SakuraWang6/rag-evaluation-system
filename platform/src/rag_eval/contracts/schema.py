"""JSON Schema export for versioned public contracts."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from rag_eval.contracts.adapter import RAGQuery, RAGResult
from rag_eval.contracts.benchmark import (
    BenchmarkGold,
    BenchmarkManifest,
    BenchmarkQuestion,
    BenchmarkSegment,
)
from rag_eval.contracts.canonical import CanonicalConformanceReport, CanonicalDocument
from rag_eval.contracts.dataset import (
    DatasetBundleManifest,
    GoldAnswer,
    GoldEvidenceSet,
    Question,
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
from rag_eval.contracts.run import CaseResult, ExperimentSpec, RunManifest
from rag_eval.contracts.wire import HandshakeResponse, WireRequest, WireResponse
from rag_eval.runs.models import (
    ArtifactCaseIndexV2,
    RunArtifactCaseV2,
    RunArtifactManifestV2,
    RunArtifactSummaryV2,
)
from rag_eval.runs.records import RunRecordV2
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
    "benchmark-manifest": BenchmarkManifest,
    "benchmark-segment": BenchmarkSegment,
    "benchmark-question": BenchmarkQuestion,
    "benchmark-gold": BenchmarkGold,
    "dataset-bundle-manifest": DatasetBundleManifest,
    "question": Question,
    "gold-answer": GoldAnswer,
    "gold-evidence-set": GoldEvidenceSet,
    "rag-query": RAGQuery,
    "rag-result": RAGResult,
    "adapter-capabilities-v2": AdapterCapabilitiesV2,
    "unified-trace-v2": UnifiedTrace,
    "adapter-run-result-v2": AdapterRunResultV2,
    "experiment-spec": ExperimentSpec,
    "case-result": CaseResult,
    "run-manifest": RunManifest,
    "run-artifact-v2": RunArtifactManifestV2,
    "run-artifact-case-v2": RunArtifactCaseV2,
    "run-artifact-summary-v2": RunArtifactSummaryV2,
    "run-artifact-case-index-v2": ArtifactCaseIndexV2,
    "run-record-v2": RunRecordV2,
    "run-record-view-v2": RunRecordViewV2,
    "run-artifact-overview-view-v1": RunArtifactOverviewView,
    "run-artifact-case-index-view-v1": RunArtifactCaseIndexView,
    "run-artifact-case-view-v1": RunArtifactCaseView,
    "run-artifact-case-collection-view-v1": RunArtifactCaseCollectionView,
    "comparison-spec": ComparisonSpec,
    "analysis-contract": AnalysisContract,
    "blind-protocol": BlindProtocol,
    "model-artifact-identity": ModelArtifactIdentity,
    "model-lock": ModelLock,
    "latency-protocol": LatencyProtocol,
    "worker-handshake": HandshakeResponse,
    "wire-request": WireRequest,
    "wire-response": WireResponse,
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
