"""Deterministic native-DOCX Adapter used by the Worker 2.0 contract kit."""

from __future__ import annotations

import asyncio
import hashlib
import re
import zipfile
from pathlib import Path
from time import monotonic
from xml.etree import ElementTree

from rag_eval.contracts.canonical import canonical_json
from rag_eval.contracts.native import (
    IngestionReceiptV2,
    NativeHealthReportV2,
    NativeQueryV2,
    OriginalDocumentV2,
    PreparedSystemV2,
    ResolvedAdapterConfigV2,
)
from rag_eval.contracts.observation import (
    AdapterCapabilitiesV2,
    AdapterRunResultV2,
    ContentObservation,
    IngestionCatalogObservation,
    ObservationCompleteness,
    ObservationProfileIdentity,
    ObservationStatus,
    ObservedStageItem,
    RuntimeChunkRecord,
    RuntimeProfileIdentity,
    SourceIdentity,
    StageName,
    StageObservation,
    StageTransitionDeclaration,
    StageTransitionMode,
    UnifiedTrace,
)
from rag_eval.contracts.wire import WorkerIdentityV2
from rag_eval.worker.app import WorkerDefinition

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ADAPTER_VERSION = "0.2.0"
SYSTEM_VERSION = "fake-rag-2"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _config_digest(value: object) -> str:
    return _sha256(canonical_json(value).encode("utf-8"))


def _capabilities() -> AdapterCapabilitiesV2:
    return AdapterCapabilitiesV2(
        ingestion_catalog=True,
        candidate_retrieval=True,
        ranked_retrieval=True,
        final_context=True,
        prompt_trace=False,
        answer=True,
        provenance=False,
        latency_breakdown=True,
        token_usage=True,
        transitions=(
            StageTransitionDeclaration(
                source_stage=StageName.CANDIDATE,
                target_stage=StageName.RANKED,
                mode=StageTransitionMode.IDENTITY_SUBSET,
            ),
            StageTransitionDeclaration(
                source_stage=StageName.RANKED,
                target_stage=StageName.CONTEXT,
                mode=StageTransitionMode.IDENTITY_SUBSET,
            ),
        ),
    )


