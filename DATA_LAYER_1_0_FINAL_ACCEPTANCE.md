# Data Layer 1.0 Final Acceptance

**Acceptance date:** 2026-08-30  
**Scope:** Benchmark Data Layer only. This acceptance adds no parser, Authoring, RAG, Adapter, execution, scoring, metric, Case, Gold, Release, or Bundle semantic change.

## Decision

> **PASS — Data Layer 1.0 accepted and frozen.**

Data Layer 1.0 has a complete, exercised development-data delivery loop:

```text
Raw DOCX
→ Canonical
→ typed Portfolio slot
→ Case / independent Gold
→ Review / Approval
→ Admission
→ Formal Validation
→ immutable Dataset Release
→ Bundle 3.0
→ runtime-only view
```

This conclusion is limited to the development-data DOCX workflow. It is not a claim of held-out readiness, generalization performance, image understanding, or source-format universality.

## Formal capabilities accepted in 1.0

| Layer | Accepted capability and authoritative contract |
| --- | --- |
| Canonical | `Canonical Contract 1.2`: deterministic, digest-pinned DOCX Canonical document with source spans, provenance, representation status, typed objects, and typed relations. It covers sections/headings, paragraphs/text spans, physical and logical table topology, figures/captions/media relations, equations, references, and notes. Canonical 1.0 and 1.1 readers exist only for immutable historical snapshots. |
| Complex tables | Physical/logical cells, row/column spans, merge origin, logical coordinates, physical↔logical mapping, explicit effective header path, and typed table/header relations. Only complete, explicit-header `gold_evidence_eligible=true` structures are Gold eligible. |
| Rich DOCX content | DrawingML figure/caption/text-reference/media lineage and raw OMML/tree/placement are retained. Figure Gold is limited to verified caption/text semantics; visual semantics remains explicitly unverified. |
| Authoring | Append-only Dataset, DocumentRevision, CaseRevision, GoldRevision, Review, Adjudication, Approval, invalidation, and supersession records. Gold has a stable ID and immutable revisions. |
| Gold semantics | Accepted answers/variants, evidence roles, MSES OR-path → AND-clause → OR-alternative structure, evidence necessity, multi-hop dependencies, bounded negative scope, near-miss/conflicting evidence, origin/trust, and freeze state. |
| Portfolio and policy | Typed Blueprint-derived slots, append-only actualization, deterministic coverage/deficit reports, source admission/isolation rules, and a distinct unpopulated held-out Portfolio contract. |
| Admission and validation | Admission preflight plus the single formal fail-closed validator. It emits versioned digest-pinned reports and blocks Release on any `ERROR`. |
| Release and lineage | Immutable Dataset Release pins source, Canonical, Case/Gold, review/approval, validation, schema, origin/config, and parent lineage. Rebuild is snapshot deterministic. |
| Delivery | `dataset-bundle/3.0` is a one-way, content-addressed projection of error-free frozen Release lineage, with full private evaluation semantics and an isolated runtime-only export. Bundle 2.0 remains a legacy compatibility projection. |

## Real end-to-end acceptance evidence

The exercised source is `XXX网站系统（S2A2G2）_V2.0.docx`.

| Check | Accepted evidence |
| --- | --- |
| Raw source | SHA-256 `7d50899d15356000782b292bb84e135e4f1ebe20672ba9799939a6a1e2861755` |
| Current Canonical | Contract 1.2, canonicalizer `/4`, append-only Canonical digest `f1bfe418f5b28ee2541dbe7e31bb0a5d098b106dfe5a8adcf9d03358bb305ed6` |
| Development Portfolio | `benchmark-v0-dry-run-48`, contract digest `dfc51b1ed537eac24956a55d2b70f5bf832585bf0bf281a84600e4ef8404428b` |
| Terminal slots | 33 `frozen`, 15 `blocked`, 0 non-terminal; coverage report digest `ada7f06bfced1afd25520894b7371d354d7e392982b6e01863aee53658bfa9c3` |
| Release lineage | Parent `dataset-release-4758bfcc6b91c492bac9c9f2` pins 8 pilot Cases/Golds; successor `dataset-release-bcc904a2f011e567e5fb5548` pins 25 additional Cases/Golds. |
| Formal validation | Parent report `f94d64ca60ac414fda5f63c924a0e2c7180fc5ce638557d6c5f9faa57f8644b7`; successor report `af71ef588a4fe4c0a657703ab527e1111c90ea09165d6b12ec57a1ff19c765c5`; both revalidated with no `ERROR`. |
| Bundle 3.0 | Private Bundle `d7673da5d1bee5708f2c2564c4bbabdd85b2cbd86a98eaf5426d6a76905a74f6`: 33 unique Cases, 33 unique Golds, 63 evidence records, and all frozen Portfolio bindings. |
| Runtime-only view | `a4a79e4d7b0f1fc31da7a2f7f24f9df48ef84ed41c195dd66ba95b7b94e3e82d`: 33 questions and exactly `manifest.json`, `questions.jsonl`, `checksums.json`, and the source DOCX. There is no `private/` directory or Gold artifact. |

