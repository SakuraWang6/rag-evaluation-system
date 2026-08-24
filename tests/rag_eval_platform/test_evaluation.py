from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from rag_eval.contracts.adapter import RAGEvidenceItem, RAGResult
from rag_eval.contracts.dataset import (
    GoldAnswer,
    GoldAnswerKind,
    GoldEvidence,
    GoldEvidenceSet,
    ObjectLocator,
)
from rag_eval.contracts.run import CaseResult, MetricResult, MetricStatus
from rag_eval.evaluation.answers import AnswerVerdict, score_answer
from rag_eval.evaluation.engine import evaluate_case
from rag_eval.evaluation.evidence import CorpusEvidenceIndex, match_evidence
from rag_eval.evaluation.metrics import evaluate_retrieval_stages
from rag_eval.execution import aggregate_metrics


def gold_fixture() -> tuple[GoldAnswer, GoldEvidenceSet, CorpusEvidenceIndex]:
    answer = GoldAnswer(
        gold_answer_id="a-1",
        kind=GoldAnswerKind.NUMERIC,
        canonical="42",
        unit="ms",
        tolerance=Decimal("0.1"),
    )
    evidence = GoldEvidence(
        evidence_id="e-1",
        document_id="doc-1",
        locator=ObjectLocator(object_type="fact", object_id="FACT-1"),
        canonical_value="42 ms",
        quote_anchor="The controlled latency is 42 ms.",
    )
    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="set-1",
        evidence=[evidence],
        required_groups=[["e-1"]],
    )
    corpus = CorpusEvidenceIndex(
        {
            "doc-1": "The controlled latency is 42 ms.",
            "doc-2": "No value is stated here.",
        }
    )
    return answer, evidence_set, corpus


def evidence_item(*, rank: int, document_id: str = "doc-1") -> RAGEvidenceItem:
    return RAGEvidenceItem(
        item_id=f"item-{rank}",
        rank=rank,
        document_id=document_id,
        content="The controlled latency is 42 ms.",
        locator=ObjectLocator(object_type="fact", object_id="FACT-1"),
    )


def metric(metrics, metric_id):
    return next(item for item in metrics if item.metric_id == metric_id)


def test_typed_numeric_scorer_rejects_substring_and_honours_tolerance() -> None:
    answer, _evidence_set, _corpus = gold_fixture()
    assert score_answer("The value is 142 ms", answer).verdict == AnswerVerdict.FAIL
    assert score_answer("The value is 42.05 ms", answer).verdict == AnswerVerdict.PASS
    assert score_answer("The value is 42 milliseconds", answer).verdict == (
        AnswerVerdict.FAIL
    )
    assert score_answer("The value is either 42 ms or 43 ms", answer).verdict == (
        AnswerVerdict.NEEDS_REVIEW
    )


def test_text_formula_and_set_scorers_fail_closed() -> None:
    text = GoldAnswer(
        gold_answer_id="text", kind=GoldAnswerKind.TEXT, canonical="北京"
    )
    assert score_answer("北京", text).verdict == AnswerVerdict.PASS
    assert score_answer("答案是北京", text).verdict == AnswerVerdict.NEEDS_REVIEW

    formula = GoldAnswer(
        gold_answer_id="formula", kind=GoldAnswerKind.FORMULA, canonical="x = 1"
    )
    assert score_answer("x = 10", formula).verdict == AnswerVerdict.NEEDS_REVIEW

    answer_set = GoldAnswer(
        gold_answer_id="set", kind=GoldAnswerKind.SET, canonical=["A", "B"]
    )
    assert score_answer("A, B", answer_set).verdict == AnswerVerdict.PASS
    assert score_answer("A, B, C", answer_set).verdict == AnswerVerdict.FAIL


def test_bare_answer_quote_with_wrong_document_is_not_gold_evidence() -> None:
    _answer, evidence_set, corpus = gold_fixture()
    wrong = evidence_item(rank=1, document_id="doc-2")
    assert match_evidence(wrong, evidence_set.evidence[0], corpus) is None


