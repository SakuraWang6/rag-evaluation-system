# Target Architecture

- Status: normative destination for new formal evaluation runs
- Decision authority: ADR 0003
- Architectural decision: one formal corpus path—original document through the RAG's native ingestion pipeline
- Compatibility: historical pre-segmented artifacts remain readable during migration but do not define this target

## Target chain

```text
Original DOCX
  → RAG-native Parser
  → RAG-native Chunker
  → RAG-native Index
  → Retrieval
  → Ranking
  → Final Context
  → Answer
  → Adapter Observation / Provenance
  → Unified Scoring
  → Run Artifact
  → WebUI
```

The key ownership rule is:

> The Platform defines where correct evidence is. The RAG decides how it parses, chunks, indexes, and retrieves. The Adapter proves where observed runtime results came from. The Scorer decides whether those proven results cover Gold.

No target component translates Gold into RAG chunk IDs before retrieval. No scorer understands a LightRAG store, marker, segment ID, or parser implementation. No UI endpoint silently changes the meaning of a completed Run.

## The four layers

```text
┌─────────────────────────────────────────────────────────────────┐
│ 1. Canonical Benchmark                                          │
│ OriginalDocument + CanonicalObjectCatalog + Questions + Gold   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ source to RAG; catalog to observer
┌───────────────────────────▼─────────────────────────────────────┐
│ 2. Observation / Adapter                                        │
│ RAG-owned execution + native records + provenance edges        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ UnifiedTrace
┌───────────────────────────▼─────────────────────────────────────┐
│ 3. Unified Evaluation                                           │
│ Canonical Gold + UnifiedTrace → localization + metrics         │
└───────────────────────────┬─────────────────────────────────────┘
                            │ immutable case/run results
┌───────────────────────────▼─────────────────────────────────────┐
│ 4. Run / Orchestration                                          │
│ preparation, isolation, execution, persistence, checksums      │
└───────────────────────────┬─────────────────────────────────────┘
                            │ persisted product projection
┌───────────────────────────▼─────────────────────────────────────┐
│ WebUI: schema-driven, read-only presentation                    │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 1 — Canonical Benchmark

The Platform owns the durable answer to “where is the evidence in the original source?” It contains:

- the original DOCX identity, path within the release, SHA-256, media type, and source-coordinate schema version;
- a canonical object catalog with stable object IDs and typed locators into that exact source;
- complete expected extents for scoreable paragraphs, ranges, tables, and physical/logical cells;
- questions, expected answers, and `GoldEvidenceSet`/minimal sufficient evidence set semantics;
- release manifests, schema versions, checksums, and authoring/representability diagnostics.

It does **not** contain:

- the chunks that a RAG must index;
- leaf markers intended to become runtime identity;
- RAG-specific parser or chunker parameters;
- a precomputed canonical-to-runtime chunk map;
- Gold information in any file made visible to the Worker.

The original DOCX is the only content submitted to the RAG for new formal runs. The canonical catalog may be supplied out of band to the Adapter's trusted observer after or alongside ingestion, because it is needed to prove coordinates. Questions and Gold must remain outside the Worker boundary, preserving ADR 0002.

#### Gold eligibility and canonical conformance

Gold eligibility is owned exclusively by this layer. A concrete canonical object
type or subtype is `gold_evidence_eligible` when the Platform's Canonical
Conformance Suite proves that its identity and extent are stable, unique, and
reproducible. It does not depend on whether LightRAG, RAG-Anything, or any other
Adapter can map that type.

Adapter provenance admission is a separate Run concern: it controls whether a
metric is available and whether a Run can enter a leaderboard. It never filters
or rewrites Benchmark Gold. Paragraph, text span, and table/cell are the first
conformance candidates; only subtypes that actually pass are admitted. A
failing vertical-merge or nested-table subtype does not block the native route
or already conformant types.

For identical DOCX bytes, parser identity, canonicalizer identity, and
configuration digest, canonical generation must reproduce identical objects,
relations, typed locators, and catalog digest. Any input or implementation
identity change creates a new immutable Snapshot. `object_id` is a
Snapshot-local key; source SHA-256, coordinate-system version, structural
locator, witness hash, parser/canonicalizer/config identity, and representation
status complete its identity proof.

### Layer 2 — Observation / Adapter

The Adapter owns translation, not retrieval truth. It:

1. declares a RAG-owned runtime profile and its observation capabilities;
2. submits the original DOCX to the public/formal native ingestion path;
3. observes the exact native chunks created by that run;
4. observes raw retrieval, ranked retrieval, final context, prompt construction, and answer where supported;
5. validates observed items against the ingestion catalog;
6. maps each native item to zero or more canonical objects with typed provenance edges;
7. emits one adapter-neutral `UnifiedTrace`.

The Adapter must not:

- upload Platform-made canonical/benchmark chunks for a formal run;
- rewrite queries, candidates, scores, ranks, context, or answers merely to make evaluation easier;
- issue a second query to reconstruct a missing stage;
- copy Gold into the RAG workspace or use Gold to choose provenance candidates;
- fan one runtime item into several ranked items because it covers several canonical objects;
- silently convert unsupported/unobserved stages to observed empty arrays;
- select among ambiguous structural or duplicate-text candidates.

Runtime-specific hooks are allowed and expected. They are part of the Adapter implementation boundary, not part of Platform scoring semantics. For example, a LightRAG adapter may read a LightRAG chunk store or use a trace hook; a RAG-Anything adapter may require a different runtime hook. Both must emit the same public observation contract.

### Layer 3 — Unified Evaluation

The Scorer has exactly two semantic inputs:

```text
Canonical Gold + UnifiedTrace
```

It localizes Gold against verified edges and stage membership, calculates generic retrieval/context/answer metrics, and emits typed failure reasons. It does not read:

- LightRAG native metadata or storage files;
- RAG-Anything objects;
- benchmark leaf markers or segment manifests;
- adapter configuration to infer missing evidence;
- a second route-specific Gold or Trace representation.

All RAG-specific facts must have been validated and normalized by the Adapter. All evidence correctness rules remain Platform-owned and adapter-neutral.

### Layer 4 — Run / Orchestration

Run orchestration owns lifecycle rather than evaluation meaning:

- verify a Canonical Benchmark release;
- create an isolated Worker environment without Gold;
- stage only authorized source/question inputs;
- invoke the common Adapter lifecycle;
- receive and validate `UnifiedTrace`;
- invoke the one scorer path;
- persist cases, metrics, judgments, diagnostics, manifests, logs, and checksums;
- publish an immutable product projection for the WebUI.

There is one formal executor. Adapter capabilities can make a metric unavailable or a run ineligible, but cannot select a parallel scorer family or change Benchmark Gold.

### WebUI — read-only presentation

The WebUI renders the persisted Run Artifact through a stable API. It may sort, filter, paginate, and format values. It must not:

- recompute provenance, Gold localization, evidence coverage, answer judgment, or failure labels;
- replace historical metric values with the current scorer at request time;
- hard-code a corpus route's metric namespace;
- infer that a missing trace array means empty retrieval.

If an old run is rescored, the result is a new, versioned derivative artifact linked to the original. A review or override is also a separately persisted record with author, reason, schema, and time. The original Run remains immutable.

## Authority matrix

| Concept | Sole authority | Consumers | Forbidden duplicate authority |
| --- | --- | --- | --- |
| Original source bytes and identity | Canonical Benchmark | RAG, Adapter, Run | Adapter-created substitute source |
| Canonical evidence coordinates and expected extents | Canonical Benchmark | Adapter mapping, Scorer | benchmark segment IDs as Gold |
| Parser/chunker/index configuration and output | RAG runtime profile | Adapter observer | Platform materializer |
| Native chunk identity/content | Observed RAG ingestion catalog | Adapter, trace validator | canonical leaf identity |
| Native→canonical relation | Adapter provenance output | Scorer, diagnostics | scorer text search or UI inference |
| Stage membership/order | Adapter-observed RAG trace | Scorer | second query/reconstructed list |
| Gold coverage and metric semantics | Unified Scorer | Run | Adapter/RAG/UI |
| Completed result shown to users | Persisted Run Artifact | API/WebUI | request-time rescore/projection |

## Unified observation contract

ADR 0003 authorizes a new Wire 2.0 schema. Phase 3 implements the following
concepts without RAG-specific fields in the scorer-facing surface. The full
contract and compatibility rules are recorded in
[`UNIFIED_OBSERVATION_CONTRACT.md`](UNIFIED_OBSERVATION_CONTRACT.md).

### Source identity

```text
SourceIdentity
  document_id
  source_sha256
  media_type
  source_coordinate_schema
  canonical_catalog_sha256
