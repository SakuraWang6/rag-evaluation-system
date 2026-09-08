# Evaluation Architecture v2

ADR 0003 is the decision authority for the Native DOCX migration. These
documents separate the audited current state, the historical explanation, the
remaining native gap, the destination, and the executable phase plan.

| Document | Role |
| --- | --- |
| [`CURRENT_ARCHITECTURE_AUDIT.md`](CURRENT_ARCHITECTURE_AUDIT.md) | Evidence-backed current implementation audit |
| [`UNIFIED_OBSERVATION_CONTRACT.md`](UNIFIED_OBSERVATION_CONTRACT.md) | Wire 2.0 observation, provenance, and transformation contract |
| [`MULTI_CORPUS_HISTORY.md`](MULTI_CORPUS_HISTORY.md) | Why the three corpus modes appeared and what each preserved |
| [`NATIVE_DOCUMENT_GAP_ANALYSIS.md`](NATIVE_DOCUMENT_GAP_ANALYSIS.md) | Remaining native provenance and observability gaps |
| [`TARGET_ARCHITECTURE.md`](TARGET_ARCHITECTURE.md) | Normative four-layer destination and semantic rules |
| [`MIGRATION_PLAN.md`](MIGRATION_PLAN.md) | Phase-by-phase implementation, gates, commits, and rollback |
| [`CANONICAL_CONFORMANCE.md`](CANONICAL_CONFORMANCE.md) | Phase 2 Snapshot identity and Platform-owned Gold admission |
| [`LIGHTRAG_NATIVE_OBSERVATION.md`](LIGHTRAG_NATIVE_OBSERVATION.md) | Phase 4 native runtime catalog, provenance receipts, and Wire 2.0 shadow |
| [`UNIFIED_EVALUATION_V2.md`](UNIFIED_EVALUATION_V2.md) | Phase 5 availability-driven extent scoring and proof-gated attribution |
| [`RUN_ARTIFACT_V2.md`](RUN_ARTIFACT_V2.md) | Phase 6 immutable Run artifact, checksum graph, and persisted-only eligibility |
| [`../decisions/0003-native-document-evaluation-v2.md`](../decisions/0003-native-document-evaluation-v2.md) | Accepted architecture decision |

The Phase 1 executable baseline is
`tests/fixtures/native_evaluation_v2/behavior-baseline.json`, guarded by
`tests/rag_eval_adapters/test_native_evaluation_v2_baseline.py`. It freezes
current behavior for migration comparison; it does not make the pre-segmented
modes part of the target architecture.
