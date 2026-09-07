# End-to-End RAG Evaluation Rehearsal Report

## E2E verdict: PASS

**PASS — the complete frozen-data → Runtime-only Bundle → LightRAG → private evaluation workflow was executed on the real DOCX without Gold entering the system under test.** This is an engineering rehearsal, not a score, ranking, or tuning claim. The observed metrics below are deliberately conservative diagnostics, not a comparative benchmark result.

## 1. Actual pipeline and immutable data lineage

```text
XXX网站系统（S2A2G2）_V2.0.docx
  → immutable Canonical / Ledger lineage validation
  → frozen Dataset Release
  → Bundle 3.0 private bundle + Runtime-only view
  → sealed source staging
  → LightRAG DOCX ingest and 33 queries
  → captured retrieval/context/answer traces
  → Worker shutdown
  → private Bundle 3.0 Gold / MSES evaluation
  → immutable RunManifest + successor evaluator report
```

This rehearsal did not rewrite any historical Case, Gold, review, approval, Canonical document, or formal release. Instead, `load_bundle_v3()` verified the sealed release chain, Canonical snapshots, source digests, Case/Gold revisions, approvals, and validation reports before the Adapter started.

| Item | Verified value |
| --- | --- |
| Dataset | `4867d37a2e17407e8ec774794e853b3c` |
| Target frozen release | `dataset-release-bcc904a2f011e567e5fb5548` |
| Target release digest | `bcc904a2f011e567e5fb5548a067c29f674d5c2f5da671ad927a8a64563898bb` |
| Parent release | `dataset-release-4758bfcc6b91c492bac9c9f2` |
| Source SHA-256 | `7d50899d15356000782b292bb84e135e4f1ebe20672ba9799939a6a1e2861755` |
| Target Canonical digest / schema | `4b52e327a691db86411dc5d17138b2c3ac2616d7240790ae804fb029d9112c97` / 1.1 |
| Parent Canonical digest / schema | `a2955ee975c9d5d42ed126fa050a7bdd6cee7e91aaa90958cfe8a25e1de18271` / 1.0 |
| Target parser / canonicalizer | `rag-eval-authoring-ooxml/1` / `rag-eval-authoring-canonicalizer/3` |
| Target canonicalizer config digest | `01a020ec981851b66ce9ff0241fe01077339a84fb3c0e49b0f4670687b5d8537` |
| Validation reports | parent `f94d64ca60ac414fda5f63c924a0e2c7180fc5ce638557d6c5f9faa57f8644b7`; target `af71ef588a4fe4c0a657703ab527e1111c90ea09165d6b12ec57a1ff19c765c5` |

Each formal validation report has 16 mandatory `ERROR`-severity rules with result `PASS`, including Canonical integrity, span/provenance, ledger revision integrity, independent review/approval lineage, MSES completeness, multi-hop closure, negative scope, answer/evidence consistency, and checksums. Its only non-pass finding is the pre-existing `WARN` that Bundle 2.0 is lossy/non-runnable for alternative paths and multi-hop semantics. Bundle 3.0 was used here; no Bundle 2.0 Gold projection was used.

The sealed lineage contains 124 approved review records and 66 reviewer approval records across the release chain. The target selection pins 33 frozen Case revisions, 33 frozen Gold revisions, and 63 evidence records.

## 2. Dataset actually executed

The development portfolio has 48 slots: **33 frozen slots were executed; 15 genuinely unsupported slots remain blocked and were not silently converted into easier questions.**

| Portfolio slice | Actual frozen Cases |
| --- | ---: |
| English / Chinese | 25 / 8 |
| Human / semi-synthetic / synthetic / adversarial source type | 12 / 9 / 8 / 4 |
| Single evidence / multi-evidence / multi-hop | 13 / 16 / 4 |
| Answerable / bounded negative-or-partial scope | 29 / 4 |
| Text / text-plus-table | 29 / 4 |
| Hard-only / Hard-or-Medium / Medium retrieval assignment | 13 / 12 / 8 |
| Direct extraction / relation-chain / aggregation-comparison or conditional compositions | 13 / 8 / 12 |
| Alternative MSES paths | 4 |

The data are all development data. The frozen historical 20-case registry was not read or modified for this run: its Bundle ID remains `d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e`, lifecycle `frozen`, usage `development/reference_diagnostic`, `held_out=false`, and `generalization_claim_allowed=false`.

## 3. Bundle 3.0 and Gold isolation

| Artifact | ID |
| --- | --- |
| Private evaluation Bundle 3.0 | `d7673da5d1bee5708f2c2564c4bbabdd85b2cbd86a98eaf5426d6a76905a74f6` |
| Runtime-only Bundle 3.0 | `a4a79e4d7b0f1fc31da7a2f7f24f9df48ef84ed41c195dd66ba95b7b94e3e82d` |

