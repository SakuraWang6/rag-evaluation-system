from __future__ import annotations

import hashlib
import json
from pathlib import Path


def write_bundle(root: Path) -> None:
    """Write the minimal Bundle v2 fixture shared by Adapter integrations."""
    document = root / "documents" / "doc-1.txt"
    document.parent.mkdir(parents=True)
    document.write_text("The controlled latency is 42 ms.", encoding="utf-8")
    digest = hashlib.sha256(document.read_bytes()).hexdigest()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "name": "controlled",
                "version": "1",
                "created_at": "2026-08-23T00:00:00Z",
                "documents": [
                    {
                        "document_id": "doc-1",
                        "path": "documents/doc-1.txt",
                        "sha256": digest,
                        "mime_type": "text/plain",
                        "metadata": {},
                    }
                ],
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    (root / "questions.jsonl").write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "question": "What is the controlled latency?",
                "gold_answer_id": "answer-1",
                "gold_evidence_set_id": "evidence-set-1",
                "tags": [],
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "gold_answers.jsonl").write_text(
        json.dumps(
            {
                "gold_answer_id": "answer-1",
                "kind": "numeric",
                "canonical": "42",
                "accepted_values": [],
                "unit": "ms",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "gold_evidence.jsonl").write_text(
        json.dumps(
            {
                "gold_evidence_set_id": "evidence-set-1",
                "evidence": [
                    {
                        "evidence_id": "evidence-1",
                        "document_id": "doc-1",
                        "locator": {"type": "text_span", "start": 0, "end": 32},
                        "canonical_value": "42 ms",
                        "quote_anchor": "The controlled latency is 42 ms.",
                    }
                ],
                "required_groups": [["evidence-1"]],
            }
        )
        + "\n",
        encoding="utf-8",
    )

