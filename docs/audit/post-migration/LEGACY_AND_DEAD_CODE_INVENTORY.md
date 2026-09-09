# Legacy and Dead Code Inventory

## Scope and decision rule

This inventory covers tracked production code, public exports, schemas, CLI/API routes, tests, fixtures and persisted-format readers at baseline `0fc494f975d9b3b2c026bba798cc13f764b93580`. Classification was not based on names or a zero-hit text search alone. For every candidate, the audit checked direct calls, dynamic/config-driven reachability, public exports, historical readers, tests, ADRs and stated retirement conditions (CMD-025).

The formal-route P1 findings are detailed in `ARCHITECTURE_AND_RUNTIME_AUDIT.md`. This report answers what may be retained, isolated or retired after those blockers are fixed.

## Inventory summary

| Asset | Current role | Formal production reachability | Disposition | Retirement condition |
| --- | --- | --- | --- | --- |
| `evaluation_corpus` selector | Wire/config compatibility for three historical corpus values | Rejected by public admission; direct executor/replay can still consume it | `KEEP_FOR_COMPAT` | Remove only after supported pre-segmented replay/write windows close and historical fixtures are migrated. |
| `source_document` | Native formal corpus identity plus Wire 1 compatibility value | Formal reachable | `KEEP` | None; eventually rename only through a versioned contract change. |
| `canonical_segments` dataset/execution support | Historical deterministic pre-segmented route | Historical/direct-internal only | `KEEP_FOR_COMPAT` | Prove no supported live replay/external caller; retain a read-only fixture converter if needed. |
| `benchmark_segments` / Bundle 2 execution support | Historical verified leaf-input route and authoring export | Historical/direct-internal; export/register API remains reachable | `KEEP_FOR_COMPAT` | Separate authoring interchange from executable corpus, then close new writes and observe zero consumers. |
| `SegmentTrace*` | Wire 1 provenance representation | Nested in legacy `RAGResult`; historical/pre-segment scoring | `KEEP_FOR_COMPAT` | Wire 1 worker protocol and Artifact 1.x replay fully retired. |
| `BenchmarkGold` | Legacy evidence contract | Legacy scorer/pre-segment compatibility and schemas | `KEEP_FOR_COMPAT` | All supported stored Bundles/Artifacts have versioned readers or migration projection. |
| `RAGResult` | Current Worker return envelope carrying answer plus v2 observation | Formal reachable | `KEEP_FOR_COMPAT` | Introduce and cut over a Wire 2 native response as execution authority; maintain an explicit Wire 1 reader. |
| `evaluate_case` and legacy failure engine | Old scorer; historical rescore | Incorrectly formal reachable, also compatibility consumers | `MERGE` | First remove from formal native control flow; retain in a clearly named legacy package until historical rescore support ends. |
| `segment_metrics` / `segment_answers` | Pre-segment retrieval and answer summaries | Imported by direct executor | `KEEP_FOR_COMPAT` | Same as pre-segment live execution retirement. |
| `evaluation/unified/shadow.py` | Compares legacy and v2 outputs in tests | Test-only | `KEEP_FOR_TEST` | Remove after the formal legacy scorer is disconnected and a release has passed equivalent v2 regression gates. |
| `contracts/observation_compat.py` | Wire 1 to Wire 2 compatibility normalizer | Public contract/test utility; no formal direct call found | `KEEP_FOR_COMPAT` | Wire 1 protocol support formally ends; preserve conversion fixtures until then. |
| Artifact 1.2 / historical provenance readers | Unique readers for immutable historical Runs | Historical only | `KEEP_FOR_COMPAT` | Never delete while supported historical artifacts exist without an equivalent immutable reader. |
| Historical rescore/replay | Explicit operator compatibility | Historical only | `KEEP_FOR_COMPAT` | Product support policy ends and immutable derived artifacts exist where required. |
| Native v2 behavior baseline fixture | Phase characterization/shadow oracle | Test-only | `KEEP_FOR_TEST` | Replace with v2-authority regression after `ARCH-001`; then remove corpus-mode snapshots no longer supported. |
| `datasets/benchmark_contract.py` | Formal release contract helpers mixed with live Bundle 2 execution utilities | Mixed | `MERGE` | Split formal immutable-contract ownership from legacy execution/materialization before retiring the latter. |
| Legacy RunHistory projections | Some current review/report endpoints plus historical consumers | Mixed | `REVIEW` | Migrate current native readers to Artifact 2.0, inventory external callers, then classify individual methods. |
| Legacy WebUI metric/evidence components and DTOs | Old presentation layer, not mounted by current pages | Unreachable from current app | `REMOVE` | Move the unique zero-vs-unavailable assertion to Artifact components, then delete as one batch. |
| Authoring compatibility export client/UI residue | Backend endpoints remain, frontend client/CSS/i18n are not mounted | Backend reachable; frontend residue unreachable | `REVIEW` | Decide whether Bundle 2 export remains a documented operator feature; remove only orphaned frontend assets or restore an explicit UI. |
| Wire 1 / Artifact 1.2 checked-in schemas | Historical interchange and read support | Compatibility | `KEEP_FOR_COMPAT` | Same as the corresponding protocol readers; never silently rewrite. |

