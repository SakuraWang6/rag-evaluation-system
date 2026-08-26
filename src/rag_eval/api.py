"""Standalone FastAPI surface for the local evaluation platform."""

from __future__ import annotations

import json
import shutil
import zipfile
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict

from rag_eval.comparison import validate_comparison
from rag_eval.contracts.research import ComparisonSpec
from rag_eval.contracts.run import ComparisonTier, ExperimentSpec
from rag_eval.service import PlatformService
from rag_eval.datasets.drafts import DatasetDraft
from rag_eval.execution_provider import ExecutionRequest
from rag_eval.products import EvaluationDraft, SystemConnection, canonical_experiment
from rag_eval.authoring.storage import AuthoringStorageError


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetRegisterRequest(APIModel):
    path: str


class SystemConnectionRequest(APIModel):
    connection: SystemConnection
    secrets: dict[str, str] = {}


class EvaluationFinalizeRequest(APIModel):
    queue: bool = True


class ComparisonRequest(APIModel):
    run_ids: list[str]
    tier: ComparisonTier
    comparison_spec: ComparisonSpec | None = None


def create_app(
    service: PlatformService, *, start_supervisor: bool = True
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if start_supervisor:
            service.supervisor.start()
        try:
            yield
        finally:
            if start_supervisor:
                service.supervisor.stop()

    app = FastAPI(
        title="RAG Evaluation Platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^http://(?:127\.0\.0\.1|localhost):\d+$",
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-RAG-EVAL-Filename"],
    )

    @app.get("/api/v1/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "schema_version": 2,
            "producer": "rag_eval_platform",
            "product_layer_enabled": service.product_enabled,
        }

    def require_authoring():
        if not service.product_enabled or service.authoring is None:
            raise HTTPException(status_code=404, detail="authoring product layer is disabled")
        return service.authoring

    @app.get("/api/v1/authoring/datasets")
    async def list_authoring_datasets() -> list[dict[str, Any]]:
        authoring = require_authoring()
        return [item.model_dump(mode="json") for item in authoring.list()]

    @app.post("/api/v1/authoring/datasets", status_code=201)
    async def upload_authoring_docx(request: Request) -> dict[str, Any]:
        """Upload raw DOCX bytes into private local authoring storage.

        Multipart is intentionally avoided so the product has the same bounded,
        streaming-compatible raw-body contract as Bundle ZIP upload.
        """

        authoring = require_authoring()
        filename = request.headers.get("x-rag-eval-filename", "")
        try:
            dataset = authoring.upload_docx(filename=filename, payload=await request.body())
            return dataset.model_dump(mode="json")
        except (AuthoringStorageError, OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}")
    async def get_authoring_dataset(authoring_dataset_id: str) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            return authoring.get(authoring_dataset_id).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/analyze")
    async def analyze_authoring_dataset(authoring_dataset_id: str) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            return authoring.analyze(authoring_dataset_id).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}/canonical")
    async def get_authoring_canonical_view(authoring_dataset_id: str) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            view = authoring.canonical_view(authoring_dataset_id)
            return {
                "view": view.model_dump(mode="json"),
                "execution_markdown": authoring.canonical_markdown(authoring_dataset_id),
            }
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/v1/authoring/datasets/{authoring_dataset_id}", status_code=204)
    async def delete_authoring_dataset(authoring_dataset_id: str) -> None:
        authoring = require_authoring()
        try:
            authoring.delete(authoring_dataset_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/datasets")
    async def datasets() -> list[dict[str, Any]]:
        return [
            {
                "bundle_id": bundle.bundle_id,
                "name": bundle.manifest.name,
                "version": bundle.manifest.version,
                "cases": len(bundle.questions),
            }
            for bundle in service.datasets.list()
        ]

    @app.post("/api/v1/datasets")
    async def register_dataset(request: DatasetRegisterRequest) -> dict[str, Any]:
        try:
            bundle = service.datasets.register(Path(request.path))
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"bundle_id": bundle.bundle_id}

    @app.get("/api/v1/systems")
    async def systems() -> list[dict[str, Any]]:
        return [
            {
                "system_id": item.system_id,
                "adapter_id": item.adapter_id,
                "adapter_factory": item.adapter_factory,
                "python_executable": item.python_executable,
                "environment_keys": sorted(item.environment),
                "request_timeout_seconds": item.request_timeout_seconds,
                "description": item.description,
            }
            for item in service.systems.list()
        ]

    @app.get("/api/v1/experiments")
    async def experiments() -> list[dict[str, Any]]:
        return [
            item.model_dump(mode="json") for item in service.experiments.list()
        ]

    @app.post("/api/v1/experiments")
    async def create_experiment(experiment: ExperimentSpec) -> dict[str, Any]:
        try:
            service.datasets.get(experiment.bundle_id)
            if not service.system_resolver.exists(experiment.system_id):
                raise FileNotFoundError(experiment.system_id)
            service.experiments.create(experiment)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return experiment.model_dump(mode="json")

    @app.post("/api/v1/experiments/{experiment_id}/runs")
    async def queue_run(experiment_id: str) -> dict[str, Any]:
        try:
            experiment = service.experiments.get(experiment_id)
            job = service.jobs.create(experiment)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        service.supervisor.notify()
        return job.model_dump(mode="json")

    @app.get("/api/v1/jobs")
    async def jobs() -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in service.jobs.list()]

    @app.get("/api/v1/jobs/{job_id}")
    async def job(job_id: str) -> dict[str, Any]:
        try:
            return service.jobs.get(job_id).model_dump(mode="json")
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str) -> dict[str, Any]:
        try:
            record = service.jobs.request_cancel(job_id)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return record.model_dump(mode="json")

    @app.get("/api/v1/runs")
    async def runs() -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in service.runs.list()]

    @app.get("/api/v1/runs/{run_id}")
    async def run(run_id: str) -> dict[str, Any]:
        try:
            return service.runs.get(run_id).model_dump(mode="json")
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/runs/{run_id}/cases")
    async def run_cases(run_id: str) -> list[dict[str, Any]]:
        try:
            return [
                item.model_dump(mode="json") for item in service.runs.cases(run_id)
            ]
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/runs/{run_id}/summary")
    async def run_summary(run_id: str) -> dict[str, Any]:
        try:
            service.runs.get(run_id)
            path = service.paths.runs / run_id / "summary.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise TypeError("run summary is malformed")
            return value
        except (OSError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/runs/{run_id}/artifacts/verify")
    async def verify_run_artifacts(run_id: str) -> dict[str, Any]:
        try:
            return asdict(service.runs.verify_artifacts(run_id))
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/runs/{run_id}/cases/{case_id}")
    async def run_case(run_id: str, case_id: str) -> dict[str, Any]:
        for item in await run_cases(run_id):
            if item["case_id"] == case_id:
                return item
        raise HTTPException(status_code=404, detail="case not found")

    @app.get("/api/v1/runs/{run_id}/report", response_class=PlainTextResponse)
    async def report(run_id: str) -> str:
        try:
            service.runs.get(run_id)
            return (service.paths.runs / run_id / "report.md").read_text(
                encoding="utf-8"
            )
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/comparisons/validate")
    async def compare(request: ComparisonRequest) -> dict[str, Any]:
        try:
            manifests = [service.runs.get(run_id) for run_id in request.run_ids]
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        summaries = {
            manifest.run_id: await run_summary(manifest.run_id)
            for manifest in manifests
        }
        decision = validate_comparison(
            manifests,
            request.tier,
            summaries=summaries,
            spec=request.comparison_spec,
        )
        return {
            "tier": decision.tier,
            "compatible": decision.compatible,
            "reasons": decision.reasons,
            "may_declare_winner": decision.may_declare_winner,
            "metric_decisions": [
                {
                    "metric_id": item.metric_id,
                    "comparable": item.comparable,
                    "reasons": item.reasons,
                    "coverage_by_run": item.coverage_by_run,
                    "winner_eligible": item.winner_eligible,
                }
                for item in decision.metric_decisions
            ],
            "runs": [
                {
                    "run": manifest.model_dump(mode="json"),
                    "summary": summaries[manifest.run_id],
                }
                for manifest in manifests
            ],
        }

    def require_product() -> None:
        if not service.product_enabled or service.products is None or service.dataset_drafts is None:
            raise HTTPException(status_code=404, detail="product layer is disabled")

    @app.get("/api/v1/product/status")
    async def product_status() -> dict[str, Any]:
        return {"enabled": service.product_enabled}

    @app.get("/api/v1/product/profiles")
    async def product_profiles() -> list[dict[str, Any]]:
        require_product()
        assert service.products is not None
        # The Basic surface intentionally has no factory/runtime/default payload.
        # Canonicalization happens server-side and expands the immutable profile.
        return [
            {
                "profile_id": item.profile_id,
                "profile_version": item.profile_version,
                "display_name": item.display_name,
                "system_id": item.system_id,
                "adapter_id": item.adapter_id,
                "default_logical_endpoint": item.default_logical_endpoint,
                "docker_available": item.docker_image is not None,
            }
            for item in service.products.profiles.list()
        ]

    @app.get("/api/v1/product/systems")
    async def product_systems() -> list[dict[str, Any]]:
        require_product()
        assert service.products is not None
        values = []
        for item in service.products.connections.list():
            connection = item
            assert isinstance(connection, SystemConnection)
            values.append(
                {
                    "system_id": connection.system_id,
                    "display_name": connection.display_name,
                    "profile_id": connection.profile_id,
                    "profile_version": connection.profile_version,
                    "execution_provider": connection.execution_provider,
                    "logical_endpoint_ref": connection.logical_endpoint_ref,
                    "secret_keys": sorted(connection.secret_bindings),
                    "configured": True,
                    "connection_test_status": connection.connection_test_status,
                    "last_connection_tested_at": connection.last_connection_tested_at,
                    "updated_at": connection.updated_at,
                }
            )
        return values

    @app.post("/api/v1/product/systems")
    async def save_product_system(request: SystemConnectionRequest) -> dict[str, Any]:
        require_product()
        assert service.products is not None and service.secrets is not None
        connection = request.connection
        profile = service.products.profiles.get(connection.profile_id, connection.profile_version)
        if connection.system_id != profile.system_id:
            raise HTTPException(status_code=400, detail="system_id must match the selected standard profile")
        if "python_executable" not in connection.model_fields_set:
            connection = connection.model_copy(
                update={
                    "python_executable": service.standard_worker_python(
                        connection.profile_id,
                        connection.python_executable,
                    )
                }
            )
        # Basic submissions deliberately omit secret references.  Preserve
        # existing references, then rotate only keys that carry a new value.
        try:
            existing = service.products.get_connection(connection.system_id)
        except FileNotFoundError:
            existing = None
        bindings = dict(existing.secret_bindings) if existing is not None else {}
        bindings.update(connection.secret_bindings)
        replaced_references: list[str] = []
        for environment_key, value in request.secrets.items():
            if not value:
                raise HTTPException(status_code=400, detail=f"secret {environment_key!r} is empty")
            previous = bindings.get(environment_key)
            bindings[environment_key] = service.secrets.set(value)
            if previous is not None and previous != bindings[environment_key]:
                replaced_references.append(previous)
        saved = service.products.save_connection(connection.model_copy(update={"secret_bindings": bindings}))
        for reference in replaced_references:
            service.secrets.delete(reference)
        return {
            "system_id": saved.system_id,
            "display_name": saved.display_name,
            "profile_id": saved.profile_id,
            "profile_version": saved.profile_version,
            "execution_provider": saved.execution_provider,
            "logical_endpoint_ref": saved.logical_endpoint_ref,
            "secret_keys": sorted(saved.secret_bindings),
            "configured": True,
            "connection_test_status": saved.connection_test_status,
            "last_connection_tested_at": saved.last_connection_tested_at,
        }

    @app.delete("/api/v1/product/systems/{system_id}/secrets/{environment_key}")
    async def remove_product_system_secret(system_id: str, environment_key: str) -> dict[str, Any]:
        require_product()
        assert service.products is not None and service.secrets is not None
        try:
            connection = service.products.get_connection(system_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"unknown product system {system_id!r}") from exc
        bindings = dict(connection.secret_bindings)
        try:
            reference = bindings.pop(environment_key)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"secret {environment_key!r} is not configured") from exc
        saved = service.products.save_connection(connection.model_copy(update={"secret_bindings": bindings}))
        service.secrets.delete(reference)
        return {
            "system_id": saved.system_id,
            "secret_keys": sorted(saved.secret_bindings),
            "configured": True,
        }

    @app.post("/api/v1/product/systems/{system_id}/test")
    async def test_product_system(system_id: str) -> dict[str, Any]:
        require_product()
        assert service.products is not None
        connection: SystemConnection | None = None
        try:
            connection = service.products.get_connection(system_id)
            resolved = service.system_resolver.resolve(system_id, provider=connection.execution_provider)
            sandbox = service.paths.product_uploads / f"connection-test-{system_id}"
            shutil.rmtree(sandbox, ignore_errors=True)
            source, work = sandbox / "source", sandbox / "work"
            handle = service.providers.get(resolved.provider).start(
                ExecutionRequest(
                    command=resolved.command,
                    run_id=f"connection-test-{system_id}",
                    log_path=sandbox / "worker.log",
                    source_dir=source,
                    work_dir=work,
                )
            )
            try:
                handshake = handle.client.handshake()
            finally:
                handle.stop()
                shutil.rmtree(sandbox, ignore_errors=True)
            service.products.save_connection(
                connection.model_copy(
                    update={
                        "connection_test_status": "passed",
                        "last_connection_tested_at": datetime.now(UTC),
                    }
                )
            )
            return {
                "status": "ok",
                "system_id": handshake.system_id,
                "adapter_id": handshake.adapter_id,
                "execution_provider": resolved.provider,
            }
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            if connection is not None:
                service.products.save_connection(
                    connection.model_copy(
                        update={
                            "connection_test_status": "failed",
                            "last_connection_tested_at": datetime.now(UTC),
                        }
                    )
                )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/product/datasets/upload")
    async def upload_dataset_bundle(request: Request) -> dict[str, Any]:
        require_product()
        filename = request.headers.get("x-rag-eval-filename", "")
        if filename and not filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="dataset upload must be one .zip file")
        target = service.paths.product_uploads / f"bundle-upload-{uuid4_hex()}"
        archive = target.with_suffix(".zip")
        target.mkdir(parents=True)
        try:
            content = await request.body()
            if not content:
                raise ValueError("uploaded Bundle ZIP is empty")
            if len(content) > 1024 * 1024 * 1024:
                raise ValueError("uploaded Bundle ZIP exceeds the 1 GiB limit")
            archive.write_bytes(content)
            _safe_extract_zip(archive, target)
            root = _bundle_root(target)
            bundle = service.datasets.register(root)
            return {"bundle_id": bundle.bundle_id}
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            shutil.rmtree(target, ignore_errors=True)
            archive.unlink(missing_ok=True)

    @app.post("/api/v1/product/datasets/local-path")
    async def register_local_dataset(request: DatasetRegisterRequest) -> dict[str, Any]:
        require_product()
        try:
            bundle = service.datasets.register(Path(request.path))
            return {"bundle_id": bundle.bundle_id}
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/product/dataset-drafts")
    async def list_dataset_drafts() -> list[dict[str, Any]]:
        require_product()
        assert service.dataset_drafts is not None
        return [item.model_dump(mode="json") for item in service.dataset_drafts.list()]

    @app.post("/api/v1/product/dataset-drafts")
    async def create_dataset_draft(draft: DatasetDraft) -> dict[str, Any]:
        require_product()
        assert service.dataset_drafts is not None
        return service.dataset_drafts.save(draft).model_dump(mode="json")

    @app.put("/api/v1/product/dataset-drafts/{draft_id}")
    async def update_dataset_draft(draft_id: str, draft: DatasetDraft) -> dict[str, Any]:
        require_product()
        if draft_id != draft.draft_id:
            raise HTTPException(status_code=400, detail="draft ID in path and payload must match")
        assert service.dataset_drafts is not None
        return service.dataset_drafts.save(draft).model_dump(mode="json")

    @app.post("/api/v1/product/dataset-drafts/{draft_id}/validate")
    async def validate_dataset_draft(draft_id: str) -> dict[str, Any]:
        require_product()
        assert service.dataset_drafts is not None
        try:
            draft = service.dataset_drafts.get(draft_id)
            service.dataset_drafts.validate(draft)
            return {"valid": True}
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/product/dataset-drafts/{draft_id}/seal")
    async def seal_dataset_draft(draft_id: str) -> dict[str, Any]:
        require_product()
        assert service.dataset_drafts is not None
        try:
            bundle = service.dataset_drafts.seal(service.dataset_drafts.get(draft_id), service.datasets)
            return {"bundle_id": bundle.bundle_id, "sealed": True}
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/product/evaluation-drafts")
    async def evaluation_drafts() -> list[dict[str, Any]]:
        require_product()
        assert service.products is not None
        return [item.model_dump(mode="json") for item in service.products.drafts.list()]

    @app.post("/api/v1/product/evaluation-drafts")
    async def save_evaluation_draft(draft: EvaluationDraft) -> dict[str, Any]:
        require_product()
        assert service.products is not None
        return service.products.save_draft(draft).model_dump(mode="json")

    @app.get("/api/v1/product/evaluation-drafts/{draft_id}/preview")
    async def preview_evaluation_draft(draft_id: str) -> dict[str, Any]:
        require_product()
        try:
            return _canonical_draft(service, draft_id).model_dump(mode="json")
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/product/evaluation-drafts/{draft_id}/finalize")
    async def finalize_evaluation_draft(
        draft_id: str,
        request: EvaluationFinalizeRequest = EvaluationFinalizeRequest(),
    ) -> dict[str, Any]:
        require_product()
        try:
            spec = _canonical_draft(service, draft_id)
            service.experiments.create(spec)
            response: dict[str, Any] = {"experiment": spec.model_dump(mode="json")}
            if request.queue:
                assert service.products is not None
                connection = service.products.get_connection(spec.system_id)
                job = service.jobs.create(spec, execution_provider=connection.execution_provider)
                service.supervisor.notify()
                response["job"] = job.model_dump(mode="json")
            return response
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def _canonical_draft(service: PlatformService, draft_id: str) -> ExperimentSpec:
    if service.products is None:
        raise ValueError("product layer is disabled")
    draft = service.products.get_draft(draft_id)
    if not draft.bundle_id or not draft.system_id or not draft.profile_id or not draft.profile_version:
        raise ValueError("Dataset, System, and profile version are required before creating an evaluation")
    bundle = service.datasets.get(draft.bundle_id)
    connection = service.products.get_connection(draft.system_id)
    profile = service.products.profiles.get(draft.profile_id, draft.profile_version)
    return canonical_experiment(draft, connection, profile, case_ids=[item.case_id for item in bundle.questions])


def _safe_extract_zip(archive: Path, target: Path) -> None:
    expanded = 0
    with zipfile.ZipFile(archive) as value:
        for info in value.infolist():
            member = Path(info.filename)
            is_link = (info.external_attr >> 16) & 0o170000 == 0o120000
            if member.is_absolute() or ".." in member.parts or is_link:
                raise ValueError("Bundle ZIP contains an unsafe path")
            expanded += info.file_size
            if expanded > 4 * 1024 * 1024 * 1024:
                raise ValueError("Bundle ZIP expands beyond the 4 GiB limit")
        value.extractall(target)


def _bundle_root(target: Path) -> Path:
    if (target / "manifest.json").is_file():
        return target
    directories = [path for path in target.iterdir() if path.is_dir()]
    files = [path for path in target.iterdir() if path.is_file()]
    if len(directories) == 1 and not files and (directories[0] / "manifest.json").is_file():
        return directories[0]
    raise ValueError("Bundle ZIP must contain one Bundle root with manifest.json")


def uuid4_hex() -> str:
    from uuid import uuid4
    return uuid4().hex
