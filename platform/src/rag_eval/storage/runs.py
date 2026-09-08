"""Schema-v2-only run artifact store."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from rag_eval.contracts.adapter import RAGResult
from rag_eval.contracts.dataset import GoldAnswer, GoldEvidenceSet
from rag_eval.contracts.run import CaseResult, ExperimentSpec, RunManifest
from rag_eval.evaluation.answers import AnswerVerdict, score_answer
from rag_eval.evaluation.evidence import CorpusEvidenceIndex, evidence_observability
from rag_eval.runs.artifacts import ArtifactV2Reader, ArtifactV2Verification
from rag_eval.runs.models import RunArtifactManifestV2
from rag_eval.storage.atomic import atomic_write_json

logger = logging.getLogger(__name__)


class RunStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def create(
        self, manifest: RunManifest, experiment: ExperimentSpec
    ) -> Path:
        run_dir = self.root / safe_id(manifest.run_id)
        if run_dir.exists() and (run_dir / "run.json").exists():
            raise ValueError(f"run already exists: {manifest.run_id}")
        self.prepare_execution_layout(manifest.run_id)
        atomic_write_json(
            run_dir / "experiment.json", experiment.model_dump(mode="json")
        )
        self.write_manifest(manifest)
        return run_dir

    def prepare_execution_layout(self, run_id: str) -> Path:
        """Create an empty run-scoped mount layout before a Provider starts.

        This allows Docker to receive only source/work bind mounts while keeping
        normal LocalProcess behavior unchanged.  No immutable artifact is
        written until ``create`` receives a validated worker handshake.
        """
        run_dir = self.root / safe_id(run_id)
        if run_dir.exists() and (run_dir / "run.json").exists():
            raise ValueError(f"run already exists: {run_id}")
        run_dir.mkdir(parents=False, exist_ok=True)
        for name in ("cases", "worker", "source", "work"):
            (run_dir / name).mkdir(exist_ok=True)
        return run_dir

    def write_manifest(self, manifest: RunManifest) -> None:
        atomic_write_json(
            self.root / safe_id(manifest.run_id) / "run.json",
            manifest.model_dump(mode="json"),
        )

    def write_case(self, run_id: str, result: CaseResult) -> Path:
        path = (
            self.root
            / safe_id(run_id)
            / "cases"
            / f"rep-{result.repetition:04d}-{safe_id(result.case_id)}.json"
        )
        atomic_write_json(path, result.model_dump(mode="json"))
        return path

    def experiment(self, run_id: str) -> ExperimentSpec:
        path = self.root / safe_id(run_id) / "experiment.json"
        return ExperimentSpec.model_validate_json(path.read_text(encoding="utf-8"))

    def artifact_v2(self, run_id: str) -> ArtifactV2Reader:
        """Return the immutable v2 reader without changing Artifact 1.2 APIs."""

        return ArtifactV2Reader(self.root / safe_id(run_id) / "artifact-v2")

    def artifact_v2_manifest(self, run_id: str) -> RunArtifactManifestV2:
        return self.artifact_v2(run_id).manifest()

    def verify_artifact_v2(self, run_id: str) -> ArtifactV2Verification:
        return self.artifact_v2(run_id).verify()

    def artifact_hashes(self, run_id: str) -> dict[str, str]:
        return artifact_file_hashes(self.root / safe_id(run_id))

    def verify_artifacts(self, run_id: str) -> ArtifactVerification:
        manifest = self.get(run_id)
        actual = self.artifact_hashes(run_id)
        expected = manifest.artifact_checksums
        missing = tuple(sorted(set(expected) - set(actual)))
        unexpected = tuple(sorted(set(actual) - set(expected)))
        mismatched = tuple(
            sorted(
                path
                for path in set(expected).intersection(actual)
                if expected[path] != actual[path]
            )
        )
        return ArtifactVerification(
            valid=not missing and not unexpected and not mismatched,
            missing=missing,
            unexpected=unexpected,
            mismatched=mismatched,
        )

    def get(self, run_id: str) -> RunManifest:
        path = self.root / safe_id(run_id) / "run.json"
        manifest = RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
        if manifest.schema_version != 2 or manifest.producer != "rag_eval_platform":
            raise ValueError("run is not a schema-v2 platform run")
        return manifest

    def cases(self, run_id: str) -> list[CaseResult]:
        cases_dir = self.root / safe_id(run_id) / "cases"
        return [
            CaseResult.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(cases_dir.glob("*.json"))
        ]

    def case_index(self, run_id: str) -> list[dict[str, object]]:
        """Return the lightweight navigation fields without serializing evidence."""

        cases_dir = self.root / safe_id(run_id) / "cases"
        values: list[dict[str, object]] = []
        for path in sorted(cases_dir.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError(f"case artifact is malformed: {path.name}")
            case_id = raw.get("case_id")
            question = raw.get("question")
            status = raw.get("status")
            repetition = raw.get("repetition")
            seed = raw.get("seed")
            if (
                not isinstance(case_id, str)
                or not isinstance(question, str)
                or not isinstance(status, str)
                or not isinstance(repetition, int)
                or not isinstance(seed, int)
            ):
                raise ValueError(f"case artifact index fields are malformed: {path.name}")
            values.append(
                {
                    "case_id": case_id,
                    "question": question,
                    "status": status,
                    "repetition": repetition,
                    "seed": seed,
                    **case_judgments(
                        status=status,
                        metrics=raw.get("metrics"),
                        failure_assessment=raw.get("failure_assessment"),
                        gold_answer=raw.get("gold_answer"),
                        gold_evidence_set=raw.get("gold_evidence_set"),
                        rag_result=raw.get("rag_result"),
                    ),
                }
            )
        return values

    def case(self, run_id: str, case_id: str, *, repetition: int = 1) -> CaseResult:
        path = (
            self.root
            / safe_id(run_id)
            / "cases"
            / f"rep-{repetition:04d}-{safe_id(case_id)}.json"
        )
        if not path.is_file():
            raise FileNotFoundError(case_id)
        return CaseResult.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[RunManifest]:
        manifests: list[RunManifest] = []
        for path in sorted(self.root.glob("*/run.json")):
            try:
                manifest = RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                logger.debug("ignoring non-platform run manifest %s: %s", path, exc)
                continue
            if manifest.schema_version == 2 and manifest.producer == "rag_eval_platform":
                manifests.append(manifest)
        return manifests


def safe_id(value: str) -> str:
    if not value or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in value):
        raise ValueError(f"unsafe identifier: {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactVerification:
    valid: bool
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]
    mismatched: tuple[str, ...]


def case_judgments(
    *,
    status: str,
    metrics: Iterable[object] | None,
    failure_assessment: object,
    gold_answer: object | None = None,
    gold_evidence_set: object | None = None,
    rag_result: object | None = None,
    review: object | None = None,
) -> dict[str, str]:
    """Project case artifacts into separate answer and evidence outcomes.

    Case execution status only says whether a request returned.  It must not
    be used as the UI result for every completed question.  Likewise an answer
    can match the Gold answer while its supporting evidence was absent from
    retrieval, so the two outcomes are intentionally independent.
    """

    if status != "completed":
        return {"answer_judgment": "unavailable", "evidence_judgment": "unavailable"}

    by_id = {
        metric_id: (metric_status, metric_value)
        for item in metrics or []
        if (parsed := _metric_fields(item)) is not None
        for metric_id, metric_status, metric_value in [parsed]
    }
    reviewed = _review_verdict(review)
    answer = reviewed or _current_answer_judgment(gold_answer, rag_result)
    if answer is None:
        answer_status, answer_value = by_id.get("answer_accuracy", (None, None))
        if answer_status == "observed" and answer_value == 1:
            answer = "correct"
        elif answer_status == "observed" and answer_value == 0:
            answer = "incorrect"
        elif answer_status == "needs_review":
            answer = "needs_review"
        else:
            answer = "unavailable"

    labels = _failure_labels(failure_assessment)
    grounding_status, grounding_value = by_id.get("answer_groundedness", (None, None))
    unsupported_status, unsupported_value = by_id.get(
        "unsupported_answer_rate", (None, None)
    )
    # ``failure_assessment.labels`` is a cross-stage diagnostic list.  A raw
    # locator failure must not mask a valid final context in the product
    # evidence judgment.  The context projection is the sole source of truth
    # for this case-level field; raw/ranked labels remain available to the
    # caller for stage diagnostics.
    context_provenance_unavailable = _provenance_unavailable(
        gold_evidence_set, rag_result
    )
    if context_provenance_unavailable:
        evidence = "unverifiable"
    elif grounding_status == "observed" and grounding_value == 1:
        evidence = "grounded"
    elif unsupported_status == "needs_review":
        # Strict Gold localization cannot decide whether semantically
        # equivalent content elsewhere supports the answer.  Keep that
        # distinction visible instead of presenting a deterministic
        # ``ungrounded`` verdict.
        evidence = "needs_review"
    elif "retrieval_missing" in labels:
        evidence = "missing"
    elif unsupported_status == "observed" and unsupported_value == 1:
        evidence = "ungrounded"
    elif grounding_status == "observed" and grounding_value == 0:
        evidence = "missing"
    elif grounding_status == "needs_review":
        evidence = "needs_review"
    else:
        evidence = "unavailable"
    return {"answer_judgment": answer, "evidence_judgment": evidence}


def _review_verdict(value: object | None) -> str | None:
    """Project the final product review without changing a run artifact.

    Human adjudication takes precedence over every LLM proposal in the
    append-only history.  This remains defensive for ledgers written by older
    versions that may contain an automated entry after a human one.
    """

    if value is None:
        return None
    history = value.get("history") if isinstance(value, Mapping) else getattr(value, "decisions", None)
    if isinstance(history, Iterable) and not isinstance(history, (str, bytes, Mapping)):
        for decision in reversed(list(history)):
            source = (
                decision.get("source")
                if isinstance(decision, Mapping)
                else getattr(decision, "source", None)
            )
            if str(source) != "human":
                continue
            verdict = (
                decision.get("verdict")
                if isinstance(decision, Mapping)
                else getattr(decision, "verdict", None)
            )
            if str(verdict) in {"correct", "incorrect", "needs_review"}:
                return str(verdict)
    latest = value.get("latest") if isinstance(value, Mapping) else getattr(value, "latest", None)
    verdict = latest.get("verdict") if isinstance(latest, Mapping) else getattr(latest, "verdict", None)
    return str(verdict) if str(verdict) in {"correct", "incorrect", "needs_review"} else None


def _provenance_unavailable(
    gold_evidence_set: object | None, rag_result: object | None
) -> bool:
    """Recognize legacy artifacts whose persisted failure label predates v1.1."""

    try:
        evidence_set = (
            gold_evidence_set
            if isinstance(gold_evidence_set, GoldEvidenceSet)
            else GoldEvidenceSet.model_validate(gold_evidence_set)
        )
        result = (
            rag_result
            if isinstance(rag_result, RAGResult)
            else RAGResult.model_validate(rag_result)
        )
    except (TypeError, ValueError):
        return False
    # Evidence matching needs only same-document quote uniqueness. The corpus
    # is deliberately empty here because this projection asks a narrower
    # question: did the adapter explicitly lose locator provenance?
    # Case-level evidence judgment is about the context consumed by answer
    # generation.  Raw/ranked provenance failures remain stage-local and must
    # not mask an independently localized context.
    if result.final_context is None:
        return False
    return evidence_observability(
        result.final_context, evidence_set, CorpusEvidenceIndex({})
    ) is not None


def _current_answer_judgment(
    gold_answer: object | None, rag_result: object | None
) -> str | None:
    """Re-score answer presentation with the current deterministic rule.

    Run artifacts remain immutable and retain the scorer version that produced
    them.  The product result card is a read-only projection, so it can apply
    a bug-fixed deterministic answer rule to older artifacts without changing
    their research record.  When either input is unavailable, callers fall
    back to the persisted metric.
    """

    try:
        gold = (
            gold_answer
            if isinstance(gold_answer, GoldAnswer)
            else GoldAnswer.model_validate(gold_answer)
        )
        answer = (
            rag_result.get("answer")
            if isinstance(rag_result, Mapping)
            else getattr(rag_result, "answer")
        )
    except (AttributeError, TypeError, ValueError):
        return None
    verdict = score_answer(answer if isinstance(answer, str) else None, gold).verdict
    return {
        AnswerVerdict.PASS: "correct",
        AnswerVerdict.FAIL: "incorrect",
        AnswerVerdict.NEEDS_REVIEW: "needs_review",
    }[verdict]


def _metric_fields(item: object) -> tuple[str, str, float | None] | None:
    if isinstance(item, Mapping):
        metric_id = item.get("metric_id")
        status = item.get("status")
        value = item.get("value")
    else:
        metric_id = getattr(item, "metric_id", None)
        status = getattr(item, "status", None)
        value = getattr(item, "value", None)
    if not isinstance(metric_id, str) or not isinstance(status, str):
        return None
    if not isinstance(value, (float, int)):
        value = None
    return metric_id, status, value


def _failure_labels(value: object) -> set[str]:
    labels = value.get("labels") if isinstance(value, Mapping) else getattr(value, "labels", [])
    return {str(label) for label in labels} if isinstance(labels, Iterable) and not isinstance(labels, str) else set()


def artifact_file_hashes(run_dir: Path) -> dict[str, str]:
    """Hash immutable run artifacts, excluding mutable manifest and work index."""
    hashes: dict[str, str] = {}
    if not run_dir.is_dir():
        raise FileNotFoundError(run_dir)
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(run_dir).as_posix()
        if relative == "run.json" or relative.startswith("work/"):
            continue
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes
