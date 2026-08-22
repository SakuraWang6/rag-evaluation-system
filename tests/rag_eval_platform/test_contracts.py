from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from rag_eval.contracts.adapter import DocumentInput, RAGEvidenceItem, RAGResult
from rag_eval.contracts.dataset import (
    GoldAnswer,
    GoldAnswerKind,
    GoldEvidence,
    GoldEvidenceSet,
    ObjectLocator,
)
from rag_eval.contracts.run import MetricResult, MetricStatus
from rag_eval.contracts.schema import PUBLIC_MODELS


def test_none_and_empty_retrieval_round_trip_have_distinct_meanings() -> None:
    unavailable = RAGResult(raw_retrieval=None)
    observed_empty = RAGResult(raw_retrieval=[])

    unavailable_round_trip = RAGResult.model_validate_json(
        unavailable.model_dump_json()
    )
    empty_round_trip = RAGResult.model_validate_json(
        observed_empty.model_dump_json()
    )

    assert unavailable_round_trip.raw_retrieval is None
    assert empty_round_trip.raw_retrieval == []


def test_evidence_groups_are_non_empty_and_reference_known_ids() -> None:
    evidence = GoldEvidence(
        evidence_id="e-1",
        document_id="doc-1",
        locator=ObjectLocator(object_type="fact", object_id="FACT-1"),
        canonical_value="42",
    )
    valid = GoldEvidenceSet(
        gold_evidence_set_id="set-1",
        evidence=[evidence],
        required_groups=[["e-1"]],
    )
    assert valid.required_groups == [["e-1"]]

    with pytest.raises(ValidationError, match="unknown evidence"):
        GoldEvidenceSet(
            gold_evidence_set_id="set-1",
            evidence=[evidence],
            required_groups=[["missing"]],
        )


def test_non_abstain_answer_requires_canonical_value() -> None:
    with pytest.raises(ValidationError, match="canonical"):
        GoldAnswer(gold_answer_id="a-1", kind=GoldAnswerKind.TEXT)


def test_metric_status_never_conflates_unavailable_with_zero() -> None:
    unavailable = MetricResult(
        metric_id="raw_recall@5",
        status=MetricStatus.UNAVAILABLE,
        scorer_id="retrieval-groups",
        scorer_version="1.0",
        scorer_digest="sha256:test",
        reason="raw retrieval is not observable",
    )
    zero = MetricResult(
        metric_id="raw_recall@5",
        status=MetricStatus.OBSERVED,
        value=0.0,
        numerator=0,
        denominator=1,
        scorer_id="retrieval-groups",
        scorer_version="1.0",
        scorer_digest="sha256:test",
    )
    assert unavailable.value is None
    assert zero.value == 0.0


def test_all_public_contracts_emit_json_schema() -> None:
    for name, model in PUBLIC_MODELS.items():
        schema = model.model_json_schema()
        assert schema["title"]
        json.dumps(schema)
        assert name


def test_platform_source_has_no_lightrag_or_raganything_imports() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src"
    forbidden = ("lightrag", "raganything", "rag_anything")
    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert all(not name.startswith(forbidden) for name in names), path


def test_evidence_item_requires_positive_rank() -> None:
    with pytest.raises(ValidationError):
        RAGEvidenceItem(item_id="x", rank=0, content="")


def test_contract_does_not_define_hallucination_metric() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src"
    for path in source_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert 'metric_id="hallucination_rate"' not in text


def test_binary_document_uses_safe_source_only_reference() -> None:
    document = DocumentInput(
        document_id="pdf-1",
        source_path="source-00000.pdf",
        mime_type="application/pdf",
    )
    assert document.content is None
    with pytest.raises(ValidationError, match="safe relative"):
        DocumentInput(
            document_id="pdf-1",
            source_path="../gold_answers.jsonl",
            mime_type="application/pdf",
        )
