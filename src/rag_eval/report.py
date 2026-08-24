"""Human-readable report generation from immutable run artifacts."""

from __future__ import annotations

import json

from rag_eval.contracts.run import CaseResult, RunManifest


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
