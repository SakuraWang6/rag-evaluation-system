# Unified Observation Contract (Direct Worker 2.0)

## Boundary

Worker 2.0 has one direct lifecycle:

```text
prepare(original_docx, resolved_config) -> PreparedSystemV2
query(prepared_system, NativeQueryV2)    -> AdapterRunResultV2
```

`prepare` performs native ingestion and binds the Original DOCX,
RuntimeProfile, ObservationProfile and ingestion receipt. `query` returns one
native answer and its `UnifiedTrace`. There is no protocol negotiation,
alternate envelope or normalization bridge.

The query contains no Benchmark Gold. The observation contract describes what
the RAG exposed and what the Adapter can prove; it does not score evidence or
attribute failures.

## Envelope

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

Every identity, content record, mapping set and transformation is
content-addressed. The validator rejects source, runtime, case, hash, rank,
lineage or receipt drift.

## Observation state

Status and completeness are independent:

```yaml
observation_status:
  observed | unsupported | unobserved | failed | corrupted
completeness:
  complete | truncated | partial | unknown
```

- `observed` carries `items`; an empty tuple is a proved empty result.
- `complete` covers the declared stage boundary.
- `truncated` is a correct ordered prefix and records configured cutoff plus
  `proven_prefix_depth`.
- `partial` means a known non-prefix omission.
- `unknown` means completeness cannot be proved.
- every non-observed status has `completeness=unknown`.
- corrupted payload may be retained for diagnosis but never contributes to a
  score.

An observed Top-5 prefix is enough for an `@5` metric even when the remaining
ranking is unknown. A missing stage is never normalized to an observed empty
result.

## Provenance

Formal mapping precedence is:

```text
native lineage
  > deterministic verified crosswalk
  > exact unique text
  > missing
```

Fuzzy or semantic matching cannot create a positive edge. Ambiguous text,
non-unique locators, content mismatch or invalid lineage fails closed.

Each positive `ProvenanceEdge` binds a runtime item and canonical extent.
`CanonicalMappingRecord` provides the reverse view. Forward and reverse IDs,
expected extents and their combined digest must round-trip exactly. Mapping
diagnostics represent missing, partial, unsupported, ambiguous or corrupt
attempts without guessing a canonical identity.

A complete ingestion catalog is necessary to prove parser/index coverage and
retrieval loss. It is not necessary to credit an independently verified
ranked item when the Adapter can prove its canonical mapping.

## Stage transformations

Each candidate-to-ranked and ranked-to-context transition declares one mode:

- `identity_subset`: pure filtering/reordering with retained native identity;
- `verified_derivation`: merge, deduplication, aggregation, compression,
  expansion or another content-producing transformation;
- `unobservable`: the Adapter cannot prove the relation.

For `identity_subset`, a complete source observation forbids a new target
identity. A `verified_derivation` output names every observed source item,
transformation kind, output identity/content digest, lineage status and
receipt. This proves derivation, not evidence survival. Context coverage also
requires provenance over the actual output content.

## Adapter neutrality and conformance

Observation hooks may wrap native calls, but must invoke the original once and
return its output unchanged. Enabling observation cannot alter chunks, rank,
context, prompt or answer.

Every Adapter result passes `rag_eval.adapters.observation_tck`. The shared TCK
covers complete and truncated prefixes, partial stages, unobserved stages,
identity subsets, verified derivations, output-level coverage and tamper
failures. Adapter-specific tests prove the runtime hooks that justify each
capability claim.

The [Unified Evaluation](UNIFIED_EVALUATION_V2.md) consumes only Canonical Gold
and a validated trace.
