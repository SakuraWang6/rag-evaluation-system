# Test and Fixture Inventory

## Baseline and executed gate matrix

The repository scan reported 103 test-file signals across Python, TypeScript and fixtures (CMD-002). The principal executable suites are 49 Platform Python modules, 8 cross-Adapter modules, 4 LightRAG-local modules, 3 CI-tool modules and 6 WebUI test files. Tests were run from the isolated checkout or with outputs directed to `/private/tmp`; no paid model or production service was invoked.

| Gate | Runtime | Result | Audit status |
| --- | --- | --- | --- |
| Exact Platform CI profile | Python 3.12.12, pytest 9.1.1 | 369 passed, 0 failed, 0 skipped (CMD-006) | PASS |
| Platform compatibility | Python 3.11.14 | 369 passed (CMD-007) | PASS |
| Platform compatibility | Python 3.13 | Could not provision offline; `lxml==6.0.2` not cached (CMD-008/029) | `UNABLE_TO_RUN` |
| Checked-in schema export | Python 3.12.12 | 35 schemas, clean byte/diff (CMD-009) | PASS |
| Adapter exact baseline | Python 3.12.12 | 24 passed (CMD-010) | PASS |
| LightRAG retained regression | Python 3.12.12 | 22 passed (CMD-011) | PASS |
| RAG-Anything observation gate | Python 3.12.12 | 7 passed (CMD-012) | PASS |
| Cross-Adapter suite | Python 3.12.12 | 42 passed, 4 environment-gated Worker-venv skips (CMD-013) | PASS with declared skips |
| CI policy tools | Python 3.12.12 | 20 passed (CMD-014) | PASS |
| Ruff differential | Ruff 0.16.1 | baseline 291, current 288, additions 0, removals 3 (CMD-015) | PASS, stale-baseline finding |
| WebUI Vitest | Node 24.12.0/npm 11.6.2 | 6 files, 37 tests passed (CMD-016) | PASS on non-CI Node |
| WebUI production build | Node 24.12.0/npm 11.6.2 | 1579 modules, success (CMD-017) | PASS on non-CI Node |
| Three Python packages | locked Python environment | Three wheels + sdists; clean install/import/resource/CLI smoke passed (CMD-018/019) | PASS |
| LightRAG Worker lifecycle | locally pinned source/image, current wheel | handshake/prepare/health/close passed; healthy, 1.5.7 (CMD-020/021) | PASS, model-free |
| RAG-Anything Worker lifecycle | locally pinned source/image, current wheel | handshake/prepare/health/close passed; ready, 1.3.1 (CMD-020/022) | PASS, model-free |
| Exact WebUI CI runtime | Node 22 | Local image/runtime absent; downloads prohibited (CMD-030) | `UNABLE_TO_RUN` |

The exploratory attempt against a nonexistent `adapters/rag-anything/tests` path was a command-selection error and is not a project failure. CMD-012 and CMD-013 are the authoritative RAG-Anything results. A first sandboxed Platform run with three loopback/process skips was superseded by CMD-006, which ran the exact profile and passed all 369 tests.

## Core invariant traceability

