"""P1 support/hallucination review stays independent from answer correctness."""

from __future__ import annotations

import pytest

from rag_eval.authoring.providers import LocalOllamaProvider
from rag_eval.llm import LLMConfigurationService
from rag_eval.reviews import (
    AnswerSupportReviewStore,
    AnswerSupportVerdict,
    CaseReviewSource,
    SemanticAnswerSupportReviewer,
    SemanticReviewCoordinator,
)
from rag_eval.run_history import RunHistory
from rag_eval.runs.models import RunArtifactCaseV2
from tests.rag_eval_platform.test_run_artifact_v2 import _evaluated_case


def _case() -> RunArtifactCaseV2:
    _resolved, case = _evaluated_case("case-support")
    return case


def test_support_reviewer_receives_final_context_but_never_gold(tmp_path, monkeypatch) -> None:
    def propose(_self, *, task, source, prompt, seed):
        assert task == "semantic_answer_support_adjudication"
        assert "gold" not in source[0]
        assert source[0]["final_context"][0]["native_chunk_id"] == "gold"
        assert source[0]["final_context"][0]["content"] == "content:gold"
        assert "missing Gold evidence alone" in prompt
        assert seed == 0
        return {"verdict": "supported", "reason": "The answer faithfully reports the context."}

    monkeypatch.setattr(LocalOllamaProvider, "propose", propose)
    store = AnswerSupportReviewStore(tmp_path / "support-reviews")
    reviewer = SemanticAnswerSupportReviewer(
        store,
        LLMConfigurationService(tmp_path / "llm"),
    )

    record = reviewer.review("run-support", _case())

    assert record.latest is not None
    assert record.latest.verdict == AnswerSupportVerdict.SUPPORTED
    assert record.latest.source == CaseReviewSource.LLM


def test_support_review_is_idempotent_and_human_is_terminal(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        LocalOllamaProvider,
        "propose",
        lambda *_args, **_kwargs: {"verdict": "uncertain", "reason": "Need a reviewer."},
    )
    store = AnswerSupportReviewStore(tmp_path / "support-reviews")
    reviewer = SemanticAnswerSupportReviewer(store, LLMConfigurationService(tmp_path / "llm"))
    case = _case()
    reviewer.review("run-support", case)
    store.append(
        run_id="run-support",
        case_id=case.case_id,
        repetition=case.repetition,
        artifact_case_digest=case.case_digest,
        verdict=AnswerSupportVerdict.UNSUPPORTED,
        source=CaseReviewSource.HUMAN,
        reviewer="reviewer-1",
        note="Human found an unsupported claim.",
    )

    with pytest.raises(ValueError, match="human support adjudication"):
        store.append(
            run_id="run-support",
            case_id=case.case_id,
            repetition=case.repetition,
            artifact_case_digest=case.case_digest,
            verdict=AnswerSupportVerdict.SUPPORTED,
            source=CaseReviewSource.LLM,
            reviewer="ollama:qwen",
            note="must not replace human",
            model="qwen",
            prompt_digest="a" * 64,
        )


def test_support_projection_counts_hallucination_without_changing_answer_accuracy(tmp_path) -> None:
    from rag_eval.contracts.run import MetricResult, MetricStatus

    metric = MetricResult(
        metric_id="answer_hallucination",
        status=MetricStatus.NEEDS_REVIEW,
        scorer_id="segment-native-answer-evidence",
        scorer_version="1.0",
        scorer_digest="sha256:test",
    )
    projected = RunHistory._project_answer_support_metric(
        metric,
        {
            "latest": {"verdict": "unsupported", "source": "llm"},
            "history": [{"verdict": "unsupported", "source": "llm"}],
        },
    )
    assert projected.status == MetricStatus.OBSERVED
    assert projected.value == 1.0
    assert projected.evaluator_mode == "append_only_llm_support_adjudication"


def test_support_coordinator_uses_same_durable_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        LocalOllamaProvider,
        "propose",
        lambda *_args, **_kwargs: {"verdict": "supported", "reason": "Grounded."},
    )
    store = AnswerSupportReviewStore(tmp_path / "support-reviews")
    reviewer = SemanticAnswerSupportReviewer(store, LLMConfigurationService(tmp_path / "llm"))
    case = _case()
    coordinator = SemanticReviewCoordinator(reviewer, lambda _run_id: [case])

    status = coordinator.review_cases("run-support", [case])

    assert status.processed_count == 1
    assert status.adjudicated_count == 1
    assert status.needs_human_count == 0
