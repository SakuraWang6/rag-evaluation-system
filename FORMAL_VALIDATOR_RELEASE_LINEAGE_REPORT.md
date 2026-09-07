# Formal Dataset Validator, Frozen Release & Lineage — P0 Report

## Scope and outcome

This phase adds the Platform's single formal Dataset validation and release
authority in `rag_eval.datasets.formal`.  It consumes the existing Canonical
Data Model 1.0 and append-only Authoring Ledger; it does not change LightRAG,
Adapter execution semantics, scorer/metric behavior, Gold semantics, or the
Bundle 2.0 schema/writer.

The formal contract is intentionally above Bundle 2.0.  Existing Bundle checks
remain local file-integrity checks, while the new formal validator is the only
authority for deciding whether a Dataset Release may be created.

## Formal validator

`FormalDatasetValidator` always returns a versioned `ValidationReport` rather
than relying on an exception as the validation result.  The report is
content-addressed and immutable under the Platform release store:

```text
formal-validation-report/1.0
formal-dataset-validator/1.0
```

Every report contains the validator version, deterministic rule findings,
severity (`ERROR`, `WARN`, `INFO`), result, message, affected IDs/evidence,
input digests, selected document/Case/Gold revisions, and a deterministic
report digest.  Re-validating identical pinned inputs produces the same digest.

The fail-closed rule set covers:

- Canonical schema, object graph, and relation integrity.
- Canonical object source spans and provenance.
- Source/config/parser/canonicalizer/checksum and DocumentRevision consistency.
- Case/Gold ledger revision parsing and release lifecycle eligibility.
- MSES completeness, answer/evidence consistency, negative/unanswerable
  scope, and acyclic multi-hop dependencies.
- Case/Gold/Canonical cross-references and complete, reachable evidence.
- Duplicate and near-miss questions, answer leakage, and ambiguous Gold.
- Independent review/approval lineage.
- Bundle 2.0 projection lossiness.

Any failing `ERROR` causes `FormalDatasetReleaseService.freeze()` to refuse
creation of a formal Dataset Release.  The preflight report is still written
and its digest appears in the failure, preserving a complete audit trail.
`WARN` does not become an `ERROR`; for example, a rich MSES that Bundle 2.0
cannot represent remains valid Authoring Gold but is marked lossy/non-runnable.

## Immutable formal Dataset Release

`DatasetRelease` (`formal-dataset-release/1.0`) is stored in the global
Platform release store and is the only formal release source of truth.  A
release pins, as typed fields:

- Dataset ID and release version, with optional typed parent release ID.
- DocumentRevision, source digest, Canonical digest, parser/canonicalizer and
  configuration identity.
- Exact frozen Case and Gold revision IDs.
- Formal validation report digest and all schema/validator versions.
- A selected Authoring Ledger state digest and the corresponding ledger event
  IDs.
- Review and Approval identities/records.
- Authoring origin, generator identity/version/config digest, trust level and
  source-world/document lineage.
- Explicit Bundle 2.0 projection state.

Release pins are Pydantic-frozen, release files cannot be overwritten with
different content, and release versions cannot be reused for different pins.
The release digest deliberately excludes only audit creation time; its
identity is deterministic from the frozen lineage content.

At freeze, the Platform also stores immutable source-DOCX and Canonical
contract snapshots.  Rebuild verifies those snapshots and the exact pinned
revisions, allowing historical releases to remain reproducible after later
workspace edits or a Gold successor.  A tampered snapshot yields a new failing
audit report and `reproducible: false`; the old release record is never
modified.

## Typed lineage and historical runs

`ReleaseLineage` answers, through typed fields rather than free-form metadata:

- source, parser, canonicalizer and config that produced the release;
- exact Canonical, Case and Gold revisions;
- authorship origin, review and approval records;
- parent release and typed Case/Gold/document differences;
- deterministic rebuild verification.

`ExperimentSpec` and `RunManifest` now have an optional
`dataset_release_id`.  When supplied, `RunExecutor` verifies that it resolves
to a lossless, runnable formal release whose Bundle ID exactly matches the
experiment Bundle before execution.  `resolve_historical_run()` distinguishes
an exact pin, a legacy unpinned run, an unknown release, and a Bundle mismatch.
This is additive: existing runs and Bundle 2.0 inputs remain readable.

## Bundle 2.0 boundary

Bundle 2.0 files and IDs are unchanged.  A formal release is classified as:

- `lossless_runnable` only when all selected formal Gold revisions project
  losslessly and a matching Bundle ID is explicitly pinned;
- `lossy_non_runnable` when Bundle 2.0 would lose alternative MSES paths,
  within-clause OR alternatives, multi-hop dependencies, supporting/
  conflicting/near-miss roles, or multi-object negative scope;
- `no_bundle` when no Bundle projection is claimed.

A lossy/non-runnable release is not allowed to claim a Bundle 2.0 ID, so it
cannot masquerade as a complete executable Bundle.  No Bundle v3 migration is
introduced here.

## Frozen 20-case reference set

The frozen 20-case Bundle remains external immutable registry metadata only:

```text
d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e
lifecycle: frozen
usage: development/reference_diagnostic
held_out: false
generalization_claim_allowed: false
```

This phase neither writes a Bundle Store entry nor changes Gold, Bundle bytes,
Bundle ID, or historical run references for that set.  Its source bytes are
not mounted in this checkout; the regression test asserts the immutable
registry record and that no Platform Bundle mutation occurs.

## Tests

`test_formal_release_lineage.py` adds coverage for:

- deterministic audit reports and rule failures that block release;
- WARN versus ERROR behavior and lossy Bundle 2.0 refusal;
- immutable releases, parent/successor lineage, and release after Gold
  supersession;
- Case/Gold revision pinning and deterministic rebuild from frozen source and
  Canonical snapshots;
- tamper detection;
- Bundle 2.0 lossless compatibility and historical run/release resolution;
- unchanged frozen-20 registry classification.

Full Platform verification:

```text
PYTHONPATH=src .venv/bin/pytest -q
102 passed, 3 skipped, 1 warning
```

`git diff --check` passes.

## Readiness answers

1. **Does the Platform now have one formal validator?** Yes.
   `FormalDatasetValidator` is the single release-gating authority; older
   Pydantic/Bundle checks are subordinate local integrity checks.
2. **Are releases truly immutable and reproducible?** Yes.  Formal releases
   are immutable content-pinned records with frozen source and Canonical
   snapshots; rebuild verifies the exact selected revisions and report digest.
3. **Can source → canonical → Case/Gold → review → release be fully traced?**
   Yes, through typed `ReleaseLineage`, pinned revisions, approval/review pins,
   source/config/origin identities, parent diff, and optional run release ID.
4. **Is there a duplicate formal validation/release source of truth?** No.
   `DatasetRelease` and `ValidationReport` are formal authority.  The prior
   Authoring freeze marker is only an internal Bundle-compatibility pin used to
   create the formal release.
5. **Can Blueprint / Portfolio + Held-out Benchmark work begin?** Yes; the
   formal validation, immutable release, and lineage prerequisites are ready.
6. **Is P0 complete?** Yes for the requested Benchmark Data Layer P0 scope:
   Canonical Contract, registry classification, Authoring Ledger/Gold
   Lifecycle, formal validator, frozen release, and lineage are implemented.
7. **Are there blockers?** No implementation blocker.  The only external
   verification limitation is a direct byte-level re-hash of the frozen
   20-case payload, which requires mounting that pre-existing Bundle artifact.
