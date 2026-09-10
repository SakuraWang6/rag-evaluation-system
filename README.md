# RAG Evaluation System

This repository owns a system-neutral platform for building a Canonical
Benchmark from DOCX and evaluating complete, native RAG pipelines.

The only supported evaluation chain is:

```text
Original DOCX
  -> immutable Benchmark Release
  -> RAG-native parse / chunk / index / retrieve / rank / context / answer
  -> AdapterRunResultV2 / UnifiedTrace
  -> Unified Evaluation
  -> Artifact 2.0
  -> Platform API
  -> WebUI
```

The Platform defines where Gold evidence exists. A RAG decides how it parses
and retrieves. An Adapter proves where runtime results came from. The scorer
judges verified coverage. The WebUI renders persisted artifacts without
recomputing provenance or scores.

## Repository map

- [`platform/`](platform/README.md) owns Benchmark authoring, Canonical
  coordinates, admission, orchestration, Unified Evaluation, Artifact 2.0 and
  the API.
- [`adapters/`](adapters/README.md) owns isolated Worker implementations for
  each RAG runtime.
- [`webui/`](webui/README.md) owns the browser application and persisted-result
  presentation.
- [`docs/architecture/`](docs/architecture/README.md) is the current
  architecture and contract index.
- [`docs/decisions/`](docs/decisions/) contains the accepted decision record.

Third-party RAG source is not vendored here. Workspace tooling resolves its
pinned repositories and Worker images independently of this repository.

## Required checks

The maintained local baseline is Python 3.11.15 from the Conda environment
`lightrag-memory-eval` and Node 24.12.0 selected through NVM. The required
workflow pins those exact language-runtime versions and tests Platform,
Adapter conformance, Schema 2.0 export, package installation, both model-free
Worker lifecycles, Ruff differential policy, and the WebUI.

```bash
conda activate lightrag-memory-eval
nvm use 24.12.0
```

Start with the [operator quick start](platform/docs/QUICK_START.md).
