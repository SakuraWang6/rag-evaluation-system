# BENCHMARK BLUEPRINT V0

Status: definition proposal only; no production schema, generator, DatasetDraft, Platform, Question generator, Gold generator, or legacy data-service code is changed by this document.

Evidence base: [DATA_BENCHMARK_CURRENT_STATE.md](/Users/sakura/RAG/DATA_BENCHMARK_CURRENT_STATE.md). In particular, this Blueprint treats `memory_data_service` as a useful legacy synthetic rendering capability, not as the definition of what a benchmark should measure.

Design map: [BENCHMARK_BLUEPRINT_V0.drawio](/Users/sakura/RAG/BENCHMARK_BLUEPRINT_V0.drawio). It depicts the proposed authoring, review, calibration and seal sequence; it is a target workflow, not current Platform behaviour.

## 1. Benchmark purpose

### Purpose

The benchmark measures how well a RAG system answers document-grounded questions **within a declared document/task distribution**, and which pipeline capability explains success or failure:

- retrieval of all required evidence;
- ranking and selection of evidence under competition;
- composition of independent evidence versus genuinely dependent multi-hop evidence;
- reasoning over text, structured objects and authority/version rules;
- resistance to semantically plausible distractors and stale information;
- calibrated abstention or escalation when the corpus does not support a stable answer;
- answer grounding in minimal sufficient evidence; and
- handling of rich-document structures when the task actually requires them.

This is not a benchmark of “can a system find a sentence in a simple document.” It is also not a claim that one score represents every real-world RAG deployment.

### Measurement principle

Each case is described along independent axes. Retrieval difficulty and reasoning difficulty are separately labelled and reported. A question that needs two distant passages but no transformation is retrieval-hard/reasoning-easy; a one-paragraph calculation can be retrieval-easy/reasoning-medium. Neither may be relabelled as broadly “hard” without those axes.

The reporting unit is a case and a declared slice, not an unqualified global aggregate. Any overall summary is descriptive only and must be accompanied by its portfolio, language, modality, retrieval-difficulty and reasoning-difficulty breakdowns.

## 2. Benchmark claims

### Supported claims

Subject to a frozen Bundle, model/configuration identity, identical case selection and the Platform’s comparability rules, the benchmark may support these conclusions:

1. **Within-suite relative comparison.** Compare retrieval/ranking configurations of the same RAG system, including LightRAG Legacy versus Enhanced, on the declared v0 distribution.
2. **Answer-level comparison.** Compare systems’ answer accuracy, grounding and answerability behaviour by task slice, language and source portfolio.
3. **Pipeline diagnosis.** Where an adapter exposes a retrieval/final-context stage, relate evidence recall/rank/coverage to answer outcomes and locate retrieval, ranking, evidence-selection or generation failures.
4. **Failure-mode analysis.** Identify relative strengths and weaknesses for long-distance retrieval, multi-evidence composition, authority/version resolution, table operations, rich-document structure and abstention.
5. **Controlled causal diagnostics.** In semi-synthetic and synthetic slices only, estimate the effect of a declared manipulation such as entity duplication, evidence distance, stale version or table layout while holding the source scenario fixed.
6. **Calibration findings.** Report whether simple lexical/dense/no-retrieval/oracle-evidence baselines expose shortcut, annotation or scorer defects before sealing.

### Unsupported claims

The benchmark must not be used to claim:

1. that a system represents “all real-world RAG” or all domains, users, languages or document types;
2. that synthetic diagnostics alone prove general RAG capability;
3. that one aggregate score is a complete ordering of RAG systems;
4. that a non-observable retrieval stage is equivalent to an observed stage, or that unavailable telemetry is zero retrieval;
5. that a score gap is causal unless the compared change and all other conditions were frozen by design;
6. that a small v0 predicts production safety, legal/medical reliability, fairness or human usefulness without separate evaluation; or
7. that success on a sealed set proves freedom from benchmark contamination or training-data exposure.

## 3. Target task taxonomy

### Design rule

