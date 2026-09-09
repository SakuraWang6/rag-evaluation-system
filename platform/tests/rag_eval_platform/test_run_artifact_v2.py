from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

import pytest

from rag_eval.contracts.adapter import (
    AdapterCapabilities,
    RAGEvidenceItem,
    RAGQuery,
    RAGResult,
)
from rag_eval.contracts.dataset import GoldAnswer, GoldAnswerKind, Question
from rag_eval.contracts.observation import (
    AdapterRunResultV2,
    ObservationStatus,
    UnifiedTrace,
)
from rag_eval.contracts.run import ExperimentSpec
from rag_eval.evaluation.evidence import CorpusEvidenceIndex
from rag_eval.evaluation.unified import EvaluationMetricStatus, FailureKind
from rag_eval.execution import execute_case
from rag_eval.runs import (
    AdapterSession,
    ArtifactV2Reader,
    ArtifactWriter,
    BenchmarkIdentityV2,
    BenchmarkResolver,
    EvaluationEngine,
    NativeCaseOrchestrator,
    TraceValidator,
    build_artifact_summary,
    derive_leaderboard_eligibility,
)
from rag_eval.storage.runs import RunStore
from tests.rag_eval_platform.test_run_history import _manifest as legacy_manifest
from tests.rag_eval_platform.test_unified_evaluation_v2 import (
    SHA_A,
    SHA_C,
    _chunk,
    _edge,
    _gold,
    _item,
    _profile,
    _text_extent,
    _trace,
)


def _trace_for_case(trace: UnifiedTrace, case_id: str) -> UnifiedTrace:
    return UnifiedTrace.build(
        case_id=case_id,
        source_identity=trace.source_identity,
        runtime_profile=trace.runtime_profile,
        observation_profile=trace.observation_profile,
        ingestion_catalog=trace.ingestion_catalog,
        provenance_edges=trace.provenance_edges,
        canonical_mapping_records=trace.canonical_mapping_records,
        mapping_diagnostics=trace.mapping_diagnostics,
        raw_retrieval=trace.raw_retrieval,
        ranked_retrieval=trace.ranked_retrieval,
        final_context=trace.final_context,
        transformations=trace.transformations,
        prompt_trace=trace.prompt_trace,
        answer=trace.answer,
        validation_receipts=trace.validation_receipts,
    )


def _observed_fixture(case_id: str = "case-1"):
    chunk = _chunk("gold")
    extent = _text_extent("gold-a")
    edge = _edge(chunk, "gold-a", extent, extent)
    item = _item(chunk, 1, (edge,))
    trace = _trace(
        chunks=(chunk,),
        edges=(edge,),
        mapping_statuses={"gold-a": "complete"},
        candidate=(item,),
        ranked=(item,),
        context=(item,),
        answer="42",
    )
    trace = _trace_for_case(trace, case_id)
    adapter_result = AdapterRunResultV2(
        adapter_id=trace.observation_profile.adapter_id,
        adapter_version=trace.observation_profile.adapter_version,
        system_id=trace.runtime_profile.system_id,
        system_version=trace.runtime_profile.system_version,
        trace=trace,
    )
    legacy_item = RAGEvidenceItem(
        item_id=chunk.native_chunk_id,
        native_id=chunk.native_chunk_id,
        rank=1,
        content=chunk.content or "",
    )
    rag_result = RAGResult(
        answer="42",
        raw_retrieval=[legacy_item],
        ranked_retrieval=[legacy_item],
        final_context=[legacy_item],
        trace={
            "wire_v2_native_observation": {
                "observation_status": "observed",
                "adapter_run_result": adapter_result.model_dump(
                    mode="json", exclude_none=True
                ),
                "wire_comparison": {"status": "verified"},
            }
        },
    )
    question = Question(
        case_id=case_id,
        question="What value is recorded?",
        gold_answer_id="answer-1",
        gold_evidence_set_id="gold-1",
    )
    answer = GoldAnswer(
        gold_answer_id="answer-1",
        kind=GoldAnswerKind.NUMERIC,
        canonical="42",
    )
    return question, answer, _gold(("gold-a",)), rag_result


def _resolver(case_ids: tuple[str, ...] = ("case-1",)) -> BenchmarkResolver:
    fixtures = [_observed_fixture(case_id) for case_id in case_ids]
    return BenchmarkResolver(
        questions={item[0].case_id: item[0] for item in fixtures},
        gold_answers={item[1].gold_answer_id: item[1] for item in fixtures},
        gold_evidence_sets={
            item[2].gold_evidence_set_id: item[2] for item in fixtures
        },
    )


