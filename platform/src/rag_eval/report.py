"""Human-readable report generation from immutable run artifacts."""

from __future__ import annotations

import json

from rag_eval.contracts.run import CaseResult, RunManifest
from rag_eval.runs.artifacts import ArtifactV2Reader


def markdown_report(
    manifest: RunManifest,
    cases: list[CaseResult],
    summary: dict[str, object],
) -> str:
    lines = [
        f"# RAG Evaluation Run {manifest.run_id}",
        "",
        f"- Status: `{manifest.status}`",
        f"- Dataset bundle: `{manifest.bundle_id}`",
        f"- Adapter: `{manifest.adapter_id}` `{manifest.adapter_version}`",
        f"- System: `{manifest.system_id}` `{manifest.system_version}`",
        f"- Case selection: `{manifest.case_selection_id}`",
        f"- Repetitions: `{manifest.repetitions}`",
        f"- Repetition seeds: `{manifest.repetition_seeds}`",
        f"- Replay of: `{manifest.replay_of_run_id}`",
        "",
        "## Metrics",
        "",
        "```json",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Cases",
    ]
    for case in cases:
        lines.extend(
            [
                "",
                f"### {case.case_id} · repetition {case.repetition}",
                "",
                f"- Status: `{case.status}`",
                f"- Question: {case.question}",
                f"- Gold answer: `{case.gold_answer.canonical if case.gold_answer else None}`",
                f"- Generated answer: `{case.rag_result.answer if case.rag_result else None}`",
                f"- Failure reason: `{case.error.message if case.error else None}`",
                "",
                "#### Failure Assessment",
                "",
                "```json",
                json.dumps(
                    case.failure_assessment.model_dump(mode="json")
                    if case.failure_assessment
                    else None,
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
                "#### Gold Evidence",
                "",
                "```json",
                json.dumps(
                    case.gold_evidence_set.model_dump(mode="json")
                    if case.gold_evidence_set
                    else None,
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
            ]
        )
        for title, items in (
            (
                "Raw Retrieved Evidence",
                case.rag_result.raw_retrieval if case.rag_result else None,
            ),
            (
                "Ranked Evidence",
                case.rag_result.ranked_retrieval if case.rag_result else None,
            ),
            (
                "Final Context",
                case.rag_result.final_context if case.rag_result else None,
            ),
        ):
            lines.extend(
                [
                    "",
                    f"#### {title}",
                    "",
                    "```json",
                    json.dumps(
                        [item.model_dump(mode="json") for item in items]
                        if items is not None
                        else {"status": "unavailable"},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    "```",
                ]
            )
        lines.extend(
            [
                "",
                "#### Metric Breakdown",
                "",
                "```json",
                json.dumps(
                    [metric.model_dump(mode="json") for metric in case.metrics],
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
            ]
        )
    return "\n".join(lines) + "\n"


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


__all__ = ["artifact_v2_markdown_report", "markdown_report"]
