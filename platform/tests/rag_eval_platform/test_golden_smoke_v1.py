from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rag_eval.adapters.fake import FakeAdapter
from rag_eval.contracts.adapter import (
    AdapterCapabilities,
    RAGEvidenceItem,
    RAGResult,
)
from rag_eval.contracts.dataset import (
    GoldAnswer,
    GoldAnswerKind,
    GoldEvidence,
    GoldEvidenceSet,
    Question,
    TextSpanLocator,
)
from rag_eval.contracts.observation import AdapterCapabilitiesV2, ObservationStatus
from rag_eval.contracts.research import FailureLabel
from rag_eval.contracts.run import ExperimentSpec, RunManifest, RunStatus
from rag_eval.datasets.bundle import load_bundle
from rag_eval.evaluation.engine import evaluate_case
from rag_eval.evaluation.evidence import CorpusEvidenceIndex
from rag_eval.evaluation.failures import assess_failure
from rag_eval.execution import aggregate_metrics, failed_case
from rag_eval.report import markdown_report

from .native_worker_fixtures import native_query, stage_native_worker_input

GOLDEN_ROOT = Path(__file__).resolve().parents[2] / "examples" / "golden-smoke-v1"


def metric(metrics, metric_id):
    return next(item for item in metrics if item.metric_id == metric_id)


def marker_fixture() -> tuple[GoldAnswer, GoldEvidenceSet, CorpusEvidenceIndex, RAGEvidenceItem]:
    answer = GoldAnswer(
        gold_answer_id="answer-marker",
        kind=GoldAnswerKind.TEXT,
        canonical="amber",
    )
    evidence = GoldEvidence(
        evidence_id="marker",
        document_id="doc-marker",
        locator=TextSpanLocator(start=0, end=20),
        canonical_value="amber",
        quote_anchor="The marker is amber.",
    )
    evidence_set = GoldEvidenceSet(
        gold_evidence_set_id="evidence-marker",
        evidence=[evidence],
        required_groups=[["marker"]],
    )
    corpus = CorpusEvidenceIndex({"doc-marker": "The marker is amber."})
    item = RAGEvidenceItem(
        item_id="marker-1",
        rank=1,
        content="The marker is amber.",
        document_id="doc-marker",
        locator=TextSpanLocator(start=0, end=20),
    )
    return answer, evidence_set, corpus, item


def test_golden_smoke_bundle_is_new_formally_valid_and_reviewed() -> None:
    bundle = load_bundle(GOLDEN_ROOT)
    review_rows = list(
        csv.DictReader(
            (GOLDEN_ROOT / "golden-smoke-review-checklist.csv").open(
                newline="", encoding="utf-8"
            )
        )
    )

    assert bundle.bundle_id == "bbfbb1d2761b714a595ae072f786bd527fdff5c85ba7c57c40b6d8087072ba1e"
    assert len(bundle.questions) == len(bundle.gold_answers) == len(bundle.gold_evidence_sets) == 24
    assert {
        question.metadata["question_type"]: sum(
            item.metadata["question_type"] == question.metadata["question_type"]
            for item in bundle.questions
        )
        for question in bundle.questions
    } == {
        "plain-text": 4,
        "numeric/unit": 4,
        "table-cell": 4,
        "explicit-ID": 4,
        "multi-evidence": 4,
        "abstain/negative": 4,
    }
    assert len(review_rows) == 24
    assert {row["case_id"] for row in review_rows} == {
        question.case_id for question in bundle.questions
    }
    for row in review_rows:
        assert all(
            row[field] == "yes"
            for field in (
                "question_valid",
                "answer_valid",
                "evidence_valid",
                "locator_valid",
                "difficulty_reasonable",
            )
        )
        assert row["reviewer"] == "author review"
        assert row["review_status"] == "approved"
    forbidden_cues = ("gold", "authoritative", "benchmark", "memory_eval")
    for document in (GOLDEN_ROOT / "documents").iterdir():
        assert not any(cue in document.read_text(encoding="utf-8").casefold() for cue in forbidden_cues)


