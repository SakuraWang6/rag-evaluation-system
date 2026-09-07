"""Runtime-only Bundle 3.0 rehearsal utilities.

This module is deliberately outside the frozen Dataset/Gold contracts.  It
uses a sealed Bundle 3.0 runtime view to drive a RAG Adapter, and only opens
the private Bundle after the worker has stopped to evaluate the captured
traces.  The evaluator preserves the Authoring Ledger's MSES OR-of-AND
semantics instead of projecting it to Bundle 2.0 ``required_groups``.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import shutil
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import monotonic
from typing import Any, Iterable

from rag_eval.artifact_contract import artifact_digest
from rag_eval.contracts.adapter import (
    AdapterCapabilities,
    DocumentInput,
    PrepareContext,
    RAGQuery,
)
from rag_eval.contracts.dataset import GoldAnswer, GoldAnswerKind
from rag_eval.contracts.research import ModelArtifactIdentity
from rag_eval.contracts.run import ExperimentSpec, RunManifest, RunStatus
from rag_eval.datasets.bundle_v3 import (
    DatasetBundleV3,
    DatasetBundleV3Runtime,
    load_bundle_v3,
    load_bundle_v3_runtime,
)
from rag_eval.evaluation.answers import (
    ANSWER_SCORER_DIGEST,
    ANSWER_SCORER_ID,
    ANSWER_SCORER_VERSION,
    AnswerVerdict,
    normalize_text,
    score_answer,
)
from rag_eval.storage.experiments import ExperimentStore
from rag_eval.storage.runs import RunStore
from rag_eval.worker.process import WorkerCommand, WorkerProcess


E2E_REHEARSAL_SCHEMA_VERSION = "rag-eval-e2e-rehearsal/1.0"
E2E_EVALUATOR_ID = "bundle-v3-private-mses-evaluator"
E2E_EVALUATOR_VERSION = "1.0"


def _source_digest() -> str:
    return "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


E2E_EVALUATOR_DIGEST = _source_digest()


class RehearsalIntegrityError(ValueError):
    """A rehearsal input or runtime/private boundary is invalid."""


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def write_jsonl(path: Path, values: Iterable[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(canonical_json_bytes(value) for value in values))


def _utc_now() -> datetime:
    return datetime.now(UTC)


def runtime_view_audit(runtime: DatasetBundleV3Runtime) -> dict[str, Any]:
    """Verify that an input is a genuine, Gold-free runtime view.

    ``load_bundle_v3_runtime`` validates checksums and rejects every file
    outside its small allowlist.  This additional audit records the exact
    boundary as an execution artifact and validates question uniqueness.
    """

    allowed_top_level = {"manifest.json", "questions.jsonl", "checksums.json"}
    observed_files = sorted(
        path.relative_to(runtime.root).as_posix()
        for path in runtime.root.rglob("*")
        if path.is_file()
    )
    violations = [
        relative
        for relative in observed_files
        if relative not in allowed_top_level and not relative.startswith("source/")
    ]
    questions = [item.model_dump(mode="json") for item in runtime.questions]
    private_keys = {
        "answer",
        "accepted_values",
        "gold",
        "gold_id",
        "gold_revision_id",
        "evidence",
        "mses_paths",
        "negative_scope_object_ids",
        "canonical",
        "private",
    }
    exposed_keys = sorted(
        {
            key
            for question in questions
            for key in question
            if key in private_keys
        }
    )
    if violations or exposed_keys:
        raise RehearsalIntegrityError(
            "runtime view leaks a private artifact or field: "
            f"files={violations}, keys={exposed_keys}"
        )
    if len(questions) != runtime.manifest.case_count:
        raise RehearsalIntegrityError("runtime case count does not match its manifest")
    case_ids = [item["case_id"] for item in questions]
    if len(case_ids) != len(set(case_ids)):
        raise RehearsalIntegrityError("runtime questions contain duplicate Case IDs")
    return {
        "schema_version": E2E_REHEARSAL_SCHEMA_VERSION,
        "runtime_bundle_id": runtime.runtime_bundle_id,
        "runtime_schema_version": runtime.manifest.schema_version,
        "target_release_id": runtime.manifest.target_release_id,
        "case_count": len(case_ids),
        "runtime_files": observed_files,
        "runtime_only": True,
        "private_file_violations": violations,
        "private_field_violations": exposed_keys,
        "source_digests": {
            source.runtime_path: source.source_digest
            for source in runtime.manifest.source_documents
        },
    }


def _validate_bundle_pair(
    bundle: DatasetBundleV3, runtime: DatasetBundleV3Runtime
) -> None:
    if bundle.manifest.target_release_id != runtime.manifest.target_release_id:
        raise RehearsalIntegrityError("private Bundle and runtime view pin different releases")
    if bundle.manifest.dataset_id != runtime.manifest.dataset_id:
        raise RehearsalIntegrityError("private Bundle and runtime view pin different datasets")
    if len(bundle.cases) != len(runtime.questions):
        raise RehearsalIntegrityError("private Bundle and runtime view have different Case counts")
    if {item.case.case_id for item in bundle.cases} != {
        item.case_id for item in runtime.questions
    }:
        raise RehearsalIntegrityError("private Bundle and runtime view have different Cases")


def stage_runtime_sources(
    runtime: DatasetBundleV3Runtime, source_dir: Path
) -> tuple[list[DocumentInput], dict[str, str]]:
    """Copy only runtime source files into a Worker-visible source directory."""

    if source_dir.exists() and any(source_dir.iterdir()):
        raise RehearsalIntegrityError("worker source sandbox is not empty")
    source_dir.mkdir(parents=True, exist_ok=True)
    documents: list[DocumentInput] = []
    staged: dict[str, str] = {}
    for ordinal, source in enumerate(runtime.manifest.source_documents):
        source_path = runtime.root / source.runtime_path
        if not source_path.is_file() or sha256_file(source_path) != source.source_digest:
            raise RehearsalIntegrityError(f"runtime source digest mismatch: {source.runtime_path}")
        destination_relative = Path("source") / source_path.name
        destination = source_dir / destination_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        if sha256_file(destination) != source.source_digest:
            raise RehearsalIntegrityError("staged source digest does not match runtime pin")
        for document_id in source.document_ids:
            documents.append(
                DocumentInput(
                    document_id=document_id,
                    source_path=destination_relative.as_posix(),
                    sha256=source.source_digest,
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                        if source_path.suffix.lower() == ".docx"
                        else "application/octet-stream"
                    ),
                    metadata={"runtime_bundle_id": runtime.runtime_bundle_id},
                )
            )
        staged[destination_relative.as_posix()] = source.source_digest
    return documents, staged


def case_selection_id(case_ids: Iterable[str]) -> str:
    material = "\n".join(sorted(case_ids)).encode("utf-8")
    return "case-selection-sha256-" + hashlib.sha256(material).hexdigest()[:24]


def default_adapter_config() -> dict[str, Any]:
    """The frozen no-tuning configuration for the diagnostic run."""

    return {
        "profile": "legacy",
        "query_mode": "naive",
        "chunking": {
            "strategy": "fixed_token",
            "chunk_token_size": 1200,
            "chunk_overlap_token_size": 100,
        },
        "retrieval_candidate_k": 20,
        "final_context_k": 5,
        "max_context_tokens": 12000,
        "enable_rerank": False,
        "ranking_strategy": "none",
        "exact_id_types": [],
        "table_preceding_context": False,
        "table_structured_envelope": False,
        "table_view": False,
        "table_row_view": False,
        "entity_extraction_instruction_profile": "legacy",
        "model": {
            "llm_binding": "ollama",
            "llm_model": "qwen3:4b-instruct",
            "llm_host": "http://127.0.0.1:11434",
            "query_llm_binding": "ollama",
            "query_llm_model": "qwen3:4b-instruct",
            "query_llm_host": "http://127.0.0.1:11434",
            "embedding_binding": "ollama",
            "embedding_model": "bge-m3:latest",
            "embedding_host": "http://127.0.0.1:11434",
            "llm_num_ctx": 32768,
        },
        "generation": {"temperature": 0.0, "seed": 20260830},
        "server_start_timeout_seconds": 90.0,
        "ingestion_timeout_seconds": 900.0,
        "query_timeout_seconds": 180.0,
        "poll_interval_seconds": 0.25,
    }


def make_experiment_spec(
    bundle: DatasetBundleV3, runtime: DatasetBundleV3Runtime
) -> ExperimentSpec:
    ids = [item.case_id for item in runtime.questions]
    return ExperimentSpec(
        experiment_id="e2e-lightrag-bundle3-runtime-33-v1",
        bundle_id=bundle.bundle_id,
        dataset_release_id=bundle.manifest.target_release_id,
        system_id="lightrag-naive-runtime-bundle3",
        adapter_id="lightrag",
        adapter_config=default_adapter_config(),
        query_config={
            "generate_answer": True,
            "retrieval_candidate_k": 20,
            "final_context_k": 5,
            "max_context_tokens": 12000,
            "order": "runtime_questions_jsonl_order",
        },
        metric_config={
            "private_evaluator": E2E_EVALUATOR_ID,
            "private_evaluator_version": E2E_EVALUATOR_VERSION,
            "private_evaluator_digest": E2E_EVALUATOR_DIGEST,
            "mses_semantics": "OR(paths) of AND(clauses) of OR(evidence alternatives)",
            "bundle_v2_projection": "not_used",
            "answer_scorer": {
                "id": ANSWER_SCORER_ID,
                "version": ANSWER_SCORER_VERSION,
                "digest": ANSWER_SCORER_DIGEST,
            },
        },
        case_ids=ids,
        case_selection_id=case_selection_id(ids),
        seed=20260830,
        repetitions=1,
        # This is a single-system engineering rehearsal, not a blind or
        # comparative formal claim.  The specification is nevertheless
        # written before execution and never rewritten.
        formal=False,
    )


def _to_evaluation_gold_answer(gold: Any) -> GoldAnswer:
    answer = gold.payload.answer
    tolerance = None
    if answer.tolerance is not None:
        try:
            tolerance = Decimal(answer.tolerance)
        except (InvalidOperation, ValueError):
            # The Ledger accepts a string because the Authoring policy owns
            # its numeric grammar.  The v1.1 scorer must not guess one.
            tolerance = None
    canonical: str | list[str] | None
    canonical = list(answer.canonical) if isinstance(answer.canonical, tuple) else answer.canonical
    return GoldAnswer(
        gold_answer_id=gold.gold_revision_id,
        kind=GoldAnswerKind(answer.kind),
        canonical=canonical,
        accepted_values=list(answer.accepted_values),
        locale=answer.locale,
        unit=answer.unit,
        tolerance=tolerance,
    )


def _normalized(value: str) -> str:
    return normalize_text(unicodedata.normalize("NFKC", value))


@dataclass(frozen=True, slots=True)
class CanonicalValueIndex:
    """Conservative private post-run bridge from chunks to Canonical IDs."""

    by_value: dict[str, frozenset[str]]
    by_object: dict[str, frozenset[str]]

    @classmethod
    def from_bundle(cls, bundle: DatasetBundleV3) -> "CanonicalValueIndex":
        values: dict[str, set[str]] = defaultdict(set)
        objects: dict[str, set[str]] = defaultdict(set)
        for document in bundle.canonical_documents.values():
            for obj in document.objects:
                normalized = _normalized(obj.canonical_value)
                if normalized:
                    values[normalized].add(obj.object_id)
                    objects[obj.object_id].add(normalized)
        # We only use a string witness when it identifies exactly one
        # canonical object across the immutable snapshots.  Short values and
        # repeated table cells remain explicitly unmapped rather than guessed.
        return cls(
            by_value={key: frozenset(value) for key, value in values.items()},
            by_object={key: frozenset(value) for key, value in objects.items()},
        )

    def matcher_for(self, canonical_object_ids: Iterable[str]) -> "CanonicalWitnessMatcher":
        return CanonicalWitnessMatcher(self, frozenset(canonical_object_ids))

    def map_content(
        self, content: str, canonical_object_ids: Iterable[str] | None = None
    ) -> dict[str, Any]:
        """Compatibility helper used by unit tests and simple diagnostics."""

        target_ids = (
            frozenset(canonical_object_ids)
            if canonical_object_ids is not None
            else frozenset(self.by_object)
        )
        return self.matcher_for(target_ids).map_content(content)


@dataclass(frozen=True, slots=True)
class CanonicalWitnessMatcher:
    """Case-local, source-unique text witnesses for private provenance replay.

    The native DOCX parser may turn a Canonical paragraph into a table block,
    so full-value containment is too strict. A witness is accepted only when
    it is at least 48 normalized characters and occurs solely in the target
    object's Canonical-value equivalence class. Short and repeated table cells
    remain unmapped; this bridge never treats approximate similarity as Gold
    evidence.
    """

    index: CanonicalValueIndex
    target_object_ids: frozenset[str]
    witness_length: int = 48

    def _safe_witnesses(self, object_id: str) -> tuple[str, ...]:
        values = self.index.by_object.get(object_id, frozenset())
        if not values:
            return ()
        value = max(values, key=len)
        if len(value) < self.witness_length:
            return ()
        equivalent_ids = self.index.by_value.get(value, frozenset({object_id}))
        starts = set(range(0, len(value) - self.witness_length + 1, 24))
        starts.add(len(value) - self.witness_length)
        accepted: list[str] = []
        for start in sorted(starts):
            witness = value[start : start + self.witness_length]
            containers: set[str] = set()
            for candidate, candidate_ids in self.index.by_value.items():
                if witness in candidate:
                    containers.update(candidate_ids)
                    if not containers.issubset(equivalent_ids):
                        break
            if containers and containers.issubset(equivalent_ids):
                accepted.append(witness)
        return tuple(dict.fromkeys(accepted))

    def map_content(self, content: str) -> dict[str, Any]:
        normalized_content = _normalized(content)
        matched: set[str] = set()
        ambiguous: set[str] = set()
        short: set[str] = set()
        for object_id in self.target_object_ids:
            values = self.index.by_object.get(object_id, frozenset())
            if not values:
                continue
            if all(len(value) < self.witness_length for value in values):
                short.add(object_id)
                continue
            witnesses = self._safe_witnesses(object_id)
            if any(witness in normalized_content for witness in witnesses):
                matched.add(object_id)
            elif not witnesses:
                ambiguous.add(object_id)
        return {
            "canonical_object_ids": sorted(matched),
            "status": "exact_unique_canonical_witness" if matched else "unmapped",
            "ambiguous_canonical_object_ids": sorted(ambiguous),
            "short_value_canonical_object_ids": sorted(short),
            "method": "private_post_run_unique_canonical_witness",
        }


def mses_progress(payload: Any, evidence_ranks: dict[str, int], *, cutoff: int | None = None) -> dict[str, Any]:
    """Evaluate Ledger MSES exactly: OR(paths) of AND(OR(alternatives))."""

    if payload.answer.kind == "abstain":
        return {
            "status": "not_applicable",
            "reason": "negative/unanswerable Gold has no positive MSES path",
            "paths": [],
            "complete_path_ids": [],
            "best_clause_coverage": None,
            "first_complete_rank": None,
        }
    paths: list[dict[str, Any]] = []
    complete: list[str] = []
    best_coverage = 0.0
    completion_ranks: list[int] = []
    for path in payload.mses_paths:
        clauses: list[dict[str, Any]] = []
        clause_ranks: list[int | None] = []
        for clause in path.clauses:
            candidate_ranks = sorted(
                evidence_ranks[evidence_id]
                for evidence_id in clause.alternatives
                if evidence_id in evidence_ranks
                and (cutoff is None or evidence_ranks[evidence_id] <= cutoff)
            )
            rank = candidate_ranks[0] if candidate_ranks else None
            clause_ranks.append(rank)
            clauses.append(
                {
                    "clause_id": clause.clause_id,
                    "alternatives": list(clause.alternatives),
                    "matched_rank": rank,
                    "satisfied": rank is not None,
                }
            )
        satisfied = sum(item["satisfied"] for item in clauses)
        coverage = satisfied / len(clauses)
        is_complete = satisfied == len(clauses)
        if is_complete:
            complete.append(path.path_id)
            completion_ranks.append(max(rank for rank in clause_ranks if rank is not None))
        best_coverage = max(best_coverage, coverage)
        paths.append(
            {
                "path_id": path.path_id,
                "clauses": clauses,
                "clause_coverage": coverage,
                "complete": is_complete,
            }
        )
    return {
        "status": "observed",
        "paths": paths,
        "complete_path_ids": complete,
        "best_clause_coverage": best_coverage,
        "first_complete_rank": min(completion_ranks) if completion_ranks else None,
    }


def _stage_evaluation(
    payload: Any,
    evidence_ranks: dict[str, int],
    provenance: list[dict[str, Any]],
) -> dict[str, Any]:
    progress = mses_progress(payload, evidence_ranks)
    mapped = sum(1 for item in provenance if item["status"] == "exact_unique_canonical_witness")
    total = len(provenance)
    result: dict[str, Any] = {
        "provenance": {
            "mapped_items": mapped,
            "total_items": total,
            "coverage": mapped / total if total else 0.0,
            "mapping_mode": "conservative_private_post_run",
            "unmapped_items": total - mapped,
        },
        "mses": progress,
        "metrics": [],
    }
    if progress["status"] == "not_applicable":
        result["metrics"] = [
            {
                "metric_id": "mses_clause_recall@" + str(k),
                "status": "not_applicable",
                "reason": progress["reason"],
            }
            for k in (1, 3, 5)
        ] + [
            {
                "metric_id": "mses_path_mrr",
                "status": "not_applicable",
                "reason": progress["reason"],
            }
        ]
        return result
    for cutoff in (1, 3, 5):
        at_cutoff = mses_progress(payload, evidence_ranks, cutoff=cutoff)
        result["metrics"].extend(
            [
                {
                    "metric_id": f"mses_clause_recall@{cutoff}",
                    "status": "observed",
                    "value": at_cutoff["best_clause_coverage"],
                    "mode": "max_clause_coverage_over_alternative_mses_paths",
                },
                {
                    "metric_id": f"mses_path_success@{cutoff}",
                    "status": "observed",
                    "value": 1.0 if at_cutoff["complete_path_ids"] else 0.0,
                    "mode": "any_complete_alternative_mses_path",
                },
            ]
        )
    first_rank = progress["first_complete_rank"]
    result["metrics"].append(
        {
            "metric_id": "mses_path_mrr",
            "status": "observed",
            "value": (1.0 / first_rank) if first_rank else 0.0,
            "mode": "reciprocal_rank_of_first_complete_mses_path",
        }
    )
    return result


def _answer_evaluation(gold: Any, answer: str | None, context: dict[str, Any]) -> dict[str, Any]:
    answer_score = score_answer(answer, _to_evaluation_gold_answer(gold))
    output: dict[str, Any] = {
        "answer_scorer": {
            "id": ANSWER_SCORER_ID,
            "version": ANSWER_SCORER_VERSION,
            "digest": ANSWER_SCORER_DIGEST,
        },
        "answer_accuracy": {
            "status": (
                "needs_review"
                if answer_score.verdict == AnswerVerdict.NEEDS_REVIEW
                else "observed"
            ),
            "value": (
                None
                if answer_score.verdict == AnswerVerdict.NEEDS_REVIEW
                else (1.0 if answer_score.passed else 0.0)
            ),
            "reason": answer_score.reason,
        },
    }
    if gold.payload.answer.kind == "abstain":
        output["answer_groundedness"] = {
            "status": "needs_review",
            "value": None,
            "reason": "bounded negative scope requires semantic human review; it is not reduced to absent retrieval",
        }
        output["unsupported_answer_rate"] = {
            "status": "needs_review",
            "value": None,
            "reason": "negative/unanswerable grounding is not automatically claimed",
        }
        return output
    if answer_score.verdict == AnswerVerdict.NEEDS_REVIEW:
        output["answer_groundedness"] = {
            "status": "needs_review",
            "value": None,
            "reason": answer_score.reason,
        }
        output["unsupported_answer_rate"] = {
            "status": "needs_review",
            "value": None,
            "reason": answer_score.reason,
        }
        return output
    complete = bool(context["mses"]["complete_path_ids"])
    supported = answer_score.passed and complete
    output["answer_groundedness"] = {
        "status": "observed",
        "value": 1.0 if supported else 0.0,
        "reason": "answer scorer plus complete context MSES path",
    }
    output["unsupported_answer_rate"] = {
        "status": "observed",
        "value": 0.0 if supported else 1.0,
        "reason": "inverse of deterministic supported-answer decision",
    }
    return output


def _failure_assessment(
    gold: Any,
    stages: dict[str, dict[str, Any]],
    answer_evaluation: dict[str, Any],
) -> dict[str, Any]:
    if gold.payload.answer.kind == "abstain":
        labels = []
        if answer_evaluation["answer_accuracy"]["status"] == "observed" and answer_evaluation["answer_accuracy"]["value"] == 0:
            labels.append("unsupported_answer")
        labels.append("needs_review")
        return {
            "labels": labels,
            "certainty": "unknown",
            "review_required": True,
            "reasons": [
                "negative/unanswerable scope is deliberately not classified from retrieval absence"
            ],
        }
    raw = stages["raw"]["mses"]
    ranked = stages["ranked"]["mses"]
    context = stages["context"]["mses"]
    labels: list[str] = []
    reasons: list[str] = []
    if not raw["complete_path_ids"]:
        labels.append("retrieval_missing")
        reasons.append("no complete MSES path mapped in raw retrieval")
    elif not ranked["complete_path_ids"]:
        labels.append("ranking_failure")
        reasons.append("a raw complete MSES path was lost before ranked retrieval")
    elif not context["complete_path_ids"]:
        labels.append("context_selection_loss")
        reasons.append("a ranked complete MSES path was lost from final context")
    accuracy = answer_evaluation["answer_accuracy"]
    if accuracy["status"] == "observed" and accuracy["value"] == 0:
        labels.append("generation_failure")
        reasons.append("answer did not satisfy the deterministic Gold answer scorer")
    if accuracy["status"] == "needs_review":
        labels.append("needs_review")
        reasons.append(accuracy["reason"])
    # A content-only bridge is intentionally conservative.  It can prove a
    # positive match, but unmapped chunks cannot prove absence.
    if any(stage["provenance"]["unmapped_items"] for stage in stages.values()):
        labels.append("needs_review")
        reasons.append("one or more runtime chunks have no safe Canonical mapping")
    return {
        "labels": sorted(set(labels)),
        "certainty": "unknown" if "needs_review" in labels else "deterministic",
        "review_required": "needs_review" in labels,
        "reasons": reasons,
    }


def _stage_matches(
    items: list[dict[str, Any]] | None,
    gold: Any,
    matcher: CanonicalWitnessMatcher,
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    evidence_by_object: dict[str, list[str]] = defaultdict(list)
    for evidence in gold.payload.evidence:
        evidence_by_object[evidence.canonical_object_id].append(evidence.evidence_id)
    ranks: dict[str, int] = {}
    provenance: list[dict[str, Any]] = []
    for item in items or []:
        mapping = matcher.map_content(str(item.get("content") or ""))
        mapping["item_id"] = item.get("item_id")
        mapping["rank"] = item.get("rank")
        provenance.append(mapping)
        rank = item.get("rank")
        if not isinstance(rank, int):
            continue
        for object_id in mapping["canonical_object_ids"]:
            for evidence_id in evidence_by_object.get(object_id, []):
                ranks[evidence_id] = min(ranks.get(evidence_id, rank), rank)
    return ranks, provenance


def evaluate_private_bundle(
    bundle: DatasetBundleV3, execution: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Evaluate post-run traces with private Gold and non-lossy MSES semantics."""

    gold_by_case = {item.gold.case_id: item.gold for item in bundle.gold}
    index = CanonicalValueIndex.from_bundle(bundle)
    results: list[dict[str, Any]] = []
    for record in execution:
        case_id = str(record["case_id"])
        gold = gold_by_case.get(case_id)
        if gold is None:
            raise RehearsalIntegrityError(f"execution Case lacks private Gold: {case_id}")
        if record["status"] != "completed":
            results.append(
                {
                    "case_id": case_id,
                    "gold_revision_id": gold.gold_revision_id,
                    "status": "execution_error",
                    "failure_assessment": {
                        "labels": ["adapter_error"],
                        "certainty": "deterministic",
                        "review_required": False,
                        "reasons": [record.get("error", {}).get("message", "execution failed")],
                    },
                }
            )
            continue
        result = record["rag_result"]
        matcher = index.matcher_for(
            evidence.canonical_object_id for evidence in gold.payload.evidence
        )
        stage_entries: dict[str, dict[str, Any]] = {}
        for name, key in (
            ("raw", "raw_retrieval"),
            ("ranked", "ranked_retrieval"),
            ("context", "final_context"),
        ):
            ranks, provenance = _stage_matches(result.get(key), gold, matcher)
            stage_entries[name] = _stage_evaluation(gold.payload, ranks, provenance)
        answer_evaluation = _answer_evaluation(gold, result.get("answer"), stage_entries["context"])
        results.append(
            {
                "case_id": case_id,
                "gold_revision_id": gold.gold_revision_id,
                "status": "completed",
                "gold_semantics": {
                    "answer_kind": gold.payload.answer.kind,
                    "mses_path_count": len(gold.payload.mses_paths),
                    "multi_hop_dependency_count": len(gold.payload.dependencies),
                    "negative_scope_object_ids": list(gold.payload.negative_scope_object_ids),
                    "evidence_roles": dict(Counter(item.role.value for item in gold.payload.evidence)),
                },
                "stages": stage_entries,
                "answer_evaluation": answer_evaluation,
                "failure_assessment": _failure_assessment(
                    gold, stage_entries, answer_evaluation
                ),
            }
        )
    return results, summarize_evaluation(results)


