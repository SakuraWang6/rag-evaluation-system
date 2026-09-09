from __future__ import annotations

from datetime import UTC, datetime

import pytest

from rag_eval.artifact_contract import artifact_digest
from rag_eval.authoring.providers import LocalOllamaProvider
from rag_eval.contracts.dataset import GoldAnswer, GoldAnswerKind
from rag_eval.contracts.observation import (
    AdapterRunResultV2,
    ContentObservation,
    UnifiedTrace,
)
from rag_eval.llm import LLMConfigurationService
from rag_eval.reviews import (
    CaseReviewSource,
    CaseReviewStore,
    CaseReviewVerdict,
    SemanticAnswerReviewer,
    SemanticReviewCoordinator,
    SemanticReviewRunState,
)
from rag_eval.runs.models import (
    ArtifactAnswerJudgment,
    ArtifactAnswerStatus,
    RunArtifactCaseV2,
)
from rag_eval.storage.runs import case_judgments
from tests.rag_eval_platform.test_run_artifact_v2 import _evaluated_case

CASE_DIGEST = "sha256:" + "d" * 64


def _semantic_case(case_id: str) -> RunArtifactCaseV2:
    _resolved, original = _evaluated_case(case_id)
    assert original.adapter_result is not None
    original_trace = original.adapter_result.trace
    trace = UnifiedTrace.build(
        case_id=original_trace.case_id,
        source_identity=original_trace.source_identity,
        runtime_profile=original_trace.runtime_profile,
        observation_profile=original_trace.observation_profile,
        ingestion_catalog=original_trace.ingestion_catalog,
        provenance_edges=original_trace.provenance_edges,
        canonical_mapping_records=original_trace.canonical_mapping_records,
        mapping_diagnostics=original_trace.mapping_diagnostics,
        raw_retrieval=original_trace.raw_retrieval,
        ranked_retrieval=original_trace.ranked_retrieval,
        final_context=original_trace.final_context,
        transformations=original_trace.transformations,
        prompt_trace=original_trace.prompt_trace,
        answer=ContentObservation.observed("北京是中国的首都。"),
        validation_receipts=original_trace.validation_receipts,
    )
    adapter_result = AdapterRunResultV2(
        adapter_id=original.adapter_result.adapter_id,
        adapter_version=original.adapter_result.adapter_version,
        system_id=original.adapter_result.system_id,
        system_version=original.adapter_result.system_version,
        trace=trace,
    )
    replaced = {
        "case_digest",
        "question",
        "gold_answer",
        "adapter_result",
        "trace_validation",
        "evaluation",
        "answer_judgment",
        "seed",
    }
    values = {
        field_name: getattr(original, field_name)
        for field_name in type(original).model_fields
        if field_name not in replaced
    }
    return RunArtifactCaseV2.build(
        **values,
        question="中国的首都是什么？",
        gold_answer=GoldAnswer(
            gold_answer_id=f"gold-{case_id}",
            kind=GoldAnswerKind.TEXT,
            canonical="中国首都是北京",
        ),
        adapter_result=adapter_result,
        trace_validation=original.trace_validation.model_copy(
            update={"adapter_result_digest": artifact_digest(adapter_result)}
        ),
        evaluation=original.evaluation.model_copy(
            update={"trace_digest": trace.trace_digest}
        ),
        answer_judgment=ArtifactAnswerJudgment(
            status=ArtifactAnswerStatus.NEEDS_REVIEW,
            reason="text equivalence requires semantic adjudication",
        ),
        seed=0,
    )


def test_human_review_ledger_is_append_only_and_changes_product_verdict(
    tmp_path,
) -> None:
    store = CaseReviewStore(tmp_path / "case-reviews")
    first = store.append(
        run_id="run-1",
        case_id="case-1",
        repetition=1,
        artifact_case_digest=CASE_DIGEST,
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
        artifact_case_digest=CASE_DIGEST,
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
        review=store.get(
            "run-1", "case-1", 1, artifact_case_digest=CASE_DIGEST
        ).api_view(),
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
    case = _semantic_case("case-semantic")

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
    case = _semantic_case("case-auto-semantic")

    coordinator = SemanticReviewCoordinator(reviewer, lambda _run_id: [case])
    status = coordinator.review_cases("run-auto-semantic", [case])

    assert status.state == SemanticReviewRunState.COMPLETED
    assert status.processed_count == 1
    assert status.adjudicated_count == 1
    review = store.get(
        "run-auto-semantic",
        case.case_id,
        1,
        artifact_case_digest=case.case_digest,
    )
    assert review.latest is not None
    assert review.latest.source == CaseReviewSource.LLM
    assert store.review_run_status("run-auto-semantic").state == SemanticReviewRunState.COMPLETED


def test_human_review_stays_final_even_if_a_legacy_llm_entry_is_later(tmp_path) -> None:
    store = CaseReviewStore(tmp_path / "case-reviews")
    human = store.append(
        run_id="run-human-final",
        case_id="case-human-final",
        repetition=1,
        artifact_case_digest=CASE_DIGEST,
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
            artifact_case_digest=CASE_DIGEST,
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


def test_review_overlay_rejects_another_artifact_case_digest(tmp_path) -> None:
    store = CaseReviewStore(tmp_path / "case-reviews")
    store.append(
        run_id="run-digest",
        case_id="case-digest",
        repetition=1,
        artifact_case_digest="sha256:" + "a" * 64,
        verdict=CaseReviewVerdict.CORRECT,
        source=CaseReviewSource.HUMAN,
        reviewer="reviewer-1",
    )

    with pytest.raises(ValueError, match="another Artifact case"):
        store.get(
            "run-digest",
            "case-digest",
            1,
            artifact_case_digest="sha256:" + "b" * 64,
        )
