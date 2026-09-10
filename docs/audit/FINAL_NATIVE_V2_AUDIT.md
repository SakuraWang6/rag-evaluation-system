# Final Native v2 Readiness Audit

## Verdict

```text
READY
```

- Audit date: 2026-09-10 (Asia/Shanghai)
- Audited repository: `evaluation-system`
- Audited implementation HEAD: `e740856a7c1c0890bd9162107307ab6722b4084e`
- Branch: `main`
- Runtime baseline: Conda environment `lightrag-memory-eval`, Python 3.11.15, pytest 9.1.1
- Web baseline: NVM Node 24.12.0, npm 11.6.2
- Scope: production code, contracts, schemas, routes, CLI, WebUI, tests, packages, Worker images, and Phase 11 data state

The commit that adds this report changes documentation only. The workspace lock pins the resulting delivery commit after publication; the runtime conclusions below refer to the implementation HEAD above.

## 1. Executive conclusion

The current implementation has one formal evaluation chain:

```text
Original DOCX
→ Immutable Benchmark Release
→ Native RAG / Direct Wire 2.0
→ Unified Trace
→ Unified Evaluation
→ Artifact 2.0
→ /api/v1 persisted views
→ WebUI
```

The two P1 issues and one P3 issue from the prior independent audit are closed:

1. A Run is now resolved directly from an immutable Benchmark Release. Dataset Bundle 2.0 is absent from admission, execution, schemas, API, CLI, and WebUI.
2. Abstention Gold preserves every `negative_scope_object_id`; the objects form conjunctive clauses and are scored without first-item truncation.
3. A Worker startup failure releases the process group, client, and log handle through one idempotent cleanup path.

No open P0, P1, P2, or P3 finding remains. Required deterministic gates pass on the user-selected local toolchain. Phase 11 deletion remains intact, historical Run IDs remain unreadable, and no valid Artifact 2.0 Run was lost because the approved inventory contained no Run eligible for preservation or migration.

## 2. Audit method and evidence policy

This conclusion was derived from the current HEAD rather than copied from an earlier READY receipt. The audit combined:

- route, import, symbol, schema, package, and filesystem reachability searches;
- executable positive and negative contract tests;
- direct-release admission and end-to-end Artifact tests;
- persisted-view tests with scorer functions deliberately made unusable;
- tamper and fail-closed tests;
- exact CI signal gates;
- isolated package builds and imports;
- model-free Worker lifecycle smoke tests using current wheels;
- independent verification of the approved Phase 11 inventory, receipts, deleted targets, and HTTP behavior.

Candidate legacy matches were checked for context. ADR text, audit history, comments, and permanent negative tests are not treated as live compatibility unless a production import, route, command, reader, writer, or public schema reaches them.

Repository baseline at the implementation HEAD:

| Signal | Result |
|---|---:|
| Tracked files | 277 |
| Tracked Markdown files | 28 |
| Test-related tracked files | 63 |
| Active public schema catalogs | one: `platform/schemas/2.0` |
| Exported active schemas | 38 |
| Tracked source changes before this report | none |

Ignored local caches and `.DS_Store` files were excluded from source conclusions.

## 3. Architecture and authority chain