def summarize_evaluation(results: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [item for item in results if item["status"] == "completed"]
    metric_values: dict[str, list[float]] = defaultdict(list)
    statuses: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    mapping: dict[str, int] = Counter()
    for item in completed:
        for stage in item["stages"].values():
            provenance = stage["provenance"]
            mapping["mapped_items"] += provenance["mapped_items"]
            mapping["total_items"] += provenance["total_items"]
            for metric in stage["metrics"]:
                statuses[metric["status"]] += 1
                if metric["status"] == "observed" and isinstance(metric.get("value"), (int, float)):
                    metric_values[metric["metric_id"]].append(float(metric["value"]))
        for name, metric in item["answer_evaluation"].items():
            if name == "answer_scorer":
                continue
            statuses[metric["status"]] += 1
            if metric["status"] == "observed" and isinstance(metric.get("value"), (int, float)):
                metric_values[name].append(float(metric["value"]))
        failures.update(item["failure_assessment"]["labels"])
    return {
        "schema_version": E2E_REHEARSAL_SCHEMA_VERSION,
        "evaluator": {
            "id": E2E_EVALUATOR_ID,
            "version": E2E_EVALUATOR_VERSION,
            "digest": E2E_EVALUATOR_DIGEST,
        },
        "case_count": len(results),
        "completed_case_count": len(completed),
        "execution_error_count": len(results) - len(completed),
        "metric_statuses": dict(sorted(statuses.items())),
        "mean_metrics": {
            name: sum(values) / len(values)
            for name, values in sorted(metric_values.items())
            if values
        },
        "failure_labels": dict(sorted(failures.items())),
        "canonical_chunk_mapping": {
            **mapping,
            "coverage": (
                mapping["mapped_items"] / mapping["total_items"]
                if mapping["total_items"]
                else 0.0
            ),
            "policy": "exact source-unique Canonical witness only; unmapped chunks never become a positive evidence match",
        },
    }


def summarize_trace_capture(execution: list[dict[str, Any]]) -> dict[str, int]:
    """Count only trace fields actually returned by the Adapter/Core."""

    counts: Counter[str] = Counter()
    for record in execution:
        if record.get("status") != "completed":
            continue
        result = record.get("rag_result") or {}
        trace = result.get("trace") or {}
        native = trace.get("light_rag_evaluation_trace") or {}
        if isinstance(native.get("final_prompt"), str) and native["final_prompt"].strip():
            counts["rendered_answer_prompt"] += 1
        if native.get("query_rewrite") is not None:
            counts["query_rewrite"] += 1
        if isinstance(native.get("retrieval_stages"), dict):
            counts["retrieval_stages"] += 1
        if result.get("raw_retrieval") is not None:
            counts["raw_retrieval"] += 1
        if result.get("ranked_retrieval") is not None:
            counts["ranked_retrieval"] += 1
        if result.get("final_context") is not None:
            counts["final_context"] += 1
        if result.get("answer") is not None:
            counts["answer"] += 1
    return dict(sorted(counts.items()))


def _manifest(
    *,
    run_id: str,
    experiment: ExperimentSpec,
    declared: AdapterCapabilities,
    observed: AdapterCapabilities,
    adapter_version: str,
    system_version: str,
    effective_config: dict[str, Any],
    model_artifacts: dict[str, ModelArtifactIdentity],
    status: RunStatus,
    started_at: datetime,
    completed_at: datetime | None = None,
    execution_counts: dict[str, int] | None = None,
    artifacts: dict[str, str] | None = None,
    artifact_checksums: dict[str, str] | None = None,
    index_fingerprint: str | None = None,
    index_artifact_digest: str | None = None,
    failure_reason: str | None = None,
) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        experiment_id=experiment.experiment_id,
        status=status,
        bundle_id=experiment.bundle_id,
        dataset_release_id=experiment.dataset_release_id,
        case_selection_id=experiment.case_selection_id,
        platform_version=importlib.metadata.version("rag-eval-platform"),
        adapter_id=experiment.adapter_id,
        adapter_version=adapter_version,
        system_id=experiment.system_id,
        system_version=system_version,
        declared_config=experiment.model_dump(mode="json"),
        effective_config=effective_config,
        scorer_id=E2E_EVALUATOR_ID,
        scorer_version=E2E_EVALUATOR_VERSION,
        scorer_digest=E2E_EVALUATOR_DIGEST,
        metric_scorers={
            "bundle_v3_mses": {
                "id": E2E_EVALUATOR_ID,
                "version": E2E_EVALUATOR_VERSION,
                "digest": E2E_EVALUATOR_DIGEST,
            },
            "answer": {
                "id": ANSWER_SCORER_ID,
                "version": ANSWER_SCORER_VERSION,
                "digest": ANSWER_SCORER_DIGEST,
            },
        },
        model_artifacts=model_artifacts,
        declared_capabilities=declared,
        observed_capabilities=observed,
        seed=experiment.seed,
        repetitions=experiment.repetitions,
        started_at=started_at,
        completed_at=completed_at,
        execution_counts=execution_counts or {},
        artifacts=artifacts or {},
        artifact_checksums=artifact_checksums or {},
        index_fingerprint=index_fingerprint,
        index_fingerprints=[index_fingerprint] if index_fingerprint else [],
        index_input_fingerprint=index_fingerprint,
        index_artifact_digest=index_artifact_digest,
        index_artifact_digests=[index_artifact_digest] if index_artifact_digest else [],
        repetition_seeds=[experiment.seed],
        failure_reason=failure_reason,
    )


