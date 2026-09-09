# Unified Evaluation v2

## Authority

`rag_eval.evaluation.unified` is the only formal scorer. It consumes Canonical
Gold plus a validated `UnifiedTrace` and imports no concrete Adapter, RAG name,
corpus mode or runtime store.

The engine emits typed metric status/value/descriptor records, canonical
localization, pipeline deltas and proof-gated failure attribution for Artifact
2.0. `UNAVAILABLE` remains a status with no numeric value.

## Evidence aggregation

Gold uses minimal sufficient evidence paths:

```text
clause = best verified OR alternative
path   = equal-weight AND clauses
case   = best valid path
suite  = macro average over cases
```

Text evidence uses the union of verified canonical intervals, so overlapping
chunks are not double-counted. One runtime item may cover several evidence
objects, and several runtime items may jointly complete one extent.

Logical cells are table scoring atoms. Physical cells, merge origins and
structural relations prove the logical footprint. Partial physical coverage
does not become a complete logical-cell hit.

## Availability proof

For each Gold alternative and metric window, the scorer computes a verified
lower bound and possible upper bound. The metric is observed only when those
bounds are equal.

- a complete reverse mapping can prove selected-stage absence;
- partial, unsupported or unknown mapping leaves uncertainty;
- a verified full extent is exactly one even if unrelated items are unknown;
- corrupted proof contributes no scoring lower bound;
- complete stage observation or a truncated prefix reaching K can support
  `@K` without observing ranks after K.

If an unknown earlier rank could complete a path sooner, MRR is unavailable.
If coverage is already proved to be one, later unknown items cannot change the
value and do not block that coverage metric.

## Metrics and descriptors

Formal core metrics are:

```text
ranked_evidence_coverage@1/@3/@5
ranked_complete_evidence_recall@1/@3/@5
ranked_complete_evidence_mrr@5
```

Diagnostics include:

```text
ranked_first_fragment_mrr@5
candidate_evidence_coverage@C
ranking_loss
context_loss
candidate_to_ranked_stage_gain
ranked_to_context_stage_gain
```

Every descriptor binds metric ID, stage, explicit cutoff, candidate cutoff,
ranked cutoff, context budget, aggregation rule, scorer identity/version and
scorer source digest. Metrics from different descriptors are not comparable.

## Pipeline deltas

Loss and gain are canonical-extent set differences:

```text
loss = upstream covered extent - downstream covered extent
gain = downstream covered extent - upstream covered extent
```

They are persisted separately and never cancel. Cross-stage deltas require a
proved `identity_subset` or verified derivation within the evaluated windows.
An unobservable transition makes the delta unavailable without invalidating an
independent stage metric.

## Failure attribution

Attribution advances only through proved prior boundaries:

| Attribution | Required proof |
| --- | --- |
| `PARSER_INDEX_LOSS` | Complete ingestion catalog/provenance and no runtime coverage for Gold |
| `RETRIEVAL_LOSS@C` | Index contains a complete Gold path and proved candidate Top-C does not retrieve it |
| `RANKING_LOSS@K` | Candidate covers the extent and ranked Top-K loses it through a verified transition |
| `CONTEXT_LOSS` | Ranked covers the extent and final context loses it through a verified transition |
| `GENERATION_FAILURE` | Final context completely covers Gold and the answer is wrong |
| `UNOBSERVABLE` | Any required proof is insufficient |

Absence without proof is always `UNOBSERVABLE`. A Gold type that an Adapter
cannot locate is an observation limitation, not a Benchmark defect.

## Leaderboard input

The scorer does not decide eligibility from Adapter name or global stage
completeness. Artifact publication aggregates the persisted metric statuses:
every case must have every formal core metric observed under identical
descriptors. A valid but insufficiently observed Run remains displayable and
leaderboard-ineligible.
