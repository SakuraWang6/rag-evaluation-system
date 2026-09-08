# Unified Evaluation v2

- Status: implemented as the Phase 5 shadow scorer
- Semantic inputs: Canonical Gold plus validated `UnifiedTrace`
- Live execution authority during Phase 5: the legacy scorer remains unchanged
- Persistence authority: deferred to Artifact 2.0 in Phase 6

## Ownership boundary

`rag_eval.evaluation.unified` owns the RAG-neutral interpretation of verified
canonical extents. It imports no concrete Adapter, RAG system, corpus mode,
runtime store, or pre-segmented manifest. Runtime-specific observation must be
normalized before this boundary.

New Canonical Benchmark publications pin `canonical_object_id` on every
`GoldEvidence`. The field is additive for historical Bundle 2.0 readers.
Legacy object locators still resolve directly; a legacy structural locator
without a pinned identity is not joined by text or by a best-effort structural
guess and therefore produces `UNAVAILABLE` in the v2 scorer.

## Availability is an interval proof

For every Gold alternative at an evaluation boundary the scorer computes:

```text
verified lower coverage <= exact value <= possible upper coverage
```

- a complete reverse mapping makes selected-stage absence exactly zero;
- a partial or unsupported mapping leaves the upper bound at one;
- a verified full extent has lower and upper bound one, even if other items
  remain unknown;
- corrupted evidence contributes no scoring lower bound and is diagnostic
  only;
- a metric is `observed` exactly when its aggregate lower and upper bounds are
  equal.

This directly implements the rule that unknown evidence makes a metric
unavailable only when it can change that metric's value.

Stage availability is evaluated per metric window. A complete stage or a
verified truncated prefix with `proven_prefix_depth >= K` is sufficient for an
`@K` metric. No result after K must be observed.

## Gold aggregation and extent math

MSES aggregation is preserved without flattening:

```text
path clause = OR(best verified evidence alternative)
path        = equal-weight AND clauses
case        = best valid path
```

Text coverage is the length of the verified interval union divided by the
expected canonical span length. Overlap is counted once. Multiple runtime
chunks may jointly complete one evidence extent, and one runtime chunk may
carry edges for several evidence objects.

For table evidence, physical-cell receipts prove coverage while merge-origin
relations group the physical footprint into logical scoring atoms. A vertically
merged logical cell is complete only after every physical member is covered;
partial physical coverage does not count as a complete logical atom.

## Metrics and descriptors

Formal core metrics are:

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
candidate_to_ranked_stage_gain
ranked_to_context_stage_gain
```

Every metric descriptor pins scorer identity/digest, candidate cutoff, ranked
cutoff, context budget, aggregation rule, stage, and metric cutoff. The MRR
algorithm examines prefix states from rank 1 through rank 5. If an unknown
earlier item could have completed the path sooner, the MRR remains
`UNAVAILABLE` even when a later rank proves complete coverage.

## Transformation and pipeline diagnostics

Pipeline loss is an actual canonical-extent set difference, not a difference
between two aggregate recall numbers:

```text
loss = upstream covered extent - downstream covered extent
gain = downstream covered extent - upstream covered extent
```

Loss and gain are persisted as separate values and cannot cancel. The scorer
computes them only when the profile declares `identity_subset` and the target
window is a proved subset, or declares `verified_derivation` and every target
item has a verified receipt whose sources are inside the evaluated upstream
window. An `unobservable` transformation makes the cross-stage metric
unavailable without invalidating independent stage metrics.

## Proof-gated failure attribution

Attribution advances only through proved prior boundaries:

1. complete ingestion plus complete reverse provenance can prove
   `PARSER_INDEX_LOSS`;
2. a complete index path plus a proved candidate prefix can prove
   `RETRIEVAL_LOSS@C`;
3. complete candidate coverage plus verified transformation lineage can prove
   `RANKING_LOSS@K`;
4. complete ranked coverage plus verified context transformation can prove
   `CONTEXT_LOSS`;
5. complete context coverage plus deterministic answer failure can prove
   `GENERATION_FAILURE`.

Any missing boundary, uncertain extent, corrupt proof, or answer requiring
semantic review yields `UNOBSERVABLE` rather than a guessed stage failure.

## Phase 5 compatibility boundary

The legacy `evaluate_case` and its `RAGResult`/corpus localizer remain intact.
`compare_legacy_shadow` compares the overlapping ranked recall metrics and
classifies each result as equivalent, expected versioned semantic change, or
not comparable. It never rewrites either result. Phase 6 may persist the v2
result models, but Phase 5 does not change orchestration, artifacts, API, or
WebUI.
