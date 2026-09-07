# Complex Table Canonicalization Report

Date: 2026-08-29  
Scope: Data Layer only. The real `XXX网站系统（S2A2G2）_V2.0.docx` was rebuilt through the Canonical DOCX path; no LightRAG, retrieval/execution adapter, RAG experiment, answer-quality test, frozen-20 Bundle, Gold content, scorer, metric, or production setting was changed.

## Result

Complex DOCX tables are now represented as a faithful physical-plus-logical topology in Canonical Contract **1.1**. The update preserves readable Contract 1.0 snapshots and Bundle 2.0’s existing physical `table_id` / `row` / `column` / `grid_span` projection. It adds topology facts and relations rather than overwriting physical OOXML cells.

The real document was rebuilt twice, from the original DOCX, with identical Canonical digests:

| Field | Value |
| --- | --- |
| Source SHA-256 | `7d50899d15356000782b292bb84e135e4f1ebe20672ba9799939a6a1e2861755` |
| Parser / canonicalizer | `rag-eval-authoring-ooxml/1` / `rag-eval-authoring-canonicalizer/3` |
| Contract schema | `1.1` (1.0 reader-compatible) |
| Configuration digest | `01a020ec981851b66ce9ff0241fe01077339a84fb3c0e49b0f4670687b5d8537` |
| Canonical digest, build 1 / build 2 | `4b52e327a691db86411dc5d17138b2c3ac2616d7240790ae804fb029d9112c97` / same |
| Objects / relations | 14,176 / 66,617 |
| Raw-source physical-cell comparisons | 5,143 / 5,143 passed |

The replayable verifier is [run_complex_table_canonical_audit.py](/Users/sakura/RAG/rag-eval-platform/scripts/run_complex_table_canonical_audit.py). Its persisted real-DOCX audit output is `/Users/sakura/RAG/.rag-eval-complex-table-audit-v3/complex-table-canonical-audit-summary.json`.

## What the original 56 partial tables were

The prior Canonicalizer conservatively marked every merged table and every nested table partial: 28 table / 193 row / 825 cell objects were complete; 56 / 786 / 4,318 were partial. The following mutually exclusive classification of those 56 original partial tables comes from the real document’s OOXML, not from inferred content:

| Original partial structure | Tables |
| --- | ---: |
| Explicit one-row header + vertical merge | 23 |
| Horizontal + vertical (mixed) merge + explicit multi-level header | 17 |
| Explicit one-row header + horizontal merge | 6 |
| Explicit one-row header + horizontal + vertical (mixed) merge | 5 |
| Horizontal + vertical (mixed) merge, no explicit header | 2 |
| Horizontal merge only | 1 |
| Horizontal merge + nested parent table | 1 |
| Structurally regular nested child table, previously partial solely because it was nested | 1 |
| **Total** | **56** |

Across all 84 source tables (categories intentionally overlap): 47 use vertical merge, 32 horizontal merge, 24 mixed merge, 17 explicit multi-level headers, 59 explicit one-row headers, 4 are regular, and 1 is nested. No table has an unrecoverable `tblGrid` width inconsistency, `gridBefore/gridAfter` irregularity, orphan `vMerge` continuation, or invalid span in this DOCX.

## New Canonical table structures

The sole formal Canonical contract now distinguishes:

```text
physical table → physical row → physical cell
                                 │
                                 ├─ physical_to_logical_cell → logical cell
                                 │                              ├─ logical row
                                 │                              └─ logical column(s)
                                 │
                                 └─ nested_table_in_cell → nested table

logical header cell ── header_for ──> logical data cell
```

`w:tblGrid`, `w:gridSpan`, `w:vMerge restart`, `w:vMerge continue`, direct nested `w:tbl`, and explicit `w:tblHeader` are parsed directly from OOXML. Every physical cell retains its own source span, physical index, row, logical start column, grid span, merge kind, and direct text witness. A logical cell records its origin physical cell, every covered logical coordinate, row/column span, all contributing physical cells, and any additional OOXML locators from vertical-merge continuations.

The Contract adds typed `logical_row`, `logical_column`, and `logical_cell` object types plus typed `table_contains_logical_row`, `table_contains_logical_column`, `logical_row_contains_cell`, `logical_column_contains_cell`, `physical_to_logical_cell`, `header_for`, and `nested_table_in_cell` relations. Logical IDs are source-derived and deterministic. Contract 1.0 snapshots remain valid because the manifest reader accepts both 1.0 and 1.1, while new builds emit 1.1.

Header semantics are intentionally structural, not heuristic. Consecutive explicit `w:tblHeader` rows become one or more header levels, and explicit `w:tblLook/@w:firstColumn` becomes a row-header column; each later logical data cell receives its effective header path and typed `header_for` relations. The implementation does not invent headers from visual first-row/first-column order when OOXML lacks either marker.

Nested parent-cell text now excludes nested-table descendants. The nested table has its own table/row/cell/locator/provenance graph; the outer physical cell points to it explicitly. This prevents accidental flattening of a nested table into outer-cell text.

