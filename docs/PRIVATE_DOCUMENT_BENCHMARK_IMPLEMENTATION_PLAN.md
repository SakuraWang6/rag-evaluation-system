# Private DOCX → RAG Benchmark Dataset MVP Implementation Plan

## Invariants

- Evaluation-domain modules do not import `rag_eval.authoring`.
- Authoring data stays under `RAG_EVAL_HOME/product/authoring`; immutable Dataset Bundles are the only crossing into Evaluation.
- Private DOCX content, canonical output, candidate records, and review data are never committed or logged as source text.
- Review is mandatory and Gold is never inferred directly from synthetic scenario truth.
- `canonical-text` and `native-docx` are distinct execution views; winner comparisons require the same view.

## Delivery phases

| Phase | Scope | Definition of done |
| --- | --- | --- |
| BYOD-1 | Gap audit, design, architecture diagram, this plan | Documents state real boundaries, reusable components, gaps, and risks. |
| BYOD-2 | DOCX ingestion, immutable workspace, manifests, diagnostics inventory | Invalid extension/ZIP rejected; source hash stable; no private source committed/logged. |
| BYOD-3 | Deterministic OOXML canonical model and execution/evidence views | Same DOCX/config gives same digest; fixtures cover tables, captions, equations, notes, images, OLE/VML; real private DOCX smoke audit. |
| BYOD-4 | Structure-first target discovery and local-model provider boundary | Every target cites frozen objects; rule-only fallback; invalid model citations flagged. |
| BYOD-5 | Separate question and answer/evidence pipelines | Candidate provenance; no hidden-answer transfer; evidence/MSES/dependency checks. |
| BYOD-6 | Quality gates, negatives, and near-miss validation | Fixtures for leakage, duplicates, alternatives, table operations, and multi-hop removal. |
| BYOD-7 | Persistent review records and approval state machine | Accept/edit/reject versioning; unreviewed or failed cases cannot export. |
| BYOD-8 | Canonical/native Bundle export and existing-API registration | Deterministic exports; `load_bundle`; blocked-case report; original source provenance retained. |
| BYOD-9 | Integrated Authoring UI/API client | Upload/analyze/review/export/register browser path; Basic/Advanced visibility checks. |
| BYOD-10 | Real reviewed end-to-end on the user-provided DOCX | User-approved cases; valid Bundle/artifacts; Legacy/Enhanced comparison; RAG-Anything canonical/native diagnostics; Case Detail attribution. |

## First implementation unit

Implement BYOD-2 and BYOD-3 first in `rag-eval-platform`:

1. Add `rag_eval.authoring` with workspace storage, safe DOCX ingestion, source manifests, persistent states, and diagnostics.
2. Add a direct OOXML canonicalizer that creates deterministic JSONL object records, natural source-derived execution Markdown, and a structured evidence view compatible with Bundle formal evidence validation.
3. Wire only composition/API routes under `/api/v1/authoring/*`; keep Evaluation Core imports unchanged.
4. Add public synthetic parser fixtures and API/unit tests; run the full Platform suite and a local smoke audit on the private DOCX without retaining its content in the repository.

## Later design choices

Local Ollama (`qwen3:4b-instruct`) is the default optional proposal engine. It is not a requirement for deterministic ingestion, canonicalization, manual authoring, or review. Remote model use is advanced, server-configured, requires explicit UI consent, and never accepts browser-held secrets.

The target size of 15–25 approved cases is an aspiration, not a generation quota. Human-authored, synthetic, semi-synthetic, and adversarial cases serve different calibration needs; a release records which are included instead of presenting one automatically generated set as universally representative.

## Repository ownership

| Repository | Allowed work |
| --- | --- |
| `rag-eval-platform` | Authoring domain, API composition, docs, exporter, tests |
| `rag-eval-webui` | BYOD-9 Authoring UX/API client only |
| `rag-eval-adapters` | No planned change; only a separately approved adapter-only bug fix |
| `LightRAG/memory_data_service` | Unchanged |
