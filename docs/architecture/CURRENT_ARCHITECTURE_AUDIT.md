# Current Architecture Audit

- Audit date: 2026-09-08
- Audited revision: `db7af4e`
- Scope: `evaluation-system/{platform,adapters,webui}` and the LightRAG/RAG-Anything runtime boundaries referenced by the adapters
- Decision constraint: the only target production path is native document ingestion; this audit does not propose retaining multiple formal corpus routes
- Change scope for this round: documentation only
- Follow-up status: CAA-01 was fixed by `3cfcb64` after the audited revision; the finding below retains the original evidence and records the resolution

## Executive verdict

The project currently has one shared Worker lifecycle, but it does **not** yet have one shared evaluation path. The three LightRAG corpus modes are historical stages of one measurement problem:

1. `source_document` preserves the desired RAG end-to-end behavior, but historically could not prove how native runtime chunks map to canonical Gold coordinates.
2. `canonical_segments` moves a deterministic canonical projection in front of the RAG so that object-to-chunk mapping can be verified.
3. `benchmark_segments` makes that control stricter—one immutable leaf per input and one exact native chunk per leaf—and adds a second Dataset/Gold/Trace/Scorer execution family.

Therefore, the current modes should not be treated as three future products. `source_document` is the destination. The other two are reliability scaffolding and characterization oracles whose validation properties must be moved into the native path before they are retired.

The present implementation already contains most of the hard primitives needed for convergence: native DOCX structural lineage, stable runtime chunk identity, stage traces, content/source digests, forward/reverse mapping checks, multi-object edges, partial unions, physical-table coverage, immutable run artifacts, and fail-closed status types. The remaining work is primarily contract consolidation, native-lineage completeness, absence semantics, artifact authority, and removal of mode-dependent branching.

## Current control flow

```text
Formal Release / Bundle
│
├─ benchmark contract present
│  └─ benchmark_segments
│     ├─ Platform renders one immutable text leaf per input
│     ├─ Adapter requires one unchanged LightRAG chunk per leaf
│     └─ execute_benchmark_case → BenchmarkGold → segment scorers
│
└─ ordinary Bundle
   └─ requested_primary_corpus
      ├─ source_document
      │  ├─ original DOCX/text is uploaded
      │  ├─ RAG parses and chunks
      │  └─ native/canonical provenance map → execute_case → generic scorer
      │
      └─ canonical_segments
         ├─ Platform renders canonical objects into bounded text batches
         ├─ Adapter requires one unchanged LightRAG chunk per batch
         └─ canonical provenance map → execute_case → generic scorer

Persisted case/summary artifacts
└─ RunHistory product projection recomputes/overlays metrics and judgments
   └─ WebUI renders the API projection and hard-coded metric selections
```

Evidence:

- Corpus selection and the benchmark/non-benchmark branch are in `platform/src/rag_eval/execution.py:132-162`, `:341-388`, and `:425-448`.
- The two case executors are in `platform/src/rag_eval/execution.py:843-918` and `:951-1017`.
- The three LightRAG modes are part of `LightRAGAdapterConfig` in `adapters/lightrag/src/rag_eval_lightrag_adapter/adapter.py:131-154`.
- `CaseResult` carries both ordinary `gold_evidence_set` and a separate optional `segment_evaluation_trace` in `platform/src/rag_eval/contracts/run.py:170-180`.

## Ownership and authority map

