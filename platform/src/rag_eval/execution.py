"""Native v2 Run execution through an isolated Adapter Worker."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread

import httpx

from rag_eval import __version__
from rag_eval.artifact_contract import artifact_digest as contract_digest
from rag_eval.contracts.adapter import DocumentInput
from rag_eval.contracts.dataset import Question
from rag_eval.contracts.native import (
    NativeQueryV2,
    OriginalDocumentV2,
    PreparedSystemV2,
    ResolvedAdapterConfigV2,
)
from rag_eval.contracts.observation import ObservationStatus
from rag_eval.contracts.research import LatencyProtocol, ModelArtifactIdentity
from rag_eval.contracts.run import ExperimentSpec
from rag_eval.contracts.wire import WorkerIdentityV2
from rag_eval.datasets.bundle import DatasetBundle, DatasetBundleStore, case_selection_id
from rag_eval.datasets.formal import DatasetReleaseStore
from rag_eval.evaluation.unified import EvaluationProfile
from rag_eval.execution_provider import (
    ExecutionProvider,
    ExecutionRequest,
    LocalProcessProvider,
    WorkerHandle,
)
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
from rag_eval.runs.records import RunRecordStoreV2, RunRecordV2
from rag_eval.runtime_admission import NATIVE_DOCUMENT_EXECUTION_CONTRACT
from rag_eval.worker.client import WorkerProtocolError, WorkerRemoteError
from rag_eval.worker.process import WorkerCommand


class RunExecutor:
    """Execute one admitted Native v2 plan and publish one Artifact 2.0."""

    def __init__(
        self,
        dataset_store: DatasetBundleStore,
        run_records: RunRecordStoreV2,
        provider: ExecutionProvider | None = None,
        dataset_release_store: DatasetReleaseStore | None = None,
    ) -> None:
        self.dataset_store = dataset_store
        self.run_records = run_records
        self.provider = provider or LocalProcessProvider()
        self.dataset_release_store = dataset_release_store

    def execute(
        self,
        experiment: ExperimentSpec,
        command: WorkerCommand,
        *,
        run_id: str | None = None,
        cancelled: Callable[[], bool] | None = None,
        worker_started: Callable[[str, int], None] | None = None,
        resolved_plan: ResolvedRunPlanV2 | None = None,
        resolved_plan_reference: ResolvedRunPlanReferenceV2 | None = None,
    ) -> RunRecordV2:
        run_id = run_id or uuid.uuid4().hex
        cancelled = cancelled or (lambda: False)
        if resolved_plan is None or resolved_plan_reference is None:
            raise ValueError(
                "RunExecutor accepts only an admitted Native v2 resolved plan"
            )

        bundle = self.dataset_store.get(experiment.bundle_id)
        self._validate_plan_inputs(
            experiment,
            command,
            bundle,
            resolved_plan,
            resolved_plan_reference,
        )
        self._validate_dataset_release_reference(experiment, bundle)
        questions = select_questions(bundle, experiment)
        question_orders = {
            seed: order_questions(questions, seed)
            for seed in (
                experiment.seed + offset
                for offset in range(experiment.repetitions)
            )
        }
        self.run_records.create(
            run_id=run_id,
            experiment_id=experiment.experiment_id,
            resolved_plan=resolved_plan_reference,
        )

        artifact_cases: list[RunArtifactCaseV2] = []
        first_worker_identity: WorkerIdentityV2 | None = None
        validation_effective_config: dict[str, object] | None = None
        cancelled_run = False
        resolved_adapter_config = dict(experiment.adapter_config)
        try:
            run_dir = self.run_records.prepare_execution_layout(run_id)
            source_dir = run_dir / "source"
            documents = source_only_documents(bundle, source_dir)
            original_docx = direct_native_document(documents, resolved_plan)

            for repetition in range(1, experiment.repetitions + 1):
                if cancelled():
                    cancelled_run = True
                    break
                repetition_seed = experiment.seed + repetition - 1
                worker_run_id = f"{run_id}-rep-{repetition:04d}"
                seeded_command = command_for_seed(command, repetition_seed)
                handle = self.provider.start(
                    ExecutionRequest(
                        command=seeded_command,
                        run_id=worker_run_id,
                        log_path=(
                            run_dir
                            / "worker"
                            / f"rep-{repetition:04d}.worker.log"
                        ),
                        source_dir=source_dir,
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

                    worker_identity = client.health().identity
                    validate_worker_identity(
                        worker_identity,
                        experiment,
                        first_worker_identity,
                    )
                    if first_worker_identity is None:
                        first_worker_identity = worker_identity
                        self.run_records.mark_running(run_id)

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
                        prepared,
                        experiment,
                        validation_effective_config,
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
                    elif current_effective != validation_effective_config:
                        raise ValueError(
                            "effective configuration changed across repetitions"
                        )

                    if experiment.latency_protocol is not None:
                        validate_latency_runtime(
                            prepared.effective_config,
                            experiment.latency_protocol,
                        )
                        run_latency_warmup(client, prepared, experiment)

                    for question in question_orders[repetition_seed]:
                        if cancelled():
                            cancelled_run = True
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
                            profile=resolved_plan.evaluation_profile,
                            expected_identity=worker_identity,
                        )
                        artifact_cases.append(artifact_case)
                        if artifact_case.status == "cancelled":
                            cancelled_run = True
                            break
                finally:
                    watcher_done.set()
                    handle.stop()
                    if watcher is not None:
                        watcher.join(timeout=1)
                if cancelled_run:
                    break

            if cancelled_run:
                return self.run_records.mark_cancelled(run_id)
            if first_worker_identity is None:
                raise RuntimeError("run did not start")
            expected_cases = len(questions) * experiment.repetitions
            if len(artifact_cases) != expected_cases:
                raise ValueError(
                    "Native v2 Run did not produce one Artifact case per planned execution"
                )
            benchmark_identity = benchmark_identity_from_release_metadata(
                bundle_id=bundle.bundle_id,
                case_selection_id=experiment.case_selection_id,
                dataset_release_id=experiment.dataset_release_id,
                metadata=bundle.manifest.metadata,
                document_sources={
                    document.document_id: document.sha256
                    for document in bundle.manifest.documents
                },
                cases=tuple(artifact_cases),
            )
            if benchmark_identity is None:
                raise ValueError(
                    "Native v2 Run could not bind Artifact 2.0 to its Benchmark Release"
                )
            running = self.run_records.get(run_id)
            if running.started_at is None:
                raise ValueError("running RunRecordV2 has no start timestamp")
            ArtifactWriter(run_dir).publish(
                run_id=run_id,
                experiment_id=experiment.experiment_id,
                benchmark_identity=benchmark_identity,
                cases=tuple(artifact_cases),
                started_at=running.started_at,
                completed_at=datetime.now(UTC),
            )
            # The store verifies the atomically published Artifact and its
            # immutable plan binding before exposing COMPLETED.
            return self.run_records.mark_completed(run_id)
        except Exception as exc:
            try:
                if cancelled():
                    self.run_records.mark_cancelled(run_id)
                else:
                    self.run_records.mark_failed(
                        run_id,
                        error=str(exc) or type(exc).__name__,
                    )
            except (FileNotFoundError, ValueError):
                # Never mask the execution failure. A terminal/completed
                # record cannot be rewritten by this defensive boundary.
                pass
            raise

    @staticmethod
    def _validate_plan_inputs(
        experiment: ExperimentSpec,
        command: WorkerCommand,
        bundle: DatasetBundle,
        plan: ResolvedRunPlanV2,
        reference: ResolvedRunPlanReferenceV2,
    ) -> None:
        if not plan.matches_experiment(experiment):
            raise ValueError("Experiment does not match its immutable resolved plan")
        if (
            command.adapter_id != plan.system.adapter_id
            or command.adapter_factory != plan.system.adapter_factory
            or command.request_timeout_seconds
            != plan.system.worker_request_timeout_seconds
        ):
            raise ValueError("Worker command does not match the immutable resolved plan")
        if plan.metric_descriptors != formal_metric_descriptors(
            plan.evaluation_profile
        ):
            raise ValueError(
                "resolved plan scorer descriptors do not match the running Platform"
            )
        if reference.digest != contract_digest(plan):
            raise ValueError("resolved plan reference digest mismatch")
        documents_by_id = {
            document.document_id: document for document in bundle.manifest.documents
        }
        planned_document = documents_by_id.get(plan.original_document.document_id)
        if (
            planned_document is None
            or planned_document.sha256 != plan.original_document.source_sha256
            or planned_document.path != plan.original_document.runtime_path
        ):
            raise ValueError(
                "runtime Bundle does not match the resolved original DOCX identity"
            )

    def _validate_dataset_release_reference(
        self,
        experiment: ExperimentSpec,
        bundle: DatasetBundle,
    ) -> None:
        """Bind an opted-in Run to exactly one immutable Benchmark Release."""

        if experiment.dataset_release_id is None:
            return
        if self.dataset_release_store is None:
            raise ValueError(
                "Dataset Release references are unavailable in this Platform mode"
            )
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
            return
        raise ValueError(
            "selected formal Dataset Release does not expose the Native v2 DOCX projection"
        )


def execution_view_identity(
    _experiment: ExperimentSpec,
    bundle: DatasetBundle,
) -> tuple[str, bool]:
    """Return the sole admitted Native v2 execution view."""

    formal_projection = bundle.manifest.metadata.get("formal_runtime_projection")
    if (
        isinstance(formal_projection, dict)
        and formal_projection.get("projection_version") == "4"
        and formal_projection.get("execution_contract")
        == NATIVE_DOCUMENT_EXECUTION_CONTRACT
    ):
        return NATIVE_DOCUMENT_EXECUTION_CONTRACT, False
    raise ValueError("execution requires an admitted Native v2 DOCX projection")


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
            raise ValueError(
                "formal worker prepare response lacks model artifact identities"
            )
        actual = prepared_model_artifacts(prepared, experiment)
        if set(actual) != set(experiment.model_artifacts):
            raise ValueError(
                "worker model identities do not match the frozen model lock"
            )
        for name, expected in experiment.model_artifacts.items():
            observed = actual[name]
            if not observed.verified or observed.identity != expected.identity:
                raise ValueError(
                    f"worker model identity drift for {name}: "
                    f"expected {expected.identity}, observed {observed.identity}"
                )


def validate_latency_runtime(
    effective_config: dict[str, object],
    protocol: LatencyProtocol,
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
                retrieval_candidate_k=experiment.query_config[
                    "retrieval_candidate_k"
                ],
                final_context_k=experiment.query_config["final_context_k"],
                max_context_tokens=experiment.query_config["max_context_tokens"],
                generation_options=experiment.query_config["generation_options"],
            ),
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
    prepared: PreparedSystemV2,
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
    """Execute one Direct Wire 2.0 query and produce unified evaluation."""

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
    cancelled: Callable[[], bool],
    done: Event,
    process: WorkerHandle,
) -> None:
    while not done.wait(0.05):
        if cancelled():
            process.cancel()
            return


def select_questions(
    bundle: DatasetBundle,
    experiment: ExperimentSpec,
) -> list[Question]:
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


def order_questions(questions: list[Question], seed: int) -> list[Question]:
    """Generate a stable per-seed order without changing selection."""

    def order_key(question: Question) -> tuple[str, str]:
        payload = f"{seed}\0{question.case_id}".encode()
        return hashlib.sha256(payload).hexdigest(), question.case_id

    return sorted(questions, key=order_key)


INGESTION_RPC_RESPONSE_GRACE_SECONDS = 30.0


def ingestion_rpc_timeout(
    command: WorkerCommand,
    adapter_config: Mapping[str, object],
) -> float:
    """Keep the Platform-to-Worker ingest request aligned with Adapter budget."""

    def declared_timeout(key: str) -> float | None:
        value = adapter_config.get(key)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value > 0
        ):
            return float(value)
        return None

    candidates = [command.request_timeout_seconds]
    for key in ("ingestion_timeout_seconds", "ingestion_run_timeout_seconds"):
        configured = declared_timeout(key)
        if configured is not None:
            candidates.append(configured + INGESTION_RPC_RESPONSE_GRACE_SECONDS)
    return max(candidates)


def source_only_documents(
    bundle: DatasetBundle,
    source_dir: Path,
) -> list[DocumentInput]:
    """Stage the Benchmark's original sources for Direct Wire 2.0."""

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
        raise ValueError("Direct Wire 2.0 requires a pinned Canonical Catalog sidecar")
    return OriginalDocumentV2(
        document_id=document.document_id,
        source_path=document.source_path,
        source_sha256=document.sha256 or "",
        media_type=document.mime_type,
        original_name=original_name,
        canonical_catalog_path=canonical_path,
        canonical_catalog_sha256=canonical_digest,
    )


__all__ = [
    "RunExecutor",
    "command_for_seed",
    "direct_native_document",
    "execution_view_identity",
    "ingestion_rpc_timeout",
    "order_questions",
    "prepared_model_artifacts",
    "run_latency_warmup",
    "select_questions",
    "source_only_documents",
    "validate_latency_runtime",
    "validate_prepared_v2",
    "validate_worker_identity",
]
