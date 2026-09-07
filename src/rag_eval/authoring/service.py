"""Application service for private DOCX ingest and deterministic analysis."""

from __future__ import annotations

from pathlib import Path

from rag_eval.authoring.canonical import CANONICALIZER_VERSION, DocxCanonicalizer
from rag_eval.authoring.models import AuthoringDataset, AuthoringState, CanonicalView
from rag_eval.authoring.storage import AuthoringWorkspaceStore, authoring_configuration_digest
from rag_eval.authoring.workflow import AuthoringWorkflow
from rag_eval.datasets.formal import (
    FormalDatasetValidator,
    FormalDocumentView,
    build_source_faithful_document_view,
)
from rag_eval.llm import LLMConfigurationService


class AuthoringService:
    """Owns mutable authoring state and does not depend on Evaluation Core."""

    def __init__(
        self,
        root: Path,
        *,
        llm_configuration: LLMConfigurationService | None = None,
        secret_store: object | None = None,
    ) -> None:
        self.store = AuthoringWorkspaceStore(root)
        self.canonicalizer = DocxCanonicalizer()
        self.workflow = AuthoringWorkflow(
            self.store,
            llm_configuration=llm_configuration,
            secret_store=secret_store,
        )
        # A reading projection is derived solely from the current Canonical
        # revision and source DOCX. Keep it in memory for the active Platform
        # process so repeatedly opening evidence never reparses the document.
        self._document_views: dict[tuple[str, str], FormalDocumentView] = {}

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
        # A re-analysis is a new Canonical interpretation.  Keep its parser,
        # canonicalizer, and configuration provenance aligned so a later
        # DocumentRevision can be validated against the emitted manifest.
        source = dataset.source.model_copy(
            update={
                "canonicalizer_identity": CANONICALIZER_VERSION,
                "configuration_digest": authoring_configuration_digest(),
            }
        )
        self._document_views = {
            key: view
            for key, view in self._document_views.items()
            if key[0] != authoring_dataset_id
        }
        try:
            workspace = self.store.workspace(authoring_dataset_id)
            result = self.canonicalizer.canonicalize(
                source_path=self.store.source_path(authoring_dataset_id),
                output_root=workspace,
                source_sha256=source.sha256,
                configuration_digest=source.configuration_digest,
                parser_identity=source.parser_identity,
            )
        except Exception as exc:
            self.store.save(dataset.model_copy(update={"state": AuthoringState.FAILED, "failure": str(exc)}))
            raise
        view = result.view(root=workspace, source_sha256=dataset.source.sha256)
        analyzed = self.store.save(
            dataset.model_copy(
                update={
                    "source": source,
                    "state": AuthoringState.ANALYZED,
                    "document_id": result.document_id,
                    "canonical_digest": result.canonical_digest,
                    "canonical_contract_digest": result.canonical_contract_digest,
                    "analysis": {
                        "canonical_view": view.model_dump(mode="json"),
                        "record_count": result.diagnostics["record_count"],
                        "records_by_status": result.diagnostics["records_by_status"],
                        "records_by_object_type": result.diagnostics["records_by_object_type"],
                        "canonical_contract": result.diagnostics["canonical_contract"],
                        "rich_content": result.diagnostics.get("rich_content", {}),
                        "package_rich_content": result.diagnostics.get("package", {}),
                    },
                    "failure": None,
                }
            )
        )
        self.workflow.ledger.ensure_dataset(analyzed)
        return analyzed

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

    def document_view(self, authoring_dataset_id: str) -> FormalDocumentView:
        """Return the same source-faithful reading projection used by releases.

        The current Canonical Contract remains the authority.  This method is
        only a local, read-only projection for an author to inspect a proposed
        question's source in the original document order.
        """

        dataset = self.store.get(authoring_dataset_id)
        cache_key = (authoring_dataset_id, dataset.canonical_digest or "")
        cached = self._document_views.get(cache_key)
        if cached is not None:
            return cached
        canonical = FormalDatasetValidator._load_canonical_document(dataset, self.store)
        view = build_source_faithful_document_view(
            canonical=canonical,
            source_path=self.store.source_path(authoring_dataset_id),
            filename=dataset.source.original_filename,
        )
        self._document_views[cache_key] = view
        return view

    def delete(self, authoring_dataset_id: str) -> None:
        """Delete only a workspace the user has explicitly archived first."""

        self.store.delete_archived(authoring_dataset_id)
        self._document_views = {
            key: view
            for key, view in self._document_views.items()
            if key[0] != authoring_dataset_id
        }

    def archive(self, authoring_dataset_id: str) -> AuthoringDataset:
        return self.store.archive(authoring_dataset_id)
