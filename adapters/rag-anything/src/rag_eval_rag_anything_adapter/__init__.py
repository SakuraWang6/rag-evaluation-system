"""RAG-Anything Adapter Worker entry point."""

from rag_eval_rag_anything_adapter.adapter import (
    RAGAnythingAdapter,
    create_worker_definition,
)

__all__ = ["RAGAnythingAdapter", "create_worker_definition"]
