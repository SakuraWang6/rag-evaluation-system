# Cleanup Plan

## Execution contract

This is a recommendation only. No cleanup was performed during the audit. Work must proceed in the six batches below, in order, after explicit approval. Every change must cite confirmed Finding IDs, preserve old-system operability until its stated retirement gate, use an independent commit, run targeted and full regression, document rollback, and stop for acceptance before the next batch.

No `REVIEW` item may be removed until the missing consumer/support-policy evidence is obtained. Historical artifacts, readers and fixtures remain immutable. Existing schemas are changed only through an explicit versioned contract.

## Dependency order

```text
Batch 1: formal result correctness
    ↓
Batch 2: one persisted read authority
    ↓
Batch 3: compatibility isolation/retirement decisions
    ↓
Batch 4: durable tests and CI gates
    ↓
Batch 5: documentation authority/consolidation
    ↓
Batch 6: locks, packaging and repository hygiene
```

## Batch 1 — Semantic and correctness blockers

**Findings:** `ARCH-001`, `ARCH-002`, `LEG-001`, `TEST-003`.

### Changes

1. Make `native-document/v2` profile derivation part of public Experiment admission. Validate candidate cutoff, ranked cutoff, context budget and scorer/descriptor version before create or queue; reject null/invalid override combinations.
2. Require every successfully completed release-bound native Run to contain a validated Artifact 2.0 manifest and cases. Treat missing v2 profile, missing trace or failed Artifact publication as an explicit Run failure, never a silent legacy fallback.
3. Make Unified Evaluation the sole formal native scoring/failure authority. Move `evaluate_case`, `assess_failure`, segment answer/metric production and legacy summary/report generation behind an explicit historical/compatibility service.
4. Ensure a legacy scorer exception cannot invalidate a completed, valid v2 Run and that formal success does not depend on generating legacy files.
5. Obtain exact same-HEAD Python 3.13 and Node 22 CI evidence. This may be done by CI rather than changing code; do not download tools during the cleanup without separate approval.

### Targeted validation

- API and CLI reject `retrieval_candidate_k=null`, missing context budgets, invalid cutoff ordering and unknown scorer descriptors.
- Built-in LightRAG and RAG-Anything profiles still admit.
- Forced legacy scorer/report exceptions do not run on the formal native path.
- Formal completion implies verified `artifact-v2/artifact.json` exists and verifies.
- One native query per case remains true.
- P0 absence-without-proof regression and all v2 availability/failure tests pass.

### Full gate

Exact Platform baseline, Python 3.11/3.13 compatibility, schema diff, all Adapter gates, WebUI Node 22 test/build, three package build/install smokes and both model-free Worker lifecycles.

### Commit and rollback

- Suggested commit: `refactor(runtime): make unified evaluation the sole native authority`
- Rollback: revert only this commit; no data migration or historical artifact rewrite is permitted.
- **Stop after commit and wait for acceptance.**

### Exit gate

- No normal native call path reaches the legacy scorer.
- No admitted native Run can complete without a valid Artifact 2.0.
- Exact required runtime evidence is attached.

## Batch 2 — Formal route and persisted-authority convergence

**Findings:** `ARCH-003`, `LEG-008`, `LEG-010`.

### Changes

1. Route current native report generation, CLI comparison, case review and semantic review through persisted Artifact 2.0 views.
2. Define an explicit versioned fallback for Artifact 1.2/historical Runs. Its responses must state legacy/unavailable status and must never be selected for a v2 Run.
3. Remove creation of root legacy `summary.json`/`report.md` from formal native Runs after all consumers move. Do not delete such files from historical Runs.
4. Decide whether authoring Bundle 2 export/register remains a supported operator API. Deprecate/version it if needed; do not infer external-client absence from frontend usage.

### Targeted validation

- Hide or monkeypatch every legacy reader/scorer and prove current native summary, cases, report, compare and review endpoints still work.
- Verify API reads do not import/call Adapter, localizer or scorer.
- Verify historical Artifact 1.2 golden fixtures still render deterministically and fail closed.
- Verify WebUI uses only persisted descriptors/statuses and contains no RAG/corpus branch.

### Full gate

Platform, API contract, review, comparison, RunHistory, Artifact presentation, WebUI tests/build and package smoke.

### Commit and rollback

- Suggested commit: `refactor(api): make artifact v2 the native read authority`
- Rollback: revert only this commit; historical files remain untouched.
- **Stop after commit and wait for acceptance.**

