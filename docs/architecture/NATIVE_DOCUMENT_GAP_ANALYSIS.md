# Native Document Gap Analysis

> Historical baseline note (Phase 1): this file records the gaps that drove
> the migration. Native observation, unified scoring, Artifact 2.0, and the
> public native-DOCX cutover are now implemented through Phase 8. See
> `MIGRATION_PLAN.md` and `NATIVE_FORMAL_CUTOVER.md` for current status; keep
> the analysis below as the retirement checklist for legacy branches.

- Target: `Original DOCX → RAG-native parse/chunk/index/retrieve → Unified Trace → Unified Scoring`
- Current reference implementation: LightRAG `source_document`
- Required safety rule: an unverifiable relation is `missing` or `partial`, never an inferred hit or miss

## Bottom line

`source_document` is already capable of running a real DOCX through LightRAG's native parser, chunker, index, retrieval, context selection, and answer generation. What it cannot yet guarantee for every formal case is a **complete, adapter-neutral proof from each returned runtime item back to the Platform's canonical source coordinates**.

Historically this gap was severe: a real-DOCX rehearsal produced 196 runtime chunks, but a conservative unique-text bridge mapped only 41 of 1,485 stage items (2.76%). The rest stayed unmapped because native parser renderings and canonical object values were different and because short/repeated table values were not unique (`platform/END_TO_END_RAG_EVALUATION_REHEARSAL_REPORT.md:99-122`).

Current LightRAG code has repaired much of that boundary with structural lineage. It is not yet sufficient to retire the pre-segmented paths because:

- the lineage contract covers a bounded set of native DOCX structures and is not guaranteed for arbitrary native chunkers/parsers;
- the canonical crosswalk is still LightRAG/storage-specific rather than a typed Adapter contract;
- some rich/merged/split structures legitimately remain partial;
- formal policy and comparison still classify native DOCX as diagnostic;
- RAG-Anything does not expose retrieval stages or lineage;
- at audited revision `db7af4e`, one localizer fallback could label an unproved absence as `retrieval_missed`; the follow-up fix now returns `provenance_missing` for formal provenance envelopes unless the complete reverse-map proof succeeds.

Native readiness does **not** require every runtime chunk or every DOCX object to map completely. It requires every scoring decision to distinguish, with proof, among `complete`, `partial`, `missing`, and a true retrieval miss.

## What the current native path actually does

```text
Platform
  stages original DOCX + checksum + canonical sidecar
      │
      ▼
LightRAG native DOCX parser
  emits rendered blocks plus source_sha256 and OOXML structural lineage
      │
      ▼
LightRAG native chunker
  creates runtime chunks; post-chunk bridge attaches source atoms/spans
      │
      ▼
LightRAG storage/index
  persists content, source span, lineage, native IDs
      │
      ▼
LightRAG Adapter after ingestion
  reads persisted chunks, joins native locators to canonical object catalog,
  builds source-pinned forward/reverse map, writes map digest
      │
      ▼
Query trace
  emits raw/ranked/context native IDs, ranks, content, spans, lineage digests
      │
      ▼
Adapter validation
  checks query item against ingestion map, then emits canonical edges
      │
      ▼
Generic evidence localizer/scorer
  compares verified edges/unions with Canonical Gold
```

Evidence:

- Source-only binary staging and checksum verification: `platform/src/rag_eval/execution.py:1397-1454` and `adapters/lightrag/src/rag_eval_lightrag_adapter/adapter.py:1564-1600`.
- Native parser lineage schema and OOXML coordinates: `../rags/LightRAG/lightrag/parser/docx/lineage.py:1-27`.
- Post-chunk lineage attachment: `../rags/LightRAG/lightrag/pipeline.py:5293-5333` and `../rags/LightRAG/lightrag/sidecar/lineage_bridge.py:583-751`.
- Persisted public source span: `../rags/LightRAG/lightrag/utils_pipeline.py:134-208`.
- Native forward/reverse manifest: `adapters/lightrag/src/rag_eval_lightrag_adapter/canonical_provenance.py:1075-1237`.
- Stage observation and ingestion-map verification: `adapters/lightrag/src/rag_eval_lightrag_adapter/adapter.py:930-1065`.

## Gap matrix

