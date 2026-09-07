# Benchmark V0 — Protocol Freeze

Status: **design and authoring protocol**. This document creates no benchmark case, changes no Dataset Bundle, Artifact Contract, Worker Protocol, Evaluation Platform, DatasetDraft, question/Gold generator, or `memory_data_service`.

Inputs: [current-state audit](/Users/sakura/RAG/DATA_BENCHMARK_CURRENT_STATE.md), [Blueprint](/Users/sakura/RAG/BENCHMARK_BLUEPRINT_V0.md), and [96-case planning matrix](/Users/sakura/RAG/BENCHMARK_V0_CASE_MATRIX.csv).

The freeze concerns the measurement construct and how a case is authored, reviewed, calibrated and sealed. It does not turn any generator truth, RAG chunk ID, Golden Smoke configuration, or historical run into benchmark Gold.

## 1. Frozen Human Core domain and source policy

### 1.1 Candidate combinations considered

| Candidate | Strength | Material risk | Decision |
| --- | --- | --- | --- |
| A. Versioned open technical system documentation + openly licensed public operational guidance | Represents the technical retrieval/structure focus and a separate authority/procedure construct; both have stable, versionable source classes. | Public guidance must be screened particularly hard for redistribution rights and time sensitivity. | **Recommended and frozen.** |
| B. Internet standards / protocol specifications + open-source technical documentation | Excellent versioning, provenance and technical precision. | Both families are technical; weak coverage of operational policy, conditional procedure and authority language. | Not selected for v0; may seed a future technical-only suite. |
| C. Public-university procedures + community/organizational guides | Can contain natural procedure language. | Licensing, redistribution, authoritativeness and revision history are too uneven for a first sealed release. | Internal pilot only unless every source passes the sealed rule. |

### 1.2 Human Core domains — frozen

Human Core uses exactly two source domains:

1. **Versioned technical manuals, system documentation and interface/release specifications.** These must be first-party, release-tagged documentation for software or systems operations, not issue discussions, blog posts, live support threads or generated examples.
2. **Openly licensed organizational policy, operational procedure or public-service guidance.** These must state an accountable issuer, intended audience, revision/effective date and explicit authority/procedure language. They are not legal opinions, medical guidance or financial advice.

The domains complement rather than imitate each other: the first supplies implementation detail, configuration/compatibility/version reasoning and realistic structured documentation; the second supplies conditional, authority, approval, exception and incomplete-information cases. They do not authorize claims about all technical or organizational RAG.

### 1.3 Source acceptance rules

Every sealed Human Core source must satisfy every rule below. A collection of documents is accepted only after each constituent source passes independently.

| Rule | Sealed Human Core requirement |
| --- | --- |
| License and redistribution | The exact source snapshot may be redistributed in the public benchmark package and retained in the sealed package. Record the license name/version, licence URL or embedded notice, rights holder, applicable attribution/notice text and any derivative-work condition. “Publicly accessible” is not a license. |
| Provenance | Capture issuer/author, official canonical URL or repository, retrieval date, source title, publication/effective date, version/revision/tag and a source-level SHA-256. Mirrors are insufficient unless the first-party source is also recorded and the mirror’s identity is verified. |
| Immutable version | Use a release tag, immutable repository revision, official dated PDF/DOCX, or an issuer-controlled versioned record. A mutable landing page alone is never a sealed source. Preserve the exact retrieved bytes and canonicalization version. |
| Document length | Default range is **1,200–20,000 canonical text tokens per document**. A 400–1,199-token structured companion document is allowed only when it is naturally an annex/table/appendix to a longer accepted source and is never the sole source of a long-context claim. Longer documents require a documented reason and section-level canonical locators. |
| Structure | Require an authentic heading hierarchy and at least one natural navigation/structure feature across the Human Core collection: section hierarchy, procedural steps, version/revision history, table, appendix, cross-reference or exception rule. Do not insert synthetic labels, Gold marks or artificial distractor text into Human sources. |
| Language | Each source is natively published in `en` or `zh`; record the source language and script. Machine translations, parallel translations and edited translations are not paired cases and may not be used to claim language equivalence. |
| Source quality | First-party issuer; identifiable accountable organization; substantive and internally coherent content; stable audience/purpose; no unresolved copyright notice; no materially broken or inaccessible referenced content required by the intended case. |
| Privacy and safety | No personal/confidential data; no medical, legal judgment, individualized financial advice, or other high-stakes instruction that could be misconstrued as operational advice. |

