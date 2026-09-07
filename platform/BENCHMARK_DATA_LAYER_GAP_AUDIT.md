# Benchmark / Data Layer Gap Audit

**Audit date:** 2026-08-29  
**Status:** audit complete; implementation deliberately not started  
**Scope:** `rag-eval-platform`, current Authoring and Dataset Bundle code,
`LightRAG/memory_data_service`, `data_generation_v2`, Benchmark Blueprint and
case-matrix artifacts, and the frozen 20-case diagnostic release.

## Executive decision

The Platform has a useful, RAG-neutral **private-DOCX Authoring MVP** and a
sound immutable Bundle 2.0 execution boundary.  It is not yet a complete,
general Benchmark Data Layer.

In particular, the current implementation cannot yet make the following
strong claim:

> A dataset can be authored from any supported raw source, independently
> reviewed, fully versioned and lineage-traced, validated by a formal
> fail-closed pipeline, frozen as a development or held-out release, and later
> reproduced without relying on a RAG runtime or historical generator.

The 20-case Bundle is therefore frozen as a **reference diagnostic /
development set**.  It is not a held-out set and cannot support a general
claim about ranking, context organisation, Evidence Pack, or answer-generation
performance.  No LightRAG production default, Gold, metric, Adapter, or
evaluation contract was changed for this audit.

## Evidence examined

| Area | Primary evidence |
| --- | --- |
| Current Platform contracts and storage | `src/rag_eval/contracts/dataset.py`, `src/rag_eval/datasets/bundle.py`, `src/rag_eval/datasets/drafts.py` |
| DOCX authoring workflow | `src/rag_eval/authoring/{storage,canonical,models,workflow,service}.py`, Authoring API routes |
| Existing product and release evidence | `README.md`, `CURRENT_STATUS.md`, `docs/PRIVATE_DOCUMENT_BENCHMARK_DESIGN.md`, `docs/BENCHMARK_DIAGNOSTIC_EXPANSION_REPORT.md` |
| Formal blind-layout facility | `src/rag_eval/datasets/blind.py`, `docs/BLIND_BENCHMARK_PROTOCOL.md` |
| Legacy generation and evaluation | `LightRAG/memory_data_service/`, `LightRAG/memory_eval_tests/` |
| Blueprint and experimental implementation | `BENCHMARK_BLUEPRINT_V0.md`, `BENCHMARK_PROTOCOL_V0.md`, `BENCHMARK_V0_CASE_MATRIX.csv`, `BENCHMARK_48_CASE_DRY_RUN_PLAN.csv`, `data_generation_v2/` |

Read-only test evidence:

- Bundle, contract, blind-protocol, and evaluation subset: **32 passed**.
- The complete Platform suite cannot collect in the checked-out `.venv` because
  the declared Authoring dependency `lxml` is absent (`ModuleNotFoundError`).
  Five modules fail at collection; this is an environment reproducibility gap,
  not evidence that those tests passed.

## Current architecture and ownership

```text
Raw DOCX
  -> Platform private Authoring workspace
  -> deterministic DOCX canonical records + execution Markdown
  -> target -> question candidate -> answer/evidence resolution -> review
  -> canonical-text / native-docx Bundle 2.0 export
  -> content-addressed Dataset Bundle Store
  -> Adapter Worker -> RAG runtime -> Evaluation / comparison

Legacy synthetic path (not called by Platform)
  request + seed -> DOCX/PDF + facts/questions/objects/relations/oracle
  -> memory_eval_tests / Recall Lab
```

The desired ownership boundary remains correct, but it is presently complete
only at the Bundle-to-Evaluation boundary:

| Owner | Already owned | Still incomplete |
| --- | --- | --- |
| Platform | Bundle registration, Gold used by evaluation, file checksums, DOCX authoring MVP, review records, run artifacts | canonical-data contract, full Gold lifecycle, release/version lineage, Blueprint portfolio and split policy, held-out release workflow |
| Adapter | Runtime request translation and provenance projection | No change required in this phase |
| RAG runtime | Ingestion, retrieval, ranking, generation | Must not receive Authoring or Gold logic |
| Legacy service | Historical synthetic source rendering, synthetic facts/questions/oracle, legacy evaluation compatibility | Must cease being a competing data/Gold/schema authority |

