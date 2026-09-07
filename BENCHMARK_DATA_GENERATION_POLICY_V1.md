# Benchmark Data Generation and Admission Policy v1

Date: 2026-08-29  
Scope: Benchmark Data Layer P1 — document/case/Gold admission, calibration reference workflow, and an independent test Portfolio.  No benchmark question, Gold, Bundle, or production evaluation configuration was generated or changed.

## Status

`src/rag_eval/datasets/admission.py` establishes versioned policy contract `benchmark-data-generation-policy/1.0`.  It is a pre-authoring/admission layer over the existing Canonical Data Model 1.0, Authoring Ledger/Gold lifecycle, Formal Validator and Portfolio contracts; it is not a second Case, Gold, validation, scoring, or RAG schema.

The fixed calibration reference-process digest is:

`878507753c5e434e3392d8308e6de7967854e285cbfa4f33eb38f0c9223f807a`

The newly created independent Portfolio is:

`benchmark-v0-held-out-96`  
Contract digest: `95e4aaf8becf87b50fd513b556a8b24bcba30528e718fa757dd0c75281b31394`

It is a plan only: it contains no selected document, Case, Gold, failure knowledge, Bundle or release.

## 1. Document source admission

Every `DocumentSourceRecord` is revisioned and records:

- stable source-document ID and source-family ID;
- DOCX document type (P1 remains scoped to the existing DOCX canonicalizer; it does not introduce PDF support);
- content summary, immutable source file digest and canonical-document digest;
- parser/canonicalizer identities and configuration digest;
- parsing completeness, structural completeness and evidence-locator completeness using Canonical `complete / partial / unsupported / missing` states;
- a structured comparison against every registered development source family, including method, corpus digest, score where determined and `distinct / near_duplicate / exact_duplicate / undetermined` disposition;
- independent-test eligibility and the admission decision; and
- actor, reason, parent revision and record digest.

A source may become an admitted formal Gold source only when parsing, structure and evidence locator status are all `complete`.  Partial, unsupported, missing or unlocatable content fails closed.  An independent-test source must additionally belong to a `held_out` source family and compare as `distinct` from every registered development family.  Exact/near duplicates fail; an undetermined semantic similarity result is explicitly `HUMAN_REVIEW_REQUIRED`, never automatic PASS.

Source family records are immutable and typed as `development`, `held_out` or `reference_diagnostic`.  Source/document registration, calibration locks and every source/case preflight report are stored outside Bundle and Gold files.  Records are append-only revisions and reports are content-digested.

## 2. Case and Gold admission

A planned slot cannot become a Case by import.  Before authoring, a case must be bound to exactly one formal Portfolio slot.  The slot supplies the existing v0 typed primary task, source type, language, evidence composition, modality, answerability and independently labelled retrieval/reasoning difficulty.  No free-tag replacement taxonomy is introduced.

The admission preflight consumes existing `CaseRevision`, independent `GoldRevision`, `CanonicalDocument`, source record and Portfolio slot.  It checks:

- canonical source digest and Portfolio-slot binding;
- formal Case/Gold lineage and complete canonical locator reachability for every Gold evidence item;
- MSES clause-level necessity checks, preserving OR alternatives rather than treating alternative evidence as redundant;
- a typed dependency graph when a slot is multi-hop;
- negative/unanswerable scope backed by complete canonical evidence and rationale;
- answer string leakage from the question;
- exact/near question duplication and, for held-out cases, comparison against development cases;
- source-family isolation and a passed source-admission report before a held-out actualization; and
- independent human admission checklist requirements.

Questions must be authored from verified canonical evidence backwards, be natural, not rely on object IDs/file names/manual hints, and have answers fully document supported.  A model failing to answer is never evidence that a case is unanswerable: abstention Gold requires an explicit bounded negative scope and evidence rationale.

Gold continues to use the existing formal `GoldPayload`, MSES paths, evidence roles, dependency graph, revision, review, approval, invalidation and supersession contracts.  This policy adds only evidence-necessity and admission-review audit records; it does not create a duplicate Gold source of truth.

## 3. Model, program, and human responsibilities

Permitted model-assisted uses are typed and limited to:

- candidate-question generation;
- question rewrite;
- candidate answer/evidence suggestion;
- distractor suggestion; and
- quality assistance.

`ModelAssistanceRecord` captures model/version/configuration/seed/output digest and has an enforced `proposal_only = true` state.  Model-origin Case/Gold cannot clear admission without independent review.  No model output is written automatically as approved Gold.

Programs decide structural/digest/provenance checks, duplicate heuristics, source-family isolation, evidence reachability, MSES shape, dependency closure and direct answer leakage.  Programs return an auditable report with `PASS`, `FAIL`, `HUMAN_REVIEW_REQUIRED` or `NOT_APPLICABLE`; unresolved semantic similarity, naturalness, ambiguity or plausible alternative answers never become automatic PASS.

Humans decide source admissibility, question naturalness, ambiguity, answer correctness, evidence sufficiency/minimality, alternative-answer risk and difficulty-label reasonableness.  Normal cases require one complete independent admission checklist.  Multi-hop, unanswerable/negative-scope, conflicting evidence, adversarial, alternative-MSES, table and rich-structure cases require two distinct independent checklist reviewers.  Unresolved disagreement cannot freeze.

## 4. Difficulty and calibration

Retrieval difficulty remains an annotation of data properties: lexical overlap, evidence location/distance, competing similar evidence, cross-section/document pressure and evidence count/composition.  Reasoning difficulty remains an annotation of the post-retrieval operation: single fact, conditional, comparison, aggregation, independent composition or ordered multi-hop dependency.  A LightRAG result or any other single RAG outcome is not a difficulty label.