| Concept | Current owner | Current authority problem | Target disposition |
| --- | --- | --- | --- |
| Original document, canonical objects, Gold | Platform authoring/Dataset packages | A second segment-native Benchmark Dataset and Gold model also exists | One Canonical Benchmark authority |
| Execution corpus | Platform materializers plus adapter configuration | Platform may replace the original document with canonical batches/leaves | Original DOCX only for new formal runs |
| Parsing/chunking/indexing | RAG runtime, but heavily configured by Adapter | Pre-segmentation and acceptance gates effectively constrain chunking | RAG-native behavior, frozen as observed config |
| Runtime observation | Adapter plus runtime trace hooks | Good primitives exist, but contracts are split between `RAGEvidenceItem` and `SegmentTrace` | One typed Unified Trace |
| Provenance mapping | LightRAG adapter and Platform `CorpusEvidenceIndex` | Mapping schema is partly free-form metadata and mode-specific | One adapter-neutral provenance-edge contract |
| Retrieval/answer scoring | Platform evaluation package | Generic and segment-native scorer families coexist | One scorer over Canonical Gold + Unified Trace |
| Run truth | Immutable case and summary files | Product reads recalculate and replace parts of the persisted result | Persisted Run Artifact is display authority |
| Presentation | WebUI | It depends on route-specific metric IDs and execution views | Schema-driven rendering only |

## Prioritized findings

### CAA-01 — P0, resolved after audit: an unproved native absence could become `retrieval_missed`

The target rule is “mapping failure is `missing` or `partial`; never guess.” The current generic localizer has a path that violates that rule:

- `CorpusEvidenceIndex.prove_true_miss()` correctly requires a complete expected extent and non-empty reverse mapping before it proves absence (`platform/src/rag_eval/evaluation/evidence.py:786-806`).
- `validate_native_provenance_contract()` checks that a Gold locator exists in the catalog, but explicitly allows an unmapped catalogued Gold object to proceed (`platform/src/rag_eval/execution.py:1478-1481`).
- If there is no exact edge, no partial edge, no returned item that can be recognized as referencing the Gold, and `_miss_reason()` cannot prove a miss, `localize_gold_evidence()` still falls through to `RETRIEVAL_MISSED` with a null reason (`platform/src/rag_eval/evaluation/evidence.py:1196-1218`).

This is not merely a label issue. It can turn a provenance-coverage gap into an observed zero retrieval score. Native DOCX cannot become the formal mainline until the invariant is:

```text
retrieval_missed ⇔ complete canonical extent
                   + verified canonical↔runtime reverse mapping
                   + verified stage membership
                   + all mapped runtime IDs absent at that stage

otherwise       ⇒ partial or provenance_missing
```

No code change is made in this audit; this is a migration gate.

Follow-up resolution: `localize_gold_evidence()` now returns `PROVENANCE_MISSING` when a formal provenance envelope exists but `_miss_reason()` cannot prove absence. The legacy source-only contract retains its historical unmatched behavior. `test_catalogued_unmapped_gold_is_not_scored_as_retrieval_missed` verifies both localization and that recall becomes unavailable rather than an observed zero.

### CAA-02 — P0: `benchmark_segments` is a parallel evaluation architecture, not only a corpus option

`benchmark_segments` duplicates authority at every important evaluation boundary:

- `BenchmarkSegment`, `BenchmarkQuestion`, and `BenchmarkGold` are deliberately separate from Bundle 2/3 and are described as the primary input for new cross-system runs (`platform/src/rag_eval/contracts/benchmark.py:1-6`).
- Gold evidence is rewritten from canonical evidence coordinates to leaf segment IDs (`platform/src/rag_eval/contracts/benchmark.py:147-177`).
- The Adapter emits a second typed representation, `SegmentTraceSet`, alongside ordinary retrieval arrays (`platform/src/rag_eval/contracts/adapter.py:86-156`, `:181-190`).
- Orchestration calls `execute_benchmark_case()` instead of `execute_case()` (`platform/src/rag_eval/execution.py:425-448`).
- Retrieval and answer/answer-support use separate scorer modules and `segment_*` metric IDs (`platform/src/rag_eval/evaluation/segment_metrics.py:1-6`, `:68-79`; `segment_answers.py:1-12`).

This is the main architectural fork that must be absorbed. Its validation mechanisms are valuable; its separate Dataset/Gold/scorer authority is not part of the target.

