# Bundle 3.0 Implementation Report

## Outcome

Bundle 3.0 (`dataset-bundle/3.0`) is now the formal, immutable delivery
projection for a validated frozen Dataset Release. It is not an Authoring
importer and is not a second source of truth: Canonical + Authoring Ledger +
Gold + Dataset Release remain authoritative. The builder reads those immutable
records, validates them, and writes a content-addressed package. It has no
write path back to Canonical, ledger, Release, or Bundle 2.0.

The real development release was built successfully:

| Item | Result |
| --- | --- |
| Target release | `dataset-release-bcc904a2f011e567e5fb5548` |
| Effective immutable release closure | `dataset-release-4758bfcc6b91c492bac9c9f2` → target release |
| Bundle ID | `d7673da5d1bee5708f2c2564c4bbabdd85b2cbd86a98eaf5426d6a76905a74f6` |
| Runtime-only Bundle ID | `a4a79e4d7b0f1fc31da7a2f7f24f9df48ef84ed41c195dd66ba95b7b94e3e82d` |
| Effective frozen Case / Gold | 33 / 33 |
| Evidence records | 63 |

The target release itself pins 25 Case/Gold revisions; its immutable parent
pins the original 8 pilot revisions. Bundle 3.0 intentionally materializes
the release-lineage closure with successor-overrides, so all 33 frozen
development Cases are delivered without modifying either Release or historical
Case/Gold records.

## Contract and package layout

The implementation is in [bundle_v3.py](src/rag_eval/datasets/bundle_v3.py),
with platform-owned paths in [layout.py](src/rag_eval/storage/layout.py) and
a reproducible command at [build_bundle_v3.py](scripts/build_bundle_v3.py).

```text
bundle-v3/<bundle-id>/
├── manifest.json
├── checksums.json
├── runtime/                         # source + question-only, exportable
│   ├── manifest.json
│   ├── questions.jsonl
│   ├── source/<source-digest>.docx
│   └── checksums.json
└── private/                         # evaluator-only
    ├── dataset.json
    ├── cases.jsonl
    ├── gold.jsonl
    ├── evidence.jsonl
    ├── canonical/<release-id>/{manifest,objects,relations}
    └── lineage/{releases,reviews,approvals,adjudications,validation}/
```

Every Case record retains its Case revision and typed Portfolio assignment.
Every Gold record retains its full independent Gold revision, accepted answer
and variants, evidence roles, all MSES paths/clauses/alternatives, dependency
graph, bounded negative scope/rationale, review, approval, and adjudication
lineage. Evidence records carry the original Gold evidence record plus the
complete Canonical object, including locator, source spans, provenance, and
Gold-eligibility attributes.

Canonical snapshots are copied by release pin, not regenerated from the live
document. This preserves complex-table physical/logical cells, span geometry,
merged-cell origin, logical coordinates, effective header paths and topology;
it also preserves Canonical 1.2 figure/caption/media and equation OMML fields
when a frozen release contains them.

## Validator and boundaries

The Bundle 3.0 loader is the delivery validator. It fails closed for:

- incomplete manifest/layout/checksum or content-address mismatch;
- altered source, Canonical, Release, validation report, Case/Gold pin, or
  review/approval lineage;
- non-frozen revisions, missing typed frozen Portfolio binding, unreachable or
  Gold-ineligible evidence, locator/provenance divergence, or duplicate
  evidence keys;
- incomplete MSES witnesses, dependency cycles/references, or omitted bounded
  negative scope;
- invalid Canonical relation/table/figure/equation structures (via the formal
  Canonical Contract validation);
- a runtime view that exposes an unknown/private artifact or differs from the
  private Case questions.

The package is private by default. `export_runtime_view()` copies only:

```text
manifest.json
questions.jsonl
checksums.json
source/<digest>.docx
```

It contains no answer, evidence, MSES, negative scope, near-miss label,
review, approval, canonical snapshot, or `private/` directory. The real
runtime export contains exactly those four files.

## Real-release verification

Rebuilding the target produced the same private Bundle ID and runtime Bundle
ID shown above. The source snapshot digest is verified against each release
pin; the package uses the target's two immutable Canonical snapshots (schema
1.0 for the parent and 1.1 for the target), rather than silently substituting
the later mutable Canonical 1.2 workspace.

The effective 33 Gold revisions include:

