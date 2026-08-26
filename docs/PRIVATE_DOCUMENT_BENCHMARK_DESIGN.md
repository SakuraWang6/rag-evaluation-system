# Private DOCX → RAG Benchmark Dataset MVP Design

## Purpose and non-goals

This MVP turns one private DOCX into a reviewable RAG benchmark dataset without changing Evaluation Core or importing the legacy data service. It is not an automatic benchmark factory: human approval is required before any candidate becomes Gold or is exported.

Non-goals: cross-view winner claims; implicit remote model use; silent rich-object conversion; automatic quotas for multi-hop questions; migration of legacy synthetic scenarios; changes to metrics, comparison rules, worker protocol, artifacts, or adapters.

## Authoring workspace

One uploaded DOCX creates one local workspace:

```text
RAG_EVAL_HOME/product/authoring/datasets/<authoring_dataset_id>/
  source/       original.docx and immutable ingestion manifest
  canonical/    deterministic object graph, execution Markdown, evidence JSONL
  targets/      structure-first discovery records
  candidates/   question and answer/evidence candidate versions
  reviews/      immutable reviewer actions
  approved/     only reviewer-approved cases
  exports/      prospective Bundle outputs and blocked-case reports
  diagnostics/  parser inventory, support status, validation diagnostics
```

Deleting this workspace is explicit and never deletes a previously registered immutable Dataset Bundle.

## Ingestion and canonicalization

Only `.docx` is accepted. Ingestion validates OOXML ZIP magic, safe member paths, required content types and `word/document.xml`, member count, uncompressed size, and configured upload size. It then copies the original to `source/original.docx`, computes SHA-256, and records ingestion time, parser/canonicalizer identity and version, configuration digest, and diagnostics.

Canonicalization is deterministic and chunker-independent. Stable IDs are derived from the source digest, object kind, and structural ordinal; timestamps and absolute paths do not enter the canonical digest. It produces ordered records for Document, Section, Block, TextSpan, Table, Row, Cell, Figure, Caption, Equation, and Reference. Every record carries a source digest, canonical digest context, stable ID, structural locator, source witness, and representation status.

| Status | MVP handling |
| --- | --- |
| Supported | body headings, paragraphs, lists, resolved tables, inline images, captions, bookmarks, hyperlinks |
| Partial | merged tables, heuristic caption association, OMML surface extraction, floating/VML shapes, notes only with a body anchor, cross-reference fields |
| Unsupported | OLE objects, unresolvable drawing/chart/SmartArt semantics, unanchored notes |

Partial and unsupported objects remain visible diagnostically. They cannot be approved Gold evidence unless the representation-specific validation proves a faithful, observable witness. Page numbers may assist review but are never canonical locators.

## Execution views

An approved authoring release creates two source views with identical approved Question, Gold Answer, and canonical Gold Evidence.

| View | Source document | Intended use |
| --- | --- | --- |
| `canonical-text` | source-derived Markdown plus structured canonical evidence JSONL | Fair normal evaluation for LightRAG Legacy, LightRAG Enhanced, and RAG-Anything when it ingests canonical text. |
| `native-docx` | original DOCX plus the same canonical evidence JSONL | RAG-Anything parser/document-understanding diagnostic only. |

Native-DOCX runs are never compared as winner claims against canonical-text runs. Capability gaps remain unavailable rather than being imputed.

## Target, candidate, and Gold flow

1. Freeze the canonical source.
2. Discover benchmark targets from structure: candidate facts, relations across sections, repeated entities, tables, captions, equations, authority/version relations, and plausible near-miss negatives. This is not quota-first.
3. Optionally enrich targets with a local structured Ollama proposal. Every proposal must cite frozen canonical object IDs. Rule-only and manual paths remain fully usable.
4. Generate a QuestionCandidate from the frozen target/source. Record provider, model, prompt digest, seed, method, and source object citations.
5. Resolve Answer/Evidence in a separate pass using only the frozen canonical source and question. This pass cannot consume a hidden scenario answer or the question generator's answer.
6. Run gates: answer/title/file/object-ID leakage, duplicate/template overlap, source/evidence digest mismatch, locator/witness round-trip, alternate answers, table recomputation, negative absence, single-block shortcuts, multi-hop removal, and export representability.
7. A reviewer accepts, edits, or rejects. Edits version the candidate and create a review record. Only approved versions form Gold.

## Product API and WebUI

Authoring APIs are under `/api/v1/authoring/*`. The initial surface supports upload, list/detail, analysis, canonical-context inspection, and explicit deletion. Later endpoints add targets, candidates, reviews, export, and registration.

The Dataset product entry points are: Upload Dataset Bundle, Create Manually, and Create from Document. The document flow is Upload → Analysis → Target Discovery → Candidate Review → Dataset Summary → Export/Register. Basic UI never exposes object IDs, digests, MSES serialization, worker paths, or adapter internals; Advanced views can expose source-grounding diagnostics needed for review.

## Export and sealing

The Authoring exporter maps only faithful Bundle 2.0 fields. It blocks cases with unsupported locators, unresolved answers, non-factorable proof paths, non-observable evidence, or failed/flagged checks requiring review. It must never weaken Gold merely to increase export rate. Candidate and review records stay outside Dataset Store; only the exported immutable Bundle is registered through the existing registration API.

An approved export is a release candidate. A sealed benchmark additionally records source/canonical/config/model digests, validation report, execution-view identity, reviewer decisions, and compatibility target. A benchmark should be released only after human review of question distribution, source grounding, ambiguity, negative quality, and capability coverage.