def _evaluated_case(
    case_id: str = "case-1",
    *,
    context_budget: int = 4096,
):
    question, answer, gold, rag_result = _observed_fixture(case_id)
    resolved = BenchmarkResolver(
        questions={case_id: question},
        gold_answers={answer.gold_answer_id: answer},
        gold_evidence_sets={gold.gold_evidence_set_id: gold},
    ).resolve(case_id)
    validation = TraceValidator().validate(
        rag_result,
        expected_case_id=case_id,
        expected_adapter_id="adapter-under-test",
        expected_system_id="system-under-test",
    )
    profile = _profile(1).model_copy(
        update={"context_budget": context_budget}
    )
    started = datetime(2026, 9, 8, tzinfo=UTC)
    case = EvaluationEngine(profile).evaluate(
        resolved,
        validation,
        started_at=started,
        completed_at=started + timedelta(seconds=1),
        repetition=1,
        seed=7,
    )
    return resolved, case


def _benchmark_identity(*resolved) -> BenchmarkIdentityV2:
    return BenchmarkIdentityV2.build(
        dataset_release_id="dataset-release-1",
        dataset_release_digest=SHA_C,
        bundle_id=SHA_A,
        case_selection_id="selection-1",
        cases=tuple(resolved),
    )


@pytest.mark.native_v2_characterization
def test_artifact_v2_is_immutable_self_verifying_and_read_without_scorer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved, case = _evaluated_case()
    started = datetime(2026, 9, 8, tzinfo=UTC)
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    writer = ArtifactWriter(run_dir)
    manifest = writer.publish(
        run_id="run-1",
        experiment_id="experiment-1",
        benchmark_identity=_benchmark_identity(resolved),
        cases=(case,),
        started_at=started,
        completed_at=started + timedelta(seconds=2),
    )

    reader = ArtifactV2Reader(run_dir / "artifact-v2")
    assert reader.verify().valid
    assert reader.manifest().artifact_digest == manifest.artifact_digest
    assert manifest.runtime_profiles[0].system_id == "system-under-test"
    assert manifest.observation_profiles[0].adapter_id == "adapter-under-test"
    assert {item.path for item in manifest.checksum_graph.nodes} == {
        "cases/rep-0001-case-1.json",
        "case-index.json",
        "summary.json",
    }
    assert reader.case("case-1").adapter_result is not None
    assert reader.case_index().cases[0].answer_judgment.value == "correct"
    assert reader.summary().leaderboard_eligibility.eligible is True
    store = RunStore(tmp_path)
    assert store.artifact_v2_manifest("run-1") == manifest
    assert store.verify_artifact_v2("run-1").valid

    def forbidden_rescore(*_args, **_kwargs):
        raise AssertionError("artifact read must not call the current scorer")

    monkeypatch.setattr(
        "rag_eval.runs.orchestration.evaluate_unified_trace", forbidden_rescore
    )
    monkeypatch.setattr(
        "rag_eval.runs.orchestration.score_answer", forbidden_rescore
    )
    assert reader.summary().metrics[0].value is not None
    assert reader.case_index().cases[0].core_metrics_available
    assert reader.case("case-1").answer_judgment.value == "correct"
    assert writer.publish(
        run_id="run-1",
        experiment_id="experiment-1",
        benchmark_identity=_benchmark_identity(resolved),
        cases=(case,),
        started_at=started,
        completed_at=started + timedelta(seconds=2),
    ).artifact_digest == manifest.artifact_digest

    case_path = run_dir / "artifact-v2" / "cases" / "rep-0001-case-1.json"
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    payload["question"] = "tampered"
    case_path.write_text(json.dumps(payload), encoding="utf-8")
    verification = reader.verify()
    assert not verification.valid
    assert verification.mismatched == ("cases/rep-0001-case-1.json",)
    with pytest.raises(FileExistsError, match="immutable Artifact 2.0"):
        writer.publish(
            run_id="run-1",
            experiment_id="experiment-1",
            benchmark_identity=_benchmark_identity(resolved),
            cases=(case,),
            started_at=started,
            completed_at=started + timedelta(seconds=2),
        )


