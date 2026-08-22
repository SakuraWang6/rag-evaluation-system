"""Trusted local system/adapter registry."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from rag_eval.storage.atomic import atomic_write_json
from rag_eval.storage.runs import safe_id
from rag_eval.worker.process import WorkerCommand


class SystemRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_id: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    adapter_factory: str = Field(pattern=r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")
    python_executable: str = Field(min_length=1)
    environment: dict[str, str] = Field(default_factory=dict)
    request_timeout_seconds: float = Field(default=180.0, gt=0)
    description: str = ""

    def worker_command(self) -> WorkerCommand:
        return WorkerCommand(
            adapter_id=self.adapter_id,
            adapter_factory=self.adapter_factory,
            python_executable=self.python_executable,
            environment=self.environment,
            request_timeout_seconds=self.request_timeout_seconds,
        )


class SystemRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def register(self, registration: SystemRegistration) -> Path:
        executable = Path(registration.python_executable)
        if not executable.is_absolute() or not executable.is_file():
            raise ValueError("python_executable must be an existing absolute file")
        path = self.root / f"{safe_id(registration.system_id)}.json"
        atomic_write_json(path, registration.model_dump(mode="json"))
        return path

    def get(self, system_id: str) -> SystemRegistration:
        path = self.root / f"{safe_id(system_id)}.json"
        return SystemRegistration.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[SystemRegistration]:
        return [
            SystemRegistration.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self.root.glob("*.json"))
        ]