### Exit gate

- A current v2 Run has one persisted interpretation across API, CLI and UI.
- Artifact 1.2 access is visibly compatibility-only.

## Batch 3 — Compatibility isolation and conditional retirement

**Findings:** `ARCH-005`, `LEG-002`, `LEG-003`, `LEG-004`, `LEG-005`, `LEG-008`, `LEG-009`, `LEG-010`.

### Changes

1. Publish a support matrix for Wire 1, Artifact 1.2, Bundle 2, `canonical_segments`, `benchmark_segments`, historical replay/rescore and authoring export.
2. Split formal immutable Benchmark contract/release ownership out of `datasets/benchmark_contract.py`; move executable pre-segment materialization under a visibly legacy/compatibility namespace.
3. Require explicit compatibility invocation for lower-level pre-segmented execution; preserve permanent public negative-admission tests.
4. Treat `RAGResult`, `SegmentTrace*`, `BenchmarkGold` and `observation_compat` as versioned legacy contracts. Do not remove them until Worker/Artifact consumers and retirement dates are proven.
5. Inventory external Python/API callers of RunHistory and authoring compatibility endpoints. Convert `REVIEW` items only after evidence.
6. If retirement conditions are met, disable new compatibility writes first, observe the support window, then remove live execution in a later sub-batch. Keep read-only readers and golden fixtures as long as historical data is supported.

### Targeted validation

- Formal core import guard prevents Canonical/Unified Evaluation/Artifact/WebUI from importing legacy corpus contracts.
- Explicit historical replay for each supported format passes.
- Public API/CLI/UI cannot create a pre-segmented formal Run.
- Schema export remains unchanged unless a separately approved new schema version is introduced.

### Full gate

All Platform and Adapter suites, schema export, historical recovery/replay, package install and Worker smokes.

### Commit and rollback

- Suggested first commit: `refactor(compat): isolate presegmented execution contracts`
- Any actual retirement must be a separate commit, e.g. `refactor(compat): retire legacy corpus writes`.
- Rollback: revert the current sub-batch only; never restore by rewriting artifacts.
- **Stop after each sub-batch and wait for acceptance.**

### Exit gate

- Every retained legacy asset has an owner, supported versions, read/write policy and retirement condition.
- No compatibility concept leaks into formal Benchmark Gold or Unified Evaluation.

## Batch 4 — Test, Fixture and CI convergence

**Findings:** `ARCH-004`, `LEG-006`, `LEG-007`, `TEST-001`, `TEST-002`, `TEST-003`, `TEST-004`, `TEST-005`.

### Changes

1. Generalize the shared Adapter TCK by declared transformation mode and completeness: identity-subset, verified derivation, complete/truncated prefix and observed partial.
2. Add conforming derived-context and partial-stage fixtures plus fail-closed receipt/output-proof cases.
3. Ratchet the Platform pass-count floor or adopt a reviewed collection manifest so unlisted test removal fails CI.
4. Remove the three fixed Ruff identities from its debt baseline and add regression fixtures for exact-identity reintroduction.
5. Remove the unreferenced `lightrag_collection` configuration and XML only if no owner elects to add a real pinned job.
6. After Batches 1–3, replace legacy/v2 equality assertions with v2-authority, one-query, immutable-read and permanent negative-admission tests. Retain historical golden-reader fixtures.
7. Move the unique observed-zero-versus-unavailable WebUI assertion to Artifact components, then remove unmounted legacy presentation code/test scaffolding.

### Targeted validation

- TCK accepts valid derived and partial traces, rejects missing receipts and false prefixes.
- CI tooling fails when one unlisted test disappears and when any removed Ruff diagnostic returns.
- `rg`/policy-tool tests show no active reference to removed XML/key.
- Historical provenance golden fixture, P0 failure semantics and Artifact immutability remain protected.

### Full gate

The exact required workflow matrix, including Python 3.13 and Node 22, plus package/Worker smokes.

### Commit and rollback

- Suggested commit: `test(ci): ratchet native v2 regression gates`
- Keep WebUI dead-code removal as a separate commit if it materially changes production files.
- Rollback: restore each baseline/test change with its single commit; never weaken thresholds to make a failure green.
- **Stop after each commit and wait for acceptance.**

### Exit gate