class FakeAdapter:
    """Small honest RAG implementation with no access to evaluation Gold."""

    def __init__(self, *, capabilities: AdapterCapabilitiesV2 | None = None) -> None:
        self.capabilities = capabilities or _capabilities()
        self._prepared: PreparedSystemV2 | None = None
        self._chunk: RuntimeChunkRecord | None = None
        self._config: dict[str, object] = {}
        self._closed = False

    async def prepare(
        self,
        original_docx: OriginalDocumentV2,
        resolved_config: ResolvedAdapterConfigV2,
    ) -> PreparedSystemV2:
        if self._closed:
            raise RuntimeError("adapter is closed")
        if self._prepared is not None:
            raise RuntimeError("adapter is already prepared")
        source_path = (Path(resolved_config.source_dir) / original_docx.source_path).resolve()
        content = _docx_text(source_path)
        self._config = {
            "final_context_k": int(
                resolved_config.adapter_config.get("final_context_k", 3)
            ),
            "delay_seconds": float(
                resolved_config.adapter_config.get("delay_seconds", 0)
            ),
            "cache_policy": {"answer": False, "query": False, "llm": False},
        }
        model_artifacts = resolved_config.adapter_config.get("model_artifacts")
        if isinstance(model_artifacts, dict) and model_artifacts:
            self._config["model_artifacts"] = model_artifacts
        content_sha256 = _sha256(content.encode("utf-8"))
        chunk_id = f"fake-chunk:{content_sha256}"
        self._chunk = RuntimeChunkRecord(
            native_document_id=original_docx.document_id,
            native_chunk_id=chunk_id,
            content_sha256=content_sha256,
            content=content,
            parser_identity="fake-docx-parser/2.0",
            chunker_identity="fake-whole-document-chunker/2.0",
            persisted_metadata_digest=_config_digest(
                {"document_id": original_docx.document_id, "chunk_id": chunk_id}
            ),
        )
        source_identity = SourceIdentity(
            document_id=original_docx.document_id,
            source_sha256=original_docx.source_sha256,
            media_type=original_docx.media_type,
            source_coordinate_schema="ooxml-structural-v1",
            canonical_catalog_sha256=original_docx.canonical_catalog_sha256,
        )
        runtime_profile = RuntimeProfileIdentity(
            profile_id="fake:native-docx",
            system_id="fake-rag",
            system_version=SYSTEM_VERSION,
            configuration_digest=_config_digest(self._config),
        )
        observation_profile = ObservationProfileIdentity.build(
            profile_id="fake-native-docx-observation/2.0",
            adapter_id="fake",
            adapter_version=ADAPTER_VERSION,
            capabilities=self.capabilities,
        )
        index_fingerprint = _config_digest(
            {
                "source_sha256": original_docx.source_sha256,
                "content_sha256": content_sha256,
                "config": self._config,
            }
        )
        receipt = IngestionReceiptV2.build(
            document_id=original_docx.document_id,
            source_sha256=original_docx.source_sha256,
            index_fingerprint=index_fingerprint,
            details={"runtime_chunk_count": 1},
        )
        self._prepared = PreparedSystemV2.build(
            effective_config=dict(self._config),
            source_identity=source_identity,
            runtime_profile=runtime_profile,
            observation_profile=observation_profile,
            ingestion_receipt=receipt,
        )
        return self._prepared

    async def health(self) -> NativeHealthReportV2:
        return NativeHealthReportV2(
            status="closed" if self._closed else "ready",
            ready=not self._closed,
            details={"prepared": self._prepared is not None},
        )

    async def query(
        self,
        prepared_system: PreparedSystemV2,
        request: NativeQueryV2,
    ) -> AdapterRunResultV2:
        if self._prepared is None or self._chunk is None:
            raise RuntimeError("adapter is not prepared")
        if prepared_system != self._prepared:
            raise ValueError("query references a different prepared system")
        delay = float(self._config.get("delay_seconds", 0))
        if delay:
            await asyncio.sleep(delay)
        started = monotonic()
        query_tokens = {
            token.casefold() for token in _TOKEN_RE.findall(request.question)
        }
        chunk_tokens = {
            token.casefold() for token in _TOKEN_RE.findall(self._chunk.content or "")
        }
        score = float(len(query_tokens & chunk_tokens))
        item = ObservedStageItem(
            native_chunk_id=self._chunk.native_chunk_id,
            native_rank=1,
            runtime_score=score,
            content_sha256=self._chunk.content_sha256,
            content=self._chunk.content or "",
            provenance_edge_ids=(),
        )
        candidate = _stage_observation(
            StageName.CANDIDATE,
            item,
            cutoff=request.retrieval_candidate_k,
            supported=self.capabilities.candidate_retrieval,
        )
        ranked = _stage_observation(
            StageName.RANKED,
            item,
            cutoff=request.retrieval_candidate_k,
            supported=self.capabilities.ranked_retrieval,
        )
        context = _stage_observation(
            StageName.CONTEXT,
            item,
            cutoff=request.final_context_k,
            supported=self.capabilities.final_context,
        )
        answer_text = self._chunk.content or ""
        answer = (
            ContentObservation.observed(answer_text)
            if request.generate_answer and self.capabilities.answer
            else ContentObservation(
                observation_status=ObservationStatus.UNSUPPORTED,
                completeness=ObservationCompleteness.UNKNOWN,
                reason="answer capability is unavailable",
            )
        )
        if not request.generate_answer and self.capabilities.answer:
            answer = ContentObservation(
                observation_status=ObservationStatus.UNOBSERVED,
                completeness=ObservationCompleteness.UNKNOWN,
                reason="answer generation was not requested",
            )
        prompt = ContentObservation(
            observation_status=(
                ObservationStatus.UNOBSERVED
                if self.capabilities.prompt_trace
                else ObservationStatus.UNSUPPORTED
            ),
            completeness=ObservationCompleteness.UNKNOWN,
            reason="fake Adapter does not expose a rendered prompt",
        )
        ingestion_catalog = IngestionCatalogObservation(
            observation_status=(
                ObservationStatus.OBSERVED
                if self.capabilities.ingestion_catalog
                else ObservationStatus.UNSUPPORTED
            ),
            completeness=(
                ObservationCompleteness.COMPLETE
                if self.capabilities.ingestion_catalog
                else ObservationCompleteness.UNKNOWN
            ),
            items=(self._chunk,) if self.capabilities.ingestion_catalog else (),
            reason=(
                None
                if self.capabilities.ingestion_catalog
                else "ingestion catalog capability is unavailable"
            ),
        )
        trace = UnifiedTrace.build(
            case_id=request.case_id,
            source_identity=self._prepared.source_identity,
            runtime_profile=self._prepared.runtime_profile,
            observation_profile=self._prepared.observation_profile,
            ingestion_catalog=ingestion_catalog,
            provenance_edges=(),
            canonical_mapping_records=(),
            mapping_diagnostics=(),
            raw_retrieval=candidate,
            ranked_retrieval=ranked,
            final_context=context,
            transformations=(),
            prompt_trace=prompt,
            answer=answer,
            validation_receipts=(),
        )
        return AdapterRunResultV2(
            adapter_id="fake",
            adapter_version=ADAPTER_VERSION,
            system_id="fake-rag",
            system_version=SYSTEM_VERSION,
            trace=trace,
            telemetry={
                "latency": {"native_query_latency": monotonic() - started},
                "token_usage": {"context_characters": len(answer_text)},
                "native_query_executions": 1,
            },
        )

    async def close(self) -> None:
        self._closed = True
        self._prepared = None
        self._chunk = None


def _stage_observation(
    stage: StageName,
    item: ObservedStageItem,
    *,
    cutoff: int,
    supported: bool,
) -> StageObservation:
    if not supported:
        return StageObservation(
            stage=stage,
            observation_status=ObservationStatus.UNSUPPORTED,
            completeness=ObservationCompleteness.UNKNOWN,
            configured_cutoff=cutoff,
            items=(),
            reason=f"{stage.value} capability is unavailable",
        )
    return StageObservation(
        stage=stage,
        observation_status=ObservationStatus.OBSERVED,
        completeness=ObservationCompleteness.COMPLETE,
        configured_cutoff=cutoff,
        items=(item,),
    )


def _docx_text(path: Path) -> str:
    if not path.is_file():
        raise ValueError("original DOCX is unavailable")
    try:
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
    except (KeyError, OSError, ElementTree.ParseError, zipfile.BadZipFile) as exc:
        raise ValueError("original source is not a readable DOCX") from exc
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_WORD_NAMESPACE}p"):
        text = "".join(
            node.text or "" for node in paragraph.iter(f"{_WORD_NAMESPACE}t")
        )
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def create_worker_definition() -> WorkerDefinition:
    return WorkerDefinition(
        adapter=FakeAdapter(),
        identity=WorkerIdentityV2(
            adapter_id="fake",
            adapter_version=ADAPTER_VERSION,
            system_id="fake-rag",
            system_version=SYSTEM_VERSION,
        ),
    )


__all__ = ["FakeAdapter", "create_worker_definition"]
