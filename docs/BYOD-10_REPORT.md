# BYOD-10 Report — Private DOCX End-to-End Acceptance

**Result: BLOCKED**

This report records a real, local-only acceptance run performed on 2026-08-27.
The source DOCX, canonical text, questions, Gold values, candidate records, parser
output, run workspaces, and artifacts remain under the local product home.  They
are not stored in this repository.  This document intentionally contains no
private document body, question wording, answer value, or evidence quote.

## Scope and controls

- One private DOCX was ingested into an isolated local `RAG_EVAL_HOME`.
- The source was rendered locally for review (105 pages) and was never committed
  or sent to a remote provider.
- Authoring used the existing `/api/v1/authoring/*` workflow, which is the
  backend used by the Authoring product flow.  Browser automation was not
  available in this environment, so the API path—not a synthetic substitute—was
  used for this acceptance.
- Local Ollama was the only generation provider.  The model-generated candidate
  recorded `qwen3:4b-instruct`, its seed, and a prompt digest.
- Evaluation Core, metrics, comparison rules, and adapters were not modified.
- `canonical-text` and `native-docx` were exported as separate immutable
  Bundles.  The native view was never included in a winner comparison.

## 1. DOCX analysis

The deterministic canonicalizer completed successfully.

| Item | Observed result |
|---|---:|
| Rendered pages | 105 |
| Canonical records | 8,241 |
| Sections | 100 |
| Body blocks | 718 |
| Tables / rows / cells | 84 / 979 / 5,143 |
| Figures / equations / references | 5 / 20 / 472 |
| Notes / embedded objects | 2 / 3 |
| Supported records | 2,587 |
| Partial records | 5,649 |
| Unsupported records | 5 |

OOXML inventory found 84 body tables (plus one nested table), 192 bookmarks,
17 body OMML equations, two inline drawings, three VML shapes, three OLE
objects, and footnote/endnote definitions.  Canonicalization produced 20
equation objects and five figure objects.  Page fields are supplementary only;
they were not used as Gold locators.

The partial/unsupported inventory was not silently promoted to evidence:

- 55 merged or irregular-table diagnostics;
- 375 other partial representations;
- 17 unresolved caption associations;
- one nested-table diagnostic and three unsupported-object diagnostics; and
- two unanchored notes.

This confirms that the rich source is being inventoried, but also exposes an
MVP gap: caption relationships are not yet sufficiently resolved to support
reviewed caption Gold, and the summary does not expose a distinct caption-record
count.  No table, figure, equation, note, VML, or OLE item was approved as Gold
in this run.

## 2. Target discovery and candidate review

Structure-first rule discovery produced 5,081 reviewable targets:

| Capability | Count |
|---|---:|
| Table lookup | 4,018 |
| Single-document retrieval | 700 |
| Cross-section relation | 235 |
| Plausible negative candidate | 84 |
| Version/authority relation | 14 |
| Figure/equation/embedded-object/note diagnostics | 30 |

3,422 targets were marked `partial_source_representation`; they were retained
as diagnostics, not candidates.  Local-model target enrichment did not produce
a persistable target result, so the stored discovery set is explicitly
rule-derived rather than being mislabelled as an LLM result.

Five question candidates were reviewed:

| Outcome | Count |
|---|---:|
| Manual candidates | 4 |
| Local-Ollama candidates | 1 |
| Accepted candidates / approved cases | 4 |
| Edited then accepted | 1 |
| Rejected | 1 |

The four approved cases each cite a supported body-block witness.  Their
automatic gates totalled 40 `PASS` results and four mandatory-human-review
`FLAG`s; none had a failed gate.  The reviewer independently checked the source,
answer representation, and canonical witness before approval.

The one local-model candidate was rejected.  Its independent answer/evidence
pass returned an invalid answer kind and a non-list dependency graph.  It was
not manually repaired into Gold.  This is an important positive result for the
separate question and answer/evidence contract: an invalid generated resolution
does not cross the approval boundary.

### Gold/evidence quality assessment

The accepted set is a valid smoke-level reviewed dataset, not a representative
RAG benchmark release:

- all four questions are answerable from one supported body block;
- there is no approved negative/abstention, multi-hop, table computation,
  figure, equation, caption, or long-context case;
- each approved evidence set has one required group and one observable witness;
- no evidence relies on page number, title, filename, object ID, partial object,
  or answer-substring matching.

The Gold standard was not relaxed to increase the case count.  The low approved
count is intentional.

## 3. Bundle export and registration

Both exports passed the existing Bundle loader under the formal validation
profile:

