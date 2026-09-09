# RAG-Anything Evaluation Adapter

This package runs RAG-Anything in a dedicated Worker environment. Register its
factory as:

```text
rag_eval_rag_anything_adapter:create_worker_definition
```

`prepare` gives the checksum-pinned Original DOCX to the native RAG-Anything
ingestion path in a run-scoped work directory and returns
`PreparedSystemV2`. `query` executes `RAGAnything.aquery` once and returns the
answer plus an `AdapterRunResultV2` observation of the same execution.

For the admitted `naive`, non-VLM, no-rerank profile, task-local hooks observe
the actual chunk-vector return and structured final context without replaying
retrieval or generation. The Adapter snapshots the native chunk store and
publishes exact IDs, content hashes, ranks, cutoffs and receipts.

RAG-Anything does not currently expose OOXML structural lineage through its
text chunks. Canonical mapping therefore uses only exact, unique parser-stream
witnesses for supported paragraph and text-span objects. Duplicate text fails
closed; split intervals may union; table/cell topology remains unsupported
until the runtime exposes sufficient structural lineage.

Other modes may still answer successfully while affected observations are
`unsupported`, `unobserved`, `partial` or `corrupted`. Metric availability is
then decided by Unified Evaluation; the Adapter never substitutes a zero or
filters Benchmark Gold.

See the [RAG-Anything observation proof boundary](../../docs/architecture/RAG_ANYTHING_NATIVE_OBSERVATION.md)
and the [shared Adapter contract](../README.md).
