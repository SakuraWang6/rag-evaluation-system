"""Small, manual TXT/Markdown dataset authoring flow for the product layer."""

from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.datasets.bundle import DatasetBundle, DatasetBundleStore, load_bundle
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.runs import safe_id


class DraftModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DraftDocument(DraftModel):
    document_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    filename: str = Field(pattern=r"^[^/\\]+\.(?:txt|md)$")
    content: str = Field(min_length=1)


class DraftCase(DraftModel):
    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    question: str = Field(min_length=1)
    gold_answer: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    span_start: int = Field(ge=0)
    span_end: int = Field(gt=0)

    @model_validator(mode="after")
    def span_has_width(self) -> DraftCase:
        if self.span_end <= self.span_start:
            raise ValueError("evidence selection must have positive width")
        return self


class DatasetDraft(DraftModel):
    draft_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    documents: list[DraftDocument] = Field(min_length=1)
    cases: list[DraftCase] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def document_ids_are_unique(self) -> DatasetDraft:
        identifiers = [item.document_id for item in self.documents]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("document IDs must be unique")
        return self


class DatasetDraftStore:
    def __init__(self, root: Path, staging_root: Path) -> None:
        self.root, self.staging_root = root, staging_root
        self.root.mkdir(parents=True, exist_ok=True)
        self.staging_root.mkdir(parents=True, exist_ok=True)

    def save(self, draft: DatasetDraft) -> DatasetDraft:
        current = draft.model_copy(update={"updated_at": datetime.now(UTC)})
        atomic_write_json(
            self.root / f"{safe_id(current.draft_id)}.json",
            current.model_dump(mode="json"),
        )
        return current

    def get(self, draft_id: str) -> DatasetDraft:
        return DatasetDraft.model_validate_json(
            (self.root / f"{safe_id(draft_id)}.json").read_text(encoding="utf-8")
        )

    def validate(self, draft: DatasetDraft) -> None:
        _validate_draft(draft)
        staging = self._materialize(draft)
        try:
            load_bundle(staging)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def seal(self, draft: DatasetDraft, bundles: DatasetBundleStore) -> DatasetBundle:
        self.validate(draft)
        staging = self._materialize(draft)
        try:
            return bundles.register(staging)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _materialize(self, draft: DatasetDraft) -> Path:
        target = self.staging_root / f"dataset-draft-{draft.draft_id}-{uuid.uuid4().hex}"
        target.mkdir()
        documents_dir = target / "documents"
        documents_dir.mkdir()
        manifest_documents = []
        for document in draft.documents:
            relative = f"documents/{document.document_id}-{document.filename}"
            path = target / relative
            path.write_text(document.content, encoding="utf-8")
            manifest_documents.append(
                {
                    "document_id": document.document_id,
                    "path": relative,
                    "sha256": hashlib.sha256(document.content.encode("utf-8")).hexdigest(),
                    "mime_type": "text/markdown" if document.filename.endswith(".md") else "text/plain",
                }
            )
        atomic_write_json(
            target / "manifest.json",
            {
                "schema_version": 2,
                "name": draft.name,
                "version": draft.version,
                "created_at": datetime.now(UTC).isoformat(),
                "documents": manifest_documents,
                "metadata": {"product_draft_id": draft.draft_id},
            },
        )
        answers, evidence_sets, questions = [], [], []
        text_by_document = {item.document_id: item.content for item in draft.documents}
        for item in draft.cases:
            source = text_by_document[item.document_id]
            selected = source[item.span_start:item.span_end]
            evidence_id = f"evidence-{item.case_id}"
            answer_id = f"answer-{item.case_id}"
            evidence_set_id = f"evidence-set-{item.case_id}"
            answers.append({"gold_answer_id": answer_id, "kind": "text", "canonical": item.gold_answer})
            evidence_sets.append(
                {
                    "gold_evidence_set_id": evidence_set_id,
                    "evidence": [
                        {
                            "evidence_id": evidence_id,
                            "document_id": item.document_id,
                            "locator": {"type": "text_span", "start": item.span_start, "end": item.span_end},
                            "canonical_value": selected,
                            "quote_anchor": selected,
                        }
                    ],
                    "required_groups": [[evidence_id]],
                }
            )
            questions.append(
                {
                    "case_id": item.case_id,
                    "question": item.question,
                    "gold_answer_id": answer_id,
                    "gold_evidence_set_id": evidence_set_id,
                }
            )
        for filename, entries in (
            ("questions.jsonl", questions),
            ("gold_answers.jsonl", answers),
            ("gold_evidence.jsonl", evidence_sets),
        ):
            (target / filename).write_text(
                "".join(json_line(entry) for entry in entries), encoding="utf-8"
            )
        return target


def json_line(value: object) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _validate_draft(draft: DatasetDraft) -> None:
    document_ids = {item.document_id for item in draft.documents}
    case_ids = [item.case_id for item in draft.cases]
    if not draft.cases:
        raise ValueError("dataset draft needs at least one Question / Gold Answer / TextSpan case before sealing")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case IDs must be unique")
    documents = {item.document_id: item for item in draft.documents}
    for case in draft.cases:
        if case.document_id not in document_ids:
            raise ValueError(f"case {case.case_id} references an unknown document")
        document = documents[case.document_id]
        if case.span_end > len(document.content):
            raise ValueError(f"case {case.case_id} TextSpan exceeds the selected document")
        if not document.content[case.span_start:case.span_end].strip():
            raise ValueError(f"case {case.case_id} TextSpan cannot select only whitespace")
