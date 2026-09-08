from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag_eval.api import create_app
from rag_eval.service import PlatformService
from rag_eval.storage.layout import PlatformPaths

CONTRACT = (
    Path(__file__).resolve().parents[3] / "contracts" / "webui-critical-api.json"
)


def _resolved_schema(openapi: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    reference = schema.get("$ref")
    if not isinstance(reference, str):
        return schema
    prefix = "#/components/schemas/"
    assert reference.startswith(prefix)
    return openapi["components"]["schemas"][reference.removeprefix(prefix)]


def test_critical_webui_operations_match_platform_openapi(tmp_path: Path) -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema_version"] == 1
    operations = contract["operations"]
    ids = [item["id"] for item in operations]
    assert len(ids) == len(set(ids))

    openapi = create_app(
        PlatformService(PlatformPaths(tmp_path / "platform")),
        start_supervisor=False,
    ).openapi()
    for expected in operations:
        route = openapi["paths"].get(expected["server_path"])
        assert route is not None, expected["id"]
        operation = route.get(expected["method"].lower())
        assert operation is not None, expected["id"]
        response = operation["responses"].get(expected["success_status"])
        assert response is not None, expected["id"]
        response_schema = _resolved_schema(
            openapi, response["content"]["application/json"]["schema"]
        )
        assert response_schema["type"] == expected["response_type"], expected["id"]

        request_schema = expected.get("request_schema")
        if request_schema is not None:
            observed = operation["requestBody"]["content"]["application/json"][
                "schema"
            ]["$ref"]
            assert observed == f"#/components/schemas/{request_schema}", expected["id"]
