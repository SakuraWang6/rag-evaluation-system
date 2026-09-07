# Benchmark Diagnostic Expansion Report

**Date:** 2026-08-28  
**Decision:** PASS for the LightRAG diagnostic expansion; RAG-Anything
canonical execution is explicitly blocked by the current host's loopback
permission and is non-gating for this phase.

This report contains no private DOCX body, question wording, answer value, or
evidence quote. Case identifiers and rank vectors are retained because they are
non-content evaluation provenance.

## 1. Scope and invariants

- The expanded canonical-text Bundle was used unchanged for both completed
  LightRAG runs:
  `d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e`.
- The release contains the original four cases plus 16 newly released cases;
  no new Gold was generated during execution.
- Gold Answer, Gold Evidence, scorer, metric, comparison, RunExecutor, and
  adapter semantics were not changed.
- The original private DOCX and all source-derived text remain in local
  product/run storage only.
- No current LightRAG-specific question optimization was applied.

## 2. Authoring and review result

The workspace contains 24 candidate records and 27 immutable review records
(the extra records are explicit edit/version reviews). The final workspace
state is 21 approved and 3 rejected candidates. Of the approved records, one
historical table-scoped negative candidate was not exportable under the formal
Bundle locator contract and was excluded from this release; its record was not
silently weakened or deleted.

| Scope | Count |
|---|---:|
| New candidates considered (including the corrected negative replacement) | 19 |
| New approved at workspace level | 17 |
| New rejected | 2 |
| New cases released in the Bundle | 16 |
| Original cases retained | 4 |
| Cases evaluated | 20 |

The two new rejections were a partial/unobservable evidence candidate and an
ambiguous subjective-ranking candidate. The historical rejected candidate is
also retained in the review ledger. No candidate was accepted to reach a quota.

### Case type distribution in the released Bundle

| Task type | Cases |
|---|---:|
| single_block_retrieval | 4 |
| single_document_retrieval | 3 |
| cross_section_relation | 1 |
| multi_hop | 1 |
| table_lookup | 3 |
| table_comparison | 2 |
| long_distance_retrieval | 3 |
| version_authority_relation | 1 |
| version_or_authority_relation | 1 |
| negative_abstention | 1 |
| **Total** | **20** |

Multi-hop was included only where the source supplied an independently
verifiable relation; no artificial multi-hop quota was used.

## 3. Evidence Representability Gate

The authoring gate was run against the frozen canonical source and the
LightRAG canonical-text provenance profile. It is diagnostic-only and never
changes Gold to fit a chunker.

| Gate outcome | Released cases |
|---|---:|
| `FULL` / `PASS` | 19 |
| `PARTIAL_UNOBSERVABLE` / `FLAG` | 1 |
| **Total** | **20** |

Additional authoring diagnostics:

- One new partial candidate was flagged and rejected during review.
- One previously approved historical candidate was blocked from export by an
  invalid table-scoped negative locator and excluded as a dataset-case issue.
- The one flagged released case is retained for diagnostic accounting and is
  never counted as a normal retrieval miss.

For exact attribution, a Gold group is a hit only when a runtime item carries
the same document and canonical locator. No answer substring, fuzzy matching,
or Gold-aware retrieval inference is used.

## 4. Actual execution

### LightRAG

| Profile | Run ID | Cases | Artifact verification |
|---|---|---:|---|
| Legacy | `4f9d2df532604bccbad7efdcebb8dd10` | 20/20 | valid; no missing, unexpected, or mismatched files |
| Enhanced / structured | `c8738013e8324fdbb52d4bb2a17a5bda` | 20/20 | valid; no missing, unexpected, or mismatched files |

Both runs used the same Bundle, case selection, model lock, seed, one
repetition, and provenance map. Raw, ranked, and final-context provenance
observations and all aggregate metrics were byte-for-byte equivalent at the
reported metric level.

### RAG-Anything canonical

