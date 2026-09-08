# LightRAG Native DOCX Observation

Phase 4 adds an Adapter-owned Wire 2.0 shadow observation to the existing
LightRAG `source_document` route. It does not replace Wire 1.0 execution yet,
and it does not add another Benchmark or corpus mode.

## Boundary

```text
Original DOCX bytes
  -> LightRAG native upload/parser/chunker/index
  -> authoritative kv_store_text_chunks.json
  -> one LightRAG query with evaluation_trace=true
  -> Adapter validation and canonical projection
  -> AdapterRunResultV2 / UnifiedTrace (shadow)
```

The Adapter consumes only runtime state and the Platform-produced Canonical
Catalog. It never consumes Gold, changes a question, injects candidates,
reorders results, rewrites context, or issues a second query. The existing
`RAGResult` remains the live execution result until the Run migration in Phase
6.

The Wire 2.0 shadow result is exposed under:

```text
RAGResult.trace.wire_v2_native_observation
```

An admitted observation has `observation_status=observed`, an
`adapter_run_result`, and a verified Wire 1.0/Wire 2.0 stage comparison. An
observation construction or integrity failure is persisted as `corrupted` or
`failed` without changing the native answer or the legacy result.

## Ingestion observation

Formal observation is currently admitted only when one `source_document` DOCX
has one supported Canonical Catalog and one authoritative LightRAG text-chunk
store. The Adapter freezes:

- exact native document and chunk IDs;
- exact chunk content and SHA-256;
- native parser lineage and its digest;
- rendered-stream spans when supplied;
- parser and chunker identities;
- persisted metadata digest;
- original DOCX source SHA and Canonical Catalog SHA.

The source checksum is verified against the unchanged uploaded DOCX before
native ingestion. The stored chunk content and lineage are then independently
checked against the generated provenance map. Missing or inconsistent runtime
identity fails closed; the Adapter does not reconstruct it from text.

## Canonical coverage proof

Mapping priority remains:

```text
native lineage
  > deterministic verified canonical crosswalk
  > missing
```

No fuzzy or semantic fallback is implemented. Direct native edges require the
same source identity, structural locator, canonical witness, native content
hash, and native-lineage receipt. Duplicate text is harmless because text is a
witness after a unique structural selection, never the selector.

The deterministic crosswalk adds two proof-preserving projections:

1. A fully verified authored paragraph can prove its canonical `text_span`
   child.
2. Verified physical table cells can prove logical-cell and table extents.

Table and logical-cell extents are sets of physical-cell atoms. This permits:

- one runtime chunk to cover several canonical evidence objects;
- several row-split chunks to union into one complete logical cell or table;
- horizontal and vertical merge metadata to remain part of the receipt;
- a partial chunk edge to stay partial while the reverse run-level union is
  complete.

Every positive edge has a content-bound receipt. Every canonical object has a
reverse record with `complete`, `partial`, `missing`, or `unsupported` status.
Forward and reverse records are validated as an exact round trip by the shared
Wire 2.0 contract. Canonical objects that LightRAG cannot prove remain in the
same Benchmark and Catalog; only their metric availability is affected in a
later phase.

## Stage observation and transformation profile

The native trace records candidate, ranked, and final-context items with exact
ID, rank, content, score, and provenance receipt references. The current
`naive` legacy profile declares:

```text
candidate --identity_subset--> ranked --identity_subset--> context
```

LightRAG can deduplicate, filter, rerank, and apply context/token cutoffs while
retaining native chunk identity. It does not currently emit a new compressed
or merged content identity in this profile, so no `TransformationRecord` is
fabricated.

Structured explicit-ID retrieval is different: LightRAG's current raw hook is
known to omit candidates injected between raw retrieval and ranking. For that
runtime profile, candidate observation is `observed + partial` and the
candidate-to-ranked transition is `unobservable`. Ranked/context observation
can still be independently useful, but the Adapter does not claim a false
subset or complete candidate set.

If a future context stage emits merged, summarized, expanded, or compressed
content, it must declare `verified_derivation` and supply transformation plus
output-level canonical coverage receipts. Until then, a new or changed context
identity fails validation and cannot silently inherit source-chunk coverage.

## Shadow and compatibility guarantees

Wire 2.0 is built from the exact response already used for Wire 1.0. The
Adapter compares each observed stage on:

```text
native ID + rank + content + runtime score
```

A mismatch marks the shadow observation corrupted. It never causes a second
retrieval or substitutes the new data into the live result. The legacy
`canonical_segments` and `benchmark_segments` paths remain runnable as
migration oracles and report the formal native Wire 2.0 observation as
unobserved.

## Phase 4 limitations

- The shared `SourceIdentity` is currently single-document, so formal native
  observation admits one DOCX per Adapter session.
- Nested-table Gold remains governed by Canonical Conformance and is currently
  not eligible; the Adapter does not special-case it into eligibility.
- Structured explicit-ID candidate derivation and third-party reranker
  transformations require stronger LightRAG hooks before their cross-stage
  lineage can be declared verified.
- Scoring, failure attribution, Artifact 2.0, API rendering, and route cutover
  remain assigned to Phases 5 through 8.

## Conformance coverage

The Phase 4 tests cover:

- exact original-DOCX upload and source checksum rejection;
- ingestion content/lineage identity and mapping receipts;
- one chunk mapping to multiple canonical objects;
- multiple split-table chunks jointly completing one logical-cell/table
  extent;
- duplicate text with structural disambiguation;
- witness mismatch and invalid spans failing closed;
- regular, split, and vertically merged physical-cell footprints;
- complete versus known-partial candidate observation profiles;
- exact Wire 1.0/Wire 2.0 stage shadow comparison from one query response.
