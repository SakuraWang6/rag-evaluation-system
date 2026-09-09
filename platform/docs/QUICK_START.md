# Native v2 Quick Start

## Start the local application

Install the Platform and WebUI dependencies. From `platform/`, run:

```bash
./scripts/start-local.sh
```

Open `http://127.0.0.1:4178`. The API defaults to
`http://127.0.0.1:8765/api/v1`.

## Create and evaluate a Benchmark

1. Choose **Create from document** and upload one DOCX.
2. Inspect Canonical analysis and discovered targets. Resolve candidate
   questions, answers and evidence, then complete the required reviews.
3. Seal an immutable Benchmark Release.
4. Choose **Add RAG system**, select LightRAG or RAG-Anything, save it and run
   **Test connection**.
5. Choose **New evaluation**, select the Release and RAG system, then resolve
   the generation model, embedding model and query settings.
6. Review the expanded configuration and choose **Confirm and run**.
7. Open the Run to inspect Artifact integrity, metric availability, cases,
   evidence flow and proof-gated failure attribution.

The Platform rejects the request before queueing if the Release does not bind
one Original DOCX, the System/Worker profile is unresolved, query or resource
configuration is incomplete, or a non-native input route is requested.

## Interpret results

- `observed` and numeric zero mean the metric was proved and its value is zero.
- `unavailable` means the exact value could not be proved; it is not zero.
- `truncated` may still support an `@K` metric when the verified prefix reaches
  K.
- `partial`, `unsupported`, `unobserved`, `failed` and `corrupted` preserve
  different observation meanings.
- Comparison requires equal persisted metric descriptor digests.

The WebUI reads these facts from Artifact 2.0 and does not rescore a Run.

## Common failures

- **Connection test fails:** verify the selected Worker environment contains
  the Adapter, Platform package and pinned RAG runtime.
- **Model identity is rejected:** resolve an immutable model/revision digest;
  a display name or mutable tag is not a formal identity.
- **A metric is unavailable:** inspect the stage status, proved prefix and
  provenance diagnostics. Do not increase a displayed value manually.
- **Artifact is corrupted:** use `rag-eval verify-run RUN_ID`; repair the
  execution source and create another Run rather than rewriting the Artifact.
- **Run is not leaderboard eligible:** ensure every case proves every formal
  metric under identical descriptors.

For authoring policy, see [Benchmark Authoring](BENCHMARK_AUTHORING.md). For
system boundaries, see the [Current Architecture](../../docs/architecture/CURRENT_ARCHITECTURE.md).
