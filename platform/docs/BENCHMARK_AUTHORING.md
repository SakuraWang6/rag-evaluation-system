# Benchmark Authoring Guide

This guide defines the maintained DOCX-to-Benchmark workflow. The Platform
owns source identity, Canonical coordinates, questions, answers, Gold evidence
and the immutable Benchmark Release. It does not author a corpus tailored to a
particular RAG.

## 1. Admit a source

Every source record binds:

- a stable document and source-family identity;
- Original DOCX bytes and SHA-256;
- parser, canonicalizer and configuration identities;
- Canonical document digest;
- parsing, structural and locator completeness; and
- source-family isolation and review decisions where the source is held out.

A source can support formal Gold only when parsing, structure and evidence
locators are complete. Partial, unsupported, missing or ambiguous source
representation fails closed. Held-out sources must additionally be distinct
from all registered development families; an undetermined similarity requires
human review.

## 2. Author from evidence

Create questions from verified Canonical evidence backwards. A case must not
depend on filenames, internal IDs, author hints or answer leakage. Its answer
must be fully supported by one or more minimal sufficient evidence paths.

For each case record:

- natural question wording and requested answer form;
- accepted answer, approved alternatives and normalization rule;
- answerability classification;
- typed task, modality, retrieval and reasoning labels;
- Canonical evidence alternatives and MSES clauses/paths;
- dependency graph when ordered multi-hop reasoning is claimed;
- negative-scope rationale for abstention; and
- source, model-assistance, review and adjudication identities.

Retrieval difficulty describes source-side location and competition. Reasoning
difficulty describes the operation after evidence is available. A failure by
one reference RAG does not define either label.

## 3. Separate responsibilities

- Models may propose candidate questions, rewrites, answers, evidence and
  distractors. Proposal output is never approved Gold.
- Programs check hashes, locators, source isolation, duplicate/leakage signals,
  MSES shape, dependency closure and required records.
- Independent reviewers decide naturalness, ambiguity, answer correctness,
  evidence sufficiency/minimality and plausible alternatives.

Cases involving multi-hop, negative scope, conflicts, alternative MSES,
tables or rich structure require the configured additional review. Unresolved
disagreement blocks Release publication.

## 4. Isolate evaluation data

Development and held-out Portfolios use different source families. A held-out
case requires a passed source-admission report before it can be actualized.
Gold remains sealed until code, model identities, query configuration,
ComparisonSpec and AnalysisContract are frozen.

Calibration may use locked BM25, dense, no-retrieval and oracle-evidence
roles to find shortcuts or annotation defects. Calibration outputs cannot edit
Gold, choose Gold evidence or redefine difficulty. Every executable reference
requires a versioned harness, configuration, prompt/model and seed digest.

## 5. Blind operation

The public package contains source and questions; the sealed package contains
Gold and Canonical proof material:

```text
blind/
  source_public/
  questions_public/
  public_manifest.json

sealed/
  gold_answers.jsonl
  gold_evidence.jsonl
  canonical/
  checksums.json
  blind_protocol.json
```

Validate the split before a formal run:

```bash
rag-eval validate-blind-layout blind sealed
```

The protocol enforces:

```text
sealed_at < config_frozen_at < formal_runs_started_at
          <= formal_runs_completed_at < gold_revealed_at
```

Any headline configuration change after Gold reveal is a new, explicitly
post-hoc experiment.

## 6. Publish and use a Release

The Authoring workflow must finish source, case and Gold validation before it
seals an immutable Benchmark Release. The Release pins one Original DOCX,
Canonical identities, reviewed cases, Gold and validation reports.

Run admission consumes that Release without regenerating or filtering Gold.
Each RAG receives the same Original DOCX and decides its own parse, chunk and
index behavior. See [Canonical Conformance](../../docs/architecture/CANONICAL_CONFORMANCE.md)
and the [Current Architecture](../../docs/architecture/CURRENT_ARCHITECTURE.md).
