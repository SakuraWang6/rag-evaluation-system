"""Application service for private DOCX ingest and deterministic analysis."""

from __future__ import annotations

from pathlib import Path

from rag_eval.authoring.canonical import DocxCanonicalizer
from rag_eval.authoring.models import AuthoringDataset, AuthoringState, CanonicalView
from rag_eval.authoring.storage import AuthoringWorkspaceStore
from rag_eval.authoring.workflow import AuthoringWorkflow


class AuthoringService:
    """Owns mutable authoring state and does not depend on Evaluation Core."""

    def __init__(self, root: Path) -> None:
        self.store = AuthoringWorkspaceStore(root)
        self.canonicalizer = DocxCanonicalizer()
        self.workflow = AuthoringWorkflow(self.store)

    def upload_docx(self, *, filename: str, payload: bytes) -> AuthoringDataset:
        return self.store.create(filename=filename, payload=payload)

    def get(self, authoring_dataset_id: str) -> AuthoringDataset:
        return self.store.get(authoring_dataset_id)

    def list(self) -> list[AuthoringDataset]:
        return self.store.list()

    def analyze(self, authoring_dataset_id: str) -> AuthoringDataset:
        dataset = self.store.get(authoring_dataset_id)
        if dataset.state not in {AuthoringState.UPLOADED, AuthoringState.ANALYZED, AuthoringState.INTERRUPTED}:
            raise ValueError(f"dataset in state {dataset.state!r} cannot be analyzed")
        try:
            workspace = self.store.workspace(authoring_dataset_id)
            result = self.canonicalizer.canonicalize(
                source_path=self.store.source_path(authoring_dataset_id),
                output_root=workspace,
                source_sha256=dataset.source.sha256,
            )
        except Exception as exc:
            self.store.save(dataset.model_copy(update={"state": AuthoringState.FAILED, "failure": str(exc)}))
            raise
        view = result.view(root=workspace, source_sha256=dataset.source.sha256)
        return self.store.save(
            dataset.model_copy(
                update={
                    "state": AuthoringState.ANALYZED,
                    "document_id": result.document_id,
                    "canonical_digest": result.canonical_digest,
                    "analysis": {
                        "canonical_view": view.model_dump(mode="json"),
                        "record_count": result.diagnostics["record_count"],
                        "records_by_status": result.diagnostics["records_by_status"],
                        "records_by_object_type": result.diagnostics["records_by_object_type"],
                    },
                    "failure": None,
                }
            )
        )

    def canonical_view(self, authoring_dataset_id: str) -> CanonicalView:
        dataset = self.store.get(authoring_dataset_id)
        raw = dataset.analysis.get("canonical_view")
        if not raw:
            raise ValueError("dataset has not been analyzed")
        return CanonicalView.model_validate(raw)

    def canonical_markdown(self, authoring_dataset_id: str) -> str:
        view = self.canonical_view(authoring_dataset_id)
        workspace = self.store.workspace(authoring_dataset_id)
        return (workspace / "canonical" / "execution.md").read_text(encoding="utf-8")

    def delete(self, authoring_dataset_id: str) -> None:
        self.store.delete(authoring_dataset_id)
