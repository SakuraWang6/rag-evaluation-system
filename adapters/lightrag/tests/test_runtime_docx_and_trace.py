"""Regression coverage for sealed runtime DOCX ingestion and trace retention."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from rag_eval.contracts.adapter import DocumentInput, PrepareContext, PreparedSystem
from rag_eval.contracts.native import (
    IngestionReceiptV2,
    NativeQueryV2,
    OriginalDocumentV2,
    PreparedSystemV2,
    ResolvedAdapterConfigV2,
)
from rag_eval.contracts.observation import (
    IngestionCatalogObservation,
    ObservationCompleteness,
    ObservationStatus,
    RuntimeChunkRecord,
)
from rag_eval.evaluation import evidence as evidence_module
from rag_eval.evaluation.evidence import CorpusEvidenceIndex
from rag_eval.runs.plans import digest_json
import rag_eval_lightrag_adapter.adapter as adapter_module
from rag_eval_lightrag_adapter.adapter import (
    CAPABILITIES,
    LightRAGAdapter,
    is_loopback_endpoint,
    ollama_model_artifacts,
    resolve_config,
)
from rag_eval_lightrag_adapter.canonical_provenance import (
    build_native_docx_provenance_manifest,
    load_native_docx_document_map,
    native_docx_runtime_chunk_mapping,
)
from rag_eval_lightrag_adapter.native_observation import (
    NativeObservationSnapshot,
    build_prepared_identities,
)


class _AliveServer:
    def poll(self) -> None:
        return None


class _CapturedAsyncResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"models": []}


class _CapturedAsyncClient:
    calls: list[dict[str, object]] = []

    def __init__(self, *_args: object, **kwargs: object) -> None:
        type(self).calls.append(kwargs)

    async def __aenter__(self) -> "_CapturedAsyncClient":
        return self

    async def __aexit__(
        self,
        _exc_type: object,
        _exc: object,
        _traceback: object,
    ) -> None:
        return None

    async def get(self, _url: str) -> _CapturedAsyncResponse:
        return _CapturedAsyncResponse()


def test_loopback_ollama_artifact_lookup_bypasses_ambient_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A local Ollama endpoint must not inherit the developer proxy."""

    _CapturedAsyncClient.calls = []
    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", _CapturedAsyncClient)

    asyncio.run(
        ollama_model_artifacts(
            {
                "llm_binding": "ollama",
                "llm_model": "gemma3:4b",
                "llm_binding_host": "http://127.0.0.1:11434",
            }
        )
    )

    assert _CapturedAsyncClient.calls == [{"timeout": 5.0, "trust_env": False}]
    assert is_loopback_endpoint("http://localhost:11434") is True
    assert is_loopback_endpoint("http://[::1]:11434") is True
    assert is_loopback_endpoint("https://models.example.test") is False


