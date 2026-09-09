# Evaluation Architecture

This directory contains the maintained Native v2 architecture. The current
policy authority is [ADR 0004](../decisions/0004-native-v2-only-convergence.md);
[ADR 0003](../decisions/0003-native-document-evaluation-v2.md) defines the
four-layer foundation but its migration and compatibility decisions are
superseded.

## Current authority

| Document | Owner and scope |
| --- | --- |
| [Current Architecture](CURRENT_ARCHITECTURE.md) | End-to-end control flow, ownership and supported boundaries |
| [Canonical Conformance](CANONICAL_CONFORMANCE.md) | Canonical identity, Gold eligibility and evidence coordinates |
| [Unified Observation Contract](UNIFIED_OBSERVATION_CONTRACT.md) | Direct Worker 2.0, stage observation, provenance and transformations |
| [Unified Evaluation](UNIFIED_EVALUATION_V2.md) | Evidence aggregation, metric availability and proof-gated failure attribution |
| [Run / Artifact 2.0](RUN_ARTIFACT_V2.md) | Resolved plan, orchestration state, publication and integrity |
| [Artifact Presentation](ARTIFACT_V2_PRESENTATION.md) | Persisted-only result API, report, comparison, review and WebUI |
| [LightRAG Observation](LIGHTRAG_NATIVE_OBSERVATION.md) | LightRAG-specific runtime observation proof boundary |
| [RAG-Anything Observation](RAG_ANYTHING_NATIVE_OBSERVATION.md) | RAG-Anything-specific runtime observation proof boundary |

Benchmark authoring and operation are documented separately in the
[Benchmark Authoring Guide](../../platform/docs/BENCHMARK_AUTHORING.md) and
[Quick Start](../../platform/docs/QUICK_START.md).

## Supported contracts

The supported execution and presentation contracts are Direct Worker 2.0,
`ResolvedRunPlanV2`, `RunRecordV2`, `UnifiedTrace`, Unified Evaluation,
Artifact 2.0 and presentation schema 2.0. There is no runtime negotiation,
pre-segmented execution, historical replay/rescore, or reader for earlier Run
formats.

Version numbers used by active Canonical, research or Benchmark data models
are owned by those contracts. A `1.x` internal version is not evidence of an
earlier Worker or Run format.

## Decision record

- [ADR 0001](../decisions/0001-runtime-evidence-cardinality-and-prompt-trace.md)
  records runtime evidence cardinality and prompt-trace ownership.
- [ADR 0002](../decisions/0002-architecture-change-envelope.md) records the
  original change envelope; its format-stability clauses are superseded.
- [ADR 0003](../decisions/0003-native-document-evaluation-v2.md) establishes
  Native DOCX, Platform-owned Gold and proof-driven evaluation.
- [ADR 0004](../decisions/0004-native-v2-only-convergence.md) makes Native v2
  the exclusive runtime, persistence and presentation authority.

Git history preserves completed plans, audits and phase reports. They are not
maintained as a second documentation authority.