`rag-eval-platform/src` has no import or call to `memory_data_service`.  The
current Platform can already author a DOCX and register a Bundle without
LightRAG or RAG-Anything.  The one optional runtime-representability profile
is diagnostic evidence about a declared execution view; it does not create or
choose Gold.

## Direct answers to the audit questions

1. **Existing data-layer capabilities.** The Platform safely ingests one DOCX
   into a private workspace; creates deterministic source-digest-derived
   canonical records; discovers structure-first targets; separates question
   proposal from answer/evidence resolution; runs basic quality gates; stores
   reviewer actions and approved cases; exports canonical/native Bundle views;
   validates Bundle references, witnesses, locators and checksums; and stores
   registered Bundles content-addressably.  It also has a small manual
   TXT/Markdown `DatasetDraft` path and a blind-layout validator.
2. **Legacy dependency.** No current Platform data-layer operation depends on
   `memory_data_service`.  Legacy exclusively retains rich synthetic document
   rendering, coupled fact/question/oracle creation, its schema 1.x,
   `memory_eval_tests`, and Recall Lab.  Those are historical/generator
   facilities, not current Platform dependencies.
3. **Experimental-only functions.** `data_generation_v2/` and its
   `*_prototype*_output` artifacts implement a separate prototype canonicalizer,
   authoring manifest, validator, exporter, sealed sidecar and blind views.
   They are not imported by Platform, have no Platform API/CLI contract, and
   explicitly report that release criteria are unmet.  Blueprint CSV/YAML
   templates and the Golden Smoke fixture are design/regression artifacts, not
   a production Benchmark authoring workflow.
4. **Missing functions.** The material omissions are listed in the P0/P1/P2
   register below: a formal canonical object-graph contract, Gold as a
   versioned lifecycle entity, a formal validator/report, release lineage,
   typed case/portfolio model, source-format-independent authoring, and an
   actual held-out Bundle.
5. **How the frozen 20-case release was produced.** A private DOCX entered the
   Authoring workspace; it was canonicalized, target/candidate/resolution
   records were reviewed, and the canonical-text view was exported/registered.
   The release combines 4 retained cases with 16 new cases.  The recorded
   workspace has 24 candidates, 27 immutable review actions, 21 approved and
   3 rejected candidates.  One approved historical table-negative candidate
   was excluded because it could not satisfy the formal locator contract.  The
   resulting Bundle ID is
   `d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e`.
   Nineteen released cases are `FULL/PASS`; one is retained as
   `PARTIAL_UNOBSERVABLE/FLAG`.  The private source and Gold are intentionally
   not committed, so repository readers can audit the process record but not
   independently re-inspect its private content.
6. **Independent Authoring workflow.** Yes, within its DOCX MVP scope.  It is
   a real API/service/workspace (`rag_eval.authoring`) with manual, rule,
   local-model and consented remote proposal paths; review is mandatory before
   export.  It is not yet independent *general-purpose* Benchmark Authoring:
   raw formats, canonical relations, Gold lifecycle, release governance and
   portfolio management remain incomplete.
7. **Creating a Bundle without LightRAG.** Yes.  Platform Authoring and Bundle
   registration contain no LightRAG dependency.  Manual `DatasetDraft` and
   direct Bundle registration also work without it.  This statement is limited
   to supported inputs and does not prove that every produced Bundle satisfies
   the future formal authoring requirements.
8. **Raw-document-to-canonical-dataset lifecycle.** Partially.  DOCX has a
   full MVP path; TXT/Markdown has a narrow draft path that bypasses the DOCX
   canonical/review model.  PDF, HTML, existing canonical JSON, multi-file
   collections and other raw formats do not have a common source-ingestion or
   canonical-data contract.  There is no uniform lifecycle across them.
9. **Blueprint implementation.** The Blueprint, Protocol and 48/96 planning
   matrices are detailed design artifacts, but their axes are not normalized
   into Platform schema, authoring UI/API, Bundle manifest, validator or report
   aggregation.  The 20 cases cover only a small diagnostic subset; the
   planned Human/Semi-synthetic/Synthetic/Adversarial and EN/ZH portfolio has
   not been delivered as a formal dataset.