The taxonomy is compositional. Every case has exactly one **primary task archetype** for sampling and reporting, plus labels on five axes below. This prevents the old failure mode where `table` or `multi_hop` simultaneously meant modality, retrieval pressure and reasoning difficulty.

### Core v0 axes

| Axis | Core v0 labels | Why it is separate |
| --- | --- | --- |
| Retrieval route | `single_semantic`, `lexical_confusable`, `long_distance`, `cross_section`, `cross_document`, `authority_bearing` | Defines how evidence must be found, not how it is used. |
| Evidence composition | `single`, `independent_multi`, `dependent_chain`, `alternative_path`, `conflict_set`, `partial_only` | Defines what evidence is sufficient and whether evidence items depend on one another. |
| Reasoning operation | `direct_extract`, `comparison`, `aggregation`, `temporal_authority`, `conditional`, `relation_chain` | Defines transformation/logic after retrieval. |
| Structured content | `none`, `table_filter`, `table_compare_aggregate`, `cross_table`, `figure_caption_text`, `equation_reference` | Defines whether a document object is semantically necessary. |
| Answerability | `answerable`, `partially_supported`, `ambiguous`, `conflicting_resolvable`, `conflicting_unresolved`, `unanswerable`, `plausible_unsupported` | Separates lack of support from ambiguity and resolvable authority conflict. |
| Context pressure | `near`, `cross_section`, `cross_document`, `dense_distractors`, `repeated_entity`, `stale_version`, `near_duplicate` | Records competing context; it is not inferred from page count. |

`direct_extract` remains in v0 only as a labelled control slice. It is not the benchmark’s dominant task. A `table_cell` lookup without filtering, ambiguous headers or a reasoning operation is not sufficient as a primary v0 table task.

### Primary task archetypes in v0

The planned primary archetypes are listed in [BENCHMARK_V0_CASE_MATRIX.csv](/Users/sakura/RAG/BENCHMARK_V0_CASE_MATRIX.csv). They cover:

- semantic and lexical-confusable single-evidence retrieval;
- long-distance, cross-section and cross-document retrieval;
- independent multi-evidence synthesis and dependent relation chains;
- comparison, aggregation, temporal/version authority and conditional reasoning;
- table filtering and table comparison/aggregation/cross-table operations;
- figure/caption/text and equation/reference relationships; and
- answerable controls, partial support, ambiguity, unresolved conflict, target-attribute absence and plausible-but-unsupported requests.

### Explicitly deferred from v0

V0 does not claim broad coverage of OCR noise, multilingual translation equivalence, complex merged-cell tables, charts requiring visual estimation, handwriting, legal interpretation, multi-turn conversation, agentic browsing, or high-stakes professional judgment. These are candidates for later benchmark families only after their construct and annotation policies are defined.

## 4. Retrieval difficulty model

Retrieval difficulty is a property of locating the minimal sufficient evidence, before reasoning over it. It is recorded as a profile, then binned as Easy, Medium or Hard using the operational rules below.

### Retrieval difficulty factors

| Factor | Observable annotation/calibration field |
| --- | --- |
| Lexical overlap | Language-appropriate content-token overlap between question and required evidence; inspect answer, entity and identifier leakage separately. |
| Semantic confusability | Number and embedding/reranker similarity of non-Gold passages that plausibly answer the question. |
| Evidence rank competition | Gold constituent ranks under frozen BM25 and dense retrieval calibration baselines. |
| Evidence distance | Same block, different section, distant section, or different document; record canonical-token/section distance rather than pages. |
| Entity duplication | Number of same-name, alias or near-name entities carrying competing attributes. |
| Document scope | Number of source documents that contain necessary versus distractor evidence. |
| Evidence cardinality | Number of required evidence items and whether each is independently retrievable. |
| Context pressure | Dense distractors, stale versions, near duplicates, repeated templates or contradictory records. |

### Operational bins