| Boundary | Result | Evidence |
|---|---|---|
| Original source | PASS | `platform/src/rag_eval/execution.py:617-649` stages exactly one `.docx`, verifies its SHA-256, and stages the pinned Canonical observation sidecar. |
| Immutable Benchmark Release | PASS | `platform/src/rag_eval/datasets/formal.py:1490-1583` requires the Release, validation report, source, Canonical snapshot, and pinned payload; missing, removed, mismatched, or invalid inputs fail closed without ledger or Bundle fallback. |
| Native admission | PASS | `platform/src/rag_eval/runtime_admission.py:45-144` binds `ExperimentSpec.dataset_release_id` to the resolved Release and constructs an immutable plan from explicit query and metric configuration. |
| Adapter input | PASS | `platform/src/rag_eval/execution.py:617-665` validates the staged Original DOCX against `ResolvedRunPlanV2`; no platform chunk list is supplied to the Worker. |
| Direct Wire 2.0 | PASS | `platform/src/rag_eval/runs/orchestration.py:54-96` accepts only `PreparedSystemV2`, `NativeQueryV2`, and `AdapterRunResultV2`; one query produces the observed result. |
| Unified Trace validation | PASS | `platform/src/rag_eval/runs/orchestration.py:99-168` validates case, Adapter, system, and version identities and marks invalid traces corrupted/unavailable. |
| Unified Evaluation | PASS | `platform/src/rag_eval/runs/orchestration.py:171-265` is the sole point that calls the unified scorer; missing validated trace produces explicit unavailable metrics and `UNOBSERVABLE`, not zero. |
| Artifact 2.0 publication | PASS | `platform/src/rag_eval/runs/artifacts.py:97-152` stages, verifies, and atomically publishes an immutable Artifact directory. |
| Run state | PASS | `platform/src/rag_eval/runs/records.py:36-114` restricts `RunRecordV2` to orchestration metadata; only `COMPLETED` may reference a verified Artifact. |
| Persisted API views | PASS | `platform/src/rag_eval/runs/artifacts.py:227-330` and `platform/src/rag_eval/runs/views.py:132-260` read and verify persisted Artifact 2.0 members without invoking runtime, mapping, or scoring. |
| Report/comparison/review/WebUI | PASS | `platform/tests/rag_eval_platform/test_artifact_presentation_v2.py:135-203` disables scorer functions and still renders every supported persisted consumer. Review overlays bind an Artifact case digest in `platform/src/rag_eval/reviews.py:195-250`. |

The effective dependency direction is:

```text
Canonical Benchmark
        ↓
Observation / Adapter
        ↓
Unified Evaluation
        ↓
Run / Artifact 2.0
        ↓
Persisted API Views
        ↓
WebUI
```

No reverse dependency lets an Adapter filter Benchmark Gold, lets presentation recompute provenance, or lets Run metadata duplicate evaluation state.

## 4. Authority invariants

### 4.1 Benchmark and Gold

- `BenchmarkGoldV2` owns answer, typed evidence, MSES paths, dependencies, and every negative-scope object (`platform/src/rag_eval/contracts/benchmark.py:138-208`).
- Abstention scopes become one required clause per object (`platform/src/rag_eval/contracts/benchmark.py:210-234`).
- Release resolution validates source, Canonical, payload, case, and Gold pins before admission (`platform/src/rag_eval/datasets/formal.py:1490-1622`).
- Gold eligibility remains a Canonical concern; production scoring has no RAG-name or Adapter-capability branch.
- Supporting, conflicting, and near-miss evidence remain available in the Artifact but do not silently become required core evidence.

### 4.2 RunRecordV2 and Artifact 2.0

`RunRecordV2` has exactly these 12 fields:

```text
schema_version
run_id
experiment_id
resolved_plan_path
resolved_plan_digest
state
created_at
started_at
completed_at
execution_error
artifact_path
artifact_digest
```

The model uses `extra="forbid"` and contains no Gold, Trace, Metric, score, Failure, Provenance, case summary, or leaderboard eligibility (`platform/src/rag_eval/runs/records.py:36-60`). The exported JSON Schema also has `additionalProperties: false`.

Artifact 2.0 is self-contained and tamper-evident. Verification checks member hashes, unexpected and missing files, typed models, case snapshots, profile identities, summary reconstruction, and index reconstruction (`platform/src/rag_eval/runs/artifacts.py:268-330`). A corrupt or missing Artifact is withheld from normal presentation and is never replaced by legacy data or numeric zero (`platform/src/rag_eval/runs/views.py:29-33`, `platform/tests/rag_eval_platform/test_artifact_presentation_v2.py:261-306`).

### 4.3 Persisted-only consumers