10. **Held-out benchmark.** No.  Repository search found no sealed held-out
    Bundle, no development/held-out release type, and no split lineage that
    prevents case/Gold/failure-knowledge overlap.  Legacy `split=validation`
    means only a generator field; it is not a held-out benchmark protocol.

## Capability assessment

### Dataset Bundle and validation

**Present and useful**

- Bundle 2.0 requires `manifest.json`, source documents, questions, Gold
  answers and Gold evidence; registration calculates a content digest and
  writes a file-hash manifest.
- Schema and loader checks reject duplicate case/Gold IDs, broken document
  checksums, missing answer/evidence references, invalid spans, and broken
  structured locators.  Formal bundles require structured witnesses for
  object/table/page locators.
- The store does not scan legacy run/dataset directories.  Evaluation receives
  only question/case inputs while scoring retains Gold server-side.

**Not sufficient yet**

- Bundle manifest v2 has only `name`, free-form `version`, `created_at`,
  documents and open-ended metadata.  It has no typed dataset identity,
  lifecycle state, split, parent release, lineage edge, generator identity,
  canonical schema digest, validation report digest, reviewer/release record,
  or compatibility policy.
- Content-addressed registration gives immutable *content identity*, not a
  first-class frozen-release record.  A name/version can be reused for
  different Bundle IDs and there is no immutable mapping/history that explains
  a successor release.
- Validation is distributed between Pydantic models, Bundle loading and
  Authoring gates.  It emits exceptions rather than a versioned validation
  report with rule IDs, severity, evidence and input digests.
- It validates referential and locator integrity, not the complete semantic
  requirements: Gold minimality, answer/evidence consistency, ambiguity,
  leakage across a release, cross-reference resolution, source-span fidelity,
  duplicate/near-miss clustering, or unreachable evidence for every declared
  execution view.
- Authoring export writes candidate Bundles but does not make a formal
  validator report a prerequisite of release freeze.  Registration revalidates
  later; formal release creation must validate and seal atomically.

### Canonical data model

**Present**

- Deterministic, source-digest-derived document, section, block, text span,
  table, row, cell, figure, equation, reference and note records with
  structural locators, witnesses and supported/partial/unsupported diagnostics.
- Tables have row/cell coordinates; captions are identified as a block kind and
  may carry an adjacent-object association.  Equations, floating/VML drawings,
  cross-reference fields and notes are deliberately marked partial where
  fidelity is not established.

**P0 gap**

The records are an extraction format rather than a formal Canonical Data Model.
They lack typed, stable and validated relationship fields for `parent`,
`children`, `siblings`, global document order, heading hierarchy/ancestry,
caption-as-object, caption-to-figure relation, cross-reference target,
source-span coordinate system, and explicit provenance for each transformed
field.  A paragraph is currently represented as a generic `block`; text spans
are block-local rather than a document coordinate system.  `page_region` is a
Bundle locator but DOCX canonicalization intentionally produces no page
coordinates.  Rich material is not silently claimed as supported, which is
correct, but there is no structured remediation contract for partial objects.

### Gold evidence lifecycle

**Present**

- Candidate resolution records evidence object IDs, required groups,
  near-miss object IDs and an optional dependency graph before review.
- Gold exported to Bundle is source-grounded, locatable and checked against
  canonical witnesses.  Candidate edits increment a version; review actions
  are append-only files; unreviewed or failed-gate candidates cannot be
  accepted.

**P0 gap**

- Gold has no independent persistent lifecycle entity/state machine.  It is a
  field of `QuestionCandidate`, then recreated as anonymous Bundle Gold on
  export.  There is no Gold draft/reviewed/approved/frozen/invalidated state,
  Gold ID that survives revisions, change set, supersession link or immutable
  approval record bound to a Gold version.
- `human`, `semi_synthetic`, `synthetic`, import and adjudicated sources do not
  have a required trust/provenance level.  Reviewer role, independence,
  adjudication and reviewer disagreement are not typed.
