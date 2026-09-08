from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest
from rag_eval.adapters.observation_tck import assert_unified_observation_tck
from rag_eval.contracts.adapter import DocumentInput, PrepareContext, RAGQuery
from rag_eval.contracts.dataset import (
    GoldEvidence,
    GoldEvidenceSet,
    GoldSourceIdentity,
)
from rag_eval.contracts.observation import (
    AdapterRunResultV2,
    MappingDiagnosticStatus,
    ObservationStatus,
    ReverseMappingStatus,
)
from rag_eval.evaluation.unified.models import EvaluationProfile
from rag_eval.evaluation.unified.scorer import evaluate_unified_trace
from rag_eval_rag_anything_adapter.adapter import (
    OfficialRAGAnythingRuntime,
    RAGAnythingAdapter,
)
from rag_eval_rag_anything_adapter.native_observation import (
    RuntimeIngestionCapture,
    RuntimeQueryCapture,
    build_native_observation_snapshot,
    build_native_run_result_v2,
)


def _sha(value: str | bytes) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()


def _canonical_record(
    *,
    document_id: str,
    source_sha256: str,
    object_id: str,
    witness: str,
    ordinal: int,
    object_type: str = "paragraph",
) -> dict[str, object]:
    return {
        "object_id": object_id,
        "document_id": document_id,
        "object_type": object_type,
        "representation_status": "complete",
        "document_order": ordinal,
        "canonical_value": witness,
        "provenance": {
            "source_sha256": source_sha256,
            "parser_identity": "python-docx/fixture",
            "canonicalizer_identity": "rag-eval-authoring-canonicalizer/5",
            "configuration_digest": "a" * 64,
            "extraction_method": "fixture",
            "source_spans": [
                {
                    "coordinate_system": "ooxml-structural-v1",
                    "part": "word/document.xml",
                    "coordinates": {"body_ordinal": ordinal},
                }
            ],
            "derived_from_object_ids": [],
        },
    }


def _write_native_inputs(tmp_path: Path, *, duplicate: bool = False) -> tuple[
    PrepareContext, DocumentInput, RuntimeIngestionCapture
]:
    source = tmp_path / "source"
    source.mkdir()
    docx = source / "source.docx"
    docx.write_bytes(b"native-docx-fixture")
    source_sha256 = _sha(docx.read_bytes())
    full_text = (
        "prefix alpha beta gamma suffix alpha beta gamma"
        if duplicate
        else "prefix alpha beta gamma suffix"
    )
    records = [
        _canonical_record(
            document_id="doc-1",
            source_sha256=source_sha256,
            object_id="paragraph-1",
            witness="alpha beta gamma",
            ordinal=1,
        ),
        _canonical_record(
            document_id="doc-1",
            source_sha256=source_sha256,
            object_id="paragraph-2",
            witness="gamma",
            ordinal=2,
        ),
        _canonical_record(
            document_id="doc-1",
            source_sha256=source_sha256,
            object_id="logical-cell-1",
            object_type="logical_cell",
            witness="beta",
            ordinal=3,
        ),
    ]
    sidecar = source / "canonical.jsonl"
    sidecar.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for item in records
        ),
        encoding="utf-8",
    )
    context = PrepareContext(
        run_id="run-native",
        work_dir=str(tmp_path / "work"),
        source_dir=str(source),
        platform_version="0.1.0",
    )
    document = DocumentInput(
        document_id="doc-1",
        source_path=docx.name,
        sha256=source_sha256,
        mime_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        metadata={
            "original_name": "source.docx",
            "canonical_provenance_path": sidecar.name,
            "canonical_provenance_sha256": _sha(sidecar.read_bytes()),
        },
    )
    capture = RuntimeIngestionCapture(
        chunks={
            "chunk-a": {
                "content": "alpha beta ",
                "full_doc_id": "doc-1",
                "chunk_order_index": 0,
                "tokens": 3,
                "file_path": "source.docx",
            },
            "chunk-b": {
                "content": "beta gamma",
                "full_doc_id": "doc-1",
                "chunk_order_index": 1,
                "tokens": 2,
                "file_path": "source.docx",
            },
        },
        full_documents={"doc-1": full_text},
        storage_identity="JsonKVStorage",
    )
    return context, document, capture