The Bundle uses the immutable Canonical 1.0/1.1 snapshots pinned by the two Releases, not the later mutable Canonical 1.2 workspace. This is required for reproducibility: a later Canonicalization can enter only a future successor Release.

The packaged 33 Golds include four multi-hop dependency graphs, four alternative MSES paths, four abstention answers with bounded negative scope, and 16 logical-cell evidence records. The package contains 124 review records and 66 approvals pinned by release lineage. Its loader validates source, Canonical manifests/objects/relations, release pins, validation reports, review/approval lineage, MSES, dependencies, negative scopes, checksums, and runtime/private agreement.

## Single source of truth and boundary audit

| Concern | Sole authoritative source | Not authoritative |
| --- | --- | --- |
| Raw source identity | Immutable source snapshot/digest pinned by `DatasetRelease` | Runtime copy in Bundle 3.0 |
| Canonical object graph | `CanonicalDocument` and its versioned manifest | Bundle copy, legacy extraction fields, retrieval traces |
| Case, Gold, Review, Approval, Adjudication | Append-only Authoring Ledger revisions | `QuestionCandidate` compatibility/workflow fields, Bundle JSONL |
| Planning and coverage | Immutable Portfolio plus append-only assignments | CSV/Markdown after immutable import |
| Source/Case admission | Versioned Admission policy/report | a model suggestion or Authoring proposal |
| Formal freeze | Formal Dataset Validator report and immutable Dataset Release | Bundle 2.0 representability gate |
| Delivery | Bundle 3.0 private package and runtime export | Bundle 3.0 as an importer or Ledger replacement |

No formal duplicate or conflicting contract remains. Compatibility boundaries are intentional:

- Canonical 1.0/1.1 are historical readers; Canonical 1.2 is the only current Canonical contract.
- `QuestionCandidate` and Bundle 2.0 are legacy workflow/execution projections; they cannot create or overwrite approved Gold.
- Portfolio owns planning/coverage, not Case or Gold content.
- Admission decides eligibility before Release; Formal Validator is the only release gate; Bundle 3.0 validates delivery after release.

## Reproducibility and frozen references

- Both historical Releases rebuilt to their exact pinned validation report digest. Immutable JSON SHA-256 values remain `04064248a82b6351ad4690fdd5d6273f370ec3c52b2be79f985e61631227bca8` (parent) and `49563d06cdbd428c0ff6c1dc781399d19632a98796713036ab4d6119c1720669` (successor).
- Bundle 3.0 rebuilt to the same private/runtime content IDs. Tampering with Gold, source snapshot, Canonical/release pins, or checksums fails closed.
- Frozen 20-case Bundle ID remains `d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e`. Its registry record is byte-identical (SHA-256 `c0b050e1481e8e1c7a9fc579db033797f0a406eca4cb2275c1c87fc454ec6750`) and retains `frozen`, `development/reference_diagnostic`, `held_out=false`, and `generalization_claim_allowed=false`.
- The private frozen-20 Bundle payload is intentionally not mounted in this checkout, so this acceptance cannot re-hash those external private bytes. No Data Layer 1.0 operation writes, imports, or re-registers it; the immutable ID and registry bytes are the local auditable proof.

## Known limits and classification

### Not 1.0 blockers