## Findings

### LEG-001 — Legacy evaluation is not isolated from the formal native executor

- **Status:** CONFIRMED
- **Severity:** P1
- **Evidence:** `platform/src/rag_eval/execution.py:92-101` imports legacy segment and scoring functions; `execution.py:1023-1045` calls `evaluate_case` and `assess_failure` after successful Unified Evaluation; `execution.py:515-521` and `577-579` publish legacy summary/report files. The shadow characterization at `platform/tests/rag_eval_platform/test_run_artifact_v2.py:406-485` codifies this coupling.
- **Disposition:** MERGE
- **Reason:** Formal native execution must use Unified Evaluation as its sole scorer. Move legacy evaluation behind a separately named compatibility executor/rescore service instead of deleting its historical readers prematurely.
- **Affected Files:** `platform/src/rag_eval/execution.py`; `platform/src/rag_eval/evaluation/engine.py`; `platform/src/rag_eval/evaluation/failures.py`; `platform/src/rag_eval/evaluation/segment_metrics.py`; `platform/src/rag_eval/evaluation/segment_answers.py`.
- **Counter-evidence checked:** Public pre-segmented admission is closed and only one native query is issued; neither fact prevents legacy scoring from controlling native Run completion.
- **Recommended owner:** Run / Orchestration and Unified Evaluation.
- **Validation after cleanup:** A formal native execution imports/calls no legacy scorer, still publishes Artifact 2.0 when the compatibility scorer is forced to raise, and historical rescore tests continue to pass through the explicit compatibility path.

### LEG-002 — The pre-segmented modes are compatibility routes, not separate public benchmarks

- **Status:** INTENTIONAL_COMPAT
- **Severity:** INFO
- **Evidence:** `platform/src/rag_eval/runtime_admission.py:22-95` rejects `evaluation_corpus`, `canonical_segments` and `benchmark_segments` on new public evaluations. Direct executor resolution remains at `execution.py:149-181`, canonical materialization at `datasets/canonical_segments.py:361-382`, Bundle 2 materialization at `datasets/benchmark_contract.py:920`, and both Adapter config models still enumerate the old values. Negative admission and positive replay tests passed in CMD-006/CMD-013.
- **Disposition:** KEEP_FOR_COMPAT
- **Reason:** Historical reproducibility and supported replay are legitimate. The remaining risk is accidental internal reachability, so the code needs an explicit compatibility boundary and support policy rather than immediate deletion.
- **Affected Files:** `platform/src/rag_eval/runtime_admission.py`; `platform/src/rag_eval/execution.py`; `platform/src/rag_eval/datasets/canonical_segments.py`; `platform/src/rag_eval/datasets/benchmark_contract.py`; both Adapter `adapter.py` files; compatibility tests and schemas.
- **Counter-evidence checked:** WebUI has no corpus selector; formal release projection contains one original DOCX; normal API/CLI create and queue routes invoke admission.
- **Recommended owner:** Run / Compatibility.
- **Validation after cleanup:** Public negative tests remain; direct legacy execution requires an explicit compatibility entry/token; telemetry or repository-wide caller evidence supports the eventual retirement decision.

### LEG-003 — Wire 1 `RAGResult` is still the formal transport envelope

- **Status:** INTENTIONAL_COMPAT
- **Severity:** P2
- **Evidence:** `platform/src/rag_eval/contracts/adapter.py:181` defines `RAGResult`; current Adapter query methods return it and attach the Wire 2 observation; `execution.py` consumes it before passing the nested `AdapterRunResultV2` to the v2 orchestrator. Adapter baselines and common-chain tests passed (CMD-010 through CMD-013).
- **Disposition:** KEEP_FOR_COMPAT
- **Reason:** Removing the model now would break Worker protocol compatibility. It should be treated as a versioned transport bridge, not as the future domain result.
- **Affected Files:** `platform/src/rag_eval/contracts/adapter.py`; Adapter query implementations; Worker protocol/client; execution and contract tests.
- **Counter-evidence checked:** Wire 2 types are real and shared, but there is no independent formal Wire 2 response envelope used end to end.
- **Recommended owner:** Observation Contract / Worker Protocol.
- **Validation after cleanup:** Add a contract-version negotiation/cutover test; prove Wire 2-native execution no longer needs legacy segment fields while the Wire 1 compatibility reader remains deterministic.

