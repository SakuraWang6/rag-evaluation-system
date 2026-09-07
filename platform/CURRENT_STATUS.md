# Current Status — Project Consolidation Baseline

**Date:** 2026-08-28  
**Scope:** Platform / WebUI / Adapters / LightRAG repository consolidation  
**Status:** baseline整理完成；evaluation contracts frozen

## 唯一主线

```text
Private DOCX
  → Platform Authoring workspace
  → canonical source + structure-first targets
  → separate question / answer / evidence resolution
  → reviewer-approved Dataset Bundle
  → isolated Adapter Worker
  → RAG Evaluation and immutable run artifacts
```

Authoring is the current entry point for private documents. It retains the
source DOCX, deterministic canonical representation, candidate versions,
review decisions, diagnostics, and export history. The normal evaluation view
is `canonical-text`; `native-docx` is a diagnostic view for parser/document-
understanding capability only.

`memory_data_service` and synthetic generation are legacy/diagnostic assets.
They are not part of Authoring, are not scanned by the Platform, and must not
be treated as the current private-document workflow.

## Repository responsibilities

| Repository | Responsibility | Current boundary |
| --- | --- | --- |
| `rag-eval-platform` | Authoring, Dataset Bundle, evaluation semantics, run artifacts, jobs, reports | system-neutral; no LightRAG/RAG-Anything import |
| `rag-eval-webui` | Basic/Advanced product UI and Authoring review screens | calls Platform APIs; does not own dataset or run semantics |
| `rag-eval-adapters` | isolated Worker implementations | execution-only; no Authoring or Gold ownership |
| `LightRAG` | RAG runtime and migration boundary | no current `/eval` product path; legacy evaluation labs are retained for audit |

Artifact Contract 1.2 and Wire Protocol 1.0 remain unchanged. This baseline
does not change ranking, dataset generation, Gold semantics, metric semantics,
comparison rules, or adapter contracts.

## Completed capabilities

- Private DOCX ingestion with OOXML safety checks and immutable source digest.
- Deterministic, chunker-independent canonicalization with structural IDs,
  source witnesses, representation status, and diagnostics.
- Structure-first target discovery and candidate generation/resolution with
  provider, prompt, seed, method, and source-object provenance.
- Separate answer/evidence resolution and review gates for leakage,
  representability, locators, tables, negatives, and source/evidence digest
  consistency.
- Immutable review actions, approved-case views, export diagnostics, and
  Dataset Bundle registration.
- WebUI flow from document upload through review and export/register, with a
  small manual TXT/Markdown editor retained as fallback.
- Isolated per-repetition adapter Workers, immutable run artifacts, replay,
  verification, and comparison using the existing frozen contracts.
- LightRAG evaluation cutover: legacy evaluation directories are not scanned
  by the current Platform startup or normal product workflow.

## Current 20-case diagnostic dataset

The current release is the 20-case canonical-text diagnostic release recorded
in [the diagnostic expansion report](docs/BENCHMARK_DIAGNOSTIC_EXPANSION_REPORT.md).
The private source and run workspace remain local product data; no private DOCX
or Gold contents are committed here.

- Bundle ID: `d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e`
- Release composition: original 4 cases + 16 additional cases = 20.
- Authoring workspace: 24 candidate records, 27 immutable reviews; 21
  approved and 3 rejected. One approved historical-table case was excluded
  from the release because its locator was invalid.
- Representability: 19 `FULL/PASS`; 1 `PARTIAL_UNOBSERVABLE/FLAG`. The partial
  case is not counted as an ordinary retrieval miss.
- Task distribution: single-block retrieval 4; single-document retrieval 3;
  cross-section relation 1; multi-hop 1; table lookup 3; table comparison 2;
  long-distance retrieval 3; version-authority relation 1;
  version-or-authority relation 1; negative abstention 1.

## Current runs and metrics

| System / profile | Run ID | Status |
| --- | --- | --- |
| LightRAG Legacy | `4f9d2df532604bccbad7efdcebb8dd10` | 20/20 cases; artifacts valid |
| LightRAG Enhanced / structured | `c8738013e8324fdbb52d4bb2a17a5bda` | 20/20 cases; artifacts valid |
| RAG-Anything | `0abea04d4e354ed6a6dbaacc31a186c9` | not executed; loopback bind permission failure |

Both completed LightRAG runs reported the same retrieval-level results:

| Metric | Result |
| --- | ---: |
| Raw Recall@1 / @3 / @5 | 0.20 / 0.40 / 0.50 |
| Ranked Recall@1 / @3 / @5 | 0.20 / 0.40 / 0.50 |
| Final-context Recall@1 / @3 / @5 | 0.20 / 0.40 / 0.50 |
| Raw / ranked MRR | 0.3465097403 |
| Context-selection loss @1 / @3 / @5 | 0 / 0 / 0 |
| Answer accuracy, observed subset | 0.1667 (1/6) |
| Groundedness, observed subset | 0.1667 (1/6) |
| Unsupported-answer rate, observed subset | 0.8333 (5/6) |

Answer metrics use a denominator of 6 because 14 cases remain
`needs_review`. These numbers are diagnostic evidence, not a leaderboard or a
claim that one profile is superior. Failure attribution was: retrieval success
7, real retrieval miss 3, final-context drop 6, partial/unobservable 1, answer
generation failure 3. Six cases were retrieved but low-ranked (ranks 6, 7, 8,
11, 14, and 20); no ranking-stage delta was observed in this run.

## Known limitations

- The current release is a small diagnostic baseline, not a public benchmark
  or a statistically general performance claim.
- The private DOCX, approved Gold contents, and run artifacts are local and
  intentionally excluded from Git.
- One case is partial/unobservable and 14 answer evaluations need review.
- Native-DOCX ingestion is diagnostic only; canonical-text is the normal fair
  evaluation view.
- The RAG-Anything attempt could not start because the host denied the
  loopback bind (`PermissionError: [Errno 1] Operation not permitted`), so no
  RAG-Anything metric is available for this release.
- Optional LightRAG backends are not all installed in the default test
  environment; the full upstream test collection therefore needs an
  environment with those dependencies.
- Manual TXT/Markdown creation, local-path registration, legacy/custom
  adapters, and direct ExperimentSpec/CLI entry points remain supported as
  advanced or diagnostic paths, not as the primary private-document flow.

## Current bottleneck

The frozen diagnostic evidence points to final-context selection and retrieval
coverage before answer quality: six cases dropped from retrieved evidence into
the final context, three were real retrieval misses, and the observed answer
subset had a high unsupported-answer rate. This is recorded for the next phase;
no ranking or context-selection optimization is performed during
consolidation.

## Next stage

After this repository baseline is accepted, the next milestone is a narrowly
scoped diagnostic of retrieval ranking/context selection on this same frozen
20-case release, followed by an independently permitted RAG-Anything rerun.
That work must preserve the current Gold, metrics, adapter, Artifact Contract,
and Wire Protocol contracts. No new cases or dataset expansion is part of the
consolidation stage.

For the complete file-by-file consolidation record, see
[PROJECT_CONSOLIDATION_REPORT.md](PROJECT_CONSOLIDATION_REPORT.md).
