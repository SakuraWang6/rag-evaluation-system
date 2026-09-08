# ADR 0001: Runtime Evidence Cardinality and Prompt Trace

- Status: Accepted
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
   One runtime item remains one `RAGEvidenceItem` at each observable stage.
2. A runtime item may carry zero, one, or many verified canonical provenance
   edges. Multiple edges are represented by `canonical_object_ids`,
   `canonical_edges`, and related plural metadata; they are not separately
   ranked retrieval items.
3. `RAGEvidenceItem.locator` is set only for exactly one unambiguous, fully
   covered canonical object. Matchers use verified plural IDs when the locator
   is intentionally absent.
4. LightRAG declares `prompt_trace = true` because it returns the rendered
   generation prompt observed on the actual query path. This capability does
   not include chain-of-thought or private model state.
5. The canonical-text provenance bridge publishes the evaluator's explicit
   `source_sha256`, `mapping_status`, and `expected_extent` fields.
   Authoring-side object status remains separate and is not treated as mapping
   status.

## Evidence

- `adapters/lightrag/src/rag_eval_lightrag_adapter/adapter.py` explicitly keeps
  canonical edges on one runtime item to preserve top-k/rank semantics.
- `platform/src/rag_eval/evaluation/evidence.py` matches plural
  `canonical_object_ids`.
- `platform/src/rag_eval/evaluation/metrics.py` applies cutoffs to runtime item
  ranks.
- `adapters/lightrag/tests/test_runtime_docx_and_trace.py` characterizes both
  one-item/many-edge behavior and the rendered prompt trace.

## Consequences

- The three former known failures become passing contract tests and are removed
  from the failure allow-list atomically.
- Canonical provenance can improve exact matching without inflating retrieval
  counts or changing ranks.
- Any future per-canonical-object ranking requires an explicit versioned
  contract decision, metric migration, and compatibility plan.

## Non-goals

This decision does not redesign provenance, lineage, SegmentTrace, Gold
matching, ranking, or evaluation metrics. It records the existing observable
behavior as the single authority.
