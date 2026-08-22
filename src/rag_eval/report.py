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
                f"### {case.case_id}",
                "",
                f"- Status: `{case.status}`",
                f"- Question: {case.question}",
                f"- Gold answer: `{case.gold_answer.canonical if case.gold_answer else None}`",
                f"- Generated answer: `{case.rag_result.answer if case.rag_result else None}`",
                f"- Failure reason: `{case.error.message if case.error else None}`",
            ]
        )
    return "\n".join(lines) + "\n"
