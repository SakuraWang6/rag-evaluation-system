"""Native v2 case flow from Benchmark resolution through persisted evaluation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Protocol

from pydantic import ValidationError

from rag_eval.artifact_contract import artifact_digest
from rag_eval.contracts.adapter import RAGEvidenceItem, RAGQuery, RAGResult
from rag_eval.contracts.dataset import GoldAnswer, GoldEvidenceSet, Question
from rag_eval.contracts.observation import (
    AdapterRunResultV2,
    ObservationStatus,
    StageName,
)
from rag_eval.evaluation.answers import AnswerVerdict, score_answer
from rag_eval.evaluation.unified.models import (
    FORMAL_CORE_METRIC_IDS,
    UNIFIED_SCORER_ID,
    UNIFIED_SCORER_VERSION,
    EvaluationMetric,
    EvaluationMetricStatus,
    EvaluationProfile,
    FailureKind,
    MetricDescriptor,
    ProofGatedFailure,
)
from rag_eval.evaluation.unified.proofs import EPSILON, same
from rag_eval.evaluation.unified.scorer import (
    evaluate_unified_trace,
    scorer_source_digest,
)
from rag_eval.runs.models import (
    ArtifactAnswerJudgment,
    ArtifactAnswerStatus,
    ArtifactCaseErrorV2,
    ArtifactEvidenceJudgment,
    ArtifactEvidenceStatus,
    BenchmarkCaseSnapshotV2,
    BenchmarkIdentityV2,
    PersistedEvaluationV2,
    RunArtifactCaseV2,
    TraceValidationRecordV2,
)

WIRE_V2_OBSERVATION_KEY = "wire_v2_native_observation"


class AdapterQueryClient(Protocol):
    def query(self, query: RAGQuery) -> RAGResult: ...


class BenchmarkResolver:
    """Resolve Platform-owned Case, Answer, and Gold without Adapter input."""

    def __init__(
        self,
        *,
        questions: Mapping[str, Question],
        gold_answers: Mapping[str, GoldAnswer],
        gold_evidence_sets: Mapping[str, GoldEvidenceSet],
    ) -> None:
        self._questions = dict(questions)
        self._gold_answers = dict(gold_answers)
        self._gold_evidence_sets = dict(gold_evidence_sets)

    def resolve(self, case_id: str) -> BenchmarkCaseSnapshotV2:
        question = self._questions[case_id]
        answer = self._gold_answers[question.gold_answer_id]
        evidence = self._gold_evidence_sets[question.gold_evidence_set_id]
        return BenchmarkCaseSnapshotV2(
            case_id=question.case_id,
            question=question.question,
            gold_answer=answer,
            gold_evidence_set=evidence,
        )


class AdapterSession:
    """Invoke one already-prepared Adapter without exposing Gold to it."""

    def __init__(
        self,
        client: AdapterQueryClient,
        *,
        validate_response: Callable[[RAGResult], None] | None = None,
    ) -> None:
        self._client = client
        self._validate_response = validate_response

    def query(self, query: RAGQuery) -> RAGResult:
        started = monotonic()
        result = self._client.query(query)
        if self._validate_response is not None:
            self._validate_response(result)
        latency = dict(result.latency or {})
        latency["end_to_end_query_latency"] = monotonic() - started
        return result.model_copy(update={"latency": latency})


@dataclass(frozen=True, slots=True)
class TraceValidationResult:
    record: TraceValidationRecordV2
    adapter_result: AdapterRunResultV2 | None = None

    @property
    def status(self) -> ObservationStatus:
        return self.record.status


class TraceValidator:
    """Validate the additive Wire 2.0 envelope and its Wire 1.0 shadow."""

    def validate(
        self,
        result: RAGResult,
        *,
        expected_case_id: str,
        expected_adapter_id: str | None = None,
        expected_adapter_version: str | None = None,
        expected_system_id: str | None = None,
        expected_system_version: str | None = None,
    ) -> TraceValidationResult:
        trace = result.trace
        if not isinstance(trace, Mapping):
            return self._unavailable(
                ObservationStatus.UNOBSERVED,
                "Adapter response contains no Wire 2.0 observation envelope",
            )
        envelope = trace.get(WIRE_V2_OBSERVATION_KEY)
        if not isinstance(envelope, Mapping):
            return self._unavailable(
                ObservationStatus.UNOBSERVED,
                "Adapter response did not publish a Wire 2.0 observation",
            )
        raw_status = envelope.get("observation_status")
        try:
            status = ObservationStatus(str(raw_status))
        except ValueError:
            return self._unavailable(
                ObservationStatus.CORRUPTED,
                "Wire 2.0 envelope has an invalid observation status",
            )
        if status != ObservationStatus.OBSERVED:
            reason = envelope.get("reason")
            return self._unavailable(
                status,
                str(reason or f"Adapter reported {status.value} observation"),
            )
        payload = envelope.get("adapter_run_result")
        try:
            adapter_result = AdapterRunResultV2.model_validate(payload)
        except (TypeError, ValidationError, ValueError) as exc:
            return self._unavailable(
                ObservationStatus.CORRUPTED,
                f"Wire 2.0 Adapter result failed contract validation: {exc}",
            )
        identity_error = self._identity_error(
            adapter_result,
            expected_case_id=expected_case_id,
            expected_adapter_id=expected_adapter_id,
            expected_adapter_version=expected_adapter_version,
            expected_system_id=expected_system_id,
            expected_system_version=expected_system_version,
        )
        if identity_error:
            return self._unavailable(ObservationStatus.CORRUPTED, identity_error)
        comparison = envelope.get("wire_comparison")
        wire_shadow_verified = False
        if comparison is not None:
            if not isinstance(comparison, Mapping) or comparison.get("status") != "verified":
                return self._unavailable(
                    ObservationStatus.CORRUPTED,
                    "Wire 1.0/Wire 2.0 comparison is not verified",
                )
            wire_shadow_verified = True
        mismatch = self._wire_shadow_mismatch(
            result,
            adapter_result,
            require_shadow=wire_shadow_verified,
        )
        if mismatch:
            return self._unavailable(ObservationStatus.CORRUPTED, mismatch)
        return TraceValidationResult(
            record=TraceValidationRecordV2(
                status=ObservationStatus.OBSERVED,
                adapter_result_digest=artifact_digest(adapter_result),
                wire_shadow_verified=wire_shadow_verified,
            ),
            adapter_result=adapter_result,
        )

    @staticmethod
    def _identity_error(
        result: AdapterRunResultV2,
        *,
        expected_case_id: str,
        expected_adapter_id: str | None,
        expected_adapter_version: str | None,
        expected_system_id: str | None,
        expected_system_version: str | None,
    ) -> str | None:
        expected = (
            ("case", expected_case_id, result.trace.case_id),
            ("Adapter", expected_adapter_id, result.adapter_id),
            ("Adapter version", expected_adapter_version, result.adapter_version),
            ("system", expected_system_id, result.system_id),
            ("system version", expected_system_version, result.system_version),
        )
        for label, wanted, actual in expected:
            if wanted is not None and wanted != actual:
                return f"Wire 2.0 {label} identity differs from the Run"
        return None

    @classmethod
    def _wire_shadow_mismatch(
        cls,
        legacy: RAGResult,
        observed: AdapterRunResultV2,
        *,
        require_shadow: bool,
    ) -> str | None:
        pairs = (
            ("candidate", legacy.raw_retrieval, observed.trace.raw_retrieval),
            ("ranked", legacy.ranked_retrieval, observed.trace.ranked_retrieval),
            ("context", legacy.final_context, observed.trace.final_context),
        )
        for label, legacy_items, observation in pairs:
            if observation.observation_status != ObservationStatus.OBSERVED:
                continue
            if legacy_items is None:
                if require_shadow:
                    return f"Wire 1.0 {label} items are absent from a verified shadow"
                continue
            left = tuple(cls._legacy_item_identity(item) for item in legacy_items)
            right = tuple(
                (
                    item.native_chunk_id,
                    item.native_rank,
                    item.content,
                    item.runtime_score,
                )
                for item in observation.items
            )
            if left != right:
                return f"Wire 1.0 and Wire 2.0 {label} items differ"
        answer = observed.trace.answer
        if (
            answer.observation_status == ObservationStatus.OBSERVED
            and legacy.answer is None
            and require_shadow
        ):
            return "Wire 1.0 answer is absent from a verified shadow"
        if (
            answer.observation_status == ObservationStatus.OBSERVED
            and legacy.answer is not None
            and answer.content != legacy.answer
        ):
            return "Wire 1.0 and Wire 2.0 answers differ"
        return None

    @staticmethod
    def _legacy_item_identity(
        item: RAGEvidenceItem,
    ) -> tuple[str, int, str, float | None]:
        return (
            item.native_id or item.item_id,
            item.rank,
            item.content,
            item.score,
        )

    @staticmethod
    def _unavailable(
        status: ObservationStatus, reason: str
    ) -> TraceValidationResult:
        return TraceValidationResult(
            record=TraceValidationRecordV2(status=status, reason=reason)
        )


class EvaluationEngine:
    """Persist the exact Unified Evaluation result or honest unavailability."""

    def __init__(self, profile: EvaluationProfile) -> None:
        self.profile = profile

    def evaluate(
        self,
        benchmark: BenchmarkCaseSnapshotV2,
        validation: TraceValidationResult,
        *,
        started_at: datetime,
        completed_at: datetime,
        repetition: int,
        seed: int,
        status: str = "completed",
        error: ArtifactCaseErrorV2 | None = None,
    ) -> RunArtifactCaseV2:
        adapter_result = validation.adapter_result
        if adapter_result is None:
            evaluation = self._unavailable_evaluation(
                benchmark.gold_evidence_set,
                validation.record.reason or "Unified Trace is unavailable",
            )
            answer_judgment = ArtifactAnswerJudgment(
                status=ArtifactAnswerStatus.UNAVAILABLE,
                reason=validation.record.reason,
            )
            evidence_judgment = ArtifactEvidenceJudgment(
                status=ArtifactEvidenceStatus.UNAVAILABLE,
                reason=validation.record.reason,
            )
        else:
            unified = evaluate_unified_trace(
                benchmark.gold_evidence_set,
                adapter_result.trace,
                profile=self.profile,
                gold_answer=benchmark.gold_answer,
            )
            evaluation = PersistedEvaluationV2.from_unified(unified)
            answer_judgment = self._answer_judgment(
                benchmark.gold_answer, adapter_result
            )
            evidence_judgment = self._evidence_judgment(evaluation)
        return RunArtifactCaseV2.build(
            case_id=benchmark.case_id,
            repetition=repetition,
            seed=seed,
            status=status,
            question=benchmark.question,
            gold_answer=benchmark.gold_answer,
            gold_evidence_set=benchmark.gold_evidence_set,
            trace_validation=validation.record,
            adapter_result=adapter_result,
            evaluation=evaluation,
            answer_judgment=answer_judgment,
            evidence_judgment=evidence_judgment,
            error=error,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _unavailable_evaluation(
        self, gold: GoldEvidenceSet, reason: str
    ) -> PersistedEvaluationV2:
        digest = scorer_source_digest()
        metrics = tuple(
            EvaluationMetric(
                metric_id=metric_id,
                status=EvaluationMetricStatus.UNAVAILABLE,
                lower_bound=0,
                upper_bound=1,
                descriptor=MetricDescriptor(
                    metric_id=metric_id,
                    scorer_digest=digest,
                    aggregation="mses_clause_equal_weight",
                    stage=StageName.RANKED,
                    cutoff=int(metric_id.rsplit("@", 1)[1]),
                    candidate_cutoff=self.profile.candidate_cutoff,
                    ranked_cutoff=int(metric_id.rsplit("@", 1)[1]),
                    context_budget=self.profile.context_budget,
                ),
                reason=reason,
            )
            for metric_id in FORMAL_CORE_METRIC_IDS
        )
        return PersistedEvaluationV2(
            scorer_id=UNIFIED_SCORER_ID,
            scorer_version=UNIFIED_SCORER_VERSION,
            scorer_digest=digest,
            gold_evidence_set_id=gold.gold_evidence_set_id,
            metrics=metrics,
            failure=ProofGatedFailure(
                kind=FailureKind.UNOBSERVABLE,
                reason=reason,
            ),
        )

    @staticmethod
    def _answer_judgment(
        gold: GoldAnswer, result: AdapterRunResultV2
    ) -> ArtifactAnswerJudgment:
        observation = result.trace.answer
        if observation.observation_status != ObservationStatus.OBSERVED:
            return ArtifactAnswerJudgment(
                status=ArtifactAnswerStatus.UNAVAILABLE,
                reason=observation.reason or "answer is not observed",
            )
        answer = score_answer(observation.content, gold)
        if answer.verdict == AnswerVerdict.NEEDS_REVIEW:
            return ArtifactAnswerJudgment(
                status=ArtifactAnswerStatus.NEEDS_REVIEW,
                reason=answer.reason,
            )
        return ArtifactAnswerJudgment(
            status=ArtifactAnswerStatus.OBSERVED,
            value=(
                "correct" if answer.verdict == AnswerVerdict.PASS else "incorrect"
            ),
            reason=answer.reason,
        )

    @staticmethod
    def _evidence_judgment(
        evaluation: PersistedEvaluationV2,
    ) -> ArtifactEvidenceJudgment:
        context = next(
            (
                item
                for item in evaluation.localizations
                if item.stage == StageName.CONTEXT
            ),
            None,
        )
        if context is None or not (
            same(context.coverage_lower, context.coverage_upper)
            and same(
                context.complete_recall_lower,
                context.complete_recall_upper,
            )
        ):
            return ArtifactEvidenceJudgment(
                status=ArtifactEvidenceStatus.UNAVAILABLE,
                reason=(context.reason if context is not None else "context is unlocalized"),
            )
        if context.complete_recall_lower >= 1 - EPSILON:
            value = "complete"
        elif context.coverage_lower > EPSILON:
            value = "partial"
        else:
            value = "missing"
        return ArtifactEvidenceJudgment(
            status=ArtifactEvidenceStatus.OBSERVED,
            value=value,
        )


@dataclass(frozen=True, slots=True)
class NativeCaseOutcome:
    rag_result: RAGResult
    artifact_case: RunArtifactCaseV2
    validation: TraceValidationResult


class NativeCaseOrchestrator:
    """Compose the five Phase 6 boundaries for one native case."""

    def __init__(
        self,
        *,
        benchmark_resolver: BenchmarkResolver,
        adapter_session: AdapterSession,
        trace_validator: TraceValidator,
        evaluation_engine: EvaluationEngine,
        expected_adapter_id: str | None = None,
        expected_adapter_version: str | None = None,
        expected_system_id: str | None = None,
        expected_system_version: str | None = None,
    ) -> None:
        self.benchmark_resolver = benchmark_resolver
        self.adapter_session = adapter_session
        self.trace_validator = trace_validator
        self.evaluation_engine = evaluation_engine
        self.expected_adapter_id = expected_adapter_id
        self.expected_adapter_version = expected_adapter_version
        self.expected_system_id = expected_system_id
        self.expected_system_version = expected_system_version

    def execute(
        self,
        *,
        case_id: str,
        query: RAGQuery,
        postprocess: Callable[[RAGResult], RAGResult] | None = None,
        repetition: int,
        seed: int,
        started_at: datetime | None = None,
    ) -> NativeCaseOutcome:
        started = started_at or datetime.now(UTC)
        benchmark = self.benchmark_resolver.resolve(case_id)
        result = self.adapter_session.query(query)
        if postprocess is not None:
            result = postprocess(result)
        validation = self.trace_validator.validate(
            result,
            expected_case_id=case_id,
            expected_adapter_id=self.expected_adapter_id,
            expected_adapter_version=self.expected_adapter_version,
            expected_system_id=self.expected_system_id,
            expected_system_version=self.expected_system_version,
        )
        artifact_case = self.evaluation_engine.evaluate(
            benchmark,
            validation,
            started_at=started,
            completed_at=datetime.now(UTC),
            repetition=repetition,
            seed=seed,
        )
        return NativeCaseOutcome(
            rag_result=result,
            artifact_case=artifact_case,
            validation=validation,
        )


def evaluation_profile_from_query_config(
    query_config: Mapping[str, Any],
) -> EvaluationProfile | None:
    """Resolve only Platform query fields; Adapter defaults are never cutoffs."""

    candidate = query_config.get("retrieval_candidate_k")
    context_budget = query_config.get("max_context_tokens")
    if isinstance(candidate, bool) or not isinstance(candidate, int) or candidate < 1:
        return None
    if (
        isinstance(context_budget, bool)
        or not isinstance(context_budget, int)
        or context_budget < 1
    ):
        return None
    return EvaluationProfile(
        candidate_cutoff=candidate,
        ranked_cutoffs=(1, 3, 5),
        ranked_mrr_cutoff=5,
        context_budget=context_budget,
    )


def benchmark_identity_from_release_metadata(
    *,
    bundle_id: str,
    case_selection_id: str,
    dataset_release_id: str | None,
    metadata: Mapping[str, Any],
    document_sources: Mapping[str, str],
    cases: tuple[RunArtifactCaseV2, ...],
) -> BenchmarkIdentityV2 | None:
    """Resolve only an immutable formal Release; never invent a Benchmark ID."""

    projection = metadata.get("formal_runtime_projection")
    if dataset_release_id is None or not isinstance(projection, Mapping):
        return None
    release_id = projection.get("release_id")
    release_digest = projection.get("release_digest")
    if release_id != dataset_release_id:
        return None
    if not isinstance(release_digest, str):
        return None
    snapshots = {
        case.case_id: BenchmarkCaseSnapshotV2(
            case_id=case.case_id,
            question=case.question,
            gold_answer=case.gold_answer,
            gold_evidence_set=case.gold_evidence_set,
        )
        for case in cases
    }
    for snapshot in snapshots.values():
        for source in snapshot.gold_evidence_set.source_identities:
            if document_sources.get(source.document_id) != source.source_sha256:
                raise ValueError(
                    "Canonical Gold source identity differs from the Bundle source"
                )
    return BenchmarkIdentityV2.build(
        dataset_release_id=dataset_release_id,
        dataset_release_digest=release_digest,
        bundle_id=bundle_id,
        case_selection_id=case_selection_id,
        cases=tuple(snapshots[key] for key in sorted(snapshots)),
    )


__all__ = [
    "AdapterSession",
    "BenchmarkResolver",
    "EvaluationEngine",
    "NativeCaseOrchestrator",
    "NativeCaseOutcome",
    "TraceValidationResult",
    "TraceValidator",
    "benchmark_identity_from_release_metadata",
    "evaluation_profile_from_query_config",
]
