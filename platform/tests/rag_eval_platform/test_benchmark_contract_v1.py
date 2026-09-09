"""Regression coverage for the immutable segment-native benchmark package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rag_eval.contracts.benchmark import (
    MAX_ENVELOPED_SEGMENT_CHARACTERS,
    BenchmarkContractError,
    render_benchmark_segment,
)
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
from rag_eval.datasets.benchmark_contract import (
    build_benchmark_dataset,
    load_benchmark_dataset,
    publish_benchmark_dataset,
)
from rag_eval.datasets.bundle import DatasetBundle


DOCUMENT_ID = "doc-benchmark-contract"


def _record(object_id: str, object_type: str, value: str, **extra: object) -> dict[str, object]:
    return {
        "document_id": DOCUMENT_ID,
        "object_id": object_id,
        "object_type": object_type,
        "canonical_value": value,
        "document_order": extra.pop("document_order", 0),
        "provenance": {
            "source_spans": [
                {
                    "coordinate_system": "ooxml-structural-v1",
                    "coordinates": {"ordinal": 1},
                }
            ]
        },
        **extra,
    }


def _bundle(tmp_path: Path) -> DatasetBundle:
    root = tmp_path / "bundle"
    document = root / "documents" / "source.txt"
    canonical = root / "canonical" / "evidence.jsonl"
    document.parent.mkdir(parents=True)
    canonical.parent.mkdir(parents=True)
    document.write_text("presentation-only source", encoding="utf-8")
    table_id = f"{DOCUMENT_ID}:table:1"
    long_value = "可验证的超长段落。" * 320
    records = [
        _record(f"{DOCUMENT_ID}:paragraph:1", "paragraph", "结论只在当前状态有效。", document_order=1),
        _record(f"{DOCUMENT_ID}:paragraph:2", "paragraph", long_value, document_order=2),
        _record(table_id, "table", "类别 | 重要程度 A | 关键", document_order=3),
        _record(f"{DOCUMENT_ID}:row:1", "row", "类别 | 重要程度", table_id=table_id, row=1, document_order=4),
        _record(f"{DOCUMENT_ID}:row:2", "row", "A | 关键", table_id=table_id, row=2, document_order=5),
        _record(f"{DOCUMENT_ID}:cell:1", "cell", "类别", table_id=table_id, row=1, column=1, document_order=6),
        _record(f"{DOCUMENT_ID}:cell:2", "cell", "重要程度", table_id=table_id, row=1, column=2, document_order=7),
        _record(f"{DOCUMENT_ID}:cell:3", "cell", "A", table_id=table_id, row=2, column=1, document_order=8),
        _record(f"{DOCUMENT_ID}:cell:4", "cell", "关键", table_id=table_id, row=2, column=2, document_order=9),
    ]
    canonical.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records),
        encoding="utf-8",
    )
    manifest = DatasetBundleManifest.model_validate(
        {
            "schema_version": 2,
            "name": "benchmark-contract-fixture",
            "version": "1.0",
            "created_at": "2026-09-06T00:00:00Z",
            "documents": [
                {
                    "document_id": DOCUMENT_ID,
                    "path": "documents/source.txt",
                    "canonical_path": "canonical/evidence.jsonl",
                    "sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
                    "mime_type": "text/plain",
                }
            ],
        }
    )
    paragraph_id = f"{DOCUMENT_ID}:paragraph:1"
    cell_id = f"{DOCUMENT_ID}:cell:4"
    return DatasetBundle(
        root=root,
        bundle_id="benchmark-contract-fixture",
        manifest=manifest,
        questions=(
            Question(
                case_id="case-paragraph",
                question="结论何时有效？",
                gold_answer_id="answer-paragraph",
                gold_evidence_set_id="evidence-paragraph",
            ),
            Question(
                case_id="case-cell",
                question="A 的重要程度是什么？",
                gold_answer_id="answer-cell",
                gold_evidence_set_id="evidence-cell",
            ),
            Question(
                case_id="case-multi",
                question="结合结论和表格，给出结论和重要程度。",
                gold_answer_id="answer-multi",
                gold_evidence_set_id="evidence-multi",
            ),
            Question(
                case_id="case-table",
                question="表格完整内容是什么？",
                gold_answer_id="answer-table",
                gold_evidence_set_id="evidence-table",
            ),
        ),
        gold_answers={
            "answer-paragraph": GoldAnswer(gold_answer_id="answer-paragraph", kind=GoldAnswerKind.TEXT, canonical="当前状态"),
            "answer-cell": GoldAnswer(gold_answer_id="answer-cell", kind=GoldAnswerKind.TEXT, canonical="关键"),
            "answer-multi": GoldAnswer(gold_answer_id="answer-multi", kind=GoldAnswerKind.TEXT, canonical="当前状态和关键"),
            "answer-table": GoldAnswer(gold_answer_id="answer-table", kind=GoldAnswerKind.TEXT, canonical="A"),
        },
        gold_evidence_sets={
            "evidence-paragraph": GoldEvidenceSet(
                gold_evidence_set_id="evidence-paragraph",
                evidence=[GoldEvidence(evidence_id="paragraph", document_id=DOCUMENT_ID, locator=ObjectLocator(object_type="paragraph", object_id=paragraph_id), canonical_value="当前状态")],
                required_groups=[["paragraph"]],
            ),
            "evidence-cell": GoldEvidenceSet(
                gold_evidence_set_id="evidence-cell",
                evidence=[GoldEvidence(evidence_id="cell", document_id=DOCUMENT_ID, locator=TableCellLocator(table_id=table_id, row=2, column=2), canonical_value="关键")],
                required_groups=[["cell"]],
            ),
            "evidence-multi": GoldEvidenceSet(
                gold_evidence_set_id="evidence-multi",
                evidence=[
                    GoldEvidence(evidence_id="paragraph", document_id=DOCUMENT_ID, locator=ObjectLocator(object_type="paragraph", object_id=paragraph_id), canonical_value="当前状态"),
                    GoldEvidence(evidence_id="cell", document_id=DOCUMENT_ID, locator=TableCellLocator(table_id=table_id, row=2, column=2), canonical_value="关键"),
                ],
                required_groups=[["paragraph"], ["cell"]],
            ),
            "evidence-table": GoldEvidenceSet(
                gold_evidence_set_id="evidence-table",
                evidence=[GoldEvidence(evidence_id="table", document_id=DOCUMENT_ID, locator=ObjectLocator(object_type="table", object_id=table_id), canonical_value="类别 | 重要程度 A | 关键")],
                required_groups=[["table"]],
            ),
        },
    )


def test_benchmark_contract_is_stable_and_splits_without_losing_text(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    first = build_benchmark_dataset(bundle, source_release_id="release-1", source_release_digest="a" * 64)
    second = build_benchmark_dataset(bundle, source_release_id="release-1", source_release_digest="a" * 64)

    assert first.manifest.contract_digest == second.manifest.contract_digest
    assert all(len(render_benchmark_segment(segment)) <= MAX_ENVELOPED_SEGMENT_CHARACTERS for segment in first.segments)
    long_leaves = [segment for segment in first.segments if segment.root_object_id.endswith("paragraph:2")]
    assert len(long_leaves) > 1
    assert all(segment.parent_segment_id for segment in long_leaves)
    prefix = "【paragraph】\n"
    assert "".join(segment.content.removeprefix(prefix) for segment in long_leaves) == "可验证的超长段落。" * 320


def test_table_and_multi_evidence_publish_as_explicit_leaf_mses(tmp_path: Path) -> None:
    dataset = build_benchmark_dataset(_bundle(tmp_path))

    table_gold = dataset.gold_by_case_id["case-table"]
    multi_gold = dataset.gold_by_case_id["case-multi"]
    assert len(table_gold.evidence_paths) == 1
    # A structural table object becomes an AND of its table-cell leaves, not a
    # fabricated aggregate retrieval chunk.
    assert len(table_gold.evidence_paths[0]) == 4
    assert len(multi_gold.evidence_paths[0]) == 2
    assert all(
        segment_id in dataset.segments_by_id
        for path in dataset.gold
        for evidence_path in path.evidence_paths
        for clause in evidence_path
        for segment_id in clause
    )


def test_legacy_contract_publish_remains_an_immutable_offline_model(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    root = tmp_path / "release" / "rag-benchmark-contract-1"
    published = publish_benchmark_dataset(bundle, root, source_release_id="release-1", source_release_digest="b" * 64)
    assert load_benchmark_dataset(root).manifest.contract_digest == published.manifest.contract_digest

    with pytest.raises(BenchmarkContractError, match="immutable"):
        publish_benchmark_dataset(
            bundle,
            root,
            source_release_id="release-2",
            source_release_digest="c" * 64,
        )