| Bin | Retrieval rule |
| --- | --- |
| Easy | One required evidence item, same canonical section, no semantically plausible competing passage, one document, and no entity/authority ambiguity. Exact lexical match is permitted only for the small control slice. |
| Medium | At least two retrieval-pressure factors: paraphrase or moderate lexical mismatch; 2–4 plausible competitors; cross-section distance; repeated entity/alias; two independently required evidence items; or a cross-document join with unambiguous identities. |
| Hard | At least three retrieval-pressure factors, including one of semantic confusability, stale/near-duplicate authority competition, dense distractors, or ambiguous aliases. It must also contain distant/cross-document evidence or multiple independently required items. At least one simple calibration baseline should face material rank competition while an oracle-evidence answer model can solve the case. |

Pages are never a difficulty label. A 20-page document may contain an Easy same-section lookup; a two-page document may be Hard if aliases, authority and evidence competition are genuine.

## 5. Reasoning difficulty model

Reasoning difficulty is defined after the required evidence is available. It is not increased merely because evidence is in multiple spans.

### Reasoning fields

- `step_count`: number of ordered inferential/transformational steps after evidence retrieval;
- `operation`: direct extraction, comparison, aggregation, temporal/authority, conditional or relation chain;
- `dependency`: independent evidence, ordered dependent chain, or conflict resolution;
- `synthesis`: one value, composed answer, computed value, qualified answer or escalation;
- `ambiguity_state`: none, resolved by an explicit authority rule, or unresolved.

### Operational bins

| Bin | Reasoning rule |
| --- | --- |
| Easy | `step_count=0`: direct extraction or a clearly labelled structured lookup. No calculation, comparison, authority choice or unresolved interpretation. |
| Medium | One explicit operation, or composition of independent evidence into a requested answer format. Examples: compare two values, sum a stated set, apply one clear condition, or filter a table using an unambiguous header. |
| Hard | Two or more ordered dependent steps; a relation chain with a necessary intermediate result; temporal/authority resolution between conflicting records; cross-table aggregation; or an answerability decision based on materially incomplete/ambiguous/conflicting evidence. No single passage may directly state the final answer. |

An independent two-evidence question may be retrieval-hard but reasoning-easy. A table aggregation may be retrieval-easy but reasoning-medium or hard.

## 6. Evidence model

### Minimal Sufficient Evidence Set (MSES)

For every answerable case, Gold records one or more **Minimal Sufficient Evidence Sets**. An MSES is the smallest set of source-level evidence that supports the accepted answer under the case’s authority/normalization rules.

```text
Case C may have alternatives: MSES-1 OR MSES-2
MSES-1 = Evidence A AND Evidence B
MSES-2 = Evidence C
```

Evidence classes are:

| Class | Meaning |
| --- | --- |
| Required | Must be present for that MSES to support the answer. |
| Alternative | Supports the same answer via a different sufficient route. One complete MSES is enough. |
| Supporting | Helps interpretation or answer phrasing but is not necessary. |
| Partial | Relevant but insufficient for the requested claim; it must not be credited as complete evidence. |
| Conflicting | Supports a different plausible answer or stale state. It is used to test authority/answerability, not counted as required Gold for the resolved answer. |

### Multi-evidence and multi-hop rule

A case is **multi-evidence** when two or more required evidence items are needed. It is **multi-hop** only when the annotation contains an explicit dependency graph:

```text
Evidence A → intermediate relation/value R → Evidence B → answer
```

The reviewer must demonstrate that removing A, B, or R prevents derivation of the final answer, and that no allowed single canonical block directly states it. Co-located spans, or two facts merely formatted into one answer, are independent multi-evidence rather than multi-hop.

### Locator and chunk-alignment principle

Gold is anchored to immutable canonical source spans/structured witnesses, not to one system’s chunk IDs. Each adapter should map returned evidence to source provenance where available; evaluation can then judge overlap with an MSES despite different chunking schemes. A case also records its expected retrieval granularity (block, table row, figure/caption, section or document). This avoids both legacy fact-ID coupling and a false requirement that all RAG systems use the same chunks.

### Design delta, not an implementation request