| Capability | Current state | Why it blocks or limits native formal use | Required convergence |
| --- | --- | --- | --- |
| Original DOCX ingestion | Implemented | None for LightRAG source input | Keep as the only new formal corpus input |
| Source identity | Implemented for DOCX/sidecar hashes | Identity is present but distributed across DocumentInput, lineage, map, and trace metadata | One typed Source Identity reused everywhere |
| Native paragraph/table/cell lineage | Implemented | First-class lineage kinds are paragraph, table, and physical cell; other canonical object types are not demonstrated end to end | Versioned native locator vocabulary with explicit unsupported/partial categories |
| Chunk lineage preservation | Partial | Default/known chunking paths can preserve spans/atoms; a transformative or custom chunker may discard or rewrite them | RAG-owned chunker must emit or retain a lineage relation; otherwise the affected item is missing, not guessed |
| Runtime chunk catalog | LightRAG-specific | Adapter scans one `kv_store_text_chunks.json`; another backend/runtime has no common read API | Adapter-neutral read-only ingestion observation surface |
| Query-stage observation | Strong for current LightRAG naive path | Other LightRAG modes and RAG-Anything are not equivalently characterized | Per-profile trace-on/off equivalence and explicit capabilities |
| Canonical crosswalk | Strong for supported structures | Uses free-form maps/metadata and only canonicalizer versions explicitly understood by the adapter | Typed provenance map/edge schema, versioned independent of LightRAG |
| Partial and multi-chunk union | Implemented in generic scorer | Relies on complete expected extents and trustworthy per-edge ranges; not every native object supplies them | Require explicit extents/coverage units for scoreable Gold |
| Tables | Substantial but partial | Whole-table, merged-cell, split-table and duplicate-table identity require physical topology, not rendered text; some table summaries are downgraded | Canonical physical footprint + native structural edges + union semantics |
| Mapping failure semantics | Initial P0 fallback fixed after audited revision | A catalogued but unmapped Gold previously fell through to `retrieval_missed` without an absence proof | Preserve the regression: formal provenance is `missing/partial` unless `prove_true_miss` succeeds |
| Formal comparison policy | Not ready | `native-docx` is `diagnostic_only` and comparison rejects it | Switch only after native admission gates pass |
| Cross-RAG support | Not ready | RAG-Anything has no observable retrieval stages | New Adapter/runtime observation hook; no new scorer or Dataset |

## Required provenance precedence

The requested precedence is correct and should be normative:

```text
1. native provenance / lineage
2. deterministic verified mapping
3. exact text matching fallback
4. no proof → missing / partial
```

### Tier 1 — native provenance / lineage

Use a runtime's own source relation when it is bound to the exact source bytes and survives parsing and chunking. For DOCX this should contain:

- source SHA-256 and coordinate-system version;
- parser and chunker identity/version;
- native document ID and runtime chunk ID;
- structural source locator, such as OOXML part/body ordinal/nested path;
- covered source atoms or ranges;
- table/cell physical coordinates and merge metadata;
- content/lineage digests.

Native lineage is authoritative about what the RAG actually parsed and retained. It still does not own Platform canonical IDs. The Adapter joins its source locator to the Platform-owned canonical locator catalog.

### Tier 2 — deterministic verified mapping

Use this only when the runtime did not preserve a direct native edge but left enough immutable witnesses for a deterministic crosswalk. Examples are:

- an exact source span in a source stream whose transform from DOCX is itself versioned and verified;
- an explicit parser block ID plus a persisted parser-side source locator;
- an exact, unique structural table/cell scope with source and content hashes;
- a runtime-native lineage artifact reconstructed from the same pinned source, parser version, and configuration, with byte-for-byte verification against the stored runtime content.

This tier must produce the same typed edge and pass the same source/catalog/round-trip checks as Tier 1. “Deterministic” means there is exactly one valid candidate. Multiple candidates mean `missing`, not “choose first.”

### Tier 3 — exact text matching fallback

Text is a witness, not normally an identity. A fallback can be accepted only under a declared compatibility policy when all of the following hold:

- document identity and source digest are already verified;
- the exact, non-lossy text occurs once in the permitted source scope;
- normalization rules are versioned and do not use fuzzy/semantic similarity;
- there is no conflicting structural locator or formal provenance claim;
- the result records `mapping_method=text_unique_exact` and its lower trust tier.

Short values, normalized-only collisions, repeated paragraphs, repeated table grids/cells, or cross-document duplicates are ambiguous and stay `missing`. A formal item that opted into the native provenance envelope must never silently fall back to text after a lineage/hash failure; current `_quote_match()` already enforces this separation (`platform/src/rag_eval/evaluation/evidence.py:1384-1424`).

