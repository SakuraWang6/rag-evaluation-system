# Frozen 20-case LightRAG Ranking / Context Selection Experiment

**Status:** PASS — complete frozen-benchmark diagnostic; no production behavior was changed.

## Scope and guardrails

This is a full 20-case controlled ranking experiment over the frozen canonical bundle. It does not modify the Dataset Bundle, Gold evidence/answers, scorer, metric definition, Evaluation Core, Platform, or Adapter contract. It does not generate answers, so answer accuracy and groundedness are explicitly **not applicable** here.

The experiment is Gold-blind through candidate scoring and selection. The rerankers receive only the natural-language question plus already retrieved candidate content and generic document structure. Gold locators, reference answers, failure labels, and scorer output enter only after the top-five selection, when the existing Platform provenance matcher evaluates the result.

## Frozen inputs and execution checks

| Item | Value |
| --- | --- |
| Bundle | `d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e` |
| Canonical document digest | `65f03397ae45ae9e2cfa306c86ca1e3f89f408377f7a8f6bd3aada05d7a1c214` |
| Source Platform/LightRAG run | `4f9d2df532604bccbad7efdcebb8dd10` (Legacy) |
| Candidate trace digest | `90545901b8f27ff8867cc5e48e8d4429bdfab8306978c157a21fa8c6d6546882` |
| Result digest | `6e3ac3bb2ca51c9b97702d13d96c04b2a1ab8136f9d2d8d4da4e329d0de73f8b` |
| Query mode / final context | `naive` / fixed `final_context_k=5` |
| Retrieval | BGE-M3 (`bge-m3:latest`), no native reranker |
| Chunking | 1200 tokens, 100-token overlap, existing 58-chunk index |
| LLM / seed | `qwen3:4b-instruct`, temperature 0, seed `20260824`; no answer call made |

The captured `candidate_k=20` raw order exactly equals the frozen Legacy run for all 20 cases. The first 20 items of each `candidate_k=50` trace also exactly equal that case's `candidate_k=20` trace (20/20). Consequently, depth is the only retrieval-pool difference in this matrix.

## Gold-blind variants

- **Baseline:** frozen BGE-M3 vector order, then top five.
- **Segment MaxSim:** BGE-M3 cosine similarity between the question and the maximum of each candidate's three fixed 480-character windows. This directly counters long-chunk dilution.
- **Structure-aware:** `0.80 × Segment MaxSim + 0.20 × heading-path similarity`, with generic penalties for TOC, summary/conclusion-like sections, repeated heading paths, and excessive chunk length. Roles are derived from headings/text only; they are not manually assigned per question.

The local embedding request batch was reduced from 96 to 16 after the larger batch stalled in the local Ollama service. That is an execution-stability change only: it does not change the candidate set, scoring functions, weights, query, or `top-5` budget.

## Full 20-case result matrix

`Candidate coverage` is mean required-evidence-group recall at the candidate cutoff; `complete` is the number of cases with every required group represented. `Rescued`, `unchanged correct`, and `regressed` use complete Context Recall@5 relative to the baseline at the same cutoff.

| candidate_k | strategy | Candidate coverage / complete | MRR | Context R@1 | R@3 | R@5 | rescued | unchanged correct | regressed |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | Baseline BGE-M3 | 0.80 / 16 | 0.347 | 0.20 | 0.40 | **0.50** | 0 | 10 | 0 |
| 20 | Segment MaxSim | 0.80 / 16 | **0.446** | **0.30** | **0.55** | **0.65** | 5 | 8 | 2 |
| 20 | Structure-aware | 0.80 / 16 | 0.437 | 0.30 | 0.50 | 0.60 | 5 | 7 | 3 |
| 50 | Baseline BGE-M3 | 0.90 / 18 | 0.350 | 0.20 | 0.40 | 0.50 | 0 | 10 | 0 |
| 50 | Segment MaxSim | 0.90 / 18 | **0.453** | **0.30** | **0.55** | 0.60 | 5 | 7 | 3 |
| 50 | Structure-aware | 0.90 / 18 | 0.446 | 0.30 | 0.50 | 0.60 | 5 | 7 | 3 |

