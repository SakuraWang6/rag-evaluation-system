# Architecture and Runtime Audit

## Audit identity

- Baseline: `0fc494f975d9b3b2c026bba798cc13f764b93580`
- Branch: `main` (`10` commits ahead of `origin/main`, `0` behind)
- Decision authority: `docs/decisions/0003-native-document-evaluation-v2.md`
- Scope: tracked repository, Git-visible repository, filesystem residue, local Worker integrations, Platform API, WebUI, and read-only workspace/runtime locks
- Method: static ownership and call-path review, route reachability analysis, contract/schema verification, invariant tests, isolated package builds, and model-free Worker lifecycle smoke

## Verdict

The intended layers exist and most v2 semantics are implemented correctly, but the formal runtime has not yet converged to one evaluation authority. The observed native path is:

```text
Original DOCX
  → public native admission
  → Adapter Worker / Native RAG
  → one RAGResult containing an AdapterRunResultV2
  → TraceValidator
  → Unified Evaluation
  → RunArtifactCaseV2 buffered in memory
  → legacy evaluate_case / legacy failure assessment       ← still control-critical
  → legacy case + summary.json + report.md                 ← second result surface
  → ArtifactWriter, conditionally                          ← not guaranteed
  → persisted Artifact API / descriptor-driven WebUI
```

Accordingly, architecture status is **BLOCKED**. `ARCH-001`, `ARCH-002`, and `ARCH-003` are P1 findings under the audit's hard rules.

## Authority matrix

| Boundary | Intended authority | Actual owner and entry points | Result |
| --- | --- | --- | --- |
| Canonical Benchmark | Platform-owned source identity, Canonical Catalog, Question, Gold Answer and Gold Evidence | `platform/src/rag_eval/authoring/canonical.py`, `canonical/conformance.py`, `datasets/formal.py`, `datasets/bundle_v3.py` | PASS |
| Gold eligibility | Canonical Conformance only | `CANONICAL_GOLD_ELIGIBILITY_MATRIX`; no Adapter/RAG imports or name checks in the canonical/unified/run cores | PASS |
| Observation | Adapter-specific capture behind one RAG-neutral contract | `contracts/observation.py`; LightRAG and RAG-Anything emit `AdapterRunResultV2` | PASS, with TCK extensibility gap `ARCH-004` |
| Evaluation | Gold + validated Unified Trace only | `evaluation/unified/*` is RAG-neutral | PASS in the v2 engine; FAIL at execution composition because legacy scoring also runs |
| Run/orchestration | `BenchmarkResolver → AdapterSession → TraceValidator → EvaluationEngine → ArtifactWriter` | `runs/orchestration.py` implements the boundary, but `execution.py` treats it as an additive branch | FAIL (`ARCH-001`, `ARCH-002`) |
| Artifact | Artifact 2.0 is the immutable display and comparison authority | `runs/artifacts.py`, `runs/eligibility.py`, `runs/views.py` | PASS when Artifact 2.0 exists; publication is optional in a completed native Run |
| Platform API | Persisted Artifact views, no live mapping/scoring | Normal result endpoints use `ArtifactPresentationReader`; report/review compatibility endpoints and CLI still consume legacy files | PARTIAL (`ARCH-003`) |
| WebUI | Descriptor/status rendering only | Artifact pages consume persisted v2 views; no corpus-mode or RAG-name scoring branch found | PASS |

## Runtime and route reachability

