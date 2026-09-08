"""Admission policy for newly created public evaluation runs.

The executor still understands historical pre-segmented experiments during the
compatibility window.  This module owns the narrower public boundary: a new
formal/release-bound run is a native-document run, and no public caller may
select a corpus implementation through Adapter configuration.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from rag_eval.contracts.run import ExperimentSpec
from rag_eval.datasets.bundle import DatasetBundle

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
    release_store: _DatasetReleaseStore | None = None,
    expected_runtime_bundle_id: str | None = None,
) -> None:
    """Validate an Experiment before a public create or queue operation.

    Persisted legacy Experiments and the direct Executor remain readable and
    testable.  Calling this policy is what distinguishes a new public run from
    a compatibility replay/oracle.
    """

    require_no_public_corpus_selector(experiment.adapter_config)
    if (
        experiment.benchmark_contract_version is not None
        or experiment.benchmark_contract_digest is not None
    ):
        raise NewRunAdmissionError(
            "pre-segmented benchmark contracts cannot create new Runs; use "
            "the release-pinned native DOCX route"
        )

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

    if experiment.dataset_release_id is None and not experiment.formal:
        # Non-formal source-document Experiments remain a development surface.
        # They cannot become a pre-segmented route because of the checks above.
        return
    if experiment.dataset_release_id is None:
        raise NewRunAdmissionError(
            "new formal Runs require an immutable Benchmark Release"
        )

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


__all__ = [
    "DOCX_MIME_TYPE",
    "NATIVE_DOCUMENT_EXECUTION_CONTRACT",
    "NewRunAdmissionError",
    "admit_new_public_experiment",
    "require_no_public_corpus_selector",
]