Attempted job: `0abea04d4e354ed6a6dbaacc31a186c9`. It did not create a run: the
restricted host rejected the worker's `127.0.0.1` port bind with
`PermissionError: [Errno 1] Operation not permitted`. This is an environment
blocker, not a dataset or adapter result. No RAG-Anything score is reported and
no cross-system winner claim is made.

## 5. Aggregate metrics

The existing scorer and metric definitions are unchanged. Values below are
computed over all 20 cases; the denominator for answer metrics is six because
14 cases correctly remain `needs_review` under the existing answer evaluator.

| Metric | Legacy | Enhanced |
|---|---:|---:|
| raw Recall@1 | 0.20 (4/20 groups) | 0.20 (4/20 groups) |
| raw Recall@3 | 0.40 (8/20 groups) | 0.40 (8/20 groups) |
| raw Recall@5 | 0.50 (10/20 groups) | 0.50 (10/20 groups) |
| ranked Recall@1 | 0.20 | 0.20 |
| ranked Recall@3 | 0.40 | 0.40 |
| ranked Recall@5 | 0.50 | 0.50 |
| raw MRR | 0.3465097403 | 0.3465097403 |
| ranked MRR | 0.3465097403 | 0.3465097403 |
| final-context Recall@1 | 0.20 | 0.20 |
| final-context Recall@3 | 0.40 | 0.40 |
| final-context Recall@5 | 0.50 | 0.50 |
| context selection loss @1/@3/@5 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| answer accuracy (observed subset) | 0.1667 (1/6) | 0.1667 (1/6) |
| answer groundedness (observed subset) | 0.1667 (1/6) | 0.1667 (1/6) |
| unsupported answer rate (observed subset) | 0.8333 (5/6) | 0.8333 (5/6) |

The formal context-selection-loss metric is zero because the scorer's stage
recall is group-based and the ranked/context cutoffs are evaluated at the same
configured `k`. The case-level attribution below separately exposes six Gold
groups that were present in ranked retrieval only at ranks 6–20 and therefore
were absent from the five-item final context.

## 6. Failure attribution

The primary buckets below are mutually exclusive for the 20 evaluated cases.
`RETRIEVED_BUT_LOW_RANK` is also reported as a secondary signal when the Gold
rank is greater than five; in this run all six such cases ended as a
`FINAL_CONTEXT_DROP` because `final_context_k=5`.

| Primary attribution | Cases |
|---|---:|
| `RETRIEVAL_SUCCESS` | 7 |
| `REAL_RETRIEVAL_MISS` | 3 |
| `FINAL_CONTEXT_DROP` | 6 |
| `PARTIAL_UNOBSERVABLE` | 1 |
| `ANSWER_GENERATION_FAILURE` | 3 |
| `RETRIEVED_BUT_LOW_RANK` (secondary signal) | 6 |
| `AMBIGUOUS_CASE` (evaluated release) | 0 |
| `DATASET_CASE_ISSUE` (evaluated release) | 0 |

The three real misses are all `FULL` representable cases. The six context
drops had exact ranked Gold ranks 6, 7, 8, 11, 14, or 20. The three answer
generation failures had all required evidence in final context but failed the
existing exact answer assessment; they are not retrieval failures. The single
partial case is the historical flagged case and is not counted as a miss.

### Per-case attribution and ranked Gold ranks

Legacy and Enhanced are identical for every row. Rank vectors are ordered by
required evidence group; `—` means no exact provenance match in that stage.

