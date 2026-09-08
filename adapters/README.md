# RAG Evaluation Adapters

Isolated Worker adapters for the RAG Evaluation Platform:

- `lightrag/`: LightRAG adapter with legacy-default parity and opt-in
  experimental profiles.
- `rag-anything/`: RAG-Anything adapter with an answer-only Wire 1.0 surface
  and additive same-execution Wire 2.0 native observation hooks.

Each adapter is installed in its own virtual environment and exposes the
versioned loopback HTTP/JSON Worker Protocol. The platform never imports either
RAG implementation. An adapter receives only source documents, questions, and
run configuration; Gold data and scorer configuration remain platform-side.

Both adapters must pass the same Worker TCK. Capabilities are observational:
`None` means a stage cannot be observed, while `[]` means it was observed
and returned no evidence.

Both native observers also pass the shared Wire 2.0 observation TCK. Adapter
implementations may use different runtime hooks, but they emit the same
`AdapterRunResultV2` and are scored by the same Platform engine.

## Current baseline boundary

The current end-to-end mainline is:

```text
Private DOCX → Platform Authoring → reviewer-approved Dataset Bundle
             → Platform RAG Evaluation → isolated Adapter Worker
```

This repository is the execution boundary only. It does not own private
document Authoring, candidate/review state, Gold data, dataset generation,
ranking policy, metrics, or comparison semantics. The Platform exports and
registers the Bundle before an adapter is started. `legacy` and `structured`
profiles are explicit diagnostic execution choices; this phase does not tune
ranking or change the adapter contract.

For a formal run, `prepare` must resolve each configured model and return a
verified immutable digest/revision. The Platform compares that identity to the
frozen model lock before ingestion. Mutable names and tags (including
`latest`) are display/resolver inputs only. Each adapter reports explicit
answer/query/LLM cache state, clears inherited experimental LightRAG controls,
and returns an index input fingerprint plus the actual run-scoped index digest.

The repository intentionally has no shared runtime environment. Install each
adapter from its own directory into a dedicated Worker venv. For local tests,
install the Platform and Adapter workspace members and run from the monorepo
root:

```bash
pytest -q tests/rag_eval_adapters
```