@pytest.mark.asyncio
async def test_fake_adapter_preserves_empty_and_unavailable_stage_semantics(
    tmp_path: Path,
) -> None:
    observable = FakeAdapter(
        capabilities=AdapterCapabilitiesV2(
            ingestion_catalog=True,
            answer=True,
            candidate_retrieval=True,
            ranked_retrieval=True,
            final_context=True,
        )
    )
    original, resolved = stage_native_worker_input(
        tmp_path / "observable",
        run_id="golden-fake-observable",
    )
    prepared = await observable.prepare(original, resolved)
    observed = await observable.query(prepared, native_query(case_id="observed"))
    assert observed.trace.raw_retrieval.observation_status == ObservationStatus.OBSERVED
    assert observed.trace.ranked_retrieval.observation_status == ObservationStatus.OBSERVED
    assert observed.trace.final_context.observation_status == ObservationStatus.OBSERVED

    partial = FakeAdapter(
        capabilities=AdapterCapabilitiesV2(ranked_retrieval=True)
    )
    original, resolved = stage_native_worker_input(
        tmp_path / "partial",
        run_id="golden-fake-unavailable",
    )
    prepared = await partial.prepare(original, resolved)
    unavailable = await partial.query(
        prepared,
        native_query(case_id="unavailable"),
    )
    assert unavailable.trace.raw_retrieval.observation_status == (
        ObservationStatus.UNSUPPORTED
    )
    assert unavailable.trace.raw_retrieval.items == ()
    assert unavailable.trace.ranked_retrieval.observation_status == (
        ObservationStatus.OBSERVED
    )
    assert unavailable.trace.final_context.observation_status == (
        ObservationStatus.UNSUPPORTED
    )


def test_golden_smoke_adversarial_evaluation_semantics() -> None:
    answer, evidence_set, corpus, hit = marker_fixture()

    wrong_answer_metrics = evaluate_case(
        RAGResult(
            answer="blue",
            raw_retrieval=[hit],
            ranked_retrieval=[hit],
            final_context=[hit],
        ),
        answer,
        evidence_set,
        corpus,
        k_values=(1,),
    )
    wrong_answer = assess_failure(
        status="completed",
        result=RAGResult(
            answer="blue",
            raw_retrieval=[hit],
            ranked_retrieval=[hit],
            final_context=[hit],
        ),
        evidence_set=evidence_set,
        corpus=corpus,
        metrics=wrong_answer_metrics,
    )
    # A lexical text mismatch may still be a paraphrase.  P1 keeps it out of
    # a deterministic generation-failure count until the semantic/human
    # answer-review stages decide equivalence.
    assert metric(wrong_answer_metrics, "answer_accuracy").status.value == "needs_review"
    assert FailureLabel.GENERATION_FAILURE not in wrong_answer.labels
    assert FailureLabel.NEEDS_REVIEW in wrong_answer.labels

    accidental_correct_result = RAGResult(
        answer="amber", raw_retrieval=[], ranked_retrieval=[], final_context=[]
    )
    accidental_correct_metrics = evaluate_case(
        accidental_correct_result,
        answer,
        evidence_set,
        corpus,
        k_values=(1,),
    )
    accidental_correct = assess_failure(
        status="completed",
        result=accidental_correct_result,
        evidence_set=evidence_set,
        corpus=corpus,
        metrics=accidental_correct_metrics,
    )
    assert metric(accidental_correct_metrics, "raw_recall@1").value == 0.0
    assert metric(accidental_correct_metrics, "answer_accuracy").value == 1.0
    assert metric(accidental_correct_metrics, "answer_groundedness").value == 0.0
    assert FailureLabel.RETRIEVAL_MISSING in accidental_correct.labels
    assert FailureLabel.UNSUPPORTED_ANSWER in accidental_correct.labels
    assert FailureLabel.GENERATION_FAILURE not in accidental_correct.labels

    review_result = RAGResult(
        answer="The marker is amber.",
        raw_retrieval=[hit],
        ranked_retrieval=[hit],
        final_context=[hit],
    )
    review_metrics = evaluate_case(
        review_result, answer, evidence_set, corpus, k_values=(1,)
    )
    review = assess_failure(
        status="completed",
        result=review_result,
        evidence_set=evidence_set,
        corpus=corpus,
        metrics=review_metrics,
    )
    assert metric(review_metrics, "answer_accuracy").status.value == "observed"
    assert metric(review_metrics, "answer_accuracy").value == 1.0
    assert not review.review_required
    assert FailureLabel.NEEDS_REVIEW not in review.labels

    second = GoldEvidence(
        evidence_id="second",
        document_id="doc-second",
        locator=TextSpanLocator(start=0, end=25),
        canonical_value="8 hours",
        quote_anchor="The backup lasts 8 hours.",
    )
    multi_set = GoldEvidenceSet(
        gold_evidence_set_id="multi",
        evidence=[evidence_set.evidence[0], second],
        required_groups=[["marker"], ["second"]],
    )
    multi_metrics = evaluate_case(
        RAGResult(raw_retrieval=[hit], ranked_retrieval=[hit], final_context=[hit]),
        answer,
        multi_set,
        CorpusEvidenceIndex(
            {"doc-marker": "The marker is amber.", "doc-second": "The backup lasts 8 hours."}
        ),
        k_values=(1,),
        evaluate_answer=False,
    )
    assert metric(multi_metrics, "raw_recall@1").value == 0.5