### LEG-004 — SegmentTrace and BenchmarkGold remain necessary only for supported legacy formats

- **Status:** INTENTIONAL_COMPAT
- **Severity:** INFO
- **Evidence:** `SegmentTraceStatus`, `SegmentTraceItem`, `SegmentTraceStage` and `SegmentTraceSet` are defined at `contracts/adapter.py:86-169`; `BenchmarkGold` is defined at `contracts/benchmark.py:147`; legacy evidence/scoring and pre-segmented Adapter tests consume them. Checked-in schemas and historical Bundles encode these structures.
- **Disposition:** KEEP_FOR_COMPAT
- **Reason:** They are not authoritative v2 scoring concepts, but they are required to read or replay immutable historical data. Relocate/deprecate them visibly instead of deleting or silently converting stored artifacts.
- **Affected Files:** Legacy contract models and schemas; `evaluation/evidence.py`; pre-segment Adapter code; historical fixtures/tests.
- **Counter-evidence checked:** No v2 Unified Scorer dependency on `BenchmarkGold` or `SegmentTrace` was found; usage is confined to the legacy/transport boundary.
- **Recommended owner:** Contracts / Historical Compatibility.
- **Validation after cleanup:** Import-boundary test prevents Unified Evaluation from importing Wire 1 types; golden historical artifacts still validate and render as explicitly legacy.

### LEG-005 — `benchmark_contract.py` has mixed formal and legacy execution ownership

- **Status:** CONFIRMED
- **Severity:** P2
- **Evidence:** Formal release code imports contract publication/validation helpers from `datasets/benchmark_contract.py` (`platform/src/rag_eval/datasets/formal.py:42-47` and release methods later in that module), while the same file contains Bundle 2 leaf-document materialization and `primary_evaluation_corpus="benchmark_segments"` at `benchmark_contract.py:920`.
- **Disposition:** MERGE
- **Reason:** A broad deletion would remove active formal contract functionality; leaving the concepts co-located obscures ownership and raises the chance that legacy corpus semantics leak into Benchmark code.
- **Affected Files:** `platform/src/rag_eval/datasets/benchmark_contract.py`; `platform/src/rag_eval/datasets/formal.py`; authoring export/register paths; related tests.
- **Counter-evidence checked:** The formal path does not select `benchmark_segments`; the module's active imports prove it is not dead as a whole.
- **Recommended owner:** Canonical Benchmark / Dataset Contracts.
- **Validation after cleanup:** Formal release tests import only the immutable-contract package; pre-segment materialization lives in a compatibility package; schema export remains byte-identical unless deliberately versioned.

### LEG-006 — The legacy-v2 shadow comparator is migration-only test scaffolding

- **Status:** INTENTIONAL_COMPAT
- **Severity:** P3
- **Evidence:** `platform/src/rag_eval/evaluation/unified/shadow.py:15` defines `compare_legacy_shadow`; repository call-site analysis found exports and tests but no runtime invocation (CMD-025). The native behavior baseline fixture explicitly snapshots all three corpus modes.
- **Disposition:** KEEP_FOR_TEST
- **Reason:** It still protects the dangerous `ARCH-001` cutover. Once the formal executor no longer invokes the legacy scorer and equivalent v2 authority regressions have passed a release, the cross-scorer equality oracle becomes misleading and may be removed.
- **Affected Files:** `platform/src/rag_eval/evaluation/unified/shadow.py`; its export/tests; `tests/fixtures/native_evaluation_v2/behavior-baseline.json`; `tests/rag_eval_adapters/test_native_evaluation_v2_baseline.py`.
- **Counter-evidence checked:** No production/dynamic registry use was found; the baseline still has unique cutover value today.
- **Recommended owner:** Unified Evaluation / Test Infrastructure.
- **Validation after cleanup:** Preserve native query-count, v2 metric, availability and Artifact authority coverage before deleting legacy-equality assertions.

### LEG-007 — Unmounted legacy WebUI presentation types and components are dead application code