The present Platform validates one Gold-evidence set structurally. Alternative MSES paths, partial/supporting/conflicting evidence roles, dependency graphs and `needs_review` behaviour are Blueprint requirements to decide and review before any future schema work. They are not silently assumed to exist today.

## 7. Answerability, abstention and escalation model

| Label | Corpus condition | Required system behaviour | Scoring intent |
| --- | --- | --- | --- |
| Answerable | At least one MSES supports one stable accepted answer. | Answer with grounding; include required qualifiers/units. | Answer and evidence completeness. |
| Conflicting, resolvable | Competing records exist, but source policy/date/authority yields one MSES. | Answer the resolved current/authoritative value and avoid stale value. | Authority resolution, not generic refusal. |
| Partially supported | Some related evidence exists, but it cannot establish every requested attribute/relation. | Abstain from the unsupported requested conclusion; may state the supported boundary if the response policy permits. | Do not reward completion by inference. |
| Unanswerable | Related entities/evidence are present but target attribute or relation is absent. | Abstain. | Reject plausible hallucination. |
| Plausible but unsupported | World knowledge or a familiar pattern suggests an answer, but corpus evidence does not. | Abstain. | Document grounding over prior knowledge. |
| Ambiguous | More than one source-supported interpretation remains because the question or source lacks a resolution rule. | `needs_review`, explain ambiguity rather than choose arbitrarily. | Calibrated escalation. |
| Conflicting, unresolved | Source records materially conflict without an authority/time rule. | `needs_review`. | Preserve uncertainty and surface conflict. |

`needs_review` is a benchmark outcome category, not an answer string. Its detailed implementation/scoring contract is intentionally deferred. V0 should not force such cases into either correct-answer or ordinary-abstain metrics.

Negative cases must contain related, tempting material. They must not use an explicit source sentence equivalent to “the requested information does not exist.” The evidence must make a wrong answer plausible while still failing the MSES rule.

## 8. Dataset portfolio

| Portfolio | V0 target | Construction role | Claims it can support | Claims it cannot support |
| --- | ---: | --- | --- | --- |
| Human Core | 36 cases | Licensed or manually curated realistic documents; human-authored questions/Gold. | Within-domain task relevance, natural ambiguity and answerability behaviour. | Broad real-world coverage or parser stress at every modality. |
| Semi-synthetic Scale | 28 cases | Curated parent source plus controlled variants of distance, distractors, aliases, versions or wording. | Directional effect of the declared manipulation; controlled retrieval/ranking analysis. | Untouched real-world prevalence. |
| Synthetic Diagnostics | 16 cases | Rebuilt semantic scenarios rendered through rich DOCX/table/figure/equation/layout capability. | Parser/structure/table/figure/equation mechanisms under controlled variables. | General answer quality by itself. |
| Adversarial Challenge | 16 cases | Deliberately confusable near-duplicates, stale values, aliases, conflicts and partial support. | Failure analysis and calibrated abstention/authority robustness. | A representative average score. |

All four portfolios are scored and separately reported. Their counts are not mechanically equal because Human Core requires more natural answerable/multi-evidence coverage, while Synthetic and Adversarial cases are diagnostic slices rather than a claim of prevalence.

## 9. V0 distribution matrix and recommended size

### Candidate scales

| Candidate | Planned cases | Intended use | Limitation |
| --- | ---: | --- | --- |
| Small protocol pilot | 48 | Validate author/reviewer workflow, MSES notation, calibration harness and seal mechanics. | Too few cases to cover all v0 slices with meaningful case-level analysis. |
| Medium sealed v0 — recommended | 96 | First comparative benchmark: 36 Human, 28 Semi-synthetic, 16 Synthetic, 16 Adversarial; roughly 30–36 source documents; 72 English / 24 Chinese cases with no translation-pair assumption. | Still a pilot release; report slices and uncertainty, not a leader board. |
| Full pilot | 160 | Expand each selected slice, run stronger calibration and estimate stability across more document families. | Premature before v0 review/calibration identifies invalid constructs. |

### Recommended v0