def test_source_only_docx_is_uploaded_from_prepared_runtime_sandbox(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "runtime"
    source_dir.mkdir()
    docx = source_dir / "source" / "fixture.docx"
    docx.parent.mkdir()
    payload = b"PK\x03\x04runtime-docx-fixture"
    docx.write_bytes(payload)
    canonical = source_dir / "canonical-00000.jsonl"
    canonical.write_text('{"document_id":"doc-runtime-fixture"}\n', encoding="utf-8")

    adapter = LightRAGAdapter()

    async def prepare_runtime(context, config):
        adapter._config = resolve_config(config)
        adapter._context = context
        adapter._server = _AliveServer()  # type: ignore[assignment]
        adapter._work_dir = Path(context.work_dir)
        adapter._work_dir.mkdir()
        (adapter._work_dir / "inputs").mkdir()
        (adapter._work_dir / "storage").mkdir()
        return PreparedSystem(
            effective_config=adapter._config.model_dump(mode="json"),
            capabilities=CAPABILITIES,
            system_version="fixture-system",
        )

    adapter._prepare_runtime = prepare_runtime  # type: ignore[method-assign]

    uploaded: list[tuple[str, bytes, str]] = []

    async def post_document(name: str, contents: bytes, mime_type: str) -> dict[str, str]:
        uploaded.append((name, contents, mime_type))
        return {"track_id": "track-1"}

    async def wait_for_ingestion(_track_id: str) -> None:
        return None

    adapter._post_document = post_document  # type: ignore[method-assign]
    adapter._wait_for_ingestion = wait_for_ingestion  # type: ignore[method-assign]

    config: dict[str, object] = {}
    result = asyncio.run(
        adapter.prepare(
            OriginalDocumentV2(
                document_id="doc-runtime-fixture",
                source_path="source/fixture.docx",
                source_sha256=hashlib.sha256(payload).hexdigest(),
                original_name="fixture.docx",
                canonical_catalog_path=canonical.name,
                canonical_catalog_sha256=hashlib.sha256(
                    canonical.read_bytes()
                ).hexdigest(),
            ),
            ResolvedAdapterConfigV2(
                run_id="runtime-docx-regression",
                work_dir=str(tmp_path / "work"),
                source_dir=str(source_dir),
                platform_version="test",
                seed=0,
                repetition=1,
                adapter_config=config,
                adapter_config_digest=digest_json(config),
            ),
        )
    )

    assert result.ingestion_receipt.ingested_documents == 1
    assert uploaded == [
        (
            "source-00000-6e02105e9e80.docx",
            payload,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    ]
    assert adapter._source_text_by_document == {}
    assert adapter._canonical_provenance_by_document == {}


def test_source_only_document_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    source_dir = tmp_path / "runtime"
    source_dir.mkdir()
    docx = source_dir / "source" / "fixture.docx"
    docx.parent.mkdir()
    docx.write_bytes(b"PK\x03\x04runtime-docx-fixture")

    adapter = LightRAGAdapter()
    adapter._context = PrepareContext(
        run_id="runtime-docx-digest-regression",
        work_dir=str(tmp_path / "work"),
        source_dir=str(source_dir),
        platform_version="test",
    )

    with pytest.raises(ValueError, match="checksum"):
        adapter._materialize_document(
            0,
            DocumentInput(
                document_id="doc-runtime-fixture",
                source_path="source/fixture.docx",
                sha256="0" * 64,
                mime_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
            ),
        )


def test_query_retains_native_trace_and_exposes_rendered_prompt() -> None:
    adapter = LightRAGAdapter()
    adapter._config = resolve_config({})
    adapter._server = _AliveServer()  # type: ignore[assignment]
    adapter._index_fingerprint = "index-fixture"
    content = "observed context"
    content_sha = hashlib.sha256(content.encode()).hexdigest()
    original = OriginalDocumentV2(
        document_id="doc-query",
        source_path="source.docx",
        source_sha256="a" * 64,
        original_name="source.docx",
        canonical_catalog_path="canonical.jsonl",
        canonical_catalog_sha256="b" * 64,
    )
    runtime_config = adapter._config.model_dump(mode="json")
    source, runtime, observation = build_prepared_identities(
        document=original,
        runtime_config=runtime_config,
        system_version="fixture-system",
        adapter_version=adapter_module.ADAPTER_VERSION,
    )
    chunk = RuntimeChunkRecord(
        native_document_id="native-doc-query",
        native_chunk_id="chunk-1",
        content_sha256=content_sha,
        content=content,
        parser_identity="fixture-parser",
        chunker_identity="fixture-chunker",
        persisted_metadata_digest="c" * 64,
    )
    adapter._native_observation_snapshot = NativeObservationSnapshot(
        source_identity=source,
        runtime_profile=runtime,
        observation_profile=observation,
        ingestion_catalog=IngestionCatalogObservation(
            observation_status=ObservationStatus.OBSERVED,
            completeness=ObservationCompleteness.COMPLETE,
            items=(chunk,),
        ),
        provenance_edges=(),
        canonical_mapping_records=(),
        mapping_diagnostics=(),
        validation_receipts=(),
        runtime_chunks={chunk.native_chunk_id: chunk},
        legacy_mappings={
            chunk.native_chunk_id: {
                "document_id": original.document_id,
                "native_document_id": chunk.native_document_id,
                "content_sha256": content_sha,
                "source_span": None,
                "canonical_objects": [],
            }
        },
        provenance_edge_ids_by_chunk={chunk.native_chunk_id: ()},
        candidate_completeness=ObservationCompleteness.COMPLETE,
    )
    prepared = PreparedSystemV2.build(
        effective_config=runtime_config,
        source_identity=source,
        runtime_profile=runtime,
        observation_profile=observation,
        ingestion_receipt=IngestionReceiptV2.build(
            document_id=original.document_id,
            source_sha256=original.source_sha256,
            index_fingerprint="index-fixture",
        ),
    )
    adapter._prepared_system = prepared

    async def post_json(_path: str, _payload: dict[str, object]) -> dict[str, object]:
        item = {
            "item_id": chunk.native_chunk_id,
            "native_id": chunk.native_chunk_id,
            "document_id": chunk.native_document_id,
            "rank": 1,
            "content": content,
            "score": 1.0,
            "source_span": None,
        }
        return {
            "response": "answer",
            "evaluation_trace": {
                "schema_version": "lightrag-evaluation-trace/1",
                "final_prompt": "rendered prompt from LightRAG",
                "retrieval_stages": {
                    "raw_retrieval": [dict(item)],
                    "ranked_retrieval": [dict(item)],
                    "final_context": [dict(item)],
                },
            },
        }

    adapter._post_json = post_json  # type: ignore[method-assign]
    result = asyncio.run(
        adapter.query(
            prepared,
            NativeQueryV2(
                case_id="case-1",
                question="What happened?",
                generate_answer=True,
                retrieval_candidate_k=20,
                final_context_k=5,
                max_context_tokens=4096,
                generation_options={},
            ),
        )
    )

    assert result.trace.prompt_trace.content == "rendered prompt from LightRAG"
    assert result.trace.answer.content == "answer"
    assert result.trace.final_context.items[0].content == content
    assert result.telemetry["native_query_executions"] == 1
    assert CAPABILITIES.prompt_trace is True


def test_native_docx_table_is_mapped_only_by_an_exact_unique_grid(
    tmp_path: Path,
) -> None:
    sidecar = tmp_path / "canonical.jsonl"
    records = [
        {
            "document_id": "doc-native-table",
            "object_id": f"doc-native-table:cell:1{row}{column}",
            "object_type": "cell",
            "table_id": "doc-native-table:table:00001",
            "row": row,
            "column": column,
            "canonical_value": value,
            "representation_status": "complete",
            "provenance": {
                "canonicalizer_identity": "rag-eval-authoring-canonicalizer/2"
            },
        }
        for row, values in enumerate((("型号", "用途"), ("S2910", "接入交换机")), start=1)
        for column, value in enumerate(values, start=1)
    ]
    sidecar.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records),
        encoding="utf-8",
    )
    document = load_native_docx_document_map(
        document_id="doc-native-table",
        sidecar_path=sidecar,
        expected_sidecar_sha256=hashlib.sha256(sidecar.read_bytes()).hexdigest(),
    )
    chunks = {
        "native-table": {
            "file_path": "source-00000.docx",
            "source_span": {"start": 40, "end": 130},
            "content": (
                '<table id="runtime-1" format="json">'
                '[["型号", "用途"], ["S2910", "接入交换机"]]</table>'
            ),
            "tokens": 12,
        },
        "different-table": {
            "file_path": "source-00000.docx",
            "source_span": {"start": 131, "end": 200},
            "content": '<table id="runtime-2" format="json">[["型号"]]</table>',
            "tokens": 4,
        },
    }
    manifest = build_native_docx_provenance_manifest(
        documents={"doc-native-table": document},
        document_by_file={"source-00000.docx": "doc-native-table"},
        stored_chunks=chunks,
        allow_historical_fallback=True,
    )

    matched = manifest["runtime_chunks"]["native-table"]
    assert matched["provenance_status"] == "full"
    assert {item["locator"]["column"] for item in matched["canonical_objects"]} == {
        1,
        2,
    }
    assert matched["canonical_objects"][-1]["locator"] == {
        "type": "table_cell",
        "table_id": "doc-native-table:table:00001",
        "row": 2,
        "column": 2,
    }
    assert manifest["runtime_chunks"]["different-table"]["provenance_status"] == "missing"


