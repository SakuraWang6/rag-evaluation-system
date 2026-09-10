# Current Native v2 Architecture

## Supported chain

```text
Original DOCX
  -> immutable Benchmark Release
  -> ResolvedRunPlanV2
  -> RAG-native parser / chunker / index
  -> candidate / ranking / final context / answer
  -> AdapterRunResultV2 / UnifiedTrace
  -> Unified Evaluation
  -> Artifact 2.0
  -> Platform API
  -> WebUI
```

This is the only supported evaluation route. A Benchmark is not regenerated
for each RAG, and the Platform does not replace native chunks with Canonical
segments.

## Ownership

| Boundary | Authority | Must not own |
| --- | --- | --- |
| Canonical Benchmark | Original DOCX identity, Canonical Catalog, questions, Gold answers, Gold evidence and immutable Release | RAG chunks, Adapter capability or metric availability |
| Observation / Adapter | Native ingest/query invocation, runtime identities, stage observations, provenance and transformation receipts | Gold selection, scoring or failure attribution |
| Unified Evaluation | Gold aggregation, canonical extent coverage, metric availability and proof-gated failure taxonomy | RAG-specific parsing or presentation policy |
| Run / Orchestration | Admission, immutable plan, Worker lifecycle, trace validation, Artifact publication and Run state | A duplicate cache of metrics, trace, Gold or leaderboard status |
| Platform API / WebUI | Verified persisted views and user interaction | Request-time provenance, scoring or failure inference |

The authoritative implementation owners are:

- `rag_eval.authoring`, `rag_eval.canonical` and `rag_eval.datasets` for the
  Benchmark layer;
- `rag_eval.contracts.native`, `rag_eval.contracts.observation` and each
  Adapter package for Worker observation;
- `rag_eval.evaluation.unified` for scoring semantics;
- `rag_eval.runs` and `rag_eval.execution` for plans, records and Artifact 2.0;
- `rag_eval.runs.views`, `rag_eval.api` and `webui/src` for persisted
  presentation.

## Benchmark publication and admission

Authoring starts from DOCX bytes. The Canonicalizer produces a deterministic,
content-addressed Catalog and Conformance report. Reviewers approve questions,
answers and Gold evidence against that Catalog. A formal Release pins the
source, Canonical, case, Gold and validation identities.

Public Run creation resolves the Release before queueing. Admission requires:

- one and only one Original DOCX projection;
- verified Release, source and Canonical digests;
- a resolved System/Adapter/Worker profile;
- complete Platform-owned query configuration;
- evaluation profile and all formal metric descriptors;
- case selection, seed, repetitions and resource limits.

The immutable result is `ResolvedRunPlanV2`. Missing values, explicit nulls,
invalid cutoff ordering, modified Release material or a non-native execution
declaration fail before a RunRecord is created. A native depth below five is
legal; metrics requiring an unproved Top-5 become `UNAVAILABLE`.

## Offline publication package

Bundle 3 is retained only as a private, content-addressed offline package for
transporting and verifying an already frozen Release, Canonical snapshot and
Gold. It has no runtime manifest, runtime question export or runtime loader.
Admission, execution, public schemas and Run summaries do not import or refer
to Bundle 3; a formal Run always resolves the immutable Release directly.

## Worker execution

The Platform invokes an isolated Worker through one direct protocol:

```text
prepare(original_docx, resolved_config) -> PreparedSystemV2
query(prepared_system, NativeQueryV2)    -> AdapterRunResultV2
```

`prepare` performs native ingestion and returns source, runtime, observation
and ingestion-receipt identities. `query` executes the native RAG request once.
The query contains no Gold or scorer policy.

An Adapter may instrument its own runtime to observe catalog, candidate,
ranked and context stages. Instrumentation must be read-only with respect to
the native result. Unsupported or failed observation remains explicit and
cannot be converted into an empty retrieval result.

## Evaluation and publication

The execution authority is atomic:

```text
BenchmarkResolver
  -> AdapterSession
  -> TraceValidator
  -> EvaluationEngine
  -> Artifact staging
  -> checksum and manifest verification
  -> atomic publish
  -> RunRecordV2 completed
```

A Worker or trace error can be persisted as a typed Artifact case with
unavailable metrics when a complete valid Artifact can still be constructed.
Artifact construction or verification failure makes the Run fail.

`RunRecordV2` contains only orchestration identity, state, timestamps, error
and the verified Artifact reference. Artifact 2.0 is the only source for Gold,
trace, localization, metrics, judgments, failure attribution and leaderboard
eligibility.

## Read authority

API summary, case, report, comparison and review paths open the RunRecord,
verify its plan and Artifact binding, then read Artifact 2.0. The WebUI renders
the same persisted presentation schema. Neither layer imports an Adapter,
provenance mapper or scorer.

Missing Run IDs return `404`. A present but invalid Artifact is `corrupted` and
its result content is withheld. No alternate response format or dynamic
projection is attempted.

## Extension rule

A new RAG integration implements the Direct Worker 2.0 lifecycle, emits an
honest `AdapterRunResultV2`, passes the shared Adapter TCK and adds its Worker
profile/lifecycle test. It does not add a Benchmark type, scorer branch,
Artifact variant, result endpoint or WebUI component.

## Executable boundaries

The required CI workflow proves:

- exact Platform collection and Native v2 invariants on Python 3.11.15;
- shared and implementation-specific Adapter conformance;
- checked-in Schema 2.0 equality;
- package build and clean installation;
- model-free LightRAG and RAG-Anything Worker lifecycle;
- persisted-only WebUI tests and production build on Node 24.12.0.

These are the maintained local/CI baselines, not an implicit compatibility
promise for additional Python or Node releases.

The [architecture index](README.md) links each contract that defines these
boundaries.
