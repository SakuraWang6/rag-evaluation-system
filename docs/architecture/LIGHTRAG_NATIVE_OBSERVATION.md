# LightRAG Native DOCX Observation

## Boundary

```text
Original DOCX bytes
  -> LightRAG native upload / parser / chunker / index
  -> persisted native chunk catalog
  -> one LightRAG query with trace observation enabled
  -> Adapter validation and canonical projection
  -> AdapterRunResultV2 / UnifiedTrace
```

The Adapter consumes runtime state plus the Platform-produced Canonical
Catalog. It does not consume Gold, modify the question, inject evaluation
candidates, reorder results, rewrite context or issue a second query.

## Ingestion proof

`prepare` accepts one checksum-pinned DOCX and a resolved configuration. After
native ingestion, the Adapter freezes:

- native document and chunk IDs;
- exact chunk content and SHA-256;
- native parser lineage and digest;
- parser and chunker identities;
- persisted metadata digest;
- Original DOCX and Canonical Catalog digests; and
- the actual index fingerprint and receipt.

Source bytes are verified before ingestion. Stored content and lineage are
checked again when the provenance map is built. Missing or inconsistent
identity fails closed; it is not reconstructed from a semantic match.

## Canonical coverage

Mapping uses native lineage first, then a deterministic verified crosswalk.
Direct edges bind source identity, structural locator, canonical witness,
runtime content and lineage receipt. Duplicate text is only a witness after a
unique structural selection; it is never the selector.

The crosswalk can project:

1. a verified paragraph to its canonical text-span child; and
2. verified physical table cells to logical-cell and table extents.

Table extents are sets of physical-cell atoms. This supports one chunk covering
multiple evidence objects, several chunks jointly covering a logical cell,
split rows, and horizontal/vertical merge footprints. Partial edges remain
partial until their verified union covers the complete extent.

Every positive edge has a content-bound receipt. Forward edges and reverse
mapping records must round-trip exactly. Objects the Adapter cannot prove stay
in the Benchmark and make only the affected metrics unavailable.

## Stage profile

Candidate, ranked and final-context items retain exact native ID, rank,
content, score and provenance references. A pure native filter/reorder declares
`identity_subset`.

Structured exact-ID behavior can introduce items not present in the raw hook.
When that relation cannot be proved, candidate observation is partial and the
candidate-to-ranked transition is `unobservable`. Ranked and context stages
may still be evaluated independently.

Any future merged, summarized, expanded or compressed context identity must
declare `verified_derivation` and provide a transformation receipt plus
canonical coverage over the actual output content.

## Neutrality and conformance

The result is built from the same native response returned to the Platform.
Observation checks native identity, rank, content and score without replacing
them. A tracing failure becomes `failed` or `corrupted`; it does not trigger a
second query or a guessed result.

Adapter tests cover original-DOCX upload, source drift, catalog and lineage
receipts, duplicate text, one-to-many and many-to-one evidence mapping,
split/merged tables, complete/partial stages and one-query neutrality. The
result also passes the shared Adapter TCK.
