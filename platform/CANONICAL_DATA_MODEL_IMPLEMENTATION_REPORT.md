# Canonical Data Model P0 Implementation Report

**Date:** 2026-08-29  
**Scope:** Versioned Canonical Data Model and frozen 20-case external dataset
registry only.

## Result

This P0 phase is complete.  `rag_eval-platform` now has an explicit,
versioned, RAG-neutral Canonical Data Model 1.0 and its existing DOCX
Authoring pipeline writes a deterministic projection into that contract.
The current frozen 20-case dataset is registered externally as a frozen
development/reference diagnostic dataset.  No Bundle file, Gold, scorer,
metric, Adapter execution path, LightRAG code or production default changed.

## Formal Canonical Contract

The new formal contract is
[`src/rag_eval/contracts/canonical.py`](src/rag_eval/contracts/canonical.py).
It is the normative source-document model for future data-layer work;
`evidence.jsonl` and `objects.jsonl` remain a backwards-compatible Bundle 2.0
projection, not a second canonical schema.

Canonical Data Model 1.0 defines:

| Contract element | Delivered behavior |
| --- | --- |
| Object types | `document`, `section`, `heading`, `paragraph`, `text_span`, `table`, `row`, `cell`, `figure`, `caption`, `equation`, `reference`, `footnote`, `endnote`, and `embedded_object`. |
| Representation status | `complete`, `partial`, `unsupported`, `missing`.  `require_complete_object()` fails closed for every status except `complete`. |
| Source span | `ooxml-structural-v1`: safe package-relative part plus direct OOXML structural coordinates. `body_ordinal` is zero-based among `w:body` children; table row/column are one-based logical coordinates; optional text offsets are zero-based/end-exclusive Unicode code points in the normalized witness of the observed OOXML object. These are never page, chunk or retrieval offsets. |
| Provenance | Every object records source SHA-256, parser identity, canonicalizer identity, configuration digest, extraction method and direct source spans. Relations record their extractor and endpoint/span provenance. |
| Relations | Typed `parent_child`, `sibling`, `section_hierarchy`, `document_order`, `caption_of`, `reference_to`, `table_contains_row`, and `row_contains_cell`. Model validation rejects unknown endpoints, invalid relation shapes, backwards document-order links, hierarchy without a matching parent link, and siblings without a shared parent. |
| Manifest/digest | Deterministic document manifest with source digest, schema version, parser/canonicalizer identities, config digest, object/relation counts and individual/object+relation/canonical SHA-256 digests. Timestamps and runtime data are absent from digest inputs. |

## DOCX Authoring integration

[`src/rag_eval/authoring/canonical_adapter.py`](src/rag_eval/authoring/canonical_adapter.py)
maps existing extraction records directly to Canonical Data Model 1.0.  It does
not consult retrieval, ranking or runtime trace data.

The adapter preserves and derives direct DOCX structure as follows:

- paragraphs, headings and captions use the existing body-order and style
  locators;
- section nesting is computed from heading levels recorded during DOCX parsing;
- paragraph/text-span and parent/child links retain existing block IDs;
- table → row → cell uses the extractor's table IDs and logical row/cell
  coordinates;
- caption, reference and bookmark topology uses the already extracted adjacent
  object, field and bookmark data;
- figure, equation and note objects attach to their OOXML body anchor;
- partial OMML, VML/cross-reference, merged/nested table and unsupported OLE
  statuses are preserved exactly as non-complete canonical objects.

Each new analyzed Authoring workspace now includes, alongside the unchanged
Bundle 2.0 compatibility files:

```text
canonical/
  evidence.jsonl                         # existing Bundle 2.0 projection
  objects.jsonl                          # existing compatibility projection
  canonical-contract-manifest.v1.json    # formal Canonical Document manifest
  canonical-objects.v1.jsonl             # CanonicalObject records
  canonical-relations.v1.jsonl           # CanonicalRelation records
```

`CanonicalView`, Authoring analysis diagnostics and the summary now expose the
new contract digest and paths.  The existing `canonical_digest` remains the
legacy compatibility digest used by the current Authoring/Bundle path; the
new `canonical_contract_digest` is the formal-document identity.  This avoids
changing existing Bundle 2.0 serialization while giving all new data-layer
work one formal source model.

## Frozen 20-case registry entry

The external registry contract is
[`src/rag_eval/datasets/registry.py`](src/rag_eval/datasets/registry.py).
`PlatformService` bootstraps its immutable registry under
`RAG_EVAL_HOME/dataset-registry/`; it does not write to the Bundle Store.

The repository-visible source record is
[`registries/reference-datasets/d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e.json`](registries/reference-datasets/d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e.json).
It records exactly:

| Field | Value |
| --- | --- |
| Bundle ID | `d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e` |
| lifecycle | `frozen` |
| usage | `development/reference_diagnostic` |
| held_out | `false` |
| generalization_claim_allowed | `false` |

Registry records are content-digested and immutable by Bundle ID.  An attempt
to change an existing classification is rejected.  This is metadata outside
the Bundle: no file below `datasets/<bundle-id>/` is created or altered.

The private frozen Bundle bytes are intentionally not present in this checkout.
The regression test therefore locks the exact published Bundle ID, validates
the checked-in record digest, and proves Platform bootstrap creates only the
external registry file.  Existing Bundle 2.0 loading/registration tests pass;
the implementation never opens or rewrites the 20-case Bundle path.

## Compatibility and verification

| Check | Result |
| --- | --- |
| Canonical schema, relation, hierarchy and table-topology validation | Pass |
| Source-span/provenance validation | Pass |
| Partial/unsupported evidence fail-closed behavior | Pass |
| DOCX hierarchy/topology mapping | Pass |
| Deterministic DOCX rebuild | Pass: formal contract digest and emitted records match across identical source builds |
| Bundle 2.0 compatibility | Pass: legacy projection remains present and all existing Authoring/Bundle tests pass |
| Frozen 20-case identity / no Bundle mutation | Pass: exact Bundle ID and immutable external registry record verified; no Bundle directory is created |
| Platform test environment | Repaired: installed declared `lxml>=5.3` into `.venv` |
| Full Platform suite | **93 passed, 3 skipped** |

## Parallel-schema decision

There is no remaining parallel **formal** canonical schema in the Platform:
Canonical Data Model 1.0 is the formal contract.  Two non-normative
compatibility/historical representations remain intentionally:

1. existing `evidence.jsonl`/`objects.jsonl`, retained solely to preserve
   Bundle 2.0 and frozen historical Bundle behavior; and
2. legacy/prototype canonical artifacts outside the Platform, which are not
   imported or used by Platform Authoring.

Future source adapters must emit Canonical Data Model 1.0.  They may provide a
separate Bundle 2.0 projection only when its mapping is faithful and
backwards-compatible.

## Next-stage readiness and blockers

The Platform can proceed to **Authoring Ledger + Gold Lifecycle**.  This phase
deliberately did not add Bundle v3, held-out data, legacy import, Gold
revision/history, benchmark portfolio, evaluator changes or RAG optimization.

There is no implementation blocker for the next phase.  The only operational
constraint is intentional: the private 20-case Bundle source bytes are not in
the repository, so its historic content identity is protected by the
registered known Bundle ID rather than reconstructed locally.  It must remain
frozen and development-only during subsequent Authoring/Gold lifecycle work.