- Alternative minimum sufficient evidence paths cannot be faithfully expressed
  by Bundle v2's AND-of-OR `required_groups`; the V2 prototype explicitly
  blocked a non-factorable alternative path.  Evidence roles (required,
  supporting, conflicting, near-miss) and multi-hop dependency/removal proof
  do not survive as a formal Gold contract.
- Ambiguous/invalid Gold is only a mix of gate flags and candidate rejection;
  there is no invalidation workflow that preserves a prior frozen release while
  producing a successor/retraction decision.

### Question and case authoring

**Present**

- Manual question entry, deterministic target discovery, optional local/remote
  structured question proposal, and a separate answer/evidence proposal are
  real API paths.
- Basic gates cover obvious answer/filename/object-ID leakage, candidate
  overlap, evidence existence/observability, table recomputation flags,
  abstention scope and a basic multi-source/removal-review flag.

**P0 gap**

- The case taxonomy is free-form `capability`/`tags`; there is no controlled
  `FACT`, `TABLE`, `MULTIHOP`, `CROSS_REFERENCE`, `FIGURE`, `EQUATION`,
  `NEGATIVE`, `UNANSWERABLE`, `ADVERSARIAL`, `LONG_CONTEXT`, `DUPLICATE` or
  `NEAR_MISS` model with required annotation fields.
- Template-assisted creation is not a first-class template/version contract.
  Synthetic and semi-synthetic paths are merely proposal methods, not governed
  authoring origins with source/world, template, generator and trust metadata.
- Semantic checks that need human judgement are flags, not a consistently
  structured review checklist/adjudication decision.  The system does not
  quantify or require evidence minimality, actual dependency necessity,
  answerability policy, authority/conflict rules or near-miss plausibility.

### Blueprint, versioning and held-out ability

**Present**

- `BENCHMARK_BLUEPRINT_V0.md`, `BENCHMARK_PROTOCOL_V0.md` and both matrices
  already define the intended axes, authoring fields, review roles, and a
  48-case dry-run portfolio.  Reuse them; do not redesign the taxonomy.
- The Platform has a blind public/sealed **layout** validator and content/file
  checksums.  Source manifests capture DOCX source hash, parser/canonicalizer
  identity and configuration digest; candidate proposal metadata can retain
  provider/prompt/seed.

**Missing**

- No typed mapping of Blueprint axes/coverage slots to documents, cases,
  releases, validators and reports.
- No Dataset/Release/Revision graph, source/generator/config/artifact digest
  bundle, parent version, release notes, reviewer roster, change history, or
  API to explain which frozen state was used by an historical run.
- No case-cluster exclusion policy, source-family isolation, Gold-knowledge
  boundary check, sealed held-out builder, access role, or prohibition of
  post-reveal parameter tuning.  Blind-layout validation alone cannot create a
  blind benchmark.

## Duplicated or competing ownership

| Duplicate | Current location | Decision |
| --- | --- | --- |
| Synthetic fact/question/answer/evidence semantics | `memory_data_service` facts/questions/oracle; `data_generation_v2` scenarios/cases; Platform candidate/Gold | Platform becomes the sole formal case/Gold authority.  Legacy and V2 may provide source-generation inputs only through a future import/generator contract. |
| Canonicalization | Platform DOCX canonicalizer and `data_generation_v2` Markdown canonicalizer | Establish one versioned Platform Canonical Data Model and adapters/importers.  Do not make two canonical schemas evolve independently. |
| Validation/export | Platform Bundle loader/Authoring gates and V2 prototype validator/exporter | Move normative rules into Platform validator/builder.  Prototype checks become test vectors or a migration fixture, not a parallel release system. |
| Provenance/versioning | legacy `GenerationProvenance`, V2 authoring manifest, Platform source metadata/Bundle digest | Create one Platform lineage contract; retain legacy provenance as imported historical metadata only. |

## P0 — required before a formal Benchmark release

