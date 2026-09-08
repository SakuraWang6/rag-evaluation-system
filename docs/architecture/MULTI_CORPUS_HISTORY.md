# Multi-Corpus History

- Status: architectural reconstruction from repository state, retained audit reports, and Git history
- Target decision: only native document ingestion remains a future formal route
- Terminology: “pre-segmented” includes inputs whose boundaries are produced by the Platform and then required to survive RAG ingestion unchanged

## Executive answer

The three LightRAG corpus modes were not created because the product needed three equivalent ways to evaluate RAG. They are successive responses to a provenance problem:

1. `source_document` exercised the real RAG path, but the early system could not reliably relate native DOCX chunks to Platform-owned canonical evidence.
2. `canonical_segments` removed most parser-alignment uncertainty by rendering canonical objects into deterministic, digest-pinned batches before ingestion while retaining the ordinary Canonical Gold and generic scorer.
3. `benchmark_segments` tightened the controlled unit to one immutable leaf and one exact runtime chunk, then introduced typed segment traces and segment-native Gold/scorers for reproducible cross-system ranking.

Each step bought stronger measurement reliability by controlling more of the input boundary. The architectural cost was increasing distance from a complete native RAG evaluation. The target is therefore not to choose among three permanent routes. It is to migrate their integrity and validation properties into `source_document`, use the pre-segmented modes temporarily as characterization oracles, and then stop creating new formal runs on them.

## Evidence and limits of the historical reconstruction

The repository contains enough artifacts to reconstruct the causal sequence, but not enough to claim an exact feature-by-feature chronology:

- Git history shows the Platform/Adapter extraction in August 2026, private-DOCX authoring work, and later canonical-sidecar/provenance/equivalence work.
- Several large Platform, Adapter, and WebUI states were imported as “frozen dirty baseline” commits on 2026-09-07. Their internal feature chronology is not recoverable from Git alone; the preserved component SHAs are recorded in `docs/migration/HISTORY_MAP.md`.
- The retained rehearsal and repair reports explicitly document the native-DOCX mapping failures that motivated a controlled canonical bridge.
- Current contracts and execution branches show the final architectural effect even where the exact sequence of intermediate commits is unavailable.

Accordingly, the sections below distinguish repository evidence from causal inference. The conclusion does not depend on an unverifiable date ordering.

## Causal timeline

### Stage 1 — Preserve the real system under test

The `source_document` route preserves the real system-under-test boundary: the original source document enters the RAG. In the current path, the Platform stages the binary source with a digest, the Adapter uploads it, and LightRAG performs native parsing, chunking, indexing, retrieval, context selection, and answer generation.

That path correctly answers “how did this RAG behave on this DOCX?” It originally failed to answer the equally important measurement question “which canonical Gold object did this returned native chunk come from?”

The retained end-to-end rehearsal is the clearest evidence. For a real DOCX, LightRAG produced 196 chunks. A conservative unique-text bridge could map only 41 of 1,485 observed stage items, or 2.76%; the remainder stayed unmapped (`platform/END_TO_END_RAG_EVALUATION_REHEARSAL_REPORT.md:99-122`). Runtime-only items intentionally contained no canonical IDs, so the low rate was a provenance failure rather than a retrieval failure.

### Stage 2 — Diagnose why text could not bridge native DOCX reliably

The repair analysis identified a coordinate-system mismatch:

```text
Platform canonical object coordinates
≠ DOCX parser's rendered blocks
≠ chunker's native spans and boundaries
```

Exact table matching was especially weak. The report classifies native chunks into exact matches, absent canonical markup, incompatible renderings, duplicate grids, and chunks without usable spans. It also records a duplicate-table case where table 17 and table 39 have equal visible grids but different OOXML body ordinals and paragraph ranges (`platform/docs/EVIDENCE_REPAIR_PLAN.md:92-160`).

The operational lessons were:

- content equality verifies a value but does not establish physical identity;
- rendered DOCX text is not a stable universal source coordinate;
- split tables require real cell/row coverage rather than a table-level string match;
- repeated short paragraphs/cells make “unique quote” assumptions unsafe;
- without a complete reverse map, an absent returned chunk cannot prove a retrieval miss.

