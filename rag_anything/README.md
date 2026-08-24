# RAG-Anything Adapter

This package runs inside a dedicated Adapter Worker environment. The Platform
does not import `raganything`, `lightrag`, or this package.

The adapter targets the public RAG-Anything 1.3 API:

- text documents use `insert_content_list` so ingestion does not invent a
  parser representation;
- binary documents use `process_document_complete` on the source-only sandbox;
- queries use `aquery`;
- storage is run-scoped and a non-empty work directory is rejected.

RAG-Anything's public query API returns an answer but does not expose the exact
raw retrieval, post-processing/ranked retrieval, or final LLM context. The
adapter therefore declares those capabilities as unavailable and returns
`None`, not an inferred or second-query approximation. Answer accuracy remains
available; retrieval and deterministic groundedness metrics are unavailable.

Example trusted local registration:

```bash
rag-eval system register rag-anything \
  rag-anything \
  rag_eval_rag_anything_adapter:create_worker_definition \
  /absolute/path/to/rag-anything-venv/bin/python
```

The worker environment is expected to contain `raganything`, this adapter, and
`rag-eval-platform`. Model identity is declared in adapter config and is saved
as effective run metadata. Credentials, if any, remain in the trusted local
worker environment and are not copied to the run manifest.

All inherited LightRAG table/exact-ID/ranking/profile and cache environment
variables are cleared before runtime creation. The controlled text track must
use explicit model/generation config; a formal Platform run accepts it only
when the resolver returns the frozen, verified model artifact identities.
