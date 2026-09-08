"""Standalone FastAPI surface for the local evaluation platform."""

from __future__ import annotations

import json
import shutil
import zipfile
from asyncio import CancelledError, Task, create_task
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote_to_bytes

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from rag_eval.authoring.models import (
    AnswerEvidenceCandidate,
    AuthoringState,
    DiscoveryJobStatus,
    DiscoveryMethod,
    GenerationJobStatus,
)
from rag_eval.authoring.storage import AuthoringStorageError
from rag_eval.authoring.workflow import AuthoringWorkflowError
from rag_eval.comparison import validate_comparison
from rag_eval.contracts.research import ComparisonSpec
from rag_eval.contracts.run import ComparisonTier, ExperimentSpec
from rag_eval.datasets.drafts import DatasetDraft
from rag_eval.datasets.docx_render import render_docx_html
from rag_eval.datasets.formal import FormalDatasetError
from rag_eval.execution_provider import ExecutionRequest, cleanup_managed_run
from rag_eval.jobs import TERMINAL_JOB_STATUSES
from rag_eval.products import EvaluationDraft, SystemConnection, canonical_experiment
from rag_eval.service import PlatformService
from rag_eval.storage.runs import safe_id
from rag_eval.llm import (
    LLMProviderConfig,
    LLMProviderKind,
    LLMStage,
    LLMStageBinding,
    provider_api_view,
    revision_api_view,
)
from rag_eval.reviews import (
    AnswerSupportVerdict,
    CaseReviewSource,
    CaseReviewVerdict,
    SemanticReviewError,
)
from rag_eval.runs.views import (
    RunArtifactCaseCollectionView,
    RunArtifactCaseIndexView,
    RunArtifactCaseView,
    RunArtifactOverviewView,
)


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetRegisterRequest(APIModel):
    path: str


class SystemConnectionRequest(APIModel):
    connection: SystemConnection
    secrets: dict[str, str] = {}


class LLMProviderRequest(APIModel):
    provider_id: str
    display_name: str
    kind: LLMProviderKind
    endpoint: str
    model: str = ""
    embedding_model: str | None = None
    enabled: bool = True


class LLMStageBindingRequest(APIModel):
    stage: LLMStage
    provider_id: str
    model: str | None = None
    enabled: bool = True
    fallback_provider_id: str | None = None


class LLMConfigurationRequest(APIModel):
    providers: list[LLMProviderRequest]
    bindings: list[LLMStageBindingRequest]
    actor: str = "local-user"
    reason: str = "updated model configuration"
    # Keys are provider IDs. Values are accepted only on the write path and
    # are immediately moved to the local SecretStore; never echo them back.
    secrets: dict[str, str] = {}


class EvaluationFinalizeRequest(APIModel):
    queue: bool = True


class ComparisonRequest(APIModel):
    run_ids: list[str]
    tier: ComparisonTier
    comparison_spec: ComparisonSpec | None = None


class AuthoringDiscoveryRequest(APIModel):
    provider: DiscoveryMethod = DiscoveryMethod.OLLAMA
    seed: int = 0
    remote_consent: bool = False


class AuthoringQuestionRequest(APIModel):
    target_id: str
    question: str
    language: str = "zh-CN"


class AuthoringTargetRequest(APIModel):
    capability: str
    source_object_ids: list[str]
    retrieval_route: list[str]
    distractor_object_ids: list[str] = []
    rationale: str = "manual reviewer target"


class AuthoringQuestionGenerationRequest(APIModel):
    target_id: str
    provider: DiscoveryMethod = DiscoveryMethod.OLLAMA
    seed: int = 0
    remote_consent: bool = False


class AuthoringBatchGenerationRequest(APIModel):
    target_ids: list[str]
    provider: DiscoveryMethod = DiscoveryMethod.OLLAMA
    seed: int = 0
    remote_consent: bool = False


class AuthoringGenerationRetryRequest(APIModel):
    target_ids: list[str] | None = None


class AuthoringResolutionRequest(APIModel):
    resolution: AnswerEvidenceCandidate


class AuthoringResolutionGenerationRequest(APIModel):
    provider: DiscoveryMethod = DiscoveryMethod.OLLAMA
    seed: int = 0
    remote_consent: bool = False


class AuthoringReviewRequest(APIModel):
    decision: str
    reviewer: str
    note: str = ""
    edited_question: str | None = None
    edited_resolution: AnswerEvidenceCandidate | None = None


class AuthoringExportRequest(APIModel):
    name: str
    version: str
    approved_case_ids: list[str] | None = None


class AuthoringFormalReleaseRequest(APIModel):
    display_name: str | None = None
    release_version: str
    actor: str


class AuthoringRepresentabilityProfileRequest(APIModel):
    profile_id: str
    system_id: str
    adapter_id: str
    execution_profile_digest: str
    runtime_map: dict[str, Any]


class CaseReviewRequest(APIModel):
    verdict: CaseReviewVerdict
    reviewer: str = "local-reviewer"
    note: str = ""


class AnswerSupportReviewRequest(APIModel):
    verdict: AnswerSupportVerdict
    reviewer: str = "local-reviewer"
    note: str = ""


class SemanticCaseReviewRequest(APIModel):
    remote_consent: bool = False


class RunPresentationRequest(APIModel):
    display_name: str
    actor: str = "local-user"
    note: str = ""


def _upload_filename(request: Request) -> str:
    """Read an ASCII-safe UTF-8 filename header while accepting legacy ASCII."""

    value = request.headers.get("x-rag-eval-filename", "")
    if not value.startswith("utf-8''"):
        return value
    try:
        return unquote_to_bytes(value.removeprefix("utf-8''")).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="uploaded filename is not valid UTF-8") from exc


