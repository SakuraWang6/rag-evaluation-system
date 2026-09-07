# RAG Evaluation System

This repository is the single Git owner for the evaluation platform, runtime
adapters, and evaluation WebUI.

Component boundaries remain explicit:

- `platform/` owns authoring, datasets, evaluation contracts, execution, and
  storage.
- `adapters/` owns Worker Protocol implementations for each RAG runtime.
- `webui/` owns the browser application and product presentation layer.
- `tests/rag_eval_adapters/` owns cross-package Adapter contract and integration
  tests. Its path is intentionally stable because known-baseline failures are
  matched by exact pytest node ID.

Third-party RAG source is never vendored here. Workspace tooling resolves the
independent repositories recorded in `/Users/sakura/RAG/repos.lock.yaml`.