class ObservedRuntime:
    system_version = "1.3.1"
    core_version = "1.4.16"

    def __init__(self, ingestion: RuntimeIngestionCapture) -> None:
        self.ingestion = ingestion
        self.model_digests = {"llm": "sha256:model"}
        self.prompt_digests = {"raganything_prompt_sources": "sha256:prompt"}
        self.query_calls = 0

    async def process_document(self, _path: Path, **_kwargs) -> None:
        return None

    async def insert_text(self, _content: str, **_kwargs) -> None:
        return None

    async def observe_ingestion_catalog(self) -> RuntimeIngestionCapture:
        return self.ingestion

    async def query_with_observation(self, *_args, **_kwargs) -> RuntimeQueryCapture:
        self.query_calls += 1
        candidates = [
            {"id": "chunk-b", "content": "beta gamma", "distance": 0.91},
            {"id": "chunk-a", "content": "alpha beta ", "distance": 0.73},
        ]
        return RuntimeQueryCapture.observed(
            answer="42 ms",
            candidate_items=candidates,
            query_result={
                "status": "success",
                "data": {
                    "chunks": [
                        {
                            "chunk_id": "chunk-b",
                            "content": "beta gamma",
                            "file_path": "source.docx",
                            "reference_id": "1",
                        },
                        {
                            "chunk_id": "chunk-a",
                            "content": "alpha beta ",
                            "file_path": "source.docx",
                            "reference_id": "1",
                        },
                    ]
                },
                "metadata": {"query_mode": "naive"},
                "llm_response": {
                    "content": "42 ms",
                    "is_streaming": False,
                    "response_iterator": None,
                },
            },
            candidate_cutoff=5,
            query_parameters={
                "mode": "naive",
                "enable_rerank": False,
                "chunk_top_k": 5,
            },
        )

    async def query(self, *_args, **_kwargs) -> str:
        raise AssertionError("the adapter must not execute a second answer-only query")

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_native_query_hook_captures_one_execution_without_changing_answer() -> None:
    class VectorStore:
        def __init__(self) -> None:
            self.calls = 0

        async def query(self, _query: str, top_k: int, query_embedding=None):
            del query_embedding
            self.calls += 1
            assert top_k == 5
            return [{"id": "chunk-1", "content": "exact", "distance": 0.9}]

    class Core:
        def __init__(self) -> None:
            self.chunks_vdb = VectorStore()
            self.calls = 0

        async def aquery_llm(self, query, param, system_prompt=None):
            del system_prompt
            self.calls += 1
            candidates = await self.chunks_vdb.query(query, top_k=param.chunk_top_k)
            return {
                "status": "success",
                "data": {
                    "chunks": [
                        {
                            "chunk_id": candidates[0]["id"],
                            "content": candidates[0]["content"],
                        }
                    ]
                },
                "metadata": {"query_mode": param.mode},
                "llm_response": {
                    "content": "native answer",
                    "is_streaming": False,
                    "response_iterator": None,
                },
            }

        async def aquery(self, query, param, system_prompt=None):
            result = await self.aquery_llm(query, param, system_prompt)
            return result["llm_response"]["content"]

    class NativeRAG:
        def __init__(self) -> None:
            self.lightrag = Core()

        async def aquery(self, question, mode="mix", **kwargs):
            param = SimpleNamespace(
                mode=mode,
                enable_rerank=False,
                chunk_top_k=kwargs["chunk_top_k"],
            )
            return await self.lightrag.aquery(question, param)

    rag = NativeRAG()
    runtime = OfficialRAGAnythingRuntime(
        rag,
        system_version="1.3.1",
        core_version="1.4.16",
        model_digests={},
        prompt_digests={},
        output_dir=Path("unused"),
        parse_timeout_seconds=1,
    )

    capture = await runtime.query_with_observation(
        "question",
        mode="naive",
        generate_answer=True,
        options={"chunk_top_k": 5, "vlm_enhanced": False},
    )

    assert capture.answer == "native answer"
    assert capture.observation_status == ObservationStatus.OBSERVED
    assert [item["id"] for item in capture.candidate_items] == ["chunk-1"]
    assert capture.query_result["llm_response"]["content"] == capture.answer
    assert rag.lightrag.calls == 1
    assert rag.lightrag.chunks_vdb.calls == 1