Adopt the **96-case Medium sealed v0**. It is deliberately small enough that every case receives independent review and calibration evidence, but substantial enough to avoid a four-example-per-category smoke-test pattern. The detailed plan is the companion [CSV matrix](/Users/sakura/RAG/BENCHMARK_V0_CASE_MATRIX.csv); it defines planned distributions only and creates no actual case.

V0 reporting must stratify at least by primary archetype, retrieval difficulty, reasoning difficulty, modality, answerability, source portfolio and language. English is the primary comparative slice; Chinese is an explicitly reported exploratory/coverage slice until enough independently reviewed Chinese cases exist. Do not treat cross-language results as translation-equivalent.

## 10. Required annotation record

Each proposed case must include:

| Field | Requirement |
| --- | --- |
| Question | Natural wording and requested answer form; no answer, Gold, authority or generator identifier cue. |
| Accepted answer(s) | Canonical answer plus approved alternatives, units, locale and answer normalization rule. |
| Answerability label | One label from the model above and the required answer/abstain/needs-review behaviour. |
| MSES | Required evidence items, their canonical locators/witnesses, and any alternative complete MSES. |
| Supporting/partial/conflicting evidence | Separate from MSES, with an explanation of why it is insufficient or conflicting. |
| Task taxonomy | Primary archetype plus all axis labels. |
| Difficulty | Retrieval profile/bin and reasoning profile/bin with an author rationale. |
| Dependency graph | Mandatory for any claimed multi-hop case. |
| Source provenance | Source type, rights/license, language, canonicalization/version and variant lineage. |
| Author rationale | Why retrieval is needed, why reasoning is needed, expected shortcut failure and intended diagnostic value. |

Generator output, object graphs and scenario metadata may propose an annotation; they are never accepted Gold without the same review process.

## 11. Review and adjudication protocol

```text
Curator/Author
  → independent Reviewer
  → disagreement record
  → Adjudicator decision
  → calibration gate
  → source/questions freeze
  → seal
```

### Roles and gates

1. **Author:** creates the source/case record, MSES and rationale; cannot self-approve.
2. **Independent reviewer:** independently checks answerability, answer normalization, MSES sufficiency, alternative paths, taxonomy, difficulty and natural wording. Every v0 case is reviewed.
3. **Disagreement:** record the exact field, competing values, evidence cited and whether a source/question rewrite is needed. Do not collapse disagreement into a Boolean approval.
4. **Adjudicator:** resolves material disagreement; may approve, revise and re-review, or reject. Material disagreement includes answerability, accepted answer, any required evidence, claimed multi-hop dependency, authority rule or primary taxonomy.
5. **Seal reviewer:** confirms all required records, calibration decisions, data rights and public/sealed paths are complete. This role does not edit a sealed case.

V0 uses one author, one independent reviewer and adjudication for every disagreement. A later scale-up may add dual independent annotation, but not by reducing v0’s mandatory independent review.

## 12. Baseline calibration plan

### Required baselines before sealing

| Baseline | Purpose | Do not use it as |
| --- | --- | --- |
| BM25 | Detect lexical shortcuts and expected rank competition. | A measure of final RAG quality. |
| Dense retrieval | Detect semantic shortcut/semantic confusability and complement BM25. | A substitute for answer evaluation. |
| No-retrieval LLM | Detect questions answerable from world knowledge, wording, ID/answer leakage or benchmark pattern. | A grounded answer system. |
| Oracle-evidence LLM | Test whether a complete MSES and normalization rule are sufficient to answer. | A realistic end-to-end RAG baseline. |
| Current LightRAG Legacy | Establish historical system behaviour and regressions. | The Gold standard. |
| Current LightRAG Enhanced | Establish expected discrimination from current improvements. | The winner or a release criterion. |

Use frozen prompts/models for calibration and retain case-level output. Run stochastic answer baselines across at least three deterministic seed/prompt realizations where applicable; a single lucky answer is not evidence of a shortcut.

### Calibration dispositions

