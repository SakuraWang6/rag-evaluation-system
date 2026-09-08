# Native DOCX Four-Layer Migration Plan v3

- Status: accepted phased migration
- Decision authority: ADR 0003
- Destination: one formal native-DOCX evaluation route
- Compatibility: Wire 1.0 and Artifact 1.2 retain their original meanings and read paths

## Destination and ownership

```text
Original DOCX
  -> RAG Native Parser / Chunker / Index
  -> Candidate -> Ranking -> Final Context -> Answer
  -> Adapter Unified Trace
  -> Unified Evaluation
  -> Artifact 2.0 -> Platform API -> WebUI
```

The Platform owns one Canonical Benchmark. Gold eligibility depends only on
Canonical Conformance. A RAG owns its runtime behavior. Its Adapter observes
that behavior and proves native-to-canonical relations. Unified Evaluation
consumes only Gold plus `UnifiedTrace`. Run orchestration persists an immutable
result, and the WebUI only renders that persisted result.

`canonical_segments` and `benchmark_segments` are migration oracles, not future
formal routes. Adapter capability can make a metric unavailable or a Run
ineligible, but it cannot change or filter Gold.

## Execution protocol for every phase

Only one phase is implemented and submitted for acceptance at a time:

1. Add characterization tests for the boundary being changed.
2. Put new behavior behind a compatibility or shadow path.
3. Keep the old system runnable.
4. Compare old and new outputs, classifying expected semantic differences.
5. Run focused tests and the existing CI gate.
6. Meet the explicit Exit Gate and create one phase-only commit.
7. Stop after the commit and wait for acceptance.
8. Roll back by reverting that phase commit only.

No phase may opportunistically implement work assigned to a later phase.

## Frozen semantic decisions

- Canonical snapshot stability is determined by DOCX bytes, parser identity,
  canonicalizer identity, and configuration digest. A change creates a new
  immutable Snapshot.
- Gold eligibility is Platform-owned and independent of every Adapter.
- Observation status and completeness are separate dimensions.
- Cross-stage validity requires declared identity-subset or verified-derivation
  lineage, not globally identical native IDs.
- Provenance priority is native lineage, deterministic verified crosswalk,
  exact unique text fallback, then missing. Fuzzy mapping is forbidden.
- Official retrieval metrics have explicit `@1`, `@3`, or `@5` cutoffs; the
  official complete-evidence MRR is `ranked_complete_evidence_mrr@5`.
- Leaderboard eligibility is metric-availability-driven. A verified Top-5 is
  sufficient for Top-5 metrics; global ranking completeness is not required.
- Failure attribution is proof-gated. Missing proof yields `UNOBSERVABLE`.
- Wire 2.0 and Artifact 2.0 are new versions, never new meanings for v1 fields.

## Phase status

| Phase | Scope | Status | Commit / exit evidence |
| --- | --- | --- | --- |
| 0 | Isolate P0 `retrieval_missed` fix | Complete | `3cfcb64` |
| 1 | ADR and behavior baseline | Complete in this phase | ADR 0003 plus `native_evaluation_v2` baseline |
| 2 | Canonical Stability | Complete in this phase | Immutable conformance artifact and Platform-owned matrix |
| 3 | Wire 2.0 / Unified Trace | Complete in this phase | RAG-neutral contracts, validator, schemas, and v1 normalizer |
| 4 | LightRAG Native Observation | Complete in this phase | Verified native catalog, provenance receipts, Unified Trace, and Wire 1.0 shadow |
| 5 | Unified Evaluation | Complete in this phase | Availability bounds, extent union, explicit MRR@5, pipeline deltas, and proof-gated failures |
| 6 | Run / Artifact 2.0 | Complete in this phase | Immutable case artifacts, persisted views, metric-driven eligibility, and checksum graph |
| 7 | Platform API / WebUI | Complete in this phase | Persisted-only views, descriptor-driven rendering, and fail-closed legacy access |
| 8 | Native formal cutover | Complete in this phase | Release-only creation, native-DOCX admission, and legacy oracle compatibility |
| 9 | RAG-Anything full observation | Complete in this phase | Same-execution native hooks, exact fail-closed crosswalk, and shared Adapter TCK |

## Phase 0 — Isolate the P0 provenance fix

### Scope

- Make `retrieval_missed` reachable only when a complete reverse-map proof
  establishes that mapped runtime evidence exists but is absent from retrieval.