### CAA-03 — P1: `source_document` has native-lineage machinery, but is not yet admitted as the comparable mainline

The current code is materially better than the historical native rehearsal:

- LightRAG emits OOXML structural locators for paragraphs, tables, and physical cells (`../rags/LightRAG/lightrag/parser/docx/lineage.py:1-14`, `:72-174`).
- Lineage is attached after chunk transformations and before chunk persistence (`../rags/LightRAG/lightrag/pipeline.py:5293-5333`).
- The Adapter builds a source-pinned forward/reverse canonical map after ingestion (`adapters/lightrag/src/rag_eval_lightrag_adapter/canonical_provenance.py:1075-1237`).

However, the production policy still calls native DOCX a diagnostic and rejects it from winner comparisons (`platform/docs/NATIVE_DOCX_COMPATIBILITY_CONTRACT.md:5-19`; `platform/src/rag_eval/comparison.py:75-96`). Native lineage currently has first-class atoms only for paragraphs, tables, and physical cells; arbitrary custom/transformative chunkers and other rich-object categories can remain unmapped. Formal mapping also depends on a LightRAG JSON chunk store inspection rather than an adapter-neutral observation API.

The authoring surface exposes the drift directly: exports can be registered as `canonical-text` or `native-docx`, while export metadata always states `primary_evaluation_corpus: canonical_segments` (`platform/src/rag_eval/authoring/workflow.py:2231-2248`), and the representability profile type permits only `canonical-text` (`platform/src/rag_eval/authoring/models.py:107-119`).

### CAA-04 — P1: the LightRAG Adapter is additive as an observer in one constrained profile, but it is not generally observation-only

There are two different questions that should not be conflated.

The observation hook itself is well placed:

- LightRAG serializes stage items without changing chunk content (`../rags/LightRAG/lightrag/utils.py:6004-6043`).
- It records ranked retrieval before final top-k/token selection and records the exact final context afterwards (`../rags/LightRAG/lightrag/utils.py:6046-6170`).
- Native lineage mutates chunk metadata, not content (`../rags/LightRAG/lightrag/sidecar/lineage_bridge.py:583-595`).
- The retained equivalence audit found no source/chunk/retrieval/ranking/context/answer divergence for its frozen canonical-text, naive-query workload (`platform/LIGHTRAG_EXECUTION_EQUIVALENCE_AUDIT.md:61-67`, `:112-118`).

The Adapter as a whole is nevertheless a controller as well as an observer:

- It allows only `query_mode="naive"`, fixes a token chunker configuration, launches a native parser, forces JSON/NanoVector/NetworkX stores, and disables caches (`adapters/lightrag/src/rag_eval_lightrag_adapter/adapter.py:93-98`, `:131-175`, `:1688-1759`).
- Every upload uses `process_options="!"`, skipping knowledge-graph extraction (`adapter.py:254-299`, `:863-878`).
- In the two pre-segmented modes it changes the input corpus and requires the native chunker to preserve Platform-made boundaries.

For the current naive profile, skipping KG work is consistent with a retriever that only consumes chunk embeddings. It is still not evidence that arbitrary LightRAG configurations remain native-equivalent. The target must separate a declared RAG-owned runtime profile from observation instrumentation and prove trace-on/trace-off equivalence for every formal profile.

### CAA-05 — P1: persisted Run Artifact is not yet the sole product/display authority

Execution writes `summary.json` and checksums it (`platform/src/rag_eval/execution.py:470-514`). The read path then recomputes a product summary from projected cases:

- `RunHistory._product_summary()` calls `aggregate_metrics()` again (`platform/src/rag_eval/run_history.py:300-314`).
- `_project_case_for_product()` can replace answer metrics, use historical rescore metrics, and downgrade metrics at request time (`run_history.py:541-615`).
- `RunStore.case_index()` calculates case judgments from raw case fields (`platform/src/rag_eval/storage/runs.py:112-151`).
- `_current_answer_judgment()` invokes the current answer scorer while reading an old artifact (`storage/runs.py:330-360`).
- presentation failure assessment can replace old labels (`run_history.py:919-982`).

