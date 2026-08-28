# LightRAG evaluation adapter

This package runs inside an Adapter Worker process. It owns a run-scoped
LightRAG API child process and translates Wire Protocol 1.0 requests into
LightRAG ingestion and query calls.

It is downstream of Platform Authoring: a private DOCX is authored and
reviewed in the Platform, exported as a sealed Dataset Bundle, and only then
provided to this Worker. Authoring, Gold, metrics, and comparison remain
outside this package.

The platform never imports this package or `lightrag`. Register the factory as:

```text
rag_eval_lightrag_adapter:create_worker_definition
```

Version 0.1 intentionally supports the `naive` query mode only. That is the
first LightRAG mode whose native vector, post-ranking, and final-context stages
can all be observed without assigning false semantics to KG entity/relation
retrieval.

`legacy` is the default profile: exact-ID, table augmentation, structured
ranking and reranking are disabled. `structured` is an explicit experiment
profile. Reranking requires an explicit `rerank_model`; the Worker never
inherits it from a shell. Generation model, temperature, seed, prompt and
response type are explicit config and cache use is disabled/reported for
latency-controlled runs. These profiles are retained for reproducible
diagnostics; no ranking optimization is part of the consolidation baseline.
