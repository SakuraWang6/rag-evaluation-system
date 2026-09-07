# Frozen 20-case Ranking / Context Diagnostic

**Status: PASS** — the frozen diagnostic establishes a ranking/context
bottleneck without finding an Adapter or Platform execution-semantic defect.

## Scope and freeze

This is a read-only diagnostic over the canonical 20-case Bundle. It does not
change the Bundle, Gold Evidence, answer scorer, evidence scorer, metrics,
Adapter contract, Evaluation Core, or any question wording.

| Frozen input | Identity |
|---|---|
| Bundle | `d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e` |
| Canonical document | `65f03397ae45ae9e2cfa306c86ca1e3f89f408377f7a8f6bd3aada05d7a1c214` |
| Legacy run | `4f9d2df532604bccbad7efdcebb8dd10` |
| Structured run | `c8738013e8324fdbb52d4bb2a17a5bda` |
| LLM / embedding lock | `qwen3:4b-instruct` `sha256:0edc…68ba0`; `bge-m3:latest` `sha256:7907…6bab` |
| Candidate / final context | `20` / `5` |

Candidate-level comparisons merge Platform’s canonical provenance projections
by `(rank, native_id)`. This avoids treating one LightRAG runtime chunk as
multiple retrieved candidates merely because it maps to several canonical
objects.

The retained local, source-redacted diagnostic artifacts are under
`/private/tmp/lightrag-ranking-context-diagnostic-20260828/`:
`frozen_analysis.json`, `top50_candidate_pool.json`, and
`counterfactual_rerank.json`.

## Baseline finding

The frozen Legacy and Structured runs have identical raw, ranked, and final
candidate orders for all 20 questions. In particular, raw and ranked retrieval
are the same list: there is no separate ranked-stage loss. The full-run
baseline is `context Recall@5 = 0.50`.

Six cases have all required Gold evidence in the fixed BGE-M3 top-20 pool but
outside final-context top-5: ranks `6, 7, 8, 11, 14, 20`. They are all
final-context selection losses, not candidate-pool misses.

| Case | Gold rank | Primary audit classification | Supporting observation |
|---|---:|---|---|
| `case-99c5a254df1a4b73a29a098368acf527` | 6 | `LEXICAL_DISTRACTOR` | Top-5 is dominated by summary-table occurrences of the status phrase; the scoring rule is in a different, long chunk. |
| `case-874745d934d24e3c85e6d2acf7d17fec` | 7 | `SEMANTIC_NEAR_MISS` | Nearby conclusion/risk text is highly topical, but the complete decision condition falls in a separate chunk. |
| `case-0dd707b2ed894a959706d58dda84625d` | 8 | `WRONG_SECTION` | A parallel summary states the same issue and ranks first, while the frozen Gold provenance is in a different analytical section. |
| `case-c191d27a84ca42a684a72f2ea84fe0a3` | 11 | `LEXICAL_DISTRACTOR` | Generic report/introduction language outranks the narrow distribution rule embedded in a broad section. |
| `case-decc05076bc84b95acbdea784dbdb4f9` | 14 | `SEMANTIC_NEAR_MISS` | Risk/conclusion/remediation passages share the query vocabulary; the factor-definition evidence is lower in the pool. |
| `case-a68460e6f98542e7be69f243d234c3a6` | 20 | `LONG_CHUNK_DILUTION` | Contents, aggregate tables, and adjacent summaries dominate a short total-count question; the answer-bearing statement is late in a long narrative chunk. |

`WRONG_SECTION` and `SEMANTIC_NEAR_MISS` are intentionally provenance-aware:
they do not claim that a top-ranked parallel passage is factually unrelated.
They explain why it cannot satisfy this frozen exact-locator evidence contract.
The common underlying mechanism is long, heterogeneous fixed-token chunks,
with repeated domain vocabulary and table summaries creating dense-similarity
distractors. `WRONG_TABLE_ROW` and `ENTITY_COLLISION` were not the primary
cause in this six-case cohort.

## Oracle rerank upper bound

The oracle preserves each case’s fixed top-20 candidate membership and only
promotes candidates already matching required Gold evidence before selecting
five final-context chunks. It does not generate a new answer or add a document
chunk.

| Full 20-case metric | Baseline | Oracle | Change |
|---|---:|---:|---:|
| Context Recall@1 | 0.20 | 0.80 | +0.60 |
| Context Recall@3 | 0.40 | 0.80 | +0.40 |
| Context Recall@5 | 0.50 | 0.80 | +0.30 |

The +0.30 is exactly the six retrievable-but-truncated cases. The remaining
0.20 consists of the three true retrieval misses plus one
`PARTIAL_UNOBSERVABLE` representability case; it is not reachable by a
top-20-only reranker.

For answer metrics, re-scoring the frozen answer strings after an oracle
context substitution leaves the observed answer accuracy and groundedness at
`1/6 = 0.167`. That calculation is non-causal: the strings were generated
from the original context. It is retained only to show that retrieval-only
reordering must not be reported as an answer-quality gain.

## Candidate-pool depth check