def _formal_native_fixture(tmp_path: Path) -> tuple[object, str, str, dict[str, object]]:
    source_sha = hashlib.sha256(b"formal-native-docx").hexdigest()
    document_id = "doc-formal-native"
    table = '<table id="runtime-table" format="json">[["A", "B"], ["C", "D"]]</table>'
    table_body = '[["A", "B"], ["C", "D"]]'
    table_start = table.index(table_body)
    cell_records: list[dict[str, object]] = []
    offsets = {"A": table.index('"A"'), "B": table.index('"B"'), "C": table.index('"C"'), "D": table.index('"D"')}
    for row, values in enumerate((("A", "B"), ("C", "D")), start=1):
        for column, value in enumerate(values, start=1):
            cell_records.append(
                {
                    "document_id": document_id,
                    "object_id": f"{document_id}:cell:{row}{column}",
                    "object_type": "cell",
                    "canonicalizer": "rag-eval-authoring-canonicalizer/5",
                    "source_sha256": source_sha,
                    "canonical_value": value,
                    "status": "supported",
                    "table_id": f"{document_id}:table:00001",
                    "row": row,
                    "column": column,
                    "structural_locator": {
                        "part": "word/document.xml",
                        "body_ordinal": 1,
                        "table_id": f"{document_id}:table:00001",
                        "row": row,
                        "column": column,
                    },
                }
            )
    records: list[dict[str, object]] = [
        {
            "document_id": document_id,
            "object_id": f"{document_id}:block:00001",
            "object_type": "block",
            "canonicalizer": "rag-eval-authoring-canonicalizer/5",
            "source_sha256": source_sha,
            "canonical_value": "Repeated",
            "status": "supported",
            "structural_locator": {
                "part": "word/document.xml",
                "body_ordinal": 0,
            },
        },
        {
            "document_id": document_id,
            "object_id": f"{document_id}:table:00001",
            "object_type": "table",
            "canonicalizer": "rag-eval-authoring-canonicalizer/5",
            "source_sha256": source_sha,
            "canonical_value": "A | B\nC | D",
            "status": "supported",
            "structural_locator": {
                "part": "word/document.xml",
                "body_ordinal": 1,
                "nested": False,
            },
        },
        *cell_records,
    ]
    sidecar = tmp_path / "formal.jsonl"
    sidecar.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records),
        encoding="utf-8",
    )
    document = load_native_docx_document_map(
        document_id=document_id,
        sidecar_path=sidecar,
        expected_sidecar_sha256=hashlib.sha256(sidecar.read_bytes()).hexdigest(),
    )
    cell_spans = [
        {"start": offsets[value], "end": offsets[value] + 3}
        for value in ("A", "B", "C", "D")
    ]
    lineage = {
        "schema_version": "lightrag-native-docx-lineage/1",
        "source_sha256": source_sha,
        "parsed_content_sha256": hashlib.sha256(table.encode()).hexdigest(),
        "parsed_content_length": len(table),
        "atoms": [
            {
                "kind": "table",
                "source_sha256": source_sha,
                "source_value": "A | B\nC | D",
                "source_value_sha256": hashlib.sha256(
                    "A | B C | D".encode()
                ).hexdigest(),
                "coverage_status": "partial",
                "source_locator": {
                    "part": "word/document.xml",
                    "body_ordinal": 1,
                    "nested": False,
                },
                "parsed_span": {"start": 0, "end": len(table)},
                "cells": [
                    {
                        "source_sha256": source_sha,
                        "source_value": value,
                        "source_value_sha256": hashlib.sha256(value.encode()).hexdigest(),
                        "coverage_status": "complete",
                        "source_locator": {
                            "part": "word/document.xml",
                            "body_ordinal": 1,
                            "row": row,
                            "column": column,
                            "table_id": "runtime-table",
                        },
                        "parsed_span": cell_span,
                    }
                    for (row, column), value, cell_span in zip(
                        ((1, 1), (1, 2), (2, 1), (2, 2)),
                        ("A", "B", "C", "D"),
                        cell_spans,
                    )
                ],
            }
        ],
    }
    return document, source_sha, table, lineage


