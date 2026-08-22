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
    Question,
)
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


class BundleIntegrityError(ValueError):
    pass
