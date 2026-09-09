from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_eval.adapters.native_observation import unavailable_native_result
from rag_eval.contracts.native import (
    IngestionReceiptV2,
    NativeQueryV2,
    OriginalDocumentV2,
    PreparedSystemV2,
    ResolvedAdapterConfigV2,
)
from rag_eval.contracts.observation import (
    AdapterCapabilitiesV2,
    ObservationProfileIdentity,
    ObservationStatus,
    RuntimeProfileIdentity,
    SourceIdentity,
)
from rag_eval.contracts.wire import WorkerHealthV2, WorkerIdentityV2
from rag_eval.execution import RunExecutor
from rag_eval.execution_provider import ExecutionRequest
from rag_eval.runs import ArtifactV2Reader, ArtifactWriter
from rag_eval.runs.plans import (
    BenchmarkReleaseIdentityV2,
    NativeMetricConfigV2,
    NativeQueryConfigV2,
    OriginalDocumentIdentityV2,
    ResolvedResourceLimitsV2,
    ResolvedRunPlanReferenceV2,
    ResolvedRunPlanStore,
    ResolvedRunPlanV2,
    ResolvedSystemIdentityV2,
    formal_metric_descriptors,
)
from rag_eval.runs.records import (
    RUN_RECORD_V2_FILENAME,
    RunRecordStateV2,
    RunRecordStoreV2,
    RunRecordV2,
)
from tests.rag_eval_platform.test_resolved_run_plan_v2 import _native_experiment
from tests.rag_eval_platform.test_run_artifact_v2 import (
    _benchmark_identity,
    _evaluated_case,
)
from tests.rag_eval_platform.test_unified_evaluation_v2 import SHA_A, SHA_C, _profile

PLAN_DIGEST = "sha256:" + "a" * 64
PLAN_REFERENCE = ResolvedRunPlanReferenceV2(
    path="resolved-run-plans/experiment-1.json",
    digest=PLAN_DIGEST,
)


def _record_plan_store(
    tmp_path: Path,
) -> tuple[ResolvedRunPlanStore, ResolvedRunPlanReferenceV2]:
    profile = _profile(1)
    plan = ResolvedRunPlanV2(
        experiment_id="experiment-1",
        experiment_digest="sha256:" + "d" * 64,
        benchmark_release=BenchmarkReleaseIdentityV2(
            release_id="dataset-release-1",
            release_digest=SHA_C,
            validation_report_digest=SHA_A,
            runtime_bundle_id=SHA_A,
        ),
        original_document=OriginalDocumentIdentityV2(
            document_id="doc-1",
            source_sha256=SHA_A,
            runtime_path="documents/source.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        system=ResolvedSystemIdentityV2(
            system_id="system-under-test",
            adapter_id="adapter-under-test",
            adapter_factory="fixture.worker:create",
            worker_profile_kind="registered_system",
            worker_profile_id="fixture-profile",
            worker_profile_version="1",
            worker_profile_digest="sha256:" + "e" * 64,
            system_config_digest="sha256:" + "f" * 64,
            execution_provider="fixture",
            worker_request_timeout_seconds=30,
        ),
        adapter_config_digest="sha256:" + "1" * 64,
        query_config=NativeQueryConfigV2(
            generate_answer=True,
            retrieval_candidate_k=1,
            final_context_k=1,
            max_context_tokens=4096,
            generation_options={},
        ),
        metric_config=NativeMetricConfigV2(k_values=(1, 3, 5)),
        evaluation_profile=profile,
        metric_descriptors=formal_metric_descriptors(profile),
        case_ids=("case-1",),
        case_selection_id="selection-1",
        seed=7,
        repetitions=1,
        resource_limits=ResolvedResourceLimitsV2(
            worker_request_timeout_seconds=30,
            max_context_tokens=4096,
        ),
    )
    store = ResolvedRunPlanStore(tmp_path / "resolved-run-plans")
    return store, store.create(plan)


