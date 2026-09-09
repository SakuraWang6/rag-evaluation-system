# Post-Migration Audit

## Final status: BLOCKED

Baseline `0fc494f975d9b3b2c026bba798cc13f764b93580` does not yet satisfy the one-chain acceptance rule.

The Canonical Benchmark, Unified Trace, Unified Evaluation and Artifact 2.0 implementations are present, shared by LightRAG and RAG-Anything, and their core fail-closed semantics passed the available deterministic tests. However, three P1 architecture findings remain:

1. **`ARCH-001`:** a normal native case is evaluated by Unified Evaluation and then unconditionally by the legacy scorer; the legacy result still participates in Run completion and produces a second summary/report authority.
2. **`ARCH-002`:** public query overrides can make the v2 evaluation profile resolve to `None`, allowing an admitted native Run to execute without a required Artifact 2.0.
3. **`ARCH-003`:** current report, CLI comparison and review surfaces still consume legacy persisted `CaseResult`/`summary.json`/`report.md` rather than Artifact 2.0.

In addition, exact same-HEAD Python 3.13 and Node 22 required-gate evidence was unavailable under the approved offline boundary (`TEST-003`). Under the predeclared hard rules, any of these conditions prevents `READY` or `READY_WITH_CLEANUP`.

## Top three actions

1. Make v2 evaluation profile validation mandatory at admission, require Artifact 2.0 for native completion, and remove the legacy scorer from formal native control flow (`ARCH-001`, `ARCH-002`, `LEG-001`).
2. Move native report, comparison and review reads to immutable Artifact 2.0 views, retaining explicitly versioned historical fallback only (`ARCH-003`, `LEG-008`).
3. Run the unchanged remediation HEAD on the full required Python 3.11/3.12.12/3.13 and Node 22 matrices, then ratchet stale test/Ruff baselines (`TEST-001` through `TEST-003`).

## Audit identity

| Field | Value |
| --- | --- |
| Repository | `/Users/sakura/RAG/evaluation-system` |
| Baseline HEAD | `0fc494f975d9b3b2c026bba798cc13f764b93580` |
| Branch/divergence | `main`; 10 commits ahead of `origin/main`, 0 behind |
| Governing decision | `docs/decisions/0003-native-document-evaluation-v2.md` |
| Phase range observed | Phase 0 `3cfcb64` through Phase 9 `0fc494f` |
| Tracked baseline | 416 files |
| Git-visible baseline | 416 files |
| Filesystem baseline | 451 files; 35 ignored/generated-only entries |
| Markdown baseline | 74 tracked files, 10,727 lines, no exact duplicates |
| Initial worktree | Tracked/index clean; no unignored untracked files |
| Audit output | Exactly these six uncommitted reports; raw evidence remains under `/private/tmp` |

The repository HEAD and existing tracked files were rechecked before report creation (CMD-028). A final post-report scope check is recorded in this report set's handoff.

## What passed

- Public API, Product service and CLI admission reject new pre-segmented formal Runs; the WebUI contains no corpus-mode selector.
- Canonical Gold Eligibility is owned solely by Canonical Conformance and has no Adapter/RAG-name dependency.
- Observation status/completeness, native/crosswalk/exact-unique/missing precedence, duplicate fail-closed behavior, multi-chunk union and merged-table coverage passed.
- Top-K availability and explicit `ranked_complete_evidence_mrr@5` semantics passed, including truncated proven prefixes and unknown-earlier-rank behavior.
- Absence without index/provenance proof remains `UNOBSERVABLE`; it is not reported as `retrieval_missed`.
- `UNAVAILABLE` remains status plus null through aggregation, Artifact, API and current WebUI; observed numeric zero remains distinct.
- Existing Artifact 2.0 manifests, member digests and checksum graph detect tampering and can be read without the current scorer/runtime.
- LightRAG and RAG-Anything emit the same Wire 2 types and use the same TraceValidator, EvaluationEngine, Artifact models, API views and WebUI.
- Python 3.11 and exact 3.12.12 Platform suites, schema export, Adapter gates, CI tooling, WebUI tests/build on Node 24, all three package builds/clean installs and both model-free Worker lifecycles passed.
- Project Worker source revisions and image digests matched `ci/worker-runtime-lock.yaml`.

## What remains compatible by design

`evaluation_corpus`, `canonical_segments`, `benchmark_segments`, `SegmentTrace*`, `BenchmarkGold`, Wire 1 `RAGResult`, Artifact 1.2 readers and historical replay/rescore are not all dead code. New public pre-segmented Runs are closed, but direct compatibility execution and historical readers remain. They are classified individually in the legacy inventory; no wholesale deletion is justified.

## Evidence and validation summary

| Evidence range | Coverage | Result |
| --- | --- | --- |
| CMD-001–005 | Baseline, three scan modes, ignored/untracked separation | Complete |
| CMD-006–008 | Platform exact/compatibility Python matrix | 3.11 and 3.12 pass; 3.13 unable offline |
| CMD-009–015 | Schemas, Adapter gates, CI tooling, Ruff | All active commands pass; stale baselines found |
| CMD-016–019 | WebUI and three package artifacts | Pass on Node 24 / locked Python |
| CMD-020–022 | Worker locks and model-free lifecycle | Both Workers pass |
| CMD-023–025 | Markdown, links, legacy/call-site inventory | Complete; findings recorded |
| CMD-026–027 | V2-profile bypass probe and Phase 9 change-surface check | Bypass confirmed; Adapter-only semantic surface confirmed |
| CMD-028–032 | Baseline recheck, exact-runtime availability and final report integrity | Python 3.13/Node 22 unavailable; six-report scope, 36 finding records and 74/74 Markdown inventory verified |