| Finding | Disposition before seal |
| --- | --- |
| Answer appears in question, ID, title, visible cue or source priority instruction | Reject or rewrite. This is a hard leakage failure. |
| Independent reviewer cannot recover a stable MSES | Reject or rewrite. |
| Oracle-evidence LLM fails to answer correctly in at least 2 of 3 controlled trials, after checking the scorer | Fix annotation/source/question or remove. |
| No-retrieval LLM repeatedly answers correctly across models/trials for an evidence-required case | Inspect for world-knowledge, wording or template shortcut; rewrite/remove unless it is an explicitly labelled easy control. |
| Hard/paraphrase/adversarial slice has no meaningful BM25 or dense rank competition | Add/repair distractors, aliases, distance or case design; do not label it hard. |
| One baseline fails because answer/evidence format is ambiguous or scorer rejects a defensible answer | Repair normalization/accepted answers and re-review. |
| All systems fail while oracle-evidence succeeds and reviewers agree on MSES | Retain as a targeted challenge only if the failure mechanism is intended and reproducible; do not let it dominate headline reporting. |
| Systems do not differ in the intended diagnostic behaviour after pilot, or results are unstable across reruns | Reclassify, modify or remove; a v0 case needs explanatory value, not merely a question. |

The calibration output defines the benchmark’s difficulty profile; it does not select a winner. Any final threshold or model identity must be frozen with the release record, not tuned after formal runs begin.

## 13. Leakage and quality gates

### Automatic pre-review gates

Every case fails or is flagged when any applicable check detects:

- answer-in-question, answer-in-ID, or answer hidden in a filename/title;
- `Gold`, `FACT`, `authoritative`, `DISTRACTOR`, “gold row,” or equivalent source-visible priority cues;
- source-visible instructions explaining which record is correct;
- fixed question-wrapper or template-family similarity above the declared duplicate threshold;
- near-duplicate questions or evidence passages outside an explicitly declared semi-synthetic variant family;
- excessive lexical overlap where the task is labelled semantic/paraphrase/hard;
- an explicit distractor label or generated ordinal/page/ID that directs retrieval;
- answer/string evidence that is not backed by a canonical source locator/witness;
- a claimed multi-hop case with a single block that directly states the final answer; or
- a negative case whose source directly says the target information is absent.

These checks must be language-aware. For Chinese, use suitable segmentation/character n-gram and human review rather than blindly applying English word-token thresholds.

### Mandatory human quality gates

The reviewer/adjudicator records an explicit pass/fail rationale for:

- realism and natural question wording;
- MSES sufficiency and absence of accidental alternative answer paths;
- true retrieval necessity;
- true reasoning necessity and multi-hop dependency, when claimed;
- answer completeness and normalization;
- ambiguity/conflict/authority interpretation;
- distractor plausibility without answer-label cues; and
- appropriateness of the claimed difficulty and primary archetype.

## 14. Blind and seal protocol

Reuse the existing Platform blind protocol as the release boundary. The v0 conceptual layout is:

```text
public/
  source_documents/
  questions_public/
  permitted_case_metadata.jsonl
  public_manifest.json

sealed/
  gold_answers.jsonl
  gold_evidence.jsonl
  canonical_witnesses/
  scorer_config/
  review_and_adjudication_records/
  calibration_decisions/
  checksums.json
  blind_protocol.json
```

The public tree may identify the question, permitted task labels and source provenance, but may not reveal Gold locators, canonical witnesses, answerability outcome, author rationale that gives away the answer, or review/adjudication content. The sealed tree contains those materials and is not exposed to experiment developers or adapter workers.

The required release ordering is:

```text
source/questions frozen
  < model/config/comparison/analysis frozen
  < formal runs started and completed
  < Gold reveal
```

The existing blind-layout/timeline validation should be used when implementation begins. This Blueprint adds review/adjudication and calibration records to the sealed conceptual package; it does not alter the current protocol or schema today.

## 15. Legacy data-service disposition