class _NativeClient:
    def __init__(self, *, adapter_id: str, system_id: str) -> None:
        self.capabilities = AdapterCapabilitiesV2(
            answer=True,
        )
        self.adapter_id = adapter_id
        self.system_id = system_id
        self.query_count = 0
        self.prepared: PreparedSystemV2 | None = None

    def health(self) -> WorkerHealthV2:
        return WorkerHealthV2(
            identity=WorkerIdentityV2(
                adapter_id=self.adapter_id,
                adapter_version="phase4-fixture",
                system_id=self.system_id,
                system_version="phase4-fixture",
            ),
            status="ready",
            ready=True,
        )

    def prepare(
        self,
        original: OriginalDocumentV2,
        resolved: ResolvedAdapterConfigV2,
        *,
        timeout: float | None = None,
    ) -> PreparedSystemV2:
        assert timeout is not None
        source = SourceIdentity(
            document_id=original.document_id,
            source_sha256=original.source_sha256,
            media_type=original.media_type,
            source_coordinate_schema="ooxml-structural-v1",
            canonical_catalog_sha256=original.canonical_catalog_sha256,
        )
        runtime = RuntimeProfileIdentity(
            profile_id="phase4-fixture",
            system_id=self.system_id,
            system_version="phase4-fixture",
            configuration_digest="a" * 64,
        )
        observation = ObservationProfileIdentity.build(
            profile_id="phase4-fixture",
            adapter_id=self.adapter_id,
            adapter_version="phase4-fixture",
            capabilities=self.capabilities,
        )
        receipt = IngestionReceiptV2.build(
            document_id=original.document_id,
            source_sha256=original.source_sha256,
            index_fingerprint="phase4-index",
        )
        self.prepared = PreparedSystemV2.build(
            effective_config=dict(resolved.adapter_config),
            source_identity=source,
            runtime_profile=runtime,
            observation_profile=observation,
            ingestion_receipt=receipt,
        )
        return self.prepared

    def query(
        self,
        prepared: PreparedSystemV2,
        query: NativeQueryV2,
    ):
        assert self.prepared == prepared
        self.query_count += 1
        return unavailable_native_result(
            prepared=prepared,
            query=query,
            status=ObservationStatus.UNOBSERVED,
            reason="phase4 fixture does not expose retrieval",
            answer="No verified evidence was observed.",
            telemetry={"native_query_executions": 1},
        )


class _NativeHandle:
    def __init__(self, client: _NativeClient) -> None:
        self.client = client
        self.worker_pid = None
        self.handle_id = None
        self.launch_metadata = {"provider": "phase3-fixture"}

    def resolve_adapter_config(
        self, config: ResolvedAdapterConfigV2
    ) -> ResolvedAdapterConfigV2:
        return config

    def stop(self) -> None:
        return None

    def cancel(self) -> bool:
        return True


class _NativeProvider:
    name = "phase3-fixture"

    def __init__(self, client: _NativeClient) -> None:
        self.client = client

    def start(self, _request: ExecutionRequest) -> _NativeHandle:
        return _NativeHandle(self.client)

    def terminate(self, _handle_id: str) -> bool:
        return True


def _native_executor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    service, experiment, bundle = _native_experiment(tmp_path)
    reference = service.admit_new_public_experiment(experiment, bundle)
    plan = service.resolved_run_plans.get(reference)
    resolved = service.system_resolver.resolve(
        experiment.system_id,
        provider=plan.system.execution_provider,
    )
    client = _NativeClient(
        adapter_id=experiment.adapter_id,
        system_id=experiment.system_id,
    )
    executor = RunExecutor(
        service.datasets,
        service.runs,
        provider=_NativeProvider(client),
        dataset_release_store=service.formal_datasets.releases,
        run_record_store=service.run_records,
    )
    monkeypatch.setattr(
        "rag_eval.execution.validate_native_provenance_contract",
        lambda *_args, **_kwargs: None,
    )
    return service, executor, experiment, plan, reference, resolved.command, client


def _pending_payload() -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "run_id": "run-1",
        "experiment_id": "experiment-1",
        "resolved_plan_path": PLAN_REFERENCE.path,
        "resolved_plan_digest": PLAN_REFERENCE.digest,
        "state": "pending",
        "created_at": datetime(2026, 9, 9, tzinfo=UTC),
        "started_at": None,
        "completed_at": None,
        "execution_error": None,
        "artifact_path": None,
        "artifact_digest": None,
    }


