# RAG Evaluation Platform

`rag_eval_platform` is a system-neutral evaluation service. It owns dataset
bundles, evaluation semantics, immutable run artifacts, job state, comparison,
and reports. It deliberately has no dependency on LightRAG or RAG-Anything.

Artifact Contract **1.2** and Wire Protocol **1.0** are frozen. A formal run
requires verified model artifact identities: display names and mutable tags such
as `latest` are resolver inputs, never benchmark identities. See
[Artifact Contract 1.2](docs/ARTIFACT_CONTRACT_1_2.md) and the
[Wire Protocol Contract](CONTRACT.md).

Phase 8 Golden Smoke real-model validation passed; its model lock, accepted
runs, checksums, and independent AI review are recorded in
[the Phase 8 validation report](docs/PHASE_8_REAL_MODEL_VALIDATION_REPORT.md).
Future formal benchmark work additionally requires the sealed public/Gold role
boundary in the [Blind Benchmark Protocol](docs/BLIND_BENCHMARK_PROTOCOL.md),
case-clustered (not case×seed) analysis, and a frozen latency lifecycle.

RAG systems run behind isolated adapter workers. The platform communicates
with workers through frozen Wire Protocol 1.0 over authenticated loopback HTTP/JSON.

The initial storage backend is an atomic file store rooted at
`RAG_EVAL_HOME` (default: `~/.rag_eval_platform`). Legacy LightRAG evaluation
directories are never scanned.

## Productization Track

The WebUI-first Productization Track is independent of the research Phase
sequence. It adds versioned System Profiles, Dataset/System resources,
Evaluation Drafts, and Local/Docker execution selection without changing the
frozen research contracts. See [Productization Track](docs/PRODUCTIZATION_TRACK.md).
Current runtime acceptance evidence and explicitly remaining interactive checks
are recorded in the [Productization Acceptance Report](docs/PRODUCTIZATION_ACCEPTANCE_REPORT.md).

Ordinary users start at **Overview → New Evaluation**. Basic mode exposes only
LightRAG and RAG-Anything. The Platform expands profile defaults into a full,
canonical `ExperimentSpec` before invoking the same `RunExecutor` used by CLI.
The old CLI and Advanced ExperimentSpec entrypoints remain supported.

## Start the local system

From the Platform checkout, start the local API and the sibling standalone
WebUI together:

```bash
./scripts/start-local.sh
```

The API binds to `127.0.0.1:8765` and the WebUI to `127.0.0.1:4178`. The
script starts no legacy `memory_eval` service and no persistent Adapter Worker:
Workers are isolated and created by the Platform for each evaluation run.

## First evaluation (WebUI)

Open `http://127.0.0.1:4178`, then follow the three actions on **Overview**:

1. **Upload dataset** — upload one validated Dataset Bundle ZIP, or create a
   small TXT/Markdown Bundle and seal it after selecting Gold evidence.
2. **Add RAG system** — select LightRAG or RAG-Anything, save it, and use
   **Test connection** to confirm the local model runtime is reachable.
3. **New evaluation** — select the sealed Dataset and tested RAG system,
   choose the required model and embedding identities (and an optional query
   mode), review the generated configuration, then run it.

The generated run remains a normal immutable artifact. Its Detail page shows
integrity verification, Cases, evidence flow, metrics, and failure assessment.
Use **Compare** only when the runs are compatible for the selected tier. See
[Quick Start](docs/QUICK_START.md) for a visual-free checklist and common
first-run remedies.

## Advanced CLI / CI

CLI commands, hand-authored `ExperimentSpec`, legacy SystemRegistration, and
Replay remain available for advanced users and CI; they are not required for
the normal WebUI workflow.

Override the storage home or ports without changing the script:

```bash
RAG_EVAL_HOME=/path/to/eval-home \
RAG_EVAL_API_PORT=8765 \
RAG_EVAL_WEBUI_PORT=4178 \
./scripts/start-local.sh
```

The startup script expects an installed Platform environment (`.venv/bin/rag-eval` or
`rag-eval` on `PATH`) and an installed sibling WebUI (`npm ci` in
`../rag-eval-webui`). Use `RAG_EVAL_WEBUI_DIR` when that checkout is elsewhere.

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
