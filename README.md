# RAG Evaluation Platform

`rag_eval_platform` is a system-neutral evaluation service. It owns dataset
bundles, evaluation semantics, immutable run artifacts, job state, comparison,
and reports. It deliberately has no dependency on LightRAG or RAG-Anything.

Artifact Contract **1.2** is under internal hardening while Wire Protocol stays
at **1.0**. A formal run requires verified model artifact identities: display
names and mutable tags such as `latest` are resolver inputs, never benchmark
identities. See [Artifact Contract 1.2](docs/ARTIFACT_CONTRACT_1_2.md).

Formal benchmark support is contract-ready but no benchmark result is implied
by this repository. Formal work additionally requires the sealed public/Gold
role boundary in the [Blind Benchmark Protocol](docs/BLIND_BENCHMARK_PROTOCOL.md),
case-clustered (not case×seed) analysis, and a frozen latency lifecycle.

RAG systems run behind isolated adapter workers. The platform communicates
with workers through frozen Wire Protocol 1.0 over authenticated loopback HTTP/JSON.

The initial storage backend is an atomic file store rooted at
`RAG_EVAL_HOME` (default: `~/.rag_eval_platform`). Legacy LightRAG evaluation
directories are never scanned.

Completed runs contain a frozen `experiment.json`, per-repetition case files,
`summary.json` with mean/standard deviation and execution-failure rate,
`report.md`, worker logs, dependency/environment snapshots, model and prompt
digests, index fingerprints, and SHA-256 checksums for every immutable artifact.

```bash
# Verify before reading or replaying a run
rag-eval --home /path/to/eval-home verify-run RUN_ID

# Re-run the exact stored ExperimentSpec through the registered system
rag-eval --home /path/to/eval-home replay RUN_ID --new-run-id NEW_RUN_ID
```

Every repetition starts a fresh Worker process and rebuilds a run-scoped index.
Seeds are derived deterministically from the ExperimentSpec base seed. Replay
refuses a run whose artifacts no longer match its manifest; strict comparison
also rejects scorer/model/config drift and, for same-system replay, dependency
or prompt drift.

When a latency protocol is supplied, the Platform records a seeded case-order
artifact, verifies that all answer/query/LLM caches are disabled as declared,
and runs its one fixed warmup query after ingestion but before timing cases.
Only Platform `end_to_end_query_latency` is a cross-system candidate; Adapter
native timings are diagnostics.