## Hashes prove integrity, not object identity

`content_sha256` is necessary but insufficient. It proves that an observed item's bytes equal a persisted chunk's bytes. It does not prove that those bytes came from canonical object A rather than an identical object B.

A formally usable provenance edge needs all of:

```text
source pin
+ runtime item identity
+ runtime content/lineage integrity
+ canonical object identity and typed locator
+ explicit expected extent
+ explicit covered extent
+ unique mapping method
+ forward ↔ reverse ↔ catalog round trip
```

This is why duplicate table 17/table 39 cannot be distinguished by equal grids alone. The retained repair audit identifies them by different OOXML body ordinals and paragraph ranges (`platform/docs/EVIDENCE_REPAIR_PLAN.md:140-160`).

## Canonical mapping and coverage semantics

### One runtime chunk covers multiple evidence objects

Keep exactly one stage item at its native rank. Attach zero to many provenance edges:

```text
RuntimeItem(rank=4, native_chunk_id=C7)
  ├─ Edge(canonical_object=P12, complete)
  ├─ Edge(canonical_object=P13, complete)
  └─ Edge(canonical_object=T4/C2, partial)
```

Do not duplicate the item or assign each edge a new rank. That would alter Recall@K, MRR, candidate count, and final-context cardinality. ADR 0001 and `platform/CONTRACT.md:69-83` already establish this invariant.

### Multiple runtime chunks jointly cover one evidence object

Each chunk emits a separately verified edge with the same canonical object identity and a covered extent. The scorer may promote the set to complete only when:

- every edge round-trips to the same canonical object;
- the canonical expected extent is complete and pinned;
- the union is gap-free over the required span/footprint;
- overlaps are allowed but do not substitute for gaps;
- every contributing chunk is present at the evaluated stage/cutoff.

Completion rank is the maximum native rank among the pieces needed to close the union. The existing `_complete_partial_union()` implements this for same-object ranges (`platform/src/rag_eval/evaluation/evidence.py:2230-2274`).

### Partial versus complete evidence coverage

Coverage is an edge/object decision, not a property inferred from text length:

- `complete`: the verified covered extent contains the entire canonical expected extent;
- `partial`: at least one verified sub-extent belongs to the object, but the union has a gap or the canonical representation itself is partial;
- `missing`: no safe object relation can be established, the relation is ambiguous, or an integrity check failed;
- `retrieval_missed`: mapping is complete before query and every runtime chunk capable of covering the Gold is absent from the observed stage.

An observed empty stage (`[]`) is still not enough to call a Gold miss if the Gold-to-runtime reverse mapping was never established. It is a true miss only relative to a complete mapping universe.

### Duplicate text

For two equal paragraphs or tables:

- structural source locators select identity;
- value/content hashes verify the selected identity's value;
- text never selects between duplicate structural candidates;
- a conflicting locator is a hard failure;
- if no structural distinction survives, report `missing/ambiguous_duplicate`.

The current evaluator contains good defenses: a formal locator cannot fall back to a unique quote without a catalog edge, same-object unions reject missing/different object IDs, and a verified Gold miss outranks an unrelated duplicate-text diagnostic. These should remain contract tests.

## Tables, merged cells, and split tables

Tables require a topology-based contract. Treating a rendered table string or table-level `coverage=full` flag as completeness is unsafe.

### Canonical authority

For every canonical table, persist:

- table structural locator (`word/document.xml`, body ordinal, nested path);
- ordered set of physical `w:tc` identities;
- row, starting column, physical-cell index;
- horizontal `grid_span`;
- vertical-merge role/status (`v_merge`);
- logical-cell projection, if exposed to Gold, as a mapping to physical cells;
- complete/partial representation status and expected footprint.

### Runtime observation

For each runtime chunk/table piece, emit the physical cells or source atoms actually covered. A chunk may cover:

- one full table;
- several rows;
- one row/cell fragment;
- a table plus surrounding paragraphs;
- multiple tables.

The chunk stays one ranked item; the coverage is an edge set.

### Completeness rules

- Whole-table Gold is complete only when selected runtime items jointly cover every required physical cell in the canonical footprint.
- A cell Gold is complete only when its physical/logical expected extent is covered.
- A horizontal merged cell uses its anchor plus declared `grid_span`; repeated rendered values do not create extra cells.
- A vertical merge uses its physical anchor/continuation metadata. Empty versus repeated continuation text is only a witness diagnostic, never identity.
- A split table can be completed by multiple chunks; the completion rank is the latest required piece.
- If the canonical table footprint is incomplete, even a retrieved row cannot be promoted to a formal partial percentage. The result is provenance `missing`, because the denominator is unknown.

