# Authoring Ledger & Gold Lifecycle — P0 Implementation Report

## Scope and outcome

This phase implements the formal, append-only Authoring domain for the
Platform.  It adds no LightRAG, Adapter execution, scorer, metric, production
default, held-out benchmark, legacy importer, or Bundle v3 workflow changes.

The new contract lives in `rag_eval.authoring.ledger` (`authoring-ledger/1.0`)
and is the formal source of truth for Case, Gold, review, adjudication,
approval, invalidation, supersession, and Authoring release lineage.  It
references Canonical Data Model object IDs and digest(s); it does not define or
maintain a second canonical document schema.  Canonical Data Model 1.0 remains
the only formal canonical document contract.

The pre-existing `QuestionCandidate`, review, approved-case, and Bundle 2.0
files remain compatibility projections for the current DOCX workflow.  They
are not the formal revision history going forward.

## Formal Authoring model

The ledger writes individual immutable JSON records under each private DOCX
workspace's `ledger/` directory:

| Domain entity | Formal record and retention rule |
| --- | --- |
| Dataset | `DatasetLedgerRecord`, created once for an Authoring dataset |
| DocumentRevision | source digest, Canonical Contract digest, parser/canonicalizer/config identities; appended after analysis changes the interpretation |
| CaseDraft / CaseRevision | stable Case ID plus sequential revisions with parent revision IDs |
| GoldRevision | stable Gold ID, revision chain, linked Case revision, independent payload and lifecycle |
| Review | reviewer identity/role, target revision, decision, checklist, comments, timestamp |
| Adjudication | independent adjudicator, disagreement review IDs, decision and rationale |
| Approval | reviewer/adjudicator identity, approved revision, rationale, timestamp |
| Invalidation / Supersession | immutable record of invalidated revision or successor revision |
| AuthoringRelease | historical pin of Case and Gold revision IDs for an exported Bundle 2.0 release |

Every Case and Gold state mutation appends a new revision file with actor,
timestamp, reason, and parent revision.  The store refuses an existing ledger
path, and ledger Pydantic contracts are frozen, so revision records are not
updated in place.

## State machines and separation of duties

The supported lifecycle is:

```text
draft -> proposed -> reviewed -> approved -> frozen
                    \-> rejected
approved/reviewed/frozen -> invalidated
approved/frozen/invalidated -> superseded (a new stable successor Gold)
```

All illegal transitions fail closed.  In particular, only a proposed revision
can become reviewed, only a reviewed revision can become approved, and an
author cannot review or approve their own revision.  Synthetic and
semi-synthetic origins are constrained to unverified/review-required trust and
cannot become approved without an independent reviewer or adjudicator.

Reviews use the `reviewer` role only; adjudication requires at least two
different review decisions and an adjudicator independent of both the author
and cited reviewers.  An adjudicator can then approve the resolved reviewed
revision through a formal Approval record.

## Independent Gold contract and MSES semantics

Gold is now an independent entity with a stable Gold ID and immutable
`GoldRevision` chain.  Its payload records answer form/value, accepted values,
locale/unit/tolerance, Authoring origin and trust level, Canonical object
evidence, negative scope, and multi-hop dependencies.

Evidence is typed as `required`, `supporting`, `conflicting`, `near_miss`, or
`negative_scope`.  Minimum Sufficient Evidence Set semantics are lossless on
the Authoring side:

- an MSES path is an AND across its clauses;
- a clause is an OR across required-evidence alternatives;
- multiple MSES paths are alternatives (OR);
- dependency nodes record multi-hop order;
- abstention/unanswerable Gold requires explicit scoped negative evidence.

The ledger rejects an answerable Gold without MSES, an unanswerable Gold
without a negative scope, MSES references to unknown/non-required evidence,
self/unknown dependency edges, and duplicate evidence or clause IDs.

## Existing DOCX Authoring migration and Bundle 2.0

`AuthoringService.analyze()` creates the Dataset and DocumentRevision ledger
records.  Existing workflow operations append formal records as follows:

