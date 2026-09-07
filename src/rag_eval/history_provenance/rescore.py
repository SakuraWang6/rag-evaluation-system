"""Offline, versioned re-scoring of retained historical RAG cases.

The historical recovery map is loaded once and passed to the platform's
production ``evaluate_case`` implementation.  This module only reads the
original run, the pinned derived map, and the retained case artifacts; all
outputs are written through the append-only derivative writers in
``reconstruction``.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from rag_eval.contracts.adapter import RAGResult
from rag_eval.contracts.dataset import GoldAnswer, GoldEvidenceSet
from rag_eval.contracts.run import CaseResult, MetricResult
from rag_eval.evaluation.evidence import CorpusEvidenceIndex

from .baseline import verify_immutable_baseline
from .reconstruction import (
    _canonical_path,
    _case_paths,
    _source_docx,
    _sha256_text,
    attach_runtime_provenance,
    write_derived_json,
    write_derived_text,
)


RESCORE_SCHEMA_VERSION = "historical-rescore/1"
RESCORE_ACCEPTANCE_SCHEMA_VERSION = "historical-rescore-acceptance/1"
_METRIC_FIELDS = (
    "status",
    "value",
    "numerator",
    "denominator",
    "scorer_id",
    "scorer_version",
    "scorer_digest",
    "evaluator_mode",
    "reason",
)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _json_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _canonical_jsonl_digest(path: Path) -> str:
    """Digest canonical JSONL records using the map's logical convention."""

    records: list[Any] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"canonical JSONL is malformed at line {line_number}: {path}"
                ) from exc
    return _json_digest(records)


def _assert_outside(run: Path, path: Path) -> None:
    resolved = path.resolve(strict=False)
    if resolved == run or run in resolved.parents:
        raise ValueError(f"historical rescore input must be outside source run: {resolved}")


def _metric_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, MetricResult):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _metric_changes(
    before_values: Sequence[Any],
    after_values: Sequence[Any],
) -> list[dict[str, Any]]:
    before = {
        str(item.get("metric_id")): _metric_dict(item)
        for item in before_values
        if isinstance(item, Mapping) and isinstance(item.get("metric_id"), str)
    }
    after = {
        str(item.get("metric_id")): _metric_dict(item)
        for item in after_values
        if isinstance(item, Mapping) and isinstance(item.get("metric_id"), str)
    }
    changes: list[dict[str, Any]] = []
    for metric_id in sorted(set(before) | set(after)):
        old = before.get(metric_id)
        new = after.get(metric_id)
        if old is None:
            changed_fields = ["metric_added"]
            explanation = "new metric emitted by the pinned production evaluator"
        elif new is None:
            changed_fields = ["metric_removed"]
            explanation = "metric is not emitted by the pinned production evaluator"
        else:
            changed_fields = [
                field for field in _METRIC_FIELDS if old.get(field) != new.get(field)
            ]
            if not changed_fields:
                explanation = "unchanged under the pinned production evaluator"
            else:
                pieces: list[str] = []
                if "status" in changed_fields:
                    pieces.append(f"status {old.get('status')} -> {new.get('status')}")
                if "value" in changed_fields:
                    pieces.append(f"value {old.get('value')} -> {new.get('value')}")
                if "numerator" in changed_fields or "denominator" in changed_fields:
                    pieces.append(
                        "numerator/denominator "
                        f"({old.get('numerator')}/{old.get('denominator')}) -> "
                        f"({new.get('numerator')}/{new.get('denominator')})"
                    )
                if "scorer_digest" in changed_fields:
                    pieces.append("scorer identity changed")
                if "reason" in changed_fields and new.get("reason"):
                    pieces.append(f"reason: {new.get('reason')}")
                explanation = "; ".join(pieces) or "metric fields changed"
        changes.append(
            {
                "metric_id": metric_id,
                "changed": bool(changed_fields),
                "changed_fields": changed_fields,
                "before": old,
                "after": new,
                "explanation": explanation,
            }
        )
    return changes