These findings made a text-only native bridge unsuitable for formal scoring.

### Stage 3 — Introduce `canonical_segments` as a deterministic bridge

`canonical_segments` projected Platform-owned canonical objects into bounded text batches. The source DOCX remained in the package for presentation/audit, but the effective RAG input became inline, digest-pinned canonical batches (`platform/src/rag_eval/datasets/canonical_segments.py:1-13`, `:318-371`).

The LightRAG Adapter then required each input batch to produce exactly one unchanged persisted chunk and constructed a forward/reverse canonical provenance map. This solved several immediate problems:

- no native DOCX parser rendering had to be aligned to canonical objects;
- every batch carried a known set of canonical source locators;
- content and source spans could be verified exactly after ingestion;
- the existing Bundle, `GoldEvidenceSet`, and generic scorer could remain in use;
- tests could characterize one runtime item with multiple canonical edges without changing rank/cardinality.

The tradeoff was fundamental: the Platform now chose the text envelope and boundaries presented to the RAG. LightRAG still executed its upload/chunk pipeline, but an acceptance rule required its output to preserve those Platform-created boundaries. This measured a constrained canonical-text profile, not the complete DOCX parser/chunker path.

### Stage 4 — Introduce `benchmark_segments` as a stricter cross-system oracle

`benchmark_segments` reduced the unit further. A benchmark leaf has a stable ID, a maximum rendered length, a marker, and a content digest. The contract requires one leaf per `DocumentInput`; the LightRAG Adapter requires exactly one native chunk with exact leaf content and a full source span (`platform/src/rag_eval/contracts/benchmark.py:1-6`, `:52-127`; `platform/src/rag_eval/datasets/benchmark_contract.py:856-908`; `adapters/lightrag/src/rag_eval_lightrag_adapter/adapter.py:1246-1419`).

This added strong reproducibility properties:

- the retrieval unit was immutable and known before ingestion;
- returned IDs, ranks, content, and mapping receipts could be checked strictly;
- split, merge, unknown, duplicate, or mutated leaf mappings could fail closed;
- fixed retrieval cutoffs enabled repeatable cross-system ranking comparisons;
- stage availability and corruption could be represented explicitly.

It also crossed an architectural boundary. `BenchmarkQuestion`/`BenchmarkGold`, `SegmentTraceSet`, `execute_benchmark_case()`, segment retrieval scorers, segment answer scorers, and `segment_*` metric IDs form a second evaluation architecture, not merely another corpus materialization (`platform/src/rag_eval/contracts/benchmark.py:147-177`; `platform/src/rag_eval/contracts/adapter.py:86-156`; `platform/src/rag_eval/execution.py:425-448`, `:951-1017`).

### Important nuance — the Adapter did not use a custom chunk insert API

The LightRAG Adapter posts all three input forms through `/documents/upload` with `process_options="!"` (`adapters/lightrag/src/rag_eval_lightrag_adapter/adapter.py:863-878`). The pre-segmented paths therefore still invoke LightRAG ingestion. They are nevertheless semantically pre-chunked for evaluation because post-ingest acceptance requires each Platform leaf/batch to survive as one exact native chunk. The distinction matters:

- they do not bypass LightRAG with an arbitrary private chunk-record write;
- they do neutralize the freedom of the native parser/chunker to choose meaningful DOCX boundaries.

## What each mode solved and what it cost

| Mode | Immediate problem solved | Reliability gained | Architectural cost | Long-term role |
| --- | --- | --- | --- | --- |
| `source_document` | Exercise the actual DOCX parser/chunker/index | Native behavior and end-to-end fidelity | Historically incomplete/ambiguous canonical provenance; current formal policy remains diagnostic | Sole future formal route |
| `canonical_segments` | Avoid native parser-to-canonical coordinate mismatch | Digest-pinned batches, exact post-ingest verification, ordinary Canonical Gold/scorer, multi-edge characterization | Platform determines text envelopes and effective boundaries | Temporary compatibility and mapping oracle |
| `benchmark_segments` | Make retrieval units strictly comparable and rankable across systems | Immutable leaf IDs/content, receipts, typed stages, exact one-leaf/one-chunk validation, fixed cutoffs | Separate Dataset/Gold/Trace/Scorer/executor/metric family; least native input | Temporary strict contract/scoring oracle |