The fixed versioned reference process uses only the Protocol roles:

1. `bm25_v0` for lexical/rank competition;
2. `dense_v0` for semantic/rank competition;
3. `no_retrieval_llm_v0` for shortcut checks; and
4. `oracle_evidence_llm_v0` for MSES sufficiency/normalization checks.

Its immutable seed policy is `20260824`, `20260825`, `20260826`.  A usable `CalibrationReferenceLock` must record the reference harness ID/revision/digest, tokenizer/preprocessing digest, every baseline configuration digest, required prompt digests, actor and lock digest.  The contract prohibits using calibration outputs to edit Gold, choose Gold evidence, or redefine difficulty from a reference system result.

The **process is locked**, but this repository still has no actual checksum-verified independent reference-harness implementation/lock to register.  Therefore calibration may not be claimed operationally ready yet.

## 5. Independent test Portfolio

The development dry-run remains unchanged as `benchmark-v0-dry-run-48`: 48 development-only planned slots.  It was not rewritten or relabelled.

`benchmark-v0-held-out-96` is a separate formal Portfolio mechanically derived from the existing unchanged 96-case matrix.  It preserves its capability taxonomy and proportions:

| Dimension | Held-out planned allocation |
| --- | ---: |
| Total | 96 |
| Human / Semi-synthetic / Synthetic / Adversarial | 36 / 28 / 16 / 16 |
| English / Chinese | 72 / 24 |
| Source family | `held_out_isolated_pending_admission` for all 96 slots |

Every held-out slot remains `planned` and requires an actual isolated `source_family_id` plus a successful source-admission report digest before it may be actualized.  It never accepts a development source family, near duplicate, or unverified source record.  Case/Gold/failure knowledge must remain isolated, Gold is not exposed before RAG configuration freeze, and once the held-out suite is used for formal validation it must not be used as an iterative tuning target.  These are policy gates, not claims that such data already exists.

## 6. Automatic checks and fail-closed behavior

Implemented rule IDs include:

- `source.parse_structure_locator`
- `source.family_classification`
- `source.family_isolation_and_similarity`
- `source.admission_status`
- `case.source_and_slot_binding`
- `case.gold_lineage`
- `gold.evidence_reachability`
- `gold.mses_minimality`
- `gold.multi_hop_dependency`
- `gold.negative_scope`
- `case.answer_leakage`
- `case.duplicate_and_contamination`
- `model.output_proposal_only`
- `review.independent_admission_checklist`

The policy reports are persisted and digest-verified.  They complement—rather than replace—the Platform’s formal release validator.  A release still requires the existing Formal Validator/Authoring lifecycle checks in addition to this pre-authoring admission policy.

## 7. Tests and verification

Added `tests/rag_eval_platform/test_benchmark_admission_policy.py` covering:

- independent 96-slot Portfolio separation and exact v0 allocation preservation;
- source parse/structure/locator failure, source-family isolation, exact/near duplicate and undetermined similarity handling;
- append-only source record/report persistence;
- immutable complete calibration lock requirements;
- canonical Gold evidence reachability, MSES necessity, multi-hop dependency and answer leakage;
- model proposal/review gating, human-review-required behavior and question contamination checks; and
- enforcement that held-out Portfolio actualization needs source admission linkage.

Full verification:

```text
PYTHONPATH=src .venv/bin/pytest -q
110 passed, 3 skipped, 1 warning
```

## Required answers

1. **What documents may enter a formal Benchmark?** Only admitted DOCX sources with immutable digest/provenance, complete parsing/structure/locators and valid Canonical evidence.  Held-out sources also require isolated held-out family membership and a distinct comparison against every development family.
2. **What questions may become formal Cases?** Only questions bound first to a typed slot, generated from verified evidence, free of answer/internal-ID/file-name cues, structurally validated and independently reviewed.
3. **What is Gold’s minimum admission standard?** Existing independent revisioned Gold plus complete reachable canonical evidence, valid MSES/necessity evidence, required dependency graph or negative scope, no answer leakage and independent review.
4. **What do models, programs and humans do?** Models propose only; programs check objective structure/provenance/contamination and issue audit reports; humans resolve natural-language semantics and approve the full checklist.
5. **How are retrieval and reasoning difficulty defined?** By the existing Blueprint’s separate data-property and post-retrieval-operation axes, never by a single RAG system’s error.
6. **How is held-out contamination prevented?** Isolated family classification, mandatory development-family source comparison, held-out question comparison, no development near duplicates, pre-authoring admission report digest and no Gold exposure before configuration freeze.
7. **Is the fixed calibration reference process locked?** Yes, the versioned process/baselines/seeds/rules are locked.  No, the concrete checksum-verified harness lock is not yet registered because no harness artifact was supplied.
8. **Has an independent test Portfolio been established?** Yes: a separate planned 96-slot `benchmark-v0-held-out-96` Portfolio.  It is not populated and does not modify the 48 development slots.
9. **Are the previous three blockers resolved?** The separate Portfolio/gating blocker is resolved at the contract level.  The operational calibration-harness lock and the real sealed-eligible held-out source-family/document admissions remain unresolved because their factual artifacts have not been provided.  Policy implementation itself is no longer a blocker.
10. **Can the first round of real data Authoring begin?** Not yet for formal benchmark data.  It may begin only after an owner registers a checksum-verified calibration harness lock and admits real source family/document records through these gates.  No code, taxonomy or Gold-lifecycle blocker remains once those external governance inputs are supplied.
