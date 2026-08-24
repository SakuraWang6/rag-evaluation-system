"""JSON Schema export for versioned public contracts."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from rag_eval.contracts.adapter import RAGQuery, RAGResult
from rag_eval.contracts.dataset import (
    DatasetBundleManifest,
    GoldAnswer,
    GoldEvidenceSet,
    Question,
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

PUBLIC_MODELS: dict[str, type[BaseModel]] = {
    "dataset-bundle-manifest": DatasetBundleManifest,
    "question": Question,
    "gold-answer": GoldAnswer,
    "gold-evidence-set": GoldEvidenceSet,
    "rag-query": RAGQuery,
    "rag-result": RAGResult,
    "experiment-spec": ExperimentSpec,
    "case-result": CaseResult,
    "run-manifest": RunManifest,
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
