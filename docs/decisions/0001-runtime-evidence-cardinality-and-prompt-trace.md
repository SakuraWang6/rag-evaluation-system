# ADR 0001: Runtime Evidence Cardinality and Prompt Trace

- Status: Accepted; current types updated by ADR 0003 and ADR 0004
- Date: 2026-09-08
- Owners: Platform contracts and LightRAG Adapter

## Context

The LightRAG Adapter can map one ranked runtime retrieval item to multiple
verified canonical objects. Two retained tests expected the Adapter to expand
that one item into one item per canonical object, while the implementation and
metric code preserve the runtime item and its rank. A third retained test
expected `prompt_trace = false` even though the executed query path exposes the
rendered prompt and the Adapter declares the capability.

These disagreements were carried as three exact known failures so that a
workspace migration could not silently choose a semantic authority.

## Decision

1. Runtime retrieval output owns evidence-item identity, cardinality, and rank.
   One runtime item remains one `ObservedStageItem` at each observable stage.
2. A runtime item may carry zero, one, or many verified `ProvenanceEdge`
   references. Multiple edges are not separately ranked retrieval items.
3. Canonical identity and extent live on receipt-backed provenance edges, not
   on a best-effort locator attached to the runtime item.
4. LightRAG declares `prompt_trace = true` because it returns the rendered
   generation prompt observed on the actual query path. This capability does
   not include chain-of-thought or private model state.
5. The canonical-text provenance bridge publishes the evaluator's explicit
   `source_sha256`, `mapping_status`, and `expected_extent` fields.
   Authoring-side object status remains separate and is not treated as mapping
   status.

## Evidence

- `rag_eval.contracts.observation.ObservedStageItem` keeps native identity and
  rank separate from plural provenance-edge references.
- `rag_eval.evaluation.unified` applies cutoffs to native ranks and unions
  verified canonical extents.
- LightRAG native-observation tests cover one-item/many-edge behavior and the
  rendered prompt trace.

## Consequences

- The three former known failures become passing contract tests and are removed
  from the failure allow-list atomically.
- Canonical provenance can improve exact matching without inflating retrieval
  counts or changing ranks.
- Any future per-canonical-object ranking requires an explicit versioned
  contract and metric decision.

## Non-goals

This decision does not authorize an Adapter to change runtime rank or make
provenance part of Gold authoring. ADR 0003 and ADR 0004 own the current
Unified Trace and evaluation contracts.