- Preserve unknown/unmapped evidence as unobservable rather than scoring a miss.
- Keep architecture documentation and new contracts out of the fix commit.

### Exit Gate

- Focused and full Platform tests pass.
- An unproved absence no longer becomes a retrieval miss.

### Commit

```text
3cfcb64 fix(evaluation): preserve unobservable provenance semantics
```

## Phase 1 — ADR and behavior baseline

### Scope

- Freeze this architecture, Wire 2.0, Artifact 2.0, metric semantics, proof
  rules, and legacy retirement policy in ADR 0003.
- Freeze current behavior for LightRAG `source_document`,
  `canonical_segments`, and `benchmark_segments`.
- Freeze LightRAG native observation and RAG-Anything answer-only behavior.
- Record RAG runtime profiles separately from Adapter observation profiles.
- Pin the existing offline Artifact 1.2 compatibility fixture by checksum.
- Add characterization guards only; do not change runtime behavior.

### Exit Gate

- Every later phase has a reproducible behavior and compatibility baseline.
- Wire 1.0 and Artifact 1.2 remain offline-readable with unchanged semantics.
- The baseline distinguishes runtime configuration from observability.
- Existing runtime, scoring, and API behavior is unchanged.

### Commit

```text
docs(architecture): freeze native evaluation v2 decisions
```

## Phase 2 — Canonical Stability

### Scope

- Add a Canonical Conformance Suite for repeat generation, locators, object
  graph relations, representation state, and digest stability.
- Add a Platform-owned Gold Eligibility matrix.
- Admit each paragraph, text-span, table, or cell subtype only after it passes
  conformance; unsupported/partial types remain ineligible.
- Keep Adapter capability imports out of Benchmark build and validation code.
- Never regenerate a historical Snapshot in place.

### Exit Gate

- Paragraph and text span have at least one formally admitted type.
- Every tested table/cell subtype has an explicit admitted or ineligible result.
- Benchmark code does not import Adapter capabilities.
- Historical Snapshot fixtures remain byte-stable.

### Implementation evidence

- `CanonicalConformanceSuite` validates Snapshot identity, typed locators,
  object relations, representation state, and explicit subtype admission.
- New canonical artifacts are immutable and content-addressed by canonical
  digest; identity changes create a sibling Snapshot.
- The formal Dataset loader verifies the conformance checksum, report digest,
  Snapshot binding, exact object coverage, and projected Gold decisions.
- New table targets use logical cells. Physical cells remain proof-only.
- Historical snapshots without the policy marker keep their read semantics.

### Commit

```text
feat(canonical): enforce platform-owned gold eligibility
```

## Phase 3 — Wire 2.0 / Unified Trace

### Scope

- Add `AdapterCapabilitiesV2`, `SourceIdentity`, `RuntimeChunkRecord`,
  `ProvenanceEdge`, `StageObservation`, `TransformationRecord`, `UnifiedTrace`,
  and `AdapterRunResultV2`.
- Implement orthogonal observation status and completeness validation.
- Represent verified Top-K prefixes with configured cutoff and
  `proven_prefix_depth`.
- Validate runtime catalogs, forward/reverse provenance, transformation
  receipts, identity-subset transitions, and verified derivations.
- Add a Wire 1.0 compatibility normalizer. Keep `RAGResult` authoritative for
  live execution in this phase.
- Keep all v2 observation contracts independent of Gold.

### Exit Gate

- Every legal and illegal status combination is tested.
- `observed + truncated` proves the intended Top-K prefix.
- Identity-subset and verified-derivation profiles pass conformance tests.
- Wire 1.0 behavior remains runnable and normalizable.

### Implementation evidence

- Wire 2.0 models live in the RAG-neutral observation contract and export
  versioned JSON Schemas without redefining Wire 1.0 fields.
- Status/completeness matrices, Top-K prefixes, runtime identities, content
  hashes, native lineage, forward/reverse maps, and receipt integrity fail
  closed under contract tests.
- Each stage transition declares `identity_subset`, `verified_derivation`, or
  `unobservable`; derived outputs retain source references and content hashes.
- The Wire 1.0 normalizer preserves the difference between missing and empty,
  content-pins visible items, and explicitly refuses to invent catalog,
  completeness, provenance, or transformation proof.
- Live execution still consumes authoritative `RAGResult`; LightRAG
  instrumentation and Unified Evaluation remain Phase 4 and Phase 5 work.

### Commit

```text
feat(contracts): add wire v2 unified observation
```