@pytest.mark.native_v2_characterization
def test_artifact_v2_persists_an_unobservable_run_without_a_trace(
    tmp_path: Path,
) -> None:
    _, _, _, no_trace = _observed_fixture()
    no_trace = no_trace.model_copy(update={"trace": None})
    resolved = _resolver().resolve("case-1")
    started = datetime(2026, 9, 8, tzinfo=UTC)
    case = EvaluationEngine(_profile(1)).evaluate(
        resolved,
        TraceValidator().validate(no_trace, expected_case_id="case-1"),
        started_at=started,
        completed_at=started + timedelta(seconds=1),
        repetition=1,
        seed=7,
    )

    manifest = ArtifactWriter(tmp_path).publish(
        run_id="run-1",
        experiment_id="experiment-1",
        benchmark_identity=_benchmark_identity(resolved),
        cases=(case,),
        started_at=started,
        completed_at=started + timedelta(seconds=2),
    )
    reader = ArtifactV2Reader(tmp_path / "artifact-v2")

    assert manifest.runtime_profiles == ()
    assert manifest.observation_profiles == ()
    assert reader.verify().valid
    assert reader.summary().leaderboard_eligibility.eligible is False
    assert reader.case("case-1").evaluation.failure is not None
    assert reader.case("case-1").evaluation.failure.kind == FailureKind.UNOBSERVABLE


@pytest.mark.native_v2_characterization
def test_leaderboard_eligibility_uses_persisted_metric_availability_and_descriptors() -> None:
    resolved_a, case_a = _evaluated_case("case-1", context_budget=4096)
    resolved_b, case_b = _evaluated_case("case-2", context_budget=8192)

    one_case = derive_leaderboard_eligibility((case_a,))
    assert one_case.eligible is True
    assert one_case.descriptor_digests

    mismatched = derive_leaderboard_eligibility((case_a, case_b))
    assert mismatched.eligible is False
    assert any("descriptor" in reason for reason in mismatched.reasons)

    _, _, _, no_trace = _observed_fixture("case-3")
    no_trace = no_trace.model_copy(update={"trace": None})
    resolved_c = _resolver(("case-3",)).resolve("case-3")
    unavailable = EvaluationEngine(_profile(1)).evaluate(
        resolved_c,
        TraceValidator().validate(no_trace, expected_case_id="case-3"),
        started_at=datetime(2026, 9, 8, tzinfo=UTC),
        completed_at=datetime(2026, 9, 8, 0, 0, 1, tzinfo=UTC),
        repetition=1,
        seed=7,
    )
    assert all(
        metric.status == EvaluationMetricStatus.UNAVAILABLE
        for metric in unavailable.evaluation.metrics
    )
    assert derive_leaderboard_eligibility((case_a, unavailable)).eligible is False
    assert build_artifact_summary((case_a, unavailable)).metrics
    assert resolved_a.case_id == "case-1"
    assert resolved_b.case_id == "case-2"


def test_trace_validator_fails_closed_without_guessing_or_changing_wire_v1() -> None:
    _, _, _, result = _observed_fixture()
    original = result.model_dump(mode="json")
    validator = TraceValidator()

    observed = validator.validate(result, expected_case_id="case-1")
    assert observed.status == ObservationStatus.OBSERVED
    assert observed.adapter_result is not None

    absent = validator.validate(
        result.model_copy(update={"trace": None}), expected_case_id="case-1"
    )
    assert absent.status == ObservationStatus.UNOBSERVED
    malformed = result.model_copy(
        update={
            "trace": {
                "wire_v2_native_observation": {
                    "observation_status": "observed",
                    "adapter_run_result": {"broken": True},
                }
            }
        }
    )
    assert validator.validate(
        malformed, expected_case_id="case-1"
    ).status == ObservationStatus.CORRUPTED

    assert result.ranked_retrieval is not None
    changed_stage = result.model_copy(
        update={
            "ranked_retrieval": [
                result.ranked_retrieval[0].model_copy(update={"content": "changed"})
            ]
        }
    )
    assert validator.validate(
        changed_stage, expected_case_id="case-1"
    ).status == ObservationStatus.CORRUPTED
    assert validator.validate(
        result, expected_case_id="different"
    ).status == ObservationStatus.CORRUPTED
    assert result.model_dump(mode="json") == original