### 1.4 Admission tier

| Tier | Allowed source condition | May enter sealed v0? |
| --- | --- | --- |
| `sealed_eligible` | Meets every rule in §1.3, including redistribution, immutable version and provenance. | Yes, after case review/calibration. |
| `internal_pilot_only` | Legitimate access/use is documented, but redistribution is absent/limited; or source is promising but has a repairable provenance/version/structure issue. It may be used only in a non-distributed internal workflow exercise. | No. |
| `prohibited` | License/provenance cannot be established; source is highly mutable/time-sensitive; contains private/personal data; is medical/legal/financial advice; is a non-authoritative mirror; or has source-visible benchmark/Gold cues. | No, including internal case authoring. |

News feeds, search-result snippets, personal blogs, public issue threads, social content, paid/vendor material without redistribution permission, pages with only “last updated” but no recoverable version, and any source whose rights state is unclear are not Human Core sealed sources.

## 2. Frozen Chinese-slice role

The 72 English / 24 Chinese allocation is frozen as follows:

> **English is the v0 primary comparative slice. Chinese is an independently reviewed exploratory coverage slice.**

Chinese is kept because a document-grounded benchmark should expose language-specific authoring, segmentation and retrieval risks early. It is not enlarged mechanically to 48/48 and it does not create a translation benchmark.

Rules:

- Report Chinese results separately by primary task, portfolio, retrieval/reasoning difficulty, modality and answerability.
- Do not pool English and Chinese into a cross-language claim, call score differences language effects, or rank systems by EN-versus-ZH accuracy.
- No English/Chinese question pair is assumed equivalent; a translated source/question needs its own provenance, authoring record, independent review and calibration.
- Every Chinese case has an author and an **independent reviewer fluent in the language of the source and question**. The reviewer cannot be the author.
- Chinese leakage review must inspect character n-grams, Chinese segmentation under two declared segmenters or equivalent human analysis, answer/alias/transliteration overlap, punctuation/number/unit/identifier cues, and template-family resemblance. English whitespace-token thresholds must not be applied blindly.

## 3. Frozen Benchmark Authoring Record and evidence contract

The normative worksheet is [BENCHMARK_CASE_AUTHORING_TEMPLATE.yaml](/Users/sakura/RAG/BENCHMARK_CASE_AUTHORING_TEMPLATE.yaml). It is an authoring-side record, deliberately separate from the current Bundle and Platform schema.

### 3.1 Required record

An authoring record is valid only when it contains all of these sections:

```text
case_id, question, accepted_answers, normalization_rule, answerability,
primary_task, taxonomy_axes, retrieval_difficulty, reasoning_difficulty,
mses, evidence, dependency_graph, source_provenance, author_rationale,
review, adjudication, calibration
```

The `evidence` section records `evidence_id`, `document_id`, canonical locator, quote/witness and one role: `required`, `supporting`, `partial`, or `conflicting`. An MSES lists only `required` evidence IDs. Alternative complete paths are represented by distinct MSES records using `alternative_to`; they are OR paths, while items within one MSES are AND requirements.

Gold is always tied to an immutable canonical source record:

```text
document bytes + source provenance + canonicalization version/digest + canonical locator + witness
```

It is never tied to a generator fact ID, source-visible label, page-only reference, or RAG-system chunk ID. A quote/witness must be sufficient to find/verify the locator but need not expose all sealed annotation material in the public package.

### 3.2 Conceptual adapter provenance interface — not a production API

Different chunkers may return different text spans. The future concept interface is:

```text
returned_chunk
  { system_chunk_id, stage, rank, text_or_digest }
        → source_provenance_mapping
  { document_id, canonicalization_digest, locator(s), mapping_quality }
        → canonical_evidence
  { evidence_id(s), role(s), MSES membership }
        → MSES coverage
```

