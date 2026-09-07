# Real DOCX Benchmark Authoring Pilot Report

Date: 2026-08-29  
Scope: bounded development-only Authoring/Gold/Admission/Release pilot using the real `XXX网站系统（S2A2G2）_V2.0.docx`. No RAG system, retriever, model provider, scorer, metric, Adapter execution, production default, held-out source, or frozen-20 Bundle was used or changed.

## Result

Eight real, human-authored Chinese Cases and independent Gold revisions were created from the audited Canonical representation, passed the formal Authoring and admission gates, and were pinned by immutable release `dataset-release-4758bfcc6b91c492bac9c9f2` (`real-pilot-1.0.0`). This is a **development pilot**, not a held-out benchmark and not a generalization claim.

| Item | Value |
| --- | --- |
| Source DOCX digest | `7d50899d15356000782b292bb84e135e4f1ebe20672ba9799939a6a1e2861755` |
| Dataset | `4867d37a2e17407e8ec774794e853b3c` |
| Canonical digest | `a2955ee975c9d5d42ed126fa050a7bdd6cee7e91aaa90958cfe8a25e1de18271` |
| Parser / canonicalizer | `rag-eval-authoring-ooxml/1` / `rag-eval-authoring-canonicalizer/2` |
| Canonical configuration digest | `01d21f985ed1e056f3cd8351b926199e1c4111ada7c0a8c0370fa0b45d5e1cc6` |
| Formal preflight report | `680fe9f1cc38113c7df2a7f295c36a53d386a6040ae5fcac22225c6acb54494f` |
| Frozen-release validation report | `f94d64ca60ac414fda5f63c924a0e2c7180fc5ce638557d6c5f9faa57f8644b7` |
| Release rebuild | reproducible; the rebuilt report digest equals the pinned release digest |

The persisted, replayable pilot state is deliberately outside the repository at `/Users/sakura/RAG/.rag-eval-real-benchmark-pilot`; its concise machine-readable index is `real-benchmark-authoring-pilot-summary.json`. The reproducible driver is [run_real_benchmark_authoring_pilot.py](/Users/sakura/RAG/rag-eval-platform/scripts/run_real_benchmark_authoring_pilot.py).

## Source admission and Gold boundary

The whole DOCX honestly remains `partial`: the real-DOCX Canonical audit found partial rich structures and non-traversed header/footer content. Its whole-source admission report is therefore intentionally non-passing (`9de85189cd572a203a00bf15c3aaddeecfa99eb76515e9f734a2ae847ff9fa7b`): it reports incomplete parse/structure plus an unadmitted candidate source. The pilot does **not** relabel that document as wholly complete.

Instead, each Case uses a typed `CanonicalEvidenceScope` with the document and canonical digests above and only selected objects whose representation status is `complete`. The admission gate verifies that the scope contains all Case/Gold evidence and rejects a missing, partial, unsupported, or foreign-digest object. This is a development-only, object-level Gold boundary; it is not a waiver for a held-out source. Held-out material still requires whole-source admission and family isolation.

All selected evidence is either a complete body paragraph, a complete table, or a complete table cell with direct OOXML locator and provenance. No partial table, figure, caption, equation, footer/header, footnote/endnote, embedded object, or unsupported object was cited as formal Gold evidence.

## Pilot Case / Gold set

All eight `AuthoringOrigin` records are `human`, evidence-first, and name the real Canonical document. The `source_type` shown by a Portfolio slot remains the immutable Blueprint planning/coverage axis; it is not a replacement for the Ledger’s actual authoring-origin record. No Case question contains a Canonical object ID, a filename, or a manual hint.

| Frozen Case / Gold | Formal slot | Question / answer | Typed evidence and MSES | Review tier |
| --- | --- | --- | --- | --- |
| `pilot-case-http-protocol` / `pilot-gold-http-protocol` | `DRY-02-slot-04` | Which protocol prevents the application’s transfer integrity from being guaranteed? → `HTTP` | required `block:00052`; `block:00024` is a recorded near-miss; one-clause MSES | standard |
| `pilot-case-conclusion-validity` / `pilot-gold-conclusion-validity` | `DRY-03-slot-04` | What later change makes the assessment conclusion inapplicable? → a change involving system components/subsystems | required `block:00016`; one-clause MSES | standard |
| `pilot-case-critical-backed-up-data` / `pilot-gold-critical-backed-up-data` | `DRY-04-slot-04` | Which categories are both critical and explicitly locally backed up? → important business/configuration/audit data | `block:00034` AND `table:00017`; two required MSES clauses | standard |
| `pilot-case-good-not-excellent` / `pilot-gold-good-not-excellent` | `DRY-05-slot-04` | Why is a score above 90 not rated excellent? → eight medium-risk issues | `block:00041` AND rating-criteria cells `2702002`, `2703002`; two-step typed dependency graph | heightened, two reviewers |
| `pilot-case-critical-data-count` / `pilot-gold-critical-data-count` | `DRY-06-slot-04` | How many categories are marked critical? → `4` | four complete criticality cells `1702005`, `1703005`, `1704005`, `1705005`; all four necessary | standard |
| `pilot-case-access-switch-model` / `pilot-gold-access-switch-model` | `DRY-07-slot-04` | What is the model of the access switch? → `S2910-48GT4XS-E` | same complete table row, cells `1002002` AND `1002005` | heightened, two reviewers |
| `pilot-case-auth-data-confidentiality` / `pilot-gold-auth-data-confidentiality` | `DRY-10-slot-04` | Is confidentiality listed for authentication data? → abstain / no | typed negative scope: complete `table:00017`; the scope records only integrity for the authentication-data row and does not turn model failure into a negative claim | heightened, two reviewers |
| `pilot-case-server-os-alternative-path` / `pilot-gold-server-os-alternative-path` | `DRY-12-slot-04` | What operating system/version does the external website server use? → `Windows2008 企业版` | two allowed MSES paths: table-12 row (`1202002`, `1202005`) OR table-34 row (`3402002`, `3402005`) | heightened, two reviewers |