- Every core invariant maps to a stable test and required gate.
- Remaining compatibility fixtures protect a declared consumer; migration-only equality scaffolding is gone or has a dated retirement condition.

## Batch 5 — Documentation merge, archive and link repair

**Findings:** `DOC-001`, `DOC-002`, `DOC-003`, `DOC-004`, `DOC-005`.

### Changes

1. Rebuild `docs/architecture/README.md` into `Current / Compatibility / Historical` sections and make ADR 0003 the explicit authority.
2. Merge current Canonical, Observation, Evaluation, Artifact, admission and Adapter protocol statements; remove phase-era “shadow/legacy authority” wording from active pages.
3. Archive completed migration plans, gap analyses, implementation reports, experiments and rehearsals using the existing archive directories and index. Preserve their Git history and unique evidence.
4. Replace `platform/CURRENT_STATUS.md` as active navigation, then archive it.
5. Make packaged benchmark-v0 resources self-contained: relative links, present companions, explicit non-normative labels where a companion is intentionally absent.
6. Repair all incoming links and nonportable absolute Markdown links. Do not keep an additional Codex phase-summary collection.
7. Only propose deletion after merge/archive proves a file has no unique remaining content; the current audit recommends no immediate Markdown deletion.

### Targeted validation

- Offline link checker reports zero broken repository/package links.
- Clean-installed wheel contains every referenced normative resource.
- Active-doc search finds no contradictory corpus hierarchy or phase authority.
- Archive index records successor and baseline commit for each moved file.

### Full gate

Schema/package build-install smoke, documentation link/resource check, and normal code CI (moves must not affect packaging/imports).

### Commit and rollback

- Suggested commit: `docs(architecture): consolidate post-migration authority`
- Suggested archive-only follow-up: `docs(history): archive completed migration reports`
- Rollback: revert the current docs commit; use Git moves, never destructive deletion untracked copies.
- **Stop after each commit and wait for acceptance.**

### Exit gate

- A new maintainer can identify current authority from one index.
- Historical evidence is retained but cannot be mistaken for current behavior.
- Package documentation has no machine-specific dependency.

## Batch 6 — Configuration, dependency, generated-output and workspace hygiene

**Findings:** `HYG-001`, `HYG-002`, `HYG-003`, `HYG-004`.

### Changes

1. In a separately authorized workspace-metadata change, update `/Users/sakura/RAG/repos.lock.yaml` to the accepted evaluation-system commit. This file is outside the project cleanup scope and must not be bundled into a project commit.
2. Confirm the project Worker runtime lock remains aligned with pinned external source revisions, image digests and Adapter package requirements after earlier batches.
3. Keep caches, virtual environments, `node_modules`, `dist`, `.DS_Store` and `tsbuildinfo` ignored; optionally clean them locally only with explicit approval. Do not track them.
4. Re-run dependency import/packaging analysis after code retirement; remove a dependency only when source, plugin/entry-point and build/test consumers are all disproved.
5. Push/merge the accepted Phase and cleanup commits before declaring release readiness, then record same-HEAD CI evidence.

### Targeted validation

- Workspace lock revision equals accepted project HEAD; external RAG revisions equal Worker lock.
- `git ls-files` contains no cache/build/generated junk.
- Three clean package builds/installs pass and packaged file inventories are reviewed.
- Dependency lock is reproducible offline with the approved cache or in CI.

### Full gate

Repeat the complete audit gate matrix and model-free Worker lifecycle. Real-model validation remains a separately approved extension.

### Commit and rollback

- Suggested project commit, only if needed: `chore(repo): remove verified migration residue`
- Workspace-lock update is an independent workspace-metadata commit.
- Rollback: revert only the relevant repository's commit.
- **Stop after each commit and wait for acceptance.**

### Exit gate

- Locks identify the released commits; no generated residue is tracked; all remaining dependencies/configuration have an evidenced consumer.

## Final verification after all approved cleanup

Run the audit again at one frozen HEAD with the same tracked/Git-visible/filesystem scans, route reachability, semantic invariants, exact CI runtimes, package installs and Worker lifecycle checks. The final status may become `READY` only when:

- no P0/P1 finding remains;
- all formal Runs have one native-v2 scoring and persisted display authority;
- every required gate has same-HEAD evidence;
- all retained legacy/test assets have an explicit supported purpose;
- no `REMOVE`, `MERGE`, `ARCHIVE` action or core `REVIEW` remains unresolved.
