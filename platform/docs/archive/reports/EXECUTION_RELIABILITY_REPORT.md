# BYOD Execution Reliability Report

**Date:** 2026-08-28  
**Execution reliability result:** PASS  
**BYOD-10 result:** PASS, with non-gating native diagnostic limitations

This report closes the execution blockers recorded in `BYOD-10_REPORT.md`.
The private DOCX, canonical text, questions, answers, evidence witnesses, parser
outputs, and run artifacts remain only in local product storage. This report
contains no private document body, question wording, answer value, or evidence
quote.

## 1. Scope and invariants

- The existing four-case canonical Bundle was reused unchanged:
  `4045b77c905d…ae86b5c2`.
- The existing native-DOCX diagnostic Bundle was reused unchanged:
  `357616db6fd0…15026d3c`.
- No cases, questions, Gold answers, or Gold evidence were added or edited.
- Evaluation Core, RunExecutor semantics, metrics, comparison rules, and the
  native-DOCX diagnostic-only policy were not changed.
- Canonical and native execution views were not compared against each other.

## 2. LightRAG canonical ingestion root cause

### Reproduction

Legacy run `7ba3f3bc13fd43e68bc9d9af3c084e13` and Enhanced run
`ee4f41a92b3e4885bdc8ca438618a2f8` failed identically. The server telemetry
showed that canonical chunks 000, 001, 002, and 003 all started in the same
second and all raised `httpx.ReadTimeout` after exactly 240.0 seconds during
entity/relation extraction. The reported `C[1/58]` / chunk-002 value was the
failure selected by the concurrent aggregator; it was not evidence that the
private content of chunk 002 was uniquely malformed.

The adapter supports only LightRAG `naive` query mode. That mode retrieves from
chunk embeddings and does not consume the knowledge graph, but the adapter had
uploaded documents with an empty `process_options` value. This unnecessarily
started concurrent LLM-based knowledge-graph extraction for the first four
1,200-token chunks against one local Ollama runner. The avoidable extraction
work exhausted the 240-second calls and blocked ingestion.

A second defect hid the evidence: LightRAG rebuilt a message-less transport
exception as a prefixed empty string, and the adapter then persisted only that
empty message. The underlying exception type was present only in server logs.

### Minimal reproduction fixture

`rag-eval-adapters/tests/fixtures/canonical_naive_minimal.md` is a six-line,
fully synthetic canonical document. It contains no text, identifier, or value
from the private source. Its regression verifies that naive document upload
uses the documented `process_options="!"`, preserving chunk embedding ingestion
while skipping unused knowledge-graph extraction.

### Query blocker found after ingestion was fixed

The first post-ingestion reruns (`7cfad6c71ef940709b9d71dbbdbe2465`
and `7d690544f7474e8dbc3b8668d738abf4`) exposed a separate runtime configuration
defect. The Experiment allowed 12,000 context tokens, while the Ollama provider
still ran at 4,096. The four observed prompts were 6,076–7,223 tokens and Ollama
correctly rejected them. LightRAG's non-streaming query route then converted
its internal failure result into an HTTP 200 placeholder, so the adapter saw a
generic missing-trace error rather than the provider exception.

This was not a Gold, metric, comparison, or RunExecutor failure.

## 3. Fixes

| Repository / commit | Fix |
|---|---|
| LightRAG `d49ddbef` | Preserve exception type and `<no message>` when prefixing a message-less transport exception. |
| LightRAG `f3dafdfb` | Turn a non-streaming `aquery_llm` failure into the existing safe HTTP 500 path; keep full provider detail in server logs and expose only a correlation ID to clients. |
| rag-eval-adapters `3511864f` | Skip unused KG extraction for LightRAG naive ingestion; include the ingestion policy in effective config/fingerprint; persist non-empty typed adapter diagnostics. |
| rag-eval-adapters `3511864f` | Add RAG-Anything native liveness records for `parsing`, `indexing`, `stalled`, `cancelling`, `cancelled`, `failed`, and `completed`, plus bounded parse timeout and privacy-safe activity observations. |
| rag-eval-adapters `7cdb5f1a` | Propagate an explicit 32,768-token Ollama context to both LightRAG server bindings and RAG-Anything LLM options. |
| rag-eval-platform `01cf0bce` | Make cancellation bypass the blocked `/close` request, terminate and verify the worker process group, persist cancellation confirmation, and expose read-only run liveness. |
| rag-eval-platform `751d17f4` | Snapshot and terminate detached parser descendant groups as well as the worker group; this covers MinerU's independent fast-api PGID. |

The fixes change adapter/runtime lifecycle behavior only. They do not reinterpret
evaluation output or relax the Dataset/Gold contract.

## 4. Tests

| Area | Result |
|---|---:|
| LightRAG query/error/exception regressions | 18 passed |
| Adapter ingestion, liveness, and context regressions | 26 passed |
| Platform full suite | 84 passed, 3 skipped |
| Privileged detached-child cancellation checks | 3 passed |
| Ruff on changed Platform files | Passed |

The cancellation fixture launches a synthetic parser child with
`start_new_session=True`. It proves that both the worker group and the detached
child group terminate. The full Platform suite's process-table-dependent cases
remain skipped under the restricted test sandbox, so the same cases were also
run separately with process-table access and passed.

## 5. Unchanged canonical reruns

All three final runs used the same Bundle, the same four explicit case IDs, one
repetition, and the existing scorer/metric contracts.