@pytest.mark.native_v2_characterization
def test_named_v2_orchestration_flow_queries_once_and_never_sends_gold() -> None:
    _, _, _, result = _observed_fixture()

    class Client:
        def __init__(self) -> None:
            self.calls: list[RAGQuery] = []

        def query(self, query: RAGQuery) -> RAGResult:
            self.calls.append(query)
            return result

    client = Client()
    flow = NativeCaseOrchestrator(
        benchmark_resolver=_resolver(),
        adapter_session=AdapterSession(client),
        trace_validator=TraceValidator(),
        evaluation_engine=EvaluationEngine(_profile(1)),
    )
    outcome = flow.execute(
        case_id="case-1",
        query=RAGQuery(case_id="case-1", question="What value is recorded?"),
        repetition=1,
        seed=7,
    )

    assert len(client.calls) == 1
    assert set(client.calls[0].model_dump()) == {
        "case_id",
        "question",
        "generate_answer",
        "retrieval_candidate_k",
        "final_context_k",
        "max_context_tokens",
        "generation_options",
    }
    assert outcome.artifact_case.observation_status == ObservationStatus.OBSERVED
    assert outcome.artifact_case.evaluation.core_metrics_available


def test_legacy_executor_shadows_one_query_without_changing_case_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    question, answer, gold, result = _observed_fixture()

    class Client:
        def __init__(self) -> None:
            self.calls = 0

        def query(self, query: RAGQuery) -> RAGResult:
            assert query.case_id == question.case_id
            self.calls += 1
            return result

    class Bundle:
        gold_answers: ClassVar = {answer.gold_answer_id: answer}
        gold_evidence_sets: ClassVar = {gold.gold_evidence_set_id: gold}

    ticks = iter((0.0, 0.5, 1.0, 1.5))
    monkeypatch.setattr(
        "rag_eval.runs.orchestration.monotonic", lambda: next(ticks)
    )
    capabilities = AdapterCapabilities(
        answer=True,
        raw_retrieval=True,
        ranked_retrieval=True,
        final_context=True,
    )
    experiment = ExperimentSpec(
        experiment_id="experiment-1",
        bundle_id=SHA_A,
        system_id="system-under-test",
        adapter_id="adapter-under-test",
        query_config={
            "retrieval_candidate_k": 1,
            "final_context_k": 1,
            "max_context_tokens": 4096,
        },
        case_selection_id="selection-1",
    )
    corpus = CorpusEvidenceIndex({})
    legacy_client = Client()
    legacy_case = execute_case(
        legacy_client,
        capabilities,
        question,
        Bundle(),  # type: ignore[arg-type]
        corpus,
        experiment,
        lambda: False,
        1,
        7,
    )
    persisted = []
    shadow_client = Client()
    case = execute_case(
        shadow_client,
        capabilities,
        question,
        Bundle(),  # type: ignore[arg-type]
        corpus,
        experiment,
        lambda: False,
        1,
        7,
        artifact_v2_profile=_profile(1),
        artifact_v2_cases=persisted,
        expected_adapter_id="adapter-under-test",
        expected_adapter_version="1",
        expected_system_id="system-under-test",
        expected_system_version="1",
    )

    assert case.status == "completed"
    assert legacy_client.calls == shadow_client.calls == 1
    assert legacy_case.model_dump(
        mode="json", exclude={"started_at", "completed_at"}
    ) == case.model_dump(mode="json", exclude={"started_at", "completed_at"})
    assert len(persisted) == 1
    assert persisted[0].evaluation.core_metrics_available


@pytest.mark.native_v2_characterization
def test_run_v2_core_has_no_rag_or_corpus_mode_branches() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "rag_eval" / "runs"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(root.glob("*.py"))
    ).lower()

    for forbidden in (
        "lightrag",
        "rag-anything",
        "rag_anything",
        "evaluation_corpus",
        "canonical_segments",
        "benchmark_segments",
    ):
        assert forbidden not in source


def test_artifact_1_2_reader_remains_unchanged_when_v2_is_absent(
    tmp_path: Path,
) -> None:
    store = RunStore(tmp_path / "runs")
    manifest = legacy_manifest()
    run_dir = store.root / manifest.run_id
    run_dir.mkdir(parents=True)
    source = run_dir / "run.json"
    source.write_text(manifest.model_dump_json(), encoding="utf-8")
    original = source.read_bytes()

    with pytest.raises(FileNotFoundError):
        ArtifactV2Reader(run_dir / "artifact-v2").manifest()
    assert store.get(manifest.run_id) == manifest
    assert source.read_bytes() == original
