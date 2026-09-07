"""Dataset Bundle 2.0 integrity and immutable storage."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from rag_eval.contracts.dataset import (
    DatasetBundleManifest,
    GoldAnswer,
    GoldEvidenceSet,
    ObjectLocator,
    PageRegionLocator,
    Question,
    TableCellLocator,
    TextSpanLocator,
)
from rag_eval.evaluation.answers import normalize_text
from rag_eval.storage.atomic import atomic_write_json

ModelT = TypeVar("ModelT", bound=BaseModel)
REQUIRED_FILES = (
    "manifest.json",
    "questions.jsonl",
    "gold_answers.jsonl",
    "gold_evidence.jsonl",
)


@dataclass(frozen=True, slots=True)
class DatasetBundle:
    root: Path
    bundle_id: str
    manifest: DatasetBundleManifest
    questions: tuple[Question, ...]
    gold_answers: dict[str, GoldAnswer]
    gold_evidence_sets: dict[str, GoldEvidenceSet]

    def source_documents(self) -> dict[str, str]:
        documents: dict[str, str] = {}
        for document in self.manifest.documents:
            path = self.root / (document.canonical_path or document.path)
            try:
                documents[document.document_id] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise BundleIntegrityError(
                    f"binary document {document.document_id!r} requires canonical_path"
                ) from exc
        return documents

    def question_by_id(self) -> dict[str, Question]:
        return {question.case_id: question for question in self.questions}


class DatasetBundleStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def register(self, source: Path) -> DatasetBundle:
        bundle = load_bundle(source)
        destination = self.root / bundle.bundle_id
        if destination.exists():
            existing = load_bundle(destination)
            if existing.bundle_id != bundle.bundle_id:
                raise BundleIntegrityError("existing bundle directory has wrong digest")
            return existing
        staging = self.root / f".{bundle.bundle_id}.staging"
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(source, staging)
        atomic_write_json(
            staging / "checksums.json",
            {"bundle_id": bundle.bundle_id, "files": canonical_file_hashes(staging)},
        )
        staging.rename(destination)
        return load_bundle(destination)

    def get(self, bundle_id: str) -> DatasetBundle:
        if not bundle_id or any(char not in "0123456789abcdef" for char in bundle_id):
            raise ValueError("bundle_id must be a lowercase hexadecimal digest")
        path = self.root / bundle_id
        if not path.is_dir():
            raise FileNotFoundError(bundle_id)
        bundle = load_bundle(path)
        if bundle.bundle_id != bundle_id:
            raise BundleIntegrityError("bundle directory name does not match contents")
        return bundle

    def list(self) -> list[DatasetBundle]:
        bundles: list[DatasetBundle] = []
        for path in sorted(self.root.iterdir()):
            if path.is_dir() and not path.name.startswith("."):
                bundles.append(self.get(path.name))
        return bundles


def load_bundle(root: Path) -> DatasetBundle:
    root = root.resolve()
    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            raise BundleIntegrityError(f"bundle is missing {name}")
    if not (root / "documents").is_dir():
        raise BundleIntegrityError("bundle is missing documents/")

    manifest = DatasetBundleManifest.model_validate_json(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    questions = tuple(_load_jsonl(root / "questions.jsonl", Question))
    answers = _unique_by(
        _load_jsonl(root / "gold_answers.jsonl", GoldAnswer), "gold_answer_id"
    )
    evidence_sets = _unique_by(
        _load_jsonl(root / "gold_evidence.jsonl", GoldEvidenceSet),
        "gold_evidence_set_id",
    )
    _validate_references(manifest, questions, answers, evidence_sets, root)

    files = canonical_file_hashes(root)
    bundle_id = digest_file_hashes(files)
    checksums_path = root / "checksums.json"
    if checksums_path.is_file():
        checksums = json.loads(checksums_path.read_text(encoding="utf-8"))
        if checksums.get("bundle_id") != bundle_id or checksums.get("files") != files:
            raise BundleIntegrityError("checksums.json does not match bundle contents")
    return DatasetBundle(
        root=root,
        bundle_id=bundle_id,
        manifest=manifest,
        questions=questions,
        gold_answers=answers,
        gold_evidence_sets=evidence_sets,
    )


def canonical_file_hashes(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative == "checksums.json" or relative.startswith("."):
            continue
        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def digest_file_hashes(files: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, file_digest in sorted(files.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def case_selection_id(case_ids: list[str], *, policy: str, seed: int) -> str:
    payload = json.dumps(
        {"case_ids": sorted(case_ids), "policy": policy, "seed": seed},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _load_jsonl(path: Path, model: type[ModelT]) -> list[ModelT]:
    values: list[ModelT] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            values.append(model.model_validate_json(line))
        except Exception as exc:
            raise BundleIntegrityError(f"{path.name}:{line_number}: {exc}") from exc
    return values


def _unique_by(values: list[ModelT], attribute: str) -> dict[str, ModelT]:
    result: dict[str, ModelT] = {}
    for value in values:
        key = str(getattr(value, attribute))
        if key in result:
            raise BundleIntegrityError(f"duplicate {attribute}: {key}")
        result[key] = value
    return result


def _validate_references(
    manifest: DatasetBundleManifest,
    questions: tuple[Question, ...],
    answers: dict[str, GoldAnswer],
    evidence_sets: dict[str, GoldEvidenceSet],
    root: Path,
) -> None:
    document_ids = {document.document_id for document in manifest.documents}
    case_ids = [question.case_id for question in questions]
    if len(case_ids) != len(set(case_ids)):
        raise BundleIntegrityError("question case IDs must be unique")
    for document in manifest.documents:
        path = root / document.path
        if not path.is_file():
            raise BundleIntegrityError(f"missing document: {document.path}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != document.sha256:
            raise BundleIntegrityError(f"document checksum mismatch: {document.path}")
        if document.canonical_path is not None:
            canonical_path = root / document.canonical_path
            if not canonical_path.is_file():
                raise BundleIntegrityError(
                    f"missing canonical document: {document.canonical_path}"
                )
        elif not document.mime_type.startswith("text/"):
            raise BundleIntegrityError(
                f"binary document {document.document_id!r} requires canonical_path"
            )
    for question in questions:
        if question.gold_answer_id not in answers:
            raise BundleIntegrityError(
                f"{question.case_id} references unknown answer {question.gold_answer_id}"
            )
        if question.gold_evidence_set_id not in evidence_sets:
            raise BundleIntegrityError(
                f"{question.case_id} references unknown evidence set "
                f"{question.gold_evidence_set_id}"
            )
    canonical_documents = _canonical_documents(manifest, root)
    formal_profile = manifest.metadata.get("validation_profile") == "formal"
    for evidence_set in evidence_sets.values():
        unknown_documents = {
            item.document_id
            for item in evidence_set.evidence
            if item.document_id not in document_ids
        }
        if unknown_documents:
            raise BundleIntegrityError(
                f"evidence references unknown documents: {sorted(unknown_documents)}"
            )
        for evidence in evidence_set.evidence:
            canonical = canonical_documents[evidence.document_id]
            _validate_evidence_locator(evidence, canonical, formal_profile)
            if (
                formal_profile
                and evidence.quote_anchor
                and normalize_text(canonical).count(normalize_text(evidence.quote_anchor))
                != 1
            ):
                raise BundleIntegrityError(
                    f"{evidence.evidence_id}: quote_anchor must be unique within "
                    f"document {evidence.document_id} for formal bundles"
                )


def _canonical_documents(
    manifest: DatasetBundleManifest, root: Path
) -> dict[str, str]:
    contents: dict[str, str] = {}
    for document in manifest.documents:
        path = root / (document.canonical_path or document.path)
        try:
            contents[document.document_id] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise BundleIntegrityError(
                f"canonical content for {document.document_id!r} is not UTF-8 text"
            ) from exc
    return contents


def _validate_evidence_locator(evidence, canonical: str, formal_profile: bool) -> None:
    locator = evidence.locator
    if isinstance(locator, TextSpanLocator):
        if locator.end > len(canonical):
            raise BundleIntegrityError(
                f"{evidence.evidence_id}: text_span is outside canonical content"
            )
        span = canonical[locator.start : locator.end]
        if evidence.quote_anchor and normalize_text(span) != normalize_text(evidence.quote_anchor):
            raise BundleIntegrityError(
                f"{evidence.evidence_id}: text_span does not match quote_anchor"
            )
        if evidence.canonical_value and normalize_text(evidence.canonical_value) not in normalize_text(span):
            raise BundleIntegrityError(
                f"{evidence.evidence_id}: text_span does not cover canonical_value"
            )
        return
    if not formal_profile:
        return
    if not isinstance(locator, (ObjectLocator, TableCellLocator, PageRegionLocator)):
        return
    if not _canonical_has_structured_witness(canonical, locator, evidence.canonical_value):
        raise BundleIntegrityError(
            f"{evidence.evidence_id}: formal structured evidence requires one canonical "
            "JSON record containing the complete locator and canonical_value"
        )


def _canonical_has_structured_witness(
    canonical: str,
    locator: ObjectLocator | TableCellLocator | PageRegionLocator,
    canonical_value: str | None,
) -> bool:
    """Check an exact structured locator and value in one canonical JSON record.

    A formal Bundle cannot establish a table cell or object identity by finding
    independent strings somewhere in a large document.  Canonical files may be
    JSON or JSON Lines and must provide a record carrying all locator fields.
    """

    for record in _canonical_json_records(canonical):
        if not _record_matches_locator(record, locator):
            continue
        if canonical_value is None:
            return True
        rendered = json.dumps(record, ensure_ascii=False, sort_keys=True)
        if normalize_text(canonical_value) in normalize_text(rendered):
            return True
    return False


def _canonical_json_records(canonical: str) -> list[dict[str, object]]:
    values: list[object] = []
    try:
        values.append(json.loads(canonical))
    except json.JSONDecodeError:
        for line in canonical.splitlines():
            if not line.strip():
                continue
            try:
                values.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    records: list[dict[str, object]] = []
    for value in values:
        records.extend(_walk_json_records(value))
    return records


def _walk_json_records(value: object) -> list[dict[str, object]]:
    if isinstance(value, dict):
        records = [value]
        for child in value.values():
            records.extend(_walk_json_records(child))
        return records
    if isinstance(value, list):
        return [record for child in value for record in _walk_json_records(child)]
    return []


def _record_matches_locator(
    record: dict[str, object],
    locator: ObjectLocator | TableCellLocator | PageRegionLocator,
) -> bool:
    if isinstance(locator, ObjectLocator):
        return (
            _same_json_value(record.get("object_type"), locator.object_type)
            and _same_json_value(record.get("object_id"), locator.object_id)
        )
    if isinstance(locator, TableCellLocator):
        return (
            _same_json_value(record.get("table_id"), locator.table_id)
            and _same_json_value(record.get("row"), locator.row)
            and _same_json_value(record.get("column"), locator.column)
        )
    return (
        _same_json_value(record.get("page"), locator.page)
        and _same_json_value(record.get("x0"), locator.x0)
        and _same_json_value(record.get("y0"), locator.y0)
        and _same_json_value(record.get("x1"), locator.x1)
        and _same_json_value(record.get("y1"), locator.y1)
    )


def _same_json_value(actual: object, expected: object) -> bool:
    if isinstance(expected, float):
        return isinstance(actual, (int, float)) and float(actual) == expected
    return actual == expected


class BundleIntegrityError(ValueError):
    pass