A temporary loopback LightRAG process queried a **copy** of the Legacy index
at `retrieval_candidate_k=50`, with answer generation and reranking disabled.
The three `FULL` raw misses were checked post-hoc with the unchanged
provenance matcher.

| Frozen true miss | First Gold rank at k=50 | Interpretation |
|---|---:|---|
| `case-09a8ceb2fd234fa792053c48363f488b` | 21 | Candidate depth can expose it, but top-20 cannot. |
| `case-e81b1553b4d64bbfbd872f95fab83dad` | 46 | Candidate depth can expose it, but requires a substantially wider pool. |
| `case-e95211e1e6d24d74b40ecdf9533a82fa` | absent | Still a retrieval miss at k=50. |

Therefore the current top-20 pool is sufficient for all six context-drop
cases, insufficient for two of the three true retrieval misses, and not
sufficient on its own for the third. Increasing `top_k` alone is not an
optimization result; it needs a subsequent, controlled reranker/context
selection policy.

## Gold-blind counterfactual reranking

The following is a diagnostic over the **preselected six-case failure cohort**,
not a new formal benchmark and not a generalization claim. For every variant:

- the natural-language question is unchanged;
- the exact frozen top-20 BGE-M3 candidate pool is unchanged;
- Gold values, locators, and answer values are unavailable to the reranker;
- changed top-5 contexts regenerate an answer with the locked Qwen model and
  are evaluated by the unchanged Platform scorers.

The first attempted Qwen listwise reranker was stopped after a single
long-context structural batch exceeded ten minutes without a result. It is
not included as a metric. The completed variants are deliberately lightweight
and configuration-only:

| Variant | Selection rule | Cohort context hit@5 | Observed answer accuracy | Observed groundedness |
|---|---|---:|---:|---:|
| Baseline | frozen BGE-M3 order, top-5 | 0/6 | 0/2 | 0/2 |
| Semantic | BGE-M3 max cosine over three fixed windows per candidate | 5/6 | 0/2 | 0/2 |
| Structure-aware | `0.80 ×` segment-MaxSim + `0.20 ×` automatic heading-path cosine | 5/6 | 0/2 | 0/2 |

Four of the six answers remain `needs_review` under the frozen typed scorer;
the other two are observed failures for every variant. Thus the experiment
establishes a 5/6 evidence-placement rescue within the diagnosed cohort, but
does **not** establish any answer-accuracy or groundedness improvement.

Both completed variants select the same top-5 in each case. The lone non-rescue
is `case-0dd707b2ed894a959706d58dda84625d`, where a parallel summary remains
more attractive than the exact Gold section. Heading-path information alone is
therefore too weak to resolve duplicate/parallel-section ambiguity.

## Why the existing Structured profile is an identity on these questions

This is configuration behavior, not an Adapter defect. The profile is enabled
in the Structured run, but `lightrag/ranking/structured.py` applies tiers only
when a query contains explicit `FACT-…` or `TBL-…` identifiers. The frozen 20
natural-language questions contain neither. `table_preceding_context`,
table-view, and row-view settings likewise introduce no candidate-order change
for this source/configuration. Consequently the strategy returns the original
vector order and Legacy/Structured results remain identical.

The Platform → Adapter → LightRAG equivalence audit already showed that this
same identity behavior occurs in both Direct and Platform execution. There is
no Adapter projection, profile serialization, or Platform semantic drift to
fix here.

## Conclusion and next milestone

Ranking/final-context selection is worth the next research iteration, ahead of
answer prompting and without changing the frozen evaluation contracts:

1. Design a Gold-blind reranker that distinguishes duplicate sections and
   table/summary views, then evaluate it without selecting cases by Gold.
2. Treat `candidate_k` and final-context selection as separate parameters:
   test a wider pool with reranking for the two k=50-revealed misses, while
   preserving a fixed context budget.
3. Keep the third k=50 miss in the retrieval diagnostic track; ranking cannot
   recover an absent candidate.
4. Keep answer-generation work separate. The current observed answer subset
   remains too small and four of these six answers are scorer-ambiguous.

No production ranking change is made in this phase. Do not modify the Adapter,
Platform, Gold, scorer, metric, or comparison contract on the basis of this
diagnostic alone.

## Verification and commits

The report is documentation-only. The frozen runs originate from LightRAG
`e3edab52f4356fb3e429fd41b2c69ee6a00b3407` and Adapter
`ac05de84d3e83146563911b647bbdef38a9cc045`; later changes before this phase
are documentation-only and were separately verified by the execution
equivalence audit.

| Repository / command | Result |
|---|---|
| Platform: `python -m pytest -q` | `89 passed, 3 skipped` |
| LightRAG: `pytest -q tests/recall_lab/test_structured_rank.py tests/api/routes/test_eval_cutover.py` | `10 passed` |
| Adapters: `pytest -q tests/rag_eval_adapters` | `29 passed, 4 skipped` |

The only committed phase change is this report (and the parent LightRAG
submodule-pointer/release-note update that records it). No runtime or
evaluation-contract code is changed.