| Invariant | Principal test nodes / fixtures | CI gate | Retain? |
| --- | --- | --- | --- |
| Canonical stability and Gold eligibility | `test_canonical_conformance.py`, `test_canonical_contract.py`, rich/complex table suites | Platform | `KEEP` |
| Public native-only admission | `test_native_formal_cutover.py`, `test_product_layer.py`, `test_jobs_and_api.py` | Platform required node IDs | `KEEP` |
| Observation status/completeness and transformation lineage | `test_wire_v2_contract.py`, both native-observation suites | Platform + Adapter gates | `KEEP` |
| Native mapping, duplicate fail-closed, multi-chunk union, merged table | `test_canonical_provenance.py`, LightRAG `test_native_unified_trace.py`, RAG-Anything native observation | Adapter gates | `KEEP` |
| Adapter neutrality / one native query | both Adapter native suites | Adapter gates | `KEEP` |
| Metric availability, MRR@5, descriptors and proof-gated failure | `test_unified_evaluation_v2.py`, `test_evaluation_contract_regressions.py` | Platform | `KEEP` |
| `retrieval_missed` P0 absence semantics | `test_evidence_localization_contract.py::test_catalogued_unmapped_gold_is_not_scored_as_retrieval_missed` | Platform | `KEEP` |
| Artifact 2.0 immutability and scorer-free read | `test_run_artifact_v2.py`, `test_artifact_presentation_v2.py` | Platform | `KEEP` |
| `UNAVAILABLE` versus observed zero through UI | Artifact presentation Python tests, `artifactPresentation.test.ts`, `components.test.ts` | Platform + WebUI | `KEEP` |
| Worker process/lifecycle | `test_worker_process.py`, `test_worker_container_bind.py`, worker smoke harness | Platform exact + Worker job | `KEEP` |
| Historical immutable recovery | `test_history_provenance.py` + `history_provenance/v1` fixture | Platform required nodes | `KEEP_FOR_COMPAT` |
| Pre-segmented route compatibility | canonical/benchmark segment tests and Adapter dirty tests | Platform + Adapter retained gate | `KEEP_FOR_COMPAT` until retirement |
| Legacy/v2 shadow equality | native-v2 behavior baseline, shadow comparator tests | Adapter/Platform | `KEEP_FOR_TEST` through `ARCH-001` cutover |

## Test suite inventory