The intent—repairing old product presentation without mutating research artifacts—is understandable. It conflicts with the new rule that WebUI shows persisted Run truth. Historical rescoring and human review should remain possible only as separately versioned, persisted derivative/review artifacts, never as invisible request-time replacement of the original result.

### CAA-06 — P2: mode identity and policy are scattered

Corpus/view identity appears in:

- Bundle metadata (`primary_evaluation_corpus`);
- `ExperimentSpec.adapter_config.evaluation_corpus`;
- benchmark-contract fields on the Experiment and Run;
- Adapter configuration and ingestion metadata;
- `execution_view` and `diagnostic_only`;
- authoring export registration;
- comparison eligibility;
- scorer namespaces and metric IDs;
- WebUI metric selection.

Examples are `platform/src/rag_eval/execution.py:680-705` and `:1269-1292`, `platform/src/rag_eval/contracts/run.py:77-126` and `:202-235`, and `webui/src/api.ts:164`. This makes a corpus choice behave like a cross-cutting architecture mode rather than an input detail.

### CAA-07 — P2: RAG-Anything reuses the Worker shell but cannot yet participate in unified retrieval evaluation

The RAG-Anything Adapter already accepts the same three corpus labels, uses native `process_document_complete()` for source documents, and returns an answer. Its public query API exposes none of raw retrieval, ranked retrieval, or final-context items; the Adapter correctly returns `None` and `unsupported_stage` instead of fabricating them (`adapters/rag-anything/src/rag_eval_rag_anything_adapter/adapter.py:43-59`, `:265-310`, `:546-720`).

This is the correct fail-closed behavior, but it means “add only an Adapter” is achievable only after the adapter/runtime combination can observe the required stages and lineage. It must not be solved by copying Dataset, scorer, Run, or UI code.

### CAA-08 — P2: the provenance boundary is powerful but too implicit

The current `CorpusEvidenceIndex` validates external map pins, source pins, object catalogs, and forward/reverse edges, which is a major strength (`platform/src/rag_eval/evaluation/evidence.py:239-430`, `:890-993`). Yet the transport is largely a `dict[str, Any]` convention spread across ingestion `details`, evidence-item metadata, and adapter-specific JSON map files. LightRAG also reads `kv_store_text_chunks.json` directly to build post-ingestion mappings (`adapters/lightrag/src/rag_eval_lightrag_adapter/adapter.py:1602-1662`).

This should become a typed, adapter-neutral observation contract. Direct store inspection can remain a LightRAG implementation technique, but its filenames/backend must not become Platform or scorer semantics.

## Direct answers to the requested review questions

