# Documentation Inventory

## Coverage and method

At baseline `0fc494f975d9b3b2c026bba798cc13f764b93580`, the repository contains **74 tracked Markdown files** totaling **10,727 lines**. The scan was complete and found no exact-content duplicates (CMD-023). Each file was checked for purpose, intended reader, normative status, last modifying commit, index/link placement, stale phase claims and local links. The offline link check found **18 Markdown links with absolute local targets, all missing** at the recorded baseline (CMD-024).

The table below inventories every tracked Markdown file. `Active` means maintain as current guidance; `Compat` means required to explain or operate a supported historical format; `Test` means fixture/example documentation; `Historical` means evidence that should be clearly archived; `Mixed/Stale` means useful content remains but the current presentation is misleading. A recommendation is not an authorization to move or delete the file.

## Findings

### DOC-001 — `CURRENT_STATUS.md` describes the retired corpus hierarchy as current

- **Status:** CONFIRMED
- **Severity:** P2
- **Evidence:** `platform/CURRENT_STATUS.md:19-23` says canonical-text is the normal path and native DOCX is diagnostic, and `CURRENT_STATUS.md:115-119` repeats the hierarchy. `platform/README.md:23-25` links this document as current status. ADR 0003 and the public admission implementation require the opposite formal boundary.
- **Disposition:** ARCHIVE
- **Reason:** It is valuable consolidation-history evidence but is unsafe as current operator guidance. Replace the README link with a short generated/current status page or the final architecture index, then move this document to the historical reports archive.
- **Affected Files:** `platform/CURRENT_STATUS.md`; `platform/README.md`; archive index.
- **Counter-evidence checked:** The title says “Project Consolidation Baseline,” but its prominent README placement gives it active authority; no superseded banner is present.
- **Recommended owner:** Platform maintainers / Documentation.
- **Validation after cleanup:** All root and Platform navigation reaches ADR 0003/current architecture; a link check passes; searching active docs no longer presents pre-segmented execution as normal.

### DOC-002 — Phase-era architecture documents still claim obsolete execution authority

- **Status:** CONFIRMED
- **Severity:** P2
- **Evidence:** `docs/architecture/UNIFIED_OBSERVATION_CONTRACT.md:3-5` describes Wire 1 as the execution authority; `UNIFIED_EVALUATION_V2.md:3-6` describes the new scorer as shadow work; `RUN_ARTIFACT_V2.md:37` says the legacy executor remains authoritative; `LIGHTRAG_NATIVE_OBSERVATION.md:3-4` is framed as a Phase 4 boundary. `docs/architecture/README.md:9-20` indexes these beside historical audit/gap/plan documents without a current-versus-history distinction.
- **Disposition:** MERGE
- **Reason:** Preserve the contract details, but consolidate current normative statements into maintained v2 protocol pages and move phase-specific status/limitations to an archive note. Do not leave readers to infer authority from migration timestamps.
- **Affected Files:** `docs/architecture/README.md`; `UNIFIED_OBSERVATION_CONTRACT.md`; `UNIFIED_EVALUATION_V2.md`; `RUN_ARTIFACT_V2.md`; `LIGHTRAG_NATIVE_OBSERVATION.md`; `TARGET_ARCHITECTURE.md`.
- **Counter-evidence checked:** Later paragraphs in several files record later phases, and ADR 0003 is correct. The contradictory opening status is still what a reader sees first.
- **Recommended owner:** Architecture owners.
- **Validation after cleanup:** Architecture index labels each page `Current`, `Compatibility`, or `Historical`; current pages agree on one authority; ADR links and code paths are checked.

### DOC-003 — Packaged benchmark protocol contains missing normative companion links