The runtime-only audit passed with zero private file violations and zero private field violations. Its exact file surface was only:

```text
checksums.json
manifest.json
questions.jsonl
source/7d50899d15356000782b292bb84e135e4f1ebe20672ba9799939a6a1e2861755.docx
```

The worker was passed only the checksum-verified source DOCX staged below its run sandbox. `worker_private_bundle_path_supplied=false`. It received no private bundle path, Gold answer, evidence label, MSES, negative scope, review result, approval, or Canonical snapshot. The private Bundle was loaded only after `worker.stop()` completed.

## 4. Pre-frozen experiment and actual LightRAG execution

`ExperimentSpec` was created before inspecting any query result:

```text
experiment_id = e2e-lightrag-bundle3-runtime-33-v1
run_id        = e2e-lightrag-bundle3-runtime-33-v1
formal        = false  # engineering rehearsal, not a formal comparison
seed          = 20260830
```

The fixed baseline was LightRAG `naive` / `legacy`, 1,200-token chunks with 100-token overlap, candidate K=20, final-context K=5, max context 12,000 tokens, reranking disabled, temperature 0, and all answer/query/LLM caches disabled. No parameter was changed after results were observed.

| Runtime identity | Recorded value |
| --- | --- |
| Adapter | `lightrag` 0.1.0; source commit `0b47f8661036678e112a00f4dc14a22ba8b2a95c` plus run-time patch digest `f4c16a9205f194a87d49a0a89aad001ab5efa2ccc5b27a924e0820f528cb4ddf` |
| LightRAG source | commit `fd118e277afd39789912646edbe8c5c70ce721f0`; server banner `v1.5.7/0329` |
| LightRAG Python distribution | `lightrag-hku` 1.5.5, which is why the immutable RunManifest reports system version 1.5.5 |
| Generation model | `qwen3:4b-instruct`, `sha256:0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0` |
| Embedding model | `bge-m3:latest`, `sha256:7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab` |
| Prompt source digest | `sha256:b4f8f544f5ad6b687fb32fca69595e7fc4710f4a37934b486f93659a16ff3c42` |
| Index fingerprint / storage digest | `5cd1690a134d524bd80cc1007b974f04fdf64732edff7e3e976d27d1f7329f3d` / `sha256:f171d1c1e6cdfc89497311e273e56d98648a492e85a0626ebce278c051f231d1` |

The real DOCX uploaded successfully. Native LightRAG logged 184 extracted blocks (83 tables, 5 drawings, 1 equation) and 196 embedded runtime chunks. All **33/33** `POST /query` calls returned HTTP 200; there were no skipped Cases or execution errors. Wall-clock run duration was 706.68 seconds, with 675.79 seconds total end-to-end query latency (20.48 seconds mean; 6.87–45.66 seconds range).

## 5. Trace capture and provenance status

Every completed Case has a `case-execution.jsonl` record linking `Run → Case revision → runtime chunk IDs → retrieval rank/context order → answer`. The Adapter preserved both normalized `raw_retrieval`, `ranked_retrieval`, and `final_context` arrays and the full native LightRAG evaluation trace.

| Trace field | Observed coverage |
| --- | ---: |
| Actual query payload and question | 33 / 33 |
| Raw retrieval candidates, ranks, scores, runtime chunk IDs | 33 / 33 |
| Ranked retrieval candidates, ranks, scores, runtime chunk IDs | 33 / 33 |
| Final 5-chunk context and order | 33 / 33 |
| Generated answer and end-to-end latency | 33 / 33 |
| Native rendered final answer prompt | 33 / 33 |
| Query rewrite / keyword trace | 0 / 33 — explicitly unavailable from the native API |
| Token usage | 0 / 33 — explicitly unavailable from the native response |

The immutable run’s capability declaration conservatively records `prompt_trace=false`, while its actual native traces contain `final_prompt` for 33/33 Cases. The current Adapter regression fix declares prompt tracing available while preserving per-result `unavailable` status if LightRAG omits `final_prompt`; the old manifest is intentionally not rewritten.

### Canonical ↔ runtime mapping

Runtime-only ingestion deliberately did not receive private Canonical data, so LightRAG’s native DOCX parser could not emit Canonical object/source-span IDs. The trace therefore correctly marks native provenance as `missing` rather than inventing object lineage. After worker shutdown, the private evaluator used a fail-closed bridge: a runtime chunk maps to a Gold object only when it contains an exact 48+ character witness unique to that Canonical object across the sealed Canonical snapshot.

