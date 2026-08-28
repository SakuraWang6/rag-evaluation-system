# Project Consolidation Report

**Date:** 2026-08-28  
**Scope:** Platform / WebUI / Adapters / LightRAG  
**Decision:** retain the current implementation and diagnostic evidence as the
maintainable baseline; freeze contracts and dataset semantics during cleanup.

## Invariants

This phase did not optimize ranking, generate cases, expand the dataset, or
modify Gold, metric, comparison, run-executor, or adapter contracts. Artifact
Contract 1.2 and Wire Protocol 1.0 remain unchanged. Private source and Gold
contents remain outside Git.

## Retained

- Platform Authoring service, canonicalizer, storage, workflow gates, export,
  registration, Dataset Bundle, evaluation, run artifacts, replay, comparison,
  Worker isolation, and product APIs.
- WebUI Basic/Advanced workflows, including document Authoring and review;
  manual TXT/Markdown creation remains as a small fallback.
- Adapter Worker implementations for LightRAG Legacy, LightRAG Enhanced, and
  RAG-Anything, including their protocol tests and runtime fixtures.
- LightRAG runtime and the migration boundary that prevents the current
  Platform from scanning historical evaluation directories.
- The 20-case diagnostic report and its immutable run IDs/metrics in
  `docs/BENCHMARK_DIAGNOSTIC_EXPANSION_REPORT.md`.
- Historical reports with reproducibility value; they were moved under
  `docs/archive/` rather than deleted.

## Archived

Platform reports and completed planning documents were moved out of the main
design surface:

- `docs/archive/reports/BYOD-10_REPORT.md`
- `docs/archive/reports/CANONICAL_PROVENANCE_BRIDGE_REPORT.md`
- `docs/archive/reports/EXECUTION_RELIABILITY_REPORT.md`
- `docs/archive/reports/PHASE_8_REAL_MODEL_VALIDATION_REPORT.md`
- `docs/archive/reports/PRODUCTIZATION_ACCEPTANCE_REPORT.md`
- `docs/archive/reports/PRIVATE_DOCUMENT_BENCHMARK_CURRENT_GAP.md`
- `docs/archive/plans/PRIVATE_DOCUMENT_BENCHMARK_IMPLEMENTATION_PLAN.md`

The WebUI’s historical `PHASE_A_UI_REPORT.md` and `UI_AUDIT.md` are retained
under `docs/archive/reports/`. LightRAG migration records remain in their
existing `docs/migration/` location because they document the repository split
and are still operationally relevant.

## Removed

No tracked source, fixture, configuration, or reproducibility report was
removed. No untracked private document, generated dataset, run artifact, or
workspace output was deleted. Duplicate/obsolete candidates were resolved by
documentation classification and links rather than irreversible deletion.

## Deprecated and legacy boundaries

- `memory_data_service` is a legacy synthetic/private-data generator and
  diagnostic service. It is not the current Authoring implementation.
- `memory_eval_tests` and `memory_recall_lab` are retained historical
  evaluation/retrieval labs for audit and reproducibility; they are not the
  current Platform evaluation path.
- LightRAG’s historical `lightrag/api/eval_index.py`,
  `eval_comparison.py`, and `lightrag/evaluation/` compatibility surfaces are
  retained only for historical tests/tools. The current Platform does not
  discover or invoke them.
- Legacy/custom adapter registration, direct CLI/ExperimentSpec authoring,
  local-path Bundle registration, and the manual TXT/Markdown editor remain
  supported advanced/diagnostic paths.
- `native-docx` is a parser/document-understanding diagnostic view; normal
  cross-system evaluation uses `canonical-text`.

## README changes

- Platform README now leads with `Private DOCX → Authoring → reviewer-approved
  Dataset → RAG Evaluation`, identifies the 20-case status file, and moves
  historical Phase 8/product-acceptance references to the archive.
- Platform Quick Start and Productization Track now describe DOCX Authoring as
  the primary workflow and TXT/Markdown as a manual diagnostic fallback.
- Adapter README files now state that adapters are execution-only and do not
  own Authoring, Gold, ranking, or dataset semantics.
- WebUI README now describes document upload, review, export/register, and the
  diagnostic-only native-DOCX boundary.
- LightRAG README files now identify the independent Platform mainline and
  explicitly classify `memory_data_service`, synthetic generation, and old
  evaluation/retrieval labs as legacy/diagnostic.

## Code cleanup audit

The audit covered Platform `src/rag_eval`, Adapter Worker implementations and
fixtures, WebUI source/API semantics, and LightRAG evaluation/migration paths.

- No production module was deleted: Platform Authoring/Dataset/Evaluation/
  Worker/Storage modules are imported by APIs, CLIs, or tests; adapter
  implementations and provenance helpers are exercised by tests; WebUI
  components and API clients are referenced by routes/tests.
- No duplicate schema/helper with a demonstrably unused owner was found.
  Contract and provenance helpers have active consumers and tests.
- No temporary debug block, unsafe print-based instrumentation, or unused
  configuration/fixture was proven removable without changing behavior.
- The legacy paths were documented and marked rather than removed because
  historical tests and reproducibility evidence still depend on them.
- No ranking logic, dataset generator, Gold content, metric, or adapter
  contract was edited.

## Tests and verification

Baseline and post-cleanup runs were kept contract-focused:

| Area | Result |
| --- | --- |
| Platform Python tests | 89 passed, 3 skipped (dependency-complete existing environment) |
| Adapter Python tests | 29 passed, 4 skipped |
| WebUI external `bun test` | 5 passed |
| WebUI nested submodule `bun test` | 92 passed |
| LightRAG targeted legacy/migration tests | 88 passed |
| LightRAG full `pytest -q` | collection blocked by missing optional backends; 15 tests skipped, 26 dependency import errors |

The LightRAG full-suite collection attempted optional imports such as Neo4j,
Qdrant, Milvus, Redis, OpenSearch, Anthropic, and aioboto3. The environment
could not install missing packages under restricted network access. This is an
environment limitation, not a cleanup regression. The final report must retain
this limitation until a dependency-complete environment runs the full suite.

Repository-level checks also include `git diff --check`, README/link review,
and verification that the four repositories and their nested submodule
checkouts have no uncommitted changes after the consolidation commits.

## Remaining technical debt

- Install and record a dependency-complete LightRAG test environment, then
  rerun the full upstream suite.
- Re-run RAG-Anything in an environment that permits its loopback worker bind.
- Decide, in a later explicitly scoped phase, whether the six final-context
  drops justify ranking/context-selection work; do not change it in this phase.
- Resolve the one partial/unobservable case through representation-specific
  review before treating the release as a general benchmark.
- Keep the 20-case diagnostic workspace and model/runtime identity snapshots
  available for reproducibility without committing private content.
- Continue reducing legacy surface only after import/test evidence shows that a
  path no longer serves historical reproduction.

## Next milestone

Freeze this consolidation baseline, then run the diagnostic ranking/context
selection study on the unchanged 20-case Bundle and separately retry
RAG-Anything. The milestone is complete only when the existing contracts and
Gold remain byte-for-byte compatible and the results are reported separately
from this cleanup baseline.
