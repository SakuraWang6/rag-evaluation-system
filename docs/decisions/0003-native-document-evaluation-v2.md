# ADR 0003: Native Document Evaluation v2

- Status: Accepted
- Date: 2026-09-08
- Scope: Native-DOCX evaluation architecture, Wire 2.0, Artifact 2.0, and migration policy
- Baseline revision: `3cfcb64`

## Context

The evaluation system currently exposes three corpus modes:
`source_document`, `canonical_segments`, and `benchmark_segments`. They are not
three intended products. They are historical stages in recovering trustworthy
evidence provenance while LightRAG owned parsing and chunking.

The pre-segmented modes added useful integrity checks, but they also let the
Platform constrain the corpus and created route-specific execution, scoring,
artifact, and UI behavior. The destination is one formal end-to-end route in
which the RAG receives the original DOCX and owns its native parser, chunker,
index, retrieval, ranking, context, and answer behavior.

ADR 0002 freezes Wire 1.0 and Artifact 1.2 meanings. This decision does not
reinterpret either contract. It authorizes new, explicitly versioned Wire 2.0
and Artifact 2.0 contracts, compatibility readers, and a phased migration.

## Decision

### One formal evaluation chain

New formal runs will converge on:

```text
Original DOCX
  -> RAG Native Parser / Chunker / Index
  -> Candidate -> Ranking -> Final Context -> Answer
  -> Adapter Unified Trace
  -> Unified Evaluation
  -> Artifact 2.0 -> Platform API -> WebUI
```

The architecture has four ownership layers:

1. **Canonical Benchmark** owns original source identity, canonical source
   coordinates, questions, expected answers, and Gold evidence.
2. **Observation / Adapter** observes a particular RAG and proves how native
   runtime content relates to canonical coordinates.
3. **Unified Evaluation** consumes only Canonical Gold and a validated
   `UnifiedTrace`.
4. **Run / Orchestration** resolves inputs, invokes the Adapter, validates the
   trace, evaluates it, and persists an immutable artifact.

The WebUI is a read-only projection of persisted Run Artifacts. It does not
localize evidence, infer provenance, or rescore results.

### Gold eligibility is Platform-owned

`gold_evidence_eligible` depends only on Canonical Conformance: whether the
Platform can define a source object and its extent stably, uniquely, and
reproducibly. Adapter capabilities, current RAG integrations, and leaderboard
requirements cannot add, remove, or filter Benchmark Gold.

Adapter provenance admission is separate. It determines whether a run can
prove metrics for a Gold type and therefore whether those metrics or that run
are leaderboard-eligible. An unsupported mapping is an observability limit of
the Adapter/runtime profile, not a defect in or alternate version of the
Benchmark.

Candidate Gold types are paragraph, text span, and table/cell. A concrete type
or subtype becomes Gold-eligible only after passing the Canonical Conformance
Suite. A failing subtype such as vertical merge or nested table remains
ineligible without blocking admitted types or the native route.

### Canonical snapshot identity

The tuple below must deterministically reproduce the same canonical objects,
relations, locators, and digest:

```text
DOCX bytes
+ parser identity
+ canonicalizer identity
+ configuration digest
```

A changed DOCX, parser/canonicalizer identity, or canonicalization
configuration creates a new Snapshot. Historical catalogs are immutable and
are never regenerated in place. `object_id` is only a Snapshot-local reference
key. Identity validation additionally binds source SHA-256, coordinate-system
version, typed structural locator, canonical witness hash,
parser/canonicalizer/config identity, and representation status.

### Wire 2.0 observation model

Wire 2.0 introduces `AdapterCapabilitiesV2`, `SourceIdentity`,
`RuntimeChunkRecord`, `ProvenanceEdge`, `StageObservation`,
`TransformationRecord`, `UnifiedTrace`, and `AdapterRunResultV2`.

Stage observation uses two independent dimensions:

```yaml
observation_status: observed | unsupported | unobserved | failed | corrupted
completeness: complete | truncated | partial | unknown
```

- `observed` always carries `items`; `items=[]` is an observed empty result.
- `truncated` is a verified ordered prefix and records configured cutoff plus
  `proven_prefix_depth`.
- `partial` means a known non-prefix omission.
- `unknown` means completeness cannot be proved.
- non-`observed` statuses require `completeness=unknown`.
- corrupted data may be persisted for diagnosis but cannot be scored.

Stages are not required to have subset-identical native IDs. Each RAG profile
declares each transition as `identity_subset`, `verified_derivation`, or
`unobservable`. A verified derivation records source stage/item references,
transformation kind, output content/identity digest, receipt, and lineage
integrity. Derived output also needs an output-content canonical coverage proof
before its evidence coverage can be scored.

The provenance precedence is:

```text
native lineage
  > deterministic verified crosswalk
  > exact unique text fallback
  > missing
```

