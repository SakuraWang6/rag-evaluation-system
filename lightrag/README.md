# LightRAG evaluation adapter

This package runs inside an Adapter Worker process. It owns a run-scoped
LightRAG API child process and translates Wire Protocol 1.0 requests into
LightRAG ingestion and query calls.

The platform never imports this package or `lightrag`. Register the factory as:

```text
rag_eval_lightrag_adapter:create_worker_definition
```

Version 0.1 intentionally supports the `naive` query mode only. That is the
first LightRAG mode whose native vector, post-ranking, and final-context stages
can all be observed without assigning false semantics to KG entity/relation
retrieval.