The best tested strategy is **`candidate_k=20 + Segment MaxSim`**. It improves Context Recall@5 from 0.50 to 0.65 (+0.15, a net three complete cases) and MRR from 0.347 to 0.446. It does not reach the fixed-pool Oracle bound of 0.80; the remaining 0.15 gap is material.

## Pool-depth versus ranking contribution

Increasing only the candidate pool from 20 to 50 raises candidate coverage from 0.80 (16/20 complete) to 0.90 (18/20 complete), but leaves baseline Context Recall@5 unchanged at 0.50. Thus depth restores candidate availability but, by itself, contributes **zero** top-five context improvement.

At `k=20`, Segment MaxSim provides the observed context benefit: five rescues offset two regressions for a net +3 complete cases. At `k=50`, the same reranker still rescues those five cases but incurs three regressions, so R@5 is only 0.60. The expanded pool introduces additional competing chunks without making a new case complete in the final five. Candidate-pool improvement and this pointwise reranker are therefore not additive.

## Retrieval-track checks

| Frozen case | k=20 | k=50 raw Gold rank | Best k=50 reranked Gold rank | Enters final top-5? | Classification |
| --- | --- | ---: | ---: | --- | --- |
| `case-09a8ceb2fd234fa792053c48363f488b` | absent | 21 | 7 (structure-aware) | No | candidate pool helps, but remains ranking/context problem at top-5 |
| `case-e81b1553b4d64bbfbd872f95fab83dad` | absent | 46 | 12 (structure-aware) | No | candidate pool helps, but remains ranking/context problem at top-5 |
| `case-e95211e1e6d24d74b40ecdf9533a82fa` | absent | absent | absent | No | **retrieval-track**; reranking cannot solve it |

The rank-21 and rank-46 cases are not recovered into `final_context_k=5` by either tested Gold-blind reranker. They are not final-context rescues and must not be presented as such. The k=50-still-absent case is a genuine retrieval-track issue.

## Structured-ranker outcome

The structure-aware variant executes and changes orders, but it does not outperform Segment MaxSim on the full benchmark. Its generic penalties and heading blend neither create a new rescue nor reduce regressions; at `k=20` it loses one additional baseline-correct case, and at `k=50` it ties Segment MaxSim on R@5. This is evidence that the current feature weights/role heuristics are not yet a robust structural solution for natural-language questions, not evidence of an Adapter/Profile defect.

## Decision

The result supports continuing **ranking/context organization research**, but not shipping this reranker or moving solely to retrieval work yet:

1. Segment MaxSim is the best reproducible Gold-blind signal and demonstrates that ranking is a real bottleneck.
2. Its regression rate (2/20 at the best setting) and remaining Oracle gap mean it is not stable enough for a production default.
3. Raising candidate depth to 50 increases coverage but does not improve final context under the current pointwise rankers; do not treat `top_k=50` as an optimization result.
4. The next experiment should improve context organization/ranking robustness — especially regression guards, duplicate/parallel-section handling, and the two newly available rank-21/rank-46 cases — while keeping `final_context_k=5`. Keep `case-e952...` on a separate retrieval track.

No answer-quality claim is made because no answers were generated in this retrieval-only experiment.

## Verification

- Platform suite in the evaluation environment: `89 passed, 3 skipped`.
- LightRAG focused regression suite (new harness, structured ranking, and evaluation cutover): `15 passed`.
- The checked-in Platform `.venv` currently lacks `lxml`, so its direct full-suite invocation stops at collection with `ModuleNotFoundError: lxml`. Re-running the identical suite in the configured `lightrag-memory-eval` environment (which supplied the experiment dependencies) passed as recorded above.
