# Benchmark Portfolio / Coverage Implementation Report

Date: 2026-08-29  
Scope: Benchmark Data Layer P1, phase 1 — Blueprint import, Portfolio planning, coverage and deficit reporting only.

## Result

The existing Benchmark v0 Blueprint is now a formal Platform planning contract.  It was imported without changing the Blueprint, Protocol, 96-case matrix, 48-case dry-run CSV, Canonical Data Model, Authoring Ledger/Gold semantics, Bundle 2.0, frozen 20-case Bundle, Adapter execution, scorer, metric, production defaults, or LightRAG.

The immutable imported contract ID is `benchmark-v0-dry-run-48`.

| Contract input | SHA-256 |
| --- | --- |
| `BENCHMARK_BLUEPRINT_V0.md` | `156317a5fd6d64f3bb25b7c198a4c2098fc6b4cb78efddb4a229a023fc7a9882` |
| `BENCHMARK_PROTOCOL_V0.md` | `6dfaec5d2688367833f568b851097dda43a21a69fcba86f1d152598bd8f771da` |
| `BENCHMARK_V0_CASE_MATRIX.csv` | `f11f1145694a11b1f987c2ca515ac7e549b7337cd69fb3d4d47caedf61d2a5f6` |
| `BENCHMARK_48_CASE_DRY_RUN_PLAN.csv` | `286ab8304fee123f0b169381f37747d344c20671809be0d4ef16f9f49fa5cc2a` |

The first import snapshots those exact bytes alongside the contract.  The formal Portfolio digest is `dfc51b1ed537eac24956a55d2b70f5bf832585bf0bf281a84600e4ef8404428b`; the empty-current-state coverage report digest is `d86c5c6bb1b2d27b14e5f57098616a6bcfe6adaf5f6e825f18d2b58c6c1ea0fe`.

## Formal Portfolio model

`src/rag_eval/datasets/portfolio.py` establishes the sole Portfolio planning contract:

- `BenchmarkPortfolio` is an immutable source-snapshotted import.
- `BlueprintMatrixRow` preserves all 19 typed v0 primary archetypes and their 96-case target allocations.
- `PortfolioSlot` materializes each of the 48 dry-run planned cases (12 groups × 4) without creating an Authoring Case or Gold.
- `PortfolioAssignment` is append-only actualization history.  Its only permitted path is `planned → authored → reviewed → approved → frozen`, with `blocked` available from an active state.  A blocked/frozen slot cannot be silently promoted or rewritten.
- `PortfolioLinks` contains typed IDs for Dataset, DocumentRevision, CaseRevision, GoldRevision and immutable Dataset Release; it is not free-form metadata.

Slots carry typed source type, usage, EN/ZH language, primary archetype, retrieval route, evidence composition, reasoning operation, structured-content modality, answerability, retrieval/reasoning difficulties, single/multi/multi-hop evidence requirement, positive/negative/escalation polarity, context pressure and source family.  The four source types are `human`, `semi_synthetic`, `synthetic`, and `adversarial`; all 48 imported protocol slots are `development`, never held-out.

The source CSV intentionally contains group constraints such as `Medium or Hard` and `comparison or aggregation`, rather than per-slot final decisions.  The importer preserves those alternatives as typed allowed values.  It does not invent a finer allocation.  Accordingly, coverage buckets for an alternative are *planned eligible-slot coverage* and can overlap; the contract never presents them as an already-authored final distribution.

## Blueprint and 48-case mapping

The 96-case matrix is retained as the formal v0 target distribution (19 primary archetypes; total 96).  The protocol dry-run is retained as a distinct 48-slot development/rehearsal Portfolio, not a half-release and not a source of automatic promotion.

Initial state is exactly:

| State | Slots |
| --- | ---: |
| planned | 48 |
| authored | 0 |
| reviewed | 0 |
| approved | 0 |
| frozen | 0 |
| blocked | 0 |

No import action created a Case, Gold, Bundle, Dataset Release, or held-out data.

## Coverage and deficit reporting

`PortfolioCoverageReport` deterministically derives `planned`, `completed`, `missing`, `blocked`, and `overrepresented` for primary task, source type, language, retrieval/reasoning difficulty, their cross product, modality, answerability, evidence requirement/composition and source family.  Completion is deliberately fail-closed: only an `approved` or `frozen` slot whose linked Case and Gold are still formally valid is counted.  A blocked, rejected, invalidated or superseded authoring item contributes no completed coverage.

Current plan coverage is below.  `completed = 0` and `missing = planned` everywhere because this phase imports a plan only.