`mapping_quality` is one of `exact`, `contained`, `overlapping`, `document_only`, or `unmapped`. Only `exact`, `contained`, and a reviewer-approved `overlapping` mapping can credit a required evidence item; `document_only` is useful telemetry but is not locator coverage.

This is a design contract, not an Adapter API request. An adapter may remain answer-only or document-level observable. It must not fabricate a locator to obtain evidence credit.

### 3.3 Metric availability rule

| Adapter output available | Metrics that remain available | Metrics that are **unavailable**, never zero |
| --- | --- | --- |
| Final answer only | Answer accuracy/normalization where applicable; abstention behaviour where applicable; end-to-end latency if measured. | All MSES recall/coverage/completeness, required-evidence rank, final-context coverage, source-locator precision, row/figure/equation witness coverage and stage attribution. |
| Returned chunks/ranks but no source-level mapping | Retrieval-count/rank telemetry for the system’s own chunks, latency. | Any canonical evidence/MSES credit, canonical rank, stage evidence coverage and object-level evidence metric. |
| Document-level mapping only | Document-level diagnostic recall, if declared. | Canonical-locator/MSES completeness, row/cell/caption/equation coverage and exact evidence precision. |
| Canonical source mapping plus retrieval/final-context stage data | Applicable MSES coverage/completeness/rank and source-level diagnostics. | Any metric for a stage the adapter did not emit. |

Unavailable must be serialized/reported as `unavailable` with a reason and excluded from denominators. It is not `0`, `false`, “no retrieval,” or evidence failure. System comparisons must display metric coverage before interpreting evidence slices.

## 4. Frozen answerability and `needs_review` policy

| Authoring label | Required outcome class | Inclusion in v0 standard aggregate/comparison |
| --- | --- | --- |
| `answerable`, `conflicting_resolvable` | `answer` | Included in answer/grounding slices; resolvable conflict is separately labelled. |
| `unanswerable`, `plausible_unsupported`, `partially_supported` | `abstain` | Included in abstention/unsupported-answer slices, with the three labels reported separately. |
| `ambiguous`, `conflicting_unresolved` | `needs_review` / escalation | **`diagnostic_only`**; excluded from accuracy, abstention accuracy and formal aggregate/comparison until a scored contract is separately approved. |

The 96-case plan contains three `ambiguous` and three `conflicting_unresolved` cases. They remain in the planned portfolio to exercise authoring, review, source provenance and qualitative system behaviour. A current Platform result does not become wrong merely because it cannot represent a formal `needs_review` outcome. For v0, record the observed response and evidence qualitatively; do not coerce it to answer/abstain and do not use it in headline comparisons.

## 5. Calibration baseline identity policy

The baseline lock format is [BENCHMARK_CALIBRATION_TEMPLATE.yaml](/Users/sakura/RAG/BENCHMARK_CALIBRATION_TEMPLATE.yaml). The reference model artifacts below are explicitly adopted from an audited, verified historical observation but are **not** implicitly inherited from Golden Smoke. The new calibration lock has its own identifier, prompts, purpose, acceptance decisions and checksum.

### 5.1 Reusable verified artifacts

| Item | Frozen reference identity | Evidence source |
| --- | --- | --- |
| Generator model | `qwen3:4b-instruct`; `sha256:0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0` | Audited Golden Smoke execution record. |
| Embedding model | `bge-m3:latest`; `sha256:7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`; dimension 1024 | Audited Golden Smoke execution record. |
| LightRAG source | Git revision `469ddb8f63cc7d480d12711cee0b94850e98967c`; `lightrag/prompt.py` SHA-256 `93a571a2d7b7825c691584eb4af77080883287851ce29e586192eaafc0581b9a` | Current workspace inspection. |

### 5.2 Required baseline set and fixed semantics