Static import/call analysis found `evaluate_unified_trace` and `score_answer` only in the evaluation/orchestration layer. API, CLI, report, comparison, reviews, Run history views, and WebUI do not import or call the scorer, an Adapter, or the provenance mapper when reading a completed Run.

Executable proof is stronger than the static check: `test_artifact_v2_api_reads_only_persisted_views` replaces scorer functions with exceptions and successfully reads summary, cases, report, comparison, and review subjects from Artifact 2.0.

## 5. Core semantic verification

| Invariant | Result | Primary regression evidence |
|---|---|---|
| Canonical identity is stable and Adapter-independent | PASS | `test_gold_carries_a_stable_canonical_identity_without_adapter_input`; `test_native_benchmark_resolves_stably_without_editable_ledger` |
| Release sidecars and digests fail closed | PASS | `test_native_benchmark_rejects_missing_payload_without_ledger_fallback`; `test_native_benchmark_rejects_tampered_release_sidecars`; four invalid-release admission cases |
| Exact Gold survives Release resolution | PASS | `test_native_benchmark_preserves_exact_case_answer_and_mses_without_projection` |
| All abstention scopes are AND clauses | PASS | `test_native_benchmark_preserves_every_abstention_scope_as_an_and_clause`; `test_multi_object_abstention_requires_every_negative_scope_clause` |
| Partial/all abstention coverage persists correctly | PASS | `platform/tests/rag_eval_platform/test_run_artifact_v2.py:360-402`: one of two scopes is `partial`/0.5; both are `complete`/1 |
| Observed, empty, unobserved, unsupported, partial, truncated remain distinct | PASS | shared observation TCK and Wire 2 contract tests |
| Verified Top-5 is enough for `@1/@3/@5` and `MRR@5` | PASS | `test_verified_top_five_computes_all_core_metrics_without_full_ranking` |
| Insufficient/unknown prefixes make only affected metrics unavailable | PASS | `test_truncated_top_three_does_not_claim_top_five_or_mrr_at_five`; `test_unknown_earlier_rank_makes_mrr_unavailable_but_not_complete_coverage` |
| `UNAVAILABLE` is not zero | PASS | unavailable metrics persist `status=unavailable` and a null value; missing/corrupt Artifact presentation has no zero fallback |
| Absence without proof is `UNOBSERVABLE` | PASS | proof-gated failure tests, including incomplete ingestion/retrieval proof cases |
| Text spans and multiple chunks use extent union | PASS | `test_text_span_union_and_equal_weight_clauses_are_not_chunk_hit_counts` |
| Multiple physical cells can prove one logical table cell | PASS | `test_logical_table_cell_is_one_atom_proved_by_multiple_physical_cells` |
| Split/merged tables can union to complete evidence | PASS | `adapters/lightrag/tests/test_native_unified_trace.py:235-390` |
| Duplicate text and invalid witness fail closed | PASS | `adapters/lightrag/tests/test_native_unified_trace.py:392-468`; RAG-Anything duplicate-parser regression |
| Derived context needs verified transformation and output coverage | PASS | shared TCK receipt tests; `test_derived_context_without_output_coverage_proof_is_unavailable` |
| Pipeline losses require proof; stage gain is separate | PASS | `test_pipeline_loss_requires_a_proved_transition`; `test_verified_stage_gain_is_recorded_separately_from_loss` |
| Failure attribution is proof-gated | PASS | `test_failure_attribution_is_proof_gated_through_generation`; `test_parser_ranking_and_context_failures_require_complete_prior_proof` |
| Observation does not replay a native query | PASS | LightRAG and RAG-Anything single-execution tests |
| Artifact tampering fails closed | PASS | Artifact reader and RunRecord tamper/binding/publication-failure tests |

## 6. Legacy reachability audit

### 6.1 Product code and public contract

The following have no production definition/import, executable route, reader/writer, public schema, CLI command, or WebUI branch:

```text
Wire 1
RAGResult
SegmentTrace / SegmentTraceSet
legacy BenchmarkGold
Artifact 1.x reader/writer
Dataset Bundle 2.0 store/registry/materializer/loader
pre-segmented execution
canonical_segments execution
benchmark_segments execution
legacy scorer/failure/report
historical replay/rescore
legacy run projection
register-dataset
/api/v1/datasets
```

The only production occurrences of `evaluation_corpus` are explicit validation guards in `runtime_admission.py` and `contracts/native.py`; callers cannot select a corpus mode. The only `replay` matches in product code are explanatory prose saying that replay is not performed.

The active OpenAPI surface contains authoring Release routes, formal Release routes, system/experiment/job routes, persisted Run views, comparison, review, and product configuration. It contains no retired Dataset Bundle route. The CLI contains:

```text
compare
create-experiment
export-schemas
freeze-analysis-contract
freeze-comparison-spec
freeze-latency-protocol
freeze-model-lock
init
register-fake
register-system
run
serve
validate-blind-layout
verify-run
```

There is no `register-dataset`, replay, or rescore command.

### 6.2 Schema catalog

`platform/schemas/2.0` is the sole active schema catalog and exports 38 schemas. Searches found no:

```text
bundle_id
runtime_bundle_id
gold_evidence_set_id
required_groups
legacy_case
legacy_unavailable
```

`ExperimentSpec` is Release-bound, and the catalog includes the Native Benchmark, Direct Wire 2.0, Unified Trace, RunRecordV2, Artifact 2.0, and persisted view schemas.

### 6.3 Offline Bundle 3 boundary

`platform/src/rag_eval/datasets/bundle_v3.py` remains a private, lossless offline publication/verification format. It declares that it is neither an authoring importer nor a runtime input (`bundle_v3.py:1-6`). The production dataset package does not import or export it (`platform/src/rag_eval/datasets/__init__.py:1-40`), and no admission, executor, API runtime summary, or public schema imports it. Tests confirm that it has no runtime manifest/questions/export path.

Therefore Bundle 3 is not a second evaluation route.

## 7. Closed findings

### NV2-FIX-001 — Runtime depended on Dataset Bundle 2.0

- Status: CLOSED
- Severity before fix: P1
- Disposition: REMOVE completed
- Evidence: commits `3576102` and `974d1ea`; `resolve_native_benchmark()` at `platform/src/rag_eval/datasets/formal.py:1490`; direct Release admission at `platform/src/rag_eval/runtime_admission.py:45`; source-only staging at `platform/src/rag_eval/execution.py:617`.
- Counter-evidence checked: API routes, CLI parser, WebUI strings/types, public schemas, package exports, runtime imports, and negative retirement tests.
- Validation: direct-release end-to-end tests pass while retired symbols and routes are asserted absent.

### NV2-FIX-002 — Multi-object abstention Gold was truncated

- Status: CLOSED
- Severity before fix: P1
- Disposition: exact Gold preservation implemented
- Evidence: `BenchmarkGoldV2.scoring_paths()` creates one clause per negative-scope object (`platform/src/rag_eval/contracts/benchmark.py:210-234`); Release and Artifact tests preserve both object IDs and distinguish partial from complete coverage.
- Counter-evidence checked: no `[0]` selection of `negative_scope_object_ids`; no lossy Bundle projection remains.
- Validation: Platform full suite includes Release-, scorer-, and persisted-Artifact-level multi-object cases.

### NV2-FIX-003 — Worker startup leaked partial resources

- Status: CLOSED
- Severity before fix: P3
- Disposition: unified cleanup implemented
- Evidence: `platform/src/rag_eval/worker/process.py:50-165` places log open, `Popen`, client construction, and readiness in one exception boundary and detaches/closes all owned resources idempotently.
- Counter-evidence checked: failure before `Popen`, failure after process creation, readiness failure, repeated stop/cancel, and partial resources without a process.
- Validation: `platform/tests/rag_eval_platform/test_worker_process.py:137-304` passes.