def _localization_summary(
    case_outputs: Sequence[Mapping[str, Any]],
    matrix: Mapping[str, Any] | None,
    after_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Expose matrix micro-counts beside production selected-path means.

    ``aggregate_metrics`` intentionally averages one case at a time, so its
    localization value is a macro case mean.  The matrix is a separate
    19-Gold diagnostic.  Keeping both views explicit prevents a reader from
    treating either denominator as the other's.
    """

    matrix_by_stage: dict[str, dict[str, int]] = {}
    if isinstance(matrix, Mapping):
        for stage in ("raw_retrieval", "ranked_retrieval", "final_context"):
            counts: Counter[str] = Counter()
            for row in matrix.get("rows", []):
                if not isinstance(row, Mapping):
                    continue
                decision = (row.get("stages") or {}).get(stage)
                if isinstance(decision, Mapping):
                    counts[str(decision.get("status"))] += 1
            matrix_by_stage[stage] = {
                status: int(counts.get(status, 0))
                for status in (
                    "matched",
                    "partial",
                    "retrieval_missed",
                    "provenance_missing",
                )
            }
            matrix_by_stage[stage]["denominator"] = sum(counts.values())

    selected_path: dict[str, dict[str, Any]] = {}
    after_metrics = after_summary.get("metrics", {}) if isinstance(after_summary, Mapping) else {}
    for stage in ("raw", "ranked", "context"):
        counts: dict[str, float] = {
            status: 0.0
            for status in (
                "matched",
                "partial",
                "retrieval_missed",
                "provenance_missing",
            )
        }
        denominator = 0.0
        for case in case_outputs:
            metrics = case.get("metrics_after", [])
            per_case_denominator: float | None = None
            for metric in metrics:
                if not isinstance(metric, Mapping):
                    continue
                metric_id = str(metric.get("metric_id", ""))
                prefix = f"{stage}_localization_"
                if not metric_id.startswith(prefix):
                    continue
                raw_denominator = metric.get("denominator")
                if isinstance(raw_denominator, (int, float)):
                    per_case_denominator = float(raw_denominator)
                status = metric_id.removeprefix(prefix)
                raw_numerator = metric.get("numerator")
                if status in counts and isinstance(raw_numerator, (int, float)):
                    counts[status] += float(raw_numerator)
            if per_case_denominator is not None:
                denominator += per_case_denominator
        case_mean = {
            status: (
                after_metrics.get(f"{stage}_localization_{status}", {}).get("value")
                if isinstance(after_metrics.get(f"{stage}_localization_{status}"), Mapping)
                else None
            )
            for status in counts
        }
        selected_path[stage] = {
            **{
                status: int(value) if float(value).is_integer() else value
                for status, value in counts.items()
            },
            "denominator": int(denominator) if denominator.is_integer() else denominator,
            "case_mean": case_mean,
        }
    return {
        "matrix_19_gold_x_3_stages": {
            "decision_count": int((matrix or {}).get("decision_count", 0))
            if isinstance(matrix, Mapping)
            else 0,
            "status_counts": (matrix or {}).get("status_counts", {})
            if isinstance(matrix, Mapping)
            else {},
            "by_stage": matrix_by_stage,
        },
        "production_selected_path_clauses": {
            "description": "Micro clause counts from production evaluate_case; the after_summary values are macro case means.",
            "by_stage": selected_path,
        },
    }


def _attach_result_provenance(
    raw_result: Mapping[str, Any],
    reconstruction: Mapping[str, Any],
) -> RAGResult:
    enriched = dict(raw_result)
    for stage in ("raw_retrieval", "ranked_retrieval", "final_context"):
        values = raw_result.get(stage)
        if values is None:
            enriched[stage] = None
            continue
        if not isinstance(values, list):
            raise ValueError(f"case result stage is not a list: {stage}")
        enriched[stage] = [
            attach_runtime_provenance(item, reconstruction)
            for item in values
            if isinstance(item, Mapping)
        ]
        if len(enriched[stage]) != len(values):
            raise ValueError(f"case result stage contains a non-object item: {stage}")
    return RAGResult.model_validate(enriched)


def _case_title(case_id: str) -> str:
    return case_id.removeprefix("pilot-case-").replace("-", " ")


def _source_pin(run: Path, map_payload: Mapping[str, Any]) -> dict[str, Any]:
    source = _source_docx(run)
    canonical = _canonical_path(run)
    source_sha = _sha256_file(source)
    canonical_sha = _sha256_file(canonical)
    history = map_payload.get("history_reconstruction", {})
    documents = map_payload.get("documents", {})
    if not isinstance(documents, Mapping) or len(documents) != 1:
        raise ValueError("historical rescore requires exactly one mapped source document")
    document_id, document = next(iter(documents.items()))
    if not isinstance(document_id, str) or not isinstance(document, Mapping):
        raise ValueError("historical map has malformed source document record")
    mapped_source_sha = document.get("source_sha256")
    if mapped_source_sha != source_sha:
        raise ValueError("source DOCX digest does not match the pinned provenance map")
    mapped_canonical = history.get("canonical_source_sha256") if isinstance(history, Mapping) else None
    # ``canonical_source_sha256`` names the source bytes represented by the
    # JSONL, whereas ``canonical_digest`` is the logical digest of its
    # records.  They are intentionally different pins.
    if isinstance(mapped_canonical, list) and mapped_canonical and source_sha not in mapped_canonical:
        raise ValueError("canonical source digest does not match the pinned provenance map")
    mapped_canonical_digest = document.get("canonical_digest") or (
        history.get("canonical_digest") if isinstance(history, Mapping) else None
    )
    actual_canonical_digest = _canonical_jsonl_digest(canonical)
    if isinstance(mapped_canonical_digest, str) and mapped_canonical_digest != actual_canonical_digest:
        raise ValueError("canonical JSONL logical digest does not match the pinned provenance map")
    return {
        "document_id": document_id,
        "source_docx": {"path": str(source), "sha256": source_sha},
        "canonical_jsonl": {"path": str(canonical), "sha256": canonical_sha},
        "mapped_source_sha256": mapped_source_sha,
        "canonical_source_sha256": mapped_canonical,
        "canonical_logical_sha256": actual_canonical_digest,
        "mapped_canonical_logical_sha256": mapped_canonical_digest,
    }


def _map_pin(
    run: Path,
    map_path: Path,
    map_acceptance_path: Path | None,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    _assert_outside(run, map_path)
    if not map_path.is_file():
        raise FileNotFoundError(map_path)
    map_file_sha = _sha256_file(map_path)
    map_digest = payload.get("map_digest") or payload.get("canonical_provenance_map_digest")
    if not isinstance(map_digest, str) or not map_digest:
        raise ValueError("historical map has no externalizable map_digest")
    if map_acceptance_path is None:
        raise ValueError("strict historical rescore requires the map acceptance pin")
    _assert_outside(run, map_acceptance_path)
    acceptance = _load_json(map_acceptance_path)
    if not isinstance(acceptance, Mapping):
        raise ValueError("map acceptance artifact is malformed")
    expected_map = acceptance.get("map", {})
    if not isinstance(expected_map, Mapping):
        raise ValueError("map acceptance artifact has no map pin")
    if expected_map.get("file_sha256") != map_file_sha:
        raise ValueError("map file digest does not match its acceptance pin")
    if expected_map.get("logical_map_sha256") != map_digest:
        raise ValueError("map logical digest does not match its acceptance pin")
    return {
        "path": str(map_path),
        "file_sha256": map_file_sha,
        "logical_map_sha256": map_digest,
        "acceptance_path": str(map_acceptance_path),
        "acceptance_file_sha256": _sha256_file(map_acceptance_path),
        "acceptance_status": acceptance.get("status"),
        "acceptance_implementation_source_sha256": acceptance.get(
            "implementation_source_sha256", {}
        ),
    }


def _matrix_pin(
    run: Path,
    matrix_path: Path | None,
    map_digest: str,
) -> dict[str, Any] | None:
    if matrix_path is None:
        return None
    _assert_outside(run, matrix_path)
    if not matrix_path.is_file():
        raise FileNotFoundError(matrix_path)
    value = _load_json(matrix_path)
    if not isinstance(value, Mapping):
        raise ValueError("matrix artifact is malformed")
    if value.get("source_map_sha256") != map_digest:
        raise ValueError("matrix is not derived from the pinned provenance map")
    if value.get("evidence_item_count") != 19 or value.get("decision_count") != 57:
        raise ValueError("matrix does not contain the required 19 x 3 decisions")
    return {
        "path": str(matrix_path),
        "file_sha256": _sha256_file(matrix_path),
        "evidence_item_count": value.get("evidence_item_count"),
        "decision_count": value.get("decision_count"),
        "status_counts": value.get("status_counts"),
        "rows": value.get("rows", []),
    }


def _implementation_sources() -> dict[str, str]:
    import rag_eval.evaluation.answers as answers_module
    import rag_eval.evaluation.engine as engine_module
    import rag_eval.evaluation.evidence as evidence_module
    import rag_eval.evaluation.metrics as metrics_module
    import rag_eval.execution as execution_module

    modules = {
        "history_provenance.rescore": Path(__file__),
        "history_provenance.reconstruction": Path(__file__).with_name("reconstruction.py"),
        "history_provenance.baseline": Path(__file__).with_name("baseline.py"),
        "evaluation.answers": Path(answers_module.__file__),
        "evaluation.engine": Path(engine_module.__file__),
        "evaluation.evidence": Path(evidence_module.__file__),
        "evaluation.metrics": Path(metrics_module.__file__),
        "execution.aggregate_metrics": Path(execution_module.__file__),
    }
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "rescore_historical_run.py"
    modules["history_provenance.rescore_cli"] = script_path
    return {
        name: _sha256_file(path.resolve(strict=True))
        for name, path in modules.items()
    }


def rescore_historical_run(
    run_dir: str | Path,
    map_path: str | Path,
    *,
    map_acceptance_path: str | Path | None,
    matrix_path: str | Path | None = None,
    baseline_path: str | Path | None = None,
    k_values: Sequence[int] = (1, 3, 5),
) -> dict[str, Any]:
    """Re-score retained cases through production ``evaluate_case`` once.

    The function requires an externally pinned map acceptance artifact.  It
    never trusts a digest copied solely from the map itself and never mutates
    any input path.
    """

    run = Path(run_dir).resolve(strict=True)
    if not run.is_dir():
        raise NotADirectoryError(run)
    map_file = Path(map_path).resolve(strict=True)
    map_acceptance = (
        Path(map_acceptance_path).resolve(strict=True)
        if map_acceptance_path is not None
        else None
    )
    matrix_file = Path(matrix_path).resolve(strict=True) if matrix_path is not None else None
    payload = _load_json(map_file)
    if not isinstance(payload, Mapping):
        raise ValueError("historical provenance map must be a JSON object")
    map_pin = _map_pin(run, map_file, map_acceptance, payload)
    source_pin = _source_pin(run, payload)
    document_id = source_pin["document_id"]
    runtime_documents = payload.get("runtime_documents", {})
    full_doc_id = payload.get("history_reconstruction", {}).get("full_doc_id") if isinstance(payload.get("history_reconstruction"), Mapping) else None
    runtime_text = runtime_documents.get(document_id) if isinstance(runtime_documents, Mapping) else None
    if not isinstance(runtime_text, str) and isinstance(full_doc_id, str) and isinstance(runtime_documents, Mapping):
        runtime_text = runtime_documents.get(full_doc_id)
    if not isinstance(runtime_text, str):
        raise ValueError("historical provenance map has no runtime execution stream")
    corpus = CorpusEvidenceIndex.from_provenance_map(
        payload,
        expected_map_digest=map_pin["logical_map_sha256"],
        source_digests={document_id: source_pin["source_docx"]["sha256"]},
        runtime_documents={document_id: runtime_text},
    )
    if not corpus.map_digest_verified or not corpus.source_pins_verified or not corpus.catalog_verified:
        raise ValueError(
            "pinned historical provenance catalog did not verify "
            f"(map={corpus.map_digest_verified}, source={corpus.source_pins_verified}, catalog={corpus.catalog_verified})"
        )
    matrix_pin = _matrix_pin(run, matrix_file, map_pin["logical_map_sha256"])
    matrix_rows = {
        (str(row.get("case_id")), str(row.get("evidence_id"))): row
        for row in (matrix_pin or {}).get("rows", [])
        if isinstance(row, Mapping)
    }
    raw_experiment_path = run / "experiment.json"
    raw_experiment = _load_json(raw_experiment_path) if raw_experiment_path.is_file() else {}
    configured_k_values = raw_experiment.get("metric_config", {}).get("k_values") if isinstance(raw_experiment, Mapping) else None
    selected_k = tuple(sorted({int(value) for value in (configured_k_values or k_values)}))
    if not selected_k or any(value < 1 for value in selected_k):
        raise ValueError("rescore k_values must contain positive integers")

    case_paths = _case_paths(run)
    if not case_paths:
        raise ValueError("historical run has no case artifacts")
    case_hashes = {
        str(path.relative_to(run)): _sha256_file(path)
        for path in case_paths
    }
    case_manifest_digest = _json_digest(
        [{"path": path, "sha256": case_hashes[path]} for path in sorted(case_hashes)]
    )
    before_summary_path = run / "summary.json"
    before_summary = _load_json(before_summary_path) if before_summary_path.is_file() else None
    case_outputs: list[dict[str, Any]] = []
    after_case_results: list[CaseResult] = []
    for path in case_paths:
        raw_case = _load_json(path)
        if not isinstance(raw_case, Mapping):
            raise ValueError(f"case artifact is malformed: {path.name}")
        case_id = raw_case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"case artifact has no case_id: {path.name}")
        if raw_case.get("status") != "completed":
            raise ValueError(f"historical rescore requires completed case: {case_id}")
        raw_result = raw_case.get("rag_result")
        if not isinstance(raw_result, Mapping):
            raise ValueError(f"completed case has no RAG result: {case_id}")
        result = _attach_result_provenance(raw_result, payload)
        gold_answer = GoldAnswer.model_validate(raw_case.get("gold_answer"))
        evidence_set = GoldEvidenceSet.model_validate(raw_case.get("gold_evidence_set"))
        from rag_eval.evaluation.engine import evaluate_case

        after_metrics = evaluate_case(
            result,
            gold_answer,
            evidence_set,
            corpus,
            k_values=selected_k,
            evaluate_answer=True,
        )
        before_values = raw_case.get("metrics", [])
        if not isinstance(before_values, list):
            raise ValueError(f"case metrics are malformed: {case_id}")
        after_values = [metric.model_dump(mode="json") for metric in after_metrics]
        changes = _metric_changes(before_values, after_values)
        case_matrix_rows = [
            value
            for (row_case, _row_evidence), value in matrix_rows.items()
            if row_case == case_id and isinstance(value, Mapping)
        ]
        case_matrix_rows.sort(key=lambda value: str(value.get("evidence_id", "")))
        try:
            parsed_case = CaseResult.model_validate(raw_case)
            after_case_results.append(parsed_case.model_copy(update={"metrics": after_metrics}))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"case cannot be represented for aggregate summary: {case_id}") from exc
        case_outputs.append(
            {
                "case_id": case_id,
                "title": _case_title(case_id),
                "question": raw_case.get("question"),
                "repetition": raw_case.get("repetition"),
                "seed": raw_case.get("seed"),
                "case_artifact": {
                    "path": str(path),
                    "sha256": case_hashes[str(path.relative_to(run))],
                },
                "answer_sha256": _sha256_text(result.answer or ""),
                "gold_evidence_count": len(evidence_set.evidence),
                "required_group_count": len(evidence_set.required_groups),
                "mses_path_count": len(evidence_set.mses_paths or [evidence_set.required_groups]),
                "stage_localization": [
                    {
                        "evidence_id": value.get("evidence_id"),
                        "object_id": value.get("object_id"),
                        "object_type": value.get("object_type"),
                        "locator": value.get("locator"),
                        "source_coordinates": value.get("source_coordinates", {}),
                        "expected_extent": value.get("expected_extent", {}),
                        "stages": value.get("stages", {}),
                    }
                    for value in case_matrix_rows
                ],
                "metrics_before": before_values,
                "metrics_after": after_values,
                "metric_changes": changes,
            }
        )

    from rag_eval.execution import aggregate_metrics

    repetitions = max(int(item.get("repetition") or 1) for item in case_outputs)
    after_summary = aggregate_metrics(
        after_case_results,
        repetitions=repetitions,
        expected=len(case_outputs),
    )
    baseline_result = None
    if baseline_path is not None:
        baseline_result = verify_immutable_baseline(run, baseline_path).as_dict()
    change_summary: dict[str, dict[str, int]] = {}
    for case in case_outputs:
        for change in case["metric_changes"]:
            metric_id = str(change["metric_id"])
            bucket = change_summary.setdefault(
                metric_id,
                {"changed": 0, "unchanged": 0, "added": 0, "removed": 0},
            )
            if change["changed"]:
                bucket["changed"] += 1
            else:
                bucket["unchanged"] += 1
            if "metric_added" in change["changed_fields"]:
                bucket["added"] += 1
            if "metric_removed" in change["changed_fields"]:
                bucket["removed"] += 1
    implementation_sources = _implementation_sources()
    pinned_sources = map_pin.get("acceptance_implementation_source_sha256", {})
    source_drift_rows = []
    if isinstance(pinned_sources, Mapping):
        for name in sorted(set(pinned_sources) & set(implementation_sources)):
            pinned = pinned_sources.get(name)
            current = implementation_sources.get(name)
            if pinned != current:
                source_drift_rows.append(
                    {"name": name, "pinned": pinned, "current": current}
                )
    source_drift = {
        "detected": bool(source_drift_rows),
        "pinned_from_map_acceptance": dict(pinned_sources)
        if isinstance(pinned_sources, Mapping)
        else {},
        "current": implementation_sources,
        "mismatches": source_drift_rows,
        "note": (
            "The production evaluator is pinned to current source bytes; a mismatch "
            "means the v2.4 map/matrix were derived with a different source snapshot."
            if source_drift_rows
            else "Current production source bytes match the map acceptance snapshot."
        ),
    }
    localization_summary = _localization_summary(
        case_outputs, matrix_pin, after_summary
    )
    rescore_identity = _json_digest(
        {
            "map": map_pin,
            "source": source_pin,
            "cases": case_manifest_digest,
            "implementation": implementation_sources,
            "k_values": selected_k,
        }
    )
    return {
        "schema_version": RESCORE_SCHEMA_VERSION,
        "status": "UNVERIFIED",
        "run_id": run.name,
        "rescore_identity": rescore_identity,
        "method": "historical_production_evaluate_case",
        "inputs": {
            "run_dir": str(run),
            "source": source_pin,
            "map": map_pin,
            "cases": {
                "count": len(case_paths),
                "sha256": case_manifest_digest,
                "files": case_hashes,
            },
            "original_summary": {
                "path": str(before_summary_path),
                "file_sha256": _sha256_file(before_summary_path) if before_summary_path.is_file() else None,
            },
            "experiment": {
                "path": str(raw_experiment_path),
                "file_sha256": _sha256_file(raw_experiment_path) if raw_experiment_path.is_file() else None,
            },
        },
        "production_index": {
            "loaded_once": True,
            "catalog_verified": bool(corpus.catalog_verified),
            "map_digest_verified": bool(corpus.map_digest_verified),
            "source_pins_verified": bool(corpus.source_pins_verified),
            "document_id": document_id,
            "object_count": len(corpus.object_catalog),
            "runtime_chunk_count": len(corpus.runtime_chunks),
        },
        "metric_config": {"k_values": list(selected_k), "evaluate_answer": True},
        "matrix": matrix_pin,
        "localization_summary": localization_summary,
        "source_drift": source_drift,
        "summary_policy": {
            "recall_denominator": "production MSES selected-path clauses per case/stage",
            "matrix_role": "19 Gold x 3 stages = 57 independent localization diagnostics; never an overall recall denominator",
            "alternative_paths": "preserved by production evaluate_case and reported in stage_localization",
        },
        "before_summary": before_summary,
        "after_summary": after_summary,
        "case_count": len(case_outputs),
        "cases": case_outputs,
        "change_summary": change_summary,
        "implementation_source_sha256": implementation_sources,
        "execution_scope": {
            "source_case_artifacts_reused": True,
            "retrieval_rerun": False,
            "answer_generation_rerun": False,
            "lightrag_rerun": False,
            "production_evaluate_case_invoked": True,
        },
        "baseline_verification": baseline_result,
        "unverified": [
            "worker/container runtime acceptance is outside this offline derivative",
            "root acceptance review of the derived metrics remains required",
            *(["map acceptance source hashes differ from the current production scorer"] if source_drift_rows else []),
        ],
    }


def _markdown_value(value: Any) -> str:
    if value is None:
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _summary_metric_text(value: Any) -> str:
    if not isinstance(value, Mapping):
        return "—"
    status = value.get("status", "—")
    metric_value = value.get("value")
    numerator = value.get("numerator")
    denominator = value.get("denominator")
    coverage = value.get("coverage")
    status_counts = value.get("status_counts")
    counts_text = ""
    if isinstance(status_counts, Mapping):
        counts_text = "; statuses=" + ", ".join(
            f"{key}:{status_counts[key]}" for key in sorted(status_counts)
        )
    return (
        f"{_markdown_value(status)} / {_markdown_value(metric_value)}; "
        f"n={_markdown_value(numerator)}/{_markdown_value(denominator)}; "
        f"coverage={_markdown_value(coverage)}{counts_text}"
    )


def _metric_cell(value: Any) -> str:
    if not isinstance(value, Mapping):
        return "—"
    return (
        f"{_markdown_value(value.get('status'))} / {_markdown_value(value.get('value'))}; "
        f"n={_markdown_value(value.get('numerator'))}/{_markdown_value(value.get('denominator'))}"
    )


def rescore_markdown(value: Mapping[str, Any]) -> str:
    lines = [
        "# Historical production re-score",
        "",
        f"Status: **{value.get('status', 'UNVERIFIED')}**",
        "",
        f"Run `{value.get('run_id', '')}` · `{value.get('method', '')}` · {value.get('case_count', 0)} retained cases.",
        "",
        "The map was loaded once and the retained results were passed through the production `evaluate_case` path. The 19 × 3 localization matrix is diagnostic, not a recall denominator.",
        "",
        "## Summary changes",
        "",
        "| Metric | Before (status/value; n; coverage; status counts) | After (status/value; n; coverage; status counts) | Δ value |",
        "|---|---|---|---:|",
    ]
    before_metrics = (value.get("before_summary") or {}).get("metrics", {})
    after_metrics = (value.get("after_summary") or {}).get("metrics", {})
    for metric_id in sorted(set(before_metrics) | set(after_metrics)):
        before = before_metrics.get(metric_id, {})
        after = after_metrics.get(metric_id, {})
        before_value = before.get("value") if isinstance(before, Mapping) else None
        after_value = after.get("value") if isinstance(after, Mapping) else None
        delta = (
            after_value - before_value
            if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float))
            else None
        )
        lines.append(
            "| " + " | ".join(
                [
                    _markdown_value(metric_id),
                    _summary_metric_text(before),
                    _summary_metric_text(after),
                    _markdown_value(delta),
                ]
            ) + " |"
        )
    localization_summary = value.get("localization_summary", {})
    matrix_summary = localization_summary.get("matrix_19_gold_x_3_stages", {})
    selected_summary = localization_summary.get("production_selected_path_clauses", {})
    lines.extend(["", "## Localization count views", ""])
    lines.append(
        "The following are separate denominators: the first table is the exact "
        "19 Gold × 3-stage diagnostic; the second is production's selected-path "
        "clause localization (the `after_summary` percentages are macro case means)."
    )
    lines.extend(
        [
            "",
            "### Exact Gold matrix (micro counts)",
            "",
            "| Stage | Matched | Partial | Retrieval missed | Provenance missing | Denominator |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    matrix_stage_names = {
        "raw_retrieval": "Raw",
        "ranked_retrieval": "Ranked",
        "final_context": "Context",
    }
    for stage, label in matrix_stage_names.items():
        row = matrix_summary.get("by_stage", {}).get(stage, {})
        lines.append(
            "| " + " | ".join(
                [
                    label,
                    _markdown_value(row.get("matched")),
                    _markdown_value(row.get("partial")),
                    _markdown_value(row.get("retrieval_missed")),
                    _markdown_value(row.get("provenance_missing")),
                    _markdown_value(row.get("denominator")),
                ]
            ) + " |"
        )
    lines.extend(
        [
            "",
            "### Production selected-path clauses (micro counts; case mean shown separately)",
            "",
            "| Stage | Matched | Partial | Retrieval missed | Provenance missing | Clause denominator | Macro matched case mean |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for stage, label in (("raw", "Raw"), ("ranked", "Ranked"), ("context", "Context")):
        row = selected_summary.get("by_stage", {}).get(stage, {})
        means = row.get("case_mean", {}) if isinstance(row, Mapping) else {}
        lines.append(
            "| " + " | ".join(
                [
                    label,
                    _markdown_value(row.get("matched")),
                    _markdown_value(row.get("partial")),
                    _markdown_value(row.get("retrieval_missed")),
                    _markdown_value(row.get("provenance_missing")),
                    _markdown_value(row.get("denominator")),
                    _markdown_value(means.get("matched")),
                ]
            ) + " |"
        )
    lines.extend(["", "## Per-question metric changes", ""])
    for case in value.get("cases", []):
        lines.extend(
            [
                f"### {_markdown_value(case.get('title') or case.get('case_id'))}",
                "",
                f"Question: {_markdown_value(case.get('question'))}",
                "",
                "| Metric | Before | After | Explanation |",
                "|---|---|---|---|",
            ]
        )
        for change in case.get("metric_changes", []):
            before = change.get("before") or {}
            after = change.get("after") or {}
            before_text = _metric_cell(before)
            after_text = _metric_cell(after)
            lines.append(
                "| " + " | ".join(
                    [
                        _markdown_value(change.get("metric_id")),
                        _markdown_value(before_text),
                        _markdown_value(after_text),
                        _markdown_value(change.get("explanation")),
                    ]
                ) + " |"
            )
        lines.extend(["", f"Gold evidence: {case.get('gold_evidence_count', 0)}; required groups: {case.get('required_group_count', 0)}; MSES paths: {case.get('mses_path_count', 0)}.", ""])
    lines.extend(["## Scope", "", "- No retrieval, answer generation, or LightRAG execution was performed.", "- Source/case/map pins, production scorer hashes, and baseline verification are retained in the JSON artifact.", "- Final status remains `UNVERIFIED` pending the external runtime and root review.", ""])
    return "\n".join(lines)


def write_historical_rescore(
    run_dir: str | Path,
    output_dir: str | Path,
    value: Mapping[str, Any],
    *,
    rescore_filename: str = "historical-rescore-v1.json",
    markdown_filename: str = "historical-rescore-v1.md",
    acceptance_filename: str = "historical-rescore-v1-acceptance.json",
) -> dict[str, str]:
    """Write a rescore bundle append-only and return its artifact paths."""

    run = Path(run_dir).resolve(strict=True)
    output = Path(output_dir).resolve(strict=False)
    rescore_path = write_derived_json(run, output / rescore_filename, value)
    markdown_path = write_derived_text(run, output / markdown_filename, rescore_markdown(value))
    acceptance = {
        "schema_version": RESCORE_ACCEPTANCE_SCHEMA_VERSION,
        "status": "UNVERIFIED",
        "run_id": value.get("run_id"),
        "rescore_identity": value.get("rescore_identity"),
        "rescore": {
            "path": str(rescore_path),
            "file_sha256": _sha256_file(rescore_path),
        },
        "markdown": {
            "path": str(markdown_path),
            "file_sha256": _sha256_file(markdown_path),
        },
        "inputs": value.get("inputs"),
        "production_index": value.get("production_index"),
        "localization_summary": value.get("localization_summary"),
        "source_drift": value.get("source_drift"),
        "after_summary": value.get("after_summary"),
        "implementation_source_sha256": value.get("implementation_source_sha256"),
        "baseline_verification": value.get("baseline_verification"),
        "unverified": value.get("unverified"),
    }
    acceptance_path = write_derived_json(run, output / acceptance_filename, acceptance)
    return {
        "rescore": str(rescore_path),
        "markdown": str(markdown_path),
        "acceptance": str(acceptance_path),
    }


__all__ = [
    "RESCORE_SCHEMA_VERSION",
    "RESCORE_ACCEPTANCE_SCHEMA_VERSION",
    "rescore_historical_run",
    "rescore_markdown",
    "write_historical_rescore",
]