## Phase 4 — LightRAG Native Observation

### Scope

- Submit the original DOCX unchanged through LightRAG's native ingestion path.
- Observe the ingestion catalog, candidates, ranked retrieval, final context,
  prompt, and answer.
- Emit Wire 2.0 provenance and transformation lineage.
- Migrate content hashes, lineage validation, mapping receipts, catalog joins,
  and round-trip validation from pre-segmented modes.
- Add output-content canonical coverage proof for merged, compressed, or
  otherwise derived outputs.
- Keep Gold eligibility independent of LightRAG support.

### Exit Gate

- Tests cover one chunk to many evidence objects, many chunks completing one
  object, duplicates, partial evidence, and split/merged tables.
- Native chunk content, source identity, lineage digest, canonical witness,
  forward/reverse mapping, and receipt integrity are independently checked.
- Candidate, ranked, context, prompt, and answer observations are built from
  one native response; Wire 1.0 and Wire 2.0 stage items pass an exact shadow
  comparison.
- The legacy native runtime result remains authoritative and all observation
  failures fail closed without changing LightRAG behavior.
- The Adapter imports no Gold model and does not participate in Canonical Gold
  Eligibility.

### Phase 4 implementation

- `source_document` now freezes the authoritative LightRAG chunk store into a
  content- and lineage-pinned `RuntimeChunkRecord` catalog.
- Native OOXML lineage creates direct proof edges; verified structural
  crosswalks project paragraph spans and physical-cell unions to logical cells
  and tables without text search.
- Every canonical object gets a reverse mapping status. A union of partial
  table fragments can be complete at run scope, while an ambiguous or
  mismatched object remains missing/corrupted.
- The `naive` legacy profile declares identity-subset transitions. Profiles
  whose raw hook omits explicit-ID injection declare candidate observation
  partial and candidate-to-ranked transformation unobservable.
- `RAGResult.trace.wire_v2_native_observation` is additive shadow output;
  Phase 5 will be the first consumer for unified scoring.

Detailed boundary and proof rules are in
`docs/architecture/LIGHTRAG_NATIVE_OBSERVATION.md`.
- Observation on/off has no unexplained difference in chunks, rank, context,
  prompt, or answer for every admitted runtime profile.
- Every observed stage item is verified or explicitly unobservable.

### Commit

```text
feat(lightrag): emit verified native unified trace
```

## Phase 5 — Unified Evaluation

### Scope

- Make the scorer consume only Canonical Gold plus validated `UnifiedTrace`.
- Implement equal-weight clause aggregation, verified extent unions, explicit
  `MRR@5`, and the metric availability engine.
- Implement `ranked_evidence_coverage@1/@3/@5`,
  `ranked_complete_evidence_recall@1/@3/@5`, and
  `ranked_complete_evidence_mrr@5`.
- Implement diagnostic first-fragment MRR, candidate coverage, canonical-extent
  pipeline loss, and stage gain.
- Implement proof-gated failure attribution.
- Keep the old scorer available as a shadow fallback during this phase.

### Phase 5 implementation

- `rag_eval.evaluation.unified` is a separate RAG-neutral scoring owner that
  consumes only `GoldEvidenceSet`, `UnifiedTrace`, and an explicit evaluation
  profile. It does not replace the legacy live scorer.
- Canonical Gold now carries an additive `canonical_object_id` plus source,
  coordinate-system, and Canonical Catalog hash pins. New formal publications
  emit them for both object and table-cell locators, while historical records
  remain readable and fail closed for v2 scoring when the pins are absent.
- Per-evidence lower/upper coverage bounds drive metric availability. A proved
  upper-bound result remains observed; uncertainty that can change the value
  produces `UNAVAILABLE`.
- Text uses verified interval unions. Table coverage groups physical receipts
  by merge origin so a logical cell remains one scoring atom.
- Pipeline diagnostics persist separate canonical set loss and gain and require
  the declared identity-subset or verified-derivation relation.
- Failure attribution advances only through proved ingestion, candidate,
  ranking, context, and answer boundaries.
- The compatibility comparator records equivalent, explicitly versioned, or
  non-comparable shadow outcomes without mutating legacy output.

### Exit Gate

- Scorer code contains no RAG name or Adapter-specific semantics.
- A verified Top-5 computes every formal core metric without full ranking.
- Any unknown item that could change a metric makes it unavailable.
- Shadow differences are either equivalent or explicitly versioned.

### Commit

```text
feat(evaluation): add availability-driven evidence scoring
```