| Suite/family | Modules | Current value | Disposition |
| --- | --- | --- | --- |
| Canonical and data contracts | `test_canonical_conformance.py`, `test_canonical_contract.py`, `test_complex_table_canonicalization.py`, `test_rich_content_canonicalization.py`, `test_bundle_v3.py`, `test_bundle_store.py` | Core Benchmark stability, subtype admission and immutable bundle behavior | `KEEP` |
| Authoring and release | `test_authoring.py`, `test_authoring_ledger.py`, `test_benchmark_admission_policy.py`, `test_benchmark_portfolio.py`, `test_blind_protocol.py`, `test_formal_release_lineage.py`, `test_product_layer.py` | Core authoring/release ownership and Gold lifecycle | `KEEP` |
| Native cutover/public admission | `test_native_formal_cutover.py`, `test_jobs_and_api.py`, `test_cli_system_registration.py`, `test_execution_sources.py` | Prevents old corpus modes and untrusted source mutation in new formal Runs | `KEEP` |
| Wire 2 / Unified Evaluation | `test_wire_v2_contract.py`, `test_unified_evaluation_v2.py`, `test_evaluation_contract_regressions.py`, `test_comparison.py`, `test_statistics.py` | Core v2 contract, availability, comparison and aggregate semantics | `KEEP`; extend for `ARCH-002/004` |
| Artifact/API presentation | `test_run_artifact_v2.py`, `test_artifact_presentation_v2.py`, `test_webui_api_contract.py`, `test_endpoint_redaction.py` | Immutability, persisted views, API/schema and redaction | `KEEP`; rewrite shadow-authority assertion |
| Run/Worker reliability | `test_execution_provider.py`, `test_executor_integration.py`, `test_reproducibility.py`, `test_supervisor.py`, `test_worker_container_bind.py`, `test_worker_process.py`, `test_worker_tck.py`, `test_llm_configuration.py` | Lifecycle, isolation, reproducibility and config safety | `KEEP` |
| Review features | `test_answer_support_reviews.py`, `test_case_reviews.py` | Current review workflows but currently coupled to legacy case projection | `REVIEW`; migrate inputs to Artifact 2.0 |
| Historical/replay | `test_history_provenance.py`, `test_run_history.py`, `test_replay.py`, `test_e2e_rehearsal.py`, `test_golden_smoke_v1.py` | Unique historical reader and reproducibility coverage | `KEEP_FOR_COMPAT` |
| Legacy evaluation | `test_evaluation.py`, `test_evidence_localization_contract.py`, `test_segment_answers.py`, `test_segment_metrics.py` | Contains P0 semantic protection plus old scorer behavior | `KEEP_FOR_COMPAT`; split enduring fail-closed tests before retirement |
| Pre-segmented Benchmark | `test_benchmark_contract_v1.py`, `test_benchmark_execution_v1.py`, `test_canonical_segment_corpus.py` | Historical Bundle/corpus reader/executor | `KEEP_FOR_COMPAT`; keep negative admission elsewhere permanently |
| Cross-Adapter base | `test_canonical_provenance.py`, `test_lightrag_adapter.py`, `test_rag_anything_adapter.py` | Shared config/provenance contract | `KEEP` |
| Cross-Adapter integration/Worker | `test_lightrag_platform_integration.py`, `test_lightrag_worker_process.py`, `test_rag_anything_platform_integration.py` | Package/process integration; four skips require dedicated env variables | `KEEP`; CI Worker smoke supplies lifecycle evidence |
| Native observation | `test_rag_anything_native_observation.py`, LightRAG `test_native_unified_trace.py`, `test_runtime_docx_and_trace.py` | One query, trace capture, split evidence, ambiguity fail-closed | `KEEP` |
| Migration characterization | `test_native_evaluation_v2_baseline.py`, LightRAG `test_benchmark_segment_trace.py`, `test_canonical_segment_provenance.py` | Cutover/legacy corpus oracle | `KEEP_FOR_TEST` or `KEEP_FOR_COMPAT` until formal decoupling and route retirement |
| CI policy tooling | `ci/tests/test_pytest_signal_gate.py`, `test_ruff_differential.py`, `test_worker_smoke_harness.py` | Ensures gate definitions themselves fail closed | `KEEP` |
| WebUI current | `apiContract.test.ts`, `artifactPresentation.test.ts`, `authoringGeneration.test.ts`, `components.test.ts`, `i18n/i18n.test.ts` | API schema, Artifact status rendering, authoring and localization | `KEEP`; adjust components test after dead UI removal |
| WebUI legacy semantics | `semantics.test.ts` | Tests helper used only by unmounted legacy components | `MERGE`, then remove obsolete helper/test |

## Fixture and oracle inventory

| Asset | Purpose | Disposition | Reason / condition |
| --- | --- | --- | --- |
| `platform/tests/fixtures/history_provenance/v1/**` | Immutable Artifact 1.x reconstruction, accepted derivative map and split-table evidence | `KEEP_FOR_COMPAT` | Unique historical-reader proof; deleting it would make compatibility claims untestable. |
| `tests/fixtures/native_evaluation_v2/behavior-baseline.json` | Frozen Phase 1 behavior and three-mode characterization | `KEEP_FOR_TEST` | Needed for formal legacy decoupling; later shrink/remove retired corpus assertions after equivalent v2 gates exist. |
| `platform/examples/golden-smoke-v1/**` | End-to-end authoring/validation smoke data including abstain, multi-evidence, units and table cells | `KEEP_FOR_TEST` | Long-term semantic coverage, not mere migration debris. |
| `tests/fixtures/canonical_naive_minimal.md` | Minimal canonical parser fixture | `KEEP_FOR_TEST` | Small deterministic canonical baseline. |
| `platform/examples/*.json` outside golden smoke | Public example requests/locks/protocols | `KEEP` | Packaging/user examples; validate with current schemas during cleanup. |
| `ci/baselines/platform-ruff-before.json` | Differential lint debt baseline | `MERGE` | Active, but refresh/ratchet after fixing the three removed diagnostics. |
| `ci/baselines/lightrag-collection-before.xml` | Imported external LightRAG collection snapshot | `REMOVE` | No workflow or CI-tool consumer found; see `TEST-004`. |

