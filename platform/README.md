# RAG Evaluation Platform

`rag_eval_platform` is a system-neutral evaluation service. It owns private
document authoring, reviewed dataset bundles, evaluation semantics, immutable
run artifacts, job state, comparison, and reports. It deliberately has no
dependency on LightRAG or RAG-Anything.

## Current baseline

The single supported product/research mainline is:

```text
Private DOCX → Authoring → immutable Benchmark Release
             → RAG-native Parser / Chunker / Index / Retrieval
             → Unified Trace → Unified Evaluation → Artifact 2.0
```

Authoring preserves the private source, canonical evidence, candidate history,
and review decisions before sealing a Benchmark Release. New formal runs
deterministically project that Release into one original-DOCX ingestion input
plus an adjacent, observer-only Canonical Catalog; they never replace the RAG's
native parser or chunker with Platform segments. The current diagnostic
release contains 20 cases; see
[CURRENT_STATUS.md](CURRENT_STATUS.md) for the frozen run IDs, metrics, and
known limitations.

Artifact Contract **1.2** and Wire Protocol **1.0** remain frozen compatibility
contracts. Unified observation uses Wire 2.0 and new formal runs persist
Artifact 2.0. A formal run requires verified model artifact identities:
display names and mutable tags such as `latest` are resolver inputs, never
benchmark identities. See
[Artifact Contract 1.2](docs/ARTIFACT_CONTRACT_1_2.md) and the
[Wire Protocol Contract](CONTRACT.md), plus the repository-level
[native architecture](../docs/architecture/README.md).

The current 20-case diagnostic release is separate from historical Phase 8 and
product-acceptance reports, which are retained under
`docs/archive/reports/` for reproducibility. Future formal benchmark work
additionally requires the sealed public/Gold role boundary in the
[Blind Benchmark Protocol](docs/BLIND_BENCHMARK_PROTOCOL.md), case-clustered
(not case×seed) analysis, and a frozen latency lifecycle.

The current LightRAG structural metadata and fixed-budget Evidence Pack audit
is recorded in [LIGHTRAG_STRUCTURAL_CONTEXT_EVIDENCE_PACK.md](LIGHTRAG_STRUCTURAL_CONTEXT_EVIDENCE_PACK.md).

RAG systems run behind isolated adapter workers. The platform communicates
with workers over authenticated loopback HTTP/JSON; versioned compatibility and
Unified Trace contracts keep system-specific observation behind the Adapter.

The initial storage backend is an atomic file store rooted at
`RAG_EVAL_HOME` (default: `~/.rag_eval_platform`). Legacy LightRAG evaluation
directories are never scanned.

## Productization Track

The WebUI-first Productization Track adds versioned System Profiles,
Benchmark/System resources, Evaluation Drafts, and Local/Docker execution
selection behind the same native admission and evaluation contracts. See
[Productization Track](docs/PRODUCTIZATION_TRACK.md).
Historical runtime acceptance evidence is retained in
`docs/archive/reports/PRODUCTIZATION_ACCEPTANCE_REPORT.md`. The current
document-authoring design and product boundaries are in
[Productization Track](docs/PRODUCTIZATION_TRACK.md) and
[Private DOCX design](docs/PRIVATE_DOCUMENT_BENCHMARK_DESIGN.md).

Ordinary users start at **Overview → New Evaluation**. Basic mode exposes only
LightRAG and RAG-Anything. The Platform expands profile defaults into a full,
resolved `ExperimentSpec` before invoking the same `RunExecutor` used by CLI.
CLI create/run applies the same native-DOCX admission policy; explicit replay
and historical readers retain compatibility behavior.

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

1. **Create a benchmark from DOCX** — inspect canonicalization and target
   discovery, resolve question/answer/evidence candidates, review them, then
   seal an immutable Benchmark Release. Bundle ZIP and TXT/Markdown resources
   remain available for legacy/development inspection but cannot start a new
   formal run.
2. **Add RAG system** — select LightRAG or RAG-Anything, save it, and use
   **Test connection** to confirm the local model runtime is reachable.
3. **New evaluation** — select the runnable Benchmark Release and tested RAG
   system, choose the required model and embedding identities (and an optional
   query mode), review the generated configuration, then run it.

The generated run remains a normal immutable artifact. Its Detail page shows
integrity verification, Cases, evidence flow, metrics, and failure assessment.
Use **Compare** only when the runs are compatible for the selected tier. See
[Quick Start](docs/QUICK_START.md) for a visual-free checklist and common
first-run remedies.

## Advanced CLI / CI

CLI commands and legacy SystemRegistration remain available for advanced users
and CI. New CLI Experiment creation/run uses the same native admission policy;
explicit Replay and historical artifacts retain their compatibility paths.

Override the storage home or ports without changing the script:

```bash
RAG_EVAL_HOME=/path/to/eval-home \
RAG_EVAL_API_PORT=8765 \
RAG_EVAL_WEBUI_PORT=4178 \
./scripts/start-local.sh
```

The startup script expects an installed Platform environment (`.venv/bin/rag-eval` or
`rag-eval` on `PATH`) and the monorepo WebUI (`npm ci` in `../webui`). Use
`RAG_EVAL_WEBUI_DIR` when that directory is elsewhere.

Completed runs contain a frozen `experiment.json`, per-repetition case files,
`summary.json` with mean/standard deviation and execution-failure rate,
`report.md`, worker logs, dependency/environment snapshots, model and prompt
digests, index fingerprints, Artifact 2.0 Unified Trace/evaluation records, and
SHA-256 checksums for every immutable artifact.

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