### NV2-AUD-001 — Ruff baseline still named deleted sources

- Status: CLOSED DURING FINAL AUDIT
- Severity: INFO
- Disposition: baseline ratcheted
- Evidence: commit `e740856`; portable baseline now records 144 current diagnostics, 87 fixable, SHA-256 `4246f2244bb89db4aa345d789aa1f6687cfde7cd4458c4f11f2e35a21f8b8b57`.
- Validation: differential result is baseline 144, current 144, added 0, removed 0.

There are no open findings requiring cleanup.

## 8. Phase 11 data verification

Approved inventory identity:

```text
inventory_id: phase11-b060b8eb8b4c21013df6
approved payload SHA-256: b060b8eb8b4c21013df6335947a13d44e668c5b711e1bfcb00080ef41f5eb6c3
exact deletion targets: 173
unique historical Run IDs: 86
```

Independent post-check results:

| Check | Result |
|---|---|
| Six inventory/staging/execution/postcheck/final-validation sidecar hashes | PASS |
| Approved exact targets currently absent | 173/173 |
| Historical Run reads | 86 IDs × 7 endpoints = 602/602 HTTP 404 |
| `/api/v1/runs` in isolated verification home | empty |
| Active project `platform-home` files | 0 |
| User-home runs/jobs/experiments/plans/reviews/presentations | 0 each |
| Runtime Artifact 2.0 manifests | 0 |
| Historical replay paths | 0 |
| Operational metadata or database residue tied to deleted Runs | 0 |
| Unknown references | 0 |

The inventory contained no `MIGRATE_ARTIFACT2_RUN` target, so no valid Artifact 2.0 Run existed to migrate or preserve. This makes the no-loss condition explicit rather than inferred.

The private source document remains intact:

```text
path: data/sources/private/XXX网站系统（S2A2G2）_V2.0.docx
size: 620650 bytes
sha256: 7d50899d15356000782b292bb84e135e4f1ebe20672ba9799939a6a1e2861755
```

One inert pre-cutover dataset-registry JSON record and an empty historical directory may exist under the user home. Current product code has no store, route, import, schema, or command capable of reading them; they are not Runs, Artifacts, jobs, reviews, or supported formats and do not form a compatibility path.

## 9. Deterministic gate results

Per the user-approved policy, this audit uses the installed local Conda/NVM environments as the sole required baseline. It makes no Python or Node cross-version compatibility claim.

| Gate | Runtime | Result |
|---|---|---|
| Platform exact signal gate | Conda Python 3.11.15 / pytest 9.1.1 | 330 passed; exact collection and required-node policy passed |
| Shared Adapter contract | same Python baseline | 20 passed |
| LightRAG native observation | same Python baseline | 18 passed |
| RAG-Anything native observation | same Python baseline | 17 passed |
| CI policy tooling | same Python baseline | 24 passed |
| Ruff differential | Ruff 0.16.1 | baseline 144, current 144, added 0 |
| Documentation authority | same Python baseline | 2 passed |
| Checked-in Schema 2.0 diff | same Python baseline | 38 exported; byte/diff clean |
| Platform package build/install smoke | uv 0.9.18 | wheel + sdist built; isolated target install/import/resource/CLI passed |
| LightRAG Adapter package | uv 0.9.18 | wheel + sdist built; isolated target import passed |
| RAG-Anything Adapter package | uv 0.9.18 | wheel + sdist built; isolated target import passed |
| WebUI tests | NVM Node 24.12.0 / npm 11.6.2 | 5 files, 34 tests passed |
| WebUI production build | same Node baseline | TypeScript/Vite build passed |
| LightRAG Worker lifecycle | Docker 29.4.0, locked base + current wheels | PASS; Wire 2.0, LightRAG 1.5.7, model-free health/prepare lifecycle |
| RAG-Anything Worker lifecycle | Docker 29.4.0, locked base + current wheels | PASS; Wire 2.0, RAG-Anything 1.3.1, model-free health/prepare lifecycle |
| Workspace lock unit tests | Conda Python baseline | 20 passed |
| Workspace lock final verifier | delivery commit | PASS after report publication and lock update |