def test_stage_metrics_explain_ranking_and_context_selection() -> None:
    _answer, evidence_set, corpus = gold_fixture()
    irrelevant = RAGEvidenceItem(
        item_id="other",
        rank=1,
        document_id="doc-2",
        content="No value is stated here.",
        locator=ObjectLocator(object_type="fact", object_id="OTHER"),
    )
    raw_hit = evidence_item(rank=2)
    ranked_hit = evidence_item(rank=1)
    result = RAGResult(
        raw_retrieval=[irrelevant, raw_hit],
        ranked_retrieval=[ranked_hit, irrelevant.model_copy(update={"rank": 2})],
        final_context=[],
    )
    metrics = evaluate_retrieval_stages(
        result, evidence_set, corpus, k_values=(1,)
    )

    assert metric(metrics, "raw_recall@1").value == 0.0
    assert metric(metrics, "ranked_recall@1").value == 1.0
    assert metric(metrics, "context_recall@1").value == 0.0
    assert metric(metrics, "retrieval_stage_delta@1").value == 1.0
    assert metric(metrics, "context_selection_loss@1").value == 1.0


def test_unobservable_stage_is_unavailable_not_zero() -> None:
    _answer, evidence_set, corpus = gold_fixture()
    metrics = evaluate_retrieval_stages(
        RAGResult(raw_retrieval=None, ranked_retrieval=[], final_context=[]),
        evidence_set,
        corpus,
        k_values=(1,),
    )
    assert metric(metrics, "raw_recall@1").status == MetricStatus.UNAVAILABLE
    assert metric(metrics, "raw_recall@1").value is None
    assert metric(metrics, "ranked_recall@1").status == MetricStatus.OBSERVED
    assert metric(metrics, "ranked_recall@1").value == 0.0


def test_groundedness_is_deterministic_and_not_named_hallucination() -> None:
    answer, evidence_set, corpus = gold_fixture()
    metrics = evaluate_case(
        RAGResult(
            answer="42 ms",
            raw_retrieval=[],
            ranked_retrieval=[evidence_item(rank=1)],
            final_context=[evidence_item(rank=1)],
        ),
        answer,
        evidence_set,
        corpus,
        k_values=(1,),
    )
    assert metric(metrics, "answer_groundedness").value == 1.0
    assert metric(metrics, "answer_groundedness").evaluator_mode == (
        "deterministic_gold_evidence"
    )
    assert metric(metrics, "unsupported_answer_rate").value == 0.0
    assert all("hallucination" not in item.metric_id for item in metrics)


def test_retrieval_only_marks_answer_metrics_not_applicable() -> None:
    answer, evidence_set, corpus = gold_fixture()
    metrics = evaluate_case(
        RAGResult(raw_retrieval=[], ranked_retrieval=[], final_context=[]),
        answer,
        evidence_set,
        corpus,
        k_values=(1,),
        evaluate_answer=False,
    )
    assert metric(metrics, "answer_accuracy").status == MetricStatus.NOT_APPLICABLE
    assert metric(metrics, "answer_groundedness").status == (
        MetricStatus.NOT_APPLICABLE
    )


def test_repetition_statistics_keep_execution_errors_out_of_metric_denominator() -> None:
    now = datetime.now(UTC)
    observed = MetricResult(
        metric_id="answer_accuracy",
        status=MetricStatus.OBSERVED,
        value=1.0,
        scorer_id="scorer",
        scorer_version="1",
        scorer_digest="sha256:test",
    )
    error = MetricResult(
        metric_id="answer_accuracy",
        status=MetricStatus.ERROR,
        scorer_id="scorer",
        scorer_version="1",
        scorer_digest="sha256:test",
        reason="timeout",
    )
    results = [
        CaseResult(
            case_id="case-1",
            status="completed",
            question="q",
            metrics=[observed],
            started_at=now,
            completed_at=now,
            repetition=1,
            seed=10,
        ),
        CaseResult(
            case_id="case-1",
            status="timeout",
            question="q",
            metrics=[error],
            started_at=now,
            completed_at=now,
            repetition=2,
            seed=11,
        ),
    ]

    summary = aggregate_metrics(results, repetitions=2, expected=2)

    accuracy = summary["metrics"]["answer_accuracy"]
    assert accuracy["mean"] == 1.0
    assert accuracy["standard_deviation"] == 0.0
    assert accuracy["repetition_values"] == [1.0]
    assert accuracy["denominator"] == 1
    assert summary["execution"]["execution_failure_rate"] == 0.5
    assert accuracy["coverage"] == 0.5
    assert accuracy["status_counts"]["error"] == 1
