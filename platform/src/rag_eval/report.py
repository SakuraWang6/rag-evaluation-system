"""Human-readable report generation from immutable run artifacts."""

from __future__ import annotations

import json

from rag_eval.runs.artifacts import ArtifactV2Reader


def artifact_v2_markdown_report(reader: ArtifactV2Reader) -> str:
    """Render a deterministic report from persisted Artifact 2.0 only."""

    verification = reader.verify()
    if not verification.valid:
        raise ValueError(
            "cannot render a report from an invalid Artifact 2.0: "
            f"{verification}"
        )
    manifest = reader.manifest()
    summary = reader.summary()
    lines = [
        f"# RAG Evaluation Run {manifest.run_id}",
        "",
        "- Artifact contract: `2.0`",
        f"- Artifact digest: `{manifest.artifact_digest}`",
        f"- Experiment: `{manifest.experiment_id}`",
        f"- Benchmark Release: `{manifest.benchmark_identity.dataset_release_id}`",
        f"- Benchmark snapshot: `{manifest.benchmark_identity.benchmark_snapshot_digest}`",
        f"- Status: `{manifest.status}`",
        "",
        "## Persisted Summary",
        "",
        "```json",
        json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Persisted Cases",
    ]
    for case in reader.cases():
        answer = (
            case.adapter_result.trace.answer.content
            if case.adapter_result is not None
            else None
        )
        lines.extend(
            [
                "",
                f"### {case.case_id} · repetition {case.repetition}",
                "",
                f"- Status: `{case.status}`",
                f"- Question: {case.question}",
                f"- Generated answer: `{answer}`",
                f"- Answer judgment: `{case.answer_judgment.status}` / `{case.answer_judgment.value}`",
                f"- Evidence judgment: `{case.evidence_judgment.status}` / `{case.evidence_judgment.value}`",
                f"- Failure attribution: `{case.evaluation.failure.kind if case.evaluation.failure else None}`",
                f"- Case digest: `{case.case_digest}`",
                "",
                "```json",
                json.dumps(
                    {
                        "trace_validation": case.trace_validation.model_dump(
                            mode="json"
                        ),
                        "metrics": [
                            metric.model_dump(mode="json")
                            for metric in case.evaluation.metrics
                        ],
                        "localizations": [
                            item.model_dump(mode="json")
                            for item in case.evaluation.localizations
                        ],
                        "pipeline_deltas": [
                            item.model_dump(mode="json")
                            for item in case.evaluation.pipeline_deltas
                        ],
                        "error": (
                            case.error.model_dump(mode="json")
                            if case.error is not None
                            else None
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
            ]
        )
    return "\n".join(lines) + "\n"


__all__ = ["artifact_v2_markdown_report"]