| Route or branch | Reachability | Evidence | Assessment |
| --- | --- | --- | --- |
| Product `NativeEvaluationDraftRequest → finalize/queue` | `FORMAL_REACHABLE` | `platform/src/rag_eval/api.py:123-149`, `1960-2019` | Intended formal entry; passes public admission. |
| Public Experiment create/queue | `FORMAL_REACHABLE` | `platform/src/rag_eval/api.py:1227-1251` | Both operations call `admit_new_public_experiment`. |
| CLI create/run | `FORMAL_REACHABLE` | `platform/src/rag_eval/cli.py:134-147` | Uses the same admission policy. |
| WebUI corpus selector | `UNREACHABLE` | no `evaluation_corpus`, `canonical_segments`, or `benchmark_segments` reference under `webui/src` | Correctly removed from normal UI. |
| Public pre-segmented Run creation | `UNREACHABLE` | `platform/src/rag_eval/runtime_admission.py:51-175`; passing cutover tests in CMD-006 | Correctly rejected. |
| Historical authoring Bundle 2.0 export/register | `INTERNAL_BUT_REACHABLE` | `platform/src/rag_eval/api.py:891-918`; `authoring/workflow.py:1405-1479` | Explicit compatibility asset; cannot pass formal native admission. |
| Direct `RunExecutor.execute` with old corpus metadata | `INTERNAL_BUT_REACHABLE` | `platform/src/rag_eval/execution.py:149-181` | Kept for compatibility, but lower-level callers can bypass public admission. |
| CLI replay of a stored old Experiment | `HISTORICAL_ONLY` | `platform/src/rag_eval/cli.py:175-204` | Intentional read/replay compatibility. |
| `benchmark_segments` execution | `HISTORICAL_ONLY` through supported public surfaces; `INTERNAL_BUT_REACHABLE` through direct executor | `platform/src/rag_eval/execution.py:164-181`, `458-486` | Not a second public benchmark, but live compatibility code remains. |
| `canonical_segments` execution | `HISTORICAL_ONLY` through supported public surfaces; `INTERNAL_BUT_REACHABLE` through direct executor | `platform/src/rag_eval/execution.py:170-181`, `280-311` | Same compatibility boundary. |
| Legacy scorer on a normal native case | `FORMAL_REACHABLE` | `platform/src/rag_eval/execution.py:993-1045` | Unconditionally runs after Unified Evaluation; architecture violation. |
| Legacy `summary.json` and `report.md` on a normal native Run | `FORMAL_REACHABLE` | `platform/src/rag_eval/execution.py:515-521`, `562-579` | Competing persisted interpretation. |
| Artifact 1.2/historical readers | `HISTORICAL_ONLY` | `platform/src/rag_eval/runs/views.py:264-355`; `run_history.py:686-842` | Correctly fail closed and retain unavailable status. |

## Core invariant results

| Invariant | Result | Evidence |
| --- | --- | --- |
| Canonical stability and immutable Snapshot identity | PASS | `canonical/conformance.py:185-288`; `test_canonical_conformance.py:120-186`; Platform 369/369 on Python 3.11 and 3.12 (CMD-006, CMD-007). |
| Gold eligibility is Platform-owned | PASS | `canonical/conformance.py:1`, `38-112`, `233-287`; no Adapter/RAG reference in canonical, unified evaluation, run, API or WebUI cores (CMD-025). |
| Orthogonal observation status/completeness | PASS | `contracts/observation.py:24-36`, `715-777`; Wire v2 contract suite in CMD-006. |
| Native lineage > verified crosswalk > exact unique text > missing | PASS | typed mapping tiers at `contracts/observation.py:51-55`; duplicate and receipt tests in both Adapter suites (CMD-011, CMD-012). No fuzzy/semantic mapping implementation found. |
| Multi-evidence and split evidence coverage | PASS | LightRAG split/merged-table test and RAG-Anything split union test; `evaluation/unified/proofs.py:130-198` (CMD-011, CMD-012). |
| Verified transformations rather than ID subset everywhere | PASS in contract/scorer | `contracts/observation.py:1223-1269`; derived-output coverage guard at `evaluation/unified/proofs.py:306-318`. Shared TCK is narrower; see `ARCH-004`. |
| Top-K metric availability and explicit MRR@5 | PASS | `evaluation/unified/scorer.py:40-148`, `223-260`; truncation and unknown-rank tests in CMD-006. |
| Descriptor identity gates comparison | PASS | `runs/eligibility.py:23-64`; `comparison.py:231-292`; Artifact tests in CMD-006. |
| Proof-gated failure attribution | PASS | `evaluation/unified/failures.py:28-120`; P0 regression `test_catalogued_unmapped_gold_is_not_scored_as_retrieval_missed` passed in CMD-006. |
| Artifact member/model/checksum immutability | PASS | `runs/models.py:481-566`; `runs/artifacts.py:269-357`; tamper tests in CMD-006. |
| `UNAVAILABLE` is not numeric zero | PASS | aggregate logic `runs/eligibility.py:88-129`, API views `runs/views.py:237-274`, WebUI `components.tsx:79-94`; Python and Vitest assertions passed (CMD-006, CMD-016). |
| Observation does not issue a second native query | PASS | LightRAG `test_run_result_v2_observes_same_native_stage_items_without_second_execution`; RAG-Anything single-call tests (CMD-011, CMD-012). |
| Completed native Run always has Artifact 2.0 | FAIL | Profile may resolve to `None`, and publication is conditional; see `ARCH-002`. |
| One formal evaluation authority | FAIL | Unified and legacy scorers both execute; see `ARCH-001`. |
| API/CLI formal interpretation is Artifact-only | FAIL | Legacy report/summary/case consumers remain; see `ARCH-003`. |

