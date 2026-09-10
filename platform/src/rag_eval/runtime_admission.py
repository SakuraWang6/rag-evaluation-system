"""Strict admission and immutable plan resolution for Native v2 Runs."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from rag_eval.artifact_contract import artifact_digest
from rag_eval.contracts.benchmark import (
    NativeBenchmarkReleaseV2,
    benchmark_case_selection_id,
)
from rag_eval.contracts.run import ExperimentSpec
from rag_eval.evaluation.unified.models import EvaluationProfile
from rag_eval.runs.plans import (
    BenchmarkReleaseIdentityV2,
    NativeMetricConfigV2,
    NativeQueryConfigV2,
    OriginalDocumentIdentityV2,
    ResolvedResourceLimitsV2,
    ResolvedRunPlanV2,
    ResolvedSystemIdentityV2,
    digest_json,
    formal_metric_descriptors,
)

_CORPUS_SELECTOR = "evaluation_corpus"


class NewRunAdmissionError(ValueError):
    """A new public Run violates the native-document execution contract."""


def require_no_public_corpus_selector(config: Mapping[str, object]) -> None:
    """Keep the native route owned by the Platform, not caller configuration."""

    if _CORPUS_SELECTOR in config:
        raise NewRunAdmissionError(
            "evaluation_corpus is reserved by the Platform; new evaluations "
            "always use native source documents"
        )


def admit_new_public_experiment(
    experiment: ExperimentSpec,
    benchmark: NativeBenchmarkReleaseV2,
    *,
    system_identity: ResolvedSystemIdentityV2,
) -> ResolvedRunPlanV2:
    """Validate every public boundary and resolve its immutable Native v2 plan."""

    require_no_public_corpus_selector(experiment.adapter_config)
    if experiment.dataset_release_id != benchmark.release_id:
        raise NewRunAdmissionError(
            "Experiment does not match the resolved immutable Benchmark Release"
        )

    if system_identity.system_id != experiment.system_id:
        raise NewRunAdmissionError(
            "resolved system identity does not match the Experiment"
        )
    if system_identity.adapter_id != experiment.adapter_id:
        raise NewRunAdmissionError(
            "resolved Adapter identity does not match the Experiment"
        )

    try:
        query_config = NativeQueryConfigV2.model_validate(experiment.query_config)
    except ValidationError as exc:
        raise NewRunAdmissionError(f"invalid query_config: {exc}") from exc
    try:
        metric_config = NativeMetricConfigV2.model_validate(experiment.metric_config)
    except ValidationError as exc:
        raise NewRunAdmissionError(f"invalid metric_config: {exc}") from exc

    selected_case_ids = sorted(
        benchmark.case_ids if experiment.case_ids is None else experiment.case_ids
    )
    if not selected_case_ids:
        raise NewRunAdmissionError("resolved Run must select at least one case")
    unknown = sorted(set(selected_case_ids) - set(benchmark.case_ids))
    if unknown:
        raise NewRunAdmissionError(
            f"Experiment references unknown cases: {unknown}"
        )
    if len(selected_case_ids) != len(set(selected_case_ids)):
        raise NewRunAdmissionError("Experiment case_ids must be unique")
    expected_selection_id = benchmark_case_selection_id(
        selected_case_ids,
        policy="explicit" if experiment.case_ids is not None else "all",
        seed=experiment.seed,
    )
    if (
        expected_selection_id != experiment.case_selection_id
        or benchmark.case_selection_id != experiment.case_selection_id
        or tuple(selected_case_ids) != benchmark.case_ids
    ):
        raise NewRunAdmissionError(
            "case_selection_id does not match selected cases/policy/seed"
        )

    evaluation_profile = EvaluationProfile(
        candidate_cutoff=query_config.retrieval_candidate_k,
        ranked_cutoffs=(1, 3, 5),
        ranked_mrr_cutoff=5,
        context_budget=query_config.max_context_tokens,
    )
    return ResolvedRunPlanV2(
        experiment_id=experiment.experiment_id,
        experiment_digest=artifact_digest(experiment),
        benchmark_release=BenchmarkReleaseIdentityV2(
            release_id=benchmark.release_id,
            release_digest=benchmark.release_digest,
            validation_report_digest=benchmark.validation_report_digest,
            payload_snapshot_digest=benchmark.payload_snapshot_digest,
            benchmark_snapshot_digest=benchmark.snapshot_digest,
        ),
        original_document=OriginalDocumentIdentityV2(
            document_id=benchmark.source_identity.document_id,
            source_sha256=benchmark.source_identity.source_sha256,
            canonical_digest=benchmark.source_identity.canonical_digest,
            canonical_catalog_sha256=(
                benchmark.source_identity.canonical_catalog_sha256
            ),
            mime_type=benchmark.source_identity.media_type,
        ),
        system=system_identity,
        adapter_config_digest=digest_json(experiment.adapter_config),
        query_config=query_config,
        metric_config=metric_config,
        evaluation_profile=evaluation_profile,
        metric_descriptors=formal_metric_descriptors(evaluation_profile),
        case_ids=tuple(selected_case_ids),
        case_selection_id=experiment.case_selection_id,
        seed=experiment.seed,
        repetitions=experiment.repetitions,
        resource_limits=ResolvedResourceLimitsV2(
            worker_request_timeout_seconds=(
                system_identity.worker_request_timeout_seconds
            ),
            max_context_tokens=query_config.max_context_tokens,
        ),
    )


__all__ = [
    "NewRunAdmissionError",
    "admit_new_public_experiment",
    "require_no_public_corpus_selector",
]
