# Phase 8 independent 24-case review

## Disposition: PASS — no Gold change

Reviewer role: `codex-independent-reviewer`
Reviewed at: `2026-08-24T14:07:57Z`

This is an independently scoped Codex review pass assigned by the user. It is
not presented as a human or external third-party attestation.

## Review boundary and method

The reviewer did not use
`golden-smoke-author-reconciliation.csv` as review evidence. The review instead
performed the following checks directly against sealed or raw artifacts:

1. Recomputed SHA-256 values for all 11 files controlled by the sealed
   `golden-smoke-v1/checksums.json`; all matched bundle
   `bbfbb1d2761b714a595ae072f786bd527fdff5c85ba7c57c40b6d8087072ba1e`.
2. Ran `rag-eval verify-run <run_id>` for each of the three accepted real runs;
   all reported `valid: true` with no missing, unexpected, or mismatched files.
3. For every one of the 24 case artifacts in each accepted run, compared the
   answer to the sealed Gold answer and evidence requirement, then inspected the
   raw final context when it was exposed.

The original case artifacts, platform metrics, and failure labels are preserved.
The review records a semantic/evidence assessment beside them; it does not
modify those outputs.

## 24-case result

| System | Answer assessment | Evidence assessment |
| --- | --- | --- |
| LightRAG Legacy | 24/24 correct, including 4 source-specific abstentions | Required Gold document present in final context for 24/24 |
| LightRAG Enhanced | 24/24 correct, including 4 source-specific abstentions | Required Gold document present in final context for 24/24 |
| RAG-Anything | 20/24 factual answers incorrect; 4/24 generic abstentions acceptable only at answer level | Retrieval, ranked retrieval, and final context unavailable for 24/24 |

For Legacy and Enhanced, the retained `needs_review`, `retrieval_missing`,
`generation_failure`, and `unsupported_answer` labels therefore describe a
limitation or mismatch in the deterministic scoring/failure assessment for the
affected case. They are not silently removed or converted into a different
platform score.

For RAG-Anything, its universal `[no-context]` response is not treated as a
correct factual answer. The four Gold `abstain` rows are marked acceptable only
as generic answer-level abstentions: absent an observable evidence stage, the
review cannot assert source-specific grounding.

Each individual determination, retained failure semantics, and no-change
disposition is in `golden-smoke-independent-review-checklist.csv`.

## Gate conclusion

All 24 independent-review rows are complete and no row proposes a Gold change.
The Phase 8 independent-review gate passes. This conclusion does not authorize
a leaderboard or a cross-system winner: the frozen comparison result remains
`compatible=false` and `may_declare_winner=false`.
