# Development Benchmark 48 Authoring Report

## Outcome

The real-document development Portfolio is terminal and auditable: all 48
`benchmark-v0-dry-run-48` slots are either frozen or structurally blocked. No
LightRAG, Adapter execution, retrieval/ranking experiment, answer-accuracy
test, held-out source, or frozen-20-case Bundle was used or changed.

| Portfolio state | Slots | Meaning |
| --- | ---: | --- |
| `frozen` | 33 | 8 preserved pilot Cases plus 25 newly authored real-DOCX Cases/Golds |
| `blocked` | 15 | The actual source cannot meet the original typed requirement without manufacturing evidence or ambiguity |
| non-terminal | 0 | No `planned`, `authored`, `reviewed`, or `approved` slot remains |

The output is stored in the existing development-authoring workspace
`/Users/sakura/RAG/.rag-eval-real-benchmark-pilot`. Its machine-readable,
deterministic run record is `development-benchmark-48-summary.json`.

## Source and Canonical lineage

| Field | Value |
| --- | --- |
| Source | `XXX网站系统（S2A2G2）_V2.0.docx` |
| Source SHA-256 | `7d50899d15356000782b292bb84e135e4f1ebe20672ba9799939a6a1e2861755` |
| Canonical Contract | `1.1` |
| Canonicalizer | `rag-eval-authoring-canonicalizer/3` |
| Canonical digest | `4b52e327a691db86411dc5d17138b2c3ac2616d7240790ae804fb029d9112c97` |
| Canonical configuration digest | `01a020ec981851b66ce9ff0241fe01077339a84fb3c0e49b0f4670687b5d8537` |
| Document revision | `document-revision-4867d37a2e17407e8ec774794e853b3c-000002` |

Every new Gold uses only an explicit `CanonicalEvidenceScope` over audited,
Gold-eligible Canonical objects. The driver rejects partial, unsupported, or
unmodelled evidence before draft creation. Text Cases use complete paragraph/
text spans; table Cases use only eligible tables and legal logical cells.

## Actualized Cases and evidence

25 new human evidence-first Case/Gold pairs were added. Each followed the
same sequence: Portfolio slot → verified Canonical evidence → Gold/MSES →
Case proposal → two independent reviews → independent approval → admission
preflight → formal validation → immutable release.

The existing eight frozen pilot slots were preserved without a revision or
Bundle change:

`DRY-02-slot-04`, `DRY-03-slot-04`, `DRY-04-slot-04`,
`DRY-05-slot-04`, `DRY-06-slot-04`, `DRY-07-slot-04`,
`DRY-10-slot-04`, and `DRY-12-slot-04`.

The added set supplies real instances of semantic single-evidence retrieval,
independent multi-evidence synthesis, dependent multi-hop remediation,
comparison, aggregation, conditional controls, bounded negative/
unanswerable evidence, and OR alternative evidence paths. MSES paths remain
in the Gold contract; they were not reduced to Bundle 2.0 fields.

### Complex tables

Three new Cases use Canonical 1.1 logical-cell topology:

- `DRY-07-slot-01`: multi-level vulnerability-count aggregation.
- `DRY-07-slot-02`: comparison under the multi-level Data Integrity header.
- `DRY-07-slot-03`: row filtering in the multi-level management-personnel summary.

Each cited logical cell has an effective header path and a provenance hop to
the physical cell. The authoring driver asserts these properties before any
Ledger write, so a merged cell cannot silently become an inferred table
meaning. Together with the retained pilot table Case, all four `table plus
text` Portfolio slots are frozen.

## Final typed coverage

The deterministic Coverage/Deficit report digest is
`ada7f06bfced1afd25520894b7371d354d7e392982b6e01863aee53658bfa9c3`.

| Capability / dimension | Frozen / planned | Blocked |
| --- | ---: | ---: |
| Table plus text | 4 / 4 | 0 |
| Dependent multi-hop | 4 / 4 | 0 |
| Bounded unanswerable | 4 / 4 | 0 |
| Alternative evidence paths | 4 / 4 | 0 |
| Independent multi-evidence | 4 / 4 | 0 |
| Comparison | 4 / 4 | 0 |
| Aggregation | 4 / 4 | 0 |
| Conditional reasoning | 4 / 4 | 0 |
| English / Chinese | 25 / 36; 8 / 12 | 11; 4 |
| Text / table-plus-text / figure-equation-text | 29 / 40; 4 / 4; 0 / 4 | 11; 0; 4 |
| Human / semi-synthetic / synthetic / adversarial plan types | 12 / 12; 9 / 12; 8 / 12; 4 / 12 | 0; 3; 4; 8 |

