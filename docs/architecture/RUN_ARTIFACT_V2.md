# Run and Artifact 2.0

## Three authorities

Native v2 separates planning, orchestration and evaluation facts:

- `ResolvedRunPlanV2` is the immutable admission-time execution plan.
- `RunRecordV2` is orchestration metadata and mutable state history.
- Artifact 2.0 is the immutable evaluation and presentation authority.

No evaluation field is copied into `RunRecordV2`.

## ResolvedRunPlanV2

The content-addressed plan binds:

- Benchmark Release and Original DOCX identities;
- System, Adapter and Worker profile identities;
- resolved Adapter configuration digest;
- complete Platform-owned query configuration;
- evaluation profile and formal metric descriptors;
- case selection, seed and repetitions; and
- resource limits.

Explicit nulls, missing fields and invalid values fail before queueing.
Adapter defaults cannot supply evaluation cutoffs after admission.

## RunRecordV2

The strict record contains only:

```text
schema_version
run_id
experiment_id
resolved_plan_path
resolved_plan_digest
state
created_at
started_at
completed_at
execution_error
artifact_path
artifact_digest
```

`pending`, `running`, `failed` and `cancelled` records cannot claim an Artifact.
A `completed` record must reference an Artifact 2.0 that verifies and matches
the Run's plan, Benchmark, source, cases, descriptors and Adapter/runtime
identities.

## Atomic execution authority

```text
BenchmarkResolver
  -> AdapterSession
  -> TraceValidator
  -> EvaluationEngine
  -> Artifact staging
  -> checksum / manifest / plan verification
  -> atomic publish
  -> RunRecordV2 completed
```

Artifact publication failure leaves no completed Run. Byte-identical repeat
publication is idempotent; different bytes at the same destination are
rejected.

## Artifact layout

```text
artifact-v2/
  artifact.json
  case-index.json
  summary.json
  cases/
    rep-0001-<case-id>.json
```

The manifest pins Benchmark, source, runtime and observation identities, every
case file, the summary/index paths, timestamps, checksum graph and manifest
self-digest.

Each case persists its Benchmark snapshot, Adapter result and Unified Trace
when observed, evaluation metrics and descriptors, localization, pipeline
deltas, judgments, failure attribution, execution status and self-digest.
Unknown observation is explicit rather than represented by a missing case.

## Verification

The reader verifies:

1. every declared file and digest;
2. the acyclic checksum dependency graph;
3. every case, index, summary and manifest model;
4. Benchmark/source/profile identity reconstruction;
5. persisted summary and index equality with persisted case facts; and
6. exact binding to the referenced `ResolvedRunPlanV2` and `RunRecordV2`.

Artifact reads require no current scorer or live RAG runtime.

## Eligibility

Leaderboard eligibility is persisted from metric availability. Every case and
repetition must contain all formal core metrics as observed, and each metric ID
must have one identical descriptor digest across the Run. Rank positions after
the required cutoff need not be observed.

The [Artifact Presentation contract](ARTIFACT_V2_PRESENTATION.md) defines how
verified persisted data reaches API and WebUI consumers.