| Disposition | Legacy components | Decision |
| --- | --- | --- |
| KEEP | DOCX/table rendering; figure/equation rendering; notes/cross-reference/layout controls; deterministic seeds; resource guards; generator provenance | Preserve as optional synthetic-diagnostic infrastructure after a future semantic redesign. |
| REWRITE | Semantic scenario generation; document language/style realization; question proposal; Gold/MSES annotation assistance; object-to-canonical evidence mapping; distractor/alias/stale-version construction; dependent multi-hop generation; post-render validation | Rebuild from the Blueprint, using source freeze and independent annotation rather than generator truth. |
| RETIRE | Visible `FACT-*` identifiers; Gold-row markers; “authoritative gold”; `DISTRACTOR-*`; priority instructions; fixed question wrappers; generator fact ID as formal evidence locator; generated answer as automatic Gold | Exclude from any benchmark source, public metadata, scorer or authoring workflow. |

No integration decision is authorized before the Blueprint, calibration gates and v0 annotation protocol are accepted. The first question is not “how to import legacy oracle data”; it is “which controlled synthetic diagnostics are useful after the construct has been specified.”

## 16. Known limitations

1. V0 has no released cases yet; counts are a plan rather than evidence of discrimination.
2. The proposed `needs_review` outcome, alternative MSES paths and rich evidence roles exceed today’s narrow Bundle/DatasetDraft representation; this Blueprint does not assume they are implemented.
3. 24 Chinese cases are meaningful coverage but not sufficient for language-equivalence claims.
4. Human Core realism is bounded by selected domains and source licensing; it does not represent all RAG use.
5. Calibration baselines can themselves be contaminated or weak; their role is defect discovery, not objective truth.
6. Rich document rendering may test parser quality and retrieval jointly. V0 must report such cases as structured-document tasks, not attribute all failure to retrieval.
7. A sealed release reduces direct access to Gold but cannot eliminate model pretraining or indirect contamination risk; provenance and release discipline remain necessary.

# Top Design Decisions

1. Measure a **capability profile**, not a global RAG score.
2. Label retrieval difficulty and reasoning difficulty independently.
3. Define Gold as independently reviewed MSES anchored in canonical source material, never generator output by default.
4. Separate Human, Semi-synthetic, Synthetic and Adversarial portfolios, and restrict their claims accordingly.
5. Treat unresolved ambiguity/conflict as `needs_review`, distinct from ordinary abstention.
6. Use a 96-case sealed v0 with full review and calibration before scale, rather than immediately producing hundreds of synthetic cases.

# Open Questions

1. Which two to three document domains should Human Core represent in v0, and what source-license/provenance constraints apply?
2. Should Chinese remain an exploratory slice in v0, or should v0 launch English-only and add Chinese as a separately calibrated release?
3. What adapter-level source-provenance interface is minimally required to score evidence across different chunking strategies without privileging one system?
4. How should `needs_review` be represented and scored alongside the current Platform answer/abstain model without conflating system uncertainty with evaluator uncertainty?
5. Which LightRAG Legacy/Enhanced configurations and model locks are stable enough to serve as calibration baselines?

# Recommended v0 Scope

Seal **96 cases** after review and calibration: 36 Human Core, 28 Semi-synthetic Scale, 16 Synthetic Diagnostics and 16 Adversarial Challenge. Use roughly 30–36 source documents, 72 English / 24 Chinese cases, no translation-pair assumption, and no aggregate leader-board claim. Publish all results by capability slice and retain the 48-case protocol pilot only as a pre-seal workflow rehearsal, not as a benchmark.

# Next 5 Actions

1. Approve or revise this Blueprint’s supported claims, v0 taxonomy, answerability policy and 96-case scope.
2. Select Human Core domains, source provenance/licensing rules and the English/Chinese release stance.
3. Define an annotation worksheet and review/adjudication ledger that can capture every required case field without changing production schemas yet.
4. Define frozen calibration baseline identities, prompts and case-level acceptance/rewrite rules.
5. Run a 48-case **protocol-only** dry run through author → review → calibration → blind seal; revise the Blueprint from those findings before authoring the 96 sealed cases.