| Axis | Planned coverage |
| --- | --- |
| Source type | Human 12; Semi-synthetic 12; Synthetic 12; Adversarial 12 |
| Language | EN 36; ZH 12 |
| Retrieval difficulty eligibility | Easy 0; Medium 28; Hard 40 |
| Reasoning difficulty eligibility | Easy 20; Medium 16; Hard 20 |
| Modality | text 40; table + text 4; figure + equation + text 4 |
| Evidence requirement | single evidence 16; multi-evidence 28; multi-hop 4 |
| Evidence composition | single 12; independent multi 16; dependent chain 12; alternative path 4; conflict set 8; partial only 4 |
| Answerability | answerable 36; conflicting-resolvable 4; partially-supported 4; unanswerable 4; plausible-unsupported 4; ambiguous 4; conflicting-unresolved 4 |
| Source family | unassigned 48 |

The deficit report is calculated from the imported formal plan, not manually enumerated.  For example, it currently reports `multi_hop: planned 4 / completed 0 / missing 4`, the four table slots, four rich-structure slots, all negative/escalation slots, every source type, and every selected difficulty combination as missing.  It also exposes the immediate source-family planning gap: all 48 slots remain `unassigned`; the original plan does not identify concrete document families and the Platform does not fabricate them.

`overrepresented` is currently zero for all buckets.  It will become nonzero only if future completed actualizations exceed the plan target; it is not guessed from an arbitrary percentage threshold.

## Authoring, Gold, and Release integration

The Portfolio has no parallel Authoring or Gold source of truth.  It references the already formal P0 contracts:

```text
planned PortfolioSlot
  → append-only PortfolioAssignment
  → Dataset / DocumentRevision / CaseRevision / GoldRevision
  → existing Review + Approval lifecycle
  → immutable DatasetRelease (required for frozen coverage)
```

An `authored` slot requires a Ledger-backed CaseRevision.  `reviewed` requires a reviewed CaseRevision.  `approved` requires a Dataset, DocumentRevision, approved CaseRevision and approved GoldRevision; `frozen` additionally requires an immutable Dataset Release pinning those revisions.  The service rechecks current lifecycle status at report time, so a later Case/Gold invalidation or Gold supersession fail-closes current coverage without rewriting historical release records.

## Frozen 20-case observation

The external frozen Bundle remains byte-identical and keeps ID:

`d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e`

It is represented only as an observational Portfolio record:

- `development/reference_diagnostic`
- `held_out = false`
- `generalization_claim_allowed = false`
- 20 cases
- source family `frozen_reference_diagnostic`

No Bundle, Gold, registry record, Dataset Release, historical run reference, or historical classification was changed.  The frozen 20-case source has no per-case typed Blueprint-axis metadata, so it cannot honestly be scored against task/modality/difficulty Portfolio buckets.  Its observable distribution is therefore clearly development/reference-only (zero held-out) and untyped; that is a coverage limitation, not a fabricated claim that it covers the v0 taxonomy.

## Tests and verification

Added `tests/rag_eval_platform/test_benchmark_portfolio.py`, covering:

- Blueprint → typed immutable Portfolio mapping and exact 48-slot import;
- typed-field validation and artifact/contract immutability;
- deterministic coverage/deficit reporting;
- multi-hop, language, source-type and difficulty-combination coverage;
- blocked slots excluded from completion;
- Authoring Case/Gold review and approval gating;
- Release pinning for frozen coverage;
- invalidation fail-closed behavior;
- frozen-20 metadata preservation; and
- absence of a LightRAG dependency.

Verification completed with:

```text
PYTHONPATH=src .venv/bin/pytest -q
106 passed, 3 skipped, 1 warning
```

## P1 status and next boundary

1. **Has the Benchmark Blueprint entered the Platform?** Yes.  The exact source artifacts are imported, snapshotted, typed, digested and immutable as a Platform Portfolio contract.
2. **Are the 48 cases a formally traceable Portfolio rather than only CSV?** Yes.  They are 48 typed slots with append-only actualization state and typed Authoring/Release links; they remain planned, not cases or Gold.
3. **Can the system automatically calculate coverage and deficits?** Yes.  The deterministic report derives planned/completed/missing/blocked/overrepresented from Portfolio slots and their current formal lifecycle links.
4. **Is the current 20-case coverage clearly skewed?** Yes at the classification level: it is entirely development/reference diagnostic, non-held-out, and has no per-case typed Blueprint metadata.  No ungrounded task-axis claim is made.
5. **Can the next phase begin creating a first held-out benchmark?** Not yet.  The planning and P0 lineage/validation foundations exist, but the existing 48 slots are development-only.  A held-out Portfolio/source-admission decision is still required, and the Protocol's checksum-verified independent calibration reference-harness lock remains an explicit blocker before real-case authoring.
6. **Is there a blocker?** Yes: (a) the Protocol’s missing verified independent calibration harness lock, (b) no sealed-eligible source families assigned to the slots, and (c) no approved held-out Portfolio/source selection.  These are intentional governance/data prerequisites, not implementation failures.

Recommended next work, once those prerequisites are authorized, is to assign source families/provenance to the planned slots; conduct the development-only 48-case author/review/calibration rehearsal with priority on multi-hop, table/rich-structure, negative and conflict/alternative-MSES slots; then propose a separate held-out Portfolio.  This phase does not create any held-out data or Bundle.
