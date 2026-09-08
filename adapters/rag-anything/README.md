# RAG-Anything Adapter

This package runs inside a dedicated Adapter Worker environment. The Platform
does not import `raganything`, `lightrag`, or this package.

The Worker consumes a sealed Dataset Bundle produced by Platform Authoring.
Private DOCX Authoring, reviewer decisions, Gold data, metrics, and comparison
remain Platform responsibilities. New formal runs submit the original DOCX to
RAG-Anything; the adjacent Canonical Catalog is visible only to the observer
that proves provenance and is never inserted as a second corpus.

The adapter targets the public RAG-Anything 1.3 API:

- text documents use `insert_content_list` so ingestion does not invent a
  parser representation;
- binary documents use `process_document_complete` on the source-only sandbox;
- queries still use `aquery` exactly once;
- storage is run-scoped and a non-empty work directory is rejected.

Wire 1.0 remains the frozen answer-only compatibility surface.  Wire 2.0 adds
an Adapter-owned, same-execution observer for the pinned native `naive`,
non-VLM, no-rerank profile. It delegates to the normal RAG-Anything query and
captures the underlying LightRAG `aquery_llm` result and actual chunk-vector
query without replaying retrieval or generation. The observer publishes:

- the complete run-scoped native chunk catalog;
- the actual ordered candidate prefix and its native cutoff;
- the identity-ranked stage for the proven no-rerank profile;
- the exact final-context chunks returned by the same query;
- content hashes, source/runtime identity, lineage receipts, and a typed
  `UnifiedTrace`.

RAG-Anything modes whose intermediate derivation cannot be proven, VLM paths,
reranked paths, missing hooks, and malformed receipts keep the answer but mark
the affected Wire 2.0 stages `unobserved` or `corrupted`. They never publish an
observed empty list as a substitute. The current canonical bridge uses only an
exact, unique parser-stream crosswalk for paragraph/heading/text-span witnesses;
duplicate text fails closed, split chunks are unioned by verified ranges, and
table/cell evidence stays unavailable until RAG-Anything exposes structural
lineage.

The Platform's shared Wire 2.0 contract, Unified Scorer, Artifact 2.0, API, and
WebUI consume this trace without a RAG-Anything-specific branch. Actual metric
availability is cutoff-driven: if the native profile proves fewer than Top-5,
the corresponding `@5` and `MRR@5` values remain unavailable.

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

See [`RAG_ANYTHING_NATIVE_OBSERVATION.md`](../../docs/architecture/RAG_ANYTHING_NATIVE_OBSERVATION.md)
for the observation proof boundary and rollback contract.