| ID | Gap and required outcome | Suggested Platform boundary | Acceptance evidence |
| --- | --- | --- | --- |
| P0-1 | **Versioned Canonical Data Model.** Define source, canonical document, canonical object and canonical relation schemas independent of any chunker/RAG.  Add typed object types, parent/child/sibling/order, heading ancestry, captions, links/cross-references, source spans, transformation provenance and representation status. | New `contracts/canonical.py` plus canonical adapters; retain a versioned DOCX adapter. | Determinism, relationship, source-span and rich-object fixture tests; a schema/digest manifest for every canonical document. |
| P0-2 | **Formal Authoring ledger.** Model Dataset, DocumentRevision, CaseDraft/Revision, GoldRevision, Review, Adjudication and Release explicitly.  Require controlled case type, origin/trust level, answerability and source/BluePrint annotations. | New Authoring domain store/API; do not put mutable records in Bundle Store. | A manual, template-assisted, synthetic and semi-synthetic case all traverse the same state machine; no proposal promotes itself to Gold. |
| P0-3 | **Gold lifecycle and MSES semantics.** Make Gold creation, validation, review, approval, freeze, supersession/invalidation and revision history first-class.  Preserve alternative MSES, evidence role, multi-hop dependency/removal, conflict/authority and negative scope in a sealed authoring sidecar. | Authoring Gold contract; compatible projected view for existing Bundle 2.0. | Gold revision/change log; rejection/invalidation regression tests; export refuses lossy projection or labels it as non-runnable. |
| P0-4 | **Fail-closed Dataset Validator.** Consolidate schema, object ID, locator/span, source/provenance, Gold, question/answer, cross-reference, duplicate/leakage, reachability/ambiguity and checksum checks into a named-rule validator that emits a versioned report. | `rag_eval.validation`; called by authoring review, bundle builder, registration and release freeze. | Any ERROR blocks release and registration; tests demonstrate every listed failure class and report includes input/rule digests. |
| P0-5 | **Frozen Bundle builder and release record.** Make a validated Bundle the only formal evaluation input.  Seal atomically after validation; include manifest, canonical data, cases, Gold, provenance, metadata, schema and validation versions, checksums and lineage. | Bundle v3 or an explicit, versioned release sidecar; v2 remains readable. | Rebuild from same source/config/approved revisions produces same digest; tamper and partial-write tests fail closed. |
| P0-6 | **Lineage/versioning.** Add typed dataset ID, release version, parent/revision links, source/config/canonical/generator/artifact digests, generation metadata and reviewer/release history. | Dataset registry/release service, not arbitrary manifest metadata. | A historical Bundle can answer who/what/config/source/gold changed and whether its bytes equal a prior experiment input. |
| P0-7 | **Development-set declaration.** Register the current 20-case Bundle as `reference_diagnostic/development`, immutable and unavailable for production-default tuning claims.  Record its documented release lineage without changing its Gold. | Additive registry metadata/compatibility record. | Existing Bundle ID and prior run references still verify; no Gold/artifact rewrite occurs. |

## P1 — benchmark data system completion

| ID | Gap and required outcome |
| --- | --- |
| P1-1 | Implement the existing Blueprint/48-case plan as a typed Portfolio/Case-Matrix contract: provenance class, EN/ZH, modality, retrieval/reasoning difficulty, answerability, evidence composition, source family and calibration disposition.  Add coverage and deficit reports. |
| P1-2 | Add a supported source-ingestion abstraction.  DOCX is the first adapter; raw text/Markdown should use the same canonical and review lifecycle, followed by explicitly scoped PDF/HTML/multi-document adapters.  Unsupported material must remain diagnosable, never silently flatten to Gold. |
| P1-3 | Build and seal an actual held-out Dataset Bundle from sources/cases/Gold that were not visible during diagnostic tuning.  Enforce source-family and case/Gold/failure-knowledge disjointness; require frozen config before Gold reveal; use the existing blind protocol as the release gate. |
| P1-4 | Add formal human-review/adjudication/calibration records and role separation.  The current single-review data is suitable for diagnostic use but not a substitute for a formal independent-review protocol. |
| P1-5 | Repair the local test environment from the declared dependency set and make the full Platform suite a required release check.  The current `.venv` is missing `lxml`, so Authoring tests cannot even collect. |

## P2 — legacy migration and cleanup