```

Every ingestion record, provenance edge, and stage item is transitively bound to this identity. Source hashes prevent cross-document joins; they do not identify a canonical object on their own.

### Runtime ingestion record

```text
RuntimeChunkRecord
  native_document_id
  native_chunk_id
  content_sha256
  content                  # optional when separately content-addressed
  native_span              # optional, typed
  native_lineage           # optional, typed/versioned
  parser_identity
  chunker_identity
  persisted_metadata_digest
```

The ingestion catalog is the universe from which query-stage items may refer. An unknown native chunk ID, content mismatch, or lineage mismatch is corruption, not an empty mapping.

### Provenance edge

```text
ProvenanceEdge
  native_chunk_id
  canonical_object_id
  canonical_locator
  mapping_tier             # native_lineage | deterministic_crosswalk | text_unique_exact
  coverage_status          # complete | partial
  expected_extent
  covered_extent
  physical_cell_footprint  # when relevant
  source_sha256
  native_content_sha256
  native_lineage_sha256
  canonical_value_sha256   # integrity witness, not identity
  receipt_sha256
  reason_code
```

A provenance edge exists only for a proved relation. A missing relation is represented separately so that it cannot carry a guessed canonical object ID:

```text
MappingDiagnostic
  native_chunk_id          # optional when the subject is a canonical object
  canonical_object_id      # optional only when that identity is already known
  status                   # missing | corrupted | unsupported
  mapping_tier_attempted
  reason_code