| View | Bundle ID | Cases | Policy |
|---|---|---:|---|
| canonical-text | `4045b77c905d…ae86b5c2` | 4 | Normal same-view evaluation |
| native-docx | `357616db6fd0…15026d3c` | 4 | RAG-Anything diagnostic only |

The views use the same reviewer-approved Question/Gold/Evidence definition.
Only the execution source changes.  Candidate and review records remain outside
the Dataset Store.

## 4. Evaluation results

All canonical experiments used the same four explicit case IDs, selection seed,
model lock, and formal cache/latency protocol.  The local model family was
Qwen3 4B Instruct plus BGE-M3.

| System/view | Run status | Result |
|---|---|---|
| LightRAG Legacy / canonical-text | Failed during ingestion | Same failure at canonical document chunk 2 of 58; no queries executed |
| LightRAG Enhanced / canonical-text | Failed during ingestion | Same failure at canonical document chunk 2 of 58; no queries executed |
| RAG-Anything / canonical-text | Completed | 4/4 cases completed; artifact verification passed |
| RAG-Anything / native-docx | Interrupted diagnostic | MinerU native parsing started, but produced no completed parser output/index within the bounded wait; job was cancelled and recovered as interrupted |

For both LightRAG profiles, the persisted error is the adapter/server ingestion
failure at `C[1/58]` / chunk 2 with an empty underlying chunk message.  This is
not a metric failure and is not attributable to a Gold relaxation or comparison
rule.

RAG-Anything canonical-text metrics:

| Metric | Result |
|---|---|
| Answer accuracy | 0.0 (0/4) |
| Answer groundedness | Unavailable (0/4 observable) |
| Raw/ranked/context recall | Unavailable (0/4 observable) |
| Unsupported-answer rate | Unavailable (0/4 observable) |
| Case execution | 4 completed; 0 timeout/system error/cancelled |
| Artifact verification | Valid; no missing, unexpected, or mismatched artifacts |

The RAG-Anything adapter declared and observed answer plus latency-breakdown
capability, but not raw retrieval, ranked retrieval, final context, object
provenance, prompt trace, or rerank trace.  The unavailable retrieval metrics
therefore reflect the adapter capability contract, not zero recall.  All four
generated answers were present but failed the existing exact answer scorer and
were labelled `needs_review` for failure attribution.

### Canonical versus native observation

The canonical view is the only completed end-to-end execution view.  Native
DOCX exercised a real MinerU process on the original document and stayed within
the intended diagnostic route, but it did not reach queryability before the
bounded cancellation.  There is no native accuracy claim and no cross-view
winner claim.

## 5. Comparison

The existing comparison validator was invoked for the completed canonical run.
It returned:

- `compatible: false`;
- `may_declare_winner: false`; and
- reason: **at least two runs are required**.

The two LightRAG canonical runs did not complete, so a three-system
task-comparable comparison cannot honestly be computed.  Native DOCX was
correctly excluded from the attempt.

Two earlier preflight-only jobs were also retained in local job history: one
was rejected for an incorrect explicit-case selection digest and one for a
worker-system-ID alias mismatch.  Both were corrected by creating new immutable
ExperimentSpecs; neither ingested the document or contributed metrics.

## 6. BYOD-10 decision

**BYOD-10: BLOCKED**

The authoring boundary, deterministic analysis, strict review, immutable export,
registration, Bundle validation, and one real canonical RAG-Anything execution
all work.  Full BYOD-10 acceptance is blocked because:

1. LightRAG Legacy and Enhanced cannot ingest this real canonical document,
   failing consistently at chunk 2/58 without an actionable underlying error.
2. The RAG-Anything native-DOCX parser has no progress/liveness completion
signal usable for a bounded 105-page diagnostic and does not promptly propagate
job cancellation.
3. Only one canonical system completed, so the existing comparison rules
   correctly prohibit a winner declaration.
4. Four supported single-block cases are deliberately insufficient evidence for
   a benchmark-quality release, even though they are valid reviewed cases.
5. Browser-level Authoring UI verification remains outstanding in this local
   environment; the same backend flow was exercised directly through its API.

## 7. Recommended next step

Prioritize **execution observability and liveness before expanding the dataset**:

1. reproduce the LightRAG chunk-2 ingestion failure with a redacted/minimal
   private fixture and preserve the underlying server/LLM exception in the
   artifact, without changing scoring or Gold;
2. add progress and cancellation checkpoints around RAG-Anything/MinerU native
   parsing so a document diagnostic has explicit parse-stage results; then
3. rerun the unchanged canonical Bundle through all three systems.  Only after
   two or more canonical runs complete should Compare be retried; only after
   that should the reviewed dataset grow into multi-hop, table, negative, and
   long-context benchmark cases.