- question creation creates a Case draft;
- answer/evidence resolution creates a separate Gold draft and proposes both
  Case and Gold only after gates pass;
- review creates Case/Gold Review records, review-state revisions, and
  independent Approval records;
- edits append Case and Gold revisions rather than rewriting formal history;
- export creates an AuthoringRelease snapshot and freezes its referenced Case
  and Gold revisions after the existing Bundle 2.0 files are written.

Pre-ledger `QuestionCandidate` files are lazily and non-destructively mapped
to imported ledger revisions on first use.  The old candidate/approved files
remain unchanged compatibility projections, so the established API and Bundle
2.0 exporter still operate as before.

`BundleV2Projection` is an explicit sidecar assessment, never a schema
extension.  A Bundle 2.0 projection is marked lossy/non-runnable when it would
lose alternative MSES paths, OR evidence alternatives, multi-hop dependencies,
supporting/conflicting/near-miss roles, or multi-object negative scope.  The
current exporter is intentionally not changed to force rich ledger semantics
into Bundle 2.0.

## Backward compatibility and frozen 20-case set

No Bundle schema, Bundle writer, Bundle ID calculation, or existing Bundle
content was changed.  The only export sidecar addition is the local
`ledger_release_id` in Authoring `export.json`; it is not emitted into Bundle
2.0 bytes.  The frozen 20-case reference remains externally registered as:

```text
d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e
lifecycle: frozen
usage: development/reference_diagnostic
held_out: false
generalization_claim_allowed: false
```

The registry metadata is immutable and explicitly records `bundle_mutated:
false`; no Bundle Store content is created or rewritten by this phase.  The
actual frozen Bundle bytes are not mounted in this repository, so an
independent re-hash of that external artifact remains an environment-level
verification step.  The Platform test verifies the external registry record
and that the Platform Bundle Store is not populated as a side effect.

## Verification

New `test_authoring_ledger.py` covers:

- append-only Case and Gold revision history and immutable records;
- approval, rejection, invalidation, and Gold supersession;
- author/reviewer separation, reviewer disagreement, and adjudication;
- synthetic proposal/self-approval fail-closed behavior;
- alternative MSES paths, OR alternatives, multi-hop dependencies, evidence
  roles, negative/unanswerable scope, and Bundle 2.0 lossy assessment;
- DOCX workflow migration, Bundle 2.0 export compatibility, frozen Authoring
  release revisions, and unchanged frozen-20 registry metadata.

Full Platform test run:

```text
PYTHONPATH=src .venv/bin/pytest -q
98 passed, 3 skipped, 1 warning
```

`git diff --check` also passes.

## P0 readiness answers

1. **Is Gold an independent formal lifecycle entity?** Yes.  Gold has stable
   IDs, immutable revisions, origin/trust/provenance, MSES/evidence semantics,
   review, approval, invalidation, supersession, and freeze state.
2. **Do Case and Gold have complete revision history?** Yes for all new ledger
   operations; historical candidate files are migrated as imported projections
   when first used.
3. **Are Review and Adjudication formalized?** Yes, as independent immutable
   records with identity, role, target revision, decisions and timestamps.
4. **Is there still a duplicate Gold/Authoring source of truth?** No formal
   duplicate.  Legacy candidate/approved JSON remains only a Bundle 2.0/API
   compatibility projection; the ledger is the formal Authoring truth.
5. **Does the frozen 20-case set remain unchanged?** Yes: this phase only
   reads/retains its external immutable registry classification and does not
   write Bundle content or Bundle IDs.  Byte re-hash requires mounting the
   external frozen artifact.
6. **Can the next Formal Validator + Frozen Release / Lineage phase begin?**
   Yes.  The required formal entities, lifecycle history, and release-pinning
   foundation are present.
7. **Are there blockers?** No implementation blocker.  The only verification
   limitation is that the referenced frozen 20-case Bundle payload is absent
   from this checkout, so a literal byte-level re-hash should be run when that
   artifact is available.