The generic scorer already contains the right shape: `_table_scope_is_verified()`, `_complete_table_union()`, and `_partial_table_footprint()` require catalogued physical cells and per-cell round trips (`platform/src/rag_eval/evaluation/evidence.py:1983-2175`). LightRAG native lineage already records physical cells, `grid_span`, and `v_merge` (`../rags/LightRAG/lightrag/parser/docx/lineage.py:94-174`). These capabilities should move into the unified contract rather than remain LightRAG-specific metadata.

## Validation capabilities to migrate from pre-segmented modes

| Existing strict capability | Current source | Native-mainline form |
| --- | --- | --- |
| Input/source content hashes | canonical and benchmark segment manifests | Pin original DOCX, canonical catalog, parser observation, every runtime chunk, and every stage item |
| Contract/file checksums | `BenchmarkManifest` | Pin Canonical Benchmark release and Unified Trace/Run files |
| Mapping receipt | `segment_mapping_receipt()` | Bind source digest + trace schema + native chunk ID + content hash + canonical edge digest + mapping method |
| Known-ID validation | benchmark segment ID set | Reject canonical IDs/locators absent from the pinned canonical catalog |
| Exact post-ingest verification | one leaf/batch equals one chunk | Verify every observed runtime item against the RAG's actual persisted/observable native chunk record; do not require 1:1 boundaries |
| Lineage validation | native lineage/source SHA checks | Validate source, parser, chunker, content, lineage schema, and canonical crosswalk versions |
| Forward/reverse validation | canonical provenance map | Runtime chunk→edges, object→chunks, and object catalog must round-trip exactly |
| Stage validation | typed SegmentTrace status, rank, receipt | Each raw/ranked/context item must have stable identity, unique stage rank, matching content/lineage receipt, and explicit unavailable/error state |
| Strict failure behavior | split/merge/unknown leaf aborts | Integrity corruption aborts; legitimate partial/missing mapping remains observable and makes only affected Gold clauses unscoreable |

The important change is that exact verification no longer means “the RAG must preserve our chunk.” It means “whatever chunk the RAG created must be observed faithfully and related to source coordinates only when that relation is provable.”

## Native formal-admission gates

`source_document` can replace both pre-segmented modes when all of these are true:

1. **Source gate:** original DOCX, canonical catalog, parser identity, and all source-coordinate schemas are immutable and digest-pinned.
2. **Observation gate:** raw, ranked, and final-context stage semantics are exposed honestly; `None` and `[]` retain their meanings.
3. **Runtime integrity gate:** each stage item resolves to exactly one ingestion-time native chunk record with matching ID, content hash, source pin, and lineage receipt.
4. **Mapping gate:** every emitted canonical edge is structurally selected, value-witnessed, catalogued, and forward/reverse round-trip verified.
5. **Coverage gate:** one-to-many and many-to-one relations preserve native item rank and use exact spans/physical footprints.
6. **Ambiguity gate:** duplicate text/structure, unsupported object types, and integrity mismatches become `missing` or `partial`.
7. **Absence gate:** no `retrieval_missed` or observed zero is emitted unless `prove_true_miss` succeeds.
8. **Behavior gate:** trace/lineage enabled versus disabled produces identical native source, chunk IDs/content, index fingerprint, stage ordering/content, final prompt/context, and answer for the same frozen RAG profile, excluding observation-only timing.
9. **Artifact gate:** the scored case, localization matrix, metric summary, and failure assessment are persisted and checksummed before WebUI reads them.
10. **Cross-adapter gate:** the contract contains no LightRAG mode, file, storage backend, or class name; a Fake Adapter and a second real RAG can implement it without scorer changes.

## Decision

The native mainline is technically feasible with the existing foundations. The blocker is not “RAG chunking is uncontrollable”; uncontrollable chunk boundaries are expected. The blocker is whether those boundaries carry a verifiable source relation and whether the evaluator refuses to score what it cannot prove.

The convergence rule is:

> Let the RAG create any native chunks it wants. Require the Adapter to report exactly what happened, authenticate each reported item, map only provable source relations, and leave all other relations partial/missing. Let the unified scorer—not the Adapter—decide Gold coverage.