CanonicalMappingRecord
  canonical_object_id
  expected_extent
  reverse_mapping_status   # complete | partial | missing | unsupported
  native_chunk_ids[]
```

`reason_code` distinguishes unsupported lineage, ambiguous duplicate, source mismatch, corrupt receipt, incomplete expected extent, and similar diagnostics. Candidate guesses are diagnostic text only; they never populate `canonical_object_id`.

### Stage observation

```text
StageObservation
  observation_status        # observed | unsupported | unobserved | failed | corrupted
  completeness              # complete | truncated | partial | unknown
  configured_cutoff         # optional
  proven_prefix_depth       # required for truncated
  items[]
    native_chunk_id
    native_rank             # unique within an ordered stage
    runtime_score           # optional and uninterpreted by provenance
    content_sha256
    provenance_edges[]
```

The two status dimensions are orthogonal:

- `observed` always carries `items`; `items=[]` is the sole representation of a real observed empty result;
- `complete` proves the whole declared stage boundary;
- `truncated` proves an ordered prefix and requires a configured cutoff and `proven_prefix_depth`;
- `partial` means a known non-prefix omission;
- `unknown` means completeness cannot be established;
- `unsupported`, `unobserved`, `failed`, and `corrupted` require `completeness=unknown`;
- corrupted observations may be persisted for diagnosis but never scored;
- raw retrieval is the candidate set before reranking/final selection;
- ranked retrieval is the ordered result after runtime ranking and before final context selection;
- final context is exactly the set/text used to build the answer prompt;
- ranks and cardinality remain native.

### Transformation lineage

Native item IDs do not have to form strict subsets across stages. Each RAG
profile declares every transition as:

```text
identity_subset | verified_derivation | unobservable
```

`identity_subset` applies to pure filtering and reordering, where a subset
violation is corruption. `verified_derivation` supports deduplication, merge,
aggregation, compression, parent expansion, and graph expansion. Each derived
output records source stage/item references, transformation kind, output
identity/content digest, a transformation receipt, and lineage integrity.

Derivation alone does not prove that source evidence survived. The output item
must also carry a canonical coverage proof for its actual output content;
otherwise its evidence coverage is unavailable.

### Unified trace

```text
UnifiedTrace
  schema_version
  source_identity
  runtime_profile
  observation_profile
  ingestion_catalog
  provenance_map_digest
  canonical_mapping_records
  mapping_diagnostics
  raw_retrieval
  ranked_retrieval
  final_context
  transformations
  prompt_trace
  answer
  validation_receipts