## Findings

### TEST-001 — Platform pass-count floors no longer protect the collected suite

- **Status:** CONFIRMED
- **Severity:** P2
- **Evidence:** `ci/known-baseline.yaml:91-92` permits 264 local or 267 CI passes, while the exact profile collected and passed 369 tests in CMD-006. Required node IDs protect selected semantics but permit roughly one hundred unlisted tests to disappear without failing the count gate.
- **Disposition:** MERGE
- **Reason:** Ratchet the exact-profile floor to the current deterministic collection or generate a reviewed manifest. Keep allowance only for explicitly named environment differences.
- **Affected Files:** `ci/known-baseline.yaml`; `ci/pytest_signal_gate.py`; policy-tool tests.
- **Counter-evidence checked:** The gate also checks required node IDs and disallows unexpected failures/skips; that does not protect unlisted test loss.
- **Recommended owner:** CI / Test Infrastructure.
- **Validation after cleanup:** Deleting one unlisted collected test must fail a policy-tool fixture; exact 3.12.12 run passes at the new floor; 3.11/3.13 remain compatibility suites.

### TEST-002 — The Ruff differential baseline contains stale exceptions

- **Status:** CONFIRMED
- **Severity:** P2
- **Evidence:** CMD-015 reported 291 baseline diagnostics versus 288 current, with no additions. The removed baseline entries are `I001` and `RUF022` in `platform/src/rag_eval/contracts/__init__.py` and `I001` in `contracts/schema.py`. The checker subtracts baseline identities, so reintroducing those exact diagnostics would not be considered new.
- **Disposition:** MERGE
- **Reason:** Remove fixed diagnostics from the baseline (and ideally ratchet periodically) so the differential gate cannot silently accept their regression.
- **Affected Files:** `ci/baselines/platform-ruff-before.json`; `ci/check_ruff_differential.py`; `ci/tests/test_ruff_differential.py`.
- **Counter-evidence checked:** Current code is cleaner and the current gate passes; this is a future-regression hole, not a present lint failure.
- **Recommended owner:** CI / Code Quality.
- **Validation after cleanup:** Current check passes with baseline count 288; a synthetic reintroduction of each removed identity fails the test harness.

### TEST-003 — Exact Python 3.13 and Node 22 matrix evidence is unavailable for this HEAD

- **Status:** UNABLE_TO_VERIFY
- **Severity:** P1
- **Evidence:** The local environment has Python 3.11.14 and 3.12.12 but not 3.13 (CMD-029); offline provisioning failed because `lxml==6.0.2` was not cached (CMD-008). WebUI passed on Node 24.12.0, but no Node 22 runtime/image was locally present (CMD-030). The audited HEAD is ten commits ahead of `origin/main`, so there is no same-HEAD remote CI result available from the recorded repository state.
- **Disposition:** REVIEW
- **Reason:** The approved audit rules make deterministic required gates without local or same-HEAD CI evidence a blocker to `READY`. This does not prove a code defect; it is an evidence gap.
- **Affected Files:** `.github/workflows/required.yml`; Python dependency locks; `webui/package-lock.json`; release evidence.
- **Counter-evidence checked:** Python 3.11 and exact 3.12 passed; Node 24 tests/build passed; packages built and Workers passed lifecycle smoke. None is exact evidence for the missing matrix entries.
- **Recommended owner:** CI / Release Engineering.
- **Validation after cleanup:** Run the unchanged HEAD in required CI or approved offline-pinned Python 3.13/Node 22 environments and attach exact pass/fail/skip outputs.

### TEST-004 — External LightRAG collection baseline is unreferenced migration residue

