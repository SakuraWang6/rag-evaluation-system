"""Local, product-scoped storage for private document authoring."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, TypeVar

from pydantic import BaseModel

from rag_eval.authoring.models import AuthoringDataset, AuthoringState, SourceManifest
from rag_eval.storage.atomic import atomic_write_bytes, atomic_write_json
from rag_eval.storage.runs import safe_id


ModelT = TypeVar("ModelT", bound=BaseModel)


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PARSER_IDENTITY = "rag-eval-authoring-ooxml/1"
CANONICALIZER_IDENTITY = "rag-eval-authoring-canonicalizer/1"
MAX_DOCX_BYTES = 128 * 1024 * 1024
MAX_DOCX_MEMBERS = 10_000
MAX_DOCX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
WORKSPACE_DIRECTORIES = (
    "source",
    "canonical",
    "targets",
    "candidates",
    "reviews",
    "approved",
    "exports",
    "diagnostics",
)


class AuthoringStorageError(ValueError):
    """An invalid input or impossible workspace state."""


def authoring_configuration_digest() -> str:
    """Digest limits and identities that influence interpretation of a source."""

    payload = {
        "canonicalizer": CANONICALIZER_IDENTITY,
        "max_docx_bytes": MAX_DOCX_BYTES,
        "max_docx_members": MAX_DOCX_MEMBERS,
        "max_docx_uncompressed_bytes": MAX_DOCX_UNCOMPRESSED_BYTES,
        "parser": PARSER_IDENTITY,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def inspect_docx_package(payload: bytes) -> dict[str, Any]:
    """Validate the OOXML ZIP envelope without extracting user-controlled paths."""

    if not payload:
        raise AuthoringStorageError("uploaded DOCX is empty")
    if len(payload) > MAX_DOCX_BYTES:
        raise AuthoringStorageError("uploaded DOCX exceeds the 128 MiB limit")
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        raise AuthoringStorageError("uploaded file is not a valid OOXML ZIP package")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as package:
            infos = package.infolist()
            if len(infos) > MAX_DOCX_MEMBERS:
                raise AuthoringStorageError("DOCX contains too many ZIP members")
            names: list[str] = []
            total_uncompressed = 0
            for info in infos:
                name = info.filename
                normalized = PurePosixPath(name)
                if (
                    normalized.is_absolute()
                    or ".." in normalized.parts
                    or "\\" in name
                    or not name
                ):
                    raise AuthoringStorageError("DOCX contains an unsafe ZIP member path")
                if info.flag_bits & 0x1:
                    raise AuthoringStorageError("encrypted DOCX packages are not supported")
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                    raise AuthoringStorageError("DOCX expands beyond the 512 MiB safety limit")
                names.append(name)
            required = {"[Content_Types].xml", "word/document.xml"}
            missing = sorted(required.difference(names))
            if missing:
                raise AuthoringStorageError(
                    "OOXML package is missing required part(s): " + ", ".join(missing)
                )
            return {
                "member_count": len(infos),
                "uncompressed_bytes": total_uncompressed,
                "has_styles": "word/styles.xml" in names,
                "has_document_relationships": "word/_rels/document.xml.rels" in names,
                "parts": sorted(names),
            }
    except zipfile.BadZipFile as exc:
        raise AuthoringStorageError("uploaded file is not a readable OOXML ZIP package") from exc


class AuthoringWorkspaceStore:
    """Owns workspace files; it never reads or writes Dataset Bundle storage."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def workspace(self, authoring_dataset_id: str) -> Path:
        identifier = safe_id(authoring_dataset_id)
        candidate = (self.root / identifier).resolve()
        if candidate.parent != self.root.resolve():
            raise AuthoringStorageError("invalid authoring dataset ID")
        return candidate

    def create(self, *, filename: str, payload: bytes) -> AuthoringDataset:
        self._validate_filename(filename)
        package_inventory = inspect_docx_package(payload)
        identifier = uuid.uuid4().hex
        workspace = self.workspace(identifier)
        workspace.mkdir()
        for directory in WORKSPACE_DIRECTORIES:
            (workspace / directory).mkdir()
        digest = hashlib.sha256(payload).hexdigest()
        now = datetime.now(UTC)
        source = SourceManifest(
            original_filename=filename,
            sha256=digest,
            size_bytes=len(payload),
            ingested_at=now,
            parser_identity=PARSER_IDENTITY,
            canonicalizer_identity=CANONICALIZER_IDENTITY,
            configuration_digest=authoring_configuration_digest(),
            package_inventory=package_inventory,
        )
        dataset = AuthoringDataset(
            authoring_dataset_id=identifier,
            state=AuthoringState.UPLOADED,
            created_at=now,
            updated_at=now,
            source=source,
        )
        try:
            atomic_write_bytes(workspace / "source" / "original.docx", payload)
            atomic_write_json(workspace / "source" / "manifest.json", source.model_dump(mode="json"))
            self.save(dataset)
        except Exception:
            shutil.rmtree(workspace, ignore_errors=True)
            raise
        return dataset

    def get(self, authoring_dataset_id: str) -> AuthoringDataset:
        path = self.workspace(authoring_dataset_id) / "authoring.json"
        if not path.is_file():
            raise FileNotFoundError(authoring_dataset_id)
        return AuthoringDataset.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[AuthoringDataset]:
        datasets: list[AuthoringDataset] = []
        for workspace in sorted(self.root.iterdir()):
            if workspace.is_dir() and (workspace / "authoring.json").is_file():
                datasets.append(
                    AuthoringDataset.model_validate_json(
                        (workspace / "authoring.json").read_text(encoding="utf-8")
                    )
                )
        return datasets

    def save(self, dataset: AuthoringDataset) -> AuthoringDataset:
        workspace = self.workspace(dataset.authoring_dataset_id)
        if not workspace.is_dir():
            raise FileNotFoundError(dataset.authoring_dataset_id)
        current = dataset.model_copy(update={"updated_at": datetime.now(UTC)})
        atomic_write_json(workspace / "authoring.json", current.model_dump(mode="json"))
        return current

    def delete(self, authoring_dataset_id: str) -> None:
        workspace = self.workspace(authoring_dataset_id)
        if not workspace.is_dir():
            raise FileNotFoundError(authoring_dataset_id)
        # `workspace()` has already resolved and constrained this target to one child.
        shutil.rmtree(workspace)

    def source_path(self, authoring_dataset_id: str) -> Path:
        return self.workspace(authoring_dataset_id) / "source" / "original.docx"

    def canonical_path(self, authoring_dataset_id: str, name: str) -> Path:
        return self.workspace(authoring_dataset_id) / "canonical" / safe_id(name)

    def target_path(self, authoring_dataset_id: str) -> Path:
        return self.workspace(authoring_dataset_id) / "targets" / "targets.json"

    def candidate_path(self, authoring_dataset_id: str, candidate_id: str) -> Path:
        return self.workspace(authoring_dataset_id) / "candidates" / f"{safe_id(candidate_id)}.json"

    def representability_profile_path(
        self, authoring_dataset_id: str, profile_id: str
    ) -> Path:
        root = self.workspace(authoring_dataset_id) / "diagnostics" / "representability"
        root.mkdir(exist_ok=True)
        return root / f"{safe_id(profile_id)}.json"

    def review_path(self, authoring_dataset_id: str, review_id: str) -> Path:
        return self.workspace(authoring_dataset_id) / "reviews" / f"{safe_id(review_id)}.json"

    def approved_path(self, authoring_dataset_id: str, case_id: str) -> Path:
        return self.workspace(authoring_dataset_id) / "approved" / f"{safe_id(case_id)}.json"

    def export_path(self, authoring_dataset_id: str, release_id: str) -> Path:
        return self.workspace(authoring_dataset_id) / "exports" / safe_id(release_id)

    def save_model(self, path: Path, value: BaseModel) -> None:
        workspace = self.workspace_from_path(path)
        if not workspace.is_dir():
            raise FileNotFoundError(workspace.name)
        atomic_write_json(path, value.model_dump(mode="json"))

    def load_model(self, path: Path, model: type[ModelT]) -> ModelT:
        if not path.is_file():
            raise FileNotFoundError(path.name)
        return model.model_validate_json(path.read_text(encoding="utf-8"))

    def workspace_from_path(self, path: Path) -> Path:
        """Return the direct workspace child that owns a known authoring path."""

        resolved = path.resolve()
        root = self.root.resolve()
        try:
            relative = resolved.relative_to(root)
        except ValueError as exc:
            raise AuthoringStorageError("path is outside authoring storage") from exc
        if len(relative.parts) < 2:
            raise AuthoringStorageError("path is not inside an authoring workspace")
        return root / relative.parts[0]

    @staticmethod
    def _validate_filename(filename: str) -> None:
        if not filename or Path(filename).name != filename:
            raise AuthoringStorageError("DOCX filename must not contain a path")
        if not filename.lower().endswith(".docx"):
            raise AuthoringStorageError("authoring upload must be one .docx file")