- **Status:** CONFIRMED
- **Severity:** P3
- **Evidence:** `webui/src/components.tsx:21-67` (`MetricCell`) and `138-164` (`EvidenceList`) are not imported by an application page; `webui/src/semantics.ts` is used only by those components and its own test; legacy `MetricResult`, `EvidenceItem`, `RAGResult` and `CaseResult` shapes in `webui/src/types.ts:3-58` have no live Artifact page consumer. The mounted Artifact component is `ArtifactMetricCell` at `components.tsx:79-94` (CMD-025).
- **Disposition:** REMOVE
- **Reason:** These definitions preserve an obsolete UI result model and make it easier to reintroduce zero/default semantics. Their one useful semantics regression should be moved to the Artifact presentation test before removal.
- **Affected Files:** `webui/src/components.tsx`; `webui/src/semantics.ts`; `webui/src/semantics.test.ts`; `webui/src/types.ts`; associated unused styles.
- **Counter-evidence checked:** TypeScript compilation, tests, page imports and string references were checked; backend legacy readers do not require these frontend types.
- **Recommended owner:** WebUI.
- **Validation after cleanup:** `npm test` and `npm run build` pass; an Artifact-specific test still distinguishes observed zero, unavailable and missing values.

### LEG-008 — Current and historical RunHistory projections are interleaved

- **Status:** REVIEW_REQUIRED
- **Severity:** P2
- **Evidence:** `run_history.case()` and `run_history.report()` are used by current review/report endpoints (`platform/src/rag_eval/api.py:1382-1490`, `1517-1522`), while the same service contains unique Artifact 1.2 and historical provenance projections. Several legacy projection helpers have no internal caller, but are public methods on a service that may have external Python consumers.
- **Disposition:** REVIEW
- **Reason:** Migrate formal native read surfaces first, then classify methods individually. Repository-local absence is insufficient proof that a public service method is safe to delete.
- **Affected Files:** `platform/src/rag_eval/run_history.py`; `platform/src/rag_eval/api.py`; CLI/report/review tests.
- **Counter-evidence checked:** Normal v2 summary/case/comparison endpoints already use `ArtifactPresentationReader`; historical views are tested and are the only fail-closed readers for old artifacts.
- **Recommended owner:** Platform API / Compatibility.
- **Validation after cleanup:** Capture public API usage/support policy; prove all current native views work with legacy files hidden; run golden Artifact 1.2 reader tests.

### LEG-009 — The Wire 1 observation normalizer is compatibility code with no current runtime caller

- **Status:** INTENTIONAL_COMPAT
- **Severity:** INFO
- **Evidence:** `platform/src/rag_eval/contracts/observation_compat.py` is exported/documented and covered by Wire 2 compatibility tests, but no direct formal runtime invocation was found in CMD-025.
- **Disposition:** KEEP_FOR_COMPAT
- **Reason:** The normalizer is the declared deterministic bridge for supported Wire 1 producers and provides valuable contract fixtures. Its lack of a current call does not invalidate the compatibility promise.
- **Affected Files:** `platform/src/rag_eval/contracts/observation_compat.py`; contracts exports; compatibility tests and protocol documentation.
- **Counter-evidence checked:** Dynamic entry points and imports were searched; existing Adapters already emit nested v2 data directly.
- **Recommended owner:** Observation Contract.
- **Validation after cleanup:** Retain golden normalization and fail-closed invalid-input tests; document the supported Wire 1 window and delete only when the protocol is retired.

### LEG-010 — Authoring compatibility UI residue has no established product owner

- **Status:** REVIEW_REQUIRED
- **Severity:** P3
- **Evidence:** Backend Bundle 2 export/register endpoints remain reachable at `platform/src/rag_eval/api.py:891-918`, but the WebUI client helpers `exportAuthoringDataset`/`registerAuthoringExport`, related compatibility-export CSS and translation strings have no mounted page caller (CMD-025).
- **Disposition:** REVIEW
- **Reason:** The backend may remain a legitimate operator compatibility feature. Decide that product contract before either deleting orphaned frontend assets or restoring an explicitly historical UI.
- **Affected Files:** `platform/src/rag_eval/api.py`; authoring workflow; WebUI API client, styles and i18n resources.
- **Counter-evidence checked:** Repository-local page imports and route registrations were reviewed; direct external API consumers cannot be disproved from this repository.
- **Recommended owner:** Product API + WebUI.
- **Validation after cleanup:** Contract/API consumer decision recorded; WebUI build and API integration tests pass; no public endpoint is removed without a versioned deprecation.

## Removal safety constraints

1. Do not delete a historical reader and its fixture in the same unverified change; first demonstrate an equivalent immutable read path.
2. Do not remove Wire 1 models from checked-in schemas until Worker protocol support is explicitly versioned and ended.
3. Do not remove pre-segmented negative-admission tests when removing the implementation; they become the guard against route reintroduction.
4. Do not treat `RAGResult`, `benchmark_contract.py` or `run_history.py` as whole-file dead code. Each contains active or compatibility-owned responsibilities.
5. No item marked `REVIEW` may move to `REMOVE` solely on another `rg` scan; it requires owner/support-policy evidence.
