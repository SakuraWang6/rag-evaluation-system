from __future__ import annotations

from pathlib import Path

import pytest

from rag_eval.contracts.adapter import DocumentInput
from rag_eval_lightrag_adapter.adapter import LightRAGAdapter, resolve_config


@pytest.mark.parametrize(
    "retired_config",
    [
        {"evaluation_corpus": "source_document"},
        {"canonical_segment_max_batch_characters": 512},
        {"benchmark_upload_batch_size": 2},
    ],
)
def test_lightrag_config_rejects_retired_input_route_fields(
    retired_config: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        resolve_config(retired_config)


@pytest.mark.asyncio
async def test_lightrag_ingestion_requires_one_document() -> None:
    adapter = LightRAGAdapter()
    adapter._config = resolve_config({})

    with pytest.raises(ValueError, match="exactly one original DOCX"):
        await adapter._ingest_documents([])


@pytest.mark.asyncio
async def test_lightrag_ingestion_rejects_inline_text() -> None:
    adapter = LightRAGAdapter()
    adapter._config = resolve_config({})
    document = DocumentInput(
        document_id="inline",
        content="retired pre-segmented input",
        mime_type="text/plain",
    )

    with pytest.raises(ValueError, match="source-only DOCX"):
        await adapter._ingest_documents([document])


@pytest.mark.asyncio
async def test_lightrag_ingestion_rejects_non_docx_source() -> None:
    adapter = LightRAGAdapter()
    adapter._config = resolve_config({})
    document = DocumentInput(
        document_id="markdown",
        source_path=Path("source.md").as_posix(),
        mime_type="text/markdown",
    )

    with pytest.raises(ValueError, match="source-only DOCX"):
        await adapter._ingest_documents([document])