## Phase 6 — Run / Artifact 2.0

### Scope

Converge orchestration on:

```text
BenchmarkResolver
  -> AdapterSession
  -> TraceValidator
  -> EvaluationEngine
  -> ArtifactWriter
```

Persist Benchmark/runtime/observation identities, Unified Trace, localization,
metric status and descriptors, failure attribution, leaderboard eligibility,
and a checksum graph. Retain Artifact 1.2 as read-only input.

### Exit Gate

- A completed Run renders fully without the current runtime or scorer.
- Artifact 1.2 remains read-only and accessible.
- Persisted metric availability alone determines leaderboard eligibility.

### Phase 6 implementation

- `rag_eval.runs` owns the RAG-neutral `BenchmarkResolver -> AdapterSession ->
  TraceValidator -> EvaluationEngine -> ArtifactWriter` boundary. The standard
  executor calls the Adapter once and keeps its legacy CaseResult/scorer path
  authoritative while collecting the new case artifact in shadow.
- A validated Wire 2.0 trace is stored in full. Missing, unsupported, failed, or
  corrupted observation instead persists explicit unavailable formal metrics
  and `UNOBSERVABLE`; it is never inferred as a retrieval failure.
- Artifact publication is atomic, immutable, and idempotent for byte-identical
  content. Per-case self-digests, Adapter-result/trace digests, file hashes, a
  dependency graph, and a manifest self-digest fail closed under verification.
- `summary.json` and `case-index.json` are persisted read models. They contain
  answer/evidence judgments, metric statuses/descriptors, localization-derived
  state, failure attribution, aggregates, and metric-driven leaderboard
  eligibility, so ordinary reads invoke neither runtime nor scorer.
- Artifact 1.2 remains unchanged and readable. A newly published v2 directory
  is exposed by additive `RunStore` accessors and an optional legacy-manifest
  pointer; historical Runs are not rewritten.

Detailed layout, integrity rules, and compatibility limits are in
`docs/architecture/RUN_ARTIFACT_V2.md`.

### Commit

```text
feat(runs): persist immutable artifact v2
```

## Phase 7 — Platform API / WebUI

### Scope

- Make normal Run APIs accept Benchmark release, system profile, and query
  configuration without a corpus-mode choice.
- Render metric and observation descriptors from Artifact 2.0.
- Remove current-route `segment_*` and RAG-specific presentation logic.
- Show absent historical fields as `legacy unavailable`; never rescore on read.

### Exit Gate

- API/read paths perform no provenance mapping or scoring.
- WebUI logic recognizes neither RAG names nor corpus modes.
- Every observation, completeness, metric, and corruption state renders from
  persisted descriptors.

### Phase 7 implementation

- The normal Run summary, case collection, case index, case detail, artifact
  verification, and comparison read paths consume the persisted-only
  `ArtifactPresentationReader`.
- Verified Artifact 2.0 data is returned through versioned
  `run-artifact-*-view-v1` schemas. Corrupted data is withheld from result
  presentation while its verification diagnostics remain available.
- Artifact 1.2 Runs expose only persisted execution facts and the explicit
  `legacy_unavailable` state. The API does not invoke current provenance or
  scoring code to synthesize missing v2 fields.
- Core metric selection comes from persisted leaderboard descriptors; metric
  stage, cutoff, evaluation windows, and scorer identity come from persisted
  `MetricDescriptor` values.
- System-specific query controls are declared by the selected System Profile.
  The WebUI contains no concrete RAG-name or corpus-mode branches.
- Phase 8 still owns removal of live `evaluation_corpus` compatibility and the
  formal native-DOCX-only creation cutover.

### Commit

```text
feat(webui): render artifact v2 generically
```

## Phase 8 — Native formal cutover

### Scope

- Remove `evaluation_corpus` from normal API and UI creation paths.
- Accept only original DOCX for new formal runs.
- Stop creation of pre-segmented formal runs while keeping historical readers
  and test oracles.
- Determine LightRAG leaderboard eligibility only from core metric
  availability.
- Remove old live execution branches in a later, separate change after one
  stable compatibility window.

### Exit Gate

- Users cannot create new pre-segmented formal runs.
- Native Run eligibility is entirely metric-driven.
- Benchmark content never branches or filters by Adapter support.
- Adding another RAG requires only an Adapter and the shared TCK.

### Phase 8 implementation