The imported Blueprint keeps `source_family=unassigned` as its immutable
planning value. Actualized slots resolve through the typed source-admission
record `real-docx-development-family`; this is a development-only source and
is explicitly not eligible for held-out use.

## Structured blocks

Blocks are valid results, not failed or downgraded Cases. They are append-only
Portfolio assignments with a typed reason:

| Slots | Typed reason | Evidence-based rationale |
| --- | --- | --- |
| `DRY-02-slot-01` to `-03` | `authentic_ambiguity_unavailable` | The English lexical-near-miss candidates are near-duplicate asset summaries. They contain no natural, unique discriminator; using only their leading entity labels would create ambiguous Gold. |
| `DRY-08-slot-01` to `-04` | `unsupported_modality` | Figure/caption/equation material is not Gold-eligible in the audited Canonical output. |
| `DRY-09-slot-01` to `-04` | `no_valid_conflict` | The single source has no audited temporal/version conflict with an authoritative resolution path. |
| `DRY-11-slot-01` to `-04` | `authentic_ambiguity_unavailable` | No unresolved ambiguity can be evidenced without manufacturing a conflict. |

Consequently, the current document does not provide valid rich
figure/equation, authentic conflict, or unresolved-ambiguity data. It should
not be used to claim those coverage categories are complete.

## Review, approval, admission, and release

All 25 new Cases and Golds have two independent reviewers (including the
stricter requirement for table, multi-hop, alternative-path, and unanswerable
Cases). The author identity is distinct from both reviewers and the release
manager. The review records attest to question naturalness, ambiguity, answer
correctness, evidence sufficiency/minimality, alternative answers, and
difficulty. Approval is never generated directly by the author.

Admission preflight succeeded with report digest
`fd94cd58e2d841116158466245d92fcc246d21a580094a07caf4036e56e1e0ae`.
The immutable successor release is:

| Field | Value |
| --- | --- |
| Release | `dataset-release-bcc904a2f011e567e5fb5548` |
| Version | `development-real-docx-v3-48-actualization-1.0.0` |
| Parent | `dataset-release-4758bfcc6b91c492bac9c9f2` (the preserved 8-case pilot) |
| Release digest | `bcc904a2f011e567e5fb5548a067c29f674d5c2f5da671ad927a8a64563898bb` |
| Formal validation digest | `af71ef588a4fe4c0a657703ab527e1111c90ea09165d6b12ec57a1ff19c765c5` |
| Rebuild | reproducible |
| Tamper check | detected and failed closed; report `3b9e64a811b273d698f8aaf9e0a2d970ed6e6cc916f1126370f38f0890d78dcb` |

The new release pins its 25 new Case/Gold revisions and Canonical document
revision. The parent release remains immutable and pins the historical pilot
revisions. Both releases rebuilt reproducibly; the historical pilot validation
digest remains `f94d64ca60ac414fda5f63c924a0e2c7180fc5ce638557d6c5f9faa57f8644b7`.
The complete 33-Case development state is therefore the typed parent/successor
lineage pair, rather than a rewritten flat release that would mutate the
pilot's historical Canonical pin.

Bundle 2.0 was not exported or rewritten. The frozen 20-case registry entry
is byte-identical in the repository and development workspace (SHA-256
`c0b050e1481e8e1c7a9fc579db033797f0a406eca4cb2275c1c87fc454ec6750`),
with Bundle ID
`d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e`,
`lifecycle=frozen`, `usage=development/reference_diagnostic`,
`held_out=false`, and `generalization_claim_allowed=false`.

The release validator records `bundle_v2.projection_lossiness` as a `WARN`
with result `FAIL`: alternative MSES paths and multi-hop dependencies cannot
be represented losslessly by Bundle 2.0. This does not block the formal
release, but it explicitly prevents treating it as a complete runnable Bundle
2.0 export.

## Verification

- `122 passed, 3 skipped` in the complete Platform test suite.
- The Portfolio contract now fail-closes a blocked assignment without a typed
  reason, or a typed blocked reason on any non-blocked state.
- Existing tests cover MSES necessity, alternate paths, dependency graphs,
  negative scope, complex-table topology, invalid evidence, release
  immutability, deterministic rebuild, and tamper detection. The real-DOCX
  driver adds its own pre-write assertions for eligible evidence and logical
  table-cell lineage.

## Decision

There is no remaining **Data Layer infrastructure blocker**: the source →
Canonical → Case/Gold → review/approval → admission/validation → frozen
release production loop has been performed on real data, and every planned
slot now has a terminal state.

The development set is sufficient to move to document-set expansion and
held-out planning, but not to assert full 48-category coverage from this one
document. The next source should deliberately supply isolated, Gold-eligible
figure/caption/equation content, authoritative temporal/version conflicts,
and genuinely unresolved ambiguity. Held-out authoring itself remains outside
this phase.