```

Legacy `RAGEvidenceItem` and `SegmentTraceSet` may be translated into this shape by compatibility readers during migration. New scorers consume only this shape.

## Provenance precedence and trust

The precedence is normative:

```text
native provenance / lineage
  > deterministic verified mapping
  > exact unique text fallback
  > no proof
```

Precedence does not mean “try weaker evidence after a stronger integrity claim fails.” If native lineage is present but has the wrong source hash, content digest, or locator, the item is corrupted/missing. It must not be rescued by text.

### Tier 1 — native lineage

Use a source-pinned relation produced by the RAG parser/chunker and preserved to the observed chunk. The Adapter validates it against the Platform canonical catalog. This is the preferred proof because it follows the actual parse and chunk transformations.

### Tier 2 — deterministic crosswalk

Use a reconstruction only when the inputs are pinned and there is exactly one valid structural/span candidate. The crosswalk must reproduce the observed runtime content/lineage and pass the same catalog, source, forward/reverse, and receipt checks as Tier 1.

### Tier 3 — exact unique text

Use only as a declared compatibility fallback inside a verified source scope. It must be exact, normalization-versioned, and unique. Repeated paragraphs, cells, table grids, or short strings are ambiguous. Fuzzy or semantic similarity is a diagnostic lead, never formal provenance.

### No proof

Emit `partial` if a verified sub-extent exists but completeness cannot be shown. Otherwise emit `missing` with a reason. Do not choose the first candidate, infer from rank, or convert the result to a retrieval miss.

## Evidence coverage semantics

### One chunk, several Gold objects

One runtime item retains one native ID and one native rank. It may carry several provenance edges. The scorer evaluates those edges without cloning the item. This preserves candidate cardinality, Recall@K, MRR, and final-context truth, as required by ADR 0001.

### Several chunks, one Gold object

The scorer may union verified covered extents belonging to the same canonical object. It declares complete coverage only when the union covers the complete expected extent without gaps. The completion rank is the greatest native rank among the minimum required pieces at that cutoff.

### Alternatives and conjunctions

Canonical Gold retains its current minimal-sufficient-evidence semantics:

```text
OR over sufficient evidence paths
  → AND over required clauses in one path
    → OR over canonical alternatives for one clause
```

The scorer resolves each alternative through canonical object IDs and verified edges; it never rewrites the expression into runtime chunk IDs before the query.

### True miss versus unknown provenance

`retrieval_missed` is permitted only if the pre-query ingestion/provenance catalog completely identifies all runtime chunks capable of covering the Gold extent and none appears in the observed stage/cutoff. If that reverse map is incomplete, the result is `provenance_missing` or `partial`, not zero recall.

### Tables and merged/split cells

Whole-table and cell evidence is defined by canonical physical footprints, structural locators, and merge topology. Native chunks report the cells/ranges actually covered. Multiple chunks can complete a table through a verified union; equal rendered grids cannot choose between duplicate tables. The detailed rules are in `NATIVE_DOCUMENT_GAP_ANALYSIS.md`.

## Metrics and availability

### Gold aggregation

Gold uses minimal-sufficient-evidence-set semantics:

```text
best valid path
  path: AND across equally weighted clauses
    clause: OR across canonical alternatives, taking best verified coverage
