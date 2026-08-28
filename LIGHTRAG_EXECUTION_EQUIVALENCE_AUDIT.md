# LightRAG Execution Equivalence Audit

**Date:** 2026-08-28  
**Decision:** **PASS** — Platform → Adapter → LightRAG did not change the
observed LightRAG retrieval execution semantics for the frozen 20-case
canonical Bundle.

## Scope and invariants

This audit compares the same frozen canonical-text Bundle through four paths:

| Path | Audit run / reference run | Result |
| --- | --- | --- |
| Direct LightRAG Legacy | `direct-legacy-20260828` | 20/20 traces collected |
| Platform → Adapter → LightRAG Legacy | `4f9d2df532604bccbad7efdcebb8dd10` | 20/20 immutable case artifacts |
| Direct LightRAG Structured | `direct-structured-20260828` | 20/20 traces collected |
| Platform → Adapter → LightRAG Structured | `c8738013e8324fdbb52d4bb2a17a5bda` | 20/20 immutable case artifacts |

The Direct runs used fresh local LightRAG workspaces, the Platform runs used
their original run-scoped workspaces, and all four used Bundle
`d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e`.
No Dataset, Gold, scorer, metric, comparison contract, Evaluation Core, or
production code was modified.

Private source text, questions, answers, and full traces remain in local audit
workspaces under `/private/tmp`; this document records only IDs, counts,
digests, spans, and comparison outcomes.

## Frozen effective configuration

The runs shared these effective execution settings:

| Factor | Effective value |
| --- | --- |
| Canonical source | SHA-256 `65f03397ae45ae9e2cfa306c86ca1e3f89f408377f7a8f6bd3aada05d7a1c214` |
| Query mode | `naive` |
| Chunker | fixed-token / `Chunking F(legacy)` |
| Chunk size / overlap | 1200 / 100 tokens |
| Runtime chunks | 58 |
| Candidate K / final-context K | 20 / 5 |
| Context budget | 12,000 tokens |
| LLM | `qwen3:4b-instruct`, digest `sha256:0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0` |
| Embedding model | `bge-m3:latest`, digest `sha256:7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab` |
| Generation | temperature `0.0`, seed `20260824`, 32,768-token Ollama context |
| Run case-order seed | `20260826` |
| Reranker | disabled; no rerank model |
| KG | skipped through ingestion `process_options="!"` |
| Cache | answer/query/LLM caches disabled |
| Table view / row view / structured envelope | disabled |

The Structured profile genuinely changed its effective configuration, but only
in the following fields:

| Field | Legacy | Structured |
| --- | --- | --- |
| `ranking_strategy` | `none` | `structured` |
| `exact_id_types` | `[]` | `FACT`, `EQ`, `REF` |
| `table_preceding_context` | `false` | `true` |
| entity-extraction instruction profile | `legacy` | `structured_fidelity` |

## Layer-by-layer result

For both Legacy and Structured, Direct versus Platform was exact at every
retrieval layer after removing the Adapter's intentional canonical-provenance
projection fan-out. That projection maps one runtime chunk to all covered
canonical objects; it is evidence representation, not an additional LightRAG
retrieval or ranking stage.

| Layer | Legacy Direct vs Platform | Structured Direct vs Platform |
| --- | ---: | ---: |
| Canonical source digest | equal | equal |
| Chunk count, IDs, content hashes, spans, token counts | 58/58 exact | 58/58 exact |
| Question hashes and frozen order | 20/20 exact | 20/20 exact |
| Raw candidates, runtime IDs, scores, order, spans | 20/20 exact | 20/20 exact |
| Ranked candidates, runtime IDs, scores, order, spans | 20/20 exact | 20/20 exact |
| Final context, runtime IDs, scores, order, spans | 20/20 exact | 20/20 exact |
| Answer SHA-256 | 20/20 exact | 20/20 exact |

The Direct retrieval-only request and Direct answer request also returned the
same raw/ranked/final trace for all 20 cases in both profiles. This rules out a
query-endpoint split as a source of observed retrieval variance.

## Why Legacy and Structured look identical

The Legacy and Structured runs produced identical source, chunks, raw
candidates, ranked order, and final context for all 20 cases in both Direct
and Platform paths. The result is explained by the frozen execution conditions:

- All 20 questions contain zero `FACT-*`, `EQ-*`, `REF-*`, or `TBL-*`
  identifiers. Therefore the Structured exact-ID configuration had no query
  activation.
- `table_view` and `table_row_view` were disabled. The one enabled structured
  table setting did not change the resulting 58-chunk manifest for this
  canonical source.
- KG extraction was explicitly skipped and query mode was `naive`, leaving a
  chunk-vector retrieval path.
- The structured ranking hook is configured and called by the naive chunk
  path, but its implementation returns the candidate list unchanged when the
  query has no `FACT-*` or `TBL-*` identifier. The logs show only `Naive query:
  20 chunks` and `Final context: 5 chunks`; they contain no effective reorder
  or reranker invocation.
- Accordingly, raw and ranked retrieval were identical for all 20 cases. The
  final context is the normal five-item truncation of the 20-item ranked list;
  it is not a ranking change.

Nineteen of twenty Legacy/Structured answers were byte-identical. The remaining
case (`case-e59e310bde1e456fa047ff1d997b7581`) had identical final context in
all paths but a different generated-answer hash between profiles. The same
generation-only difference appears in Direct and Platform, so it is not an
Adapter or Platform semantic drift.

## Divergence assessment

No divergence was found at source representation, chunking, runtime chunk ID,
query request, raw retrieval, scoring, ranking, top-K, final-context selection,
or Adapter projection after its documented deprojection.

**Conclusion:** Platform extraction did not cause retrieval degradation. The
Adapter/Profile implementation does not show an execution-semantic defect for
this frozen Bundle. The observed Legacy/Structured metric equality is a real
property of this workload and configuration, not a Platform-induced collapse.

## Tests and provenance

- Direct audit harness syntax check: passed.
- Direct Legacy: 20/20; Direct Structured: 20/20.
- Current Adapter repository: `pytest -q tests/rag_eval_adapters` → **29
  passed, 4 skipped**.
- LightRAG ranking/cutover tests: `tests/recall_lab/test_structured_rank.py`
  and `tests/api/routes/test_eval_cutover.py` → **10 passed**.
- A mirrored legacy test in `LightRAG/tests/rag_eval_adapters` reported **1
  failed, 6 passed** because it still expects `object_provenance=False` while
  the current Adapter deliberately exposes canonical provenance. This is
  stale-test technical debt, not an audit-run regression and was not changed.

Execution provenance recorded by the frozen Platform runs: LightRAG
`e3edab52f4356fb3e429fd41b2c69ee6a00b3407`, Adapter
`ac05de84d3e83146563911b647bbdef38a9cc045`. Current repository commits differ
only through documentation/submodule-baseline consolidation changes:
LightRAG `42577f25`, Adapter `8646e6fa0a50014632035df762c7f577b930ff46`,
Platform pre-report `34cecee82d08a5d2a89e053045291c2a0404ddb1`.

## Next stage

Do not repair the Platform or Adapter for retrieval equivalence: the audit
passes. The next separately scoped work is a ranking/context diagnostic on the
unchanged 20-case Bundle, with an activation condition that can actually
exercise the ranking strategy. It must remain distinct from Dataset expansion
and must preserve the current Gold, metrics, Adapter contract, and Evaluation
Core.