- DOCX is the only formal raw-input chain.
- Image visual semantics is not trusted Gold; figures support only verified caption/text/reference semantics.
- VML/OLE remain partial/unsupported. Unresolved figure references, unanchored notes, partial references, and non-eligible objects cannot be Gold evidence.
- Header/footer OOXML parts remain outside Canonical traversal and are prohibited as Gold evidence.
- The one real source cannot naturally fill every 48-slot category: 15 slots remain correctly blocked, including authentic ambiguity/conflict classes and the natural figure-to-equation relation chain.
- A separate held-out Portfolio contract exists, but no held-out source, Case, Gold, frozen release, or benchmark exists. The 20-case and 33-case sets are development-only and cannot support generalization claims.
- PDF, HTML, multi-document collections, and legacy import are outside this release.

### Data Layer 1.0 blockers

**None.** Each limitation is an explicit `partial`, `unsupported`, `blocked`, or out-of-scope boundary. None invalidates the proven DOCX development lifecycle.

## Freeze rules

Do not modify the following in place:

1. Canonical 1.2 object/relation/status/provenance/locator semantics and fail-closed Gold-eligibility rules.
2. Authoring Ledger lifecycle, revision immutability, reviewer separation, and Gold/MSES/dependency/negative-scope semantics.
3. Portfolio 1.0 typed axes and terminal assignment history. A blocked slot must not be silently re-opened or relabelled as complete.
4. Admission policy 1.0, Formal Validator 1.0 rule/report semantics, and Release 1.0 pinning/identity rules.
5. Both existing Releases, their source/Canonical snapshots, reports, Case/Gold revisions, and lineage.
6. Bundle 3.0 private/runtime isolation, checksum/digest algorithm, and frozen Bundle outputs.
7. Frozen-20 registry classification and historical Bundle identity.

Any future change must be additive and versioned: new DocumentRevision, Case/Gold revision, validation report, successor Dataset Release, and new Bundle digest. It must not rewrite an earlier artifact to appear to have newer semantics.

## Backlog after 1.0

### Data Layer 1.x

- Operationalize held-out governance: isolated source families, calibration lock, and a reviewed/frozen held-out release without Gold or failure-knowledge leakage.
- Add real documents that naturally cover the 15 blocked types; do not manufacture them from the current source.
- Extend DOCX parsing only where a future dataset needs it: header/footer traversal, further resolved references/notes, and rich-object relations.
- Create successor Releases under Canonical 1.2 when a naturally supported caption/text/equation Case is authored and reviewed.

### Data Layer 2.0 or separate approvals

- PDF, HTML, existing-canonical, and multi-document ingestion under the same lifecycle.
- Auditable visual-semantic evidence with a separate evidence/review contract; never reclassify current unverified media retroactively.
- VML/OLE/embedded-object semantics and any legacy importer.

## Verification performed

```text
pytest -q
133 passed, 3 skipped, 1 third-party deprecation warning
```

The two historical formal Releases were rebuilt from pinned snapshots and reproduced their exact validation digests. The real Bundle 3.0 and exported runtime-only view loaded and validated successfully.

## Required answers

1. **Is Data Layer 1.0 complete?** Yes, for its defined DOCX development-data lifecycle and delivery boundary.
2. **Is Raw DOCX → frozen Benchmark → Bundle 3.0 a real closed loop?** Yes; it was exercised through 33 frozen Cases/Golds and immutable parent/successor Release lineage.
3. **What are the unique sources of truth?** CanonicalDocument for Canonical; Authoring Ledger for Case/Gold/review/approval; Portfolio for planning; Admission report for intake; Formal Validator plus Dataset Release for formal freeze; Bundle 3.0 only for delivery.
4. **What limitations remain?** The explicit DOCX-only, rich-media, source-coverage, held-out, and additional-format limits above.
5. **Must anything be fixed before the next phase?** No Data Layer 1.0 blocker. Held-out work has external governance/source prerequisites, not an acceptance repair.
6. **What is frozen?** The seven artifact/contract classes in *Freeze rules*, including historical Releases, Bundle semantics, and frozen-20 classification.
7. **What enters 1.x / 2.0?** Held-out operationalization and targeted DOCX additions in 1.x; new raw formats, multi-document, visual semantics, VML/OLE, and importer work in 2.0 or separate scopes.
8. **Can Data Layer 1.0 formally end now?** Yes.

> **PASS — Data Layer 1.0 accepted and frozen.**