def test_formal_native_lineage_maps_partial_table_parent_and_full_cells(
    tmp_path: Path,
) -> None:
    document, source_sha, table, lineage = _formal_native_fixture(tmp_path)
    mapping = native_docx_runtime_chunk_mapping(
        chunk_id="chunk-table-row-piece",
        document=document,
        content=table,
        source_span={"start": 100, "end": 100 + len(table)},
        lineage=lineage,
        source_sha256=source_sha,
    )

    assert mapping["mapping_mode"] == "native_docx_lineage"
    assert mapping["provenance_status"] == "partial"
    # Only proof-bearing edges enter the formal forward map.  The partial
    # table envelope stays available under diagnostics while its complete
    # physical cells remain usable proof edges.
    assert len(mapping["canonical_edges"]) == 4
    table_edge = next(edge for edge in mapping["diagnostic_edges"] if edge["object_type"] == "table")
    cell_edges = [edge for edge in mapping["canonical_edges"] if edge["object_type"] == "cell"]
    assert table_edge["coverage"] == "partial"
    assert {edge["coverage"] for edge in cell_edges} == {"full"}
    assert all(edge["overlap_span"] is not None for edge in cell_edges)


def test_native_manifest_catalog_round_trip_uses_typed_locator_and_normalized_witness(
    tmp_path: Path,
) -> None:
    """Full-width values must use one witness domain in all map directions."""

    source_sha = hashlib.sha256(b"fullwidth-native-docx").hexdigest()
    document_id = "doc-fullwidth-native"
    table_id = f"{document_id}:table:00001"
    cell_id = f"{document_id}:cell:11"
    value = "报告编号：A"
    table = (
        '<table id="runtime-table" format="json">'
        + json.dumps([[value]], ensure_ascii=False, separators=(",", ":"))
        + "</table>"
    )
    value_start = table.index(json.dumps(value, ensure_ascii=False))
    value_end = value_start + len(json.dumps(value, ensure_ascii=False))
    normalized_hash = hashlib.sha256("报告编号:A".encode()).hexdigest()
    records = [
        {
            "document_id": document_id,
            "object_id": table_id,
            "object_type": "table",
            "canonicalizer": "rag-eval-authoring-canonicalizer/5",
            "source_sha256": source_sha,
            "canonical_value": value,
            "status": "supported",
            "structural_locator": {
                "part": "word/document.xml",
                "body_ordinal": 1,
                "nested": False,
            },
        },
        {
            "document_id": document_id,
            "object_id": cell_id,
            "object_type": "cell",
            "canonicalizer": "rag-eval-authoring-canonicalizer/5",
            "source_sha256": source_sha,
            "canonical_value": value,
            "status": "supported",
            "table_id": table_id,
            "row": 1,
            "column": 1,
            "structural_locator": {
                "part": "word/document.xml",
                "body_ordinal": 1,
                "table_id": table_id,
                "row": 1,
                "column": 1,
            },
        },
    ]
    sidecar = tmp_path / "fullwidth.jsonl"
    sidecar.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records),
        encoding="utf-8",
    )
    document = load_native_docx_document_map(
        document_id=document_id,
        sidecar_path=sidecar,
        expected_sidecar_sha256=hashlib.sha256(sidecar.read_bytes()).hexdigest(),
    )
    lineage = {
        "schema_version": "lightrag-native-docx-lineage/1",
        "source_sha256": source_sha,
        "parsed_content_sha256": hashlib.sha256(table.encode()).hexdigest(),
        "parsed_content_length": len(table),
        "atoms": [
            {
                "kind": "table",
                "source_sha256": source_sha,
                "source_value": value,
                "source_value_sha256": normalized_hash,
                "coverage_status": "complete",
                "source_locator": {
                    "part": "word/document.xml",
                    "body_ordinal": 1,
                    "nested": False,
                },
                "parsed_span": {"start": 0, "end": len(table)},
                "cells": [
                    {
                        "source_sha256": source_sha,
                        "source_value": value,
                        "source_value_sha256": normalized_hash,
                        "coverage_status": "complete",
                        "source_locator": {
                            "part": "word/document.xml",
                            "body_ordinal": 1,
                            "table_id": table_id,
                            "row": 1,
                            "column": 1,
                        },
                        "parsed_span": {"start": value_start, "end": value_end},
                    }
                ],
            }
        ],
    }
    manifest = build_native_docx_provenance_manifest(
        documents={document_id: document},
        document_by_file={"source-00000.docx": document_id},
        stored_chunks={
            "native-fullwidth": {
                "file_path": "source-00000.docx",
                "content": table,
                "lineage": lineage,
                "source_span": {"start": 0, "end": len(table)},
            }
        },
    )

    index = CorpusEvidenceIndex.from_provenance_map(
        manifest,
        documents={document_id: "canonical source view"},
        runtime_documents={document_id: table},
        source_digests={document_id: source_sha},
        expected_map_digest=evidence_module._mapping_digest(manifest),
    )

    assert index.catalog_verified is True
    assert index.map_digest_verified is True
    assert index.source_pins_verified is True
    assert index._catalog_round_trip_ok is True
    edge = manifest["runtime_chunks"]["native-fullwidth"]["canonical_edges"][1]
    catalog = manifest["object_catalog"][cell_id]
    assert edge["witness_sha256"] == normalized_hash
    assert catalog["witness_sha256"] == normalized_hash
    assert edge["locator"] == catalog["locator"] == {
        "type": "table_cell",
        "table_id": table_id,
        "row": 1,
        "column": 1,
    }
    assert edge["source_locator"] == catalog["source_locator"]
    assert edge["expected_extent"]["status"] == "complete"
    assert catalog["mapping_status"] == "complete"