- **Status:** CONFIRMED
- **Severity:** P3
- **Evidence:** `ci/known-baseline.yaml:120-154` defines `lightrag_collection` and points at `ci/baselines/lightrag-collection-before.xml`; neither `.github/workflows/required.yml`, the signal-gate script nor CI tooling invokes that section (repository call-site search in CMD-025).
- **Disposition:** REMOVE
- **Reason:** It describes an external repository collection state that is not enforced and can be mistaken for a current gate. Remove both definition and snapshot together unless an owner first adds a real, pinned job.
- **Affected Files:** `ci/known-baseline.yaml`; `ci/baselines/lightrag-collection-before.xml`.
- **Counter-evidence checked:** Worker runtime locks and lifecycle smoke are separately active; no dynamic section enumeration or documentation reference was found.
- **Recommended owner:** CI / LightRAG Integration.
- **Validation after cleanup:** CI-tool tests and all active required jobs pass; no script/docs reference the deleted key or file.

### TEST-005 — Migration shadow and legacy fixtures still have bounded regression value

- **Status:** INTENTIONAL_COMPAT
- **Severity:** INFO
- **Evidence:** The behavior baseline and LightRAG dirty tests protect runtime/observation-profile separation, one-query equivalence, content hashes, round trip, split tables and both historical pre-segmented modes. CMD-010/011 passed all exact expected nodes.
- **Disposition:** KEEP_FOR_TEST
- **Reason:** Do not remove them merely to reduce test count. Reclassify or delete only after `ARCH-001` and route retirement provide equivalent stable v2 and negative-admission coverage.
- **Affected Files:** `tests/fixtures/native_evaluation_v2/behavior-baseline.json`; `test_native_evaluation_v2_baseline.py`; LightRAG dirty tests; unified shadow helper/tests.
- **Counter-evidence checked:** Some assertions are phase-specific and will become obsolete; today they cover the riskiest cutover boundary.
- **Recommended owner:** Evaluation / Adapter Test Owners.
- **Validation after cleanup:** Produce an invariant-by-invariant equivalence table before deleting any node; run exact Adapter and Platform gates after each removal.

### TEST-006 — Current shared Adapter TCK is narrower than Wire 2

- **Status:** CONFIRMED
- **Severity:** P2
- **Evidence:** `platform/src/rag_eval/adapters/observation_tck.py:21-44` assumes catalog identity and contiguous `1..N` ranks for all observed stages, while Wire 2 permits verified derivation and observed partial stages. Current LightRAG/RAG-Anything fixtures pass because both use identity-preserving stages (CMD-012/013).
- **Disposition:** MERGE
- **Reason:** Parameterize the TCK by declared stage transition/completeness before using it as proof that a third RAG needs Adapter changes only.
- **Affected Files:** Shared observation TCK; both Adapter TCK tests; new derived/partial fixtures.
- **Counter-evidence checked:** Core transformation validation tests exist and pass; the gap is specifically at Adapter conformance admission.
- **Recommended owner:** Observation Contract / Adapter TCK.
- **Validation after cleanup:** Contract-valid derived and partial fake Adapters pass; broken receipts, coverage proofs and prefix claims fail.

### TEST-007 — All locally runnable deterministic package, schema and lifecycle gates pass

- **Status:** DISPROVED
- **Severity:** INFO
- **Evidence:** CMD-006 through CMD-022 passed every locally runnable declared gate, including 369 Platform tests, exact Adapter gates, schema byte comparison, WebUI tests/build, three package builds/clean install and both model-free Worker lifecycles.
- **Disposition:** KEEP
- **Reason:** There is no evidence of a general red test suite, broken package or drifted Worker lock at this baseline. Findings above are policy/coverage gaps and architectural failures, not broad build instability.
- **Affected Files:** CI workflow, locks, packages, tests and Worker images.
- **Counter-evidence checked:** The missing Python/Node matrix and paid/real-model inference were explicitly excluded or unavailable and are not represented as passes.
- **Recommended owner:** All maintainers.
- **Validation after cleanup:** Repeat the same matrix after every cleanup batch and add exact missing-runtime evidence before release readiness is reassessed.
