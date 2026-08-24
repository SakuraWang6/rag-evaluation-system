# RAG Evaluation Adapters

Isolated Worker adapters for the RAG Evaluation Platform:

- `lightrag/`: LightRAG adapter with legacy-default parity and opt-in
  experimental profiles.
- `rag_anything/`: RAG-Anything adapter using only its public APIs.

Each adapter is installed in its own virtual environment and exposes the
versioned loopback HTTP/JSON Worker Protocol. The platform never imports either
RAG implementation. An adapter receives only source documents, questions, and
run configuration; Gold data and scorer configuration remain platform-side.

Both adapters must pass the same Worker TCK. Capabilities are observational:
`None` means a stage cannot be observed, while `[]` means it was observed
and returned no evidence.

For a formal run, `prepare` must resolve each configured model and return a
verified immutable digest/revision. The Platform compares that identity to the
frozen model lock before ingestion. Mutable names and tags (including
`latest`) are display/resolver inputs only. Each adapter reports explicit
answer/query/LLM cache state, clears inherited experimental LightRAG controls,
and returns an index input fingerprint plus the actual run-scoped index digest.

The repository intentionally has no shared runtime environment. Install each
adapter from its own directory into a dedicated Worker venv. For local tests,
install `rag-eval-platform` separately (or keep its repository as a sibling)
and run:

```bash
pytest -q tests/rag_eval_adapters
```