| Case ID | Task type | Representability | Raw ranks | Ranked ranks | Final ranks | Primary attribution |
|---|---|---|---|---|---|---|
| `case-09a8ceb2fd234fa792053c48363f488b` | single_document_retrieval | FULL | — | — | — | REAL_RETRIEVAL_MISS |
| `case-0dd707b2ed894a959706d58dda84625d` | long_distance | FULL | 8 | 8 | — | FINAL_CONTEXT_DROP |
| `case-37308a726ef441d08f085367ac2a6c70` | table_lookup | FULL | 2,2 | 2,2 | 2,2 | RETRIEVAL_SUCCESS |
| `case-6f4c41dbfd8649c1a42f789b82204736` | version_or_authority_relation | PARTIAL_UNOBSERVABLE | — | — | — | PARTIAL_UNOBSERVABLE |
| `case-6f8984c0b5d8431d9c591dc7a8e8bf0a` | cross_section | FULL | 1,1 | 1,1 | 1,1 | RETRIEVAL_SUCCESS |
| `case-874745d934d24e3c85e6d2acf7d17fec` | table_lookup | FULL | 7,7 | 7,7 | —,— | FINAL_CONTEXT_DROP |
| `case-99c5a254df1a4b73a29a098368acf527` | table_comparison | FULL | 6,6,6 | 6,6,6 | —,—,— | FINAL_CONTEXT_DROP |
| `case-a68460e6f98542e7be69f243d234c3a6` | single_document_retrieval | FULL | 20 | 20 | — | FINAL_CONTEXT_DROP |
| `case-b72d79202f5b41de9b345fa75c1375a9` | long_distance | FULL | 1 | 1 | 1 | RETRIEVAL_SUCCESS |
| `case-bcfdc5a86d53445297cff3aed59e05fc` | single_block_retrieval | FULL | 5 | 5 | 5 | ANSWER_GENERATION_FAILURE |
| `case-c191d27a84ca42a684a72f2ea84fe0a3` | single_block_retrieval | FULL | 11 | 11 | — | FINAL_CONTEXT_DROP |
| `case-cc787fe6dab24d0d958270c977b76f3d` | multi_hop | FULL | 3,3 | 3,3 | 3,3 | RETRIEVAL_SUCCESS |
| `case-ccd246a577734bb1986e1b43c1fce62a` | table_lookup | FULL | 2,2,2 | 2,2,2 | 2,2,2 | ANSWER_GENERATION_FAILURE |
| `case-db0c0c9312414a1584a8c4d6df0a83ec` | table_comparison | FULL | 2,2,2 | 2,2,2 | 2,2,2 | ANSWER_GENERATION_FAILURE |
| `case-decc05076bc84b95acbdea784dbdb4f9` | long_distance | FULL | 14 | 14 | — | FINAL_CONTEXT_DROP |
| `case-e59e310bde1e456fa047ff1d997b7581` | negative_abstention | FULL | 4 | 4 | 4 | RETRIEVAL_SUCCESS |
| `case-e81b1553b4d64bbfbd872f95fab83dad` | single_document_retrieval | FULL | — | — | — | REAL_RETRIEVAL_MISS |
| `case-e95211e1e6d24d74b40ecdf9533a82fa` | single_block_retrieval | FULL | — | — | — | REAL_RETRIEVAL_MISS |
| `case-e9a763b99ca5407294c57158d995bbbb` | single_block_retrieval | FULL | 1 | 1 | 1 | RETRIEVAL_SUCCESS |
| `case-f5d5c8e7ec554295b34aa010a6947d4b` | version_authority | FULL | 1,1 | 1,1 | 1,1 | RETRIEVAL_SUCCESS |

### Task-type observations

| Task type | Cases | Success | Real miss | Final drop | Answer failure | Partial |
|---|---:|---:|---:|---:|---:|---:|
| single_block_retrieval | 4 | 1 | 1 | 1 | 1 | 0 |
| single_document_retrieval | 3 | 0 | 2 | 1 | 0 | 0 |
| cross_section_relation | 1 | 1 | 0 | 0 | 0 | 0 |
| multi_hop | 1 | 1 | 0 | 0 | 0 | 0 |
| table_lookup | 3 | 1 | 0 | 1 | 1 | 0 |
| table_comparison | 2 | 0 | 0 | 1 | 1 | 0 |
| long_distance | 3 | 1 | 0 | 2 | 0 | 0 |
| version_authority_relation | 1 | 1 | 0 | 0 | 0 | 0 |
| version_or_authority_relation | 1 | 0 | 0 | 0 | 0 | 1 |
| negative_abstention | 1 | 1 | 0 | 0 | 0 | 0 |