This safely mapped **41 / 1,485** stage items (2.76%). Short and ambiguous values, especially logical table cells, remain unmapped and never become false-positive evidence hits. Thus runtime chunks are fully traceable to the source DOCX and their native IDs, but Canonical object mapping is **partial**, not complete. This is the principal Evaluation/Adapter follow-up, not a Data Layer semantic defect.

## 6. Private Gold evaluation

The Worker had already stopped before Gold was read. The private evaluator was `bundle-v3-private-mses-evaluator` 1.0, source digest `sha256:8e350fb7e8ca9fb76dbc29927b8add9bdcc1d12c3a8b33b3f64969b853bdedb2`.

It evaluates formal Bundle 3.0 semantics exactly as **OR(MSES paths) of AND(clauses) of OR(evidence alternatives)**. It did not flatten evidence, use Bundle 2.0 `required_groups`, or infer negative/unanswerable truth from retrieval absence. Multi-hop dependencies, alternative paths, evidence roles, and bounded negative scope remain explicit.

Because only the safe subset of chunks maps to Canonical evidence, all retrieval/context figures are lower-bound diagnostics:

| Stage | Clause recall @1 / @3 / @5 | Complete MSES path @1 / @3 / @5 | MRR |
| --- | --- | --- | ---: |
| Raw retrieval | 0.1034 / 0.1552 / 0.1552 | 0.0690 / 0.1034 / 0.1034 | 0.0990 |
| Ranked retrieval | 0.1034 / 0.1552 / 0.1552 | 0.0690 / 0.1034 / 0.1034 | 0.0990 |
| Final context | 0.1034 / 0.1552 / 0.1552 | 0.0690 / 0.1034 / 0.1034 | 0.0862 |

The typed answer scorer observed an exact result for 18 Cases (one passed); 15 Cases were `needs_review` because their representation is semantically ambiguous or non-canonical. Groundedness was observed for 14 answerable Cases and is `needs_review` for 19 Cases, including all four bounded negative/unanswerable Cases. No answer metric claims that retrieval absence proves an abstention correct.

## 7. Failure diagnosis with representative traces

The evaluator produces per-Case reasons, not only zeros. Counts are overlapping labels:

| Label | Cases | Interpretation |
| --- | ---: | --- |
| `retrieval_missing` | 22 | No complete MSES path was safely mapped in raw retrieval; this is a conservative lower bound due the partial bridge. |
| `context_selection_loss` | 4 | A safely mapped complete path occurred in ranked retrieval but was absent from final context. |
| `generation_failure` | 14 | The deterministic typed answer contract did not accept the generated answer. |
| `unsupported_answer` | 3 | Observed answer failed the typed answer contract in a bounded negative/unanswerable Case; it still requires semantic review. |
| `needs_review` | 33 | At least one runtime chunk was unmapped, or the answer/negative semantics are not safely automatic. |
| `ranking_failure`, `hallucination`, `abstention_failure`, `infrastructure_failure` | 0 labelled | Not asserted merely because of an unmapped chunk or a low metric. |

Representative non-Gold-leaking cases:

- `dev48-case-access-approval-controls`: its complete two-clause MSES path was safely present at ranked rank 7, then absent from the final five chunks. This is a real **context-selection** diagnosis, with answer evaluation retained as `needs_review`.
- `dev48-case-commissioned-evaluator`: its one-clause MSES path was safely mapped at rank 1 and retained in final context, but the generated answer did not satisfy the typed answer contract. This isolates a **generation/answer** failure rather than retrieval.
- `dev48-case-fire-suppression-remediation`: a two-hop Gold had one of two required clauses at rank 6, with none complete in final context. It is a **multi-hop partial-retrieval** diagnosis, not a claim that the missing clause is absent from the DOCX.
- `dev48-case-server-database-alternative`: its two legal alternative MSES paths were evaluated as alternatives, rather than flattened. Neither path had a safely mapped complete match; the result remains **retrieval lower bound / needs review**.
- `pilot-case-good-not-excellent`: its three-clause multi-hop path has no safe raw complete mapping and an observed answer mismatch; this preserves the distinction between evidence coverage and generation.
- `pilot-case-http-protocol`: it contains a `near_miss` evidence role. The evaluator did not convert that distractor into a required hit and retained the case as **needs review** under partial provenance.

## 8. Engineering repair performed during rehearsal

Two Evaluation/Adapter engineering issues were addressed without changing LightRAG behavior or any frozen data:

1. Runtime-only `DocumentInput(source_path=..., content=None)` now reads only from the prepared source sandbox, verifies the SHA-256, preserves `.docx`, and uploads the real binary. Regression coverage verifies sealed DOCX upload and rejects silent content substitution.
2. The original private full-value bridge mapped 0/1,485 stage items because native DOCX chunks and Canonical object values use different textual envelopes. A successor evaluator artifact replaced it with the source-unique long-witness rule, mapping 41/1,485 items. It is deliberately conservative, has regression tests for short/ambiguous rejection and unique-witness acceptance, and does not mutate the original run or its old evaluation artifacts.

The successor replay is at `/Users/sakura/RAG/.rag-eval-e2e-rehearsal-v5/private-evaluation-replay-v2`. Its manifest SHA-256 is `beb68e3383b57d8a6ccabce4bf12b3dd1d990dc304c384ad3b8b72ba45ed572b`; its evaluation JSONL SHA-256 is `80d3fa0068330697ba24243068f196a83ad703345de08838757f33e8b0460860`. It pins the original RunManifest SHA-256 `49c4a55c27b89784b5358df7a5838c34e08ca0c689510a53ff35f33b5492497c` and original execution trace SHA-256 `ac850cdab1f7dbc3698a49508032be840f307f53f03132bc93945315270e6a9e`.

## 9. Reproducibility and current limits

- Original RunManifest artifact digest: `sha256:4843c3ab2ec0afa6748c30bbf572e725481a1aa06f0711488d4321bcaf298131`.
- `RunStore.verify_artifacts()` passes with no missing, unexpected, or mismatched artifact.
- Final regression: Platform suite **137 passed, 3 skipped**; LightRAG Adapter suite **3 passed**. Both relevant code paths also pass `py_compile`.
- Execution workspace: `/Users/sakura/RAG/.rag-eval-e2e-rehearsal-v5`.
- Reproduction assets: `experiments/e2e-lightrag-bundle3-runtime-33-v1.json`, `runs/e2e-lightrag-bundle3-runtime-33-v1/run.json`, `release-snapshot.json`, `runtime-view-audit.json`, `ingestion.json`, `private-evaluation/case-execution.jsonl`, the immutable original private evaluation, and the sealed successor evaluation replay.

Remaining non-blocking limitations:

1. Native DOCX chunk IDs have no trusted direct source-span / Canonical-object bridge in Runtime-only mode. A future Adapter/Evaluator version should export deterministic native parser locators or a privacy-preserving canonical-to-runtime bridge for tables and rich structure. Do not loosen the current fail-closed rule to improve recall.
2. Query rewrites and token usage are absent from the current LightRAG response API, and are recorded as unavailable rather than fabricated.
3. The answer scorer intentionally routes semantic ambiguity, rich table values, and negative/unanswerable groundedness to human review. It must not be used as a blanket string-match benchmark metric.
4. This is one fixed development baseline only. It is not held-out validation, a system comparison, or permission to tune against its 33 Cases.

## 10. Platform acceptance answers

1. **Can the real DOCX reach a frozen Dataset / Bundle?** Yes: immutable source, Canonical, Case/Gold, review/approval, validation, Release, private Bundle, and runtime view lineage all verify.
2. **Does the Runtime-only Bundle isolate Gold?** Yes: zero private files and zero private fields, and only source DOCX/questions/checksums/manifest were staged.
3. **Did LightRAG ingest/query only through Runtime View?** Yes: only checksum-pinned runtime DOCX was supplied to the Worker.
4. **Do all 33 Cases have execution records?** Yes: 33 completed, 0 system errors.
5. **Are retrieval/context/answer traces complete?** Yes for LightRAG-provided retrieval stages, final context, answers, prompts, ranks, IDs, and latency. Query rewrite and token usage are explicitly unavailable.
6. **Can runtime chunks map back to Canonical evidence?** Partially and fail-closed: 41/1,485 safe mappings. It is not yet a complete direct provenance bridge.
7. **Does the private evaluator understand MSES, multi-hop, alternatives, and negative scope?** Yes; it evaluates those typed semantics without Bundle 2.0 flattening, and routes unsupported semantic conclusions to `needs_review`.
8. **Can it distinguish retrieval, ranking, context, and generation?** Yes when evidence is safely mapped; unmapped data remains labelled `needs_review`, never silently classified.
9. **Is the experiment reproducible through RunManifest?** Yes: configuration, source/model identities, indices, artifacts, checksums, and successor evaluator inputs are pinned and verified.
10. **Is there an Evaluation Layer blocker?** No blocker for this E2E workflow-health rehearsal. The incomplete Canonical↔runtime provenance bridge is a priority follow-up before treating retrieval scores as comprehensive benchmark measurements.

**Final conclusion: PASS — the platform has genuinely completed the end-to-end execution loop from real data production lineage through private Gold evaluation, with Gold isolation intact and partial provenance clearly fail-closed.**
