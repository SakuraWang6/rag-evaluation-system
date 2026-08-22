# RAG Evaluation Platform

`rag_eval_platform` is a system-neutral evaluation service. It owns dataset
bundles, evaluation semantics, immutable run artifacts, job state, comparison,
and reports. It deliberately has no dependency on LightRAG or RAG-Anything.

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