## Adapter common-chain assessment

LightRAG and RAG-Anything use the same `AdapterRunResultV2`, `TraceValidator`, `EvaluationEngine`, Artifact models, API views and WebUI components. Phase 9 changed Adapter code, the shared observation TCK, tests, CI and documentation; it did not introduce RAG-Anything branches in Dataset, Scorer, Artifact or UI code (CMD-027). A whole-core search found no RAG name in `canonical/`, `evaluation/unified/`, `runs/`, Dataset core, Platform API or WebUI.

The common-chain conclusion is therefore **substantively true for the two current Adapters**, but the current TCK would reject some contract-valid future RAGs that use derived context items. That does not create a second scorer today, but it weakens the claimed third-Adapter acceptance test.

## Findings

### ARCH-001 — Formal native execution is still control-coupled to the legacy scorer

- **Status:** CONFIRMED
- **Severity:** P1
- **Evidence:** `platform/src/rag_eval/execution.py:993-1016` executes the v2 orchestrator and buffers a `RunArtifactCaseV2`; `execution.py:1023-1045` then unconditionally calls legacy `evaluate_case` and `assess_failure`; `execution.py:515-521` and `577-579` aggregate and render the legacy result before Artifact 2.0 publication. `platform/tests/rag_eval_platform/test_run_artifact_v2.py:406-485` explicitly asserts that v2 remains shadow-additive to an unchanged legacy `CaseResult`.
- **Disposition:** REMOVE
- **Reason:** Remove the legacy scorer dependency from the formal native branch and its success/failure control flow. Preserve it only behind an explicit compatibility executor/reader. A valid Unified Evaluation can currently be lost if legacy evaluation raises afterward.
- **Affected Files:** `platform/src/rag_eval/execution.py`; `platform/src/rag_eval/evaluation/engine.py`; `platform/src/rag_eval/evaluation/failures.py`; `platform/tests/rag_eval_platform/test_run_artifact_v2.py`; legacy report/summary tests.
- **Counter-evidence checked:** The Adapter is queried only once; v2 results are persisted when all later legacy work succeeds; public pre-segmented creation is blocked. None removes the legacy scorer from formal success semantics.
- **Recommended owner:** Run / Orchestration.
- **Validation after cleanup:** Inject a legacy scorer exception and prove a formal native Run still publishes a verified Artifact 2.0; assert no legacy scorer function is called; run Platform, Adapter and WebUI gates.

### ARCH-002 — Public admission does not guarantee a scoreable v2 profile or Artifact 2.0

- **Status:** CONFIRMED
- **Severity:** P1
- **Evidence:** `NativeEvaluationDraftRequest` accepts arbitrary override dictionaries (`platform/src/rag_eval/api.py:123-149`); `canonical_experiment` deep-merges them without v2-profile validation (`products.py:271-301`); `evaluation_profile_from_configs` returns `None` for a missing candidate cutoff (`runs/orchestration.py:513-531`); the executor silently takes the non-v2 branch (`execution.py:331-340`, `993-1022`) and publishes Artifact 2.0 only when v2 cases exist (`execution.py:533-560`). CMD-026 proved that RAG-Anything 1.0.1 plus public `query_overrides={"retrieval_candidate_k": null}` yields `evaluation_profile=None`, while the Adapter retains `top_k=3` and can execute (`adapters/rag-anything/.../adapter.py:988-1002`).
- **Disposition:** MERGE
- **Reason:** V2 profile construction belongs in public admission/spec validation, and a completed `native-document/v2` Run must assert Artifact 2.0 publication rather than silently completing as legacy-only.
- **Affected Files:** `platform/src/rag_eval/api.py`; `platform/src/rag_eval/products.py`; `platform/src/rag_eval/runtime_admission.py`; `platform/src/rag_eval/execution.py`; `platform/src/rag_eval/runs/orchestration.py`.
- **Counter-evidence checked:** Built-in profile defaults are valid and ordinary UI submissions work. The override surface is public and accepts JSON null, so defaults do not close the route.
- **Recommended owner:** Platform API + Run / Orchestration.
- **Validation after cleanup:** API/CLI create and queue reject missing/invalid cutoff or context budget; every completed release-bound Run has a verified `artifact-v2/artifact.json`; no silent fallback test remains.

