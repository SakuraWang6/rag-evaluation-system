from __future__ import annotations

import asyncio
import hashlib
import json

from rag_eval.contracts.adapter import RAGQuery
from rag_eval.contracts.observation import (
    AdapterRunResultV2,
    ObservationCompleteness,
    ObservationStatus,
    ReverseMappingStatus,
    StageName,
    StageTransitionMode,
)
from rag_eval_lightrag_adapter.adapter import (
    ADAPTER_VERSION,
    LightRAGAdapter,
    resolve_config,
)
from rag_eval_lightrag_adapter.canonical_provenance import (
    NativeDocxCanonicalObject,
    NativeDocxDocumentMap,
    build_native_docx_provenance_manifest,
)
from rag_eval_lightrag_adapter.native_observation import (
    build_native_observation_snapshot,
    build_native_run_result_v2,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _object(
    *,
    document_id: str,
    source_sha256: str,
    object_id: str,
    object_type: str,
    body_ordinal: int,
    value: str,
    **attributes: object,
) -> NativeDocxCanonicalObject:
    locator = {
        "part": "word/document.xml",
        "body_ordinal": body_ordinal,
    }
    locator.update(
        {
            key: value
            for key, value in attributes.items()
            if key
            in {
                "table_id",
                "row",
                "column",
                "physical_cell_index",
                "grid_span",
                "v_merge",
            }
        }
    )
    raw = {
        "document_id": document_id,
        "object_id": object_id,
        "object_type": object_type,
        "source_sha256": source_sha256,
        "canonicalizer": "rag-eval-authoring-canonicalizer/5",
        "canonical_value": value,
        "status": "supported",
        "structural_locator": locator,
        **attributes,
    }
    return NativeDocxCanonicalObject(
        object_id=object_id,
        object_type=object_type,
        representation_status="complete",
        source_sha256=source_sha256,
        locator=locator,
        expected_extent={
            "status": "complete",
            "object_id": object_id,
        },
        canonical_value=value,
        witness_sha256=_sha(value),
        raw_record=raw,
    )


def _document(
    objects: tuple[NativeDocxCanonicalObject, ...],
    *,
    document_id: str,
    source_sha256: str,
) -> NativeDocxDocumentMap:
    return NativeDocxDocumentMap(
        document_id=document_id,
        canonical_sidecar_sha256=_sha("canonical-sidecar"),
        canonical_digest=_sha("canonical-catalog"),
        canonicalizer="rag-eval-authoring-canonicalizer/5",
        tables=(),
        diagnostics=(),
        source_sha256=source_sha256,
        objects=objects,
    )


def _lineage(
    *,
    source_sha256: str,
    content: str,
    atoms: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": "lightrag-native-docx-lineage/1",
        "source_sha256": source_sha256,
        "parsed_content_sha256": _sha(content),
        "parsed_content_length": len(content),
        "atoms": atoms,
    }


def _paragraph_atom(
    *,
    source_sha256: str,
    body_ordinal: int,
    value: str,
    content: str,
) -> dict[str, object]:
    return {
        "kind": "paragraph",
        "source_sha256": source_sha256,
        "source_value": value,
        "source_value_sha256": _sha(value),
        "coverage_status": "complete",
        "source_locator": {
            "part": "word/document.xml",
            "body_ordinal": body_ordinal,
        },
        "parsed_span": {"start": 0, "end": len(content)},
    }


def _runtime_config() -> dict[str, object]:
    return {
        "profile": "legacy",
        "query_mode": "naive",
        "ranking_strategy": "none",
        "exact_id_types": [],
        "chunking": {
            "strategy": "fixed_token",
            "chunk_token_size": 1200,
            "chunk_overlap_token_size": 100,
        },
    }


def test_native_snapshot_projects_one_chunk_to_paragraph_and_text_span() -> None:
    document_id = "doc-one-to-many"
    source_sha = _sha("original-docx")
    value = "Repeated evidence"
    block_id = f"{document_id}:block:00001"
    span_id = f"{document_id}:text_span:00001"
    block = _object(
        document_id=document_id,
        source_sha256=source_sha,
        object_id=block_id,
        object_type="block",
        body_ordinal=0,
        value=value,
    )
    span = _object(
        document_id=document_id,
        source_sha256=source_sha,
        object_id=span_id,
        object_type="text_span",
        body_ordinal=0,
        value=value,
        block_id=block_id,
    )
    document = _document(
        (block, span), document_id=document_id, source_sha256=source_sha
    )
    lineage = _lineage(
        source_sha256=source_sha,
        content=value,
        atoms=[
            _paragraph_atom(
                source_sha256=source_sha,
                body_ordinal=0,
                value=value,
                content=value,
            )
        ],
    )
    stored = {
        "chunk-1": {
            "content": value,
            "file_path": "source.docx",
            "full_doc_id": "native-doc-1",
            "source_span": {"start": 0, "end": len(value)},
            "lineage": lineage,
        }
    }
    manifest = build_native_docx_provenance_manifest(
        documents={document_id: document},
        document_by_file={"source.docx": document_id},
        stored_chunks=stored,
    )

    snapshot = build_native_observation_snapshot(
        document=document,
        stored_chunks=stored,
        provenance_manifest=manifest,
        runtime_config=_runtime_config(),
        system_version="1.4.0",
        adapter_version=ADAPTER_VERSION,
    )

    edges = {edge.canonical_object_id: edge for edge in snapshot.provenance_edges}
    assert set(edges) == {block_id, span_id}
    assert edges[block_id].mapping_tier.value == "native_lineage"
    assert edges[span_id].mapping_tier.value == "deterministic_crosswalk"
    assert {edge.native_chunk_id for edge in edges.values()} == {"chunk-1"}
    assert all(edge.coverage_status.value == "complete" for edge in edges.values())


def test_split_merged_table_chunks_union_to_complete_logical_evidence() -> None:
    document_id = "doc-split-merge"
    source_sha = _sha("split-merge-docx")
    table_id = f"{document_id}:table:00001"
    logical_id = f"{document_id}:logical_cell:00001"
    origin_id = f"{document_id}:cell:00001"
    continuation_id = f"{document_id}:cell:00002"
    table = _object(
        document_id=document_id,
        source_sha256=source_sha,
        object_id=table_id,
        object_type="table",
        body_ordinal=0,
        value="A\nA",
        table_id=table_id,
    )
    logical = _object(
        document_id=document_id,
        source_sha256=source_sha,
        object_id=logical_id,
        object_type="logical_cell",
        body_ordinal=0,
        value="A",
        table_id=table_id,
        row=1,
        column=1,
        derived_from_object_ids=[origin_id, continuation_id],
        origin_physical_cell_id=origin_id,
    )
    origin = _object(
        document_id=document_id,
        source_sha256=source_sha,
        object_id=origin_id,
        object_type="cell",
        body_ordinal=0,
        value="A",
        table_id=table_id,
        row=1,
        column=1,
        physical_cell_index=1,
        grid_span=1,
        v_merge="restart",
        logical_cell_id=logical_id,
        merged_cell_origin_physical_id=origin_id,
    )
    continuation = _object(
        document_id=document_id,
        source_sha256=source_sha,
        object_id=continuation_id,
        object_type="cell",
        body_ordinal=0,
        value="",
        table_id=table_id,
        row=2,
        column=1,
        physical_cell_index=1,
        grid_span=1,
        v_merge="continue",
        logical_cell_id=logical_id,
        merged_cell_origin_physical_id=origin_id,
    )
    document = _document(
        (table, logical, origin, continuation),
        document_id=document_id,
        source_sha256=source_sha,
    )
    stored: dict[str, dict[str, object]] = {}
    for row, chunk_id in ((1, "chunk-row-1"), (2, "chunk-row-2")):
        content = '<table id="runtime" format="json">[["A"]]</table>'
        cell_start = content.index('"A"')
        atom = {
            "kind": "table",
            "source_sha256": source_sha,
            "source_value": "A\nA",
            "source_value_sha256": _sha("A A"),
            "coverage_status": "partial",
            "missing_reason": "table_row_split",
            "source_locator": {
                "part": "word/document.xml",
                "body_ordinal": 0,
            },
            "parsed_span": {"start": 0, "end": len(content)},
            "covered_ranges": {"rows": [row]},
            "cells": [
                {
                    "source_sha256": source_sha,
                    "source_value": "A",
                    "source_value_sha256": _sha("A"),
                    "coverage_status": "complete",
                    "source_locator": {
                        "part": "word/document.xml",
                        "body_ordinal": 0,
                        "row": row,
                        "column": 1,
                        "physical_cell_index": 1,
                        "grid_span": 1,
                        "v_merge": "restart" if row == 1 else "continue",
                    },
                    "parsed_span": {
                        "start": cell_start,
                        "end": cell_start + len('"A"'),
                    },
                }
            ],
        }
        stored[chunk_id] = {
            "content": content,
            "file_path": "source.docx",
            "full_doc_id": "native-doc-1",
            "lineage": _lineage(
                source_sha256=source_sha,
                content=content,
                atoms=[atom],
            ),
        }
    manifest = build_native_docx_provenance_manifest(
        documents={document_id: document},
        document_by_file={"source.docx": document_id},
        stored_chunks=stored,
    )

    snapshot = build_native_observation_snapshot(
        document=document,
        stored_chunks=stored,
        provenance_manifest=manifest,
        runtime_config=_runtime_config(),
        system_version="1.4.0",
        adapter_version=ADAPTER_VERSION,
    )

    logical_edges = [
        edge
        for edge in snapshot.provenance_edges
        if edge.canonical_object_id == logical_id
    ]
    table_edges = [
        edge
        for edge in snapshot.provenance_edges
        if edge.canonical_object_id == table_id
    ]
    assert {edge.native_chunk_id for edge in logical_edges} == {
        "chunk-row-1",
        "chunk-row-2",
    }
    assert {edge.coverage_status.value for edge in logical_edges} == {"partial"}
    assert {edge.native_chunk_id for edge in table_edges} == {
        "chunk-row-1",
        "chunk-row-2",
    }
    reverse = {
        item.canonical_object_id: item for item in snapshot.canonical_mapping_records
    }
    assert reverse[logical_id].reverse_mapping_status == ReverseMappingStatus.COMPLETE
    assert reverse[table_id].reverse_mapping_status == ReverseMappingStatus.COMPLETE
    assert len(logical_edges[0].physical_cell_footprint) == 1


def test_duplicate_text_uses_native_locator_and_bad_witness_fails_closed() -> None:
    document_id = "doc-duplicate"
    source_sha = _sha("duplicate-docx")
    value = "same text"
    first = _object(
        document_id=document_id,
        source_sha256=source_sha,
        object_id=f"{document_id}:block:00001",
        object_type="block",
        body_ordinal=0,
        value=value,
    )
    second = _object(
        document_id=document_id,
        source_sha256=source_sha,
        object_id=f"{document_id}:block:00002",
        object_type="block",
        body_ordinal=1,
        value=value,
    )
    document = _document(
        (first, second), document_id=document_id, source_sha256=source_sha
    )
    stored: dict[str, dict[str, object]] = {}
    for ordinal, chunk_id in ((0, "chunk-first"), (1, "chunk-second")):
        atom = _paragraph_atom(
            source_sha256=source_sha,
            body_ordinal=ordinal,
            value=value,
            content=value,
        )
        if ordinal == 1:
            atom["source_value"] = "tampered"
        stored[chunk_id] = {
            "content": value,
            "file_path": "source.docx",
            "full_doc_id": "native-doc-1",
            "source_span": {"start": ordinal * 20, "end": ordinal * 20 + len(value)},
            "lineage": _lineage(
                source_sha256=source_sha,
                content=value,
                atoms=[atom],
            ),
        }
    manifest = build_native_docx_provenance_manifest(
        documents={document_id: document},
        document_by_file={"source.docx": document_id},
        stored_chunks=stored,
    )

    snapshot = build_native_observation_snapshot(
        document=document,
        stored_chunks=stored,
        provenance_manifest=manifest,
        runtime_config=_runtime_config(),
        system_version="1.4.0",
        adapter_version=ADAPTER_VERSION,
    )

    assert {
        (edge.native_chunk_id, edge.canonical_object_id)
        for edge in snapshot.provenance_edges
    } == {("chunk-first", first.object_id)}
    reverse = {
        item.canonical_object_id: item for item in snapshot.canonical_mapping_records
    }
    assert (
        reverse[first.object_id].reverse_mapping_status == ReverseMappingStatus.COMPLETE
    )
    assert (
        reverse[second.object_id].reverse_mapping_status == ReverseMappingStatus.MISSING
    )
    assert any(
        item.native_chunk_id == "chunk-second" and "witness" in item.reason_code
        for item in snapshot.mapping_diagnostics
    )


def test_regular_physical_cell_does_not_claim_a_merge_origin() -> None:
    document_id = "doc-regular-cell"
    source_sha = _sha("regular-cell-docx")
    table_id = f"{document_id}:table:00001"
    cell_id = f"{document_id}:cell:00001"
    cell = _object(
        document_id=document_id,
        source_sha256=source_sha,
        object_id=cell_id,
        object_type="cell",
        body_ordinal=0,
        value="value",
        table_id=table_id,
        row=1,
        column=1,
        physical_cell_index=1,
        grid_span=1,
        v_merge="none",
        logical_cell_id=f"{document_id}:logical_cell:00001",
        merged_cell_origin_physical_id=cell_id,
    )
    document = _document((cell,), document_id=document_id, source_sha256=source_sha)
    content = '<table id="runtime" format="json">[["value"]]</table>'
    value_start = content.index('"value"')
    atom = {
        "kind": "table",
        "source_sha256": source_sha,
        "source_value": "value",
        "source_value_sha256": _sha("value"),
        "coverage_status": "partial",
        "source_locator": {
            "part": "word/document.xml",
            "body_ordinal": 0,
        },
        "parsed_span": {"start": 0, "end": len(content)},
        "cells": [
            {
                "source_sha256": source_sha,
                "source_value": "value",
                "source_value_sha256": _sha("value"),
                "coverage_status": "complete",
                "source_locator": {
                    "part": "word/document.xml",
                    "body_ordinal": 0,
                    "row": 1,
                    "column": 1,
                    "physical_cell_index": 1,
                    "grid_span": 1,
                    "v_merge": "none",
                },
                "parsed_span": {
                    "start": value_start,
                    "end": value_start + len('"value"'),
                },
            }
        ],
    }
    stored = {
        "chunk-cell": {
            "content": content,
            "file_path": "source.docx",
            "full_doc_id": "native-doc-1",
            "lineage": _lineage(
                source_sha256=source_sha,
                content=content,
                atoms=[atom],
            ),
        }
    }
    manifest = build_native_docx_provenance_manifest(
        documents={document_id: document},
        document_by_file={"source.docx": document_id},
        stored_chunks=stored,
    )

    snapshot = build_native_observation_snapshot(
        document=document,
        stored_chunks=stored,
        provenance_manifest=manifest,
        runtime_config=_runtime_config(),
        system_version="1.4.0",
        adapter_version=ADAPTER_VERSION,
    )

    edge = next(
        item
        for item in snapshot.provenance_edges
        if item.canonical_object_id == cell_id
    )
    assert edge.physical_cell_footprint[0].v_merge == "none"
    assert edge.physical_cell_footprint[0].merge_origin_physical_cell_id is None


def test_run_result_v2_observes_same_native_stage_items_without_second_execution() -> (
    None
):
    document_id = "doc-trace"
    source_sha = _sha("trace-docx")
    value = "evidence"
    block = _object(
        document_id=document_id,
        source_sha256=source_sha,
        object_id=f"{document_id}:block:00001",
        object_type="block",
        body_ordinal=0,
        value=value,
    )
    document = _document((block,), document_id=document_id, source_sha256=source_sha)
    lineage = _lineage(
        source_sha256=source_sha,
        content=value,
        atoms=[
            _paragraph_atom(
                source_sha256=source_sha,
                body_ordinal=0,
                value=value,
                content=value,
            )
        ],
    )
    stored = {
        "chunk-1": {
            "content": value,
            "file_path": "source.docx",
            "full_doc_id": "native-doc-1",
            "source_span": {"start": 0, "end": len(value)},
            "lineage": lineage,
        }
    }
    manifest = build_native_docx_provenance_manifest(
        documents={document_id: document},
        document_by_file={"source.docx": document_id},
        stored_chunks=stored,
    )
    snapshot = build_native_observation_snapshot(
        document=document,
        stored_chunks=stored,
        provenance_manifest=manifest,
        runtime_config=_runtime_config(),
        system_version="1.4.0",
        adapter_version=ADAPTER_VERSION,
    )
    raw_item = {
        "item_id": "chunk-1",
        "rank": 1,
        "native_id": "chunk-1",
        "document_id": "native-doc-1",
        "file_path": "source.docx",
        "content": value,
        "score": 0.8,
        "source_span": {"start": 0, "end": len(value)},
        "source_sha256": source_sha,
        "lineage_sha256": manifest["runtime_chunks"]["chunk-1"]["lineage_sha256"],
    }
    stages = {
        "raw_retrieval": [dict(raw_item)],
        "ranked_retrieval": [dict(raw_item)],
        "final_context": [dict(raw_item)],
    }
    frozen_stages = json.loads(json.dumps(stages))

    result = build_native_run_result_v2(
        snapshot=snapshot,
        case_id="case-1",
        retrieval_stages=stages,
        final_prompt="prompt",
        answer="answer",
        candidate_cutoff=20,
        ranked_cutoff=20,
        context_cutoff=5,
        generate_answer=True,
    )

    assert stages == frozen_stages
    trace = result.trace
    assert trace.raw_retrieval.observation_status == ObservationStatus.OBSERVED
    assert trace.raw_retrieval.completeness == ObservationCompleteness.COMPLETE
    assert trace.ranked_retrieval.items[0].native_chunk_id == "chunk-1"
    assert trace.final_context.items[0].content == value
    assert trace.prompt_trace.content == "prompt"
    assert trace.answer.content == "answer"
    assert (
        trace.observation_profile.capabilities.transition(
            trace.raw_retrieval.stage, trace.ranked_retrieval.stage
        ).mode
        == StageTransitionMode.IDENTITY_SUBSET
    )
    assert trace.transformations == ()

    structured_config = _runtime_config()
    structured_config["profile"] = "structured"
    structured_config["ranking_strategy"] = "structured"
    structured_config["exact_id_types"] = ["FACT"]
    structured_snapshot = build_native_observation_snapshot(
        document=document,
        stored_chunks=stored,
        provenance_manifest=manifest,
        runtime_config=structured_config,
        system_version="1.4.0",
        adapter_version=ADAPTER_VERSION,
    )
    structured_result = build_native_run_result_v2(
        snapshot=structured_snapshot,
        case_id="case-structured",
        retrieval_stages=stages,
        final_prompt="prompt",
        answer="answer",
        candidate_cutoff=20,
        ranked_cutoff=20,
        context_cutoff=5,
        generate_answer=True,
    )
    assert (
        structured_result.trace.raw_retrieval.completeness
        == ObservationCompleteness.PARTIAL
    )
    assert (
        structured_result.trace.observation_profile.capabilities.transition(
            StageName.CANDIDATE, StageName.RANKED
        ).mode
        == StageTransitionMode.UNOBSERVABLE
    )

    class _AliveServer:
        def poll(self) -> None:
            return None

    adapter = LightRAGAdapter()
    adapter._config = resolve_config({})
    adapter._server = _AliveServer()  # type: ignore[assignment]
    adapter._index_fingerprint = "index-fixture"
    adapter._native_observation_snapshot = snapshot
    adapter._native_observation_reason = "observed"
    adapter._runtime_provenance_by_chunk = dict(manifest["runtime_chunks"])
    adapter._source_by_file = {"source.docx": document_id}
    calls: list[tuple[str, dict[str, object]]] = []

    async def post_json(path: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append((path, payload))
        return {
            "response": "answer",
            "evaluation_trace": {
                "schema_version": "lightrag-evaluation-trace/1",
                "final_prompt": "prompt",
                "retrieval_stages": stages,
            },
        }

    adapter._post_json = post_json  # type: ignore[method-assign]
    legacy = asyncio.run(adapter.query(RAGQuery(case_id="case-1", question="question")))

    assert len(calls) == 1
    assert calls[0][1]["evaluation_trace"] is True
    assert legacy.raw_retrieval is not None
    assert legacy.raw_retrieval[0].native_id == "chunk-1"
    assert legacy.trace is not None
    observed = legacy.trace["wire_v2_native_observation"]
    assert observed["observation_status"] == "observed"
    AdapterRunResultV2.model_validate(observed["adapter_run_result"])
    assert observed["wire_comparison"] == {
        "status": "verified",
        "comparison": "native_id+rank+content+score",
        "stage_item_counts": {
            "raw_retrieval": 1,
            "ranked_retrieval": 1,
            "final_context": 1,
        },
    }