- **Status:** CONFIRMED
- **Severity:** P2
- **Evidence:** `platform/src/rag_eval/resources/benchmark-v0/BENCHMARK_BLUEPRINT_V0.md:5,7,78,220` and `BENCHMARK_PROTOCOL_V0.md:5,71,135,199,221-225` point to absolute `/Users/sakura/RAG/...` files. The packaged resource directory contains only the two Markdown files and two CSV files; referenced current-state, draw.io and YAML templates are absent. CMD-024 found these plus two historical-report links, for 18 missing Markdown targets total.
- **Disposition:** MERGE
- **Reason:** These files are shipped as package resources and describe authoring protocol inputs as normative. Either package/version the companions and use relative links, or remove/demote claims that they are required. Historical report links should become repository-relative or plain archival provenance.
- **Affected Files:** Both `platform/src/rag_eval/resources/benchmark-v0/*.md`; `platform/COMPLEX_TABLE_CANONICALIZATION_REPORT.md`; `platform/REAL_BENCHMARK_AUTHORING_PILOT_REPORT.md`; package-data configuration.
- **Counter-evidence checked:** Two referenced CSVs have similarly named packaged copies, but the absolute links do not resolve and the YAML/draw.io/current-state files have no tracked equivalent.
- **Recommended owner:** Benchmark Protocol / Packaging.
- **Validation after cleanup:** Build and clean-install the Platform wheel, enumerate packaged resources, and run an offline relative-link checker against repository and installed-package copies.

### DOC-004 — Phase and experiment reports remain in the Platform root as if actively maintained

- **Status:** CONFIRMED
- **Severity:** P3
- **Evidence:** Twenty-one implementation, audit, experiment, rehearsal and acceptance reports sit directly under `platform/`; most were imported together at commit `0e93afb`, while an archive with plan/report subdirectories already exists. They contain unique historical evidence but are not separated from `README.md`, policy and current contract documents (CMD-023).
- **Disposition:** ARCHIVE
- **Reason:** Move historical reports into the existing indexed archive after confirming links. This reduces current-doc surface without discarding provenance. No report is recommended for deletion because no exact duplicate or fully redundant unique-evidence-free file was proven.
- **Affected Files:** Platform-root `*_REPORT.md`, `*_AUDIT.md`, `*_ACCEPTANCE.md`, experiment/rehearsal documents; `platform/docs/archive/README.md`; incoming links.
- **Counter-evidence checked:** No exact-content duplicate exists; several reports contain hashes, empirical outcomes or acceptance rationale, so wholesale deletion would lose evidence.
- **Recommended owner:** Documentation / Release Engineering.
- **Validation after cleanup:** Repository-relative links pass; current README lists only maintained documents; archive index records title, date/commit and successor.

### DOC-005 — No exact duplicate Markdown is present

- **Status:** DISPROVED
- **Severity:** INFO
- **Evidence:** CMD-023 hashed all 74 tracked Markdown files and found no duplicate digest.
- **Disposition:** KEEP
- **Reason:** Document cleanup should be semantic consolidation and archiving, not a filename/count-driven deletion campaign.
- **Affected Files:** All tracked Markdown.
- **Counter-evidence checked:** Similar titles and phase reports were reviewed for semantic overlap; they retain distinct evidence even where conclusions are superseded.
- **Recommended owner:** Documentation.
- **Validation after cleanup:** Re-run hash and semantic/link inventory; delete only documents whose unique information has first been incorporated or intentionally discarded with approval.

### DOC-006 — Architecture navigation does not distinguish specification from migration history

- **Status:** CONFIRMED
- **Severity:** P2
- **Evidence:** `docs/architecture/README.md:9-20` lists `CURRENT_ARCHITECTURE_AUDIT.md`, `NATIVE_DOCUMENT_GAP_ANALYSIS.md`, `MIGRATION_PLAN.md`, target/contract/phase pages and final cutover pages in one undifferentiated sequence. `MIGRATION_PLAN.md` is 527 lines and remains linked despite Phase 0–9 completion.
- **Disposition:** MERGE
- **Reason:** Keep ADR 0003 and maintained contracts as the normative set; move audits, gaps and phase execution plans under an indexed migration-history section. This avoids future agents treating old limitations as live requirements.
- **Affected Files:** `docs/architecture/README.md`; architecture audit/gap/migration plan; current contract pages; archive index.
- **Counter-evidence checked:** File titles contain some historical cues, but the index assigns no authority/status labels and active documents link back to them.
- **Recommended owner:** Architecture owners.
- **Validation after cleanup:** A new maintainer can identify the current runtime, protocols and compatibility policy from one index without reading phase reports.

## Complete Markdown inventory