The single multi-hop case was retrieved at rank 3 for both required groups.
The negative/abstention case was retrieved at rank 4 and is therefore useful
for answerability diagnostics, but one case is not a quality estimate for
negative handling. Long-distance cases show the clearest ranking/context
pressure: one succeeds at rank 1 while two land outside the final top five.

## 7. Gold and evidence quality findings

- The representability gate successfully separates the historical partial case
  from true misses; it prevents the report from calling an unobservable locator
  a retrieval failure.
- Gold locators are exact canonical locators and all released `FULL` cases
  round-trip through the LightRAG provenance map. No answer substring or fuzzy
  inference was used.
- Three cases show exact evidence in final context but an answer-generation
  failure under the existing scorer. This is a real generation/answer-format
  signal, not a reason to weaken Gold.
- Fourteen answer metrics remain `needs_review` by contract. They must not be
  converted into automatic passes or failures merely to increase coverage.
- The excluded historical negative candidate demonstrates that a source-grounded
  case can still fail Bundle representability at export time; this is a dataset
  authoring issue, not a retrieval miss.

## 8. Legacy versus Enhanced

There is no measurable difference in this 20-case run:

- raw/ranked/final-context ranks are identical for all 20 cases;
- Recall@1/@3/@5 and MRR are identical;
- answer metrics and observed-subset coverage are identical;
- no ranking-stage delta is observed.

This does not prove the implementations are globally equivalent. It only says
that this controlled document, case selection, seed, and one repetition do not
separate them.

## 9. Current bottleneck diagnosis

For the 19 `FULL` cases, the largest observed failure bucket is final-context
selection pressure: six cases retrieve the Gold provenance but rank it 6–20,
outside `final_context_k=5`. Raw and ranked stages are identical, so there is
no evidence of a separate ranked-stage drop in this run. Three additional
`FULL` cases are true retrieval misses, and three are answer-generation
failures despite complete final evidence. One case is representation-limited.

**Current ordering of concern:**

1. ranking/context selection (six low-rank cases dropped by the top-five
   context cut);
2. retrieval coverage (three exact provenance misses);
3. answer generation/format compliance (three failures with evidence present);
4. dataset representation (one flagged case, explicitly isolated).

The data therefore supports a targeted RAG investigation of candidate ranking
and final-context selection before broad dataset expansion. It does not support
a claim that Enhanced is better than Legacy.

## 10. Tests and repository changes

- Authoring/representability regression suite: **11 passed**.
- Both completed run artifact verifications: **valid**.
- Legacy/Enhanced comparison: `compatible: true`, no global incompatibility
  reasons, `may_declare_winner: false`.
- No changes were made to `rag-eval-adapters` or `LightRAG` in this phase.
- The new Platform changes add manual source-frozen targets, representability
  profile registration/gating, export selection, and regression coverage only;
  Evaluation Core and scorer semantics are unchanged.

## 11. Decision and next step

**BYOD Diagnostic Expansion: PASS (LightRAG track).** The 20-case release is
reviewed, representability-labeled, reproducible, and sufficient to expose a
ranking/context-selection signal. RAG-Anything canonical remains **not run**
because the host denied loopback worker creation; it is an explicit remaining
environment blocker and not a score.

Do not expand to 48/96 cases yet. The next step should be a narrowly scoped
LightRAG ranking/context-selection diagnostic using this frozen Bundle, while
preserving Gold and scorer contracts. After that, rerun the same Bundle in an
environment that permits the RAG-Anything worker to establish its independent
canonical diagnostic baseline.
