# Frozen 20-case LightRAG Ranking / Context Robustness

**Status:** PASS — the best Gold-blind conservative strategy improves the frozen benchmark while eliminating the observed Segment MaxSim regressions. It is an experimental result, not a production-default change.

## Scope and reproducibility

This phase reuses the frozen 20-case Bundle, the captured candidate traces, the Legacy source run, the canonical provenance map, and the existing Platform evaluator. It does not modify Platform, Adapter, Dataset, Gold, scorer, metric definitions, provenance semantics, or `final_context_k=5`. Answer generation is disabled.

| Item | Value |
| --- | --- |
| Bundle | `d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e` |
| Source run | `4f9d2df532604bccbad7efdcebb8dd10` |
| Candidate pools | frozen BGE-M3 raw `k=20` and `k=50`; `k=50` prefix-20 was previously verified identical per case |
| Final context | fixed `k=5` |
| Local rerank model | BGE-M3 (`bge-m3:latest`), no LLM listwise reranker |
| Result artifact digest | `7bce52632f9f1cf770f41128014f078c3cbb72d6813ea1cfa4990b2203a06c32` |
| Private transition-audit digest | `a0d9186200892fb23dd73e182b874c4dc93507e14860cf91c03a6593ef63d10b` |

The detailed audit includes the natural-language query, every candidate's baseline and variant rank, runtime ID, structural/content features, Gold-matched runtime chunks, top-five transitions, promotions, and displacements. It remains a local private artifact because it derives from the private document; it is not committed with document text.

## Mechanism audit

Segment MaxSim rescued five `k=20` cases because a local window carries a materially stronger query match than the whole chunk. The table uses only post-hoc identification of the Gold candidate; these values were not available to any reranker.

| Case | Gold baseline → Segment rank | Whole similarity | Segment MaxSim | Locality gain | Segment concentration |
| --- | ---: | ---: | ---: | ---: |
| `case-874…fec` | 7 → 1 | 0.620 | 0.719 | 0.099 | 0.160 |
| `case-99c…527` | 6 → 5 | 0.569 | 0.613 | 0.044 | 0.071 |
| `case-a684…3a6` | 20 → 1 | 0.588 | 0.703 | 0.115 | 0.126 |
| `case-c191…0a3` | 11 → 3 | 0.516 | 0.562 | 0.046 | 0.067 |
| `case-decc…4f9` | 14 → 2 | 0.602 | 0.686 | 0.083 | 0.089 |

Across those five Gold candidates, mean locality gain is **0.077** and mean segment concentration is **0.102**. For the two `k=20` Segment MaxSim regressions, the already-correct Gold chunks were at baseline rank 4–5, with mean locality gain **-0.009** and mean concentration **0.052**. The pointwise MaxSim ranker instead promoted multiple local peaks at once, pushing the baseline Gold out of the fixed five.

| Case | Baseline Gold rank → Segment rank | Segment promoted baseline ranks | Mechanism |
| --- | ---: | --- | --- |
| `case-bcfd…5fc` | 5 → 13 | 13, 10, 19, 8 | Four local peaks displaced a low-concentration, whole-chunk-supported baseline answer chunk. |
| `case-e59e…581` | 4 → 6 | 6, 20 | Two promotions displaced rank 4; the second was a deep-tail local peak. |
| `case-ccd…62a` (new only at k=50) | 2 → 6 | 36, 8 | Extra depth supplied a rank-36 local peak and created the third regression. |

The available execution trace contains no heading path for all 1,400 evaluated candidates (400 at `k=20`, 1,000 at `k=50`); every role is therefore `body`. Summary/conclusion/TOC and duplicate/parallel-section features are not observable in this index representation. The present data consequently do **not** establish parallel sections as the main remaining failure mode; that needs a future context-organization/evidence-pack representation with reliable structural metadata.

## Conservative Gold-blind policy

The winning policy begins from the frozen baseline top five. It ranks outside candidates by Segment MaxSim and permits a replacement only when the candidate exceeds the currently weakest selected Segment MaxSim by at least **0.02**.

- **Confidence-gated:** at most one replacement; candidates deeper than baseline rank 20 cannot replace context.
- **Conservative Segment:** at most two replacements; a second replacement must have baseline rank at most 14, and every candidate deeper than rank 20 is blocked.
- **Baseline + Segment fusion:** 0.70 normalized baseline retrieval score + 0.30 normalized Segment MaxSim.

These are deterministic, configuration-controlled, and strictly Gold-blind. The displacement cap and baseline-rank prior are uncertainty fallbacks: if local evidence is insufficiently decisive, baseline context remains intact.

## Full frozen 20-case matrix

`Coverage` is required-evidence-group recall at the candidate cutoff. Rescue/regression labels compare complete Context Recall@5 with the same-cutoff baseline.