| # | Path | Purpose / audience | Normative state | Last commit | Recommendation | Link/index note |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `README.md` | Workspace map for all users | Active | `50aa694` | `KEEP` | Correctly points to project/locks; workspace path is descriptive, not a Markdown link. |
| 2 | `adapters/README.md` | Shared Adapter development guide | Active | `0fc494f` | `KEEP` | Update only when Wire 1 retirement is scheduled. |
| 3 | `adapters/lightrag/README.md` | LightRAG operator/developer guide | Active | `25d19aa` | `KEEP` | Link from Adapter index is appropriate. |
| 4 | `adapters/rag-anything/README.md` | RAG-Anything operator/developer guide | Active | `0fc494f` | `KEEP` | Current native observation guide. |
| 5 | `docs/architecture/ARTIFACT_V2_PRESENTATION.md` | API/UI persisted-view contract | Active | `4889f44` | `KEEP` | Retain as current after `ARCH-003` update. |
| 6 | `docs/architecture/CANONICAL_CONFORMANCE.md` | Canonical/Gold eligibility protocol | Active normative | `d94923c` | `KEEP` | Current and aligned with code. |
| 7 | `docs/architecture/CURRENT_ARCHITECTURE_AUDIT.md` | Pre-migration architecture audit | Historical | `4889f44` | `ARCHIVE` | Index as input to ADR 0003, not current audit. |
| 8 | `docs/architecture/LIGHTRAG_NATIVE_OBSERVATION.md` | LightRAG observation design | Mixed/Stale | `25d19aa` | `MERGE` | Preserve Adapter detail; remove Phase-4 authority wording. |
| 9 | `docs/architecture/MIGRATION_PLAN.md` | Phase 0–9 execution plan | Historical | `0fc494f` | `ARCHIVE` | Completed plan; link from migration history only. |
| 10 | `docs/architecture/MULTI_CORPUS_HISTORY.md` | Explanation of legacy corpus modes | Compat/Historical | `e08b0e9` | `KEEP_FOR_COMPAT` | Valuable rationale while modes remain readable. |
| 11 | `docs/architecture/NATIVE_DOCUMENT_GAP_ANALYSIS.md` | Pre-migration gap analysis | Historical | `0fc494f` | `ARCHIVE` | Superseded as status; retains decision evidence. |
| 12 | `docs/architecture/NATIVE_FORMAL_CUTOVER.md` | Native public-admission/cutover contract | Active | `4889f44` | `KEEP` | Update with enforcement found in `ARCH-002`. |
| 13 | `docs/architecture/RAG_ANYTHING_NATIVE_OBSERVATION.md` | RAG-Anything native observation | Active | `0fc494f` | `KEEP` | Current Adapter-specific implementation guide. |
| 14 | `docs/architecture/README.md` | Architecture navigation | Mixed/Stale | `4889f44` | `MERGE` | Add authority/status groups; see `DOC-006`. |
| 15 | `docs/architecture/RUN_ARTIFACT_V2.md` | Artifact 2.0 design/contract | Mixed/Stale | `4889f44` | `MERGE` | Preserve contract; remove legacy-authority phase statement. |
| 16 | `docs/architecture/TARGET_ARCHITECTURE.md` | Detailed target design | Historical/Mixed | `0fc494f` | `ARCHIVE` | ADR/current contracts should carry normative content; keep design rationale. |
| 17 | `docs/architecture/UNIFIED_EVALUATION_V2.md` | Unified scorer specification | Mixed/Stale | `9f9b4e3` | `MERGE` | Keep formulas; update shadow/authority wording. |
| 18 | `docs/architecture/UNIFIED_OBSERVATION_CONTRACT.md` | Wire 2 observation specification | Mixed/Stale | `2e53e11` | `MERGE` | Keep contract; update Wire 1 authority wording and TCK caveat. |
| 19 | `docs/decisions/0001-runtime-evidence-cardinality-and-prompt-trace.md` | Accepted evidence/trace ADR | Active normative | `34f4ed8` | `KEEP` | Stable decision record. |
| 20 | `docs/decisions/0002-architecture-change-envelope.md` | Accepted change-envelope ADR | Active normative | `4889f44` | `KEEP` | Stable decision record. |
| 21 | `docs/decisions/0003-native-document-evaluation-v2.md` | Governing native-v2 ADR | Active normative | `e08b0e9` | `KEEP` | Primary audit authority. |
| 22 | `docs/migration/HISTORY_MAP.md` | Repository migration provenance | Compat/Historical | `d022563` | `KEEP_FOR_COMPAT` | Retain; local workspace reference is archival provenance. |
| 23 | `platform/AUTHORING_LEDGER_GOLD_LIFECYCLE_REPORT.md` | Phase implementation evidence | Historical | `0e93afb` | `ARCHIVE` | Move to reports archive; unique evidence retained. |
| 24 | `platform/BENCHMARK_DATA_GENERATION_POLICY_V1.md` | Benchmark authoring/admission policy | Active normative | `0e93afb` | `KEEP` | Link from current docs and verify against Canonical Conformance. |
| 25 | `platform/BENCHMARK_DATA_LAYER_GAP_AUDIT.md` | Data-layer gap audit | Historical | `0e93afb` | `ARCHIVE` | Superseded status, useful rationale. |
| 26 | `platform/BENCHMARK_PORTFOLIO_COVERAGE_REPORT.md` | Coverage implementation report | Historical | `0e93afb` | `ARCHIVE` | Unique acceptance evidence. |
| 27 | `platform/BUNDLE_V3_IMPLEMENTATION_REPORT.md` | Bundle 3 implementation report | Historical | `0e93afb` | `ARCHIVE` | Retain as release evidence. |
| 28 | `platform/CANONICAL_DATA_MODEL_IMPLEMENTATION_REPORT.md` | Canonical model phase report | Historical | `0e93afb` | `ARCHIVE` | Superseded by conformance docs. |
| 29 | `platform/COMPLEX_TABLE_CANONICALIZATION_REPORT.md` | Table canonicalization experiment/report | Historical | `0e93afb` | `ARCHIVE` | Two broken absolute links; repair or annotate before move. |
| 30 | `platform/CONTRACT.md` | Wire Protocol 1.0 contract | Compat normative | `34f4ed8` | `KEEP_FOR_COMPAT` | Mark clearly as Wire 1 and link to successor. |
| 31 | `platform/CURRENT_STATUS.md` | Old consolidation status | Stale | `0e93afb` | `ARCHIVE` | Contradicts native-v2 formal route; see `DOC-001`. |
| 32 | `platform/DATASET_CREATION_FLOW_AUDIT.md` | Dataset-flow audit | Historical | `0e93afb` | `ARCHIVE` | Preserve rationale, not current instructions. |
| 33 | `platform/DATA_LAYER_1_0_FINAL_ACCEPTANCE.md` | Data-layer acceptance evidence | Historical | `0e93afb` | `ARCHIVE` | Retain immutable release evidence. |
| 34 | `platform/DEVELOPMENT_BENCHMARK_48_AUTHORING_REPORT.md` | Authoring run report | Historical | `0e93afb` | `ARCHIVE` | Contains external-workspace provenance; not current guide. |
| 35 | `platform/END_TO_END_RAG_EVALUATION_REHEARSAL_REPORT.md` | Rehearsal results | Historical | `0e93afb` | `ARCHIVE` | Contains unique hashes/results. |
| 36 | `platform/FORMAL_VALIDATOR_RELEASE_LINEAGE_REPORT.md` | Validator/release phase report | Historical | `0e93afb` | `ARCHIVE` | Preserve acceptance trail. |
| 37 | `platform/LIGHTRAG_EXECUTION_EQUIVALENCE_AUDIT.md` | Adapter equivalence audit | Historical | `0e93afb` | `ARCHIVE` | Useful historical neutrality evidence. |
| 38 | `platform/LIGHTRAG_RANKING_CONTEXT_DIAGNOSTIC.md` | Ranking/context diagnostic | Historical experiment | `0e93afb` | `ARCHIVE` | Retain empirical evidence; label non-normative. |
| 39 | `platform/LIGHTRAG_RANKING_CONTEXT_EXPERIMENT.md` | Ranking/context experiment | Historical experiment | `0e93afb` | `ARCHIVE` | Retain results, remove from current-doc surface. |
| 40 | `platform/LIGHTRAG_RANKING_CONTEXT_ROBUSTNESS.md` | Robustness experiment | Historical experiment | `0e93afb` | `ARCHIVE` | Unique empirical evidence. |
| 41 | `platform/LIGHTRAG_STRUCTURAL_CONTEXT_EVIDENCE_PACK.md` | Structural evidence pack | Historical experiment | `0e93afb` | `ARCHIVE` | Large unique evidence record; do not delete. |
| 42 | `platform/PROJECT_CONSOLIDATION_REPORT.md` | Earlier consolidation report | Historical | `0e93afb` | `ARCHIVE` | Superseded status; preserve provenance. |
| 43 | `platform/README.md` | Platform user/developer entry | Active with stale link | `4889f44` | `MERGE` | Keep, but replace `CURRENT_STATUS` authority and reorganize navigation. |
| 44 | `platform/REAL_BENCHMARK_AUTHORING_PILOT_REPORT.md` | Real-DOCX pilot report | Historical | `0e93afb` | `ARCHIVE` | One broken absolute Markdown link plus nonportable commands. |
| 45 | `platform/REAL_DOCX_CANONICAL_DATA_AUDIT.md` | Real-DOCX canonical audit | Historical | `0e93afb` | `ARCHIVE` | Retain evidence, not current protocol. |
| 46 | `platform/RICH_CONTENT_CANONICALIZATION_REPORT.md` | Rich-content phase report | Historical | `0e93afb` | `ARCHIVE` | Preserve subtype evidence. |
| 47 | `platform/docs/ARTIFACT_CONTRACT_1_2.md` | Artifact 1.2 format | Compat normative | `0e93afb` | `KEEP_FOR_COMPAT` | Unique historical reader contract. |
| 48 | `platform/docs/BENCHMARK_DIAGNOSTIC_EXPANSION_REPORT.md` | Diagnostic expansion report | Historical | `0e93afb` | `ARCHIVE` | Move under archive/reports. |
| 49 | `platform/docs/BLIND_BENCHMARK_PROTOCOL.md` | Blind evaluation procedure | Active normative | `0e93afb` | `KEEP` | Maintain if blind runs remain supported. |
| 50 | `platform/docs/EVIDENCE_REPAIR_PLAN.md` | Evidence-localization repair plan | Historical/Compat | `0e93afb` | `ARCHIVE` | Preserve P0 rationale; local paths are historical examples. |
| 51 | `platform/docs/NATIVE_DOCX_COMPATIBILITY_CONTRACT.md` | Native/legacy compatibility policy | Compat normative | `4889f44` | `KEEP_FOR_COMPAT` | Required until legacy corpus/read support ends. |
| 52 | `platform/docs/PRIVATE_DOCUMENT_BENCHMARK_DESIGN.md` | Earlier product design | Mixed/Historical | `4889f44` | `MERGE` | Fold still-current product requirements into policy/product track; archive design snapshot. |
| 53 | `platform/docs/PRODUCTIZATION_TRACK.md` | Maintainer delivery/operations track | Active | `4889f44` | `KEEP` | Refresh after P1 remediation. |
| 54 | `platform/docs/QUICK_START.md` | WebUI/operator quick start | Active | `4889f44` | `KEEP` | Revalidate commands after runtime cleanup. |
| 55 | `platform/docs/archive/README.md` | Archive navigation | Active index | `4889f44` | `KEEP` | Expand with incoming historical reports and successors. |
| 56 | `platform/docs/archive/plans/PRIVATE_DOCUMENT_BENCHMARK_IMPLEMENTATION_PLAN.md` | Archived implementation plan | Historical archived | `0e93afb` | `ARCHIVE` | Already correctly placed; keep indexed. |
| 57 | `platform/docs/archive/reports/BYOD-10_REPORT.md` | Archived acceptance report | Historical archived | `0e93afb` | `ARCHIVE` | Already correctly placed. |
| 58 | `platform/docs/archive/reports/CANONICAL_PROVENANCE_BRIDGE_REPORT.md` | Archived provenance report | Historical archived | `0e93afb` | `ARCHIVE` | Already correctly placed. |
| 59 | `platform/docs/archive/reports/EXECUTION_RELIABILITY_REPORT.md` | Archived reliability report | Historical archived | `0e93afb` | `ARCHIVE` | Already correctly placed. |
| 60 | `platform/docs/archive/reports/PHASE_8_REAL_MODEL_VALIDATION_REPORT.md` | Archived real-model report | Historical archived | `0e93afb` | `ARCHIVE` | Keep as empirical record, clearly non-current. |
| 61 | `platform/docs/archive/reports/PRIVATE_DOCUMENT_BENCHMARK_CURRENT_GAP.md` | Archived gap audit | Historical archived | `0e93afb` | `ARCHIVE` | “Current” is historical only; archive placement resolves ambiguity. |
| 62 | `platform/docs/archive/reports/PRODUCTIZATION_ACCEPTANCE_REPORT.md` | Archived acceptance report | Historical archived | `0e93afb` | `ARCHIVE` | Already correctly placed. |
| 63 | `platform/docs/evidence-repair/HISTORICAL_RECOVERY_V2.md` | Historical recovery operator guide | Compat normative | `0e93afb` | `KEEP_FOR_COMPAT` | Replace machine-specific paths with parameters/examples when maintained. |
| 64 | `platform/examples/golden-smoke-v1/documents/abstain-negative.md` | Golden-smoke input | Test data | `0e93afb` | `KEEP_FOR_TEST` | Not documentation debt. |
| 65 | `platform/examples/golden-smoke-v1/documents/multi-evidence.md` | Golden-smoke input | Test data | `0e93afb` | `KEEP_FOR_TEST` | Protects multi-evidence behavior. |
| 66 | `platform/examples/golden-smoke-v1/documents/numeric-units.md` | Golden-smoke input | Test data | `0e93afb` | `KEEP_FOR_TEST` | Protects numeric/unit behavior. |
| 67 | `platform/examples/golden-smoke-v1/documents/plain-text.md` | Golden-smoke input | Test data | `0e93afb` | `KEEP_FOR_TEST` | Baseline smoke input. |
| 68 | `platform/src/rag_eval/resources/benchmark-v0/BENCHMARK_BLUEPRINT_V0.md` | Packaged benchmark blueprint | Active packaged protocol | `0e93afb` | `MERGE` | Four missing absolute links; package/relativize companions. |
| 69 | `platform/src/rag_eval/resources/benchmark-v0/BENCHMARK_PROTOCOL_V0.md` | Packaged benchmark protocol | Active packaged normative | `0e93afb` | `MERGE` | Twelve missing absolute links; absent normative YAML companions. |
| 70 | `tests/fixtures/canonical_naive_minimal.md` | Canonicalization fixture | Test data | `5bcda26` | `KEEP_FOR_TEST` | Not user-facing documentation. |
| 71 | `webui/README.md` | WebUI development guide | Active | `4889f44` | `KEEP` | Current build/test instructions passed CMD-016/017. |
| 72 | `webui/docs/archive/README.md` | WebUI archive index | Active index | `4889f44` | `KEEP` | Maintain as archive navigation. |
| 73 | `webui/docs/archive/reports/PHASE_A_UI_REPORT.md` | Archived UI phase report | Historical archived | `1e9912c` | `ARCHIVE` | Already correctly placed. |
| 74 | `webui/docs/archive/reports/UI_AUDIT.md` | Archived UI/UX audit | Historical archived | `1e9912c` | `ARCHIVE` | Already correctly placed. |

## Consolidation map

| Destination | Inputs | Required result |
| --- | --- | --- |
| `docs/architecture/README.md` | Current ADRs, Canonical, Observation, Evaluation, Artifact, admission and Adapter pages | One status-labelled architecture index; no phase chronology presented as authority. |
| Current protocol pages | Useful normative sections from `TARGET_ARCHITECTURE.md`, phase-era contract pages and product design | A single maintained statement per contract; historical wording removed or moved to an appendix. |
| `platform/docs/archive/reports/` | Platform-root implementation/audit/experiment/rehearsal reports | Preserve files and hashes, add successor/status metadata, repair incoming links. |
| `platform/docs/archive/plans/` | Completed migration/repair/implementation plans | Historical plan index, clearly non-normative. |
| Packaged `benchmark-v0` resource set | Blueprint, protocol, present CSVs and any truly required templates | Self-contained wheel resources with relative links and explicit version/status. |

## Deletion conclusion

No existing Markdown file is presently proven safe for direct deletion. The audit recommends **archive or merge first** because no exact duplicate exists and the phase/experiment documents retain unique evidence. After consolidation, a later cleanup may delete a superseded source only if its unique content has been incorporated, its incoming links are updated, its successor is recorded and approval is explicit.
