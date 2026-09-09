# Evaluation Architecture v2

ADR 0004 is the current decision authority for the Native v2-only convergence.
ADR 0003 remains the architectural foundation and migration history, but its
Wire 1, Artifact 1.2, compatibility-reader, and retirement-window decisions
are superseded. These documents separate the audited current state, historical
explanation, destination, and executable phase plan.

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
| [`ARTIFACT_V2_PRESENTATION.md`](ARTIFACT_V2_PRESENTATION.md) | Phase 7 persisted-only Platform API and descriptor-driven WebUI |
| [`NATIVE_FORMAL_CUTOVER.md`](NATIVE_FORMAL_CUTOVER.md) | Phase 8 native-DOCX public admission and compatibility window |
| [`../decisions/0004-native-v2-only-convergence.md`](../decisions/0004-native-v2-only-convergence.md) | Current accepted convergence and compatibility decision |
| [`../decisions/0003-native-document-evaluation-v2.md`](../decisions/0003-native-document-evaluation-v2.md) | Architectural foundation and migration-era decision history |

The current convergence characterization gate is:

```bash
uv run --project platform --extra test --frozen --python 3.12.12 \
  pytest -q -m native_v2_characterization platform/tests
```

The earlier `tests/fixtures/native_evaluation_v2/behavior-baseline.json` and
its Adapter test remain migration-era evidence until the test-retirement phase;
they do not define the supported post-convergence contract.