def test_timeout_and_adapter_error_stay_errors_across_json_metrics_and_report() -> None:
    answer, evidence_set, _corpus, _hit = marker_fixture()
    question = Question(
        case_id="semantic-case",
        question="What is the marker?",
        gold_answer_id=answer.gold_answer_id,
        gold_evidence_set_id=evidence_set.gold_evidence_set_id,
    )
    experiment = ExperimentSpec(
        experiment_id="semantic-experiment",
        bundle_id="bundle",
        system_id="fake",
        adapter_id="fake",
        case_selection_id="selection",
        metric_config={"k_values": [1]},
    )
    timeout_case = failed_case(
        question.case_id,
        question.question,
        answer,
        evidence_set,
        datetime.now(UTC),
        status="timeout",
        code="timeout",
        message="adapter query timed out",
        experiment=experiment,
    )
    adapter_error_case = failed_case(
        question.case_id,
        question.question,
        answer,
        evidence_set,
        datetime.now(UTC),
        status="system_error",
        code="adapter_error",
        message="adapter crashed",
        experiment=experiment,
    )
    summary = aggregate_metrics([timeout_case], expected=1)
    raw_summary = summary["metrics"]["raw_recall@1"]

    assert FailureLabel.TIMEOUT in timeout_case.failure_assessment.labels
    assert FailureLabel.ADAPTER_ERROR in adapter_error_case.failure_assessment.labels
    assert raw_summary["status"] == "error"
    assert raw_summary["value"] is None
    assert raw_summary["denominator"] == 0
    encoded = json.loads(timeout_case.model_dump_json())
    assert encoded["failure_assessment"]["labels"] == ["timeout"]

    manifest = RunManifest(
        run_id="semantic-run",
        experiment_id=experiment.experiment_id,
        status=RunStatus.COMPLETED,
        bundle_id=experiment.bundle_id,
        case_selection_id=experiment.case_selection_id,
        platform_version="0.1.0",
        adapter_id="fake",
        adapter_version="0.1.0",
        system_id="fake",
        system_version="fake-rag-1",
        declared_config={},
        effective_config={},
        scorer_id="typed-answer",
        scorer_version="1.1",
        scorer_digest="sha256:test",
        declared_capabilities=AdapterCapabilities(),
        observed_capabilities=AdapterCapabilities(),
        seed=0,
        repetitions=1,
        started_at=datetime.now(UTC),
    )
    report = markdown_report(manifest, [timeout_case], summary)
    assert "#### Failure Assessment" in report
    assert '"timeout"' in report