| Question | Finding |
| --- | --- |
| 1. Why can `source_document` not replace the others today? | Native lineage is not complete across all parser objects/chunker behaviors; formal policy still marks native runs diagnostic; and mapping transport is LightRAG-specific. The audited unproved-absence bug has now been fixed, but the other admission gaps remain. See `NATIVE_DOCUMENT_GAP_ANALYSIS.md`. |
| 2. What did `canonical_segments` solve? | It removed DOCX-parser-to-canonical alignment uncertainty by putting canonical objects into deterministic, digest-pinned text batches, then requiring one exact persisted chunk per batch. It retains ordinary Canonical Gold and the generic scorer. |
| 2. What did `benchmark_segments` solve? | It made the retrieval unit immutable and cross-system rankable through one leaf/one chunk, known segment IDs, typed stage statuses, mapping receipts, and fixed cutoffs. It also created a parallel Gold/Trace/Scorer path. |
| 3. What strict capabilities should migrate? | Source/content/contract hashes, mapping receipts, known-ID validation, lineage/source pin validation, forward↔reverse↔catalog round trips, exact stage identity/rank checks, explicit unsupported/corrupted states, and immutable checksummed artifacts. |
| 4. Can native chunks map without controlling chunking? | Yes, when each native chunk retains source lineage or a verifiable deterministic crosswalk. One item keeps many edges; multiple items may form a gap-free union; tables use verified physical-cell footprints. Unknown/ambiguous cases remain partial/missing. |
| 5. Is the requested provenance precedence correct? | Yes. Native lineage first, deterministic verified mapping second, exact unique text only as a last fallback. Duplicate/fuzzy/semantic text never establishes physical identity. |
| 6. Is the Adapter observation-only? | The trace/lineage hooks are additive in the audited naive profile. The full Adapter also fixes runtime policy and, in pre-segmented modes, changes the corpus, so it is not generally a passive observer yet. |
| 7. Are there Scorer/Run/UI forks? | Yes: separate benchmark executors/scorers/traces/metrics, mode/view fields in Run and comparison, request-time Run projections, and WebUI hard-coding of `segment_*` metrics. |
| 8. Should RAG-Anything need only a new Adapter? | Yes at the target architecture level. That Adapter may require RAG-Anything-specific runtime observation hooks, but Canonical Dataset, Scorer, Run, API, and UI must remain shared. |

## Strengths to preserve

- Gold remains outside the system-under-test boundary; ADR 0002 makes that a stable invariant.
- `None` versus `[]` and raw/ranked/context meanings are explicit in `platform/CONTRACT.md:57-67`.
- Runtime item identity/cardinality/rank is authoritative; one chunk with many canonical edges is not fanned out (ADR 0001).
- Native mapping checks source SHA, chunk content SHA, lineage SHA, structural locators, witnesses, and catalog membership.
- The evaluator already supports same-object gap-free partial unions and physical-table footprint unions.
- Duplicate text does not override a stronger structural identity, and a formal item cannot fall back silently to quote matching.
- Run files are immutable and checksummed even though the product read model currently overlays them.
- Unsupported RAG stages are represented explicitly rather than converted to empty results or zeros.

## Disproof pass

The following tempting conclusions are not supported by the repository evidence:

- **“Native DOCX has no provenance.”** Outdated. Native structural lineage and adapter mapping now exist; the gap is completeness, neutrality, and unified contract authority.
- **“The Adapter always changes LightRAG ranking.”** Not demonstrated. The frozen naive-profile equivalence audit found no change. The stronger finding is that neutrality has only been proved for a constrained profile.
- **“`benchmark_segments` bypasses LightRAG chunking through a custom insert API.”** Incorrect. LightRAG still receives `/documents/upload`; the acceptance gate requires its resulting chunker output to be exactly one unchanged chunk per leaf (`adapter.py:1341-1419`). It is pre-segmentation by constraint, not a custom-chunk endpoint.
- **“All scoring is LightRAG-specific.”** Incorrect. The ordinary evidence engine is adapter-neutral. The architectural problem is the additional segment-native scorer family and LightRAG-shaped provenance transport.
- **“The browser itself recomputes provenance.”** Not found. The browser consumes API results. Recalculation currently happens in Platform read services, while the browser hard-codes route-specific metrics.
- **“A score parity gate should require native and pre-segmented runs to have equal recall.”** Incorrect. Native chunking is intentionally free to change retrieval behavior. Migration parity must cover contracts, provenance truth, and scorer semantics—not force equal retrieval outcomes across different corpora.

## Architecture decision

The repository should converge by treating:

```text
source_document     = future formal mainline
canonical_segments  = temporary characterization/compatibility oracle
benchmark_segments  = temporary strict mapping/scoring oracle
```

The destination and required contracts are specified in `TARGET_ARCHITECTURE.md`; native gaps and mapping rules are detailed in `NATIVE_DOCUMENT_GAP_ANALYSIS.md`; historical causality is in `MULTI_CORPUS_HISTORY.md`; the staged retirement gates are in `MIGRATION_PLAN.md`.