def run_rehearsal(
    *,
    private_bundle_root: Path,
    runtime_root: Path,
    output_root: Path,
    worker_python: str,
) -> dict[str, Any]:
    """Run all runtime Bundle questions and only then evaluate privately."""

    private_bundle_root = private_bundle_root.resolve()
    runtime_root = runtime_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"rehearsal output root already exists: {output_root}")

    # Load validates all sealed source/release/Canonical/Gold lineage before
    # any adapter is started.  The runtime audit happens separately so only it
    # is ever staged in the Worker-visible source directory.
    bundle = load_bundle_v3(private_bundle_root)
    runtime = load_bundle_v3_runtime(runtime_root)
    _validate_bundle_pair(bundle, runtime)
    audit = runtime_view_audit(runtime)

    output_root.mkdir(parents=True)
    experiment = make_experiment_spec(bundle, runtime)
    experiment_path = ExperimentStore(output_root / "experiments").create(experiment)

    run_id = "e2e-lightrag-bundle3-runtime-33-v1"
    run_store = RunStore(output_root / "runs")
    run_dir = run_store.prepare_execution_layout(run_id)
    documents, staged_sources = stage_runtime_sources(runtime, run_dir / "source")
    audit["staged_worker_sources"] = staged_sources
    audit["worker_private_bundle_path_supplied"] = False
    write_json(run_dir / "runtime-view-audit.json", audit)

    started_at = _utc_now()
    worker = WorkerProcess(
        WorkerCommand(
            adapter_id="lightrag",
            adapter_factory="rag_eval_lightrag_adapter:create_worker_definition",
            python_executable=worker_python,
            request_timeout_seconds=210.0,
        ),
        run_id=run_id,
        log_path=run_dir / "worker" / "worker.log",
    )
    execution: list[dict[str, Any]] = []
    prepared_config: dict[str, Any] = {}
    model_artifacts: dict[str, ModelArtifactIdentity] = {}
    declared = AdapterCapabilities()
    observed = AdapterCapabilities()
    adapter_version = "unresolved"
    system_version = "unresolved"
    ingestion: dict[str, Any] = {}
    index_fingerprint: str | None = None
    index_artifact_digest: str | None = None
    manifest_created = False
    run_error: BaseException | None = None

    try:
        client = worker.start(handshake_timeout=20.0)
        handshake = client.handshake()
        declared = handshake.capabilities
        adapter_version = handshake.adapter_version
        system_version = handshake.system_version
        prepared = client.prepare(
            PrepareContext(
                run_id=run_id,
                work_dir=str(run_dir / "work"),
                source_dir=str(run_dir / "source"),
                platform_version=importlib.metadata.version("rag-eval-platform"),
                seed=experiment.seed,
                repetition=1,
            ),
            experiment.adapter_config,
        )
        observed = prepared.capabilities
        prepared_config = prepared.effective_config
        model_artifacts = {
            role: ModelArtifactIdentity.model_validate(value)
            for role, value in dict(prepared_config.get("model_artifacts") or {}).items()
        }
        manifest = _manifest(
            run_id=run_id,
            experiment=experiment,
            declared=declared,
            observed=observed,
            adapter_version=adapter_version,
            system_version=prepared.system_version,
            effective_config=prepared_config,
            model_artifacts=model_artifacts,
            status=RunStatus.INGESTING,
            started_at=started_at,
        )
        run_store.create(manifest, experiment)
        manifest_created = True

        ingestion_result = client.ingest(documents)
        ingestion = ingestion_result.model_dump(mode="json")
        if ingestion_result.ingested_documents != len(documents):
            raise RuntimeError("LightRAG did not acknowledge every runtime source document")
        index_fingerprint = ingestion_result.index_fingerprint
        index_artifact_digest = str(
            ingestion_result.details.get("index_artifact_digest") or ""
        ) or None

        for ordinal, question in enumerate(runtime.questions, 1):
            case_started = _utc_now()
            timer = monotonic()
            try:
                result = client.query(
                    RAGQuery(
                        case_id=question.case_id,
                        question=question.question,
                        generate_answer=True,
                        retrieval_candidate_k=20,
                        final_context_k=5,
                        max_context_tokens=12000,
                    )
                )
                execution.append(
                    {
                        "case_id": question.case_id,
                        "case_revision_id": question.case_revision_id,
                        "ordinal": ordinal,
                        "question": question.question,
                        "status": "completed",
                        "started_at": case_started.isoformat(),
                        "completed_at": _utc_now().isoformat(),
                        "end_to_end_query_latency": monotonic() - timer,
                        "rag_result": result.model_dump(mode="json"),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - preserve every Case attempt
                execution.append(
                    {
                        "case_id": question.case_id,
                        "case_revision_id": question.case_revision_id,
                        "ordinal": ordinal,
                        "question": question.question,
                        "status": "system_error",
                        "started_at": case_started.isoformat(),
                        "completed_at": _utc_now().isoformat(),
                        "end_to_end_query_latency": monotonic() - timer,
                        "error": {"type": type(exc).__name__, "message": str(exc)},
                    }
                )
    except BaseException as exc:  # keep a typed failed Run manifest after cleanup
        run_error = exc
    finally:
        worker.stop()

    write_jsonl(run_dir / "private-evaluation" / "case-execution.jsonl", execution)
    private_results, evaluation_summary = evaluate_private_bundle(bundle, execution)
    write_jsonl(run_dir / "private-evaluation" / "case-evaluation.jsonl", private_results)
    write_json(run_dir / "private-evaluation" / "summary.json", evaluation_summary)
    release_snapshot = {
        "bundle_id": bundle.bundle_id,
        "runtime_bundle_id": runtime.runtime_bundle_id,
        "dataset_id": bundle.manifest.dataset_id,
        "target_release_id": bundle.manifest.target_release_id,
        "target_release_digest": bundle.manifest.target_release_digest,
        "release_chain": [item.model_dump(mode="json") for item in bundle.manifest.release_chain],
        "canonical_documents": [
            item.model_dump(mode="json") for item in bundle.manifest.canonical_documents
        ],
        "source_documents": [
            item.model_dump(mode="json") for item in bundle.manifest.source_documents
        ],
        "case_count": len(bundle.cases),
        "gold_count": len(bundle.gold),
        "evidence_count": len(bundle.evidence),
        "frozen_case_count": sum(item.case.lifecycle.value == "frozen" for item in bundle.cases),
        "frozen_gold_count": sum(item.gold.lifecycle.value == "frozen" for item in bundle.gold),
    }
    write_json(run_dir / "release-snapshot.json", release_snapshot)
    write_json(run_dir / "ingestion.json", ingestion)

    completed_at = _utc_now()
    counts = Counter(record["status"] for record in execution)
    final_status = RunStatus.COMPLETED if run_error is None else RunStatus.FAILED
    artifacts = {
        "runtime_view_audit": "runtime-view-audit.json",
        "release_snapshot": "release-snapshot.json",
        "ingestion": "ingestion.json",
        "case_execution": "private-evaluation/case-execution.jsonl",
        "case_evaluation": "private-evaluation/case-evaluation.jsonl",
        "evaluation_summary": "private-evaluation/summary.json",
        "experiment_spec": str(experiment_path.relative_to(output_root)),
    }
    initial_manifest = _manifest(
        run_id=run_id,
        experiment=experiment,
        declared=declared,
        observed=observed,
        adapter_version=adapter_version,
        system_version=system_version,
        effective_config=prepared_config,
        model_artifacts=model_artifacts,
        status=final_status,
        started_at=started_at,
        completed_at=completed_at,
        execution_counts=dict(sorted(counts.items())),
        artifacts=artifacts,
        index_fingerprint=index_fingerprint,
        index_artifact_digest=index_artifact_digest,
        failure_reason=(f"{type(run_error).__name__}: {run_error}" if run_error else None),
    )
    if not manifest_created:
        run_store.create(initial_manifest, experiment)
    else:
        run_store.write_manifest(initial_manifest)
    final_manifest = initial_manifest.model_copy(
        update={"artifact_checksums": run_store.artifact_hashes(run_id)}
    )
    run_store.write_manifest(final_manifest)
    verification = run_store.verify_artifacts(run_id)
    if not verification.valid:
        raise RehearsalIntegrityError(f"run artifacts failed self-verification: {verification}")

    return {
        "schema_version": E2E_REHEARSAL_SCHEMA_VERSION,
        "output_root": str(output_root),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "experiment_path": str(experiment_path),
        "release_snapshot": release_snapshot,
        "runtime_audit": audit,
        "execution_counts": dict(sorted(counts.items())),
        "trace_capture": summarize_trace_capture(execution),
        "evaluation_summary": evaluation_summary,
        "run_manifest_digest": artifact_digest(final_manifest),
        "artifact_verification": {
            "valid": verification.valid,
            "missing": list(verification.missing),
            "unexpected": list(verification.unexpected),
            "mismatched": list(verification.mismatched),
        },
        "run_error": (
            {"type": type(run_error).__name__, "message": str(run_error)}
            if run_error
            else None
        ),
    }


def replay_private_evaluation(
    *,
    private_bundle_root: Path,
    run_dir: Path,
    replay_root: Path,
) -> dict[str, Any]:
    """Create a successor private evaluation from immutable captured traces.

    This is intentionally a post-run evaluator repair path: the original
    RunManifest, runtime source, worker logs, and captured results are never
    altered.  The replay manifest pins their hashes and the new evaluator
    source digest, so comparison of the two evaluation projections is
    auditable.
    """

    private_bundle_root = private_bundle_root.resolve()
    run_dir = run_dir.resolve()
    replay_root = replay_root.resolve()
    if replay_root.exists():
        raise FileExistsError(f"private evaluation replay already exists: {replay_root}")
    execution_path = run_dir / "private-evaluation" / "case-execution.jsonl"
    manifest_path = run_dir / "run.json"
    if not execution_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError("immutable execution or RunManifest artifact is missing")
    bundle = load_bundle_v3(private_bundle_root)
    execution = [
        json.loads(line)
        for line in execution_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(execution) != bundle.manifest.case_count:
        raise RehearsalIntegrityError("execution replay input does not cover every frozen Case")
    results, evaluation_summary = evaluate_private_bundle(bundle, execution)
    original_manifest = RunManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    store = RunStore(run_dir.parent)
    verification = store.verify_artifacts(original_manifest.run_id)
    if not verification.valid:
        raise RehearsalIntegrityError("immutable source Run artifacts no longer verify")
    release_snapshot = json.loads((run_dir / "release-snapshot.json").read_text(encoding="utf-8"))
    runtime_audit = json.loads((run_dir / "runtime-view-audit.json").read_text(encoding="utf-8"))
    counts = Counter(item.get("status") for item in execution)
    replay_root.mkdir(parents=True)
    write_jsonl(replay_root / "case-evaluation.jsonl", results)
    write_json(replay_root / "summary.json", evaluation_summary)
    replay_manifest = {
        "schema_version": "rag-eval-e2e-private-evaluation-replay/1.0",
        "evaluator": evaluation_summary["evaluator"],
        "reason": "replace full-value-only provenance bridge with source-unique long-witness bridge",
        "private_bundle_id": bundle.bundle_id,
        "target_release_id": bundle.manifest.target_release_id,
        "source_run_id": original_manifest.run_id,
        "source_run_manifest_sha256": sha256_file(manifest_path),
        "source_execution_sha256": sha256_file(execution_path),
        "source_artifact_verification": {
            "valid": verification.valid,
            "missing": list(verification.missing),
            "unexpected": list(verification.unexpected),
            "mismatched": list(verification.mismatched),
        },
        "case_count": len(execution),
    }
    write_json(replay_root / "replay-manifest.json", replay_manifest)
    return {
        "schema_version": E2E_REHEARSAL_SCHEMA_VERSION,
        "output_root": str(replay_root.parent),
        "run_id": original_manifest.run_id,
        "run_dir": str(run_dir),
        "experiment_path": str(run_dir / "experiment.json"),
        "release_snapshot": release_snapshot,
        "runtime_audit": runtime_audit,
        "execution_counts": dict(sorted(counts.items())),
        "trace_capture": summarize_trace_capture(execution),
        "evaluation_summary": evaluation_summary,
        "run_manifest_digest": artifact_digest(original_manifest),
        "artifact_verification": {
            "valid": verification.valid,
            "missing": list(verification.missing),
            "unexpected": list(verification.unexpected),
            "mismatched": list(verification.mismatched),
        },
        "evaluation_replay": {
            "root": str(replay_root),
            "manifest_sha256": sha256_file(replay_root / "replay-manifest.json"),
            "case_evaluation_sha256": sha256_file(replay_root / "case-evaluation.jsonl"),
        },
        "run_error": None,
    }


def render_rehearsal_report(summary: dict[str, Any]) -> str:
    """Render a concise report without leaking private Gold values."""

    release = summary["release_snapshot"]
    evaluation = summary["evaluation_summary"]
    runtime = summary["runtime_audit"]
    counts = summary["execution_counts"]
    trace_capture = summary.get("trace_capture", {})
    execution_ok = counts.get("completed", 0) == release["case_count"] and not summary["run_error"]
    health = "PASS" if execution_ok and summary["artifact_verification"]["valid"] else "BLOCKED"
    lines = [
        "# End-to-End RAG Evaluation Rehearsal Report",
        "",
        f"## Workflow health: {health}",
        "",
        "This is an engineering rehearsal, not a comparative performance claim. "
        "All Gold-bearing evaluation happened only after the Adapter Worker stopped.",
        "",
        "## Frozen inputs and lineage",
        "",
        f"- Bundle 3.0: `{release['bundle_id']}`",
        f"- Runtime view: `{release['runtime_bundle_id']}`",
        f"- Dataset / target release: `{release['dataset_id']}` / `{release['target_release_id']}`",
        f"- Target release digest: `{release['target_release_digest']}`",
        f"- Frozen Case / Gold / evidence counts: {release['frozen_case_count']} / {release['frozen_gold_count']} / {release['evidence_count']}",
        f"- Source digest: `{release['source_documents'][0]['source_digest']}`",
        f"- Canonical pins: {', '.join(item['release_id'] + ':' + item['canonical_digest'] for item in release['canonical_documents'])}",
        "",
        "## Runtime/private isolation",
        "",
        f"- Runtime audit passed: `{runtime['runtime_only']}`; private file violations: {len(runtime['private_file_violations'])}; private field violations: {len(runtime['private_field_violations'])}.",
        "- The Worker received only checksum-pinned runtime source DOCX files in its source sandbox; no private Bundle path, Gold, evidence, answer, or Canonical snapshot was supplied.",
        "- Private Bundle loading and MSES/Gold scoring occurred after Worker shutdown in the coordinator's private-evaluation directory.",
        "",
        "## Execution",
        "",
        f"- Case attempts: {release['case_count']}; completed: {counts.get('completed', 0)}; system errors: {counts.get('system_error', 0)}.",
        "- Adapter configuration was frozen in ExperimentSpec before execution: LightRAG naive/legacy, fixed-token 1200/100, candidate K=20, final-context K=5, rerank disabled, temperature 0, seed 20260830.",
        "- Captured traces contain query payload, LightRAG raw/ranked/context retrieval stages, answer, latency, runtime chunk IDs and model-effective configuration. "
        + (
            f"LightRAG returned a rendered answer prompt for {trace_capture.get('rendered_answer_prompt', 0)}/{release['case_count']} Cases; "
            if trace_capture.get("rendered_answer_prompt")
            else "LightRAG did not expose a rendered answer prompt; it is marked unavailable. "
        )
        + (
            f"query rewrite was exposed for {trace_capture.get('query_rewrite', 0)}/{release['case_count']} Cases."
            if trace_capture.get("query_rewrite")
            else "query rewrite was not exposed and is marked unavailable."
        )
        + " No synthetic trace was created.",
        "",
        "## Private evaluation",
        "",
        f"- Evaluator: `{evaluation['evaluator']['id']}` {evaluation['evaluator']['version']} (`{evaluation['evaluator']['digest']}`).",
        "- Gold semantics: exact Ledger MSES OR(paths) of AND(clauses) of OR(evidence alternatives); no Bundle 2.0 `required_groups` projection was used.",
        f"- Canonical-to-runtime chunk mapping coverage: {evaluation['canonical_chunk_mapping']['mapped_items']}/{evaluation['canonical_chunk_mapping']['total_items']} ({evaluation['canonical_chunk_mapping']['coverage']:.3f}). It is conservative: only an exact, source-unique Canonical text witness is a match; short or ambiguous table values remain unmapped.",
        "- Mean observed metrics:",
        "",
    ]
    if evaluation["mean_metrics"]:
        lines.extend(
            f"  - `{name}`: {value:.4f}"
            for name, value in evaluation["mean_metrics"].items()
        )
    else:
        lines.append("  - No observed metrics (execution did not complete).")
    lines.extend(
        [
            "",
            "- Failure-label counts:",
            "",
        ]
    )
    if evaluation["failure_labels"]:
        lines.extend(
            f"  - `{name}`: {value}"
            for name, value in evaluation["failure_labels"].items()
        )
    else:
        lines.append("  - None.")
    lines.extend(
        [
            "",
            "## Reproducibility artifacts",
            "",
            f"- Run manifest digest: `{summary['run_manifest_digest']}`",
            f"- Artifact self-verification: `{summary['artifact_verification']['valid']}`",
            f"- Rehearsal workspace: `{summary['output_root']}`",
            "- Key artifacts: `experiments/e2e-lightrag-bundle3-runtime-33-v1.json`, `runs/e2e-lightrag-bundle3-runtime-33-v1/run.json`, `runtime-view-audit.json`, `ingestion.json`, `private-evaluation/case-execution.jsonl`, `private-evaluation/case-evaluation.jsonl`, and `private-evaluation/summary.json`.",
            "",
            "## Explicit limitations",
            "",
            "- This one-system rehearsal does not make a score or ranking claim and does not tune LightRAG.",
            "- Query rewrite is not exposed by this LightRAG API trace. Rendered answer prompts are retained when the native trace provides `final_prompt`; neither field is inferred.",
            "- Binary DOCX ingestion is now supported by the Adapter through the sealed runtime source path. Its native trace has no source-span bridge to private Canonical snapshots, so post-run mapping is source-unique-text-witness-only and fail-closed for ambiguous/short table cells.",
            "- Negative/unanswerable Gold groundedness is deliberately left `needs_review`; missing retrieval is never treated as proof of an unanswerable claim.",
            "",
            "## Verdict",
            "",
            ("PASS — the frozen Bundle 3.0 runtime → Adapter execution → private Gold evaluation workflow completed without Gold entering the system-under-test." if health == "PASS" else "BLOCKED — inspect the failed execution or artifact verification above before treating this as an end-to-end workflow pass."),
            "",
        ]
    )
    if replay := summary.get("evaluation_replay"):
        lines[lines.index("## Reproducibility artifacts")] = "## Reproducibility artifacts"
        insert_at = lines.index("## Explicit limitations")
        lines[insert_at:insert_at] = [
            "- Private evaluator successor: `"
            + replay["root"]
            + "` (manifest SHA-256 `"
            + replay["manifest_sha256"]
            + "`). It pins, and does not modify, the original verified RunManifest and execution trace.",
            "",
        ]
    return "\n".join(lines)
