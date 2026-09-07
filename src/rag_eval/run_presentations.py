"""Append-only product presentation metadata for immutable Runs.

Run manifests are research artifacts and must never be edited to correct a
label in the product UI.  This small ledger keeps human-facing run names
outside ``runs/`` while retaining every rename as a revision.  It intentionally
does not participate in scoring, comparison, replay, or artifact integrity.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.runs import safe_id


class _PresentationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunPresentationDecision(_PresentationModel):
    revision: int = Field(ge=1)
    decision_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    display_name: str = Field(min_length=1, max_length=160)
    source: Literal["user", "migration"] = "user"
    actor: str = Field(default="local-user", min_length=1, max_length=160)
    note: str = Field(default="", max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_nonblank_name(self) -> "RunPresentationDecision":
        if not self.display_name.strip():
            raise ValueError("display_name must not be blank")
        if not self.actor.strip():
            raise ValueError("actor must not be blank")
        return self


class RunPresentationRecord(_PresentationModel):
    schema_version: Literal["run-presentation/1"] = "run-presentation/1"
    run_id: str = Field(min_length=1)
    history: list[RunPresentationDecision] = Field(default_factory=list)

    @property
    def latest(self) -> RunPresentationDecision | None:
        return self.history[-1] if self.history else None

    def api_view(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class RunPresentationStore:
    """One append-only name ledger per Run, stored outside immutable artifacts."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        return self.root / f"{safe_id(run_id)}.json"

    def get(self, run_id: str) -> RunPresentationRecord:
        path = self._path(run_id)
        if not path.is_file():
            return RunPresentationRecord(run_id=run_id)
        record = RunPresentationRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if record.run_id != run_id:
            raise ValueError("run presentation record does not match requested run")
        return record

    def append(
        self,
        *,
        run_id: str,
        display_name: str,
        actor: str = "local-user",
        note: str = "",
        source: Literal["user", "migration"] = "user",
    ) -> RunPresentationRecord:
        """Append a new label revision without ever touching the Run directory."""

        current = self.get(run_id)
        decision = RunPresentationDecision(
            revision=len(current.history) + 1,
            display_name=display_name.strip(),
            source=source,
            actor=actor.strip(),
            note=note.strip(),
        )
        updated = current.model_copy(update={"history": [*current.history, decision]})
        atomic_write_json(self._path(run_id), updated.model_dump(mode="json"))
        return updated


__all__ = [
    "RunPresentationDecision",
    "RunPresentationRecord",
    "RunPresentationStore",
]