Raw command logs, collector JSON and temporary build/test artifacts are under `/private/tmp/evaluation-system-post-migration-audit.wHG1Z2` and are intentionally not part of the repository.

## Repository hygiene findings

### HYG-001 — Workspace repository lock does not identify the audited project revision

- **Status:** CONFIRMED
- **Severity:** P2
- **Evidence:** `/Users/sakura/RAG/repos.lock.yaml:25-35` pins evaluation-system revision `db7af4ed3dc66b8ea281c0f2a123b0cb984079b9`, while the audited repository is at `0fc494f975d9b3b2c026bba798cc13f764b93580`; the branch is ten commits ahead of `origin/main` (CMD-001). External LightRAG and RAG-Anything revisions in the workspace lock match the project Worker lock.
- **Disposition:** REVIEW
- **Reason:** The workspace file is metadata outside this project's cleanup scope. Update it only after the audit/remediation commit is accepted and released; do not mutate it as part of these six reports.
- **Affected Files:** `/Users/sakura/RAG/repos.lock.yaml` (external workspace metadata); project release/CI evidence.
- **Counter-evidence checked:** `ci/worker-runtime-lock.yaml` correctly pins current external RAG source/image identities; the mismatch is only the evaluation-system workspace revision.
- **Recommended owner:** Workspace / Release Engineering.
- **Validation after cleanup:** Workspace lock equals the accepted project commit and each independent repository verifies cleanly at its pinned revision.

### HYG-002 — Generated and cache files are present locally but none is tracked

- **Status:** DISPROVED
- **Severity:** INFO
- **Evidence:** Filesystem scan found 451 files versus 416 tracked/Git-visible files; `git status --ignored` identifies `.DS_Store`, `.pytest_cache`, `.ruff_cache`, `.venv`, Python `__pycache__`, `webui/node_modules`, `webui/dist` and `webui/tsconfig.tsbuildinfo`. `git ls-files` found none of these generated paths (CMD-002–005).
- **Disposition:** KEEP
- **Reason:** Ignore policy is functioning. Local deletion is optional housekeeping and was neither necessary nor authorized.
- **Affected Files:** Ignore configuration and local ignored outputs only.
- **Counter-evidence checked:** Tracked-file and unignored-untracked scans were both empty for these patterns.
- **Recommended owner:** Repository maintainers.
- **Validation after cleanup:** `git ls-files` continues to contain no cache/build artifacts; package/WebUI builds remain reproducible in isolation.

### HYG-003 — No unused direct package dependency was proven

- **Status:** DISPROVED
- **Severity:** INFO
- **Evidence:** Direct dependency declarations were cross-checked against imports, packaging/entry-point use and tests; no dependency met the audit's removal proof standard. Three offline package builds and clean installs/import/CLI/resource smoke passed (CMD-018/019).
- **Disposition:** KEEP
- **Reason:** Version age alone is not evidence of redundancy or vulnerability. No network vulnerability scan was permitted, so this finding makes no security-freshness claim.
- **Affected Files:** Root/package `pyproject.toml` and lock files; `webui/package.json`/lock.
- **Counter-evidence checked:** Optional Worker/runtime and build-time consumers were included; absence of one source import alone was not treated as proof.
- **Recommended owner:** Package maintainers.
- **Validation after cleanup:** Re-run import/entry-point/build analysis after dead-code retirement; remove dependencies only with clean-install and full-suite proof.

### HYG-004 — Project Worker runtime lock matches local pinned integrations

- **Status:** DISPROVED
- **Severity:** INFO
- **Evidence:** `ci/worker-runtime-lock.yaml:4-57` pins LightRAG `6eff0064...` / image `sha256:c1b5...` and RAG-Anything `698e4f17...` / image `sha256:dae4...`; local source revisions and image digests matched (CMD-020), and both current-wheel model-free lifecycle smokes passed (CMD-021/022).
- **Disposition:** KEEP
- **Reason:** No stale Worker pin was found. The LightRAG `profile: legacy` setting names its runtime integration profile, not a selectable evaluation corpus route.
- **Affected Files:** `ci/worker-runtime-lock.yaml`; both Worker Dockerfiles/package locks.
- **Counter-evidence checked:** Source revision, package identity, image digest and runtime-reported system version were all checked; paid/native query quality was outside scope.
- **Recommended owner:** Worker Integration / Release Engineering.
- **Validation after cleanup:** Repeat digest/source verification and lifecycle smoke after any Adapter or dependency change.

## Limitations

- Python 3.13 and exact Node 22 could not be run without a prohibited download; there is no same-HEAD remote CI result in the frozen repository evidence.
- Worker checks were model-free lifecycle tests. Real native ingest/retrieval/generation against paid or production model endpoints was deliberately excluded.
- No network vulnerability scanner was used. Dependency findings concern ownership/use and reproducibility, not undisclosed CVEs.
- External LightRAG, RAG-Anything and workspace metadata were read-only integration evidence and are not cleanup targets.
- Static absence cannot disprove unknown external Python/API consumers; affected candidates remain `REVIEW`.

## Report index

- [Architecture and Runtime Audit](ARCHITECTURE_AND_RUNTIME_AUDIT.md)
- [Legacy and Dead Code Inventory](LEGACY_AND_DEAD_CODE_INVENTORY.md)
- [Documentation Inventory](DOCUMENTATION_INVENTORY.md)
- [Test and Fixture Inventory](TEST_AND_FIXTURE_INVENTORY.md)
- [Cleanup Plan](CLEANUP_PLAN.md)

## Decision

The project is **not ready for cleanup execution or release acceptance yet**. First approve and complete Batch 1 of the cleanup plan, then stop for review. Existing files, compatibility data and historical documents must remain untouched until their specific batch and retirement gates are approved.