| candidate_k | Strategy | Coverage | MRR | R@1 | R@3 | R@5 | Rescue | Preserved | Regression | Rescue:Regression |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 20 | Baseline | 0.80 | 0.347 | 0.20 | 0.40 | 0.50 | 0 | 10 | 0 | n/a |
| 20 | Segment MaxSim | 0.80 | 0.446 | 0.30 | 0.55 | 0.65 | 5 | 8 | 2 | 2.5 |
| 20 | Structure-aware | 0.80 | 0.437 | 0.30 | 0.50 | 0.60 | 5 | 7 | 3 | 1.67 |
| 20 | Baseline + Segment fusion | 0.80 | 0.395 | 0.25 | 0.45 | 0.55 | 1 | 10 | 0 | ∞ |
| 20 | Confidence-gated | 0.80 | 0.425 | 0.30 | 0.45 | 0.65 | 3 | 10 | 0 | ∞ |
| 20 | **Conservative Segment** | **0.80** | **0.459** | **0.30** | **0.55** | **0.75** | **5** | **10** | **0** | **∞** |
| 50 | Baseline | 0.90 | 0.350 | 0.20 | 0.40 | 0.50 | 0 | 10 | 0 | n/a |
| 50 | Segment MaxSim | 0.90 | 0.453 | 0.30 | 0.55 | 0.60 | 5 | 7 | 3 | 1.67 |
| 50 | Structure-aware | 0.90 | 0.446 | 0.30 | 0.50 | 0.60 | 5 | 7 | 3 | 1.67 |
| 50 | Baseline + Segment fusion | 0.90 | 0.401 | 0.25 | 0.45 | 0.55 | 1 | 10 | 0 | ∞ |
| 50 | Confidence-gated | 0.90 | 0.429 | 0.30 | 0.45 | 0.65 | 3 | 10 | 0 | ∞ |
| 50 | **Conservative Segment** | **0.90** | **0.462** | **0.30** | **0.55** | **0.75** | **5** | **10** | **0** | **∞** |

Conservative Segment is the best tested strategy. Relative to ordinary Segment MaxSim it keeps all five rescues and removes both `k=20` regressions and all three `k=50` regressions. It improves R@5 by +0.10 over Segment MaxSim at `k=20` and +0.15 at `k=50`.

## Case-level transition summary

For the winning strategy, both candidate cutoffs have the same high-level transition: 5 rescues, 10 preserved-correct cases, 0 regressions, and 5 unchanged failures. The private audit contains the full 20-row candidate-rank matrix; the meaningful changes are:

| Segment outcome | Conservative outcome | Cases |
| --- | --- | --- |
| rescue | rescue | `874…`, `99c…`, `a684…`, `c191…`, `decc…` |
| regression | preserved correct | `bcfd…`, `e59e…`; plus `ccd…` at k=50 |
| unchanged failure | unchanged failure | `0dd…`, `09a8…`, `6f4…`, `e81…`, `e952…` |
| preserved correct | preserved correct | remaining 10 cases |

## Deep-pool and retrieval-track cases

| Case | Raw Gold rank at k=50 | Segment rank | Conservative rank | Enters top-5? | Interpretation |
| --- | ---: | ---: | ---: | --- | --- |
| `case-09a8…88b` | 21 | 8 | 21 | No | Segment partially improves it, but the conservative deep-tail gate retains baseline; no natural rescue. |
| `case-e81b…dad` | 46 | 13 | 46 | No | Same conclusion; a deep local peak is not sufficiently safe to displace baseline context. |
| `case-e952…2fa` | absent | absent | absent | No | True retrieval-track case; reranking cannot repair a missing candidate. |

At `k=50`, coverage increases from 0.80 to 0.90, but the best R@5 remains 0.75. Enlarging the pool alone therefore contributes no final-context gain under the safe policy.

## Oracle gap and next decision

The frozen-pool Oracle is R@5=`0.80`; Conservative Segment reaches `0.75`, leaving **0.05**. The remaining candidate-present ranking/context gap is `case-0dd…`, which is present but not naturally promoted by any tested policy. The other unchanged failures are the deep-pool cases above, the documented partial/unobservable provenance case, and the true retrieval-track miss.

This is sufficient evidence to stop iterating on pointwise semantic reranking for this frozen benchmark. The next milestone should be **context organization / evidence-pack research** with a structural representation that exposes headings and parallel sections, while retaining `case-e952…` on the retrieval track. The present parameter values were chosen during an exploratory audit of this same frozen benchmark; without a held-out bundle they must not become the production default.

## Verification

- New harness unit suite: `6 passed`.
- The full robustness matrix completed across 20 cases × 2 candidate pools × 6 strategies.
- No answer generation, Platform code, Adapter code, Bundle, Gold, scorer, metric, or production ranking default was changed.