No dependency installation into a new virtual environment was required. Python commands used `conda run -n lightrag-memory-eval`; package installation smoke used an empty isolated `--target` directory. Node commands used the installed NVM Node 24.12.0 binaries.

## 10. Command ledger

| ID | Reproducible action | Result |
|---|---|---|
| `FINAL-CMD-001` | Record HEAD/status, tracked/Markdown/test counts, schema directories | implementation HEAD and counts recorded above |
| `FINAL-CMD-002` | `conda run -n lightrag-memory-eval python ci/pytest_signal_gate.py --section platform_pytest --profile ci` | 330 passed |
| `FINAL-CMD-003` | Run `adapter_pytest`, `lightrag_native_pytest`, and `rag_anything_pytest` signal gates | 20 + 18 + 17 passed |
| `FINAL-CMD-004` | `conda run ... pytest -q ci/tests` and Ruff differential | 24 passed; no added diagnostics |
| `FINAL-CMD-005` | Export schemas to `/private/tmp` and `diff -ru` against `platform/schemas/2.0` | 38 schemas; no diff |
| `FINAL-CMD-006` | NVM Node 24.12.0: `npm test` and `npm run build` | 34 tests and production build passed |
| `FINAL-CMD-007` | Build three wheel/sdist pairs; install to an empty target; run import/resource/CLI probes | passed |
| `FINAL-CMD-008` | Build candidate Worker images from locked bases plus current wheels; run model-free lifecycle smoke | both passed |
| `FINAL-CMD-009` | Search product imports/routes/schemas/CLI/WebUI for retired contracts and corpus modes | no live legacy route found |
| `FINAL-CMD-010` | Inspect `RunRecordV2` schema and product OpenAPI/CLI inventory | strict 12-field record; no retired API/command |
| `FINAL-CMD-011` | Verify Phase 11 SHA sidecars, 173 targets, active homes, and source DOCX | passed |
| `FINAL-CMD-012` | Probe seven persisted Run endpoints for each of 86 historical IDs | 602/602 returned 404 |
| `FINAL-CMD-013` | Run workspace lock tests, pin delivery commit, and run `scripts/verify_workspace_lock.py` | passed |

Raw command output and temporary build artifacts were kept under `/private/tmp` and are not committed to the repository.

## 11. Limitations

- The required compatibility baseline is intentionally the local Conda Python 3.11.15 and NVM Node 24.12.0 environment. Python 3.12/3.13 and Node 22 are not part of this audit's acceptance contract.
- Worker smoke is model-free and validates protocol, packaging, process lifecycle, and native prepare/health behavior. It does not call paid models or production services.
- No retained completed Run exists after the approved Phase 11 deletion, so persisted-read behavior is proven by deterministic synthetic Artifact 2.0 fixtures rather than a surviving user Run.

These are declared scope boundaries, not missing mandatory evidence.

## 12. Final readiness decision

The repository satisfies every hard READY condition:

- one direct Release-bound Native DOCX execution route;
- no executable/readable historical format or hidden second main chain;
- Direct Wire 2.0 shared by fake, LightRAG, and RAG-Anything Adapters;
- Unified Evaluation as the sole scoring and failure-attribution authority;
- Artifact 2.0 as the sole result authority;
- strict orchestration-only RunRecordV2;
- persisted-only API/report/comparison/review/WebUI reads;
- proof-gated `UNAVAILABLE`/`UNOBSERVABLE`, Top-K/MRR, transformation, multi-chunk, duplicate, table, and tamper semantics;
- complete Phase 11 deletion with no unknown reference or lost valid Artifact 2.0 Run;
- all mandatory local deterministic gates green.

Final status:

```text
READY
```