Fuzzy or semantic matching is never formal provenance. Source, identity,
content, lineage, receipt, or locator ambiguity fails closed. A mapping failure
is `missing` or `partial`; it is never guessed into either a hit or a miss.

### Unified metric semantics

Canonical Gold keeps minimal-sufficient-evidence-set semantics: clauses within
a path are AND, alternatives within a clause are OR, clauses have equal
weight, a clause chooses its best verified alternative, and a case chooses its
best valid path. Dataset aggregation is a macro average over cases.

Verified text spans are unioned. Logical cells are table scoring atoms;
physical cells, merge origins, and structural relations are proof material.
One runtime item may cover multiple evidence objects without rank fan-out, and
multiple runtime items may jointly complete one evidence extent.

The formal core metrics are:

```text
ranked_evidence_coverage@1/@3/@5
ranked_complete_evidence_recall@1/@3/@5
ranked_complete_evidence_mrr@5
```

Diagnostics include `ranked_first_fragment_mrr@5`,
`candidate_evidence_coverage@C`, `ranking_loss`, `context_loss`, and
`stage_gain`. Every pipeline metric descriptor persists candidate cutoff,
ranked cutoff, context budget, and scorer version. Cross-run comparison requires
identical descriptors.

Metric availability is proved per metric, not inferred from global stage
completeness or Adapter name. An `@K` metric requires an observed stage that is
complete, or truncated with `proven_prefix_depth >= K`, plus verified Top-K
rank/identity/content and sufficient provenance. Unknown mappings make a metric
unavailable only when they could change its exact value. MRR additionally
requires all items before the completion rank to be known.

A run is leaderboard-eligible only when every case has every formal core
metric available and the metric descriptors are comparable. Rank positions
after the required cutoff need not be observed.

### Proof-gated failure attribution

Failures are attributed only when the necessary facts are proved:

| Attribution | Required proof |
| --- | --- |
| `PARSER_INDEX_LOSS` | Complete ingestion catalog/provenance and no runtime coverage for Gold |
| `RETRIEVAL_LOSS@C` | Index contains a complete Gold path and observed candidate Top-C does not retrieve it |
| `RANKING_LOSS@K` | Candidate covers an extent and ranked Top-K loses it |
| `CONTEXT_LOSS` | Ranked covers an extent and final context loses it |
| `GENERATION_FAILURE` | Final context completely covers Gold and the answer is wrong |
| `UNOBSERVABLE` | Any required proof is unavailable |

Absence of proof is not proof of absence. `ranking_loss` and `context_loss` are
canonical-extent set differences. Evidence introduced by parent or graph
expansion is recorded as `stage_gain` and does not erase an upstream loss.

### Artifact 2.0 and compatibility

Artifact 2.0 persists Benchmark, runtime, and observation identities;
`UnifiedTrace`; localization; metric statuses and descriptors; proof-gated
failure attribution; leaderboard eligibility; and a checksum graph. Completed
artifacts are display authority and need no live runtime or current scorer.

Wire 1.0 and Artifact 1.2 remain readable with their original meanings. A
compatibility normalizer may project them into v2 read models, but never mutates
the source artifact or claims facts it did not contain. Historical rescoring is
a separately versioned derivative artifact.

### Migration and retirement

Migration follows the phase protocol in
`docs/architecture/MIGRATION_PLAN.md`: characterization first, compatibility or
shadow path, old system kept runnable, focused and aggregate tests, an explicit
exit gate, one commit, then acceptance before the next phase.

`canonical_segments` and `benchmark_segments` remain characterization oracles
and historical readers during migration. After native cutover they stop
accepting new formal runs. Live execution branches are removed only after a
stable compatibility window; retained artifacts remain readable.

RAG-Anything may initially emit an honest answer-only Wire 2.0 observation.
Adding full retrieval evaluation requires Adapter/runtime observation hooks and
the shared Adapter TCK, not a new Dataset, scorer, executor, artifact, API, or
WebUI path.

## Consequences

- Canonical object stability becomes a first-class Platform conformance
  responsibility.
- Adapter work may include RAG-specific read-only runtime instrumentation, but
  the public Adapter Contract remains shared.
- Some runs and metrics will be unavailable rather than assigned misleading
  zeros or failure categories.
- Native and pre-segmented scores are not expected to match because they test
  different ingestion behavior; shadow comparison validates semantics and
  integrity, not score equality.
- The migration is a versioned architecture change, not a package-layout-only
  refactor.

## Non-goals

- Standardizing RAG parser or chunk boundaries.
- Making Adapter capability part of Benchmark authoring.
- Requiring an entire ranked corpus when a verified Top-K suffices.
- Treating derivation lineage alone as proof that evidence survived a
  transformation.
- Deleting legacy modes or changing runtime behavior in this decision phase.