def test_formal_native_lineage_rejects_witness_mismatch_and_duplicate_locator(
    tmp_path: Path,
) -> None:
    document, source_sha, table, lineage = _formal_native_fixture(tmp_path)
    bad_lineage = json.loads(json.dumps(lineage))
    bad_lineage["atoms"][0]["cells"][0]["source_value"] = "wrong"
    bad = native_docx_runtime_chunk_mapping(
        chunk_id="bad-witness",
        document=document,
        content=table,
        source_span=None,
        lineage=bad_lineage,
        source_sha256=source_sha,
    )
    # The bad cell is excluded, but unrelated structurally verified edges in
    # the same runtime chunk remain available as partial provenance.
    assert bad["provenance_status"] == "partial"
    assert bad["reason"] == "native_source_value_witness_mismatch"
    assert len(bad["canonical_edges"]) == 3
    assert any(
        edge["object_type"] == "table" for edge in bad["diagnostic_edges"]
    )
    assert all(
        edge["object_id"] != f"{document.document_id}:cell:11"
        for edge in bad["canonical_edges"]
    )

    duplicate_document = replace(
        document,
        objects=document.objects + (document.objects[-1],),
    )
    ambiguous = native_docx_runtime_chunk_mapping(
        chunk_id="duplicate-locator",
        document=duplicate_document,
        content=table,
        source_span=None,
        lineage=lineage,
        source_sha256=source_sha,
    )
    assert ambiguous["provenance_status"] == "partial"
    assert ambiguous["reason"] == "ambiguous_native_structural_locator"
    assert len(ambiguous["canonical_edges"]) == 4


