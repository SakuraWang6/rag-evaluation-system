# RAG-Anything Native Observation

- Status: implemented as the Phase 9 bounded native observation profile
- Runtime target: RAG-Anything 1.3.x with LightRAG 1.4.x
- Formal input: one checksum-pinned Original DOCX plus an adjacent Canonical
  Catalog used only by the observer
- Compatibility: Wire 1.0 remains answer-only

## Decision

RAG-Anything continues to own parsing, chunking, indexing, retrieval, context
construction, and generation. The Adapter adds a same-execution observer; it
does not add an evaluation retrieval path.

For `naive + non-VLM + no rerank`, the normal call remains:

```text
RAGAnything.aquery
  -> LightRAG.aquery
     -> LightRAG.aquery_llm
        -> chunks_vdb.query
```

The Adapter installs transparent callback wrappers around the last two calls.
Each wrapper invokes the original exactly once, records the returned value in a
task-local capture, and returns it unchanged. There is no second query and no
reconstructed score or rank. Hooks are restored when the run-scoped runtime is
closed.

## Observed boundaries

The ingestion barrier snapshots the configured run-scoped `JsonKVStorage`:

- `text_chunks` supplies the complete runtime chunk ID/content catalog;
- `full_docs` supplies the native parser text stream when present;
- persisted metadata, parser/chunker/runtime identities, source/catalog pins,
  and content hashes are included in receipt-backed Wire 2.0 records.

The query capture publishes:

- candidate: the exact ordered return from the actual chunk vector query and
  the actual native cutoff;
- ranked: the same identities/order only after observing `enable_rerank=false`;
- context: the exact chunk list in the structured result from the same query;
- answer: the public RAG-Anything return, verified equal to the captured
  structured response.

`candidate -> ranked -> context` is therefore `identity_subset` for this
profile. A new identity, changed content hash, duplicate ID/rank, invalid
cutoff, multiple native query calls, or answer mismatch is corruption.

## Canonical provenance

RAG-Anything 1.3 does not expose OOXML structural lineage through its parsed
text chunks. Phase 9 therefore uses only the last allowed fallback tier:

```text
exact unique parser-stream text -> canonical witness
```

It is deliberately narrower than semantic localization:

- only complete paragraph, heading, and text-span witnesses are admitted;
- both the canonical witness and each chunk must have a unique exact position
  in the captured parser stream;
- interval intersection creates positive partial/complete provenance edges;
- interval union supports several chunks jointly covering one evidence object;
- one chunk may carry edges to several canonical objects;
- duplicate or ambiguous text produces a corruption diagnostic and no edge;
- absent text produces `missing`;
- table/cell objects remain `unsupported` because rendered text cannot prove
  physical/logical cell topology or merges.

No mapping outcome changes Canonical Gold eligibility. It changes only metric
availability for this Adapter run.

## Availability and fallback

The Adapter's Wire 2.0 profile declares the capabilities it can provide, while
each run records the actual status. Non-naive modes, VLM, reranking, missing
hooks, incomplete storage enumeration, and malformed receipts preserve the
answer but mark retrieval/context stages `unobserved`, `unsupported`, or
`corrupted` as appropriate.

The candidate cutoff is the cutoff actually passed to the native chunk vector
query. It may differ from the Platform's requested diagnostic candidate cutoff
because that is native RAG behavior. The shared scorer then makes a metric
unavailable unless the observed prefix proves its required `K`; it never
pretends a larger prefix was observed.

## Architecture test

Both LightRAG and RAG-Anything results pass
`platform/src/rag_eval/adapters/observation_tck.py`, which validates the same
`AdapterRunResultV2`, catalog identity, ordered stage items, and content hashes.
RAG-Anything imports no scorer and adds no Dataset, Run, API, Artifact, or WebUI
branch.

Rollback is a revert of the Phase 9 commit: the frozen answer-only behavior and
all shared Phase 0-8 contracts remain intact.
