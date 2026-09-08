# Unified Observation Contract (Wire 2.0)

- Status: implemented in Phase 3
- Schema version: `2.0`
- Live execution authority during Phase 3: Wire 1.0 `RAGResult`
- Scope: RAG-neutral observation, provenance, and transformation evidence

## Boundary

Wire 2.0 describes what a RAG exposed and what an Adapter can prove. It does
not contain Benchmark Gold, scoring policy, failure attribution, or a concrete
RAG implementation. The Platform may normalize a Wire 1.0 `RAGResult` into
this shape for shadow comparison, but normalization cannot manufacture proof
that Wire 1.0 did not capture.

The core envelope is:

```text
AdapterRunResultV2
  -> UnifiedTrace
       -> SourceIdentity
       -> RuntimeProfileIdentity
       -> ObservationProfileIdentity / AdapterCapabilitiesV2
       -> IngestionCatalogObservation / RuntimeChunkRecord[]
       -> StageObservation(candidate, ranked, context)
       -> ProvenanceEdge[] <-> CanonicalMappingRecord[]
       -> TransformationRecord[]
       -> ContentObservation(prompt, answer)
       -> validation receipts and trace digest
```

`rag_eval.contracts.observation.SourceIdentity` identifies a document and its
Canonical Catalog. It is intentionally distinct from the research package's
software/package `SourceIdentity`; callers should use module-qualified imports
when both concepts are present.

## Observation state

Availability and completeness are orthogonal:

```yaml
observation_status:
  observed | unsupported | unobserved | failed | corrupted
completeness:
  complete | truncated | partial | unknown
```

Only `observed` can carry scoreable observations. An observed empty tuple is a
verified empty observation; a missing observation is never normalized to an
empty result. Every non-observed status has `completeness=unknown`.
`corrupted` may retain diagnostic payload, but `proves_prefix(K)` always
returns false for it.

An ordered Top-K prefix is represented by:

```yaml
observation_status: observed
completeness: truncated
configured_cutoff: 20
proven_prefix_depth: 5
items: # ranks 1..5, contiguous and content-pinned
```

This proves only the first five results. It does not claim that the whole
ranking was observed.

## Runtime identity and provenance

Each observed stage item is content-addressed and points either to a runtime
ingestion record or to a verified transformation output. With a complete
ingestion catalog, an unknown ID, source mismatch, content mismatch, or native
lineage mismatch corrupts trace validation.

Positive canonical relations exist only as receipt-backed `ProvenanceEdge`
records. The allowed priority tiers are:

```text
native_lineage
> deterministic_crosswalk
> text_unique_exact
> missing
```

Missing, ambiguous, unsupported, and corrupt attempts use
`MappingDiagnostic`; they never receive a guessed canonical object ID.
Fuzzy or semantic text matching is outside the contract and cannot emit a
`ProvenanceEdge`.
Forward edges and reverse `CanonicalMappingRecord` entries must agree exactly
on native IDs and expected canonical extent. Their combined digest makes the
mapping set tamper-evident. Receipts establish contract integrity; Phase 4's
Adapter admission/TCK establishes that a RAG-specific producer earned the
claim it emits.

A complete ingestion catalog is required to prove parser/index coverage and
retrieval loss. It is not required merely to locate an observed ranked item:
an Adapter may still emit a verified deterministic or exact-unique edge for a
content-pinned stage item. In that case ranked coverage may become available,
while parser/index and retrieval-loss attribution remains unobservable.

## Stage transformations

Each transition is declared independently as:

- `identity_subset` for a pure filter/reorder;
- `verified_derivation` for merge, dedup, aggregation, compression, parent
  expansion, graph expansion, or another content-producing transformation;
- `unobservable` when the relation cannot be proved.

An `identity_subset` transition with a complete source observation rejects a
new target identity. A `verified_derivation` target requires a verified,
content-pinned receipt that names all observed source items. This proves the
derivation relation only. It does not prove that a summary or merged output
still covers canonical evidence; that requires a separate provenance edge for
the output content.

## Wire 1.0 compatibility

`normalize_rag_result_v1` is additive and does not mutate `RAGResult`:

- `None` becomes `unobserved` or `unsupported`, according to the frozen v1
  capability profile;
- an explicit empty list becomes `observed` with empty items;
- legacy items retain rank, native identity, score, and a content hash;
- completeness stays `unknown` because v1 has no prefix receipt;
- legacy locators and segment mappings remain unsupported diagnostics,
  not Wire 2.0 provenance;
- ingestion catalog and transformation lineage remain unsupported.

Therefore the compatibility trace is useful for shadow comparison and
Artifact migration, but it is not automatically eligible for Phase 5's
proof-driven retrieval metrics.

## Phase boundary

Phase 3 adds contracts, validators, public JSON Schemas, and a compatibility
normalizer only. It does not instrument LightRAG, replace live `RAGResult`
execution, score `UnifiedTrace`, or change APIs and WebUI. Those responsibilities
remain in Phases 4–7.