@pytest.mark.asyncio
async def test_native_query_observation_failure_does_not_change_answer() -> None:
    class Uncopyable:
        def __deepcopy__(self, _memo):
            raise TypeError("fixture cannot be copied")

    class VectorStore:
        def __init__(self) -> None:
            self.calls = 0

        async def query(self, _query: str, top_k: int, query_embedding=None):
            del query_embedding
            self.calls += 1
            return [{"id": "chunk-1", "content": "exact", "distance": 0.9}]

    class Core:
        def __init__(self) -> None:
            self.chunks_vdb = VectorStore()
            self.calls = 0

        async def aquery_llm(self, query, param, system_prompt=None):
            del system_prompt
            self.calls += 1
            candidates = await self.chunks_vdb.query(query, top_k=param.chunk_top_k)
            return {
                "status": "success",
                "data": {"chunks": candidates},
                "llm_response": {"content": "native answer"},
                "observer_hostile_value": Uncopyable(),
            }

        async def aquery(self, query, param, system_prompt=None):
            result = await self.aquery_llm(query, param, system_prompt)
            return result["llm_response"]["content"]

    class NativeRAG:
        def __init__(self) -> None:
            self.lightrag = Core()

        async def aquery(self, question, mode="mix", **kwargs):
            param = SimpleNamespace(
                mode=mode,
                enable_rerank=False,
                chunk_top_k=kwargs["chunk_top_k"],
            )
            return await self.lightrag.aquery(question, param)

    rag = NativeRAG()
    runtime = OfficialRAGAnythingRuntime(
        rag,
        system_version="1.3.1",
        core_version="1.4.16",
        model_digests={},
        prompt_digests={},
        output_dir=Path("unused"),
        parse_timeout_seconds=1,
    )

    capture = await runtime.query_with_observation(
        "question",
        mode="naive",
        generate_answer=True,
        options={"chunk_top_k": 5, "vlm_enhanced": False},
    )

    assert capture.answer == "native answer"
    assert capture.observation_status == ObservationStatus.CORRUPTED
    assert capture.reason == "native query observation capture failed: aquery_llm_capture:TypeError"
    assert rag.lightrag.calls == 1
    assert rag.lightrag.chunks_vdb.calls == 1


