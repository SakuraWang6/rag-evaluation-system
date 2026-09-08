# Canonical Conformance v1

Phase 2 makes Gold eligibility a property of the Platform-owned Canonical
Snapshot. It is not an Adapter admission result.

## Authority and artifacts

The policy authority is
`rag_eval.canonical.conformance.CANONICAL_GOLD_ELIGIBILITY_MATRIX`. The
canonicalizer evaluates that matrix through `CanonicalConformanceSuite` and
writes four content-addressed, immutable files under:

```text
canonical/snapshots/<canonical_digest>/
  manifest.json
  objects.jsonl
  relations.jsonl
  conformance.json
```

`conformance.json` is bound to the Canonical manifest by source SHA-256,
canonical digest, parser identity, canonicalizer identity, configuration
digest, object IDs, typed locator digests, witness hashes, and a report digest.
The formal Dataset loader verifies the file checksum and every binding before
accepting current-policy Gold. A changed source or implementation identity
creates a different snapshot directory; an existing snapshot file is never
rewritten with different bytes.

The legacy `canonical/objects.jsonl`, `canonical/evidence.jsonl`, and
`canonical/execution.md` files remain mutable working projections for Wire 1.0
and authoring compatibility. They are not the immutable Snapshot authority.

## First-wave decisions

The first policy admits conformant, non-empty paragraphs and text spans.
Tables and logical cells are admitted only when the table has complete,
unambiguous topology, an admitted header path, and data cells. Regular,
inferred regular-grid, horizontal-merge, vertical-merge, and mixed-merge
subtypes currently pass the suite.

The following fail closed:

- headerless, header-only, irregular/partial, and nested tables;
- logical cells whose parent table is missing or ineligible;
- physical cells as independent Gold (they remain topology and merge proof);
- every object with partial, unsupported, or missing representation;
- candidate objects with missing/duplicate typed locators, empty witnesses, or
  broken structural relations;
- types outside the first-wave candidate set, including figures and equations.

Figure, equation, physical-cell, and unsupported object records remain in the
Canonical Catalog for audit and future policy versions. Their exclusion from
Gold does not remove or downgrade the source representation.

## Compatibility boundary

Snapshots carrying the v1 policy marker require an explicit eligibility
decision on every canonical object and a valid conformance artifact. Historical
Canonical 1.0–1.2 snapshots without that marker retain their frozen read
semantics and are not regenerated or retroactively reclassified.

The authoring workflow now chooses logical cells for new table Gold. Physical
cell targets already frozen in historical artifacts remain readable through
the compatibility path.

No module in Canonical Conformance, Benchmark admission, formal validation, or
Bundle V3 imports Adapter capabilities. Adapter support begins affecting a Run
only in later observation and metric-availability phases.