## Why pre-segmentation became necessary

The repository evidence points to five concrete pressures rather than one abstract design preference.

### 1. Native lineage did not initially survive the full pipeline

The parser, transformations, chunker, persistence layer, and query stages needed a continuous source relation. If any step dropped that relation, the Adapter saw only chunk text and a runtime ID. Native structural lineage and the post-chunk bridge now repair much of this for LightRAG, but those facilities were not available to the early rehearsal.

### 2. Canonical and parser renderings were not equivalent

DOCX paragraphs, headings, lists, tables, merged cells, drawings, and equations can have several text projections. The Platform's canonical object value and LightRAG's rendered chunk content were not guaranteed to share the same whitespace, markup, table layout, or object grouping.

### 3. Duplicate values defeated text identity

Repeated table grids, boilerplate paragraphs, and short cells are valid document content. Hashing the visible value proves equality but cannot select the correct physical source object. A controlled leaf ID avoided the ambiguity, at the cost of replacing native identity with Platform identity.

### 4. Native chunk boundaries did not align with Gold objects

A chunk may contain several canonical objects, and one canonical object—especially a table—may be split across several chunks. Early scorers and mappings benefited from a one-to-one unit because exact Recall@K/MRR accounting was easier. The correct permanent model is one runtime item with zero-to-many edges and many items forming a verified union, not boundary alignment.

### 5. Formal comparison demanded strict, repeatable failure behavior

Cross-system ranking needed stable IDs, known candidate units, fixed cutoffs, and a way to distinguish unsupported stages from empty stages. `benchmark_segments` supplied these quickly. Those are valid contract requirements, but they do not require a permanent segment-native Dataset or scorer.

## Capability disposition

### Preserve and migrate into the native path

These mechanisms solve permanent integrity problems and should survive the route retirement:

- original source, canonical catalog, content, contract, map, and artifact digests;
- stable runtime item IDs and unique native stage ranks;
- known-canonical-ID and locator validation;
- source pin, parser/chunker identity, content hash, and lineage hash checks;
- signed/digested mapping receipts tying runtime identity to provenance edges;
- forward map, reverse map, and object-catalog round-trip validation;
- one runtime item with zero-to-many edges, without rank fan-out;
- gap-free same-object and table-footprint unions across multiple chunks;
- explicit `unsupported`, `unobserved`, `empty`, `corrupted`, `partial`, and `missing` states;
- fail-closed rejection of integrity corruption and fail-closed localization of ambiguity;
- immutable, checksummed artifacts and Gold isolation from the Worker.

### Keep temporarily as characterization infrastructure

These artifacts remain useful during migration but must not define the target:

- canonical and benchmark input fixtures as deterministic oracles;
- one-batch/one-chunk and one-leaf/one-chunk acceptance tests;
- equivalence tests for a frozen canonical-text LightRAG profile;
- old `SegmentTrace` and `segment_*` readers for historical artifacts;
- route comparison pages used to explain differences during the transition;
- `diagnostic_only` labels while native admission gates are incomplete.

### Retire from new formal evaluation

These are route scaffolding rather than permanent reliability properties:

- Platform-rendered canonical batches or benchmark leaves as the system-under-test corpus;
- benchmark markers and leaf-size constraints as retrieval identity;
- segment IDs as formal Gold coordinates;
- separate `BenchmarkQuestion`/`BenchmarkGold` authority;
- `SegmentTraceSet` as a second result contract;
- segment-specific retrieval and answer scorer families;
- `execute_benchmark_case()` and benchmark-only aggregate/metric namespaces;
- a winner/comparison split that treats native DOCX as permanently diagnostic.

## Historical decision in one sentence

The multi-route architecture arose because the project could either preserve native RAG behavior or prove canonical evidence provenance, but could not initially do both; pre-segmentation made provenance deterministic, and the next phase must carry that determinism into native lineage and validation rather than preserve the workaround as a second product architecture.