| Baseline ID | Purpose | Frozen operational settings |
| --- | --- | --- |
| `bm25_v0` | Lexical shortcut and rank competition diagnostic. | Canonical source text only; declared language-aware tokenizer; `k=20`; no reranker; no generation; no chunk-ID Gold credit. Exact reference-harness revision and tokenizer artifact digest must be locked before the dry run. |
| `dense_v0` | Semantic shortcut/confusability and rank competition diagnostic. | BGE-M3 artifact above; cosine score; dimension 1024; `k=20`; no reranker; no generation. Exact reference-harness revision/preprocessing digest must be locked before the dry run. |
| `no_retrieval_llm_v0` | Detect question/answer/ID/template/world-knowledge shortcuts. | Qwen artifact above; no source/context; fixed no-retrieval prompt; `temperature=0`, seed policy `three_fixed_seeds`; context budget `0`; no reranker. |
| `oracle_evidence_llm_v0` | Test MSES sufficiency and answer normalization independently of retrieval. | Qwen artifact above; one complete MSES at a time; fixed oracle prompt; `temperature=0`, same three seeds; context budget 12,000 canonical tokens; no retrieval/reranking. |
| `lightrag_legacy_v0` | Historical RAG comparator, not Gold. | LightRAG revision/prompt digest above; `profile=legacy`, `query_mode=naive`, candidate `k=20`, final context `k=5`, max context 12,000, no reranker, Qwen/BGE artifacts above, temperature 0, seed policy below. |
| `lightrag_enhanced_v0` | Structured-profile RAG comparator, not release criterion. | Same lock as Legacy except `profile=structured`; all other controlled factors identical. |

For all answer-producing baselines, seeds are `20260824`, `20260825`, `20260826`; a calibration output records all three. `temperature=0` does not remove the need to record seeds because service implementations can still vary. No cache may supply an answer; cache state is off or run-scoped and recorded. The precise literal prompts, model/embedding digests, code/harness revision, tokenizer/preprocessing digest, retrieval `k`, reranking policy and context budget are all lock fields, not free-form run settings.

**Execution-lock limitation:** this workspace contains verified model artifacts and LightRAG profiles, but it does not contain a versioned standalone reference harness for the BM25/dense/no-retrieval/oracle baselines. The template therefore marks the harness digest as a mandatory pre-dry-run fill. A benchmark dry run must not start until that independent calibration lock is instantiated and checksum-verified.

## 6. Frozen case acceptance, rewrite and challenge rules

Calibration never selects cases based on LightRAG Legacy/Enhanced winning or losing. The only permitted dispositions are `ACCEPT`, `REWRITE`, `REJECT`, and `CHALLENGE_ONLY`.

| Finding after author/review/calibration | Disposition | Required action |
| --- | --- | --- |
| Answer is stated or trivially recoverable from question, ID, title, filename or visible metadata | `REJECT` unless a source/question rewrite removes the cue before re-entry | Record the shortcut; do not hide it by changing a scorer. |
| Visible `Gold`, `FACT`, `gold-row`, `authoritative`, `DISTRACTOR`, source-priority instruction or equivalent cue | `REJECT` | Source construction is invalid for v0. |
| Oracle-evidence baseline cannot answer stably in at least 2 of 3 trials after scoring check | `REWRITE`, then `REJECT` if unresolved | Repair question, MSES, witness, normalization or source; re-review. |
| No-retrieval baseline repeatedly answers an evidence-required case across configured trials | Shortcut audit → `REWRITE` | Retain only when it is an explicitly labelled Easy control and the review record explains why this outcome is expected. |
| Claimed Hard retrieval case shows no material BM25 or dense rank competition | `REWRITE` or reclassify | Add natural competition/distance/alias pressure or change the retrieval label. |
| Claimed multi-hop case has a permitted single canonical block stating the final answer | `REWRITE` or reclassify | Remove the shortcut or call it single/independent multi-evidence. |
| MSES, answerability, authority rule, accepted answer or task label remains disputed after adjudication | `REJECT` before seal | A sealed case cannot carry unresolved annotation disagreement. |
| Source fails provenance/license/immutable-version rule | `REJECT` | It cannot be repaired by better annotation. |
| All ordinary RAG comparators fail while oracle succeeds and reviewers agree on the construct | `CHALLENGE_ONLY` candidate | Retain only when the mechanism is intended, reproducible and separately reported; exclude from headline aggregate unless later promoted by an explicit policy decision. |
| Required case fields, witness or review record missing | `REWRITE` | Complete record and rerun review/calibration. |
| All applicable checks pass and the intended construct remains discriminative | `ACCEPT` | Eligible for later public/sealed packaging; not automatically sealed. |

