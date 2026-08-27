# Canonical Evidence Provenance Bridge Report

**Date:** 2026-08-28  
**Decision:** BLOCKED — bridge implementation and offline validation pass; the
required real 4-case reruns could not start because this execution environment
rejects all local loopback `bind` calls.

This report contains no private DOCX body, question wording, answer value, or
evidence quote.

## Scope and invariants

- The existing four-case canonical Bundle was used unchanged:
  `4045b77c905d7a8400b4cf27fd1eb040d418466e5e69b35f2df67ae0ae86b5c2`.
- No case, Question, Gold Answer, Gold Evidence, scorer, metric, comparison
  rule, or RunExecutor semantic was changed.
- The native-DOCX diagnostic view was not mixed into this bridge.
- The private source remains in local product/run storage only.

## 1. Where provenance was lost

| Boundary | Before the bridge | Consequence |
|---|---|---|
| Bundle → Platform staging | `source_only_documents()` copied only the execution source and dropped `manifest.canonical_path`. | The worker could not see the canonical object sidecar. |
| Adapter → LightRAG upload | Only the Markdown source was uploaded. No canonical map entered the run-scoped adapter state. | LightRAG had no object vocabulary to attach to a chunk. |
| LightRAG chunking → storage | Built-in chunkers emitted private `_source_span`, but `build_chunks_dict_from_chunking_result()` stripped it. | The persisted `text_chunks` row had no source interval. |
| Storage → retrieval trace | Vector results were projected directly into the raw trace and the valid chunk projection dropped `full_doc_id` and source span. | Raw/ranked/final traces could not prove which source interval was retrieved. |
| Adapter normalize → Artifact | `_evidence_items()` always emitted `locator=None`. | Artifact evidence had document/file identity but no canonical object locator. |
| Artifact → metric | No loss occurs here. Existing evidence matching already supports exact object locators. | The old `Recall=0` was unobservable provenance, not yet a semantic miss. |

## 2. Implemented bridge

### Canonical source map

The adapter reads the staged `canonical/evidence.jsonl` sidecar and builds a
deterministic `CanonicalDocumentMap`. For canonicalizer v1 it aligns records to
the exact execution-Markdown rendering using line boundaries, body order, and
exact strings only. It does not read Gold and does not search for an answer.

Each aligned object records only provenance metadata:

- `document_id`, `object_id`, `object_type`, and status;
- half-open canonical source span `{start, end}`;
- object locator (`ObjectLocator` or `TableCellLocator`);
- SHA-256 witness digest of the source interval; and
- alignment method.

Ambiguous, unsupported, missing, or non-round-tripping records remain in
diagnostics and do not become exact locators.

### Runtime map

After ingestion, the adapter reads the authoritative run-scoped LightRAG
`text_chunks` JSON KV store (the adapter explicitly configures this backend).
For every stored runtime chunk it persists a local
`canonical-provenance-map.json` containing:

```text
runtime_chunk_id
  → document_id
  → runtime source span
  → source/content witness digests
  → intersecting canonical object IDs and spans

canonical object ID
  → runtime chunk IDs with full/partial coverage
```

The file contains no source body. Its digest is returned in ingestion details
and in query native metadata.

### Retrieval and Artifact projection

LightRAG now persists the validated public `source_span` alongside each chunk,
joins it back from `text_chunks` after vector search, and carries it through
raw, ranked, and final-context evaluation traces.

The adapter verifies that a query trace's span and content digest match the
ingestion map. A full object coverage is projected as an exact locator into the
existing `RAGEvidenceItem`. If one runtime chunk covers multiple objects, it is
represented by deterministic same-rank provenance projections sharing the same
`runtime_chunk_id`. Partial overlap is retained in metadata but deliberately
has no exact locator. Missing or mismatched provenance is also retained as a
diagnostic item with `locator=None`.

This preserves the existing scorer's ranking and locator semantics. No Gold-aware
selection, answer substring matching, fuzzy matching, or scorer change was
introduced.

## 3. Mapping contract

The bridge uses half-open UTF-8 Python character intervals against the exact
uploaded execution source. A mapping is exact only when:

1. the runtime span is structurally valid and in bounds;
2. the runtime chunk content equals the source witness at that span;
3. the ingestion map and query trace carry the same runtime span; and
4. the runtime interval fully covers the canonical object interval.

Otherwise the observable state is `partial` or `missing`; it is never upgraded
to an exact Gold hit.

The map is independent of Gold. Gold matching still happens only in the
existing `provenance-evidence-groups` scorer.

## 4. Real canonical source audit

The unchanged Bundle's canonical sidecar contains 8,241 object records. Exact
canonicalizer-v1 alignment produced 6,496 object spans and 148 explicit
alignment diagnostics. The four approved cases' Gold object locators are
supported body blocks and both distinct block IDs used by the cases have an
aligned source span. No private source text is reproduced here.

The prior canonical runs remain the pre-bridge baseline:

- Legacy: `4ee55a24304f4ae8bb1874c4c117abe4`;
- Enhanced: `20bc5e70446c49279cdf4e24e229e987`.

Those runs contain no bridge metadata and therefore cannot be retroactively
classified. Their observed zero retrieval recall must remain **unclassified**
until the same Bundle is executed through the new bridge.

## 5. Tests

### Platform

- Full suite under the dependency-complete local environment: **85 passed, 3
  skipped**.
- Added a staging regression proving the canonical sidecar is copied into the
  worker sandbox with a safe name and verified digest.

### LightRAG core

- Provenance/retrieval/chunk regressions: **107 passed** in the exercised suite.
- Added storage and trace regressions for persisted source spans and raw trace
  round-trip.

### LightRAG adapter

- Provenance and adapter regressions: **18 passed**.
- Coverage includes canonical object → runtime chunk, runtime chunk → object,
  one chunk covering multiple objects, one object spanning multiple chunks,
  overlapping intervals, exact Gold locator matching, and missing/partial
  fail-closed behavior.

## 6. Required rerun status

No new LightRAG Legacy or Enhanced run ID was created. The attempted Platform
job failed before a worker/run was allocated with:

```text
PermissionError: [Errno 1] Operation not permitted
```

The same restriction is reproducible with a minimal `socket.bind((127.0.0.1,
0))` probe in this environment. The privileged rerun request was rejected by
the host usage-limit policy. It is therefore not valid to report retrieval
Recall, MRR, Gold Rank, `REAL_RETRIEVAL_MISS`, or `PROVENANCE_MATCHED` for this
bridge attempt.

The required comparison was consequently not run. Existing comparison and
metric semantics remain untouched.

## 7. Limitations

1. The current adapter reads the configured JSON KV text-chunk store to create
   the ingestion-time reverse map. A future non-JSON backend needs an explicit
   read-only chunk-provenance API; it must not fall back to text guessing.
2. Canonicalizer v1 did not persist execution character spans in the Bundle,
   so this bridge reconstructs them from exact rendering. Future canonicalizer
   releases should emit an explicit span sidecar and remove this format coupling.
3. A large object split across chunks is observable as partial coverage but is
   intentionally not an exact evidence hit. This protects Gold semantics at
   the cost of recall for object-level evidence that is not fully contained in
   one runtime item.
4. Same-rank projections preserve ranking semantics but can increase the number
   of Artifact evidence rows when a chunk covers many objects. This should be
   monitored on large tables without changing metric definitions.

## 8. Decision and next step

**Canonical Provenance Bridge implementation: PASS.**  
**BYOD-10 bridge acceptance: BLOCKED pending real reruns.**

The bridge is ready for an environment with local loopback worker permission.
At that point, rerun the unchanged four-case Bundle on Legacy and Enhanced,
inspect each Gold item using exact provenance, and only then classify old zero
recalls as `REAL_RETRIEVAL_MISS` or `PROVENANCE_MATCHED`.

**Benchmark Dataset Expansion: do not enter yet.** The provenance contract and
offline tests are in place, but the real retrieval classification and Compare
evidence are still missing.

## Commits

- `c9f414f2` — stage canonical provenance sidecars for workers
- `e3edab52` — preserve runtime chunk source provenance
- `ac05de84` — bridge canonical evidence provenance into retrieval artifacts