| Legacy area | Decision | Rationale |
| --- | --- | --- |
| `memory_data_service` rich DOCX/PDF renderers and deterministic scenario worlds | **Retain temporarily as a generator backend / historical fixture**, behind a future Platform source-generation import interface | The rendering capability is valuable, but its coupled facts/questions/oracle are not formal Gold. |
| Legacy `DatasetManifest`, `FactRecord`, `QuestionRecord`, `DocumentObject`, `ObjectRelation`, `OraclePayload` semantics | **Deprecate as an authoring/evaluation authority; retain read-only historical compatibility** | Its schema couples source rendering and oracle truth, lacks verified canonical locators and conflicts with Platform ownership. |
| `memory_eval_tests`, Recall Lab and legacy run envelopes | **Historical compatibility / diagnostic only** | Platform must not scan or ingest their transient directories as formal data input. |
| `data_generation_v2` prototype canonicalizer, validator and exporter | **Migrate concepts and fixtures, then retire as a release path** | It contains useful prior work, but runs a parallel schema/sidecar/export system and states that it is not a release. |

No migration should copy legacy Gold wholesale.  An importer may bring raw source,
generation provenance and proposed annotations into an **untrusted draft**;
canonicalization, validation and independent review must establish any new
formal Gold.

## Recommended implementation order

1. Freeze this audit and mark the 20-case release as development/reference in
   an additive registry record; do not modify production RAG modules.
2. Write the Canonical Data Model and Dataset/Gold/Release contracts, including
   a backwards-compatible Bundle v2-to-v3 migration/read policy.
3. Implement the Authoring ledger and Gold lifecycle on top of the canonical
   contract; migrate only the existing Platform authoring workspace shape, not
   legacy oracle semantics.
4. Implement the one formal validator/report and make Bundle building,
   registration and freezing fail closed on it.
5. Implement typed lineage/release registry and validated Bundle builder;
   demonstrate deterministic rebuild and historical reproduction.
6. Map the existing Blueprint and 48-case dry-run plan into portfolio schema,
   authoring forms and reports.  Do not invent a second taxonomy.
7. Create a source-disjoint held-out authoring workspace, keep it sealed while
   configuration work is frozen, then run one predeclared validation pass.
8. Only after P0/P1 are complete, implement the limited legacy importer and
   retire duplicate prototype release paths.

## Migration risks and controls

| Risk | Control |
| --- | --- |
| Breaking current reproducible runs | Keep Bundle 2.0 readable and store the 20-case reference as an immutable historic release; never rewrite its Gold. |
| Leaking Gold to a RAG runtime | Maintain Authoring/Bundle-to-Worker separation; validate public/sealed roles and inspect request payloads. |
| Narrowing the canonical model to LightRAG chunks | Canonical IDs, relations and source spans must arise solely from raw-document adapters; runtime provenance remains a one-way diagnostic projection. |
| Quietly degrading rich DOCX objects | Preserve `supported/partial/unsupported` status and block unsupported evidence from formal Gold. |
| Overfitting the held-out release | Seal case/Gold/source disjointness and configuration before reveal; publish the validation outcome without parameter retuning. |
| Duplicated sources of truth during migration | Platform contracts own formal semantics; legacy/prototype data is imported as untrusted historical metadata only. |

## Modules explicitly out of scope for this phase

- `LightRAG/lightrag/` ranking, context organisation, Evidence Pack and answer
  generation code, including Segment MaxSim/Conservative Segment thresholds.
- `rag-eval-adapters/` runtime execution translation, except a separately
  approved trace-projection defect.
- Existing Artifact Contract 1.2, Wire Protocol 1.0, evaluation metrics and
  frozen 20-case Gold/Bundle bytes.  Data-layer work must be additive and
  backwards-compatible until an explicit contract migration is approved.
- Case-specific retrieval work, including the previously named ranking/deep-tail
  and `case-e952...` investigations.

## Completion gate for this program

The data layer is **not complete today**.  It becomes complete only when P0 is
implemented and tested, P1's Blueprint mapping and source-disjoint held-out
Bundle are sealed, and the complete Platform test suite runs from the declared
environment.

At that point the Platform will be able to build a formal Benchmark without
LightRAG/RAG-Anything participating in authoring or seeing Gold.  It will then
be appropriate to run the already-frozen held-out validation once, after RAG
configuration is locked.  Until then, all existing 20-case ranking/context
results are development-set diagnostic results, not evidence of generalisation.
