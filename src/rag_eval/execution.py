"""Standalone run execution through an isolated adapter worker."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread

import httpx

from rag_eval import __version__
from rag_eval.contracts.adapter import DocumentInput, PrepareContext, RAGQuery
from rag_eval.contracts.run import (
    CaseError,
    CaseResult,
    ExperimentSpec,
    MetricResult,
    MetricStatus,
    RunManifest,
    RunStatus,
)
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
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.runs import RunStore
from rag_eval.worker.client import WorkerRemoteError
from rag_eval.worker.process import WorkerCommand, WorkerProcess


class RunExecutor:
    def __init__(
        self,
        dataset_store: DatasetBundleStore,
        run_store: RunStore,
    ) -> None:
        self.dataset_store = dataset_store
        self.run_store = run_store

    def execute(
        self,
        experiment: ExperimentSpec,
        command: WorkerCommand,
        *,
        run_id: str | None = None,
        cancelled: Callable[[], bool] | None = None,
        worker_started: Callable[[str, int], None] | None = None,
    ) -> RunManifest:
        run_id = run_id or uuid.uuid4().hex
        cancelled = cancelled or (lambda: False)
        bundle = self.dataset_store.get(experiment.bundle_id)
        questions = select_questions(bundle, experiment)
        run_dir = self.run_store.root / run_id
        temporary_log = self.run_store.root / f".{run_id}.worker.log"
        process = WorkerProcess(
            command, run_id=run_id, log_path=temporary_log
        )
        manifest: RunManifest | None = None
        watcher_done = Event()
        watcher: Thread | None = None
        try:
            client = process.start()
            assert process.process is not None
            if worker_started:
                worker_started(run_id, process.process.pid)
            watcher = Thread(
                target=watch_cancellation,
                args=(cancelled, watcher_done, process),
                name=f"rag-eval-cancel-{run_id}",
                daemon=True,
            )
            watcher.start()
            handshake = client.handshake()
            started_at = datetime.now(UTC)
            manifest = RunManifest(
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
                },
                effective_config={},
                scorer_id=ANSWER_SCORER_ID,
                scorer_version=ANSWER_SCORER_VERSION,
                scorer_digest=ANSWER_SCORER_DIGEST,
                declared_capabilities=handshake.capabilities,
                observed_capabilities=handshake.capabilities,
                seed=experiment.seed,
                repetitions=experiment.repetitions,
                started_at=started_at,
            )
            self.run_store.create(manifest, experiment)
            source_dir = run_dir / "source"
            documents = source_only_documents(bundle, source_dir)
            prepared = client.prepare(
                PrepareContext(
                    run_id=run_id,
                    work_dir=str(run_dir / "work"),
                    source_dir=str(source_dir),
                    platform_version=__version__,
                ),
                experiment.adapter_config,
            )
            if (
                experiment.query_config.get("generate_answer", True)
                and not prepared.capabilities.answer
            ):
                raise ValueError(
                    "experiment requests answer generation but adapter lacks answer capability"
                )
            manifest = manifest.model_copy(
                update={
                    "status": RunStatus.INGESTING,
                    "system_version": prepared.system_version,
                    "effective_config": {
                        "adapter": prepared.effective_config,
                        "query": experiment.query_config,
                        "metrics": experiment.metric_config,
                    },
                    "observed_capabilities": prepared.capabilities,
                }
            )
            self.run_store.write_manifest(manifest)
            ingestion = client.ingest(documents)
            manifest = manifest.model_copy(
                update={
                    "status": RunStatus.RUNNING,
                    "index_fingerprint": ingestion.index_fingerprint,
                }
            )
            self.run_store.write_manifest(manifest)

            corpus = CorpusEvidenceIndex(bundle.source_documents())
            results: list[CaseResult] = []
            for question in questions:
                if cancelled():
                    manifest = manifest.model_copy(update={"status": RunStatus.CANCELLED})
                    break
                started = datetime.now(UTC)
                gold_answer = bundle.gold_answers[question.gold_answer_id]
                evidence_set = bundle.gold_evidence_sets[
                    question.gold_evidence_set_id
                ]
                query = RAGQuery(
                    case_id=question.case_id,
                    question=question.question,
                    generate_answer=bool(
                        experiment.query_config.get("generate_answer", True)
                    ),
                    retrieval_candidate_k=experiment.query_config.get(
                        "retrieval_candidate_k"
                    ),
                    final_context_k=experiment.query_config.get("final_context_k"),
                    max_context_tokens=experiment.query_config.get(
                        "max_context_tokens"
                    ),
                    generation_options=experiment.query_config.get(
                        "generation_options", {}
                    ),
                )
                try:
                    rag_result = client.query(query)
                    validate_result_capabilities(
                        rag_result,
                        prepared.capabilities,
                        generate_answer=query.generate_answer,
                    )
                    metrics = evaluate_case(
                        rag_result,
                        gold_answer,
                        evidence_set,
                        corpus,
                        k_values=metric_k_values(experiment),
                        evaluate_answer=query.generate_answer,
                    )
                    case = CaseResult(
                        case_id=question.case_id,
                        status="completed",
                        question=question.question,
                        gold_answer=gold_answer,
                        gold_evidence_set=evidence_set,
                        rag_result=rag_result,
                        metrics=metrics,
                        started_at=started,
                        completed_at=datetime.now(UTC),
                    )
                except httpx.TimeoutException as exc:
                    case = failed_case(
                        question.case_id,
                        question.question,
                        gold_answer,
                        evidence_set,
                        started,
                        status="cancelled" if cancelled() else "timeout",
                        code="cancelled" if cancelled() else "timeout",
                        message=str(exc) or "adapter query timed out",
                        experiment=experiment,
                    )
                except (WorkerRemoteError, httpx.HTTPError) as exc:
                    case = failed_case(
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
                    )
                self.run_store.write_case(run_id, case)
                results.append(case)
                if case.status == "cancelled":
                    manifest = manifest.model_copy(update={"status": RunStatus.CANCELLED})
                    break

            if manifest.status != RunStatus.CANCELLED:
                manifest = manifest.model_copy(update={"status": RunStatus.COMPLETED})
            counts = execution_counts(results)
            summary = aggregate_metrics(results)
            atomic_write_json(run_dir / "summary.json", summary)
            manifest = manifest.model_copy(
                update={
                    "completed_at": datetime.now(UTC),
                    "execution_counts": counts,
                    "artifacts": {"summary": "summary.json", "cases": "cases/"},
                }
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
        finally:
            watcher_done.set()
            process.stop()
            if watcher is not None:
                watcher.join(timeout=1)
            if temporary_log.exists() and run_dir.is_dir():
                final_log = run_dir / "worker" / "worker.log"
                temporary_log.replace(final_log)


def watch_cancellation(
    cancelled: Callable[[], bool], done: Event, process: WorkerProcess
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
        started_at=started,
        completed_at=datetime.now(UTC),
    )


def execution_counts(results: list[CaseResult]) -> dict[str, int]:
    counts = {"total": len(results), "completed": 0, "timeout": 0, "system_error": 0, "cancelled": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return counts


def aggregate_metrics(results: list[CaseResult]) -> dict[str, object]:
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
            if metric.status in {MetricStatus.OBSERVED, MetricStatus.ERROR}
        ]
        if not applicable:
            aggregate[metric_id] = {
                "status": "unavailable",
                "value": None,
                "denominator": 0,
            }
            continue
        numerator = sum(
            metric.value or 0.0
            for metric in applicable
            if metric.status == MetricStatus.OBSERVED
        )
        aggregate[metric_id] = {
            "status": "observed",
            "value": numerator / len(applicable),
            "numerator": numerator,
            "denominator": len(applicable),
            "errors": sum(metric.status == MetricStatus.ERROR for metric in applicable),
        }
    return {"metrics": aggregate, "execution": execution_counts(results)}


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
