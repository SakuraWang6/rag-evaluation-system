"""Standalone run execution through an isolated adapter worker."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from statistics import pstdev
from threading import Event, Thread
from time import monotonic

import httpx

from rag_eval import __version__
from rag_eval.artifact_contract import artifact_digest as contract_digest
from rag_eval.contracts.adapter import (
    AdapterCapabilities,
    DocumentInput,
    PreparedSystem,
    RAGQuery,
    RAGResult,
    SegmentTraceSet,
    SegmentTraceStage,
    SegmentTraceStatus,
)
from rag_eval.contracts.benchmark import (
    BENCHMARK_CONTRACT_SCHEMA_VERSION,
    BenchmarkDataset,
    BenchmarkQuestion,
    SegmentEvaluationOutcome,
    SegmentEvaluationTrace,
)
from rag_eval.contracts.dataset import GoldEvidence, ObjectLocator, Question
from rag_eval.contracts.native import (
    NativeQueryV2,
    OriginalDocumentV2,
    PreparedSystemV2,
    ResolvedAdapterConfigV2,
)
from rag_eval.contracts.observation import AdapterCapabilitiesV2, ObservationStatus
from rag_eval.contracts.research import (
    FailureAssessment,
    FailureLabel,
    LatencyProtocol,
    ModelArtifactIdentity,
)
from rag_eval.contracts.run import (
    CaseError,
    CaseResult,
    ExperimentSpec,
    MetricResult,
    MetricStatus,
    RunManifest,
    RunStatus,
)
from rag_eval.contracts.wire import WorkerIdentityV2
from rag_eval.datasets.benchmark_contract import (
    formal_release_benchmark_contract_path,
    load_benchmark_dataset,
    materialize_benchmark_segment_documents,  # noqa: F401 - removed in Phase 5
)
from rag_eval.datasets.bundle import (
    DatasetBundle,
    DatasetBundleStore,
    case_selection_id,
)
from rag_eval.datasets.canonical_segments import (
    CanonicalSegmentError,
    load_staged_canonical_segment_manifest,
    materialize_canonical_segment_documents,
)
from rag_eval.datasets.formal import BundleProjectionStatus, DatasetReleaseStore
from rag_eval.evaluation.answers import (
    ANSWER_SCORER_DIGEST,
    ANSWER_SCORER_ID,
    ANSWER_SCORER_VERSION,
)
from rag_eval.evaluation.engine import (
    GROUNDING_SCORER_DIGEST,
    GROUNDING_SCORER_ID,
    GROUNDING_SCORER_VERSION,
    evaluate_case,
)
from rag_eval.evaluation.evidence import (
    EVIDENCE_SCORER_DIGEST,
    EVIDENCE_SCORER_ID,
    EVIDENCE_SCORER_VERSION,
    CorpusEvidenceIndex,
)
from rag_eval.evaluation.failures import assess_failure
from rag_eval.evaluation.segment_answers import (
    SEGMENT_ANSWER_SCORER_DIGEST,
    SEGMENT_ANSWER_SCORER_ID,
    SEGMENT_ANSWER_SCORER_VERSION,
    answer_error_metrics,
    answer_not_applicable_metrics,
    evaluate_segment_answer,
)
from rag_eval.evaluation.segment_metrics import (
    SEGMENT_SCORER_DIGEST,
    SEGMENT_SCORER_ID,
    SEGMENT_SCORER_VERSION,
    evaluate_segment_retrieval,
)
from rag_eval.evaluation.unified import EvaluationProfile
from rag_eval.execution_provider import (
    ExecutionProvider,
    ExecutionRequest,
    LocalProcessProvider,
    WorkerHandle,
)
from rag_eval.report import markdown_report
from rag_eval.reproducibility import capture_reproducibility
from rag_eval.runs import (
    AdapterSession,
    ArtifactCaseErrorV2,
    ArtifactWriter,
    BenchmarkResolver,
    EvaluationEngine,
    NativeCaseOrchestrator,
    RunArtifactCaseV2,
    TraceValidationRecordV2,
    TraceValidationResult,
    TraceValidator,
    benchmark_identity_from_release_metadata,
)
from rag_eval.runs.plans import (
    ResolvedRunPlanReferenceV2,
    ResolvedRunPlanV2,
    formal_metric_descriptors,
)
from rag_eval.runs.records import RunRecordStoreV2
from rag_eval.runtime_admission import NATIVE_DOCUMENT_EXECUTION_CONTRACT
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.runs import RunStore
from rag_eval.worker.client import WorkerProtocolError, WorkerRemoteError
from rag_eval.worker.process import WorkerCommand


class RunExecutor:
    def __init__(
        self,
        dataset_store: DatasetBundleStore,
        run_store: RunStore,
        provider: ExecutionProvider | None = None,
        dataset_release_store: DatasetReleaseStore | None = None,
        run_record_store: RunRecordStoreV2 | None = None,
    ) -> None:
        self.dataset_store = dataset_store
        self.run_store = run_store
        self.provider = provider or LocalProcessProvider()
        self.dataset_release_store = dataset_release_store
        self.run_record_store = run_record_store

    def execute(
        self,
        experiment: ExperimentSpec,
        command: WorkerCommand,
        *,
        run_id: str | None = None,
        cancelled: Callable[[], bool] | None = None,
        worker_started: Callable[[str, int], None] | None = None,
        replay_of_run_id: str | None = None,
        execution_metadata: dict[str, object] | None = None,
        resolved_plan: ResolvedRunPlanV2 | None = None,
        resolved_plan_reference: ResolvedRunPlanReferenceV2 | None = None,
    ) -> RunManifest:
        run_id = run_id or uuid.uuid4().hex
        cancelled = cancelled or (lambda: False)
        if resolved_plan is None or resolved_plan_reference is None:
            raise ValueError(
                "RunExecutor accepts only an admitted Native v2 resolved plan"
            )
        bundle = self.dataset_store.get(experiment.bundle_id)
        if resolved_plan is not None:
            if not resolved_plan.matches_experiment(experiment):
                raise ValueError("Experiment does not match its immutable resolved plan")
            if (
                command.adapter_id != resolved_plan.system.adapter_id
                or command.adapter_factory != resolved_plan.system.adapter_factory
                or command.request_timeout_seconds
                != resolved_plan.system.worker_request_timeout_seconds
            ):
                raise ValueError(
                    "Worker command does not match the immutable resolved plan"
                )
            if resolved_plan.metric_descriptors != formal_metric_descriptors(
                resolved_plan.evaluation_profile
            ):
                raise ValueError(
                    "resolved plan scorer descriptors do not match the running Platform"
                )
            if self.run_record_store is None:
                raise ValueError(
                    "Native v2 execution requires the RunRecordV2 store"
                )
            if resolved_plan_reference is None:
                raise ValueError(
                    "Native v2 execution requires its resolved plan reference"
                )
            if resolved_plan_reference.digest != contract_digest(resolved_plan):
                raise ValueError("resolved plan reference digest mismatch")
            documents_by_id = {
                document.document_id: document for document in bundle.manifest.documents
            }
            planned_document = documents_by_id.get(
                resolved_plan.original_document.document_id
            )
            if (
                planned_document is None
                or planned_document.sha256
                != resolved_plan.original_document.source_sha256
                or planned_document.path
                != resolved_plan.original_document.runtime_path
            ):
                raise ValueError(
                    "runtime Bundle does not match the resolved original DOCX identity"
                )
        self._validate_dataset_release_reference(experiment, bundle)
        benchmark_dataset = self._load_benchmark_contract(experiment)
        questions = (
            select_benchmark_questions(benchmark_dataset, experiment)
            if benchmark_dataset is not None
            else select_questions(bundle, experiment)
        )
        primary_corpus = (
            "benchmark_segments"
            if benchmark_dataset is not None
            else requested_primary_corpus(experiment, bundle)
        )
        resolved_adapter_config = dict(experiment.adapter_config)
        # Pre-segmented compatibility runs still need their historical Adapter
        # selector.  Native runs omit it entirely: the Adapter receives the
        # original source and its own default/native ingestion behavior owns
        # parsing and chunking.
        if primary_corpus != "source_document":
            resolved_adapter_config.setdefault("evaluation_corpus", primary_corpus)
        question_orders = {
            repetition_seed: order_questions(questions, repetition_seed)
            for repetition_seed in (
                experiment.seed + offset for offset in range(experiment.repetitions)
            )
        }
        if resolved_plan is not None:
            assert self.run_record_store is not None
            assert resolved_plan_reference is not None
            self.run_record_store.create(
                run_id=run_id,
                experiment_id=experiment.experiment_id,
                resolved_plan=resolved_plan_reference,
            )
        manifest: RunManifest | None = None
        documents: list[DocumentInput] | None = None
        original_docx: OriginalDocumentV2 | None = None
        results: list[CaseResult] = []
        artifact_v2_cases: list[RunArtifactCaseV2] = []
        artifact_v2_profile = (
            resolved_plan.evaluation_profile if resolved_plan is not None else None
        )
        artifact_v2_profile_resolved = resolved_plan is not None
        index_fingerprints: list[str] = []
        index_artifact_digests: list[str] = []
        first_worker_identity: WorkerIdentityV2 | None = None
        # The raw worker response is kept only in memory for repetition
        # validation. Persisted artifacts must not contain resolved endpoints.
        validation_effective_config: dict[str, object] | None = None
        effective_config: dict[str, object] | None = None
        repetition_seeds = [
            experiment.seed + offset for offset in range(experiment.repetitions)
        ]
        try:
            run_dir = self.run_store.prepare_execution_layout(run_id)
            for repetition, repetition_seed in enumerate(repetition_seeds, start=1):
                if cancelled():
                    if manifest is not None:
                        manifest = manifest.model_copy(
                            update={"status": RunStatus.CANCELLED}
                        )
                    break
                worker_run_id = f"{run_id}-rep-{repetition:04d}"
                temporary_log = (
                    self.run_store.root / f".{worker_run_id}.worker.log"
                )
                seeded_command = command_for_seed(command, repetition_seed)
                handle = self.provider.start(
                    ExecutionRequest(
                        command=seeded_command,
                        run_id=worker_run_id,
                        log_path=temporary_log,
                        source_dir=run_dir / "source",
                        work_dir=run_dir / "work" / f"rep-{repetition:04d}",
                    )
                )
                watcher_done = Event()
                watcher: Thread | None = None
                try:
                    client = handle.client
                    if worker_started and handle.worker_pid is not None:
                        worker_started(run_id, handle.worker_pid)
                    watcher = Thread(
                        target=watch_cancellation,
                        args=(cancelled, watcher_done, handle),
                        name=f"rag-eval-cancel-{worker_run_id}",
                        daemon=True,
                    )
                    watcher.start()
                    worker_health = client.health()
                    worker_identity = worker_health.identity
                    validate_worker_identity(
                        worker_identity,
                        experiment,
                        first_worker_identity,
                    )
                    if first_worker_identity is None:
                        first_worker_identity = worker_identity
                        manifest = initial_manifest(
                            run_id,
                            experiment,
                            bundle,
                            worker_identity,
                            repetition_seeds,
                            replay_of_run_id,
                        )
                        assert self.run_record_store is not None
                        self.run_record_store.mark_running(
                            run_id, started_at=manifest.started_at
                        )
                        self.run_store.create(manifest, experiment)
                        provider_metadata = {
                            **handle.launch_metadata,
                            **(execution_metadata or {}),
                        }
                        if provider_metadata:
                            atomic_write_json(
                                run_dir / "execution-environment.json",
                                provider_metadata,
                            )
                            manifest = manifest.model_copy(
                                update={
                                    "artifacts": {
                                        **manifest.artifacts,
                                        "execution_environment": "execution-environment.json",
                                    }
                                }
                            )
                            self.run_store.write_manifest(manifest)
                        source_dir = run_dir / "source"
                        documents = source_only_documents(
                            bundle,
                            source_dir,
                            primary_corpus="source_document",
                        )
                        original_docx = direct_native_document(
                            documents,
                            resolved_plan,
                        )
                    assert manifest is not None
                    assert original_docx is not None
                    source_dir = run_dir / "source"
                    direct_config = handle.resolve_adapter_config(
                        ResolvedAdapterConfigV2(
                            run_id=worker_run_id,
                            work_dir=str(
                                run_dir / "work" / f"rep-{repetition:04d}"
                            ),
                            source_dir=str(source_dir),
                            platform_version=__version__,
                            seed=repetition_seed,
                            repetition=repetition,
                            adapter_config=resolved_adapter_config,
                            adapter_config_digest=resolved_plan.adapter_config_digest,
                        )
                    )
                    prepared = client.prepare(
                        original_docx,
                        direct_config,
                        timeout=ingestion_rpc_timeout(
                            seeded_command,
                            resolved_adapter_config,
                        ),
                    )
                    validate_prepared_v2(
                        prepared, experiment, validation_effective_config
                    )
                    current_artifact_v2_profile = resolved_plan.evaluation_profile
                    if not artifact_v2_profile_resolved:
                        artifact_v2_profile = current_artifact_v2_profile
                        artifact_v2_profile_resolved = True
                    elif current_artifact_v2_profile != artifact_v2_profile:
                        raise ValueError(
                            "Artifact 2.0 evaluation profile changed across repetitions"
                        )
                    current_effective = {
                        "adapter": prepared.effective_config,
                        "query": experiment.query_config,
                        "metrics": experiment.metric_config,
                        "execution": {
                            "base_seed": experiment.seed,
                            "repetitions": experiment.repetitions,
                        },
                    }
                    if validation_effective_config is None:
                        validation_effective_config = current_effective
                        effective_config = redact_runtime_endpoints(current_effective)
                        reproducibility = capture_reproducibility(
                            seeded_command, run_dir, current_effective
                        )
                        manifest = manifest.model_copy(
                            update={
                                "status": RunStatus.RUNNING,
                                "system_version": (
                                    prepared.runtime_profile.system_version
                                ),
                                "effective_config": effective_config,
                                "declared_capabilities": (
                                    legacy_manifest_capabilities(
                                        prepared.observation_profile.capabilities
                                    )
                                ),
                                "observed_capabilities": (
                                    legacy_manifest_capabilities(
                                        prepared.observation_profile.capabilities
                                    )
                                ),
                                "reproducibility": reproducibility,
                                "model_artifacts": prepared_model_artifacts(
                                    prepared, experiment
                                ),
                            }
                        )
                    elif current_effective != validation_effective_config:
                        raise ValueError(
                            "effective configuration changed across repetitions"
                        )
                    self.run_store.write_manifest(manifest)
                    ingestion = prepared.ingestion_receipt
                    index_fingerprints.append(ingestion.index_fingerprint)
                    artifact_digest = ingestion.index_artifact_digest
                    if artifact_digest is not None:
                        index_artifact_digests.append(
                            artifact_digest
                            if artifact_digest.startswith("sha256:")
                            else f"sha256:{artifact_digest}"
                        )
                    manifest = manifest.model_copy(
                        update={
                            "status": RunStatus.RUNNING,
                            "index_fingerprint": index_fingerprints[0],
                            "index_fingerprints": index_fingerprints,
                            "index_input_fingerprint": index_fingerprints[0],
                            "index_artifact_digest": index_artifact_digests[0]
                            if index_artifact_digests
                            else None,
                            "index_artifact_digests": index_artifact_digests,
                        }
                    )
                    self.run_store.write_manifest(manifest)
                    if experiment.latency_protocol is not None:
                        validate_latency_runtime(
                            prepared.effective_config, experiment.latency_protocol
                        )
                        run_latency_warmup(
                            client,
                            prepared,
                            experiment,
                        )
                    for question in question_orders[repetition_seed]:
                        if cancelled():
                            manifest = manifest.model_copy(
                                update={"status": RunStatus.CANCELLED}
                            )
                            break
                        artifact_case = execute_native_case(
                            client,
                            prepared,
                            question,
                            bundle,
                            experiment,
                            cancelled,
                            repetition,
                            repetition_seed,
                            profile=current_artifact_v2_profile,
                            expected_identity=worker_identity,
                        )
                        artifact_v2_cases.append(artifact_case)
                        if artifact_case.status == "cancelled":
                            manifest = manifest.model_copy(
                                update={"status": RunStatus.CANCELLED}
                            )
                            break
                finally:
                    watcher_done.set()
                    handle.stop()
                    if watcher is not None:
                        watcher.join(timeout=1)
                    if temporary_log.exists() and run_dir.is_dir():
                        final_log = (
                            run_dir
                            / "worker"
                            / f"rep-{repetition:04d}.worker.log"
                        )
                        temporary_log.replace(final_log)
                if manifest is not None and manifest.status == RunStatus.CANCELLED:
                    break

            if manifest is None:
                raise RuntimeError("run did not start")
            expected_cases = len(questions) * experiment.repetitions
            counts = artifact_execution_counts(
                artifact_v2_cases,
                expected=expected_cases,
            )
            summary = {
                "metrics": {},
                "execution": {
                    **counts,
                    "execution_failure_rate": (
                        (counts["expected"] - counts["completed"])
                        / counts["expected"]
                        if counts["expected"]
                        else 0.0
                    ),
                    "authority": "artifact-v2",
                },
            }
            atomic_write_json(run_dir / "summary.json", summary)
            atomic_write_json(
                run_dir / "case-order.json",
                {
                    "policy": "seeded_sha256_case_order_v1",
                    "orders": {
                        str(seed): [question.case_id for question in ordered]
                        for seed, ordered in question_orders.items()
                    },
                },
            )
            completed_at = datetime.now(UTC)
            artifact_v2_reference: dict[str, str] = {}
            benchmark_identity = None
            if manifest.status != RunStatus.CANCELLED:
                if resolved_plan is not None and len(artifact_v2_cases) != expected_cases:
                    raise ValueError(
                        "Native v2 Run did not produce one Artifact case per planned execution"
                    )
                manifest = manifest.model_copy(update={"status": RunStatus.COMPLETED})
            if manifest.status == RunStatus.COMPLETED and (
                resolved_plan is not None
                or (artifact_v2_cases and len(artifact_v2_cases) == expected_cases)
            ):
                benchmark_identity = benchmark_identity_from_release_metadata(
                    bundle_id=bundle.bundle_id,
                    case_selection_id=experiment.case_selection_id,
                    dataset_release_id=experiment.dataset_release_id,
                    metadata=bundle.manifest.metadata,
                    document_sources={
                        document.document_id: document.sha256
                        for document in bundle.manifest.documents
                    },
                    cases=tuple(artifact_v2_cases),
                )
                if benchmark_identity is None:
                    if resolved_plan is not None:
                        raise ValueError(
                            "Native v2 Run could not bind Artifact 2.0 to its Benchmark Release"
                        )
                else:
                    artifact_v2_reference = {
                        "artifact_v2": "artifact-v2/artifact.json"
                    }
            manifest = manifest.model_copy(
                update={
                    "completed_at": completed_at,
                    "execution_counts": counts,
                    "artifacts": {
                        **manifest.artifacts,
                        "summary": "summary.json",
                        "case_order": "case-order.json",
                        "cases": "cases/",
                        "reproducibility": "reproducibility/",
                        "report": "report.md",
                        **artifact_v2_reference,
                    },
                }
            )
            (run_dir / "report.md").write_text(
                markdown_report(manifest, results, summary), encoding="utf-8"
            )
            self.run_store.write_manifest(manifest)
            manifest = manifest.model_copy(
                update={"artifact_checksums": self.run_store.artifact_hashes(run_id)}
            )
            self.run_store.write_manifest(manifest)
            if benchmark_identity is not None:
                # Artifact publication and RunRecord completion are the final
                # authority transition. Transitional outputs above cannot
                # make a Native v2 Run visible as completed, and no fallible
                # legacy write occurs after this boundary.
                ArtifactWriter(run_dir).publish(
                    run_id=run_id,
                    experiment_id=experiment.experiment_id,
                    benchmark_identity=benchmark_identity,
                    cases=tuple(artifact_v2_cases),
                    started_at=manifest.started_at,
                    completed_at=completed_at,
                )
            if resolved_plan is not None:
                assert self.run_record_store is not None
                if manifest.status == RunStatus.CANCELLED:
                    self.run_record_store.mark_cancelled(
                        run_id, completed_at=completed_at
                    )
                else:
                    # This is the final authority transition.  The store reads
                    # and verifies the atomically published Artifact before it
                    # can expose COMPLETED.
                    self.run_record_store.mark_completed(run_id)
            return manifest
        except Exception as exc:
            if manifest is not None:
                manifest = manifest.model_copy(
                    update={
                        "status": RunStatus.FAILED,
                        "completed_at": datetime.now(UTC),
                        "failure_reason": str(exc) or type(exc).__name__,
                    }
                )
                self.run_store.write_manifest(manifest)
            if resolved_plan is not None and self.run_record_store is not None:
                try:
                    if cancelled():
                        self.run_record_store.mark_cancelled(run_id)
                    else:
                        self.run_record_store.mark_failed(
                            run_id,
                            error=str(exc) or type(exc).__name__,
                        )
                except (FileNotFoundError, ValueError):
                    # Never mask the execution failure. A terminal/completed
                    # record cannot be rewritten by this defensive boundary.
                    pass
            raise

    def _validate_dataset_release_reference(
        self, experiment: ExperimentSpec, bundle: DatasetBundle
    ) -> None:
        """Bind an opted-in run to exactly one immutable formal Dataset Release."""

        if experiment.dataset_release_id is None:
            return
        if self.dataset_release_store is None:
            raise ValueError("Dataset Release references are unavailable in this Platform mode")
        release = self.dataset_release_store.get(experiment.dataset_release_id)
        runtime_projection = bundle.manifest.metadata.get("formal_runtime_projection")
        if (
            isinstance(runtime_projection, Mapping)
            and runtime_projection.get("release_id") == release.release_id
            and runtime_projection.get("release_digest") == release.release_digest
            and runtime_projection.get("validation_report_digest")
            == release.validation_report_digest
            and runtime_projection.get("projection_version") == "4"
            and runtime_projection.get("execution_contract")
            == NATIVE_DOCUMENT_EXECUTION_CONTRACT
        ):
            # New formal runs resolve a content-addressed projection whose
            # ingestion input is the pinned DOCX. An older release's Bundle
            # projection identity must not override this native route.
            return
        if release.bundle_projection.status == BundleProjectionStatus.LOSSLESS_RUNNABLE:
            if release.bundle_projection.bundle_id != bundle.bundle_id:
                raise ValueError("experiment Bundle does not match selected formal Dataset Release")
            return
        if (
            release.bundle_projection.projections
            and isinstance(runtime_projection, dict)
            and runtime_projection.get("release_id") == release.release_id
            and runtime_projection.get("release_digest") == release.release_digest
        ):
            # This is a deterministic, release-pinned runtime projection. It
            # preserves formal MSES alternatives when legacy Bundle 2.0 could
            # not represent them; it is neither a release mutation nor a
            # workspace export.
            return
        raise ValueError("selected formal Dataset Release is not runnable through the standard executor")

    def _load_benchmark_contract(
        self, experiment: ExperimentSpec
    ) -> BenchmarkDataset | None:
        """Resolve a vNext run only from the immutable Release-adjacent package."""

        if experiment.benchmark_contract_digest is None:
            if experiment.benchmark_contract_version is not None:
                raise ValueError("benchmark contract version requires a contract digest")
            return None
        if experiment.benchmark_contract_version != BENCHMARK_CONTRACT_SCHEMA_VERSION:
            raise ValueError("unsupported benchmark contract version")
        if experiment.dataset_release_id is None or self.dataset_release_store is None:
            raise ValueError("benchmark execution requires an immutable Dataset Release")
        release = self.dataset_release_store.get(experiment.dataset_release_id)
        dataset = load_benchmark_dataset(
            formal_release_benchmark_contract_path(
                self.dataset_release_store.root,
                release.release_id,
            )
        )
        if dataset.manifest.contract_digest != experiment.benchmark_contract_digest:
            raise ValueError("experiment benchmark contract digest does not match Release artifact")
        if (
            dataset.manifest.source_release_id != release.release_id
            or dataset.manifest.source_release_digest != release.release_digest
        ):
            raise ValueError("benchmark contract source release pin does not match experiment")
        return dataset


def initial_manifest(
    run_id: str,
    experiment: ExperimentSpec,
    bundle: DatasetBundle,
    worker_identity: WorkerIdentityV2,
    repetition_seeds: list[int],
    replay_of_run_id: str | None,
) -> RunManifest:
    started_at = datetime.now(UTC)
    # New Runs carry a useful immutable label.  Existing Runs remain exactly
    # as they are and receive a deterministic presentation-only fallback in
    # RunHistory instead.
    display_name = experiment.display_name or (
        f"{experiment.system_id} · {started_at.strftime('%Y-%m-%d %H:%M UTC')} · {run_id[:8]}"
    )
    execution_view, diagnostic_only = execution_view_identity(experiment, bundle)
    return RunManifest(
        run_id=run_id,
        experiment_id=experiment.experiment_id,
        display_name=display_name,
        execution_view=execution_view,
        diagnostic_only=diagnostic_only,
        status=RunStatus.PREPARING,
        bundle_id=bundle.bundle_id,
        dataset_release_id=experiment.dataset_release_id,
        benchmark_contract_version=experiment.benchmark_contract_version,
        benchmark_contract_digest=experiment.benchmark_contract_digest,
        case_selection_id=experiment.case_selection_id,
        platform_version=__version__,
        adapter_id=worker_identity.adapter_id,
        adapter_version=worker_identity.adapter_version,
        system_id=worker_identity.system_id,
        system_version=worker_identity.system_version,
        declared_config={
            "adapter": experiment.adapter_config,
            "query": experiment.query_config,
            "metrics": experiment.metric_config,
            "model_lock_digest": experiment.model_lock_digest,
            "comparison_spec_digest": experiment.comparison_spec_digest,
            "analysis_contract_digest": experiment.analysis_contract_digest,
            "latency_protocol_digest": experiment.latency_protocol_digest,
            "formal": experiment.formal,
            "execution_view": execution_view,
            "diagnostic_only": diagnostic_only,
            "benchmark_contract": {
                "version": experiment.benchmark_contract_version,
                "digest": experiment.benchmark_contract_digest,
            }
            if experiment.benchmark_contract_digest is not None
            else None,
        },
        effective_config={},
        scorer_id=ANSWER_SCORER_ID,
        scorer_version=ANSWER_SCORER_VERSION,
        scorer_digest=ANSWER_SCORER_DIGEST,
        metric_scorers={
            "typed_answer": {
                "scorer_id": ANSWER_SCORER_ID,
                "scorer_version": ANSWER_SCORER_VERSION,
                "scorer_digest": ANSWER_SCORER_DIGEST,
            },
            "gold_evidence": {
                "scorer_id": EVIDENCE_SCORER_ID,
                "scorer_version": EVIDENCE_SCORER_VERSION,
                "scorer_digest": EVIDENCE_SCORER_DIGEST,
            },
            "gold_grounding": {
                "scorer_id": GROUNDING_SCORER_ID,
                "scorer_version": GROUNDING_SCORER_VERSION,
                "scorer_digest": GROUNDING_SCORER_DIGEST,
            },
            "segment_native_retrieval": {
                "scorer_id": SEGMENT_SCORER_ID,
                "scorer_version": SEGMENT_SCORER_VERSION,
                "scorer_digest": SEGMENT_SCORER_DIGEST,
            },
            "segment_native_answer_evidence": {
                "scorer_id": SEGMENT_ANSWER_SCORER_ID,
                "scorer_version": SEGMENT_ANSWER_SCORER_VERSION,
                "scorer_digest": SEGMENT_ANSWER_SCORER_DIGEST,
            },
        },
        model_artifacts=experiment.model_artifacts,
        # RunManifest is a transitional, non-authoritative persistence model
        # retired in Phase 6. Direct Worker capabilities are recorded after
        # prepare and evaluation remains exclusively in Artifact 2.0.
        declared_capabilities=AdapterCapabilities(),
        observed_capabilities=AdapterCapabilities(),
        seed=experiment.seed,
        repetitions=experiment.repetitions,
        latency_protocol_digest=experiment.latency_protocol_digest,
        repetition_seeds=repetition_seeds,
        replay_of_run_id=replay_of_run_id,
        started_at=started_at,
    )


def execution_view_identity(
    experiment: ExperimentSpec, bundle: DatasetBundle
) -> tuple[str, bool]:
    """Freeze the declared execution view without rewriting historical runs.

    A release-pinned ``native-document/v2`` projection is the formal route.
    Older authoring-native inputs retain their historical diagnostic identity,
    while persisted Artifact 2.0 availability decides modern eligibility.
    """

    if experiment.benchmark_contract_digest is not None:
        return "benchmark-contract/v1", False
    metadata = bundle.manifest.metadata
    formal_projection = metadata.get("formal_runtime_projection")
    if (
        isinstance(formal_projection, dict)
        and formal_projection.get("projection_version") == "4"
        and formal_projection.get("execution_contract")
        == NATIVE_DOCUMENT_EXECUTION_CONTRACT
    ):
        return NATIVE_DOCUMENT_EXECUTION_CONTRACT, False
    authoring = metadata.get("authoring") if isinstance(metadata, dict) else None
    raw_view = authoring.get("execution_view") if isinstance(authoring, dict) else None
    if raw_view == "native-docx" or (
        isinstance(authoring, dict) and authoring.get("native_diagnostic_only") is True
    ):
        return "native-docx", True
    if raw_view == "canonical-text":
        return "canonical-text", False
    requested = experiment.adapter_config.get("evaluation_corpus")
    if requested in {"canonical_segments", "canonical-segments/v1"}:
        return "canonical-segments", False
    return "source-document", False


def validate_worker_identity(
    identity: WorkerIdentityV2,
    experiment: ExperimentSpec,
    first: WorkerIdentityV2 | None,
) -> None:
    if identity.adapter_id != experiment.adapter_id:
        raise ValueError("worker adapter_id does not match ExperimentSpec")
    if identity.system_id != experiment.system_id:
        raise ValueError("worker system_id does not match ExperimentSpec")
    if first is not None and identity != first:
        raise ValueError("worker identity changed across repetitions")


def validate_prepared(
    prepared: PreparedSystem,
    experiment: ExperimentSpec,
    previous_effective: dict[str, object] | None,
) -> None:
    """Validate the retained legacy model object outside the v2 runtime path."""

    if (
        experiment.query_config.get("generate_answer", True)
        and not prepared.capabilities.answer
    ):
        raise ValueError(
            "experiment requests answer generation but adapter lacks answer capability"
        )
    if previous_effective is not None:
        previous_adapter = previous_effective.get("adapter")
        if prepared.effective_config != previous_adapter:
            raise ValueError("adapter effective config changed across repetitions")
    if experiment.formal:
        raw_artifacts = prepared.effective_config.get("model_artifacts")
        if not isinstance(raw_artifacts, dict) or not raw_artifacts:
            raise ValueError("formal worker prepare response lacks model artifact identities")
        actual = prepared_model_artifacts(prepared, experiment)
        if set(actual) != set(experiment.model_artifacts):
            raise ValueError("worker model identities do not match the frozen model lock")
        for name, expected in experiment.model_artifacts.items():
            observed = actual[name]
            if not observed.verified or observed.identity != expected.identity:
                raise ValueError(
                    f"worker model identity drift for {name}: expected {expected.identity}, "
                    f"observed {observed.identity}"
                )


def validate_prepared_v2(
    prepared: PreparedSystemV2,
    experiment: ExperimentSpec,
    previous_effective: dict[str, object] | None,
) -> None:
    if (
        experiment.query_config.get("generate_answer", True)
        and not prepared.observation_profile.capabilities.answer
    ):
        raise ValueError(
            "experiment requests answer generation but adapter lacks answer capability"
        )
    if previous_effective is not None:
        previous_adapter = previous_effective.get("adapter")
        if prepared.effective_config != previous_adapter:
            raise ValueError("adapter effective config changed across repetitions")
    if experiment.formal:
        raw_artifacts = prepared.effective_config.get("model_artifacts")
        if not isinstance(raw_artifacts, dict) or not raw_artifacts:
            raise ValueError("formal worker prepare response lacks model artifact identities")
        actual = prepared_model_artifacts(prepared, experiment)
        if set(actual) != set(experiment.model_artifacts):
            raise ValueError("worker model identities do not match the frozen model lock")
        for name, expected in experiment.model_artifacts.items():
            observed = actual[name]
            if not observed.verified or observed.identity != expected.identity:
                raise ValueError(
                    f"worker model identity drift for {name}: expected {expected.identity}, "
                    f"observed {observed.identity}"
                )


def validate_latency_runtime(
    effective_config: dict[str, object], protocol: LatencyProtocol
) -> None:
    cache_policy = effective_config.get("cache_policy")
    if not isinstance(cache_policy, dict):
        raise TypeError("latency protocol requires an observed adapter cache_policy")
    expected = {
        "answer": protocol.answer_cache_enabled,
        "query": protocol.query_cache_enabled,
        "llm": protocol.llm_cache_enabled,
    }
    observed = {name: cache_policy.get(name) for name in expected}
    if observed != expected:
        raise ValueError(
            "adapter cache policy differs from frozen latency protocol: "
            f"expected {expected}, observed {observed}"
        )


def run_latency_warmup(
    client,
    prepared: PreparedSystemV2,
    experiment: ExperimentSpec,
) -> None:
    assert experiment.latency_protocol is not None
    protocol = experiment.latency_protocol
    for index in range(protocol.warmup_queries):
        result = client.query(
            prepared,
            NativeQueryV2(
                case_id=f"__rag_eval_warmup_{index + 1}",
                question=protocol.warmup_question,
                generate_answer=False,
                retrieval_candidate_k=experiment.query_config["retrieval_candidate_k"],
                final_context_k=experiment.query_config["final_context_k"],
                max_context_tokens=experiment.query_config["max_context_tokens"],
                generation_options=experiment.query_config["generation_options"],
            )
        )
        TraceValidator().validate(
            result,
            expected_case_id=f"__rag_eval_warmup_{index + 1}",
            expected_adapter_id=prepared.observation_profile.adapter_id,
            expected_adapter_version=prepared.observation_profile.adapter_version,
            expected_system_id=prepared.runtime_profile.system_id,
            expected_system_version=prepared.runtime_profile.system_version,
        )


def prepared_model_artifacts(
    prepared: PreparedSystem | PreparedSystemV2,
    experiment: ExperimentSpec,
) -> dict[str, ModelArtifactIdentity]:
    raw = prepared.effective_config.get("model_artifacts", {})
    if not raw:
        return experiment.model_artifacts
    if not isinstance(raw, dict):
        raise TypeError("adapter model_artifacts must be an object")
    try:
        return {
            str(name): ModelArtifactIdentity.model_validate(value)
            for name, value in raw.items()
        }
    except Exception as exc:
        raise ValueError("adapter returned invalid model artifact identities") from exc


def redact_runtime_endpoints(value: object) -> object:
    """Replace launch-only endpoint values with stable non-reversible digests."""
    endpoint_keys = {
        "ollama_host",
        "llm_host",
        "query_llm_host",
        "embedding_host",
        "query_llm_binding_host",
        "embedding_binding_host",
        "llm_binding_host",
        "host",
        "endpoint",
        "base_url",
    }
    if isinstance(value, dict):
        return {
            key: (
                {
                    "redacted": True,
                    "endpoint_identity_digest": "sha256:"
                    + hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                }
                if key.lower() in endpoint_keys and isinstance(raw, str) and raw
                else redact_runtime_endpoints(raw)
            )
            for key, raw in value.items()
        }
    if isinstance(value, list):
        return [redact_runtime_endpoints(item) for item in value]
    return value


def execute_native_case(
    client,
    prepared: PreparedSystemV2,
    question: Question,
    bundle: DatasetBundle,
    experiment: ExperimentSpec,
    cancelled: Callable[[], bool],
    repetition: int,
    seed: int,
    *,
    profile: EvaluationProfile,
    expected_identity: WorkerIdentityV2,
) -> RunArtifactCaseV2:
    """Execute one Direct Wire 2.0 query and persist only unified evaluation."""

    started = datetime.now(UTC)
    gold_answer = bundle.gold_answers[question.gold_answer_id]
    evidence_set = bundle.gold_evidence_sets[question.gold_evidence_set_id]
    resolver = BenchmarkResolver(
        questions={question.case_id: question},
        gold_answers={question.gold_answer_id: gold_answer},
        gold_evidence_sets={question.gold_evidence_set_id: evidence_set},
    )
    query = NativeQueryV2(
        case_id=question.case_id,
        question=question.question,
        generate_answer=experiment.query_config["generate_answer"],
        retrieval_candidate_k=experiment.query_config["retrieval_candidate_k"],
        final_context_k=experiment.query_config["final_context_k"],
        max_context_tokens=experiment.query_config["max_context_tokens"],
        generation_options=experiment.query_config["generation_options"],
    )
    flow = NativeCaseOrchestrator(
        benchmark_resolver=resolver,
        adapter_session=AdapterSession(client),
        trace_validator=TraceValidator(),
        evaluation_engine=EvaluationEngine(profile),
        expected_adapter_id=expected_identity.adapter_id,
        expected_adapter_version=expected_identity.adapter_version,
        expected_system_id=expected_identity.system_id,
        expected_system_version=expected_identity.system_version,
    )
    try:
        return flow.execute(
            case_id=question.case_id,
            prepared_system=prepared,
            query=query,
            repetition=repetition,
            seed=seed,
            started_at=started,
        ).artifact_case
    except httpx.TimeoutException as exc:
        was_cancelled = cancelled()
        status = "cancelled" if was_cancelled else "timeout"
        code = "cancelled" if was_cancelled else "timeout"
        message = str(exc) or "adapter query timed out"
    except (WorkerProtocolError, WorkerRemoteError, httpx.HTTPError) as exc:
        was_cancelled = cancelled()
        status = "cancelled" if was_cancelled else "system_error"
        if was_cancelled:
            code = "cancelled"
        elif isinstance(exc, WorkerProtocolError):
            code = "worker_protocol_error"
        else:
            code = getattr(exc, "code", "adapter_error")
        message = str(exc)
    return EvaluationEngine(profile).evaluate(
        resolver.resolve(question.case_id),
        TraceValidationResult(
            record=TraceValidationRecordV2(
                status=ObservationStatus.FAILED,
                reason=message,
            )
        ),
        started_at=started,
        completed_at=datetime.now(UTC),
        repetition=repetition,
        seed=seed,
        status=status,
        error=ArtifactCaseErrorV2(code=code, message=message),
    )


def execute_case(
    client,
    capabilities: AdapterCapabilities,
    question: Question,
    bundle: DatasetBundle,
    corpus: CorpusEvidenceIndex,
    experiment: ExperimentSpec,
    cancelled: Callable[[], bool],
    repetition: int,
    seed: int,
    *,
    artifact_v2_profile: EvaluationProfile | None = None,
    artifact_v2_cases: list[RunArtifactCaseV2] | None = None,
    expected_adapter_id: str | None = None,
    expected_adapter_version: str | None = None,
    expected_system_id: str | None = None,
    expected_system_version: str | None = None,
) -> CaseResult:
    started = datetime.now(UTC)
    gold_answer = bundle.gold_answers[question.gold_answer_id]
    evidence_set = bundle.gold_evidence_sets[question.gold_evidence_set_id]
    resolver = BenchmarkResolver(
        questions={question.case_id: question},
        gold_answers={question.gold_answer_id: gold_answer},
        gold_evidence_sets={question.gold_evidence_set_id: evidence_set},
    )
    query = RAGQuery(
        case_id=question.case_id,
        question=question.question,
        generate_answer=bool(experiment.query_config.get("generate_answer", True)),
        retrieval_candidate_k=experiment.query_config.get("retrieval_candidate_k"),
        final_context_k=experiment.query_config.get("final_context_k"),
        max_context_tokens=experiment.query_config.get("max_context_tokens"),
        generation_options=experiment.query_config.get("generation_options", {}),
    )

    def validate_adapter_response(rag_result: RAGResult) -> None:
        validate_result_capabilities(
            rag_result,
            capabilities,
            generate_answer=query.generate_answer,
        )

    def postprocess_result(rag_result: RAGResult) -> RAGResult:
        native_metadata = dict(rag_result.native_metadata)
        if corpus.catalog_diagnostics:
            native_metadata["evidence_catalog_diagnostics"] = list(
                corpus.catalog_diagnostics
            )
        native_metadata["evidence_catalog"] = {
            "catalog_verified": corpus.catalog_verified,
            "map_digest_verified": corpus.map_digest_verified,
            "map_bytes_digest_verified": corpus.map_bytes_digest_verified,
            "map_pin_verified": corpus.map_pin_verified,
            "source_pins_verified": corpus.source_pins_verified,
        }
        return rag_result.model_copy(update={"native_metadata": native_metadata})

    try:
        if artifact_v2_profile is not None:
            raise ValueError(
                "legacy execute_case cannot produce Native v2 evaluation; "
                "use execute_native_case"
            )
        rag_result = postprocess_result(client.query(query))
        validate_adapter_response(rag_result)
        metrics = evaluate_case(
            rag_result,
            gold_answer,
            evidence_set,
            corpus,
            k_values=metric_k_values(experiment),
            evaluate_answer=query.generate_answer,
        )
        return CaseResult(
            case_id=question.case_id,
            status="completed",
            question=question.question,
            gold_answer=gold_answer,
            gold_evidence_set=evidence_set,
            rag_result=rag_result,
            metrics=metrics,
            failure_assessment=assess_failure(
                status="completed",
                result=rag_result,
                evidence_set=evidence_set,
                corpus=corpus,
                metrics=metrics,
            ),
            started_at=started,
            completed_at=datetime.now(UTC),
            repetition=repetition,
            seed=seed,
        )
    except httpx.TimeoutException as exc:
        was_cancelled = cancelled()
        status = "cancelled" if was_cancelled else "timeout"
        code = "cancelled" if was_cancelled else "timeout"
        message = str(exc) or "adapter query timed out"
        case = failed_case(
            question.case_id,
            question.question,
            gold_answer,
            evidence_set,
            started,
            status=status,
            code=code,
            message=message,
            experiment=experiment,
            repetition=repetition,
            seed=seed,
        )
        append_unavailable_artifact_v2_case(
            profile=artifact_v2_profile,
            cases=artifact_v2_cases,
            resolver=resolver,
            case=case,
            code=code,
            message=message,
        )
        return case
    except (WorkerRemoteError, httpx.HTTPError) as exc:
        was_cancelled = cancelled()
        status = "cancelled" if was_cancelled else "system_error"
        code = (
            "cancelled"
            if was_cancelled
            else getattr(exc, "code", "adapter_error")
        )
        message = str(exc)
        case = failed_case(
            question.case_id,
            question.question,
            gold_answer,
            evidence_set,
            started,
            status=status,
            code=code,
            message=message,
            experiment=experiment,
            repetition=repetition,
            seed=seed,
        )
        append_unavailable_artifact_v2_case(
            profile=artifact_v2_profile,
            cases=artifact_v2_cases,
            resolver=resolver,
            case=case,
            code=code,
            message=message,
        )
        return case


def append_unavailable_artifact_v2_case(
    *,
    profile: EvaluationProfile | None,
    cases: list[RunArtifactCaseV2] | None,
    resolver: BenchmarkResolver,
    case: CaseResult,
    code: str,
    message: str,
) -> None:
    if profile is None or cases is None:
        return
    cases.append(
        EvaluationEngine(profile).evaluate(
            resolver.resolve(case.case_id),
            TraceValidationResult(
                record=TraceValidationRecordV2(
                    status=ObservationStatus.FAILED,
                    reason=message,
                )
            ),
            started_at=case.started_at,
            completed_at=case.completed_at,
            repetition=case.repetition,
            seed=case.seed,
            status=case.status,
            error=ArtifactCaseErrorV2(code=code, message=message),
        )
    )


def execute_benchmark_case(
    client,
    capabilities: AdapterCapabilities,
    question: BenchmarkQuestion,
    dataset: BenchmarkDataset,
    experiment: ExperimentSpec,
    cancelled: Callable[[], bool],
    repetition: int,
    seed: int,
) -> CaseResult:
    """Execute one vNext case without invoking legacy locator/provenance scoring."""

    started = datetime.now(UTC)
    gold = dataset.gold_by_id[question.gold_id]
    query = RAGQuery(
        case_id=question.case_id,
        question=question.question,
        generate_answer=bool(experiment.query_config.get("generate_answer", True)),
        retrieval_candidate_k=experiment.query_config.get("retrieval_candidate_k"),
        final_context_k=experiment.query_config.get("final_context_k"),
        max_context_tokens=experiment.query_config.get("max_context_tokens"),
        generation_options=experiment.query_config.get("generation_options", {}),
    )
    try:
        query_started = monotonic()
        rag_result = client.query(query)
        validate_result_capabilities(
            rag_result,
            capabilities,
            generate_answer=query.generate_answer,
        )
        validate_benchmark_result_capabilities(rag_result, capabilities)
        latency = dict(rag_result.latency or {})
        latency["end_to_end_query_latency"] = monotonic() - query_started
        native_metadata = {
            **rag_result.native_metadata,
            "benchmark_contract_digest": dataset.manifest.contract_digest,
            "benchmark_contract_schema_version": BENCHMARK_CONTRACT_SCHEMA_VERSION,
            "retrieval_evaluation": "segment_native_only",
        }
        rag_result = rag_result.model_copy(
            update={"latency": latency, "native_metadata": native_metadata}
        )
        metrics, trace = evaluate_segment_retrieval(
            rag_result,
            gold,
            benchmark_contract_digest=dataset.manifest.contract_digest,
            known_segment_ids=set(dataset.segments_by_id),
            k_values=segment_metric_k_values(experiment),
        )
        metrics.extend(
            evaluate_segment_answer(
                rag_result,
                gold,
                trace,
                evaluate_answer=query.generate_answer,
            )
        )
        return CaseResult(
            case_id=question.case_id,
            status="completed",
            question=question.question,
            gold_answer=gold.answer,
            rag_result=rag_result,
            metrics=metrics,
            segment_evaluation_trace=trace,
            failure_assessment=assess_segment_failure(trace, answer_metrics=metrics),
            started_at=started,
            completed_at=datetime.now(UTC),
            repetition=repetition,
            seed=seed,
        )
    except httpx.TimeoutException as exc:
        return failed_benchmark_case(
            question,
            gold.answer,
            gold,
            dataset,
            started,
            status="cancelled" if cancelled() else "timeout",
            code="cancelled" if cancelled() else "timeout",
            message=str(exc) or "adapter query timed out",
            experiment=experiment,
            repetition=repetition,
            seed=seed,
        )
    except (WorkerRemoteError, httpx.HTTPError) as exc:
        return failed_benchmark_case(
            question,
            gold.answer,
            gold,
            dataset,
            started,
            status="cancelled" if cancelled() else "system_error",
            code="cancelled" if cancelled() else getattr(exc, "code", "adapter_error"),
            message=str(exc),
            experiment=experiment,
            repetition=repetition,
            seed=seed,
        )


def failed_benchmark_case(
    question: BenchmarkQuestion,
    gold_answer,
    gold,
    dataset: BenchmarkDataset,
    started,
    *,
    status: str,
    code: str,
    message: str,
    experiment: ExperimentSpec,
    repetition: int,
    seed: int,
) -> CaseResult:
    """Persist query failures as runtime errors, never as fabricated zeros."""

    traces = SegmentTraceSet(
        raw=SegmentTraceStage(
            stage="raw", status=SegmentTraceStatus.RUNTIME_ERROR, reason=message
        ),
        ranked=SegmentTraceStage(
            stage="ranked", status=SegmentTraceStatus.RUNTIME_ERROR, reason=message
        ),
        context=SegmentTraceStage(
            stage="context", status=SegmentTraceStatus.RUNTIME_ERROR, reason=message
        ),
    )
    metrics, trace = evaluate_segment_retrieval(
        RAGResult(segment_traces=traces),
        gold,
        benchmark_contract_digest=dataset.manifest.contract_digest,
        known_segment_ids=set(dataset.segments_by_id),
        k_values=segment_metric_k_values(experiment),
    )
    if experiment.query_config.get("generate_answer", True):
        metrics.extend(answer_error_metrics(message))
    else:
        metrics.extend(
            answer_not_applicable_metrics(
                "answer generation is disabled for this experiment"
            )
        )
    return CaseResult(
        case_id=question.case_id,
        status=status,  # type: ignore[arg-type]
        question=question.question,
        gold_answer=gold_answer,
        metrics=metrics,
        segment_evaluation_trace=trace,
        error=CaseError(code=code, message=message),
        failure_assessment=FailureAssessment(
            labels=[
                FailureLabel.TIMEOUT
                if status == "timeout"
                else FailureLabel.RUNTIME_ERROR
            ],
            certainty="deterministic",
            reasons=[message],
        ),
        started_at=started,
        completed_at=datetime.now(UTC),
        repetition=repetition,
        seed=seed,
    )


def assess_segment_failure(
    trace: SegmentEvaluationTrace,
    *,
    answer_metrics: list[MetricResult] | None = None,
) -> FailureAssessment:
    """Map strict segment outcomes to deterministic, non-provenance labels."""

    labels: list[FailureLabel] = []
    reasons: list[str] = []
    label_by_outcome = {
        SegmentEvaluationOutcome.RETRIEVAL_MISSING: FailureLabel.RETRIEVAL_MISSING,
        SegmentEvaluationOutcome.PARTIAL_COVERAGE: FailureLabel.PARTIAL_COVERAGE,
        SegmentEvaluationOutcome.UNSUPPORTED_STAGE: FailureLabel.UNSUPPORTED_STAGE,
        SegmentEvaluationOutcome.RUNTIME_ERROR: FailureLabel.RUNTIME_ERROR,
        SegmentEvaluationOutcome.MAPPING_CORRUPTED: FailureLabel.MAPPING_CORRUPTED,
    }
    for stage in (trace.raw, trace.ranked, trace.context):
        label = label_by_outcome.get(stage.outcome)
        if label is not None:
            labels.append(label)
            reasons.append(
                stage.reason
                or f"{stage.stage} retrieval stage is {stage.outcome.value}"
            )
    if (
        trace.raw.outcome == SegmentEvaluationOutcome.COMPLETE
        and trace.ranked.outcome != SegmentEvaluationOutcome.COMPLETE
    ):
        labels.append(FailureLabel.RANKING_FAILURE)
        reasons.append("raw Gold path was complete but ranked retrieval lost it")
    if (
        trace.ranked.outcome == SegmentEvaluationOutcome.COMPLETE
        and trace.context.outcome != SegmentEvaluationOutcome.COMPLETE
    ):
        labels.append(FailureLabel.CONTEXT_SELECTION_LOSS)
        reasons.append("ranked Gold path was complete but final context lost it")
    review_required = False
    if answer_metrics:
        by_id = {metric.metric_id: metric for metric in answer_metrics}
        accuracy = by_id.get("answer_accuracy")
        grounding = by_id.get("answer_groundedness")
        hallucination = by_id.get("answer_hallucination")
        if (
            trace.context.outcome == SegmentEvaluationOutcome.COMPLETE
            and accuracy is not None
            and accuracy.status == MetricStatus.OBSERVED
            and accuracy.value == 0.0
        ):
            labels.append(FailureLabel.GENERATION_FAILURE)
            reasons.append(
                "final segment context completed Gold Evidence but the answer rule failed"
            )
        # Groundedness is intentionally *not* translated into an unsupported
        # answer label.  A strict Gold miss can coexist with semantically
        # equivalent support; it is a retrieval finding, not a hallucination
        # determination.
        if hallucination is not None:
            if (
                hallucination.status == MetricStatus.OBSERVED
                and hallucination.value == 1.0
            ):
                labels.append(FailureLabel.UNSUPPORTED_ANSWER)
                reasons.append(hallucination.reason or "answer was deterministically unsupported")
            elif hallucination.status == MetricStatus.NEEDS_REVIEW:
                review_required = True
                labels.append(FailureLabel.NEEDS_REVIEW)
                reasons.append(hallucination.reason or "answer support requires review")
        if accuracy is not None and accuracy.status == MetricStatus.NEEDS_REVIEW:
            review_required = True
            labels.append(FailureLabel.NEEDS_REVIEW)
            reasons.append(accuracy.reason or "answer equivalence requires review")
        if grounding is not None and grounding.status == MetricStatus.NEEDS_REVIEW:
            review_required = True
            labels.append(FailureLabel.NEEDS_REVIEW)
            reasons.append(grounding.reason or "answer grounding requires review")
    return FailureAssessment(
        labels=list(dict.fromkeys(labels)),
        certainty="unknown" if review_required else "deterministic",
        reasons=list(dict.fromkeys(reasons)),
        review_required=review_required,
    )


def command_for_seed(command: WorkerCommand, seed: int) -> WorkerCommand:
    environment = dict(command.environment)
    environment.update(
        {
            "PYTHONHASHSEED": str(seed),
            "RAG_EVAL_SEED": str(seed),
        }
    )
    return replace(command, environment=environment)


def watch_cancellation(
    cancelled: Callable[[], bool], done: Event, process: WorkerHandle
) -> None:
    while not done.wait(0.05):
        if cancelled():
            process.cancel()
            return


def select_questions(bundle: DatasetBundle, experiment: ExperimentSpec):
    question_by_id = bundle.question_by_id()
    case_ids = experiment.case_ids or sorted(question_by_id)
    unknown = [case_id for case_id in case_ids if case_id not in question_by_id]
    if unknown:
        raise ValueError(f"experiment references unknown cases: {unknown}")
    expected_selection_id = case_selection_id(
        case_ids,
        policy="explicit" if experiment.case_ids is not None else "all",
        seed=experiment.seed,
    )
    if expected_selection_id != experiment.case_selection_id:
        raise ValueError("case_selection_id does not match selected cases/policy/seed")
    return [question_by_id[case_id] for case_id in case_ids]


def select_benchmark_questions(
    dataset: BenchmarkDataset,
    experiment: ExperimentSpec,
) -> list[BenchmarkQuestion]:
    question_by_id = {item.case_id: item for item in dataset.questions}
    case_ids = experiment.case_ids or sorted(question_by_id)
    unknown = [case_id for case_id in case_ids if case_id not in question_by_id]
    if unknown:
        raise ValueError(f"experiment references unknown benchmark cases: {unknown}")
    expected_selection_id = case_selection_id(
        case_ids,
        policy="explicit" if experiment.case_ids is not None else "all",
        seed=experiment.seed,
    )
    if expected_selection_id != experiment.case_selection_id:
        raise ValueError("case_selection_id does not match selected benchmark cases/policy/seed")
    return [question_by_id[case_id] for case_id in case_ids]


def order_questions(
    questions: list[Question] | list[BenchmarkQuestion], seed: int
) -> list[Question] | list[BenchmarkQuestion]:
    """Generate a stable, persisted per-seed order without changing selection."""

    def order_key(question: Question) -> tuple[str, str]:
        payload = f"{seed}\0{question.case_id}".encode()
        return hashlib.sha256(payload).hexdigest(), question.case_id

    return sorted(questions, key=order_key)


def requested_primary_corpus(experiment: ExperimentSpec, bundle: DatasetBundle) -> str:
    """Resolve the explicit primary corpus without changing old run records."""

    requested = experiment.adapter_config.get("evaluation_corpus")
    if requested is None:
        requested = bundle.manifest.metadata.get("primary_evaluation_corpus")
    if requested in (None, "source_document", "native_source"):
        return "source_document"
    if requested in {"canonical_segments", "canonical-segments/v1"}:
        return "canonical_segments"
    raise ValueError(
        "unsupported evaluation_corpus; use 'canonical_segments' or 'source_document'"
    )


def segment_metric_k_values(experiment: ExperimentSpec) -> tuple[int, ...]:
    """The benchmark contract fixes the comparable strict Retrieval cutoffs."""

    values = tuple(
        sorted({int(value) for value in experiment.metric_config.get("k_values", [1, 3, 5, 10])})
    )
    if values != (1, 3, 5, 10):
        raise ValueError("segment-native benchmark requires k_values [1, 3, 5, 10]")
    return values


INGESTION_RPC_RESPONSE_GRACE_SECONDS = 30.0


def ingestion_rpc_timeout(
    command: WorkerCommand,
    adapter_config: Mapping[str, object],
) -> float:
    """Keep the Platform→Worker ingest request aligned with Adapter budget.

    The Worker call encloses all native ingestion work.  A strict Adapter can
    legitimately wait for its own declared ingestion deadline, so the outer
    client must not impose a shorter hidden deadline and turn a live index
    build into a generic ``ReadTimeout``.  The small fixed allowance covers
    serializing the Wire response; the Adapter's configured timeout remains
    the authoritative operational budget.
    """

    def declared_timeout(key: str) -> float | None:
        value = adapter_config.get(key)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value > 0
        ):
            return float(value)
        return None

    # ``ingestion_timeout_seconds`` protects one native track; a corpus with
    # many bounded benchmark batches additionally declares its complete
    # Worker-call budget through ``ingestion_run_timeout_seconds``.  Retain
    # the former as a safe fallback for legacy adapters/configurations.
    candidates = [command.request_timeout_seconds]
    for key in ("ingestion_timeout_seconds", "ingestion_run_timeout_seconds"):
        configured = declared_timeout(key)
        if configured is not None:
            candidates.append(configured + INGESTION_RPC_RESPONSE_GRACE_SECONDS)
    return max(candidates)


def validate_benchmark_ingestion_contract(
    details: Mapping[str, object],
    dataset: BenchmarkDataset,
    *,
    strict_segment_ranking: bool,
) -> None:
    """Reject a run before query if exact leaf-to-native mapping was not proven."""

    if details.get("benchmark_contract_schema_version") != BENCHMARK_CONTRACT_SCHEMA_VERSION:
        raise ValueError("adapter did not acknowledge the benchmark contract schema")
    if details.get("benchmark_contract_digest") != dataset.manifest.contract_digest:
        raise ValueError("adapter benchmark contract digest does not match Dataset Release")
    if details.get("benchmark_segment_inputs") != len(dataset.segments):
        raise ValueError("adapter benchmark input count does not match the contract")
    mapping_status = details.get("benchmark_segment_mapping_status")
    if not strict_segment_ranking:
        if mapping_status != "unsupported_stage":
            raise ValueError("Answer-only adapter must explicitly mark segment mapping unsupported")
        return
    if mapping_status != "verified":
        raise ValueError("adapter did not verify benchmark leaf-to-native mapping")
    if details.get("benchmark_segment_runtime_chunks") != len(dataset.segments):
        raise ValueError("adapter benchmark native chunk count does not match the contract")
    mapping_digest = details.get("benchmark_segment_mapping_file_digest")
    if not isinstance(mapping_digest, str) or len(mapping_digest) != 64:
        raise ValueError("adapter did not pin its benchmark native mapping artifact")


def validate_benchmark_result_capabilities(
    result: RAGResult,
    capabilities: AdapterCapabilities,
) -> None:
    if not capabilities.segment_traces:
        raise ValueError("benchmark Adapter must implement typed segment trace capability")
    if result.segment_traces is None:
        raise ValueError("benchmark Adapter did not return typed segment traces")


def canonical_segment_batch_limit(adapter_config: Mapping[str, object]) -> int:
    """Choose a conservative pre-ingestion envelope below LightRAG's chunk size.

    This is only a packing hint.  The post-ingestion acceptance gate remains
    authoritative and rejects any actual split regardless of this estimate.
    """

    explicit = adapter_config.get("canonical_segment_max_batch_characters")
    if isinstance(explicit, int) and not isinstance(explicit, bool):
        if explicit < 256:
            raise ValueError(
                "canonical_segment_max_batch_characters must be at least 256"
            )
        return explicit
    chunking = adapter_config.get("chunking")
    chunk_size = 1200
    if isinstance(chunking, Mapping):
        candidate = chunking.get("chunk_token_size")
        if isinstance(candidate, int) and not isinstance(candidate, bool) and candidate > 0:
            chunk_size = candidate
    # Treat character count as a deliberately pessimistic token estimate.  A
    # Unicode/tokenizer edge case can still only fail closed at ingest.
    return max(256, min(3000, (chunk_size * 7) // 10))


def source_only_documents(
    bundle: DatasetBundle,
    source_dir: Path,
    *,
    primary_corpus: str = "source_document",
    canonical_segment_max_batch_characters: int | None = None,
) -> list[DocumentInput]:
    if primary_corpus == "canonical_segments":
        return materialize_canonical_segment_documents(
            bundle,
            source_dir,
            max_batch_characters=(
                canonical_segment_max_batch_characters
                if canonical_segment_max_batch_characters is not None
                else 3000
            ),
        )
    if primary_corpus != "source_document":
        raise ValueError(f"unsupported primary corpus {primary_corpus!r}")
    source_dir.mkdir(parents=True, exist_ok=True)
    inputs: list[DocumentInput] = []
    for document in bundle.manifest.documents:
        original = bundle.root / document.path
        suffix = original.suffix.lower()
        safe_digest = hashlib.sha256(document.document_id.encode()).hexdigest()[:12]
        sandbox_path = source_dir / f"source-{len(inputs):05d}-{safe_digest}{suffix}"
        shutil.copyfile(original, sandbox_path)
        content = None
        if document.mime_type.startswith("text/"):
            content = original.read_text(encoding="utf-8")
        metadata: dict[str, object] = {"original_name": original.name}
        if document.canonical_path is not None:
            canonical = bundle.root / document.canonical_path
            canonical_suffix = "".join(canonical.suffixes).lower() or ".data"
            canonical_sandbox_path = (
                source_dir
                / f"canonical-{len(inputs):05d}-{safe_digest}{canonical_suffix}"
            )
            shutil.copyfile(canonical, canonical_sandbox_path)
            metadata.update(
                {
                    "canonical_provenance_path": canonical_sandbox_path.name,
                    "canonical_provenance_sha256": hashlib.sha256(
                        canonical.read_bytes()
                    ).hexdigest(),
                }
            )
        inputs.append(
            DocumentInput(
                document_id=document.document_id,
                content=content,
                source_path=sandbox_path.name,
                sha256=document.sha256,
                mime_type=document.mime_type,
                metadata=metadata,
            )
        )
    return inputs


def direct_native_document(
    documents: list[DocumentInput],
    plan: ResolvedRunPlanV2,
) -> OriginalDocumentV2:
    """Bind the staged source sandbox to the admitted single-DOCX plan."""

    if len(documents) != 1:
        raise ValueError("Direct Wire 2.0 requires exactly one original DOCX")
    document = documents[0]
    if document.content is not None or document.source_path is None:
        raise ValueError("Direct Wire 2.0 cannot ingest inline or missing content")
    if (
        document.document_id != plan.original_document.document_id
        or document.sha256 != plan.original_document.source_sha256
        or document.mime_type != plan.original_document.mime_type
    ):
        raise ValueError("staged DOCX identity differs from the resolved plan")
    canonical_path = document.metadata.get("canonical_provenance_path")
    canonical_digest = document.metadata.get("canonical_provenance_sha256")
    original_name = document.metadata.get("original_name")
    if not all(
        isinstance(value, str) and value
        for value in (canonical_path, canonical_digest, original_name)
    ):
        raise ValueError(
            "Direct Wire 2.0 requires a pinned Canonical Catalog sidecar"
        )
    return OriginalDocumentV2(
        document_id=document.document_id,
        source_path=document.source_path,
        source_sha256=document.sha256 or "",
        media_type=document.mime_type,
        original_name=original_name,
        canonical_catalog_path=canonical_path,
        canonical_catalog_sha256=canonical_digest,
    )


def legacy_manifest_capabilities(
    capabilities: AdapterCapabilitiesV2,
) -> AdapterCapabilities:
    """Populate the non-authoritative RunManifest until Phase 6 removes it."""

    return AdapterCapabilities(
        answer=capabilities.answer,
        raw_retrieval=capabilities.candidate_retrieval,
        ranked_retrieval=capabilities.ranked_retrieval,
        final_context=capabilities.final_context,
        object_provenance=capabilities.provenance,
        prompt_trace=capabilities.prompt_trace,
        latency_breakdown=capabilities.latency_breakdown,
        token_usage=capabilities.token_usage,
    )


class NativeProvenanceContractError(ValueError):
    """A native source cannot be scored without a verified runtime bridge."""


def validate_native_provenance_contract(
    bundle: DatasetBundle,
    questions: list[Question] | tuple[Question, ...],
    documents: list[DocumentInput],
    corpus: CorpusEvidenceIndex,
    *,
    ingestion_details: Mapping[str, object] | None = None,
) -> None:
    """Fail a native-document run before querying when its bridge is unusable.

    Native Word coordinates (paragraph/table/cell) and LightRAG's rendered
    chunk stream are different coordinate systems.  A quote-only fallback can
    help an *offline historical recovery*, but it cannot prove a production
    retrieval hit or miss.  Therefore a run containing native DOCX Gold
    Evidence must have a pinned, round-trip-verified catalog before the first
    query is issued.

    This deliberately validates catalog availability and typed Gold locator
    presence, not whether every Gold object has a complete runtime mapping. An
    unmapped but catalogued Gold object is a legitimate later
    ``provenance_missing`` outcome. Only a complete reverse map can prove
    ``retrieval_missed``; an absent catalog is an ingestion failure.
    """

    native_document_ids = {
        document.document_id
        for document in documents
        if document.content is None
        and (
            "wordprocessingml.document" in document.mime_type.lower()
            or Path(document.source_path or "").suffix.lower() == ".docx"
        )
    }
    if not native_document_ids:
        return

    native_gold: list[tuple[str, str, object]] = []
    for question in questions:
        evidence_set = bundle.gold_evidence_sets.get(question.gold_evidence_set_id)
        if evidence_set is None:
            raise NativeProvenanceContractError(
                f"dataset is missing Gold Evidence set {question.gold_evidence_set_id!r}"
            )
        for evidence in evidence_set.evidence:
            if evidence.document_id in native_document_ids:
                native_gold.append((question.case_id, evidence.evidence_id, evidence))
    # A native document that carries no Gold Evidence is not a localization
    # target for this run.  Do not impose the native contract on it merely
    # because another source in the same Bundle is a DOCX.
    if not native_gold:
        return

    details = ingestion_details if isinstance(ingestion_details, Mapping) else {}
    problems: list[str] = []
    advertised_documents = details.get("canonical_provenance_documents")
    if not isinstance(advertised_documents, int) or isinstance(advertised_documents, bool):
        problems.append("adapter did not report canonical_provenance_documents")
    elif advertised_documents < len(native_document_ids):
        problems.append(
            "adapter reported "
            f"{advertised_documents} canonical provenance document(s) for "
            f"{len(native_document_ids)} native source document(s)"
        )
    if corpus.provenance_map is None:
        problems.append("adapter did not publish a provenance map")
    if not corpus.runtime_chunks:
        problems.append("provenance map contains no runtime chunks")
    if not corpus.object_catalog:
        problems.append("provenance map contains no canonical objects")
    if not any(corpus.reverse_index.values()):
        problems.append("provenance map contains no forward/reverse edges")
    if not corpus.map_pin_verified:
        problems.append("provenance map is not externally digest-pinned")
    if not corpus.source_pins_verified:
        problems.append("provenance map source checksum pins are unavailable or mismatched")
    if not corpus.catalog_round_trip_verified:
        problems.append("provenance map forward/reverse catalog round-trip failed")
    if not corpus.catalog_verified:
        problems.append("provenance catalog is not verified")

    # Do not let a missing table/cell/paragraph object surface later as an
    # opaque per-case "unverifiable" result.  The required source coordinate
    # must exist in the map before an evaluator claims to score it.
    missing_locators = [
        f"{case_id}/{evidence_id}"
        for case_id, evidence_id, evidence in native_gold
        if not corpus.object_ids_for_locator(evidence.document_id, evidence.locator)
    ]
    if missing_locators:
        preview = ", ".join(missing_locators[:8])
        suffix = " …" if len(missing_locators) > 8 else ""
        problems.append(f"Gold locator(s) absent from provenance catalog: {preview}{suffix}")

    if problems:
        diagnostics = "; ".join(corpus.catalog_diagnostics)
        message = (
            "native DOCX provenance contract failed before evaluation: "
            + "; ".join(problems)
        )
        if diagnostics:
            message += f"; diagnostics: {diagnostics}"
        raise NativeProvenanceContractError(message)


class CanonicalSegmentProvenanceContractError(ValueError):
    """The primary canonical corpus has no complete chunk-to-segment proof."""


def validate_canonical_segment_provenance_contract(
    bundle: DatasetBundle,
    questions: list[Question] | tuple[Question, ...],
    documents: list[DocumentInput],
    corpus: CorpusEvidenceIndex,
    *,
    source_dir: Path,
    ingestion_details: Mapping[str, object] | None = None,
) -> None:
    """Enforce the canonical corpus acceptance gate before the first query.

    A primary run can only make retrieval claims after LightRAG has proved all
    of the following facts: every prepared canonical batch was persisted once,
    every persisted chunk has the exact batch bytes, and the batch's declared
    ``chunk -> segment_id(s)`` relation round-trips through the run catalog.
    This is intentionally stricter than a post-hoc textual match.  A missing,
    split, merged, or ambiguous chunk aborts the run at ingestion time.
    """

    primary = [
        item
        for item in documents
        if item.metadata.get("primary_evaluation_corpus") == "canonical_segments"
    ]
    if not primary:
        return
    if len(primary) != len(documents):
        raise CanonicalSegmentProvenanceContractError(
            "canonical primary corpus cannot be mixed with raw source inputs"
        )
    try:
        manifest = load_staged_canonical_segment_manifest(source_dir, documents)
    except CanonicalSegmentError as exc:
        raise CanonicalSegmentProvenanceContractError(
            f"canonical segment manifest is not usable: {exc}"
        ) from exc
    if manifest is None:
        raise CanonicalSegmentProvenanceContractError(
            "canonical segment inputs do not publish a staged manifest"
        )

    details = ingestion_details if isinstance(ingestion_details, Mapping) else {}
    problems: list[str] = []
    if details.get("canonical_segment_manifest_digest") != manifest.manifest_digest:
        problems.append("adapter did not return the pinned canonical segment manifest digest")
    if details.get("canonical_segment_mapping_status") != "verified":
        problems.append("adapter did not report a verified canonical chunk-to-segment map")
    for key, expected in (
        ("canonical_segment_batches", len(manifest.batches)),
        ("canonical_segment_segments", len(manifest.segments)),
        ("canonical_segment_runtime_chunks", len(manifest.batches)),
    ):
        value = details.get(key)
        if value != expected:
            problems.append(
                f"adapter reported {key}={value!r}; expected {expected}"
            )

    payload = corpus.provenance_map
    if not isinstance(payload, Mapping):
        problems.append("adapter did not publish the canonical chunk provenance map")
        payload = {}
    primary_meta = payload.get("primary_corpus")
    if not isinstance(primary_meta, Mapping):
        problems.append("provenance map lacks a primary corpus declaration")
    elif (
        primary_meta.get("mode") != "canonical-segments/v1"
        or primary_meta.get("manifest_digest") != manifest.manifest_digest
    ):
        problems.append("provenance map primary corpus declaration does not match the staged manifest")

    if not corpus.map_pin_verified:
        problems.append("canonical chunk provenance map is not externally digest-pinned")
    if not corpus.source_pins_verified:
        problems.append("canonical chunk provenance source checksum pins are unavailable or mismatched")
    if not corpus.catalog_round_trip_verified or not corpus.catalog_verified:
        problems.append("canonical chunk provenance catalog did not pass forward/reverse round-trip verification")

    expected_batches = {item.batch_id: item for item in manifest.batches}
    expected_segments = {item.segment_id: item for item in manifest.segments}
    raw_segment_catalog = payload.get("segment_catalog")
    if not isinstance(raw_segment_catalog, Mapping):
        problems.append("provenance map lacks a segment catalog")
        raw_segment_catalog = {}
    if set(raw_segment_catalog) != set(expected_segments):
        problems.append("provenance segment catalog does not contain exactly the staged segment IDs")
    else:
        for segment_id, expected in expected_segments.items():
            observed = raw_segment_catalog.get(segment_id)
            if not isinstance(observed, Mapping) or (
                observed.get("content_sha256") != expected.content_sha256
                or observed.get("document_id") != expected.document_id
            ):
                problems.append(
                    f"segment catalog entry {segment_id!r} does not match the staged segment"
                )
                break

    raw_batch_chunks = payload.get("batch_to_runtime_chunks")
    raw_runtime_segments = payload.get("runtime_chunk_to_segment_ids")
    if not isinstance(raw_batch_chunks, Mapping):
        problems.append("provenance map lacks batch-to-runtime-chunk edges")
        raw_batch_chunks = {}
    if not isinstance(raw_runtime_segments, Mapping):
        problems.append("provenance map lacks runtime-chunk-to-segment edges")
        raw_runtime_segments = {}
    if set(raw_batch_chunks) != set(expected_batches):
        problems.append("provenance batch map does not contain exactly the staged batches")
    else:
        expected_runtime_ids: set[str] = set()
        for batch_id, batch in expected_batches.items():
            runtime_ids = raw_batch_chunks.get(batch_id)
            if not isinstance(runtime_ids, list) or len(runtime_ids) != 1 or not isinstance(runtime_ids[0], str):
                problems.append(
                    f"batch {batch_id!r} did not persist as exactly one LightRAG chunk"
                )
                continue
            runtime_id = runtime_ids[0]
            expected_runtime_ids.add(runtime_id)
            runtime = corpus.runtime_chunks.get(runtime_id)
            if not isinstance(runtime, Mapping):
                problems.append(f"runtime chunk {runtime_id!r} is absent from the provenance map")
                continue
            observed_segments = raw_runtime_segments.get(runtime_id)
            if not isinstance(observed_segments, list) or tuple(observed_segments) != batch.segment_ids:
                problems.append(
                    f"runtime chunk {runtime_id!r} has a non-deterministic segment mapping"
                )
            if (
                runtime.get("batch_id") != batch_id
                or tuple(runtime.get("segment_ids") or ()) != batch.segment_ids
                or runtime.get("content_sha256") != batch.content_sha256
                or runtime.get("provenance_status") != "full"
            ):
                problems.append(
                    f"runtime chunk {runtime_id!r} does not exactly match canonical batch {batch_id!r}"
                )
        if expected_runtime_ids != set(corpus.runtime_chunks):
            problems.append("provenance map contains a runtime chunk outside the staged canonical batches")

    # Gold locator identity is checked once before the first query.  An absent
    # locator is an ingestion/contract error, not a completed case with an
    # opaque 'unverifiable' badge.  Whole Word tables are special: their
    # envelope may legitimately be represented by partial row edges, so a
    # deterministic table mapping means *every physical cell* has a full
    # runtime witness, not merely that the table root has any row edge.
    missing_gold: list[str] = []
    for question in questions:
        evidence_set = bundle.gold_evidence_sets.get(question.gold_evidence_set_id)
        if evidence_set is None:
            missing_gold.append(f"{question.case_id}/missing-evidence-set")
            continue
        for evidence in evidence_set.evidence:
            if not _gold_has_deterministic_canonical_mapping(evidence, corpus):
                missing_gold.append(f"{question.case_id}/{evidence.evidence_id}")
    if missing_gold:
        preview = ", ".join(missing_gold[:8])
        suffix = " …" if len(missing_gold) > 8 else ""
        problems.append(f"Gold Evidence lacks deterministic segment mapping: {preview}{suffix}")

    if problems:
        diagnostics = "; ".join(corpus.catalog_diagnostics)
        message = "canonical segment acceptance gate failed before evaluation: " + "; ".join(problems)
        if diagnostics:
            message += f"; diagnostics: {diagnostics}"
        raise CanonicalSegmentProvenanceContractError(message)


def _gold_has_deterministic_canonical_mapping(
    evidence: GoldEvidence,
    corpus: CorpusEvidenceIndex,
) -> bool:
    """Return whether one Gold locator can be deterministically evaluated.

    The canonical segment gate is deliberately stricter than non-empty reverse
    edges.  A partial edge is useful for UI navigation but cannot alone prove
    that a Gold object was retrieved or missed.  A whole table uses its
    physical-cell footprint, which remains valid when its renderer-specific
    table envelope is partitioned across rows.
    """

    document_id = evidence.document_id
    locator = evidence.locator
    if isinstance(locator, ObjectLocator) and locator.object_type == "table":
        return corpus.has_complete_table_footprint(document_id, locator.object_id)

    object_ids = corpus.object_ids_for_locator(document_id, locator)
    if not object_ids:
        return False
    return all(
        any(
            (edge.get("coverage") or edge.get("canonical_object_coverage"))
            == "full"
            for edge in corpus.runtime_edges_for(document_id, object_id)
        )
        for object_id in object_ids
    )


def corpus_evidence_index_after_ingest(
    bundle: DatasetBundle,
    documents: list[DocumentInput],
    *,
    run_dir: Path,
    repetition: int,
    ingestion_details: Mapping[str, object] | None = None,
) -> CorpusEvidenceIndex:
    """Load one pinned provenance catalog for an ingested repetition.

    The adapter's map is a run/work artifact, not the Bundle's canonical
    JSONL source.  Source/quote text and native execution streams are kept in
    separate index views.  If the adapter did not publish a valid, externally
    pinned map, the returned index remains a legacy quote-only index and all
    strict locator decisions fail closed.
    """

    details = ingestion_details if isinstance(ingestion_details, Mapping) else {}
    source_documents = bundle.source_documents()
    runtime_documents = {
        item.document_id: item.content
        for item in documents
        if isinstance(item.content, str)
        and item.metadata.get("primary_evaluation_corpus") != "canonical_segments"
    }
    # Source-only DocumentInput values (the normal DOCX path) cannot supply
    # the native execution coordinate space.  A formal adapter may publish
    # that stream in ingestion details; it is accepted only as a separate
    # runtime view and is still checked against each mapped span below.
    for key in ("runtime_documents", "execution_streams", "native_runtime_documents"):
        value = details.get(key)
        if not isinstance(value, Mapping):
            continue
        for document_id, content in value.items():
            if isinstance(document_id, str) and isinstance(content, str):
                runtime_documents.setdefault(document_id, content)
    diagnostics: list[str] = []
    source_digests: dict[str, str] = {}
    for item in documents:
        if item.metadata.get("primary_evaluation_corpus") == "canonical_segments":
            document_id = item.metadata.get("canonical_segment_source_document_id")
            digest = item.metadata.get("canonical_segment_source_sha256")
            if not isinstance(document_id, str) or not isinstance(digest, str):
                diagnostics.append("canonical segment input lacks a source document checksum pin")
                continue
            previous = source_digests.get(document_id)
            if previous is not None and previous != digest:
                diagnostics.append(
                    "canonical segment inputs disagree about a source document checksum pin"
                )
                continue
            source_digests[document_id] = digest
            continue
        if isinstance(item.sha256, str) and item.sha256:
            source_digests[item.document_id] = item.sha256

    fallback = CorpusEvidenceIndex(
        source_documents,
        runtime_documents=runtime_documents,
        source_digests=source_digests,
        catalog_diagnostics=diagnostics,
    )

    payload: Mapping[str, Any] | None = None
    serialized_map_digest: str | None = None
    embedded = _first_mapping_value(
        details,
        "canonical_provenance_map",
        "provenance_map",
        "canonical_provenance_manifest",
    )
    if isinstance(embedded, Mapping):
        payload = embedded
    else:
        map_path = _resolve_ingestion_map_path(
            run_dir,
            repetition,
            details,
        )
        if map_path is not None:
            try:
                serialized = map_path.read_bytes()
                loaded = json.loads(serialized.decode("utf-8"))
                serialized_map_digest = hashlib.sha256(serialized).hexdigest()
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                loaded = None
            if isinstance(loaded, Mapping):
                payload = loaded
            else:
                diagnostics.append(
                    f"provenance map at {map_path.name!r} is missing or malformed"
                )
        elif _first_text_value(
            details,
            "canonical_provenance_map_path",
            "provenance_map_path",
            "canonical_provenance_manifest_path",
            "provenance_manifest_path",
            "map_path",
        ):
            diagnostics.append("provenance map path is outside the repetition sandbox or missing")

    if payload is None:
        if not diagnostics:
            diagnostics.append("adapter did not publish a provenance map")
        fallback.catalog_diagnostics = tuple(diagnostics)
        return fallback

    # A map payload may carry its native stream even when the adapter did not
    # duplicate it in ``IngestionResult.details``.  Keep the explicit
    # details/document view authoritative for matching IDs, then add map
    # aliases that are not already present.  This avoids replacing a pinned
    # native stream with the Bundle's canonical JSONL text.
    formal_runtime_documents = dict(runtime_documents)
    payload_runtime_documents = payload.get("runtime_documents") or payload.get(
        "execution_streams"
    )
    if isinstance(payload_runtime_documents, Mapping):
        for document_id, content in payload_runtime_documents.items():
            if isinstance(document_id, str) and isinstance(content, str):
                formal_runtime_documents.setdefault(document_id, content)

    expected_digest = _first_text_value(
        details,
        "canonical_provenance_map_digest",
        "provenance_map_digest",
        "map_digest",
    )
    # A malformed or mismatched ingestion digest deliberately leaves the map
    # untrusted.  The index still exposes diagnostics and source text without
    # manufacturing a formal retrieval result.
    if expected_digest is not None and not _valid_sha256_digest(expected_digest):
        diagnostics.append("adapter provenance map digest is malformed")
        expected_digest = None
    try:
        index = CorpusEvidenceIndex.from_provenance_map(
            payload,
            documents=source_documents,
            runtime_documents=formal_runtime_documents,
            source_digests=source_digests,
            expected_map_digest=expected_digest,
            expected_map_bytes_digest=expected_digest,
            map_bytes_digest=serialized_map_digest,
            catalog_diagnostics=diagnostics,
        )
        if expected_digest is None:
            index.catalog_diagnostics = tuple(
                (*index.catalog_diagnostics, "provenance map lacks an external digest pin")
            )
        elif not index.map_pin_verified:
            index.catalog_diagnostics = tuple(
                (*index.catalog_diagnostics, "provenance map digest does not match the loaded payload")
            )
        if not index.source_pins_verified:
            index.catalog_diagnostics = tuple(
                (*index.catalog_diagnostics, "provenance map source pins are incomplete or mismatched")
            )
        if not index.catalog_verified and not index.catalog_round_trip_verified:
            index.catalog_diagnostics = tuple(
                (*index.catalog_diagnostics, "provenance forward/reverse/catalog edges failed round-trip validation")
            )
        return index
    except (TypeError, ValueError):
        diagnostics.append("provenance map could not be loaded under the formal catalog contract")
        fallback.catalog_diagnostics = tuple(diagnostics)
        return fallback


def _resolve_ingestion_map_path(
    run_dir: Path,
    repetition: int,
    details: Mapping[str, object],
) -> Path | None:
    """Resolve adapter map paths while enforcing the run sandbox boundary."""

    raw = _first_text_value(
        details,
        "canonical_provenance_map_path",
        "provenance_map_path",
        "canonical_provenance_manifest_path",
        "provenance_manifest_path",
        "map_path",
    )
    rep_dir = run_dir / "work" / f"rep-{repetition:04d}"
    candidates: list[Path] = []
    explicit = bool(raw)
    if raw:
        requested = Path(raw)
        if requested.is_absolute():
            candidates.append(requested)
            # Docker adapters may report the container mount rather than the
            # host path.  Translate only the exact, known mount prefix for
            # this repetition; arbitrary absolute paths remain rejected and
            # cannot escape the host run sandbox.
            parts = requested.parts
            repetition_name = f"rep-{repetition:04d}"
            for index in range(len(parts) - 2):
                if (
                    parts[index : index + 2] == ("rag-eval", "work")
                    and parts[index + 2] == repetition_name
                ):
                    suffix_parts = parts[index + 3 :]
                    if suffix_parts:
                        candidates.append(rep_dir.joinpath(*suffix_parts))
                    break
        else:
            candidates.extend((rep_dir / requested, run_dir / requested))
    # Current worker adapters use this deterministic path and may only return
    # the digest in IngestionResult.details.
    if not explicit:
        candidates.append(rep_dir / "canonical-provenance-map.json")
    rep_root = rep_dir.resolve()
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(rep_root)
        except (OSError, ValueError):
            continue
        if resolved.is_file():
            return resolved
    # An explicitly advertised path must not silently fall back to another
    # repetition's default map when it is missing, malformed, or outside the
    # sandbox.  The caller records the resulting diagnostic and scores formal
    # provenance as unavailable.
    return None


def _first_mapping_value(mapping: Mapping[str, object], *keys: str) -> Mapping[str, Any] | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def _first_text_value(mapping: Mapping[str, object], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _valid_sha256_digest(value: str) -> bool:
    normalized = value.removeprefix("sha256:")
    return len(normalized) == 64 and all(
        character in "0123456789abcdef" for character in normalized
    )


def metric_k_values(experiment: ExperimentSpec) -> tuple[int, ...]:
    raw = experiment.metric_config.get("k_values", [1, 3, 5])
    values = tuple(sorted({int(value) for value in raw}))
    if not values or any(value < 1 for value in values):
        raise ValueError("metric k_values must contain positive integers")
    return values


def failed_case(
    case_id,
    question,
    gold_answer,
    evidence_set,
    started,
    *,
    status,
    code,
    message,
    experiment,
    repetition=1,
    seed=0,
) -> CaseResult:
    answer_metric_ids = [
        "answer_accuracy",
        "answer_groundedness",
        "unsupported_answer_rate",
    ]
    retrieval_metric_ids: list[str] = []
    for stage in ("raw", "ranked", "context"):
        retrieval_metric_ids.extend(
            f"{stage}_recall@{cutoff}" for cutoff in metric_k_values(experiment)
        )
    for cutoff in metric_k_values(experiment):
        retrieval_metric_ids.extend(
            [f"retrieval_stage_delta@{cutoff}", f"context_selection_loss@{cutoff}"]
        )
    retrieval_metric_ids.extend(["raw_mrr", "ranked_mrr"])
    metrics = [
        MetricResult(
            metric_id=metric_id,
            status=MetricStatus.ERROR,
            scorer_id=(
                GROUNDING_SCORER_ID
                if metric_id in {"answer_groundedness", "unsupported_answer_rate"}
                else ANSWER_SCORER_ID
            ),
            scorer_version=(
                GROUNDING_SCORER_VERSION
                if metric_id in {"answer_groundedness", "unsupported_answer_rate"}
                else ANSWER_SCORER_VERSION
            ),
            scorer_digest=(
                GROUNDING_SCORER_DIGEST
                if metric_id in {"answer_groundedness", "unsupported_answer_rate"}
                else ANSWER_SCORER_DIGEST
            ),
            evaluator_mode="deterministic_gold_evidence"
            if metric_id in {"answer_groundedness", "unsupported_answer_rate"}
            else None,
            reason=message,
        )
        for metric_id in answer_metric_ids
    ]
    metrics.extend(
        MetricResult(
            metric_id=metric_id,
            status=MetricStatus.ERROR,
            scorer_id=EVIDENCE_SCORER_ID,
            scorer_version=EVIDENCE_SCORER_VERSION,
            scorer_digest=EVIDENCE_SCORER_DIGEST,
            reason=message,
        )
        for metric_id in retrieval_metric_ids
    )
    if not experiment.query_config.get("generate_answer", True):
        metrics = [
            metric.model_copy(
                update={
                    "status": MetricStatus.NOT_APPLICABLE,
                    "reason": "answer generation is disabled for this experiment",
                }
            )
            if metric.metric_id in answer_metric_ids
            else metric
            for metric in metrics
        ]
    return CaseResult(
        case_id=case_id,
        status=status,
        question=question,
        gold_answer=gold_answer,
        gold_evidence_set=evidence_set,
        metrics=metrics,
        error=CaseError(code=code, message=message),
        failure_assessment=assess_failure(
            status=status,
            result=None,
            evidence_set=evidence_set,
            corpus=CorpusEvidenceIndex({}),
            metrics=metrics,
        ),
        started_at=started,
        completed_at=datetime.now(UTC),
        repetition=repetition,
        seed=seed,
    )


def execution_counts(
    results: list[CaseResult], *, expected: int | None = None
) -> dict[str, int]:
    expected = len(results) if expected is None else expected
    counts = {
        "expected": expected,
        "total": len(results),
        "not_run": max(0, expected - len(results)),
        "completed": 0,
        "timeout": 0,
        "system_error": 0,
        "cancelled": 0,
    }
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return counts


def artifact_execution_counts(
    cases: list[RunArtifactCaseV2],
    *,
    expected: int,
) -> dict[str, int]:
    counts = {
        "expected": expected,
        "total": len(cases),
        "not_run": max(0, expected - len(cases)),
        "completed": 0,
        "timeout": 0,
        "system_error": 0,
        "cancelled": 0,
    }
    for case in cases:
        counts[case.status] = counts.get(case.status, 0) + 1
    return counts


def aggregate_metrics(
    results: list[CaseResult], *, repetitions: int = 1, expected: int | None = None
) -> dict[str, object]:
    metric_ids = sorted(
        {metric.metric_id for result in results for metric in result.metrics}
    )
    aggregate: dict[str, object] = {}
    for metric_id in metric_ids:
        values = [
            metric
            for result in results
            for metric in result.metrics
            if metric.metric_id == metric_id
        ]
        applicable = [
            metric
            for metric in values
            if metric.status == MetricStatus.OBSERVED
        ]
        status_counts = {
            status.value: sum(metric.status == status for metric in values)
            for status in MetricStatus
        }
        # ``coverage`` remains the historical all-case observation rate.  A
        # benchmark can, however, contain an abstention/negative case whose
        # retrieval metrics are correctly *not applicable*.  Keep that case
        # visible in the legacy rate, but also publish the rate across cases
        # for which this metric is actually scoreable.  This prevents a
        # correct N/A result from being mistaken for missing metric support.
        scoreable_cases = len(values) - status_counts[MetricStatus.NOT_APPLICABLE.value]
        scoreable_coverage = (
            len(applicable) / scoreable_cases if scoreable_cases else 0.0
        )
        if not applicable:
            status = (
                "needs_review"
                if status_counts[MetricStatus.NEEDS_REVIEW.value]
                else "not_applicable"
                if status_counts[MetricStatus.NOT_APPLICABLE.value]
                else "error"
                if status_counts[MetricStatus.ERROR.value]
                else "unavailable"
            )
            reasons = sorted(
                {
                    metric.reason
                    for metric in values
                    if isinstance(metric.reason, str) and metric.reason.strip()
                }
            )
            aggregate[metric_id] = {
                "status": status,
                "value": None,
                "denominator": 0,
                "coverage": 0.0,
                "scoreable_cases": scoreable_cases,
                "scoreable_coverage": scoreable_coverage,
                "errors": status_counts[MetricStatus.ERROR.value],
                "status_counts": status_counts,
                # Product readers need an actionable reason for an
                # unavailable aggregate.  Preserve the compact distinct set
                # rather than making the UI guess from a zero denominator.
                "reason": " · ".join(reasons) if reasons else None,
            }
            continue
        numerator = sum(
            metric.value or 0.0
            for metric in applicable
            if metric.status == MetricStatus.OBSERVED
        )
        repetition_values: list[float] = []
        for repetition in range(1, repetitions + 1):
            repeated = [
                metric
                for result in results
                if result.repetition == repetition
                for metric in result.metrics
                if metric.metric_id == metric_id
                and metric.status == MetricStatus.OBSERVED
            ]
            if repeated:
                repetition_values.append(
                    sum(
                        metric.value or 0.0
                        for metric in repeated
                    )
                    / len(repeated)
                )
        aggregate[metric_id] = {
            "status": "observed",
            "value": numerator / len(applicable),
            "mean": numerator / len(applicable),
            "standard_deviation": pstdev(repetition_values)
            if len(repetition_values) > 1
            else 0.0,
            "repetition_values": repetition_values,
            "numerator": numerator,
            "denominator": len(applicable),
            "errors": sum(metric.status == MetricStatus.ERROR for metric in applicable),
            "coverage": len(applicable) / expected if expected else 0.0,
            "scoreable_cases": scoreable_cases,
            "scoreable_coverage": scoreable_coverage,
            "status_counts": status_counts,
        }
    counts = execution_counts(results, expected=expected)
    expected_count = counts["expected"]
    failures = expected_count - counts["completed"]
    execution = {
        **counts,
        "execution_failure_rate": failures / expected_count
        if expected_count
        else 0.0,
    }
    return {"metrics": aggregate, "execution": execution}


def validate_result_capabilities(
    result, capabilities, *, generate_answer: bool
) -> None:
    fields = {
        "answer": result.answer,
        "raw_retrieval": result.raw_retrieval,
        "ranked_retrieval": result.ranked_retrieval,
        "final_context": result.final_context,
        "latency_breakdown": result.latency,
        "token_usage": result.token_usage,
    }
    for capability, value in fields.items():
        declared = getattr(capabilities, capability)
        required = declared and (capability != "answer" or generate_answer)
        if required and value is None:
            raise ValueError(
                f"adapter declared {capability} but query returned it as unavailable"
            )
        if not declared and value is not None:
            raise ValueError(
                f"adapter returned {capability} without declaring the capability"
            )
