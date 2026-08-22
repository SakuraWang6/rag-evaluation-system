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