### ARCH-003 — Formal read/review surfaces are not uniformly Artifact-2-only

- **Status:** CONFIRMED
- **Severity:** P1
- **Evidence:** Normal summary/case/comparison API paths use persisted v2 views (`api.py:1337-1378`, `1524-1541`), but `/runs/{run_id}/report` returns the legacy `report.md` (`api.py:1517-1522`; `run_history.py:1022-1027`), CLI comparison reads root legacy `summary.json` (`cli.py:148-169`), and review/semantic-review endpoints resolve the legacy `CaseResult` (`api.py:1382-1490`; `run_history.py:201-208`). The WebUI does not call the legacy report endpoint.
- **Disposition:** MERGE
- **Reason:** Move current native report, comparison and review inputs to persisted Artifact 2.0 views. Retain explicitly versioned historical fallbacks only for Artifact 1.2 Runs. Otherwise users can receive two formal interpretations of the same native Run.
- **Affected Files:** `platform/src/rag_eval/api.py`; `platform/src/rag_eval/cli.py`; `platform/src/rag_eval/run_history.py`; semantic/human review services and their tests.
- **Counter-evidence checked:** None of these paths invokes a live Adapter; the normal WebUI metric views are clean. The problem is competing persisted authority, not read-time recomputation.
- **Recommended owner:** Platform API / Run History.
- **Validation after cleanup:** Monkeypatch legacy readers/scorers to fail and prove current native report, compare, case review and semantic review still work from Artifact 2.0; prove historical Artifact 1.2 still returns explicit legacy-unavailable/compatibility data.

### ARCH-004 — Shared Adapter TCK rejects contract-valid derived and partial stages

- **Status:** CONFIRMED
- **Severity:** P2
- **Evidence:** `platform/src/rag_eval/adapters/observation_tck.py:21-44` requires every observed stage item ID/content to exist unchanged in the ingestion catalog and every observed stage to have ranks `1..N`. Wire 2.0 explicitly permits `verified_derivation` with new output identities (`contracts/observation.py:45-48`, `1245-1269`) and permits observed `partial` data without claiming a contiguous prefix (`observation.py:738-766`).
- **Disposition:** MERGE
- **Reason:** The TCK should validate according to the declared transition and completeness profile: catalog identity for identity-subset stages, receipts/output proof for derived stages, and only prefix-contiguity for complete/truncated prefixes.
- **Affected Files:** `platform/src/rag_eval/adapters/observation_tck.py`; both Adapter TCK call sites; new derivation-focused TCK fixtures.
- **Counter-evidence checked:** Both current Adapters use identity-preserving observed stages and pass the TCK. Core contract/scorer derivation tests pass. The issue is the promised generic third-Adapter admission surface.
- **Recommended owner:** Observation Contract / Adapter TCK.
- **Validation after cleanup:** Add one conforming derived-context fixture and one observed-partial fixture; both pass the TCK, while missing receipt/output coverage and false prefix claims fail.

### ARCH-005 — Pre-segmented routes remain live compatibility code but are closed at public admission

- **Status:** INTENTIONAL_COMPAT
- **Severity:** INFO
- **Evidence:** Public admission rejects corpus selectors and pre-segmented Bundle/contract metadata (`runtime_admission.py:51-95`), and API/CLI call admission before create/queue. Direct execution, replay, Adapter config and historical Bundle export still recognize `canonical_segments` and `benchmark_segments` (`execution.py:149-181`; both Adapter config models).
- **Disposition:** KEEP_FOR_COMPAT
- **Reason:** This is not a second Benchmark authority on the supported public route. It is nevertheless executable compatibility code and must have a named support window, explicit entry boundary and retirement telemetry before deletion.
- **Affected Files:** `platform/src/rag_eval/execution.py`; `datasets/canonical_segments.py`; `datasets/benchmark_contract.py`; both Adapter implementations; legacy schemas/tests.
- **Counter-evidence checked:** Product UI has no selector; normal API and CLI reject the routes; formal release projection contains one DOCX. Direct executor and replay remain callable by design.
- **Recommended owner:** Run / Compatibility.
- **Validation after cleanup:** Maintain negative public-admission tests plus positive historical replay tests until retirement; then remove live execution atomically.

