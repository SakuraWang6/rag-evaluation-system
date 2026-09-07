# Private Document Benchmark — Current Gap Audit

Status: approved design baseline for BYOD-1. This document describes the checked-in codebase as it exists before Authoring is introduced. It does not treat a smoke dataset as a benchmark.

## Current architecture

`rag-eval-platform` already owns immutable Dataset Bundle 2.0 registration, experiment specifications, adapter worker execution, run/artifact persistence, metrics, comparisons, and the product API. The product layer also has editable `DatasetDraft` records. None of those components currently ingests DOCX, canonicalizes OOXML, discovers benchmark targets, generates candidate questions, records review decisions, or exports a reviewed private-document dataset.

The Evaluation Core is deliberately neutral about document authoring. `DatasetBundleStore` validates and content-addresses a complete Bundle. `RunExecutor`, the worker protocol, artifact contract, metrics, and comparison logic consume that Bundle and must remain unchanged.

## Existing reusable pieces

| Component | Current capability | Reuse decision |
| --- | --- | --- |
| Dataset Bundle 2.0 | Immutable, checksum-validated document/question/gold/evidence package | Reuse unchanged as the only export and evaluation boundary. |
| Formal evidence validation | Validates text spans and structured object/table evidence against canonical JSON records | Reuse; Authoring must emit faithful structured witnesses. |
| Product storage layout | Separates editable product state from registered bundles and run artifacts | Extend with an Authoring workspace root. |
| DatasetDraft | Creates a small manual text dataset, with one text answer and TextSpan evidence | Keep for its existing manual workflow; it is not a DOCX authoring backend. |
| Adapter capability model | Records unavailable retrieval stages without fabricating data | Reuse for canonical vs native execution diagnostics. |
| V2 prototype concepts | Deterministic hashes, canonical ordering, export policy, and validation ideas | Port concepts only; do not import synthetic scenario truth, FACT/TBL cues, fixed cases, or legacy services. |

## Verified gaps

1. There is no tracked `rag_eval.authoring` package and no `/api/v1/authoring/*` namespace.
2. There is no local authoring workspace with immutable source, canonical output, target/candidate/review records, diagnostics, or exports.
3. The platform accepts a binary source in a Bundle only when the Bundle separately provides UTF-8 canonical content. It does not create that canonical content from DOCX.
4. Current DatasetDraft supports only uploaded `.txt` / `.md` source material and a simple TextSpan answer/evidence path. It cannot express tables, figures, equations, structured object locators, candidate provenance, or mandatory review.
5. No current workflow distinguishes question generation from answer/evidence resolution; no gate prevents hidden-answer transfer or template leakage.
6. There is no private-source policy, OOXML support inventory, parser diagnostics, or page-number policy.
7. There is no product UI for document analysis, source-grounded candidate review, export blocking, or the two execution views.

## Integration boundary

The legacy `LightRAG/memory_data_service` and related synthetic generators are not the Platform's Dataset Authoring backend. They remain outside the Platform repository and are not called by the existing Platform process. They may inform design only. Direct integration would carry synthetic facts/scenario truth and benchmark-specific cues across the authoring boundary, which conflicts with private-document source grounding.

Authoring will therefore be co-hosted in the Platform process but isolated in a new package. Evaluation-domain modules must not import it. The API/composition layer can initialize Authoring and, after explicit user approval, register its exported immutable Bundle through the existing Dataset Bundle store.

## Source fixture audit

The user-provided DOCX is a viable private fixture for implementation smoke testing: it is a valid OOXML package with a long, structured Chinese document, headings, tables, captions, equations, inline media, bookmarks, VML/OLE objects, and note parts. Its rendered pagination differs from displayed page fields. Consequently page numbers are review metadata only and must never be a canonical Gold locator. The private source, extracted content, and generated private artifacts must remain outside Git and logs.

## Risk register

| Risk | Required control |
| --- | --- |
| Parser silently drops rich content | Every encountered object receives a supported/partial/unsupported diagnostic record. |
| Synthetic/template leakage | Discovery is structure-first; question and answer/evidence passes are separate; gates detect title, filename, object-ID, and overlap leakage. |
| Gold does not match retrieval corpus | Canonical witnesses are deterministic, locator round-trippable, and the source for the canonical execution view. |
| Native vs canonical comparison is unfair | Native DOCX is diagnostic-only; comparison winner claims are limited to same-view runs. |
| Private document exposure | Local product storage only; no source committed, source text logged, or browser-held remote secret sent. |

## Decision

Build the benchmark definition and authoring controls first. Data generation is not itself a benchmark; only a reviewed, frozen, validated, and sealed Bundle becomes one.