| System | Final run ID | Execution | Artifact verification | Main metric observation |
|---|---|---:|---:|---|
| LightRAG Legacy | `4ee55a24304f4ae8bb1874c4c117abe4` | 4/4 completed; 0 system error | Valid | retrieval recall/MRR 0.0; answer metrics 4/4 `needs_review` |
| LightRAG Enhanced | `20bc5e70446c49279cdf4e24e229e987` | 4/4 completed; 0 system error | Valid | retrieval recall/MRR 0.0; answer metrics 4/4 `needs_review` |
| RAG-Anything canonical | `18f6610ac2c04fa2a227103a26d92d0c` | 4/4 completed; 0 system error | Valid | answer accuracy 0.0; retrieval/groundedness unavailable by declared capability |

LightRAG returned 20 raw items, 20 ranked items, and five final-context items per
case. Its returned items had document identity but no canonical object locator,
while Gold evidence uses canonical object locators. Therefore the observed 0.0
provenance recall cannot, by itself, distinguish a semantic retrieval miss from
an execution-evidence alignment miss. No metric or Gold logic was changed to
make this number look better.

LightRAG answer review reasons were either an answer containing the Gold value
without exact normalization or an additional contradictory/ambiguous numeric
value. RAG-Anything canonical answers failed the existing exact answer scorer.
These are answer-quality results, not execution failures.

## 6. Comparison result

The existing comparison validator was run across the three final canonical
runs at the task-comparable tier.

- `compatible: true`
- global incompatibility reasons: none
- `may_declare_winner: false`

No winner is declared. Answer accuracy is not metric-comparable because the two
LightRAG runs require review while RAG-Anything has an observed score. Retrieval
metrics are not comparable across all three systems because RAG-Anything's
public adapter correctly declares those traces unavailable. Legacy and Enhanced
also have identical observed retrieval scores on these four cases, so the
current set supplies no evidence for a winner between them.

## 7. Native-DOCX liveness diagnostic

### Bounded real diagnostic

Run `8f4cf0d437f74c9882d8229794677e36` exercised the original DOCX through the
real MinerU path. Liveness remained `parsing`; `progress_seq` advanced from 9 to
595, child CPU time increased, and the run never crossed the 120-second stall
threshold. It never emitted an `indexing` transition.

At the configured 1,200-second hard limit, the run transitioned to terminal
`failed` with `failed_stage=parsing`, the `RuntimeError` type, and an actionable
MinerU timeout message. The job also became `failed`. All associated worker,
MinerU CLI, fast-api, resource-tracker, and multiprocessing child PIDs were gone
after termination.

This is a parser throughput/completion limitation for this real document, not
an unobservable hang. It remains diagnostic-only and is excluded from the
canonical comparison.

### Real cancellation probe

Run `3b707a544b1848089551b9dcde2a7943` was started against the same native Bundle
only to verify cancellation. Before cancellation, the process tree contained a
worker group and a distinct MinerU fast-api group with multiprocessing children.
The official job cancel endpoint produced:

- job status `cancelled`;
- liveness stage `cancelled`, terminal `true`;
- `cancellation_confirmed: true`; and
- no remaining matching worker, MinerU, fast-api, or child PID.

The cancellation probe did not query cases, produce metrics, enter Compare, or
change the Dataset.

## 8. Remaining blockers and risks

1. MinerU did not complete this 105-page native parse within 1,200 seconds. The
   diagnostic is now bounded and actionable, but native indexing/queryability
   has not been demonstrated for this source.
2. LightRAG retrieval items do not carry the canonical object locators used by
   Gold evidence. The current 0.0 provenance metrics are therefore not yet a
   clean measurement of semantic retrieval quality.
3. Answer scoring exposes real output ambiguity: the two LightRAG profiles need
   review on all four answers and RAG-Anything canonical scores 0/4.
4. The four approved cases remain a reviewed smoke/acceptance set, not a formal
   benchmark release. This phase intentionally did not expand it.
5. The prior API-backed Authoring acceptance is unchanged; browser-level UI
   coverage was not re-run in this execution-reliability phase.

## 9. BYOD-10 decision

**BYOD-10: PASS, with non-gating native diagnostic limitations.**

The conditions that made BYOD-10 execution `BLOCKED` are closed:

- both LightRAG profiles now ingest and query the unchanged canonical Bundle;
- all three canonical systems complete 4/4 cases with valid artifacts;
- a same-view Compare completes under the existing rules and correctly refuses
  a winner claim;
- native parsing now reports live activity, active stage, explicit timeout, and
  terminal failure instead of hanging silently; and
- real cancellation is confirmed and leaves no parser processes behind.

This PASS is an execution/product acceptance result. It is not a benchmark
quality seal, a native-parser success claim, or a RAG winner declaration.

## 10. Recommended next step

Before adding cases, implement and validate a **canonical evidence provenance
bridge**: preserve canonical object IDs (or a deterministic object-to-runtime-
chunk mapping) through canonical ingestion and retrieval traces, then test
round-trip evidence observability without weakening Gold or changing metric
semantics. This is the highest-value next step because the systems now execute
reliably, but the current LightRAG recall values cannot cleanly separate a real
retrieval miss from locator non-observability.

After that, profile MinerU page/stage throughput and cache/model startup so the
native diagnostic can reach indexing within a documented budget. Dataset
expansion should remain deferred until the existing four cases produce
interpretable retrieval and answer evidence.