### SEM-001 — Concern that Adapter capability filters Benchmark Gold

- **Status:** DISPROVED
- **Severity:** INFO
- **Evidence:** `canonical/conformance.py` owns the matrix and conformance result; the canonical, formal dataset and unified scorer cores have no Adapter capability or RAG-name dependency. First-wave fail-closed tests passed in CMD-006.
- **Disposition:** KEEP
- **Reason:** Current ownership matches ADR 0003.
- **Affected Files:** `platform/src/rag_eval/canonical/conformance.py`; `authoring/canonical.py`; `datasets/formal.py`.
- **Counter-evidence checked:** Adapter representability diagnostics in `authoring/workflow.py` affect flags/run availability, not Gold eligibility.
- **Recommended owner:** Canonical Benchmark.
- **Validation after cleanup:** Keep import/name guard and conformance matrix tests.

### SEM-002 — Concern that `UNAVAILABLE` becomes zero

- **Status:** DISPROVED
- **Severity:** INFO
- **Evidence:** Unified metrics persist `value=None` when bounds are not exact; aggregation preserves `UNAVAILABLE`; API comparison checks `status`; Artifact WebUI displays literal `UNAVAILABLE`. CMD-006 and CMD-016 passed observed-zero versus unavailable regressions.
- **Disposition:** KEEP
- **Reason:** The end-to-end status/null semantics are correct on Artifact 2.0.
- **Affected Files:** `evaluation/unified/scorer.py`; `runs/eligibility.py`; `runs/views.py`; `webui/src/components.tsx`; `webui/src/artifactPresentation.ts`.
- **Counter-evidence checked:** `|| 0` occurrences in WebUI apply to execution-count display, not metric values. A dead legacy component is inventoried separately.
- **Recommended owner:** Unified Evaluation / WebUI.
- **Validation after cleanup:** Preserve Python serialization/API and Vitest zero/unavailable assertions.

### SEM-003 — Concern that absence without proof becomes retrieval failure

- **Status:** DISPROVED
- **Severity:** INFO
- **Evidence:** `evaluation/unified/failures.py:42-61` emits `UNOBSERVABLE` for unknown ingestion/candidate bounds; the legacy P0 fix states and tests the same absence rule at `evaluation/evidence.py:792`, `1187-1230` and `test_evidence_localization_contract.py:1203-1256`.
- **Disposition:** KEEP
- **Reason:** Proof-gated failure semantics are protected in both v2 and supported historical presentation.
- **Affected Files:** Unified failures, legacy evidence compatibility, regression tests.
- **Counter-evidence checked:** Legacy persisted files may contain stale labels, but current historical presentation removes them or requires an accepted derivative; immutable originals are not rewritten.
- **Recommended owner:** Unified Evaluation.
- **Validation after cleanup:** Retain the P0 regression and one v2 ingestion/candidate ambiguity regression.

### SEM-004 — Concern that Artifact display depends on current scorer/runtime

- **Status:** DISPROVED
- **Severity:** INFO
- **Evidence:** `ArtifactV2Reader` reads and verifies persisted models only (`runs/artifacts.py:228-357`); reader tests monkeypatch scoring to fail and still read metrics (`test_run_artifact_v2.py:183-245`); API presentation tamper tests passed.
- **Disposition:** KEEP
- **Reason:** Artifact 2.0 is self-contained when it is published.
- **Affected Files:** `platform/src/rag_eval/runs/artifacts.py`; `runs/views.py`; Artifact tests.
- **Counter-evidence checked:** `ARCH-002` concerns missing publication, not the integrity of an existing Artifact.
- **Recommended owner:** Run / Artifact.
- **Validation after cleanup:** Keep member, manifest-digest, checksum graph, summary/index recomputation and scorer-free-read tests.