def test_native_grid_is_explicitly_historical_only(tmp_path: Path) -> None:
    document, _source_sha, table, _lineage = _formal_native_fixture(tmp_path)
    default_mapping = native_docx_runtime_chunk_mapping(
        chunk_id="no-fallback",
        document=document,
        content=table,
        source_span={"start": 0, "end": len(table)},
    )
    assert default_mapping["reason"] == "native_lineage_missing"


def test_adapter_keeps_one_item_for_many_native_edges(tmp_path: Path) -> None:
    document, source_sha, table, lineage = _formal_native_fixture(tmp_path)
    mapping = native_docx_runtime_chunk_mapping(
        chunk_id="chunk-table-row-piece",
        document=document,
        content=table,
        source_span={"start": 100, "end": 100 + len(table)},
        lineage=lineage,
        source_sha256=source_sha,
    )
    adapter = LightRAGAdapter()
    # LightRAG's runtime/full-doc id is deliberately distinct from the
    # canonical document id.  The manifest pins the association explicitly;
    # the adapter must not rewrite or accept an unrelated filename match.
    mapping["native_document_id"] = "doc-native-runtime"
    adapter._runtime_provenance_by_chunk = {"chunk-table-row-piece": mapping}
    adapter._source_by_file = {"source-00000.docx": "doc-formal-native"}
    adapter._provenance_map_digest = "m" * 64
    result = adapter._evidence_items(
        [
            {
                "item_id": "ranked-item",
                "content": table,
                "native_id": "chunk-table-row-piece",
                "file_path": "source-00000.docx",
                "document_id": "doc-native-runtime",
                "source_span": {"start": 100, "end": 100 + len(table)},
                "score": 0.9,
                "lineage_sha256": mapping["lineage_sha256"],
                "source_sha256": source_sha,
            }
        ],
        "ranked",
    )

    assert len(result) == 1
    assert result[0].item_id == "ranked:ranked-item"
    assert result[0].locator is None
    assert result[0].metadata["canonical_edge_count"] == 4
    assert len(result[0].metadata["canonical_edges"]) == 4
    assert result[0].metadata["runtime_document_id"] == "doc-native-runtime"
    assert result[0].metadata["runtime_source_span"] == {
        "start": 100,
        "end": 100 + len(table),
    }


def test_native_edge_never_clamps_an_out_of_bounds_span_to_full(
    tmp_path: Path,
) -> None:
    document, source_sha, table, lineage = _formal_native_fixture(tmp_path)
    bad_lineage = json.loads(json.dumps(lineage))
    bad_lineage["atoms"][0]["cells"][0]["parsed_span"]["end"] = len(table) + 1
    mapping = native_docx_runtime_chunk_mapping(
        chunk_id="out-of-bounds",
        document=document,
        content=table,
        source_span={"start": 100, "end": 100 + len(table)},
        lineage=bad_lineage,
        source_sha256=source_sha,
    )

    cell_edge = next(
        edge
        for edge in mapping["diagnostic_edges"]
        if edge["object_type"] == "cell"
        and edge["locator"]["row"] == 1
        and edge["locator"]["column"] == 1
    )
    assert cell_edge["coverage"] == "partial"
    assert cell_edge["mapping_status"] == "partial"
    assert cell_edge["overlap_span"] is None
    assert cell_edge["reason"] == "runtime_parsed_span_out_of_bounds"