@pytest.mark.native_v2_characterization
def test_run_record_v2_is_only_orchestration_metadata() -> None:
    record = RunRecordV2.model_validate(_pending_payload())

    assert set(record.model_dump()) == {
        "schema_version",
        "run_id",
        "experiment_id",
        "resolved_plan_path",
        "resolved_plan_digest",
        "state",
        "created_at",
        "started_at",
        "completed_at",
        "execution_error",
        "artifact_path",
        "artifact_digest",
    }
    for forbidden in (
        "gold",
        "trace",
        "metrics",
        "score",
        "failure",
        "provenance",
        "case_summary",
        "leaderboard_eligibility",
    ):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            RunRecordV2.model_validate({**_pending_payload(), forbidden: {}})


@pytest.mark.native_v2_characterization
def test_run_record_state_cannot_claim_an_artifact_outside_completed() -> None:
    now = datetime(2026, 9, 9, tzinfo=UTC)
    artifact_fields = {
        "artifact_path": "artifact-v2/artifact.json",
        "artifact_digest": "sha256:" + "b" * 64,
    }

    with pytest.raises(ValidationError, match="COMPLETED requires"):
        RunRecordV2.model_validate(
            {
                **_pending_payload(),
                "state": "completed",
                "started_at": now,
                "completed_at": now,
            }
        )
    with pytest.raises(ValidationError, match="only COMPLETED"):
        RunRecordV2.model_validate({**_pending_payload(), **artifact_fields})
    with pytest.raises(ValidationError, match="FAILED requires"):
        RunRecordV2.model_validate(
            {
                **_pending_payload(),
                "state": "failed",
                "started_at": now,
                "completed_at": now,
            }
        )


@pytest.mark.native_v2_characterization
def test_run_record_completes_only_after_verified_artifact_publication(
    tmp_path: Path,
) -> None:
    plans, reference = _record_plan_store(tmp_path)
    records = RunRecordStoreV2(tmp_path / "runs", plans)
    created = datetime(2026, 9, 9, tzinfo=UTC)
    records.create(
        run_id="run-1",
        experiment_id="experiment-1",
        resolved_plan=reference,
        created_at=created,
    )
    running = records.mark_running("run-1", started_at=created)
    assert running.state == RunRecordStateV2.RUNNING

    resolved, case = _evaluated_case()
    manifest = ArtifactWriter(tmp_path / "runs" / "run-1").publish(
        run_id="run-1",
        experiment_id="experiment-1",
        benchmark_identity=_benchmark_identity(resolved),
        cases=(case,),
        started_at=created,
        completed_at=created + timedelta(seconds=1),
    )
    completed = records.mark_completed("run-1")

    assert completed.state == RunRecordStateV2.COMPLETED
    assert completed.artifact_path == "artifact-v2/artifact.json"
    assert completed.artifact_digest == manifest.artifact_digest
    assert (
        tmp_path / "runs" / "run-1" / RUN_RECORD_V2_FILENAME
    ).is_file()

    second = records.create(
        run_id="run-2",
        experiment_id="experiment-1",
        resolved_plan=reference,
        created_at=created,
    )
    records.mark_running(second.run_id, started_at=created)
    with pytest.raises(ValueError, match="verification"):
        records.mark_completed(second.run_id)
    assert records.get(second.run_id).state == RunRecordStateV2.RUNNING


@pytest.mark.native_v2_characterization
def test_tampered_artifact_cannot_complete_a_run_record(tmp_path: Path) -> None:
    plans, reference = _record_plan_store(tmp_path)
    records = RunRecordStoreV2(tmp_path / "runs", plans)
    created = datetime(2026, 9, 9, tzinfo=UTC)
    records.create(
        run_id="run-1",
        experiment_id="experiment-1",
        resolved_plan=reference,
        created_at=created,
    )
    records.mark_running("run-1", started_at=created)
    resolved, case = _evaluated_case()
    ArtifactWriter(tmp_path / "runs" / "run-1").publish(
        run_id="run-1",
        experiment_id="experiment-1",
        benchmark_identity=_benchmark_identity(resolved),
        cases=(case,),
        started_at=created,
        completed_at=created + timedelta(seconds=1),
    )
    case_path = (
        tmp_path
        / "runs"
        / "run-1"
        / "artifact-v2"
        / "cases"
        / "rep-0001-case-1.json"
    )
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    payload["question"] = "tampered"
    case_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="verification"):
        records.mark_completed("run-1")
    assert records.get("run-1").state == RunRecordStateV2.RUNNING


