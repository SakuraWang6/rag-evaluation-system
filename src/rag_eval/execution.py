"""Standalone run execution through an isolated adapter worker."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from statistics import pstdev
from threading import Event, Thread
from time import monotonic

import httpx

from rag_eval import __version__
from rag_eval.contracts.adapter import (
    AdapterCapabilities,
    DocumentInput,
    PrepareContext,
    PreparedSystem,
    RAGQuery,
)
from rag_eval.contracts.dataset import Question
from rag_eval.contracts.research import LatencyProtocol, ModelArtifactIdentity
from rag_eval.contracts.run import (
    CaseError,
    CaseResult,
    ExperimentSpec,
    MetricResult,
    MetricStatus,
    RunManifest,
    RunStatus,
)
from rag_eval.contracts.wire import HandshakeResponse
from rag_eval.datasets.bundle import (
    DatasetBundle,
    DatasetBundleStore,
    case_selection_id,
)
from rag_eval.evaluation.answers import (
    ANSWER_SCORER_DIGEST,
    ANSWER_SCORER_ID,
    ANSWER_SCORER_VERSION,
)
from rag_eval.evaluation.engine import evaluate_case
from rag_eval.evaluation.evidence import (
    EVIDENCE_SCORER_DIGEST,
    EVIDENCE_SCORER_ID,
    EVIDENCE_SCORER_VERSION,
    CorpusEvidenceIndex,
)
from rag_eval.evaluation.failures import assess_failure
from rag_eval.report import markdown_report
from rag_eval.reproducibility import capture_reproducibility
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.runs import RunStore
from rag_eval.worker.client import WorkerRemoteError
from rag_eval.execution_provider import (
    ExecutionProvider,
    ExecutionRequest,
    LocalProcessProvider,
    WorkerHandle,
)
from rag_eval.worker.process import WorkerCommand


class RunExecutor:
    def __init__(
        self,
        dataset_store: DatasetBundleStore,
        run_store: RunStore,
        provider: ExecutionProvider | None = None,
    ) -> None:
        self.dataset_store = dataset_store
        self.run_store = run_store
        self.provider = provider or LocalProcessProvider()

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
    ) -> RunManifest:
        run_id = run_id or uuid.uuid4().hex
        cancelled = cancelled or (lambda: False)
        bundle = self.dataset_store.get(experiment.bundle_id)
        questions = select_questions(bundle, experiment)
        question_orders = {
            repetition_seed: order_questions(questions, repetition_seed)
            for repetition_seed in (
                experiment.seed + offset for offset in range(experiment.repetitions)
            )
        }
        run_dir = self.run_store.prepare_execution_layout(run_id)
        manifest: RunManifest | None = None
        documents: list[DocumentInput] | None = None
        corpus: CorpusEvidenceIndex | None = None
        results: list[CaseResult] = []
        index_fingerprints: list[str] = []
        index_artifact_digests: list[str] = []
        first_handshake = None
        # The raw worker response is kept only in memory for repetition
        # validation. Persisted artifacts must not contain resolved endpoints.
        validation_effective_config: dict[str, object] | None = None
        effective_config: dict[str, object] | None = None
        repetition_seeds = [
            experiment.seed + offset for offset in range(experiment.repetitions)
        ]
        try:
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
                    handshake = client.handshake()
                    validate_handshake(handshake, experiment, first_handshake)
                    if first_handshake is None:
                        first_handshake = handshake
                        manifest = initial_manifest(
                            run_id,
                            experiment,
                            bundle,
                            handshake,
                            repetition_seeds,
                            replay_of_run_id,
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
                        documents = source_only_documents(bundle, source_dir)
                        corpus = CorpusEvidenceIndex(bundle.source_documents())
                    assert manifest is not None
                    assert documents is not None
                    assert corpus is not None
                    source_dir = run_dir / "source"
                    prepared = client.prepare(
                        handle.prepare_context(PrepareContext(
                            run_id=worker_run_id,
                            work_dir=str(
                                run_dir / "work" / f"rep-{repetition:04d}"
                            ),
                            source_dir=str(source_dir),
                            platform_version=__version__,
                            seed=repetition_seed,
                            repetition=repetition,
                        )),
                        experiment.adapter_config,
                    )
                    validate_prepared(
                        prepared, experiment, validation_effective_config
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
                                "status": RunStatus.INGESTING,
                                "system_version": prepared.system_version,
                                "effective_config": effective_config,
                                "observed_capabilities": prepared.capabilities,
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
                    ingestion = client.ingest(documents)
                    if ingestion.index_fingerprint is None:
                        raise ValueError("adapter did not return an index fingerprint")
                    index_fingerprints.append(ingestion.index_fingerprint)
                    artifact_digest = ingestion.details.get("index_artifact_digest")
                    if artifact_digest is not None:
                        if not isinstance(artifact_digest, str) or not artifact_digest.startswith(
                            "sha256:"
                        ):
                            raise ValueError("adapter returned malformed index artifact digest")
                        index_artifact_digests.append(artifact_digest)
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
                            prepared.capabilities,
                            experiment,
                        )
                    for question in question_orders[repetition_seed]:
                        if cancelled():
                            manifest = manifest.model_copy(
                                update={"status": RunStatus.CANCELLED}
                            )
                            break
                        case = execute_case(
                            client,
                            prepared.capabilities,
                            question,
                            bundle,
                            corpus,
                            experiment,
                            cancelled,
                            repetition,
                            repetition_seed,
                        )
                        self.run_store.write_case(run_id, case)
                        results.append(case)
                        if case.status == "cancelled":
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
            if manifest.status != RunStatus.CANCELLED:
                manifest = manifest.model_copy(update={"status": RunStatus.COMPLETED})
            expected_cases = len(questions) * experiment.repetitions
            counts = execution_counts(results, expected=expected_cases)
            summary = aggregate_metrics(
                results,
                repetitions=experiment.repetitions,
                expected=expected_cases,
            )
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
            manifest = manifest.model_copy(
                update={
                    "completed_at": datetime.now(UTC),
                    "execution_counts": counts,
                    "artifacts": {
                        **manifest.artifacts,
                        "summary": "summary.json",
                        "case_order": "case-order.json",
                        "cases": "cases/",
                        "reproducibility": "reproducibility/",
                        "report": "report.md",
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
            raise


def initial_manifest(
    run_id: str,
    experiment: ExperimentSpec,
    bundle: DatasetBundle,
    handshake: HandshakeResponse,
    repetition_seeds: list[int],
    replay_of_run_id: str | None,
) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        experiment_id=experiment.experiment_id,
        status=RunStatus.PREPARING,
        bundle_id=bundle.bundle_id,
        case_selection_id=experiment.case_selection_id,
        platform_version=__version__,
        adapter_id=handshake.adapter_id,
        adapter_version=handshake.adapter_version,
        system_id=handshake.system_id,
        system_version=handshake.system_version,
        declared_config={
            "adapter": experiment.adapter_config,
            "query": experiment.query_config,
            "metrics": experiment.metric_config,
            "model_lock_digest": experiment.model_lock_digest,
            "comparison_spec_digest": experiment.comparison_spec_digest,
            "analysis_contract_digest": experiment.analysis_contract_digest,
            "latency_protocol_digest": experiment.latency_protocol_digest,
            "formal": experiment.formal,
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
        },
        model_artifacts=experiment.model_artifacts,
        declared_capabilities=handshake.capabilities,
        observed_capabilities=handshake.capabilities,
        seed=experiment.seed,
        repetitions=experiment.repetitions,
        latency_protocol_digest=experiment.latency_protocol_digest,
        repetition_seeds=repetition_seeds,
        replay_of_run_id=replay_of_run_id,
        started_at=datetime.now(UTC),
    )


def validate_handshake(
    handshake: HandshakeResponse,
    experiment: ExperimentSpec,
    first: HandshakeResponse | None,
) -> None:
    if handshake.adapter_id != experiment.adapter_id:
        raise ValueError("worker adapter_id does not match ExperimentSpec")
    if handshake.system_id != experiment.system_id:
        raise ValueError("worker system_id does not match ExperimentSpec")
    if first is not None and handshake != first:
        raise ValueError("worker handshake changed across repetitions")


def validate_prepared(
    prepared: PreparedSystem,
    experiment: ExperimentSpec,
    previous_effective: dict[str, object] | None,
) -> None:
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
    capabilities: AdapterCapabilities,
    experiment: ExperimentSpec,
) -> None:
    assert experiment.latency_protocol is not None
    protocol = experiment.latency_protocol
    for index in range(protocol.warmup_queries):
        result = client.query(
            RAGQuery(
                case_id=f"__rag_eval_warmup_{index + 1}",
                question=protocol.warmup_question,
                generate_answer=False,
                retrieval_candidate_k=experiment.query_config.get("retrieval_candidate_k"),
                final_context_k=experiment.query_config.get("final_context_k"),
                max_context_tokens=experiment.query_config.get("max_context_tokens"),
                generation_options=experiment.query_config.get("generation_options", {}),
            )
        )
        validate_result_capabilities(result, capabilities, generate_answer=False)


def prepared_model_artifacts(
    prepared: PreparedSystem, experiment: ExperimentSpec
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
) -> CaseResult:
    started = datetime.now(UTC)
    gold_answer = bundle.gold_answers[question.gold_answer_id]
    evidence_set = bundle.gold_evidence_sets[question.gold_evidence_set_id]
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
        latency = dict(rag_result.latency or {})
        latency["end_to_end_query_latency"] = monotonic() - query_started
        rag_result = rag_result.model_copy(update={"latency": latency})
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
        return failed_case(
            question.case_id,
            question.question,
            gold_answer,
            evidence_set,
            started,
            status="cancelled" if cancelled() else "timeout",
            code="cancelled" if cancelled() else "timeout",
            message=str(exc) or "adapter query timed out",
            experiment=experiment,
            repetition=repetition,
            seed=seed,
        )
    except (WorkerRemoteError, httpx.HTTPError) as exc:
        return failed_case(
            question.case_id,
            question.question,
            gold_answer,
            evidence_set,
            started,
            status="cancelled" if cancelled() else "system_error",
            code="cancelled"
            if cancelled()
            else getattr(exc, "code", "adapter_error"),
            message=str(exc),
            experiment=experiment,
            repetition=repetition,
            seed=seed,
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
            process.stop()
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


def order_questions(questions: list[Question], seed: int) -> list[Question]:
    """Generate a stable, persisted per-seed order without changing selection."""

    def order_key(question: Question) -> tuple[str, str]:
        payload = f"{seed}\0{question.case_id}".encode()
        return hashlib.sha256(payload).hexdigest(), question.case_id

    return sorted(questions, key=order_key)


def source_only_documents(
    bundle: DatasetBundle, source_dir: Path
) -> list[DocumentInput]:
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
        inputs.append(
            DocumentInput(
                document_id=document.document_id,
                content=content,
                source_path=sandbox_path.name,
                sha256=document.sha256,
                mime_type=document.mime_type,
                metadata={"original_name": original.name},
            )
        )
    return inputs


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
            scorer_id=ANSWER_SCORER_ID,
            scorer_version=ANSWER_SCORER_VERSION,
            scorer_digest=ANSWER_SCORER_DIGEST,
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
            aggregate[metric_id] = {
                "status": status,
                "value": None,
                "denominator": 0,
                "coverage": 0.0,
                "errors": status_counts[MetricStatus.ERROR.value],
                "status_counts": status_counts,
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
