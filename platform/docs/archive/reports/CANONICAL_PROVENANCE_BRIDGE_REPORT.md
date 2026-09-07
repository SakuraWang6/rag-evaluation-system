# Canonical Evidence Provenance Bridge Report

**Date:** 2026-08-28  
**Decision:** PASS — bridge implementation, offline validation, and the required
real four-case Legacy/Enhanced reruns all pass. Retrieval misses are now
separable from partial or unobservable provenance.

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

The prior canonical runs are the pre-bridge baseline:

- Legacy: `4ee55a24304f4ae8bb1874c4c117abe4`;
- Enhanced: `20bc5e70446c49279cdf4e24e229e987`.

Those runs contain no bridge metadata and therefore cannot be retroactively
classified. Their observed zero retrieval recall remains **unclassified**. The
post-bridge reruns described below use the same Bundle, cases, Gold, model lock,
seed, and retrieval configuration.

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

## 6. Real rerun acceptance

The reruns were executed in a host context that permits the local loopback
worker. Both formal runs completed all four cases with no timeout, system error,
or cancellation:

| Profile | Run ID | Cases | Artifact verification |
|---|---|---:|---|
| LightRAG Legacy | `088137b9d3964d1aaf8cfde04da1a93a` | 4/4 | valid; no missing, unexpected, or mismatched files |
| LightRAG Enhanced | `815c9099d9244c2d8d38d3d9c606dc49` | 4/4 | valid; no missing, unexpected, or mismatched files |

Both runs produced the same deterministic provenance-map digest. Each map has
58 runtime chunks, 6,275 reverse-mapped canonical object IDs, and 6,945 mapping
edges. Of the runtime chunks, 56 have full source-span provenance and two have
explicit `missing` provenance. Forward and reverse edge verification found zero
missing or inconsistent round trips in either run.

### Trace observability

Legacy and Enhanced produced identical provenance coverage for this controlled
run:

| Trace stage | Projected items | Runtime chunk ID | Runtime source span | Canonical object locator |
|---|---:|---:|---:|---:|
| raw | 12,083 | 12,083 | 12,081 | 5,600 |
| ranked | 12,083 | 12,083 | 12,081 | 5,600 |
| final context | 3,660 | 3,660 | 3,659 | 1,749 |

The item counts exceed the configured runtime candidate count because one
runtime chunk may deterministically project to many canonical objects at the
same rank. This does not manufacture extra ranks. Every projected item carries
the provenance-map digest; fallback items from the two spanless runtime chunks
remain visible with `provenance_status=missing` and no invented locator.

### Retrieval metrics

No scorer or metric was changed. These are the values emitted by the existing
evaluation pipeline:

| Run | raw Recall@1/@3/@5 | raw MRR | ranked Recall@1/@3/@5 | ranked MRR | final-context Recall@1/@3/@5 |
|---|---|---:|---|---:|---|
| Legacy | 0 / 0 / 0 | 0.0125 | 0 / 0 / 0 | 0.0125 | 0 / 0 / 0 |
| Enhanced | 0 / 0 / 0 | 0.0125 | 0 / 0 / 0 | 0.0125 | 0 / 0 / 0 |

The non-zero MRR with zero Recall@5 is expected: one exact Gold object is at
rank 20. Across four cases, `(1 / 20) / 4 = 0.0125`.

### Per-case Gold classification

The two profiles produced the same classification and Gold ranks:

| Case ID | Legacy raw / ranked / final Gold rank | Enhanced raw / ranked / final Gold rank | Classification | Evidence |
|---|---|---|---|---|
| `case-09a8ceb2fd234fa792053c48363f488b` | — / — / — | — / — / — | `REAL_RETRIEVAL_MISS` | The Gold object has a full runtime mapping, but its runtime chunk was absent from every retrieval stage. |
| `case-6f4c41dbfd8649c1a42f789b82204736` | partial 4,17 / partial 4,17 / partial 4 | partial 4,17 / partial 4,17 / partial 4 | `PARTIAL / UNOBSERVABLE` | The Gold object crosses runtime chunks 002 and 003. Neither chunk fully covers it; partial overlap is visible but intentionally cannot become an exact locator. |
| `case-a68460e6f98542e7be69f243d234c3a6` | 20 / 20 / — | 20 / 20 / — | `PROVENANCE_MATCHED` | Exact canonical Gold locator matched at raw/ranked rank 20 and was dropped before the top-five final context. |
| `case-e81b1553b4d64bbfbd872f95fab83dad` | — / — / — | — / — / — | `REAL_RETRIEVAL_MISS` | The Gold object has a full runtime mapping, but its runtime chunk was absent from every retrieval stage. |

Thus, the prior blanket zero recall did not describe one homogeneous failure:
two cases are real retrieval misses, one is an exact but low-ranked retrieval,
and one cannot be scored as an exact object hit under the current chunk
boundaries. The formal metric remains unchanged and correctly reports the last
partial case as zero rather than weakening Gold.

### Compare

The new runs pass `task_comparable` validation with no compatibility reasons.
All retrieval metrics are comparable at coverage 1.0. `may_declare_winner` is
false: both profiles have identical retrieval results on this four-case run,
and answer accuracy, groundedness, and unsupported-answer rate remain
`needs_review` with zero automatic coverage. No winner is declared.

### Historical environment blocker

The earlier attempt failed before run allocation because that sandbox rejected
local loopback `bind` with `PermissionError: [Errno 1] Operation not permitted`.
It was an execution-environment restriction, not a bridge or worker failure.
The successful reruns above close that blocker.

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
**BYOD-10 bridge acceptance: PASS.**

The required real runs, exact/partial classification, Artifact verification,
round-trip validation, and Compare are complete. The bridge now makes the
difference between retrieval failure, low ranking, final-context selection
loss, and unrepresentable partial evidence observable without changing Gold or
metric semantics.

**Benchmark Dataset Expansion: may proceed, with an evidence-representability
gate.** Before adding many cases, Authoring validation should flag approved
Gold objects that no runtime chunk fully covers for each declared execution
profile. Such cases may remain useful diagnostics, but they must be labeled
partial/unobservable rather than silently counted as ordinary retrieval misses.
The next expansion should also retain the exact provenance audit used here and
must not optimize questions or Gold to the current LightRAG chunker.

## Commits

- `c9f414f2` — stage canonical provenance sidecars for workers
- `e3edab52` — preserve runtime chunk source provenance
- `ac05de84` — bridge canonical evidence provenance into retrieval artifacts