## 7. 96-case matrix review

### Decision: **NO MATRIX CHANGE**

The matrix remains a planning distribution, not a statistically balanced scorecard. The review found no measurement-backed reason to alter it before a protocol dry run.

| Review question | Finding | Decision rationale |
| --- | --- | --- |
| Task duplication | The 38 `direct_extract` cases split into semantic, lexical-confusable, long-distance, independent multi-evidence and six Easy controls. Only six are basic direct controls. | The other 32 intentionally isolate retrieval/ranking from post-retrieval reasoning; removing them simply to lower the label proportion would erase a key diagnostic. |
| Retrieval-hard / reasoning-easy value | These cases separate evidence location/rank competition from reasoning. | Retain; this is the Blueprint’s central two-axis construct. |
| Reasoning-hard coverage | 29 planned cases explicitly require dependent chain, temporal authority, conditional reasoning, hard table operations, ambiguity or unresolved conflict. | Sufficient for first-v0 slice analysis without making all failures uninterpretable mixtures of retrieval and reasoning. |
| Answerability | 74 answerable, 6 resolvable-conflict answer cases, 10 abstain cases, and 6 diagnostic-only `needs_review` cases. | Keep the three abstain labels and both escalation labels; three-to-four cases per narrow label are not a claim of stable sub-leaderboards. Rebalance only after calibration evidence, not for symmetry. |
| Human Core role | 36 cases span realistic retrieval, multi-evidence, comparison, aggregation, conditional, structured and abstention roles. | The new two-domain/source policy supplies the missing realism constraint without changing counts. |
| Synthetic role | All 16 Synthetic cases are attached to controlled mechanism/structured-object or controlled relation/authority tests. | Correct: Synthetic stays diagnostic, rather than defining overall RAG quality. |
| Adversarial influence | 16/96 cases (16.7%) exercise confusability, stale/authority and negative/uncertain evidence. | Large enough for failure analysis, too small to dominate the portfolio; report separately. |
| Rich structure | Exactly 16 cases: table 10, figure/caption 3, equation/reference 3. | Adequate as a mechanism slice for v0. It is not a claim of broad multimodal coverage. |

Matrix diff: `NO MATRIX CHANGE` — all portfolio totals remain Human 36 / Semi-synthetic 28 / Synthetic 16 / Adversarial 16; EN 72 / ZH 24; total 96. The 48-case dry run deliberately uses a different, coverage-first sample and is not a half-release.

## 8. 48-case protocol dry run

The sampling design is [BENCHMARK_48_CASE_DRY_RUN_PLAN.csv](/Users/sakura/RAG/BENCHMARK_48_CASE_DRY_RUN_PLAN.csv). It is 12 planned slot groups of four cases, not 48 actual cases and not a subset that can automatically graduate into sealed v0.

Its purpose is to demonstrate that two people can author/review the same record, disagree intelligibly, adjudicate it, calibrate it, prepare blind materials and identify workflow defects. It samples 12 slots from each portfolio; 36 EN / 12 ZH; 40 answer, 4 abstain and 4 `needs_review` slots. It deliberately covers single/multi/multi-hop evidence; Easy/Medium/Hard retrieval and reasoning; text/table/figure/equation; and alternative/conflicting evidence. It is not statistically representative of the final 96 distribution.

### Dry-run entry criteria

Before any of the 48 slots becomes a real case, all must be true:

1. This protocol and all four templates have a version/checksum and named owner.
2. Two Human Core domains and source admission tiers are applied to candidate sources; no pilot-only/prohibited source is mistaken for sealed-eligible.
3. The new independent calibration lock has every mandatory implementation/model/tokenizer/prompt/config/seed/digest field populated and verified.
4. Named author, independent reviewer, adjudicator and seal reviewer roles exist; the author cannot self-approve.
5. Canonicalization and source-provenance conventions are demonstrated on one non-case source sample.
6. The `needs_review` cases are marked `diagnostic_only` in the dry-run plan and excluded from any accuracy/abstention aggregate.
7. A blind-package rehearsal location and access boundary are available, without modifying production Bundle/Platform schemas.

