# Canonical Benchmark and Conformance

## Authority

The Platform alone decides whether source evidence is stable enough to become
Gold. `rag_eval.canonical.conformance.CANONICAL_GOLD_ELIGIBILITY_MATRIX` and
`CanonicalConformanceSuite` are the policy authority. No Adapter capability,
RAG name, runtime chunk or leaderboard requirement participates in this
decision.

An Adapter that cannot map an eligible Gold type produces unavailable metrics
for that Run. It does not remove the Gold or create another Benchmark.

## Snapshot identity

The identity inputs are:

```text
DOCX bytes
+ parser identity
+ canonicalizer identity
+ configuration digest
```

Equal inputs must reproduce equal objects, relations, typed locators, witness
hashes and Canonical digest. Changing any identity input creates a different
Snapshot. Published Snapshots are immutable and are never regenerated in
place.

The content-addressed Snapshot contains:

```text
canonical/snapshots/<canonical_digest>/
  manifest.json
  objects.jsonl
  relations.jsonl
  conformance.json
```

`object_id` is a Snapshot-local reference key. Identity validation also binds
the DOCX SHA-256, coordinate-system version, typed structural locator,
canonical witness hash, parser/canonicalizer/configuration identities and
representation status.

## Gold eligibility

The current candidate families are paragraph, text span, table and logical
cell. A concrete type or subtype is eligible only after its object identity,
locator, witness and required relations pass Conformance.

Current fail-closed cases include:

- empty or duplicate witnesses and non-unique typed locators;
- partial, unsupported or missing source representation;
- broken parent, table-topology, merge-origin or membership relations;
- headerless, header-only, irregular/partial or nested tables;
- logical cells whose parent table is not eligible;
- physical cells as independent Gold; and
- figures, equations or other types without an admitted Conformance policy.

Physical cells and merge relations remain proof material for logical-cell and
table extents. Unsupported objects remain in the Catalog for audit and future
policy versions.

Canonical and research contracts may retain their own active `1.x` schema
versions. Those numbers do not denote a Worker or Run compatibility path.

## Case and Gold admission

A formal case is bound to a reviewed Portfolio slot and one immutable Release.
Admission verifies:

- source and Canonical identities;
- question, answer and Gold revision lineage;
- reachable Canonical evidence for every Gold alternative;
- MSES clause/path structure and evidence necessity;
- a dependency graph for declared multi-hop cases;
- an evidence-backed negative scope for abstention cases;
- answer leakage and duplicate/contamination checks; and
- the required independent human review decisions.

Gold uses minimal-sufficient-evidence-set semantics. Evidence alternatives
inside one clause are OR; clauses in one path are AND; alternative complete
paths remain distinct. Gold is anchored to canonical source extents, never a
RAG chunk ID.

Models may propose questions, rewrites, answers, evidence or distractors, but
their output is proposal-only. Programs verify objective structure and
provenance. Humans decide naturalness, ambiguity, answer correctness,
sufficiency and minimality. Unresolved review cannot be frozen into a Release.

## Runtime boundary

The immutable Release resolves directly to the Original DOCX required by the
RAG and observer-only Canonical material required to prove provenance. There
is no executable runtime-bundle projection. Canonical content is not inserted
as a second corpus and does not control native chunking.

The [Benchmark Authoring Guide](../../platform/docs/BENCHMARK_AUTHORING.md)
describes source admission, review, held-out isolation and blind operation.
The [Unified Observation Contract](UNIFIED_OBSERVATION_CONTRACT.md) begins
where runtime content is mapped back to these coordinates.