@pytest.mark.asyncio
async def test_adapter_emits_typed_native_trace_and_unions_split_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    context, document, ingestion = _write_native_inputs(tmp_path)
    runtime = ObservedRuntime(ingestion)

    async def create(*_args, **_kwargs):
        return runtime

    monkeypatch.setattr(OfficialRAGAnythingRuntime, "create", create)
    adapter = RAGAnythingAdapter()
    await adapter.prepare(context, {"query_mode": "naive"})
    details = await adapter.ingest([document])
    result = await adapter.query(
        RAGQuery(
            case_id="case-1",
            question="What is the latency?",
            retrieval_candidate_k=20,
            final_context_k=5,
        )
    )

    assert details.details["wire_v2_native_observation"]["observation_status"] == "observed"
    assert result.answer == "42 ms"
    # Wire 1.0 remains the frozen answer-only compatibility surface.  The
    # additive Wire 2.0 envelope is the execution authority for native metrics.
    assert result.raw_retrieval is None
    envelope = result.trace["wire_v2_native_observation"]
    observed = AdapterRunResultV2.model_validate(envelope["adapter_run_result"])
    assert_unified_observation_tck(
        observed,
        adapter_id="rag-anything",
        system_id="rag-anything",
        case_id="case-1",
    )
    assert observed.trace.raw_retrieval.observation_status == ObservationStatus.OBSERVED
    assert observed.trace.ranked_retrieval.proves_prefix(5)
    assert observed.trace.final_context.observation_status == ObservationStatus.OBSERVED
    mapping = {
        item.canonical_object_id: item for item in observed.trace.canonical_mapping_records
    }
    assert mapping["paragraph-1"].reverse_mapping_status == ReverseMappingStatus.COMPLETE
    assert mapping["paragraph-1"].native_chunk_ids == ("chunk-a", "chunk-b")
    assert (
        mapping["logical-cell-1"].reverse_mapping_status
        == ReverseMappingStatus.UNSUPPORTED
    )
    assert len(
        [
            edge
            for edge in observed.trace.provenance_edges
            if edge.canonical_object_id == "paragraph-1"
        ]
    ) == 2
    assert len(
        [
            edge
            for edge in observed.trace.provenance_edges
            if edge.native_chunk_id == "chunk-b"
        ]
    ) == 2
    assert all(
        edge.native_lineage_sha256 is not None
        for edge in observed.trace.provenance_edges
    )
    assert runtime.query_calls == 1

    gold = GoldEvidenceSet(
        gold_evidence_set_id="gold-1",
        evidence=[
            GoldEvidence(
                evidence_id="evidence-1",
                document_id="doc-1",
                canonical_object_id="paragraph-1",
                canonical_value="alpha beta gamma",
                locator={
                    "type": "object",
                    "object_type": "paragraph",
                    "object_id": "paragraph-1",
                },
            )
        ],
        required_groups=[["evidence-1"]],
        source_identities=(
            GoldSourceIdentity(
                document_id="doc-1",
                source_sha256=document.sha256,
                source_coordinate_schema="ooxml-structural-v1",
                canonical_catalog_sha256=document.metadata[
                    "canonical_provenance_sha256"
                ],
            ),
        ),
    )
    scored = evaluate_unified_trace(
        gold,
        observed.trace,
        profile=EvaluationProfile(
            candidate_cutoff=20,
            ranked_cutoffs=(1, 3, 5),
            ranked_mrr_cutoff=5,
            context_budget=12000,
        ),
    )
    metrics = {item.metric_id: item for item in scored.metrics}
    assert metrics["ranked_complete_evidence_mrr@5"].value == 0.5


@pytest.mark.asyncio
async def test_duplicate_parser_text_fails_closed_instead_of_guessing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    context, document, ingestion = _write_native_inputs(tmp_path, duplicate=True)
    runtime = ObservedRuntime(ingestion)

    async def create(*_args, **_kwargs):
        return runtime

    monkeypatch.setattr(OfficialRAGAnythingRuntime, "create", create)
    adapter = RAGAnythingAdapter()
    await adapter.prepare(context, {"query_mode": "naive"})
    await adapter.ingest([document])
    result = await adapter.query(
        RAGQuery(case_id="case-1", question="What is the latency?", final_context_k=5)
    )
    observed = AdapterRunResultV2.model_validate(
        result.trace["wire_v2_native_observation"]["adapter_run_result"]
    )
    record = next(
        item
        for item in observed.trace.canonical_mapping_records
        if item.canonical_object_id == "paragraph-1"
    )
    assert record.reverse_mapping_status == ReverseMappingStatus.MISSING
    assert any(
        item.canonical_object_id == "paragraph-1"
        and item.status == MappingDiagnosticStatus.CORRUPTED
        and item.reason_code == "ambiguous_exact_witness_in_parser_stream"
        for item in observed.trace.mapping_diagnostics
    )


