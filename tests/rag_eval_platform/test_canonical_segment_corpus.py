"""Primary canonical corpus materialization tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rag_eval.contracts.dataset import (
    DatasetBundleManifest,
    GoldAnswer,
    GoldAnswerKind,
    GoldEvidence,
    GoldEvidenceSet,
    ObjectLocator,
    Question,
    TableCellLocator,
)
from rag_eval.datasets.bundle import DatasetBundle
from rag_eval.datasets.canonical_segments import (
    CanonicalSegmentError,
    build_canonical_segment_manifest,
    load_staged_canonical_segment_manifest,
    materialize_canonical_segment_documents,
)


DOC_ID = "doc-canonical-segments"


def _record(object_id: str, object_type: str, value: str, **extra: object) -> dict[str, object]:
    return {
        "document_id": DOC_ID,
        "object_id": object_id,
        "object_type": object_type,
        "canonical_value": value,
        "representation_status": "complete",
        "document_order": int(extra.pop("document_order", 0)),
        "provenance": {
            "source_spans": [
                {"coordinates": {"body_ordinal": 1}, "part": "word/document.xml"}
            ]
        },
        **extra,
    }


def _bundle(tmp_path: Path) -> DatasetBundle:
    root = tmp_path / "bundle"
    document_path = root / "documents" / "source.txt"
    canonical_path = root / "canonical" / "evidence.jsonl"
    document_path.parent.mkdir(parents=True)
    canonical_path.parent.mkdir(parents=True)
    document_path.write_text("presentation source", encoding="utf-8")
    table_id = f"{DOC_ID}:table:1"
    records = [
        _record(f"{DOC_ID}:paragraph:1", "paragraph", "结论仅在当前状态有效。", document_order=1),
        _record(table_id, "table", "名称 | 型号 交换机 | S2910", document_order=2),
        _record(f"{DOC_ID}:row:1", "row", "名称 | 型号", table_id=table_id, row=1, document_order=3),
        _record(f"{DOC_ID}:row:2", "row", "交换机 | S2910", table_id=table_id, row=2, document_order=4),
        _record(f"{DOC_ID}:cell:1", "cell", "名称", table_id=table_id, row=1, column=1, document_order=5),
        _record(f"{DOC_ID}:cell:2", "cell", "型号", table_id=table_id, row=1, column=2, document_order=6),
        _record(f"{DOC_ID}:cell:3", "cell", "交换机", table_id=table_id, row=2, column=1, document_order=7),
        _record(f"{DOC_ID}:cell:4", "cell", "S2910", table_id=table_id, row=2, column=2, document_order=8),
    ]
    canonical_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records),
        encoding="utf-8",
    )
    manifest = DatasetBundleManifest.model_validate(
        {
            "schema_version": 2,
            "name": "canonical-segment-fixture",
            "version": "1",
            "created_at": "2026-09-05T00:00:00Z",
            "documents": [
                {
                    "document_id": DOC_ID,
                    "path": "documents/source.txt",
                    "canonical_path": "canonical/evidence.jsonl",
                    "sha256": hashlib.sha256(document_path.read_bytes()).hexdigest(),
                    "mime_type": "text/plain",
                }
            ],
            "metadata": {"primary_evaluation_corpus": "canonical_segments"},
        }
    )
    return DatasetBundle(
        root=root,
        bundle_id="canonical-segment-fixture",
        manifest=manifest,
        questions=(
            Question(
                case_id="case-table",
                question="交换机的型号是什么？",
                gold_answer_id="answer-table",
                gold_evidence_set_id="evidence-table",
            ),
            Question(
                case_id="case-paragraph",
                question="结论什么时候有效？",
                gold_answer_id="answer-paragraph",
                gold_evidence_set_id="evidence-paragraph",
            ),
        ),
        gold_answers={
            "answer-table": GoldAnswer(
                gold_answer_id="answer-table", kind=GoldAnswerKind.TEXT, canonical="S2910"
            ),
            "answer-paragraph": GoldAnswer(
                gold_answer_id="answer-paragraph",
                kind=GoldAnswerKind.TEXT,
                canonical="当前状态",
            ),
        },
        gold_evidence_sets={
            "evidence-table": GoldEvidenceSet(
                gold_evidence_set_id="evidence-table",
                evidence=[
                    GoldEvidence(
                        evidence_id="table-cell",
                        document_id=DOC_ID,
                        locator=TableCellLocator(table_id=f"{DOC_ID}:table:1", row=2, column=2),
                        canonical_value="S2910",
                    )
                ],
                required_groups=[["table-cell"]],
            ),
            "evidence-paragraph": GoldEvidenceSet(
                gold_evidence_set_id="evidence-paragraph",
                evidence=[
                    GoldEvidence(
                        evidence_id="paragraph",
                        document_id=DOC_ID,
                        locator=ObjectLocator(
                            object_type="paragraph", object_id=f"{DOC_ID}:paragraph:1"
                        ),
                        canonical_value="当前状态",
                    )
                ],
                required_groups=[["paragraph"]],
            ),
        },
    )


def test_canonical_segments_are_stable_and_materialize_as_primary_inputs(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)

    first = build_canonical_segment_manifest(bundle, max_batch_characters=600)
    second = build_canonical_segment_manifest(bundle, max_batch_characters=600)

    assert first.manifest_digest == second.manifest_digest
    assert len(first.segments) == 3  # paragraph + two table rows
    assert len(first.batches) >= 1
    table_segment = next(
        item for item in first.segments if f"{DOC_ID}:cell:4" in {edge.object_id for edge in item.edges}
    )
    assert f"{DOC_ID}:cell:4" in {edge.object_id for edge in table_segment.edges}
    assert f"{DOC_ID}:table:1" in {
        edge.object_id for edge in table_segment.edges if edge.coverage == "partial"
    }

    inputs = materialize_canonical_segment_documents(
        bundle, tmp_path / "run" / "source", max_batch_characters=600
    )
    staged = load_staged_canonical_segment_manifest(tmp_path / "run" / "source", inputs)

    assert staged is not None
    assert staged.manifest_digest == first.manifest_digest
    assert all(item.metadata["primary_evaluation_corpus"] == "canonical_segments" for item in inputs)
    assert all(item.content and "[[CANONICAL_SEGMENT" in item.content for item in inputs)


def test_canonical_primary_rejects_gold_without_a_named_segment(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    invalid = GoldEvidence(
        evidence_id="page-only",
        document_id=DOC_ID,
        locator=ObjectLocator(object_type="paragraph", object_id="missing-object"),
        canonical_value="unavailable",
    )
    bundle = DatasetBundle(
        root=bundle.root,
        bundle_id=bundle.bundle_id,
        manifest=bundle.manifest,
        questions=bundle.questions,
        gold_answers=bundle.gold_answers,
        gold_evidence_sets={
            **bundle.gold_evidence_sets,
            "bad": GoldEvidenceSet(
                gold_evidence_set_id="bad", evidence=[invalid], required_groups=[["page-only"]]
            ),
        },
    )
    with pytest.raises(CanonicalSegmentError, match="no deterministic segment"):
        build_canonical_segment_manifest(bundle)