- Normal product creation accepts a Benchmark Release, System Profile, and
  query/runtime configuration through `NativeEvaluationDraftRequest`; it no
  longer accepts a Bundle ID, formal toggle, or corpus selector.
- Formal runtime projection version 4 submits exactly the release-pinned DOCX
  for ingestion and keeps the Canonical Catalog adjacent for observation and
  provenance proof only.
- The shared public admission policy rejects corpus selectors, pre-segmented
  Benchmark Contracts, pre-segmented Bundle metadata, and non-DOCX formal
  projections at Experiment creation and queue time. It also rebuilds the
  selected Release's deterministic projection and requires the exact same
  content-addressed Bundle identity, preventing a Release ID from being paired
  with modified Benchmark content. CLI create/run uses the same policy.
- WebUI creation lists only runnable Benchmark Releases. The old raw
  Experiment editor and queue action are read-only history now.
- Verified Artifact 2.0 runs are not rejected by legacy native-diagnostic
  route labels; persisted core metric availability and descriptor consistency
  remain the leaderboard authority.
- Direct pre-segmented execution helpers, tests, readers, and published
  oracles remain intact for the compatibility window. Their live branches are
  not deleted in this Phase.

Detailed admission and rollback rules are in
`docs/architecture/NATIVE_FORMAL_CUTOVER.md`.

### Commit

```text
refactor(runtime): make native docx the formal route
```

## Phase 9 — RAG-Anything full observation

### Scope

- Keep answer-only Wire 2.0 runs honest and usable.
- Add native ingestion, retrieval, ranking, context, and lineage hooks when the
  runtime makes those facts observable.
- Pass the same Adapter TCK against the same Benchmark and scorer.
- Add no RAG-Anything Dataset, scoring, Run, API, or UI branch.

### Implemented boundary

- Wire 1.0 remains answer-only, preserving the frozen Phase 1 behavior and
  preventing legacy scoring from treating an unobserved stage as empty.
- For the pinned `naive`, non-VLM, no-rerank runtime profile, an Adapter-owned
  callback wrapper observes the actual chunk-vector query and the structured
  `aquery_llm` result while the normal `RAGAnything.aquery` call executes once.
  It does not replay retrieval or generation and returns the public answer
  unchanged.
- The observer snapshots the complete run-scoped JsonKV chunk catalog after
  ingestion. Every query item must round-trip to that catalog with the same ID
  and content hash.
- Candidate-to-ranked and ranked-to-context are declared and verified as
  `identity_subset` only for that proven profile. Other query modes, VLM,
  reranking, unavailable hooks, and invalid receipts keep answer observation
  but make stage metrics unavailable.
- The canonical bridge is an exact-unique parser-stream fallback for textual
  paragraph/heading/span evidence. It supports one chunk covering several
  objects and range union across several chunks. Repeated text fails closed;
  table/cell evidence remains unsupported until native structural lineage is
  available.
- LightRAG and RAG-Anything run through the same reusable Wire 2.0 Adapter TCK
  and the RAG-neutral Unified Scorer. No Dataset, scorer, Run, API, or WebUI
  branch was added.

Detailed invariants and profile limits are recorded in
`docs/architecture/RAG_ANYTHING_NATIVE_OBSERVATION.md`.

### Exit Gate

- Single-execution shadow tests prove one vector query, one structured query,
  and an unchanged answer.
- Runtime catalog, rank, content, lineage, reverse-map, split-union, duplicate,
  and unsupported-profile tests pass.
- Both native Adapters pass the same Wire 2.0 observation TCK.
- Existing Adapter, Platform, CI, schema, and WebUI gates remain green.

### Commit

```text
feat(rag-anything): add native observation hooks
```

## Final acceptance

The migration is complete only when:

- Platform Canonical Conformance alone controls Gold eligibility.
- Adapter admission controls only metric availability and Run eligibility.
- all formal MRR metrics have explicit cutoffs;
- reliable Top-5 observation is sufficient for `@1`, `@3`, `@5`, and `MRR@5`;
- the leaderboard does not require global stage completeness;
- derived native items have verified transformation lineage and output coverage;
- unproved absence is never attributed as parser, retrieval, ranking, or
  context loss;
- each phase remains independently testable, revertible, and accepted; and
- adding a third RAG requires only its Adapter/runtime hooks and the shared TCK.

The final architecture test remains:

> The Platform defines where correct evidence is; the RAG decides how it parses
> and retrieves; the Adapter proves where returned results came from; the
> Scorer decides whether they cover Gold.
