# Run / Artifact 2.0

- Status: implemented as the Phase 6 compatibility path
- Write authority: Run / Orchestration
- Evaluation authority: the persisted Phase 5 result
- Read authority: immutable Artifact 2.0 files
- Legacy authority during Phase 6: `RAGResult`, CaseResult, and Artifact 1.2 remain unchanged

## Owned boundary

Phase 6 introduces one RAG-neutral orchestration boundary:

```text
BenchmarkResolver
  -> AdapterSession
  -> TraceValidator
  -> EvaluationEngine
  -> ArtifactWriter
```

`BenchmarkResolver` resolves Platform-owned question, answer, and Gold records.
Only the RAG-neutral `RAGQuery` crosses into `AdapterSession`; Gold is never an
Adapter input. `AdapterSession` invokes the already-prepared Adapter once and
adds the same end-to-end latency observation used by the legacy executor.

`TraceValidator` validates the additive Wire 2.0 envelope, Adapter/runtime/case
identities, contract digests, and any declared Wire 1.0 shadow comparison. A
missing envelope is `unobserved`; malformed data or a failed identity/shadow
check is `corrupted`. It never repairs, guesses, or changes the legacy result.

`EvaluationEngine` persists either the exact Phase 5 Unified Evaluation result
or a proof-gated `UNOBSERVABLE` result whose formal metrics are unavailable.
Therefore an answer-only or uninstrumented Adapter can still produce a truthful
Artifact 2.0; the absence of a trace does not become a retrieval failure.

`ArtifactWriter` publishes only after all case executions are available. During
Phase 6 this path is additive: the legacy executor still writes Artifact 1.2 and
uses its existing scorer, while formal-release runs with a deterministic
evaluation profile also receive an Artifact 2.0 directory.

## Persisted layout

```text
artifact-v2/
  artifact.json
  case-index.json
  summary.json
  cases/
    rep-0001-<case-id>.json
```

`artifact.json` pins:

- immutable Dataset Release, Bundle, case-selection, Benchmark Snapshot, and
  Canonical source identities;
- every distinct RAG runtime profile and Adapter observation profile found in
  the validated traces;
- every case/repetition file and its file digest;
- the persisted summary and case-index paths;
- the checksum graph, run timestamps, and manifest self-digest.

Each case file contains the complete Benchmark case snapshot, validated
`AdapterRunResultV2` and `UnifiedTrace` when available, metric values and
statuses, metric descriptors, localization, pipeline deltas, proof-gated
failure attribution, answer/evidence judgments, execution error state, and a
case self-digest. Unknown observation is represented explicitly rather than by
omitting the case.

The lightweight `case-index.json` and aggregate `summary.json` are materialized
at publication time. A reader returns those stored views; it does not call a
RAG runtime, provenance mapper, or scorer.

## Identity and integrity

Artifact publication fails closed at each boundary:

1. Benchmark source identities must match the source digests in the immutable
   Bundle projection.
2. The Benchmark Snapshot digest is rebuilt from the unique persisted case
   snapshots, independent of repetitions.
3. An observed case must carry a validated Adapter result whose digest, trace
   digest, case identity, runtime identity, and observation identity agree.
4. An unobserved/unsupported/failed/corrupted case cannot carry observed
   metrics, localization, or observed judgments, and its failure attribution
   must be `UNOBSERVABLE`.
5. Every case, summary, and index file has a SHA-256 node. Summary and index
   nodes depend on every case node; the graph is acyclic and self-digested.
6. The manifest has a separate self-digest over its identities and checksum
   graph.
7. Verification revalidates every model and digest, reconstructs the Benchmark
   and profile identities, and compares the persisted summary/index with the
   persisted case facts.

Publication uses a run-local staging directory followed by an atomic rename.
Repeating publication with byte-identical content is idempotent. A different
Artifact at the same destination is rejected, so a completed Run is never
silently reinterpreted.

## Metric-driven leaderboard eligibility

Leaderboard admission is calculated exclusively from persisted metric facts.
For every case and repetition, all formal core metric IDs must be `observed`,
and each metric ID must have one identical descriptor digest across the Run.
The descriptor includes its explicit cutoff, candidate cutoff, ranked cutoff,
context budget, scorer identity, version, and source digest.

Neither Adapter name nor global stage completeness participates in admission.
A verified Top-5 may therefore be eligible for the `@1`, `@3`, `@5`, and
`MRR@5` metrics, while a complete stage with insufficient provenance remains
ineligible. The eligibility decision and its reasons are persisted in
`summary.json`; later readers do not recompute it with the current scorer.

## Artifact 1.2 compatibility

Artifact 1.2 keeps its existing paths and meaning. Phase 6 adds read-only
`RunStore` accessors for Artifact 2.0 but does not modify the Artifact 1.2
reader, case model, replay contract, or historical files. When Artifact 2.0 is
published, the legacy manifest receives only an additive pointer, and its
existing checksum inventory also pins the new directory.

Runs without a formal release pin or without a deterministic evaluation
profile continue to produce only Artifact 1.2. Pre-segmented and Benchmark
contract execution branches remain compatibility behavior until the Phase 8
native cutover; they are not promoted to new formal routes by this phase.

## Phase boundary

Phase 6 deliberately does not:

- change Run creation APIs or WebUI rendering;
- remove `evaluation_corpus` or pre-segmented execution;
- make Artifact 2.0 the product read path;
- rescore historical artifacts;
- implement derivative re-scoring or human-review artifacts.

Those changes remain assigned to Phases 7 and 8.