## Real-document result and Gold eligibility

| Object type | Complete | Partial |
| --- | ---: | ---: |
| table | 83 | 1 |
| physical row | 973 | 6 |
| physical cell | 5,128 | 15 |
| logical row | 973 | 6 |
| logical column | 495 | 4 |
| logical cell | 4,375 | 15 |

Thus **55 of the original 56 partial tables** are now complete; total complete tables rise from **28 to 83**. This is not a blanket status upgrade: a table is complete only when its OOXML grid, all spans, vertical-merge origin/continuation sequence, and physical→logical mapping are uniquely recovered.

For formal Gold use, the policy is stricter than `complete`: the table must be complete **and** have an explicit, explainable header-to-data relation. The Canonicalizer writes this as `gold_evidence_eligible = true|false` on the table and every derived table object; `CanonicalDocument.require_complete_object`, the Authoring workflow, Admission policy, and Formal Dataset Validator fail closed when it is `false`. That yields **76 Gold-eligible tables**. All other tables are prohibited as table-level formal Gold evidence:

| Gold-prohibited set | Why |
| --- | --- |
| `table:00003` | The outer parent contains a nested table. Its child (`table:00084`) is represented independently, but the combined outer-table semantic surface is deliberately partial rather than flattened. |
| `table:00001`, `00002`, `00022`, `00029`, `00043`, `00082`, `00084` | Their physical/logical topology is complete, but OOXML supplies no explicit header row. The Platform will not infer a header path from visual order, so these seven table roots cannot become formal Gold evidence under the strict header-explainability rule. |

The remaining limits are not demonstrated parser defects: the source verifier found no mismatch. They are document-semantic limits—nested-content composition in the outer table and absent structural header declarations. A future manually adjudicated schema could make a bounded case-specific decision, but it must create a new reviewed Canonical/authoring revision; this phase does not silently elevate them.

## Source-side verification and safety checks

The real-document verifier parses `word/document.xml` directly and checks every Canonical physical cell against source OOXML:

- 84 source tables match 84 Canonical tables;
- 5,143 raw physical cells match exactly by table, row, physical-cell index, direct text witness, logical start column, `gridSpan`, and `vMerge` kind;
- 5,143 `physical_to_logical_cell` mappings exist for complete physical cells;
- 4,766 `header_for` relations and one `nested_table_in_cell` relation are source-grounded;
- repeated canonicalization yields byte-identical object/relation artifacts and the same Canonical digest; and
- malformed span/merge fixtures fail closed and remain partial.

The implementation includes content-agnostic unit coverage in [test_complex_table_canonicalization.py](/Users/sakura/RAG/rag-eval-platform/tests/rag_eval_platform/test_complex_table_canonicalization.py): horizontal merge, vertical merge, mixed merge, multi-level and first-column headers, physical/logical mapping, deterministic rebuild, orphan continuation failure, grid overflow, grid-offset irregularity, source locator integrity, and nested-table non-flattening. Existing Canonical tests additionally cover 1.0 reader compatibility and fail-closed Gold eligibility.

```text
.venv/bin/python -m pytest \
  tests/rag_eval_platform/test_canonical_contract.py \
  tests/rag_eval_platform/test_complex_table_canonicalization.py -q
15 passed, 1 warning

.venv/bin/python scripts/run_complex_table_canonical_audit.py \
  --source-docx '/Users/sakura/RAG/XXX网站系统（S2A2G2）_V2.0.docx' \
  --output-root /Users/sakura/RAG/.rag-eval-complex-table-audit-v3 --reset
source-side verification passed; deterministic rebuild passed.

.venv/bin/python -m pytest -q
121 passed, 3 skipped, 1 warning
```

## Answers

1. **What were the original 56 partial tables?** The exclusive OOXML categories and counts are listed above; they are almost entirely merge/multi-header structures, plus one nested parent and one nested child.
2. **What complex-table capabilities were added?** Physical/logical topology, span recovery, merge origins and coverage, explicit header paths, typed header/data links, nested parent-cell links, direct-cell text boundaries, multi-locator provenance, and deterministic logical IDs.
3. **How many became complete?** 55; complete table count is 28 → 83.
4. **How many can now be Gold?** 76 table roots satisfy the stricter complete-plus-explicit-header-relation rule.
5. **Which remain unsafe?** The nested outer parent `table:00003` and seven headerless tables listed above; their logical content must not be used as table-level formal Gold evidence.
6. **Are the remaining issues parser defects or DOCX ambiguity?** The audit found no source/canonical mismatch. The limits are intentional conservative handling of nested composition and missing structural header semantics in the DOCX.
7. **Is this sufficient for subsequent large-scale Case/Gold authoring?** Yes for development authoring from the 76 eligible tables and the previously eligible complete paragraphs/text spans, subject to the existing Ledger, review, admission, validator, and release gates. It does not authorize use of the eight prohibited tables, held-out authoring, or any RAG work.
