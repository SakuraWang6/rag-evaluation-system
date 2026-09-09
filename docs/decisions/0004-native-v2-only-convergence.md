# ADR 0004: Native v2-Only Runtime and Artifact Authority

- Status: Accepted
- Date: 2026-09-09
- Scope: Final runtime, persistence, API-presentation, and historical-format policy
- Baseline revision: `71428cd`
- Supersedes: ADR 0002's Wire 1 / Artifact 1.2 stability commitment and
  ADR 0003's compatibility-reader and retirement-window decisions

## Context

ADR 0003 established the correct Native DOCX, Unified Trace, Unified
Evaluation, and Artifact 2.0 architecture. Its phased migration deliberately
retained Wire 1, Artifact 1.2 readers, pre-segmented execution oracles, and
historical replay/rescore while the v2 path matured.

The post-migration audit at revision `0fc494f` found that this compatibility
surface still participates in normal execution and presentation. A native case
can be evaluated by both scorers, a run can complete without Artifact 2.0, and
some API, CLI, report, comparison, and review paths still treat legacy files as
an authority. Keeping those formats supported would preserve the dual system
that the migration is intended to remove.

This decision authorizes an intentionally breaking convergence. It defines the
only supported post-migration contracts before production code changes begin.

## Decision

### One supported evaluation chain

The only supported evaluation chain is:

```text
Original DOCX
  -> immutable Benchmark Release
  -> RAG-native parse / chunk / index / retrieval / ranking / context / answer
  -> Adapter Unified Trace
  -> Unified Evaluation
  -> Artifact 2.0
  -> Platform API
  -> WebUI
```

Canonical Benchmark remains the sole owner of source coordinates, questions,
Gold answers, and Gold evidence. Adapter observability affects metric and
leaderboard availability; it never filters or reshapes Benchmark Gold.

There is no supported runtime or read path for `canonical_segments`,
`benchmark_segments`, or any other pre-segmented corpus mode after convergence.

### HTTP URI stability is not response compatibility

`/api/v1` URI remains stable. Backward compatibility with legacy Artifact 1.x
response variants is intentionally discontinued.

The Artifact presentation payload advances to schema version `2.0` and exposes
only Artifact 2.0 projections. Legacy response alternatives such as
`legacy_case`, `legacy_unavailable`, and an Artifact 1.x contract-version union
are removed. No `/api/v2`, content negotiation, tombstone, redirect, or hidden
legacy fallback is introduced. A removed historical run is reported as not
found.

### Admission and metric availability are separate

Every public run must resolve an immutable Benchmark Release containing exactly
one original DOCX and a complete evaluation plan before it can be queued. The
Platform query configuration, not Adapter defaults, owns evaluation cutoffs.
Explicit nulls, missing required values, and invalid configurations fail at
admission.

A retrieval or ranking depth below five is still a legal execution. Metrics
whose required prefix cannot be proved are `UNAVAILABLE`, and the run is not
leaderboard-eligible for those metrics. Adapter limitations never make a Gold
object ineligible and never create another Benchmark.

### RunRecord is orchestration metadata only

An immutable resolved-plan snapshot records Benchmark, document, runtime,
observation, query, evaluation-descriptor, seed, repetition, and resource-limit
identities. `RunRecordV2` references that snapshot and may contain only:

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

It must reject Gold, traces, metrics, scores, failure attribution, provenance,
case summaries, and leaderboard eligibility. Those facts exist only in
Artifact 2.0. A run may become `COMPLETED` only after its Artifact 2.0 has been
atomically published and fully verified.

### Worker 2.0 is direct and exclusive

The formal Worker evaluation surface is:

```text
prepare(original_docx, resolved_config) -> PreparedSystemV2
query(prepared_system, NativeQueryV2)    -> AdapterRunResultV2
```

Preparation performs native ingestion and binds source, runtime, observation,
and ingestion-receipt identities. Query returns `AdapterRunResultV2` directly,
including its `UnifiedTrace` and optional typed telemetry.

There is no Wire negotiation, v1/v2 dual mode, compatibility normalization, or
`RAGResult` envelope in the final contract. LightRAG, RAG-Anything, the fake
Adapter, and Platform switch as one release unit.

### Historical formats have no support commitment

The following formats and facilities are retired from product code, public
exports, schemas, APIs, CLI commands, WebUI, and the maintained test path:

```text
Wire 1
Artifact 1.x
pre-segmented runs
legacy run metadata
historical replay and rescore
legacy readers and projections
```

A historical run may be retained only when its complete Artifact 2.0 verifies
and all required `RunRecordV2` and resolved-plan fields can be reconstructed
deterministically without defaults, guessing, rescoring, or Artifact mutation.
All other historical run records and references are deleted through a separate
destructive gate driven by a content-addressed inventory. Unknown references
are never guessed through and block final readiness.

The one-shot inventory or migration implementation is operational tooling, not
a retained compatibility reader or a supported product interface.

### Artifact authority changes atomically

The executor, Artifact publication, RunRecord completion, API, CLI, report,
comparison, review, and WebUI read paths switch in one accepted change. No
committed state may route readers exclusively to Artifact 2.0 while successful
runs are still allowed to omit it.

## Executable conformance boundary

The required workflow runs the exact Platform collection and shared Adapter
conformance gates. The maintained tests protect:

- immutable-release projection of exactly one original DOCX;
- rejection of new pre-segmented public runs;
- one native query per case without Gold entering the Worker request;
- Platform-owned Gold and RAG-neutral Unified Evaluation;
- Top-K availability, explicit MRR cutoff, and proof-gated attribution;
- Artifact 2.0 integrity, persisted-only reads, and diagnostic corruption;
- `UNAVAILABLE` rather than guessed zero or failure;
- WebUI and core scoring independence from RAG names and corpus modes.

The CI baseline pins exact collection plus named critical nodes, and rejects
unlisted test removal. Adapter suites validate Direct Worker 2.0 and the shared
observation TCK. Schema export, package installation, model-free Worker
lifecycle and Node 22 WebUI checks are also required.

## Consequences

- Existing clients that consume legacy `/api/v1` response alternatives must be
  updated; the unchanged URI does not imply payload compatibility.
- Old run IDs disappear unless their valid Artifact 2.0 can be migrated
  losslessly. Removed IDs return `404` with no format-specific response.
- Artifact 2.0 is the only evaluation and presentation authority. RunRecordV2
  cannot become a cache of evaluation facts.
- A RAG may complete a valid but leaderboard-ineligible run when observation is
  insufficient for the formal metric cutoffs.
- Git history and ADRs preserve design history; executable compatibility code
  and historical runtime data are not retained for that purpose.
- Each migration phase remains independently tested, committed, accepted, and
  reversible until the separately approved destructive data phase.

## Non-goals

- Changing Canonical object identities or Gold eligibility rules.
- Standardizing native parser, chunker, retrieval, or transformation behavior.
- Converting unavailable evidence into zero or a deterministic failure.
- Providing an Artifact 1.x conversion service or a Wire 1 compatibility SDK.
- Deleting runtime data during this decision and characterization phase.