Dry-run outputs may change the Blueprint, templates and 96-case planning matrix. They are never automatically promoted, published as a benchmark or merged into a sealed release.

## 9. Protocol artifacts and workflow

| Artifact | Role |
| --- | --- |
| [BENCHMARK_CASE_AUTHORING_TEMPLATE.yaml](/Users/sakura/RAG/BENCHMARK_CASE_AUTHORING_TEMPLATE.yaml) | Authoring record and MSES/evidence/source contract. |
| [BENCHMARK_REVIEW_TEMPLATE.yaml](/Users/sakura/RAG/BENCHMARK_REVIEW_TEMPLATE.yaml) | Independent reviewer’s field-level decision. |
| [BENCHMARK_ADJUDICATION_TEMPLATE.yaml](/Users/sakura/RAG/BENCHMARK_ADJUDICATION_TEMPLATE.yaml) | Material-disagreement resolution and outcome. |
| [BENCHMARK_CALIBRATION_TEMPLATE.yaml](/Users/sakura/RAG/BENCHMARK_CALIBRATION_TEMPLATE.yaml) | Independent baseline lock plus case calibration disposition. |
| [BENCHMARK_48_CASE_DRY_RUN_PLAN.csv](/Users/sakura/RAG/BENCHMARK_48_CASE_DRY_RUN_PLAN.csv) | Coverage-first protocol rehearsal slots. |

The required transition is:

```text
source candidate → authoring record → independent review → adjudication
→ calibration under a new lock → source/question freeze rehearsal → blind package rehearsal
→ dry-run findings → Blueprint/protocol revision (if needed)
```

No step can replace review with generator output, turn unavailable evidence telemetry into zero, or equate an unsealed dry-run record with a release case.

# Frozen Decisions

1. Human Core is the two-domain combination in §1.2, with the sealed/internal/prohibited source policy in §1.4.
2. EN 72 is the primary comparative slice; ZH 24 is an independently reviewed exploratory coverage slice.
3. Gold/MSES is canonical-source-bound and supports alternative, partial, supporting and conflicting evidence only in the authoring record for now.
4. `ambiguous` and `conflicting_unresolved` remain `diagnostic_only`; they do not enter formal accuracy or abstention aggregates.
5. The six baseline roles, model artifacts, LightRAG profiles, prompt/seed/config lock fields and case dispositions are fixed by this protocol.
6. The 96-case matrix has **NO MATRIX CHANGE** before empirical dry-run calibration.

# Remaining Open Questions

1. Which concrete sealed-eligible documents meet the recommended two-domain policy? This is a source-selection task, not an authorization to author cases yet.
2. Which versioned independent reference harness will implement `bm25_v0`, `dense_v0`, `no_retrieval_llm_v0` and `oracle_evidence_llm_v0`, and what are its immutable revision/tokenizer/preprocessing digests?
3. What future Platform scoring contract should represent `needs_review` after v0 diagnostic observation proves the construct useful?
4. What public/sealed file layout can carry the authoring record without prematurely changing the production Bundle schema?

# Matrix Changes

**NO MATRIX CHANGE.** The existing 96-case plan is retained exactly. The justification and before/after totals are in §7.

# 48-case Dry Run Entry Criteria

See §8. The immediate blocker is a checksum-verified independent calibration reference-harness lock; this cannot be substituted with the historical Golden Smoke configuration.

# Protocol Freeze Gate

**PROTOCOL FREEZE: BLOCKED** for execution, not for measurement design.

The authoring/review/MSES/answerability/source-policy protocol is frozen. A 48-case dry run must remain blocked until the standalone calibration reference-harness revision, tokenizer/preprocessing digest and the resulting independent calibration-lock checksum are recorded and verified. This prevents a non-reproducible “baseline by name” from entering the first authoring exercise.