| Semantics | Count |
| --- | ---: |
| multi-hop dependency graph | 4 |
| alternative MSES path | 4 |
| abstention answer | 4 |
| bounded negative scope | 4 |
| logical-cell evidence records | 16 |
| physical-cell evidence records | 12 |

No selected real Gold currently uses a figure or equation: that is a property
of this historical 33-Case release, not a Bundle limitation. Bundle 3.0
round-trip tests cover the 1.2 figure boundary (`caption_and_text_only` with
unverified visual semantics) and equation raw-OMML/tree/locator preservation.
An unverified visual semantic therefore cannot be presented as usable Gold.

The source Release JSON digests remain unchanged after package creation:

```text
dataset-release-4758bfcc6b91c492bac9c9f2  04064248a82b6351ad4690fdd5d6273f370ec3c52b2be79f985e61631227bca8
dataset-release-bcc904a2f011e567e5fb5548  49563d06cdbd428c0ff6c1dc781399d19632a98796713036ab4d6119c1720669
```

## Backward compatibility

Bundle 2.0 has not been changed, rewritten, or used as a Bundle 3.0 input.
Its existing reader continues to load schema version 2. Formal Release's
existing explicit Bundle 2.0 lossless/lossy projection remains intact; Bundle
3.0 is the default delivery path for releases requiring the richer Gold
semantics. It does not claim a Bundle 2.0 ID for a lossy projection.

The frozen 20-case registry record is byte-identical:

```text
Bundle ID: d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e
Registry file SHA-256: c0b050e1481e8e1c7a9fc579db033797f0a406eca4cb2275c1c87fc454ec6750
lifecycle=frozen; usage=development/reference_diagnostic;
held_out=false; generalization_claim_allowed=false
```

## Verification

New focused tests cover deterministic construction, MSES AND/OR path and
clause preservation, multi-hop dependencies, alternative paths, negative
scope, complex logical-table evidence, figure/equation representation,
runtime/private separation, Gold leakage prevention, tamper detection,
release-source mismatch, Bundle 2.0 reading, and frozen-20 registry stability.

```text
pytest -q tests/rag_eval_platform/test_bundle_v3.py                                  5 passed
pytest -q tests/rag_eval_platform/test_bundle_v3.py \
          tests/rag_eval_platform/test_formal_release_lineage.py \
          tests/rag_eval_platform/test_authoring_ledger.py \
          tests/rag_eval_platform/test_authoring.py                                   27 passed
pytest -q tests/rag_eval_platform/test_bundle_v3.py \
          tests/rag_eval_platform/test_complex_table_canonicalization.py \
          tests/rag_eval_platform/test_rich_content_canonicalization.py               15 passed
```

## Answers

1. **Can Bundle 3.0 losslessly express current formal Gold?** Yes. Full
   GoldPayload and the selected release's Canonical objects are preserved;
   Bundle 3.0 is not a flattened Bundle 2.0 projection.
2. **Were all 33 real Cases packaged?** Yes, through the immutable
   parent-to-successor release closure.
3. **Are MSES, multi-hop, and unanswerable semantics preserved?** Yes. The
   formal MSES graph is retained verbatim; dependencies and negative scope are
   validated and represented separately as needed.
4. **Is complex-table logical structure preserved?** Yes. Complete Canonical
   snapshots and relations are included, with 16 actual logical-cell evidence
   records in the real package.
5. **Are figure/equation Gold boundaries strict?** Yes. Their complete
   Canonical metadata is retained and Canonical eligibility validation applies;
   unverified visual semantics remains ineligible.
6. **Are runtime input and private evaluation data isolated?** Yes. The
   runtime export has an allowlisted four-file layout and no Gold content.
7. **Is the Bundle deterministic, immutable, and tamper-detectable?** Yes.
   It is content-addressed, rebuilt to the same IDs, and validates all file,
   source, Canonical, Release, and semantic digests fail-closed.
8. **Is Bundle 2.0 compatibility retained?** Yes; its reader and all historical
   artifacts remain untouched.
9. **Is the frozen 20-case Bundle unchanged?** Yes; its ID and registry bytes
   are unchanged.
10. **Is the Data Layer 1.0 delivery loop complete?** Yes for the scoped
    development data flow: frozen validated Release → lossless private Bundle
    → isolated runtime view. This does not assert held-out readiness or create
    held-out data. There is no Bundle 3.0/Data Layer blocker; a future release
    that needs figure/equation Gold must first be formally authored, reviewed,
    validated, and frozen under Canonical 1.2.