def create_app(
    service: PlatformService, *, start_supervisor: bool = True
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        resume_task: Task[None] | None = None
        if start_supervisor:
            service.supervisor.start()
            if service.semantic_review_coordinator is not None:
                # Only resumes persisted queued/running review batches; it
                # never scans old completed Runs and never rewrites them.
                service.semantic_review_coordinator.resume_pending()
            if service.semantic_support_review_coordinator is not None:
                service.semantic_support_review_coordinator.resume_pending()
        if service.product_enabled and service.authoring is not None:
            async def resume_authoring_background_jobs() -> None:
                for dataset in service.authoring.list():
                    for job in service.authoring.workflow.list_generation_jobs(dataset):
                        if job.state not in {
                            GenerationJobStatus.QUEUED,
                            GenerationJobStatus.RUNNING,
                        }:
                            continue
                        await run_in_threadpool(
                            lambda job_id=job.job_id, item=dataset: service.authoring.workflow.run_generation_job(
                                item, job_id=job_id
                            )
                        )
                    for job in service.authoring.workflow.list_discovery_jobs(dataset):
                        if job.state not in {
                            DiscoveryJobStatus.QUEUED,
                            DiscoveryJobStatus.RUNNING,
                        }:
                            continue
                        await run_in_threadpool(
                            lambda job_id=job.job_id, item=dataset: service.authoring.workflow.run_discovery_job(
                                item, job_id=job_id
                            )
                        )

            resume_task = create_task(resume_authoring_background_jobs())
        try:
            yield
        finally:
            if resume_task is not None and not resume_task.done():
                resume_task.cancel()
                with suppress(CancelledError):
                    await resume_task
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
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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

    def formal_release_display_name(item: Any) -> str:
        if item.display_name:
            return item.display_name
        # Older releases did not store a product-facing name.  Their retained
        # Word file is the best local label; when that workspace has gone, the
        # semantic release version is still more useful than an opaque ID.
        try:
            assert service.formal_datasets is not None
            source_name = service.formal_datasets.source_filename(item.release_id)
            return Path(source_name).stem or source_name
        except (AssertionError, FileNotFoundError, OSError, ValueError):
            return item.release_version

    def bundle_display_name(bundle: Any) -> str:
        """Use a formal release's product name for its legacy Bundle 2.0 view."""

        if service.formal_datasets is None:
            return bundle.manifest.name
        projection = bundle.manifest.metadata.get("formal_runtime_projection")
        release_id = projection.get("release_id") if isinstance(projection, dict) else None
        if not isinstance(release_id, str):
            return bundle.manifest.name
        try:
            return formal_release_display_name(service.formal_datasets.releases.get(release_id))
        except (FileNotFoundError, OSError, ValueError):
            return bundle.manifest.name

    def require_authoring():
        if not service.product_enabled or service.authoring is None:
            raise HTTPException(status_code=404, detail="authoring product layer is disabled")
        return service.authoring

    @app.get("/api/v1/authoring/datasets")
    async def list_authoring_datasets() -> list[dict[str, Any]]:
        authoring = require_authoring()
        datasets = authoring.list()
        # Compatibility migration for workspaces published before the direct
        # formal-release flow closed their state.  The source workspace stays
        # private provenance, never a draft the product UI should resume.
        if service.formal_datasets is not None:
            release_ids_by_dataset: dict[str, list[str]] = {}
            for release in service.formal_datasets.releases.list(include_removed=True):
                release_ids_by_dataset.setdefault(release.dataset_id, []).append(release.release_id)
            normalized = []
            for item in datasets:
                release_ids = release_ids_by_dataset.get(item.authoring_dataset_id, [])
                if release_ids and item.state is not AuthoringState.FORMAL_RELEASED:
                    item = authoring.workflow.mark_formal_released(
                        item, release_id=release_ids[-1]
                    )
                    # Retain all linked releases where a prior API user has
                    # intentionally created immutable successors.
                    if set(item.formal_release_ids) != set(release_ids):
                        item = authoring.store.save(
                            item.model_copy(
                                update={
                                    "formal_release_ids": list(
                                        dict.fromkeys([*item.formal_release_ids, *release_ids])
                                    )
                                }
                            )
                        )
                normalized.append(item)
            datasets = normalized
        return [item.model_dump(mode="json") for item in datasets]

    @app.post("/api/v1/authoring/datasets", status_code=201)
    async def upload_authoring_docx(request: Request) -> dict[str, Any]:
        """Upload raw DOCX bytes into private local authoring storage.

        Multipart is intentionally avoided so the product has the same bounded,
        streaming-compatible raw-body contract as Bundle ZIP upload.
        """

        authoring = require_authoring()
        filename = _upload_filename(request)
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

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}/document")
    async def get_authoring_document_view(authoring_dataset_id: str) -> dict[str, Any]:
        """Read the source-faithful authoring document with Canonical IDs for highlighting."""

        authoring = require_authoring()
        try:
            return await run_in_threadpool(
                lambda: authoring.document_view(authoring_dataset_id).model_dump(mode="json")
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}/source")
    async def download_authoring_source(authoring_dataset_id: str) -> FileResponse:
        authoring = require_authoring()
        try:
            dataset = authoring.get(authoring_dataset_id)
            return FileResponse(
                authoring.store.source_path(authoring_dataset_id),
                media_type=dataset.source.mime_type,
                filename=dataset.source.original_filename,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}/document/native", response_class=HTMLResponse)
    async def render_authoring_document_native(authoring_dataset_id: str) -> HTMLResponse:
        """Render the uploaded DOCX with its native OOXML structure preserved."""

        authoring = require_authoring()
        try:
            dataset = authoring.get(authoring_dataset_id)
            content = await run_in_threadpool(
                lambda: render_docx_html(
                    authoring.store.source_path(authoring_dataset_id),
                    dataset.source.original_filename,
                )
            )
            return HTMLResponse(content=content)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            raise HTTPException(status_code=422, detail=f"DOCX native rendering failed: {exc}") from exc

    @app.delete("/api/v1/authoring/datasets/{authoring_dataset_id}", status_code=204)
    async def delete_authoring_dataset(authoring_dataset_id: str) -> None:
        """Permanently remove one archived local authoring workspace only."""

        authoring = require_authoring()
        try:
            authoring.delete(authoring_dataset_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/archive")
    async def archive_authoring_dataset(authoring_dataset_id: str) -> dict[str, Any]:
        """Soft-archive an editable authoring workspace without losing history."""

        authoring = require_authoring()
        try:
            return authoring.archive(authoring_dataset_id).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}/targets")
    async def list_authoring_targets(authoring_dataset_id: str) -> list[dict[str, Any]]:
        authoring = require_authoring()
        try:
            return [item.model_dump(mode="json") for item in authoring.workflow.list_targets(authoring.get(authoring_dataset_id))]
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}/targets/{target_id}/preview")
    async def get_authoring_target_preview(authoring_dataset_id: str, target_id: str) -> dict[str, Any]:
        """Read-only source projection used by the authoring review screen."""

        authoring = require_authoring()
        try:
            return authoring.workflow.target_preview(authoring.get(authoring_dataset_id), target_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/targets/discover")
    async def discover_authoring_targets(authoring_dataset_id: str, request: AuthoringDiscoveryRequest) -> list[dict[str, Any]]:
        authoring = require_authoring()
        try:
            dataset = authoring.get(authoring_dataset_id)
            targets = await run_in_threadpool(
                authoring.workflow.discover_targets,
                dataset,
                provider=request.provider,
                seed=request.seed,
                remote_consent=request.remote_consent,
            )
            return [item.model_dump(mode="json") for item in targets]
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}/discovery-jobs")
    async def list_authoring_discovery_jobs(authoring_dataset_id: str) -> list[dict[str, Any]]:
        """Read durable target-discovery progress after a page refresh/reopen."""

        authoring = require_authoring()
        try:
            dataset = authoring.get(authoring_dataset_id)
            return [
                item.model_dump(mode="json")
                for item in authoring.workflow.list_discovery_jobs(dataset)
            ]
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/discovery-jobs", status_code=202)
    async def create_authoring_discovery_job(
        authoring_dataset_id: str,
        request: AuthoringDiscoveryRequest,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        """Queue long-running target discovery without holding the HTTP request."""

        authoring = require_authoring()
        try:
            dataset = authoring.get(authoring_dataset_id)
            job = authoring.workflow.create_discovery_job(
                dataset,
                provider=request.provider,
                seed=request.seed,
                remote_consent=request.remote_consent,
            )
            background_tasks.add_task(
                authoring.workflow.run_discovery_job,
                dataset,
                job_id=job.job_id,
            )
            return job.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/authoring/datasets/{authoring_dataset_id}/discovery-jobs/{job_id}/retry",
        status_code=202,
    )
    async def retry_authoring_discovery_job(
        authoring_dataset_id: str,
        job_id: str,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            dataset = authoring.get(authoring_dataset_id)
            job = authoring.workflow.retry_discovery_job(dataset, job_id=job_id)
            background_tasks.add_task(
                authoring.workflow.run_discovery_job,
                dataset,
                job_id=job.job_id,
            )
            return job.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail="authoring dataset or target discovery job not found"
            ) from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/targets", status_code=201)
    async def create_authoring_target(
        authoring_dataset_id: str, request: AuthoringTargetRequest
    ) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            dataset = authoring.get(authoring_dataset_id)
            target = authoring.workflow.create_target(
                dataset,
                capability=request.capability,
                source_object_ids=request.source_object_ids,
                retrieval_route=request.retrieval_route,
                distractor_object_ids=request.distractor_object_ids,
                rationale=request.rationale,
            )
            return target.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}/candidates")
    async def list_authoring_candidates(authoring_dataset_id: str) -> list[dict[str, Any]]:
        authoring = require_authoring()
        try:
            return [item.model_dump(mode="json") for item in authoring.workflow.list_candidates(authoring.get(authoring_dataset_id))]
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}/representability-profiles")
    async def list_authoring_representability_profiles(authoring_dataset_id: str) -> list[dict[str, Any]]:
        authoring = require_authoring()
        try:
            dataset = authoring.get(authoring_dataset_id)
            return [
                item.model_dump(mode="json")
                for item in authoring.workflow.list_representability_profiles(dataset)
            ]
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/representability-profiles", status_code=201)
    async def register_authoring_representability_profile(
        authoring_dataset_id: str,
        request: AuthoringRepresentabilityProfileRequest,
    ) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            dataset = authoring.get(authoring_dataset_id)
            profile = authoring.workflow.register_representability_profile(
                dataset,
                profile_id=request.profile_id,
                system_id=request.system_id,
                adapter_id=request.adapter_id,
                execution_profile_digest=request.execution_profile_digest,
                runtime_map=request.runtime_map,
            )
            return profile.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/candidates", status_code=201)
    async def create_authoring_question(authoring_dataset_id: str, request: AuthoringQuestionRequest) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            candidate = authoring.workflow.create_question(authoring.get(authoring_dataset_id), target_id=request.target_id, question=request.question, language=request.language)
            return candidate.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/candidates/generate", status_code=201)
    async def generate_authoring_question(authoring_dataset_id: str, request: AuthoringQuestionGenerationRequest) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            candidate = authoring.workflow.generate_question(authoring.get(authoring_dataset_id), target_id=request.target_id, provider=request.provider, seed=request.seed, remote_consent=request.remote_consent)
            return candidate.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/candidates/generate-proposal", status_code=201)
    async def generate_authoring_question_and_answer(
        authoring_dataset_id: str,
        request: AuthoringQuestionGenerationRequest,
    ) -> dict[str, Any]:
        """Generate one reviewable question + answer + source evidence proposal."""

        authoring = require_authoring()
        try:
            candidate = authoring.workflow.generate_question_and_answer(
                authoring.get(authoring_dataset_id),
                target_id=request.target_id,
                provider=request.provider,
                seed=request.seed,
                remote_consent=request.remote_consent,
            )
            return candidate.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}/generation-jobs")
    async def list_authoring_generation_jobs(authoring_dataset_id: str) -> list[dict[str, Any]]:
        """List persisted batch-generation jobs for reopening the authoring flow."""

        authoring = require_authoring()
        try:
            dataset = authoring.get(authoring_dataset_id)
            return [
                item.model_dump(mode="json")
                for item in authoring.workflow.list_generation_jobs(dataset)
            ]
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/generation-jobs", status_code=202)
    async def create_authoring_generation_job(
        authoring_dataset_id: str,
        request: AuthoringBatchGenerationRequest,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        """Queue a durable batch proposal job and return before model work runs."""

        authoring = require_authoring()
        try:
            dataset = authoring.get(authoring_dataset_id)
            job = authoring.workflow.create_generation_job(
                dataset,
                target_ids=request.target_ids,
                provider=request.provider,
                seed=request.seed,
                remote_consent=request.remote_consent,
            )
            background_tasks.add_task(
                authoring.workflow.run_generation_job,
                dataset,
                job_id=job.job_id,
            )
            return job.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/generation-jobs/{job_id}/cancel")
    async def cancel_authoring_generation_job(
        authoring_dataset_id: str, job_id: str
    ) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            job = authoring.workflow.cancel_generation_job(
                authoring.get(authoring_dataset_id), job_id=job_id
            )
            return job.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset or generation job not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/generation-jobs/{job_id}/retry", status_code=202)
    async def retry_authoring_generation_job(
        authoring_dataset_id: str,
        job_id: str,
        request: AuthoringGenerationRetryRequest,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            dataset = authoring.get(authoring_dataset_id)
            job = authoring.workflow.retry_generation_job(
                dataset, job_id=job_id, target_ids=request.target_ids
            )
            background_tasks.add_task(
                authoring.workflow.run_generation_job,
                dataset,
                job_id=job.job_id,
            )
            return job.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset or generation job not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}/candidates/{candidate_id}")
    async def get_authoring_candidate(authoring_dataset_id: str, candidate_id: str) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            return authoring.workflow.get_candidate(authoring.get(authoring_dataset_id), candidate_id).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset or candidate not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/candidates/{candidate_id}/resolve")
    async def resolve_authoring_answer_evidence(authoring_dataset_id: str, candidate_id: str, request: AuthoringResolutionRequest) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            candidate = authoring.workflow.resolve_answer_evidence(authoring.get(authoring_dataset_id), candidate_id=candidate_id, resolution=request.resolution)
            return candidate.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset or candidate not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/candidates/{candidate_id}/resolve/generate")
    async def generate_authoring_answer_evidence(authoring_dataset_id: str, candidate_id: str, request: AuthoringResolutionGenerationRequest) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            candidate = authoring.workflow.generate_answer_evidence(authoring.get(authoring_dataset_id), candidate_id=candidate_id, provider=request.provider, seed=request.seed, remote_consent=request.remote_consent)
            return candidate.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset or candidate not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/candidates/{candidate_id}/review")
    async def review_authoring_candidate(authoring_dataset_id: str, candidate_id: str, request: AuthoringReviewRequest) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            candidate = authoring.workflow.review(authoring.get(authoring_dataset_id), candidate_id=candidate_id, decision=request.decision, reviewer=request.reviewer, note=request.note, edited_question=request.edited_question, edited_resolution=request.edited_resolution)
            return candidate.model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset or candidate not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}/reviews")
    async def list_authoring_reviews(authoring_dataset_id: str) -> list[dict[str, Any]]:
        authoring = require_authoring()
        try:
            return [item.model_dump(mode="json") for item in authoring.workflow.list_reviews(authoring.get(authoring_dataset_id))]
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc

    @app.get("/api/v1/authoring/datasets/{authoring_dataset_id}/approved")
    async def list_authoring_approved(authoring_dataset_id: str) -> list[dict[str, Any]]:
        authoring = require_authoring()
        try:
            return [item.model_dump(mode="json") for item in authoring.workflow.list_approved(authoring.get(authoring_dataset_id))]
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/exports", status_code=201)
    async def export_authoring_dataset(authoring_dataset_id: str, request: AuthoringExportRequest) -> dict[str, Any]:
        authoring = require_authoring()
        try:
            return authoring.workflow.export(authoring.get(authoring_dataset_id), name=request.name, version=request.version, approved_case_ids=request.approved_case_ids).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/exports/{release_id}/register/{view}")
    async def register_authoring_export(authoring_dataset_id: str, release_id: str, view: str) -> dict[str, Any]:
        """The sole composition-layer crossing from mutable Authoring to Evaluation."""

        authoring = require_authoring()
        try:
            dataset = authoring.get(authoring_dataset_id)
            export = authoring.workflow.get_export(dataset, release_id)
            relative = export.views.get(view)
            if not relative:
                raise AuthoringWorkflowError("unknown execution view")
            bundle = service.datasets.register(authoring.store.workspace(authoring_dataset_id) / relative)
            updated = authoring.workflow.mark_registered(dataset, release_id=release_id, view=view, bundle_id=bundle.bundle_id)
            return {"bundle_id": bundle.bundle_id, "export": updated.model_dump(mode="json")}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset or export not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/authoring/datasets/{authoring_dataset_id}/formal-releases", status_code=201)
    async def publish_authoring_formal_release(
        authoring_dataset_id: str,
        request: AuthoringFormalReleaseRequest,
    ) -> dict[str, Any]:
        """Freeze all currently approved Cases as one immutable Dataset Release."""

        authoring = require_authoring()
        if service.formal_datasets is None:
            raise HTTPException(status_code=404, detail="formal Data Layer is disabled")
        try:
            dataset = authoring.get(authoring_dataset_id)
            approved = authoring.workflow.list_approved(dataset)
            if not approved:
                raise AuthoringWorkflowError("at least one approved question is required before publication")
            predecessors = [
                item
                for item in service.formal_datasets.releases.list(include_removed=True)
                if item.dataset_id == authoring_dataset_id
            ]
            parent_release_id = (
                max(predecessors, key=lambda item: item.created_at).release_id
                if predecessors
                else None
            )
            release = service.formal_datasets.freeze(
                authoring_dataset_id,
                display_name=request.display_name,
                release_version=request.release_version,
                case_ids=tuple(item.case_id for item in approved),
                actor=request.actor,
                parent_release_id=parent_release_id,
            )
            authoring.workflow.mark_formal_released(dataset, release_id=release.release_id)
            return {
                "release_id": release.release_id,
                "dataset_id": release.dataset_id,
                "name": release.display_name,
                "version": release.release_version,
                "case_count": len(release.cases),
                "gold_count": len(release.gold),
            }
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="authoring dataset not found") from exc
        except (ValueError, AuthoringWorkflowError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/datasets")
    async def datasets() -> list[dict[str, Any]]:
        return [
            {
                "bundle_id": bundle.bundle_id,
                "name": bundle_display_name(bundle),
                "version": bundle.manifest.version,
                "cases": len(bundle.questions),
            }
            for bundle in service.datasets.list()
        ]

    @app.get("/api/v1/product/formal-datasets")
    async def formal_datasets() -> dict[str, Any]:
        """Expose immutable formal releases and their standard-runtime status."""
        if service.formal_datasets is None:
            return {"releases": [], "bundles_v3": []}
        releases = [
            {
                "release_id": item.release_id,
                "dataset_id": item.dataset_id,
                "name": formal_release_display_name(item),
                "version": item.release_version,
                "release_digest": item.release_digest,
                "parent_release_id": item.parent_release_id,
                "case_count": len(item.cases),
                "gold_count": len(item.gold),
                "canonical_digest": item.document.canonical_digest,
                "validation_report_digest": item.validation_report_digest,
                # The execution projection is generated only at preview/finalise
                # time from immutable release pins, never from a workspace.
                # It preserves formal MSES alternatives when the legacy Bundle
                # 2.0 view would be lossy.
                "runnable": bool(item.bundle_projection.projections),
                "runtime_reason": None
                if item.bundle_projection.projections
                else "no runtime projection assessment",
            }
            for item in service.formal_datasets.releases.list()
        ]
        bundles: list[dict[str, Any]] = []
        if service.bundles_v3 is not None:
            for bundle_id, manifest in service.bundles_v3.list_manifest_records():
                bundles.append(
                    {
                        "bundle_id": bundle_id,
                        "target_release_id": manifest.target_release_id,
                        "dataset_id": manifest.dataset_id,
                        "case_count": manifest.case_count,
                        "gold_count": manifest.gold_count,
                        "evidence_count": manifest.evidence_count,
                        "runnable": False,
                        "visibility": "bundle_v3_private_and_runtime_exports",
                    }
                )
        return {"releases": sorted(releases, key=lambda value: value["release_id"]), "bundles_v3": sorted(bundles, key=lambda value: value["bundle_id"])}

    @app.get("/api/v1/product/formal-datasets/{release_id}/content")
    async def formal_dataset_content(release_id: str) -> dict[str, Any]:
        """Return the compatibility all-Case inspection view for local UI.

        New product views use the index and single-Case endpoints below.  This
        endpoint remains for callers that need the all-Case payload, now served
        from the persisted read model instead of parsing Canonical snapshots.
        """

        if service.formal_datasets is None:
            raise HTTPException(status_code=404, detail="formal Data Layer is disabled")
        try:
            return await run_in_threadpool(
                lambda: service.formal_datasets.content(release_id).model_dump(mode="json")
            )
        except FormalDatasetError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"formal Dataset Release content unavailable: {exc}",
            ) from exc
        except (FileNotFoundError, OSError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=f"formal Dataset Release not found: {release_id}") from exc

    @app.get("/api/v1/product/formal-datasets/{release_id}/benchmark-contract")
    async def formal_dataset_benchmark_contract(release_id: str) -> dict[str, Any]:
        """Read the verified immutable rag-benchmark-contract/1 package."""

        if service.formal_datasets is None:
            raise HTTPException(status_code=404, detail="formal Data Layer is disabled")
        try:
            dataset = await run_in_threadpool(
                lambda: service.formal_datasets.get_benchmark_contract(release_id)
            )
            return {
                "manifest": dataset.manifest.model_dump(mode="json"),
                "segment_count": len(dataset.segments),
                "case_count": len(dataset.questions),
                "artifact_path": str(dataset.root),
            }
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail=f"benchmark contract not published for formal Dataset Release: {release_id}",
            ) from exc
        except (FormalDatasetError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/product/formal-datasets/{release_id}/benchmark-contract", status_code=201)
    async def publish_formal_dataset_benchmark_contract(release_id: str) -> dict[str, Any]:
        """Publish the Release-adjacent immutable segment-native benchmark package."""

        if service.formal_datasets is None:
            raise HTTPException(status_code=404, detail="formal Data Layer is disabled")
        try:
            dataset = await run_in_threadpool(
                lambda: service.formal_datasets.publish_benchmark_contract(
                    release_id, service.datasets
                )
            )
            return {
                "schema_version": dataset.manifest.schema_version,
                "dataset_id": dataset.manifest.dataset_id,
                "name": dataset.manifest.name,
                "version": dataset.manifest.version,
                "contract_digest": dataset.manifest.contract_digest,
                "segment_count": len(dataset.segments),
                "case_count": len(dataset.questions),
            }
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"formal Dataset Release not found: {release_id}") from exc
        except (FormalDatasetError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/product/formal-datasets/{release_id}/cases")
    async def formal_dataset_case_index(release_id: str) -> dict[str, Any]:
        """Return the fast published Case directory for one formal Dataset."""

        if service.formal_datasets is None:
            raise HTTPException(status_code=404, detail="formal Data Layer is disabled")
        try:
            return await run_in_threadpool(
                lambda: service.formal_datasets.case_index(release_id)
            )
        except FormalDatasetError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"formal Dataset Release Case index unavailable: {exc}",
            ) from exc
        except (FileNotFoundError, OSError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=f"formal Dataset Release not found: {release_id}") from exc

    @app.get("/api/v1/product/formal-datasets/{release_id}/cases/{case_id}")
    async def formal_dataset_case(release_id: str, case_id: str) -> dict[str, Any]:
        """Return one Case detail without loading sibling Cases or Canonical data."""

        if service.formal_datasets is None:
            raise HTTPException(status_code=404, detail="formal Data Layer is disabled")
        try:
            return await run_in_threadpool(
                lambda: service.formal_datasets.case_content(release_id, case_id)
            )
        except FormalDatasetError as exc:
            message = str(exc)
            status_code = 404 if "Case not found" in message else 422
            raise HTTPException(status_code=status_code, detail=message) from exc
        except (FileNotFoundError, OSError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=f"formal Dataset Release not found: {release_id}") from exc

    @app.delete("/api/v1/product/formal-datasets/{release_id}")
    async def remove_formal_dataset_from_catalog(release_id: str) -> dict[str, Any]:
        """Remove one frozen version from the current product dataset list.

        Immutable release artifacts remain available to historical runs; this
        operation does not mutate a release, Gold, Canonical snapshot, or
        Bundle.
        """

        if service.formal_datasets is None:
            raise HTTPException(status_code=404, detail="formal Data Layer is disabled")
        try:
            release = service.formal_datasets.remove_from_catalog(
                release_id,
                actor="local-product-user",
            )
            return {"release_id": release.release_id, "deleted": True}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"formal Dataset Release not found: {release_id}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/product/formal-datasets/{release_id}/document")
    async def formal_dataset_document(release_id: str) -> dict[str, Any]:
        """Return a compact source-faithful reading view for evidence highlighting."""

        if service.formal_datasets is None:
            raise HTTPException(status_code=404, detail="formal Data Layer is disabled")
        try:
            return await run_in_threadpool(
                lambda: service.formal_datasets.document_view(release_id).model_dump(mode="json")
            )
        except (FileNotFoundError, OSError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=f"formal Dataset Release not found: {release_id}") from exc

    @app.get("/api/v1/product/formal-datasets/{release_id}/source")
    async def download_formal_source(release_id: str) -> FileResponse:
        """Download the immutable source snapshot pinned by a formal release."""

        if service.formal_datasets is None:
            raise HTTPException(status_code=404, detail="formal Data Layer is disabled")
        try:
            source = service.formal_datasets.releases.source_snapshot(release_id)
            filename = service.formal_datasets.source_filename(release_id)
            return FileResponse(
                source,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename=filename,
            )
        except (FileNotFoundError, OSError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=f"formal Dataset Release not found: {release_id}") from exc

    @app.get("/api/v1/product/formal-datasets/{release_id}/document/native", response_class=HTMLResponse)
    async def render_formal_document_native(release_id: str) -> HTMLResponse:
        """Render the immutable release source with its native DOCX structure."""

        if service.formal_datasets is None:
            raise HTTPException(status_code=404, detail="formal Data Layer is disabled")
        try:
            source = service.formal_datasets.releases.source_snapshot(release_id)
            filename = service.formal_datasets.source_filename(release_id)
            content = await run_in_threadpool(lambda: render_docx_html(source, filename))
            return HTMLResponse(content=content)
        except (FileNotFoundError, OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            raise HTTPException(status_code=404, detail=f"formal Dataset Release not found: {release_id}") from exc

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
        return await run_in_threadpool(service.run_history.list_views)

    @app.get("/api/v1/runs/{run_id}")
    async def run(run_id: str) -> dict[str, Any]:
        try:
            return await run_in_threadpool(lambda: service.run_history.run_view(run_id))
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/v1/runs/{run_id}/presentation")
    async def update_run_presentation(
        run_id: str, payload: RunPresentationRequest
    ) -> dict[str, Any]:
        """Append a UI name revision without changing an immutable Run."""

        if service.run_presentations is None:
            raise HTTPException(status_code=404, detail="run presentation is unavailable in this Platform mode")
        try:
            await run_in_threadpool(lambda: service.run_history.get(run_id))
            record = await run_in_threadpool(
                lambda: service.run_presentations.append(
                    run_id=run_id,
                    display_name=payload.display_name,
                    actor=payload.actor,
                    note=payload.note,
                )
            )
            return {
                "run": await run_in_threadpool(lambda: service.run_history.run_view(run_id)),
                "presentation": record.api_view(),
            }
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/runs/{run_id}/liveness")
    async def run_liveness(run_id: str) -> dict[str, Any]:
        """Expose privacy-safe adapter stage/progress records for active runs."""

        try:
            run_dir = service.paths.runs / safe_id(run_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not run_dir.is_dir():
            raise HTTPException(status_code=404, detail="run does not exist")
        repetitions: list[dict[str, Any]] = []
        for path in sorted((run_dir / "work").glob("rep-*/ingestion-liveness.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, TypeError, ValueError):
                continue
            if isinstance(payload, dict):
                repetitions.append(
                    {
                        "repetition": path.parent.name,
                        **payload,
                    }
                )
        return {
            "run_id": run_id,
            "status": repetitions[0].get("stage") if repetitions else "pending",
            "repetitions": repetitions,
        }

    @app.get("/api/v1/runs/{run_id}/cases")
    async def run_cases(run_id: str) -> RunArtifactCaseCollectionView:
        try:
            return await run_in_threadpool(
                service.run_history.artifact_cases, run_id
            )
        except (OSError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/runs/{run_id}/cases/index")
    async def run_case_index(run_id: str) -> RunArtifactCaseIndexView:
        try:
            return await run_in_threadpool(
                service.run_history.artifact_case_index, run_id
            )
        except (OSError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/runs/{run_id}/summary")
    async def run_summary(run_id: str) -> RunArtifactOverviewView:
        try:
            return await run_in_threadpool(
                service.run_history.artifact_overview, run_id
            )
        except (OSError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/runs/{run_id}/artifacts/verify")
    async def verify_run_artifacts(run_id: str) -> dict[str, Any]:
        try:
            presentation = await run_in_threadpool(
                service.run_history.artifact_presentation, run_id
            )
            if presentation.has_artifact_v2:
                verification = await run_in_threadpool(
                    lambda: presentation.overview().verification
                )
                assert verification is not None
                return verification.model_dump(mode="json")
            return await run_in_threadpool(
                lambda: asdict(service.run_history.verify_artifacts(run_id))
            )
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/runs/{run_id}/cases/{case_id}/review")
    async def review_run_case(
        run_id: str,
        case_id: str,
        payload: CaseReviewRequest,
        repetition: int = 1,
    ) -> dict[str, Any]:
        """Append a human decision without touching immutable Case artifacts."""

        if service.case_reviews is None:
            raise HTTPException(status_code=404, detail="case review is unavailable in this Platform mode")
        try:
            await run_in_threadpool(
                lambda: service.run_history.case(run_id, case_id, repetition=repetition)
            )
            record = await run_in_threadpool(
                lambda: service.case_reviews.append(
                    run_id=run_id,
                    case_id=case_id,
                    repetition=repetition,
                    verdict=payload.verdict,
                    source=CaseReviewSource.HUMAN,
                    reviewer=payload.reviewer,
                    note=payload.note,
                )
            )
            return record.api_view()
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="case not found") from exc

    @app.post("/api/v1/runs/{run_id}/cases/{case_id}/semantic-review")
    async def semantic_review_run_case(
        run_id: str,
        case_id: str,
        payload: SemanticCaseReviewRequest,
        repetition: int = 1,
    ) -> dict[str, Any]:
        """Run the configured second-pass LLM and append its auditable proposal."""

        if service.semantic_reviewer is None:
            raise HTTPException(status_code=404, detail="semantic review is unavailable in this Platform mode")
        try:
            case = await run_in_threadpool(
                lambda: service.run_history.case(run_id, case_id, repetition=repetition)
            )
            record = await run_in_threadpool(
                lambda: service.semantic_reviewer.review(
                    run_id,
                    case,
                    remote_consent=payload.remote_consent,
                )
            )
            return record.api_view()
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="case not found") from exc
        except SemanticReviewError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/runs/{run_id}/cases/{case_id}/answer-support-review")
    async def review_run_case_answer_support(
        run_id: str,
        case_id: str,
        payload: AnswerSupportReviewRequest,
        repetition: int = 1,
    ) -> dict[str, Any]:
        """Append a human grounding/hallucination decision separately."""

        if service.answer_support_reviews is None:
            raise HTTPException(
                status_code=404,
                detail="answer support review is unavailable in this Platform mode",
            )
        try:
            await run_in_threadpool(
                lambda: service.run_history.case(run_id, case_id, repetition=repetition)
            )
            record = await run_in_threadpool(
                lambda: service.answer_support_reviews.append(
                    run_id=run_id,
                    case_id=case_id,
                    repetition=repetition,
                    verdict=payload.verdict,
                    source=CaseReviewSource.HUMAN,
                    reviewer=payload.reviewer,
                    note=payload.note,
                )
            )
            return record.api_view()
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="case not found") from exc

    @app.post("/api/v1/runs/{run_id}/cases/{case_id}/semantic-answer-support-review")
    async def semantic_review_run_case_answer_support(
        run_id: str,
        case_id: str,
        payload: SemanticCaseReviewRequest,
        repetition: int = 1,
    ) -> dict[str, Any]:
        """Run a no-Gold support proposal against final retrieved context."""

        if service.semantic_support_reviewer is None:
            raise HTTPException(
                status_code=404,
                detail="answer support review is unavailable in this Platform mode",
            )
        try:
            case = await run_in_threadpool(
                lambda: service.run_history.case(run_id, case_id, repetition=repetition)
            )
            record = await run_in_threadpool(
                lambda: service.semantic_support_reviewer.review(
                    run_id,
                    case,
                    remote_consent=payload.remote_consent,
                )
            )
            return record.api_view()
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="case not found") from exc
        except SemanticReviewError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/runs/{run_id}/cases/{case_id}")
    async def run_case(
        run_id: str, case_id: str, repetition: int = 1
    ) -> RunArtifactCaseView:
        try:
            return await run_in_threadpool(
                lambda: service.run_history.artifact_case(
                    run_id, case_id, repetition=repetition
                )
            )
        except (OSError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="case not found") from exc

    @app.get("/api/v1/runs/{run_id}/report", response_class=PlainTextResponse)
    async def report(run_id: str) -> str:
        try:
            return service.run_history.report(run_id)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/comparisons/validate")
    async def compare(request: ComparisonRequest) -> dict[str, Any]:
        try:
            manifests = [service.run_history.get(run_id) for run_id in request.run_ids]
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        summaries = {
            manifest.run_id: service.run_history.artifact_comparison_summary(
                manifest.run_id
            )
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
                    # Presentation metadata is an append-only product overlay;
                    # preserve the raw manifest for comparison validation but
                    # return the readable label to the UI.
                    "run": service.run_history.run_view(manifest.run_id),
                    "summary": service.run_history.artifact_overview(
                        manifest.run_id
                    ).model_dump(mode="json"),
                }
                for manifest in manifests
            ],
        }

    def require_product() -> None:
        if not service.product_enabled or service.products is None or service.dataset_drafts is None:
            raise HTTPException(status_code=404, detail="product layer is disabled")

    def require_llm():
        require_product()
        if service.llm is None or service.secrets is None:
            raise HTTPException(status_code=404, detail="LLM configuration is disabled")
        return service.llm

    @app.get("/api/v1/product/status")
    async def product_status() -> dict[str, Any]:
        return {"enabled": service.product_enabled}

    @app.get("/api/v1/product/llm/config")
    async def llm_configuration() -> dict[str, Any]:
        """Return the current sanitized provider/stage configuration."""

        configuration = require_llm().current()
        return revision_api_view(configuration)

    @app.get("/api/v1/product/llm/config/revisions")
    async def llm_configuration_revisions() -> list[dict[str, Any]]:
        """Return immutable configuration revision metadata for audit views."""

        configuration = require_llm()
        return [revision_api_view(item) for item in configuration.revisions()]

    @app.put("/api/v1/product/llm/config")
    async def save_llm_configuration(request: LLMConfigurationRequest) -> dict[str, Any]:
        configuration = require_llm()
        assert service.secrets is not None
        try:
            existing = configuration.current()
            existing_by_id = {item.provider_id: item for item in existing.providers}
            provider_ids = {item.provider_id for item in request.providers}
            unknown_secrets = sorted(set(request.secrets).difference(provider_ids))
            if unknown_secrets:
                raise ValueError(f"secret supplied for unknown provider(s): {', '.join(unknown_secrets)}")
            providers: list[LLMProviderConfig] = []
            for item in request.providers:
                previous = existing_by_id.get(item.provider_id)
                api_key_ref = previous.api_key_ref if previous is not None else None
                if item.provider_id in request.secrets:
                    value = request.secrets[item.provider_id]
                    if not value:
                        raise ValueError(f"secret for provider {item.provider_id!r} is empty")
                    replacement = service.secrets.set(value)
                    if api_key_ref and api_key_ref != replacement:
                        service.secrets.delete(api_key_ref)
                    api_key_ref = replacement
                if item.kind == LLMProviderKind.OPENAI_COMPATIBLE and not api_key_ref:
                    raise ValueError(f"external provider {item.display_name!r} requires an API key")
                providers.append(
                    LLMProviderConfig(
                        provider_id=item.provider_id,
                        display_name=item.display_name,
                        kind=item.kind,
                        endpoint=item.endpoint,
                        model=item.model,
                        embedding_model=item.embedding_model,
                        enabled=item.enabled,
                        api_key_ref=api_key_ref,
                    )
                )
            bindings = [LLMStageBinding(**item.model_dump()) for item in request.bindings]
            saved = configuration.save(providers, bindings, actor=request.actor, reason=request.reason)
            for provider_id, previous in existing_by_id.items():
                if provider_id not in provider_ids and previous.api_key_ref:
                    service.secrets.delete(previous.api_key_ref)
            return revision_api_view(saved)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/product/llm/providers/{provider_id}/health")
    async def check_llm_provider(provider_id: str) -> dict[str, Any]:
        configuration = require_llm()
        assert service.secrets is not None
        try:
            provider = await run_in_threadpool(
                lambda: configuration.check_provider(provider_id, secret_store=service.secrets)
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"unknown LLM provider {provider_id!r}") from exc
        return provider_api_view(provider)

    @app.post("/api/v1/product/llm/providers/{provider_id}/speed")
    async def measure_llm_provider_latency(provider_id: str) -> dict[str, Any]:
        """Measure provider response latency without refreshing its model list."""

        configuration = require_llm()
        assert service.secrets is not None
        try:
            provider = await run_in_threadpool(
                lambda: configuration.check_latency(provider_id, secret_store=service.secrets)
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"unknown LLM provider {provider_id!r}") from exc
        return provider_api_view(provider)

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
                "query_modes": item.query_modes,
                "query_timeout_min_seconds": item.query_timeout_min_seconds,
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

    @app.delete("/api/v1/product/systems/{system_id}")
    async def delete_product_system(system_id: str) -> dict[str, Any]:
        """Delete one editable product system configuration.

        Local and Docker are execution providers for the same product system
        identity; they are never separate records.  Deleting the connection
        therefore removes the one active provider selection, while immutable
        runs, datasets, releases, and bundles remain untouched.  Refuse the
        operation while a queued/running job still depends on this system so
        a live evaluation cannot lose its resolver input.
        """

        require_product()
        assert service.products is not None and service.secrets is not None
        active_jobs = [
            job
            for job in service.jobs.list()
            if job.experiment.system_id == system_id and job.status not in TERMINAL_JOB_STATUSES
        ]
        if active_jobs:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"system {system_id!r} is used by active job(s): "
                    + ", ".join(job.job_id for job in active_jobs)
                ),
            )
        try:
            removed = service.products.delete_connection(system_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"unknown product system {system_id!r}") from exc
        # Remove only the exact, label-verified legacy connection-test worker.
        # A current run-scoped worker is independently named and is not
        # affected by deleting editable configuration.
        if removed.execution_provider == "docker":
            cleanup_managed_run(f"connection-test-{system_id}")
        for reference in sorted(set(removed.secret_bindings.values())):
            service.secrets.delete(reference)
        return {
            "system_id": removed.system_id,
            "deleted": True,
            "previous_execution_provider": removed.execution_provider,
            "secret_keys": sorted(removed.secret_bindings),
        }

    @app.post("/api/v1/product/systems/{system_id}/test")
    async def test_product_system(system_id: str) -> dict[str, Any]:
        require_product()
        assert service.products is not None
        connection: SystemConnection | None = None
        sandbox: Path | None = None
        try:
            connection = service.products.get_connection(system_id)
            resolved = service.system_resolver.resolve(system_id, provider=connection.execution_provider)
            if resolved.provider == "docker":
                # Clean up the deterministic name used by older Platform
                # builds, but only when Docker labels prove that it is the
                # abandoned connection-test worker owned by this app.
                cleanup_managed_run(f"connection-test-{system_id}")
            # A connection test is a real, short-lived Worker launch.  Give
            # every attempt a unique run ID so a failed Docker handshake can
            # never collide with the previous attempt's container name.
            test_run_id = f"connection-test-{safe_id(system_id)}-{uuid4_hex()}"
            sandbox = service.paths.product_uploads / test_run_id
            source, work = sandbox / "source", sandbox / "work"
            handle = service.providers.get(resolved.provider).start(
                ExecutionRequest(
                    command=resolved.command,
                    run_id=test_run_id,
                    log_path=sandbox / "worker.log",
                    source_dir=source,
                    work_dir=work,
                )
            )
            try:
                handshake = handle.client.handshake()
            finally:
                handle.stop()
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
        finally:
            if sandbox is not None:
                shutil.rmtree(sandbox, ignore_errors=True)

    @app.post("/api/v1/product/datasets/upload")
    async def upload_dataset_bundle(request: Request) -> dict[str, Any]:
        require_product()
        filename = _upload_filename(request)
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

    @app.post("/api/v1/product/dataset-drafts")
    async def create_dataset_draft(draft: DatasetDraft) -> dict[str, Any]:
        require_product()
        assert service.dataset_drafts is not None
        return service.dataset_drafts.save(draft).model_dump(mode="json")

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
    if (
        not (draft.bundle_id or draft.dataset_release_id)
        or not draft.system_id
        or not draft.profile_id
        or not draft.profile_version
    ):
        raise ValueError("Dataset, System, and profile version are required before creating an evaluation")
    if draft.dataset_release_id:
        if service.formal_datasets is None:
            raise ValueError("formal Dataset Releases are unavailable in this Platform mode")
        bundle = service.formal_datasets.materialize_runtime_bundle(
            draft.dataset_release_id, service.datasets
        )
        # A formal Dataset Release is evaluated only through its immutable
        # canonical-segment corpus.  Keeping this explicit in the frozen
        # ExperimentSpec (rather than relying solely on the Bundle metadata)
        # makes the LightRAG chunk -> segment acceptance contract visible and
        # reproducible for every newly created evaluation.
        draft = draft.model_copy(
            update={
                "adapter_overrides": {
                    **draft.adapter_overrides,
                    "evaluation_corpus": "canonical_segments",
                }
            }
        )
    else:
        assert draft.bundle_id is not None
        bundle = service.datasets.get(draft.bundle_id)
    connection = service.products.get_connection(draft.system_id)
    profile = service.products.profiles.get(draft.profile_id, draft.profile_version)
    return canonical_experiment(
        draft,
        connection,
        profile,
        case_ids=[item.case_id for item in bundle.questions],
        bundle_id=bundle.bundle_id,
    )


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
