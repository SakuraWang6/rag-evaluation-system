"""Standalone FastAPI surface for the local evaluation platform."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict

from rag_eval.comparison import validate_comparison
from rag_eval.contracts.run import ComparisonTier, ExperimentSpec
from rag_eval.service import PlatformService


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetRegisterRequest(APIModel):
    path: str


class ComparisonRequest(APIModel):
    run_ids: list[str]
    tier: ComparisonTier


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
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/v1/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "schema_version": 2, "producer": "rag_eval_platform"}

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
            service.systems.get(experiment.system_id)
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
                raise ValueError("run summary is malformed")
            return value
        except (OSError, ValueError) as exc:
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
        decision = validate_comparison(manifests, request.tier)
        return {
            "tier": decision.tier,
            "compatible": decision.compatible,
            "reasons": decision.reasons,
            "may_declare_winner": decision.may_declare_winner,
            "runs": [
                {
                    "run": manifest.model_dump(mode="json"),
                    "summary": await run_summary(manifest.run_id),
                }
                for manifest in manifests
            ],
        }

    return app