Every MSES clause has an independent evidence-removal necessity record. The set includes one AND-MSES, one typed multi-hop dependency, one negative/unanswerable scope, and one alternative OR-MSES path. Thus those semantics are now exercised with real Canonical objects, rather than only fixtures.

## Lifecycle, review, and admission

Each Case and Gold follows immutable append-only history:

```text
draft → proposed → reviewed → approved → frozen
```

The author is `pilot-human-author`; reviewers are distinct identities `pilot-reviewer-a` and, for heightened cases, `pilot-reviewer-b`; the release action is by `pilot-release-manager`. Reviews are recorded on the proposed immutable revisions. The admission attestation records both the actual reviewed revision IDs and stable Case/Gold identities, so a later reviewed/approved revision never overwrites or obscures what was inspected.

The final release pins revision `000005` for every Case and Gold. The release also pins the source/Critical Canonical digests, document revision, schema versions, review/approval lineage, ledger selection digest, validation-report digest, source snapshot, and Canonical snapshot. The Portfolio assignments progress append-only through `authored → reviewed → approved → frozen` and link those pinned revisions and release ID.

All eight individual admission reports are passing. They check source/digest binding, complete scoped evidence, Case/Gold lineage, evidence reachability, MSES necessity, negative scope, multi-hop dependency where applicable, answer leakage, question duplication, proposal-only rules, and independent review.

## Formal validation and release behavior

The frozen-release validator has 16 `ERROR/PASS` rules, covering Canonical graph/provenance, revision integrity, review and approval integrity, evidence reachability, MSES/answer consistency, negative scope, multi-hop closure, duplicate/near-miss Cases, checksum consistency, and cross references. No ERROR was present when freezing.

The only non-passing finding is deliberately transparent:

| Rule | Severity / result | Consequence |
| --- | --- | --- |
| `bundle_v2.projection_lossiness` | `WARN / FAIL` | Bundle 2.0 cannot losslessly and runnably represent the selected formal Gold set (notably OR-MSES, dependency and negative-scope semantics). No Bundle 2.0 export or Bundle ID is claimed for this release. |

Source-tamper verification copied the immutable release source snapshot, appended bytes, and revalidated it. Report `03f7d696a8db598d27a34a5d99192f5891e58543859625ec582713570d066978` contains `integrity.checksums = ERROR/FAIL`; the temporary tampered file was then removed. This demonstrates fail-closed reproducibility rather than only a happy-path freeze.

The existing frozen 20-case Bundle remains byte-identical with ID `d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e`, lifecycle `frozen`, usage `development/reference_diagnostic`, `held_out = false`, and `generalization_claim_allowed = false`.

## Verification

```text
.venv/bin/python -m pytest \
  tests/rag_eval_platform/test_benchmark_admission_policy.py \
  tests/rag_eval_platform/test_authoring_ledger.py \
  tests/rag_eval_platform/test_formal_release_lineage.py -q
13 passed, 1 warning

.venv/bin/python scripts/run_real_benchmark_authoring_pilot.py \
  --source-docx '/Users/sakura/RAG/XXX网站系统（S2A2G2）_V2.0.docx' \
  --platform-home /Users/sakura/RAG/.rag-eval-real-benchmark-pilot --reset
8 Case/Gold pairs frozen; deterministic rebuild passed; tamper detection failed closed.

.venv/bin/python -m pytest -q
121 passed, 3 skipped, 1 warning
```

## Decision

The Platform now has a real, auditable development Case/Gold authoring pilot grounded in complete Canonical evidence. It is safe to proceed to the separately scoped complex-table Canonicalization work, then author further development cases only from Gold-eligible objects.

This does **not** authorize held-out authoring: the real DOCX belongs to a development source family, is globally partial, and the checksum-verified independent calibration harness / sealed held-out source admission requirements remain unresolved. Those governance limits are not bypassed by this pilot.