```

Datasets macro-average cases. Text coverage uses verified span union. Table
coverage scores logical cells while physical cells, merge origins, and
structural relations provide the proof.

### Metric vocabulary

Formal core metrics have explicit cutoffs:

```text
ranked_evidence_coverage@1/@3/@5
ranked_complete_evidence_recall@1/@3/@5
ranked_complete_evidence_mrr@5
```

Diagnostics are:

```text
ranked_first_fragment_mrr@5
candidate_evidence_coverage@C
ranking_loss
context_loss
stage_gain
```

`ranked_complete_evidence_mrr@5` is `1/r` at the earliest rank `r <= 5`
whose prefix completely covers one valid Gold path. It is zero only when a
reliable Top-5 is observed and does not complete a path. Otherwise it is
unavailable.

Pipeline loss is a canonical-extent set difference between adjacent stages.
New parent/graph evidence is `stage_gain`; it does not cancel an upstream loss.
Metric descriptors persist candidate cutoff, ranked cutoff, context budget, and
scorer version. Only identical descriptors are cross-Run comparable.

### Metric-driven eligibility

An `@K` metric is available only when:

1. the stage is observed;
2. completeness is `complete`, or is `truncated` with
   `proven_prefix_depth >= K`;
3. the Top-K ranks, identities, and content pass integrity validation;
4. provenance proves the metric's exact value; and
5. any required cross-stage transformation lineage passes validation.

Unknown mappings do not automatically invalidate a saturated coverage value,
but they do invalidate a value they could change. MRR additionally requires all
items before the completion rank to be known. Leaderboard eligibility requires
every case and every formal core metric to be available with compatible metric
descriptors; it does not require global stage completeness or ranks after the
metric cutoff.

## Proof-driven failure attribution

| Attribution | Required proof |
| --- | --- |
| `PARSER_INDEX_LOSS` | Complete ingestion catalog/provenance and no Gold runtime coverage |
| `RETRIEVAL_LOSS@C` | Index has a complete Gold path but observed candidate Top-C does not retrieve it |
| `RANKING_LOSS@K` | Candidate covers an extent that ranked Top-K loses |
| `CONTEXT_LOSS` | Ranked covers an extent that final context loses |
| `GENERATION_FAILURE` | Final context completely covers Gold but answer is wrong |
| `UNOBSERVABLE` | Any required proof is insufficient |

Failure labels are conclusions, not guesses. An Adapter's inability to map a
Gold type is `UNOBSERVABLE`, not a Benchmark defect or retrieval failure.

## Runtime profile versus observation profile

The target separates two declarations that the current LightRAG Adapter mixes:

```text
RAGRuntimeProfile
  parser/chunker/index/retrieval/ranking/context/answer configuration
  owned and versioned as the system under test

ObservationProfile
  trace/lineage hooks and read-only extraction configuration
  owned by the Adapter
