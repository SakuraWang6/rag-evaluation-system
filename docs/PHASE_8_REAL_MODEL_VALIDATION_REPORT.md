# Phase 8 real-model Golden Smoke validation

## Final gate: BLOCKED

The real-model execution gate completed successfully, but Phase 8 closure is
**BLOCKED**. The remaining blocker is the required independent reviewer gate:
the 24-case author reconciliation is complete, while the independent-review
checklist is intentionally still blank. No author review is presented as an
independent review, and no Gold answer or evidence was changed.

## Immutable runtime

- Bundle: `golden-smoke-v1`, 24 cases, bundle ID
  `bbfbb1d2761b714a595ae072f786bd527fdff5c85ba7c57c40b6d8087072ba1e`.
- Formal model-lock digest:
  `sha256:b586b442f79bc0f22e8353bda35afd06f2cc6921aa0931fdc713705b4a67f96c`.
- Generation model: `Qwen3 4B Instruct`, requested `qwen3:4b-instruct`,
  resolved `sha256:0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.
- Embedding model: `BGE-M3`, requested `bge-m3:latest`, resolved
  `sha256:7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`.
- Both identities were resolved from local Ollama `GET /api/tags` and frozen
  with `verified=true`; tags are display/request references, not the immutable
  execution identity. Evidence: `examples/golden-smoke-v1-execution/model-identity-verification.json`.
- The cache/latency, analysis, and comparison artifacts are frozen under
  `examples/golden-smoke-v1-execution/frozen/`. Each run uses one fresh worker,
  one fresh run-scoped index, one warmup, disabled answer/query/LLM caches, and
  concurrency one.

## Accepted real runs

| System | Run ID | Cases | Query latency mean (s) | Artifact verification |
| --- | --- | ---: | ---: | --- |
| LightRAG Legacy | `4ba57bbe7a0e4ae09676dd2d73ccb93f` | 24/24 | 4.318419 | valid |
| LightRAG Enhanced | `b49509a9fd5e454faaac9813cc2162ec` | 24/24 | 4.962717 | valid |
| RAG-Anything | `11bb5d01955e453d89e04787252331d3` | 24/24 | 0.165860 | valid |

All accepted runs have zero timeout, zero system error, and zero cancelled case.
Their source-only inputs, raw case results, answer, metrics, failure assessment,
latency, manifest, Markdown report, reproducibility record, and checksums are
retained in `examples/golden-smoke-v1-execution/platform-home/runs/`. LightRAG
runs retain raw retrieval, ranked retrieval, and final context. RAG-Anything
retains these stages as `null`, matching its declared public-API capability;
they are not inferred or scored as zero.

## Result interpretation and reconciliation

The platform’s deterministic scorer is intentionally conservative. For both
LightRAG runs, 16 expanded natural-language answers were `needs_review`; four
natural-language abstentions were scored as observed zero with
`generation_failure` / `unsupported_answer`. The author’s case-by-case review
found all 24 LightRAG answers semantically correct and source-traceable. This is
a scorer/failure-label discrepancy, not a Gold change or a rewritten run result.

RAG-Anything returned `[no-context]` abstentions for all 24 questions. The
author reconciled the 20 factual questions as incorrect. The four negative-case
generic abstentions remain explicitly pending independent judgment because they
do not cite the source-specific absence. Full record:
`examples/golden-smoke-v1-execution/golden-smoke-author-reconciliation.csv`.

The independent reviewer must complete all 24 rows in
`examples/golden-smoke-v1-execution/golden-smoke-independent-review-checklist.csv`.
If a Gold change is proposed, it must be a separate, reviewed amendment; none is
silently applied to this sealed run.

## Metrics and comparison semantics

- LightRAG Legacy/Enhanced: raw, ranked, and context recall@1 are each
  `16/24 = 0.666667`; answer metric coverage is `8/24`, with 16 cases retained
  as `needs_review` rather than coerced to zero.
- RAG-Anything: answer accuracy is observed `0/24`; answer groundedness,
  unsupported-answer rate, and retrieval/context metrics are `unavailable`, not
  zero, because its public API exposes no matching evidence stages.
- A task-comparable comparison request across all three accepted runs returned
  `compatible=false` and `may_declare_winner=false`. No leaderboard or winner
  claim is made.

API checks returned HTTP 200 for the real run, cases, summary, artifact
verification, and report endpoints. The WebUI semantics suite passed 3 tests
and its production build passed; it distinguishes observed zero, unavailable,
error, and needs-review values. Evidence:
`examples/golden-smoke-v1-execution/semantic-verification.json`.

## Audit trail

`examples/golden-smoke-v1-execution/run-checksums.json` records the three
accepted manifests, per-run index artifact digests, and canonical checksum-map
hashes. Earlier preflight attempts were retained but are not accepted runs:

- `07b442145d8a4e6cbf7304a75b9345f3`: pre-normalization Ollama bare digest
  rejection; no case executed.
- `84fcb579227745ac85193d53c03a9d1c`: ambiguous short-name resolver selected
  `qwen3:8b`; immutable lock rejected it; no case executed.
- `4df57c23e7a9480382f9efed357c01e0`: RAG-Anything MinerU parser prerequisite
  missing; no case executed.

The two resolver defects were corrected in adapter commits `30c669d8` and
`90766fe2`; the Worker virtual-environment symlink preservation was corrected
in Platform commit `d56e6872`. These fixes made the formal lock enforceable and
are not a relaxation of the lock.
