"""Strict admission and immutable plan resolution for Native v2 Runs."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from rag_eval.artifact_contract import artifact_digest
from rag_eval.contracts.run import ExperimentSpec
from rag_eval.datasets.bundle import DatasetBundle, case_selection_id
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

NATIVE_DOCUMENT_EXECUTION_CONTRACT = "native-document/v2"
DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_CORPUS_SELECTOR = "evaluation_corpus"
_PRESEGMENTED_CORPORA = {
    "canonical_segments",
    "canonical-segments/v1",
    "benchmark_segments",
    "benchmark-segments/v1",
}


class NewRunAdmissionError(ValueError):
    """A new public Run violates the native-document execution contract."""


class _ReleaseDocumentIdentity(Protocol):
    document_id: str
    source_digest: str


class _DatasetReleaseIdentity(Protocol):
    release_id: str
    release_digest: str
    validation_report_digest: str
    document: _ReleaseDocumentIdentity


class _DatasetReleaseStore(Protocol):
    def get(self, release_id: str) -> _DatasetReleaseIdentity: ...


def require_no_public_corpus_selector(config: Mapping[str, object]) -> None:
    """Keep the native route owned by the Platform, not caller configuration."""

    if _CORPUS_SELECTOR in config:
        raise NewRunAdmissionError(
            "evaluation_corpus is reserved by the Platform; new evaluations "
            "always use native source documents"
        )


def admit_new_public_experiment(
    experiment: ExperimentSpec,
    bundle: DatasetBundle,
    *,
    system_identity: ResolvedSystemIdentityV2,
    release_store: _DatasetReleaseStore | None = None,
    expected_runtime_bundle_id: str | None = None,
) -> ResolvedRunPlanV2:
    """Validate every public boundary and resolve its immutable Native v2 plan."""

    require_no_public_corpus_selector(experiment.adapter_config)
    metadata = bundle.manifest.metadata
    declared_corpus = metadata.get("primary_evaluation_corpus")
    if isinstance(declared_corpus, str) and declared_corpus in _PRESEGMENTED_CORPORA:
        raise NewRunAdmissionError(
            "pre-segmented Bundle corpora cannot create new Runs; use the "
            "release-pinned native DOCX route"
        )
    if declared_corpus not in (None, "source_document", "native_source"):
        raise NewRunAdmissionError(
            f"unsupported legacy corpus declaration {declared_corpus!r}"
        )

    if experiment.dataset_release_id is None:
        raise NewRunAdmissionError(
            "new public Runs require an immutable Benchmark Release"
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

    if release_store is None:
        raise NewRunAdmissionError(
            "Benchmark Release verification is unavailable in this Platform mode"
        )
    try:
        release = release_store.get(experiment.dataset_release_id)
    except (OSError, ValueError) as exc:
        raise NewRunAdmissionError(
            "selected Benchmark Release is unavailable or invalid"
        ) from exc
    if expected_runtime_bundle_id is None:
        raise NewRunAdmissionError(
            "exact Benchmark Release runtime projection verification is unavailable"
        )
    if experiment.bundle_id != bundle.bundle_id:
        raise NewRunAdmissionError(
            "Experiment bundle_id does not match the resolved runtime Bundle"
        )
    if bundle.bundle_id != expected_runtime_bundle_id:
        raise NewRunAdmissionError(
            "selected Bundle is not the exact runtime projection of the "
            "immutable Benchmark Release"
        )

    projection = metadata.get("formal_runtime_projection")
    if not isinstance(projection, Mapping):
        raise NewRunAdmissionError(
            "release-bound Run requires a verified native runtime projection"
        )
    if projection.get("release_id") != experiment.dataset_release_id:
        raise NewRunAdmissionError(
            "runtime projection does not match the selected Benchmark Release"
        )
    if (
        projection.get("release_id") != release.release_id
        or projection.get("release_digest") != release.release_digest
        or projection.get("validation_report_digest")
        != release.validation_report_digest
    ):
        raise NewRunAdmissionError(
            "runtime projection identity does not match the immutable Benchmark Release"
        )
    if (
        projection.get("projection_version") != "4"
        or projection.get("execution_contract")
        != NATIVE_DOCUMENT_EXECUTION_CONTRACT
    ):
        raise NewRunAdmissionError(
            "Benchmark Release does not provide the native-document/v2 runtime contract"
        )

    documents = bundle.manifest.documents
    if len(documents) != 1:
        raise NewRunAdmissionError(
            "native formal Runs require exactly one original DOCX document"
        )
    document = documents[0]
    if (
        document.document_id != release.document.document_id
        or document.sha256 != release.document.source_digest
    ):
        raise NewRunAdmissionError(
            "runtime document identity does not match the Benchmark Release source pin"
        )
    if (
        document.mime_type.lower() != DOCX_MIME_TYPE
        or Path(document.path).suffix.lower() != ".docx"
    ):
        raise NewRunAdmissionError(
            "native formal Runs accept only the original DOCX document"
        )
    if document.metadata.get("execution_view") != NATIVE_DOCUMENT_EXECUTION_CONTRACT:
        raise NewRunAdmissionError(
            "runtime document is not admitted under native-document/v2"
        )

    question_ids = sorted(item.case_id for item in bundle.questions)
    selected_case_ids = sorted(
        question_ids if experiment.case_ids is None else experiment.case_ids
    )
    if not selected_case_ids:
        raise NewRunAdmissionError("resolved Run must select at least one case")
    unknown = sorted(set(selected_case_ids) - set(question_ids))
    if unknown:
        raise NewRunAdmissionError(
            f"Experiment references unknown cases: {unknown}"
        )
    if len(selected_case_ids) != len(set(selected_case_ids)):
        raise NewRunAdmissionError("Experiment case_ids must be unique")
    expected_selection_id = case_selection_id(
        selected_case_ids,
        policy="explicit" if experiment.case_ids is not None else "all",
        seed=experiment.seed,
    )
    if expected_selection_id != experiment.case_selection_id:
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
            release_id=release.release_id,
            release_digest=release.release_digest,
            validation_report_digest=release.validation_report_digest,
            runtime_bundle_id=bundle.bundle_id,
        ),
        original_document=OriginalDocumentIdentityV2(
            document_id=document.document_id,
            source_sha256=document.sha256,
            runtime_path=document.path,
            mime_type=document.mime_type,
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
    "DOCX_MIME_TYPE",
    "NATIVE_DOCUMENT_EXECUTION_CONTRACT",
    "NewRunAdmissionError",
    "admit_new_public_experiment",
    "require_no_public_corpus_selector",
]