```

An experiment may intentionally fix a runtime profile—for example, a LightRAG naive retriever with a specified chunker. That is valid experimental control, not an observation side effect. The manifest must say which settings define the system under test and which settings merely expose facts.

For every admitted profile, trace-on/trace-off characterization must show that observation does not change:

- source submitted to the parser;
- stored chunk content and identity;
- retrieval candidates/scores;
- ranking order;
- final context;
- prompt and answer.

Where a hook necessarily changes behavior, it becomes part of the declared RAG runtime profile and the run is not represented as passive observation.

## Run Artifact as product truth

A completed Artifact 2.0 contains, directly or by checksummed content-addressed references:

- Canonical Benchmark release identity and source digests;
- Adapter, RAG runtime, parser, chunker, model, and observation profile identities;
- capability negotiation and preflight outcomes;
- ingestion catalog and provenance map/receipts;
- the complete `UnifiedTrace` for each case;
- Gold localization statuses and reason codes;
- metric values/statuses/descriptors with scorer identity/schema and cutoffs;
- answer judgments and failure assessments;
- aggregate summary and metric-driven leaderboard eligibility;
- logs/diagnostics separated from scored facts;
- checksums for every authoritative member.

The product-facing summary/case index is persisted at run completion and included in the checksum graph. A later re-score creates `DerivativeRun(original_run_id, scorer_version, ...)`; a human review creates a versioned review artifact. Neither silently mutates the original API response.

## Dependency rules

```text
Canonical Benchmark ───────┐
                           ├─→ Unified Scorer → Run Artifact → WebUI
Adapter / UnifiedTrace ────┘

RAG runtime → Adapter implementation
RAG runtime ✕ Scorer
RAG runtime ✕ WebUI
Adapter implementation ✕ Canonical Gold answers
WebUI ✕ live scoring/localization
```

Enforce these mechanically where practical:

- scorer packages may import canonical and unified-trace contracts, never adapter packages;
- adapters may import public contracts, never evaluation functions;
- the WebUI/API read model accepts persisted result schemas, never scorer services;
- authoring creates source/canonical truth, never execution chunks;
- adapter-specific metadata remains opaque diagnostics outside scorer decisions.

## Adding RAG-Anything or another RAG

At the target boundary, a new RAG needs:

1. an Adapter implementation for prepare/ingest/query/cleanup;
2. any runtime-specific, read-only hooks required to expose native chunk lineage and the three retrieval/context stages;
3. conformance tests proving source pins, cardinality/rank, stage semantics, provenance validation, and observation neutrality.

It does not need a new:

- Dataset or Gold model;
- evidence expression language;
- scorer or metric namespace;
- execution branch;
- Run Artifact family;
- API or WebUI page.

The current RAG-Anything Adapter honestly reports unsupported retrieval stages. Until its runtime exposes those stages and lineage, it may run answer-only diagnostics but is not admitted to formal retrieval/context comparison. Unsupported capability is a property of the Adapter/runtime profile, not a reason to fork the architecture.

## Target invariants

A new formal run is conformant only when all of the following hold:

1. The RAG receives the original, checksum-pinned DOCX and no Platform-created retrieval chunks.
2. Gold is not available inside the Worker or Adapter query decision path.
3. The RAG owns parser, chunker, index, retrieval, ranking, context, and answer behavior.
4. Observation preserves native item identity, rank, order, and cardinality.
5. Every formal provenance claim is source-pinned, integrity-checked, catalogued, and round-trip validated.
6. Ambiguous or incomplete mappings stay `missing`/`partial`; only a complete reverse map can prove `retrieval_missed`.
7. The scorer consumes only Canonical Gold and `UnifiedTrace`.
8. There is one formal executor and one generic metric vocabulary.
9. The persisted Run Artifact is the only result authority exposed to the WebUI.
10. Adding a RAG changes Adapter/runtime integration code, not Dataset, scorer, Run, API, or UI semantics.
11. Gold eligibility is determined only by Canonical Conformance; Adapter admission affects only metric and Run eligibility.
12. A verified Top-5 is sufficient for all formal `@1`, `@3`, `@5`, and `MRR@5` metrics without claiming a complete ranking.

## Non-goals

- Forcing all RAGs to use the same chunker or to produce equal retrieval scores.
- Requiring every native chunk to map to a canonical Gold object.
- Treating fuzzy semantic alignment as formal source provenance.
- Erasing historical pre-segmented runs or breaking their readers during migration.
- Moving RAG implementation details into Platform canonical coordinates.
- Keeping canonical/benchmark pre-segmentation as a permanent formal fallback.
