from __future__ import annotations

from datetime import UTC, datetime

import pytest

from rag_eval.authoring.providers import LocalOllamaProvider
from rag_eval.contracts.adapter import RAGResult
from rag_eval.contracts.dataset import GoldAnswer, GoldAnswerKind
from rag_eval.contracts.run import CaseResult
from rag_eval.llm import LLMConfigurationService
from rag_eval.reviews import (
    CaseReviewSource,
    CaseReviewStore,
    CaseReviewVerdict,
    SemanticAnswerReviewer,
    SemanticReviewCoordinator,
    SemanticReviewRunState,
)
from rag_eval.storage.runs import case_judgments


def test_human_review_ledger_is_append_only_and_changes_product_verdict(
    tmp_path,
) -> None:
    store = CaseReviewStore(tmp_path / "case-reviews")
    first = store.append(
        run_id="run-1",
        case_id="case-1",
        repetition=1,
        verdict=CaseReviewVerdict.NEEDS_REVIEW,
        source=CaseReviewSource.LLM,
        reviewer="ollama:qwen",
        note="The model cannot decide whether the wording is equivalent.",
        model="qwen",
        prompt_digest="a" * 64,
    )
    second = store.append(
        run_id="run-1",
        case_id="case-1",
        repetition=1,
        verdict=CaseReviewVerdict.CORRECT,
        source=CaseReviewSource.HUMAN,
        reviewer="reviewer-1",
        note="Equivalent meaning confirmed against the source.",
    )

    assert [decision.revision for decision in second.decisions] == [1, 2]
    assert first.latest is not None
    assert first.latest.verdict == CaseReviewVerdict.NEEDS_REVIEW
    assert second.latest is not None
    assert second.latest.source == CaseReviewSource.HUMAN
    assert case_judgments(
        status="completed",
        metrics=[],
        failure_assessment=None,
        review=store.get("run-1", "case-1", 1).api_view(),
    )["answer_judgment"] == "correct"


def test_semantic_review_records_an_auditable_llm_verdict(
    tmp_path, monkeypatch
) -> None:
    def propose(_self, *, task, source, prompt, seed):
        assert task == "semantic_answer_adjudication"
        assert source[0]["generated_answer"] == "北京是中国的首都。"
        assert "equivalence adjudicator" in prompt
        assert seed == 0
        return {"verdict": "equivalent", "reason": "The answer states the same fact."}

    monkeypatch.setattr(LocalOllamaProvider, "propose", propose)
    reviewer = SemanticAnswerReviewer(
        CaseReviewStore(tmp_path / "case-reviews"),
        LLMConfigurationService(tmp_path / "llm"),
    )
    now = datetime.now(UTC)
    case = CaseResult(
        case_id="case-semantic",
        status="completed",
        question="中国的首都是什么？",
        gold_answer=GoldAnswer(
            gold_answer_id="gold-semantic",
            kind=GoldAnswerKind.TEXT,
            canonical="中国首都是北京",
        ),
        rag_result=RAGResult(answer="北京是中国的首都。"),
        started_at=now,
        completed_at=now,
        repetition=1,
        seed=0,
    )

    record = reviewer.review("run-semantic", case)

    assert record.latest is not None
    assert record.latest.source == CaseReviewSource.LLM
    assert record.latest.verdict == CaseReviewVerdict.CORRECT
    assert record.latest.prompt_digest is not None


def test_automatic_semantic_review_is_durable_and_leaves_run_artifacts_alone(
    tmp_path, monkeypatch
) -> None:
    def propose(_self, *, task, source, prompt, seed):
        assert task == "semantic_answer_adjudication"
        assert source[0]["generated_answer"] == "北京是中国的首都。"
        return {"verdict": "equivalent", "reason": "Same fact in a different order."}

    monkeypatch.setattr(LocalOllamaProvider, "propose", propose)
    store = CaseReviewStore(tmp_path / "case-reviews")
    reviewer = SemanticAnswerReviewer(store, LLMConfigurationService(tmp_path / "llm"))
    now = datetime.now(UTC)
    case = CaseResult(
        case_id="case-auto-semantic",
        status="completed",
        question="中国的首都是什么？",
        gold_answer=GoldAnswer(
            gold_answer_id="gold-auto-semantic",
            kind=GoldAnswerKind.TEXT,
            canonical="中国首都是北京",
        ),
        rag_result=RAGResult(answer="北京是中国的首都。"),
        started_at=now,
        completed_at=now,
        repetition=1,
        seed=0,
    )

    coordinator = SemanticReviewCoordinator(reviewer, lambda _run_id: [case])
    status = coordinator.review_cases("run-auto-semantic", [case])

    assert status.state == SemanticReviewRunState.COMPLETED
    assert status.processed_count == 1
    assert status.adjudicated_count == 1
    assert store.get("run-auto-semantic", case.case_id, 1).latest is not None
    assert store.get("run-auto-semantic", case.case_id, 1).latest.source == CaseReviewSource.LLM
    assert store.review_run_status("run-auto-semantic").state == SemanticReviewRunState.COMPLETED


def test_human_review_stays_final_even_if_a_legacy_llm_entry_is_later(tmp_path) -> None:
    store = CaseReviewStore(tmp_path / "case-reviews")
    human = store.append(
        run_id="run-human-final",
        case_id="case-human-final",
        repetition=1,
        verdict=CaseReviewVerdict.CORRECT,
        source=CaseReviewSource.HUMAN,
        reviewer="reviewer-1",
        note="human confirms equivalence",
    )
    with pytest.raises(ValueError, match="human adjudication"):
        store.append(
            run_id="run-human-final",
            case_id="case-human-final",
            repetition=1,
            verdict=CaseReviewVerdict.INCORRECT,
            source=CaseReviewSource.LLM,
            reviewer="ollama:qwen",
            note="should not be appended",
            model="qwen",
            prompt_digest="b" * 64,
        )
    legacy_view = human.api_view()
    legacy_view["history"].append(
        {
            "revision": 2,
            "verdict": "incorrect",
            "source": "llm",
            "reviewer": "legacy-model",
            "note": "old retry",
            "created_at": datetime.now(UTC).isoformat(),
            "model": "legacy",
            "prompt_digest": "c" * 64,
        }
    )
    legacy_view["latest"] = legacy_view["history"][-1]
    assert case_judgments(
        status="completed",
        metrics=[],
        failure_assessment=None,
        review=legacy_view,
    )["answer_judgment"] == "correct"