@pytest.mark.native_v2_characterization
def test_self_valid_artifact_for_another_plan_cannot_complete_the_run(
    tmp_path: Path,
) -> None:
    plans, reference = _record_plan_store(tmp_path)
    records = RunRecordStoreV2(tmp_path / "runs", plans)
    started = datetime(2026, 9, 9, tzinfo=UTC)
    records.create(
        run_id="run-1",
        experiment_id="experiment-1",
        resolved_plan=reference,
        created_at=started,
    )
    records.mark_running("run-1", started_at=started)
    resolved, wrong_descriptor_case = _evaluated_case(context_budget=8192)
    ArtifactWriter(tmp_path / "runs" / "run-1").publish(
        run_id="run-1",
        experiment_id="experiment-1",
        benchmark_identity=_benchmark_identity(resolved),
        cases=(wrong_descriptor_case,),
        started_at=started,
        completed_at=started + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="ResolvedRunPlanV2"):
        records.mark_completed("run-1")
    assert records.get("run-1").state == RunRecordStateV2.RUNNING


def test_run_record_rejects_a_plan_for_another_experiment(tmp_path: Path) -> None:
    plans, reference = _record_plan_store(tmp_path)
    records = RunRecordStoreV2(tmp_path / "runs", plans)

    with pytest.raises(ValueError, match="another Experiment"):
        records.create(
            run_id="run-1",
            experiment_id="different-experiment",
            resolved_plan=reference,
        )


def test_run_record_refuses_to_overlay_a_legacy_run_directory(tmp_path: Path) -> None:
    plans, reference = _record_plan_store(tmp_path)
    run_directory = tmp_path / "runs" / "run-1"
    run_directory.mkdir(parents=True)
    (run_directory / "run.json").write_text("{}", encoding="utf-8")
    records = RunRecordStoreV2(tmp_path / "runs", plans)

    with pytest.raises(FileExistsError, match="another format"):
        records.create(
            run_id="run-1",
            experiment_id="experiment-1",
            resolved_plan=reference,
        )

    assert not (run_directory / RUN_RECORD_V2_FILENAME).exists()


@pytest.mark.native_v2_characterization
def test_native_executor_completes_only_after_publishing_verified_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        service,
        executor,
        experiment,
        plan,
        reference,
        command,
        client,
    ) = _native_executor(tmp_path, monkeypatch)

    executor.execute(
        experiment,
        command,
        run_id="native-authority",
        resolved_plan=plan,
        resolved_plan_reference=reference,
    )

    record = service.run_records.get("native-authority")
    reader = ArtifactV2Reader(
        service.paths.runs / "native-authority" / "artifact-v2"
    )
    assert record.state == RunRecordStateV2.COMPLETED
    assert reader.verify().valid
    assert record.artifact_digest == reader.manifest().artifact_digest
    assert client.query_count == 1


@pytest.mark.native_v2_characterization
def test_artifact_publication_failure_marks_native_run_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, executor, experiment, plan, reference, command, _client = (
        _native_executor(tmp_path, monkeypatch)
    )

    def fail_publish(*_args, **_kwargs):
        raise RuntimeError("simulated Artifact publication failure")

    monkeypatch.setattr("rag_eval.execution.ArtifactWriter.publish", fail_publish)
    with pytest.raises(RuntimeError, match="publication failure"):
        executor.execute(
            experiment,
            command,
            run_id="failed-publication",
            resolved_plan=plan,
            resolved_plan_reference=reference,
        )

    record = service.run_records.get("failed-publication")
    assert record.state == RunRecordStateV2.FAILED
    assert record.artifact_path is None
    assert record.artifact_digest is None