@pytest.mark.asyncio
async def test_non_naive_profile_keeps_answer_but_marks_stages_unobserved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    context, document, ingestion = _write_native_inputs(tmp_path)
    runtime = ObservedRuntime(ingestion)

    async def create(*_args, **_kwargs):
        return runtime

    monkeypatch.setattr(OfficialRAGAnythingRuntime, "create", create)
    adapter = RAGAnythingAdapter()
    await adapter.prepare(context, {"query_mode": "mix"})
    await adapter.ingest([document])
    result = await adapter.query(
        RAGQuery(case_id="case-1", question="What is the latency?", final_context_k=5)
    )
    observed = AdapterRunResultV2.model_validate(
        result.trace["wire_v2_native_observation"]["adapter_run_result"]
    )
    assert result.answer == "42 ms"
    assert observed.trace.answer.observation_status == ObservationStatus.OBSERVED
    assert observed.trace.raw_retrieval.observation_status == ObservationStatus.UNOBSERVED
    assert observed.trace.ranked_retrieval.observation_status == ObservationStatus.UNOBSERVED
    assert observed.trace.final_context.observation_status == ObservationStatus.UNOBSERVED


@pytest.mark.asyncio
async def test_native_wire_v2_answer_only_fallback_remains_typed_and_usable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    context, document, ingestion = _write_native_inputs(tmp_path)

    class CatalogOnlyRuntime:
        system_version = "1.3.1"
        core_version = "1.4.16"
        model_digests: ClassVar[dict[str, str]] = {"llm": "sha256:model"}
        prompt_digests: ClassVar[dict[str, str]] = {
            "raganything_prompt_sources": "sha256:prompt"
        }

        async def process_document(self, _path: Path, **_kwargs) -> None:
            return None

        async def insert_text(self, _content: str, **_kwargs) -> None:
            return None

        async def observe_ingestion_catalog(self) -> RuntimeIngestionCapture:
            return ingestion

        async def query(self, *_args, **_kwargs) -> str:
            return "42 ms"

        async def close(self) -> None:
            return None

    runtime = CatalogOnlyRuntime()

    async def create(*_args, **_kwargs):
        return runtime

    monkeypatch.setattr(OfficialRAGAnythingRuntime, "create", create)
    adapter = RAGAnythingAdapter()
    await adapter.prepare(context, {"query_mode": "naive"})
    await adapter.ingest([document])
    result = await adapter.query(
        RAGQuery(case_id="case-1", question="What is the latency?", final_context_k=5)
    )
    observed = AdapterRunResultV2.model_validate(
        result.trace["wire_v2_native_observation"]["adapter_run_result"]
    )

    assert result.answer == "42 ms"
    assert observed.trace.answer.observation_status == ObservationStatus.OBSERVED
    assert observed.trace.raw_retrieval.observation_status == ObservationStatus.UNOBSERVED
    assert "same-execution" in observed.trace.raw_retrieval.reason


def test_corrupted_context_cannot_receive_verified_stage_lineage(
    tmp_path: Path,
) -> None:
    context, document, ingestion = _write_native_inputs(tmp_path)
    snapshot = build_native_observation_snapshot(
        document=document,
        source_dir=Path(context.source_dir),
        capture=ingestion,
        runtime_config={"query_mode": "naive", "parser": "mineru"},
        system_version="1.3.1",
        core_version="1.4.16",
        adapter_version="0.1.0",
    )
    capture = RuntimeQueryCapture.observed(
        answer="42 ms",
        candidate_items=[
            {"id": "chunk-a", "content": "alpha beta ", "distance": 0.8}
        ],
        query_result={
            "data": {
                "chunks": [
                    {
                        "chunk_id": "chunk-a",
                        "content": "content changed after retrieval",
                    }
                ]
            },
            "llm_response": {"content": "42 ms"},
        },
        candidate_cutoff=5,
        query_parameters={"mode": "naive", "enable_rerank": False},
    )

    result = build_native_run_result_v2(
        snapshot=snapshot,
        case_id="case-corrupted-context",
        capture=capture,
        generate_answer=True,
        adapter_version="0.1.0",
    )

    assert result.trace.final_context.observation_status == ObservationStatus.CORRUPTED
    assert not any(
        item.receipt_kind == "same_execution_stage_lineage"
        for item in result.trace.validation_receipts
    )
