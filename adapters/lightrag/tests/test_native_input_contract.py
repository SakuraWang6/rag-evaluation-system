from __future__ import annotations

import pytest
from pydantic import ValidationError

from rag_eval.contracts.native import OriginalDocumentV2
from rag_eval_lightrag_adapter.adapter import resolve_config


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


def test_lightrag_native_input_contract_rejects_non_docx_source() -> None:
    with pytest.raises(ValidationError, match="original DOCX"):
        OriginalDocumentV2(
            document_id="markdown",
            source_path="source.md",
            source_sha256="a" * 64,
            original_name="source.md",
            canonical_catalog_path="canonical.jsonl",
            canonical_catalog_sha256="b" * 64,
        )
