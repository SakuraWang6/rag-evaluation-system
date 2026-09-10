from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from rag_eval.adapters.native_observation import unavailable_native_result
from rag_eval.contracts.benchmark import (
    BenchmarkAnswerKindV2,
    BenchmarkAnswerV2,
    BenchmarkCaseV2,
)
from rag_eval.contracts.native import (
    IngestionReceiptV2,
    NativeQueryV2,
    PreparedSystemV2,
)
from rag_eval.contracts.observation import (
    AdapterRunResultV2,
    ObservationStatus,
    UnifiedTrace,
)
from rag_eval.evaluation.unified import EvaluationMetricStatus, FailureKind
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
from tests.rag_eval_platform.test_unified_evaluation_v2 import (
    SHA_A,
    SHA_B,
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
    gold = _gold(("gold-a",)).model_copy(
        update={
            "case_id": case_id,
            "case_revision_id": f"{case_id}-revision-1",
            "answer": BenchmarkAnswerV2(
                kind=BenchmarkAnswerKindV2.NUMERIC,
                canonical="42",
            ),
        }
    )
    benchmark_case = BenchmarkCaseV2(
        case_id=case_id,
        case_revision_id=f"{case_id}-revision-1",
        target_id=f"target-{case_id}",
        question="What value is recorded?",
        language="en",
        source_object_ids=("gold-a",),
        gold=gold,
    )
    return benchmark_case, benchmark_case.gold.answer, benchmark_case.gold, adapter_result


def _prepared_fixture(result: AdapterRunResultV2) -> PreparedSystemV2:
    receipt = IngestionReceiptV2.build(
        document_id=result.trace.source_identity.document_id,
        source_sha256=result.trace.source_identity.source_sha256,
        index_fingerprint="fixture-index",
    )
    return PreparedSystemV2.build(
        effective_config={"fixture": "direct-wire-v2"},
        source_identity=result.trace.source_identity,
        runtime_profile=result.trace.runtime_profile,
        observation_profile=result.trace.observation_profile,
        ingestion_receipt=receipt,
    )


def _native_query(case_id: str = "case-1") -> NativeQueryV2:
    return NativeQueryV2(
        case_id=case_id,
        question="What value is recorded?",
        generate_answer=True,
        retrieval_candidate_k=5,
        final_context_k=1,
        max_context_tokens=4096,
        generation_options={},
    )


def _resolver(case_ids: tuple[str, ...] = ("case-1",)) -> BenchmarkResolver:
    fixtures = [_observed_fixture(case_id) for case_id in case_ids]
    return BenchmarkResolver(
        cases={item[0].case_id: item[0] for item in fixtures},
    )


def _evaluated_case(
    case_id: str = "case-1",
    *,
    context_budget: int = 4096,
):
    benchmark_case, _answer, _gold_value, adapter_result = _observed_fixture(case_id)
    resolved = BenchmarkResolver(cases={case_id: benchmark_case}).resolve(case_id)
    validation = TraceValidator().validate(
        adapter_result,
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
    return BenchmarkIdentityV2(
        release_id="dataset-release-1",
        release_digest=SHA_C,
        validation_report_digest=SHA_A,
        payload_snapshot_digest=SHA_B,
        case_selection_id=SHA_A,
        benchmark_snapshot_digest=SHA_C,
        source_identity=resolved[0].gold.source_identity,
    )


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


def test_artifact_v2_persists_an_unobservable_direct_v2_result(
    tmp_path: Path,
) -> None:
    _, _, _, observed = _observed_fixture()
    no_trace = unavailable_native_result(
        prepared=_prepared_fixture(observed),
        query=_native_query(),
        status=ObservationStatus.UNOBSERVED,
        reason="fixture cannot observe native retrieval",
        answer=None,
    )
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

    assert len(manifest.runtime_profiles) == 1
    assert len(manifest.observation_profiles) == 1
    assert reader.verify().valid
    assert reader.summary().leaderboard_eligibility.eligible is False
    assert reader.case("case-1").evaluation.failure is not None
    assert reader.case("case-1").evaluation.failure.kind == FailureKind.UNOBSERVABLE

    retrieval_only = unavailable_native_result(
        prepared=_prepared_fixture(observed),
        query=_native_query().model_copy(update={"generate_answer": False}),
        status=ObservationStatus.UNOBSERVED,
        reason="fixture cannot observe native retrieval",
        answer=None,
    )
    assert retrieval_only.trace.answer.observation_status == (
        ObservationStatus.UNOBSERVED
    )


def test_leaderboard_eligibility_uses_persisted_metric_availability_and_descriptors() -> None:
    resolved_a, case_a = _evaluated_case("case-1", context_budget=4096)
    resolved_b, case_b = _evaluated_case("case-2", context_budget=8192)

    one_case = derive_leaderboard_eligibility((case_a,))
    assert one_case.eligible is True
    assert one_case.descriptor_digests

    mismatched = derive_leaderboard_eligibility((case_a, case_b))
    assert mismatched.eligible is False
    assert any("descriptor" in reason for reason in mismatched.reasons)

    _, _, _, observed = _observed_fixture("case-3")
    no_trace = unavailable_native_result(
        prepared=_prepared_fixture(observed),
        query=_native_query("case-3"),
        status=ObservationStatus.UNOBSERVED,
        reason="fixture cannot observe native retrieval",
        answer=None,
    )
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


def test_trace_validator_fails_closed_on_direct_v2_identity_mismatch() -> None:
    _, _, _, result = _observed_fixture()
    original = result.model_dump(mode="json")
    validator = TraceValidator()

    observed = validator.validate(result, expected_case_id="case-1")
    assert observed.status == ObservationStatus.OBSERVED
    assert observed.adapter_result is not None

    mismatched = result.model_copy(update={"adapter_id": "different-adapter"})
    assert validator.validate(
        mismatched,
        expected_case_id="case-1",
        expected_adapter_id="adapter-under-test",
    ).status == ObservationStatus.CORRUPTED
    assert validator.validate(
        result, expected_case_id="different"
    ).status == ObservationStatus.CORRUPTED
    assert result.model_dump(mode="json") == original


def test_named_v2_orchestration_flow_queries_once_and_never_sends_gold() -> None:
    _, _, _, result = _observed_fixture()

    class Client:
        def __init__(self) -> None:
            self.calls: list[tuple[PreparedSystemV2, NativeQueryV2]] = []

        def query(
            self,
            prepared_system: PreparedSystemV2,
            query: NativeQueryV2,
        ) -> AdapterRunResultV2:
            self.calls.append((prepared_system, query))
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
        prepared_system=_prepared_fixture(result),
        query=_native_query(),
        repetition=1,
        seed=7,
    )

    assert len(client.calls) == 1
    assert set(client.calls[0][1].model_dump()) == {
        "schema_version",
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
