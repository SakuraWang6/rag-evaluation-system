# RAG-Anything Native Observation

## Boundary

RAG-Anything owns native parsing, chunking, indexing, retrieval, context and
generation. The Adapter adds same-execution observation and returns
`AdapterRunResultV2` directly.

For an admitted `naive`, non-VLM, no-rerank profile, the native call remains:

```text
RAGAnything.aquery
  -> LightRAG.aquery
     -> LightRAG.aquery_llm
        -> chunks_vdb.query
```

Task-local wrappers invoke the original calls exactly once, capture returned
values and return them unchanged. Hooks are removed with the run-scoped
runtime.

## Observed boundaries

After `prepare`, the ingestion barrier snapshots the run-scoped storage:

- native text chunks provide the runtime catalog;
- full-document storage provides the parser text stream when available;
- metadata, parser/chunker/runtime identities, source/catalog pins and content
  hashes form the ingestion receipt.

The query trace records:

- candidate: exact vector-query order, scores and native cutoff;
- ranked: the same identity order only after proving reranking is disabled;
- context: exact chunks from the structured response;
- answer: the public return, checked against the captured structured result.

For this profile, candidate-to-ranked-to-context is `identity_subset`. A new
identity, changed content hash, duplicate rank/ID, invalid cutoff, multiple
query calls or answer mismatch corrupts the observation.

## Canonical provenance

The pinned runtime does not expose OOXML structural lineage through parsed
text chunks. The Adapter therefore uses the last formal fallback tier: exact,
unique parser-stream text mapped to a canonical witness.

- paragraph, heading and text-span witnesses must each have a unique exact
  parser-stream position;
- interval intersection creates partial or complete edges;
- several chunks may union one canonical extent;
- one chunk may map to several canonical objects;
- duplicate/ambiguous text fails closed;
- absent text is missing; and
- table/cell evidence remains unsupported without topology lineage.

No outcome changes Canonical Gold eligibility.

## Availability

Other query modes, VLM, reranking, absent hooks, incomplete catalog enumeration
or malformed receipts preserve the native answer when possible while marking
affected stages `unsupported`, `unobserved`, `failed` or `corrupted`.

The recorded cutoff is the value actually passed to the native vector query.
If the trace cannot prove a metric's required prefix, Unified Evaluation marks
that metric unavailable rather than enlarging the observation or assigning
zero.

RAG-Anything imports no scorer and adds no Dataset, Run, Artifact, API or
WebUI branch. Its output passes the same shared Adapter TCK as LightRAG.
