# Real DOCX Canonical Data Audit

## Scope and result

This audit processed the actual source document, `XXX网站系统（S2A2G2）_V2.0.docx`, through the Platform DOCX canonicalizer and Canonical Data Model 1.0.  It did not create Cases, Gold, a Benchmark Bundle, a Release, or execute any RAG component.

The body content is reproducibly canonicalized and has a safe subset for later Case/Gold authoring.  The document is **not** fully canonical-complete: non-empty headers/footers are outside the current traversal, and several rich or merged structures are deliberately partial or unsupported.  Those sources must not become formal Gold evidence.

| Item | Value |
| --- | --- |
| Source SHA-256 | `7d50899d15356000782b292bb84e135e4f1ebe20672ba9799939a6a1e2861755` |
| Canonical schema | `1.0` |
| Parser | `rag-eval-authoring-ooxml/1` |
| Canonicalizer | `rag-eval-authoring-canonicalizer/2` |
| Configuration digest | `01d21f985ed1e056f3cd8351b926199e1c4111ada7c0a8c0370fa0b45d5e1cc6` |
| Canonical document ID | `doc-7d50899d15356000` |
| Canonical document digest | `a2955ee975c9d5d42ed126fa050a7bdd6cee7e91aaa90958cfe8a25e1de18271` |
| Object digest | `743a35ce2d7eb6757a86d7b2a8a0f7b3a3cccea9a7aee21226912fe35380f142` |
| Relation digest | `09d174a07123623e05bd5dce96cc62be912dc5ae1b766b38df3f549a4ba109c1` |
| Objects / relations | 8,308 / 29,452 |
| Bundle 2.0 compatibility projection digest for this temporary authoring workspace | `747c9b63595532c499a1834baa9c5c9d6cca09a64aabeba61163899f10c04509` |

Two independent uploads of the same bytes produced the same Canonical digest and byte-identical `canonical-objects.v1.jsonl` and `canonical-relations.v1.jsonl` artifacts.

## Source inventory and representation status

The source package contains 718 non-empty or rich body paragraphs, 83 top-level tables plus one nested table, 979 physical rows, and 5,143 physical cells.  It also contains two inline drawings, three VML shapes, three OLE objects, 17 OMML equations, 192 bookmark starts, one footnote definition, and one endnote definition.

Canonical statuses below use the formal meanings: `complete` is eligible for subsequent evidence review, while `partial`, `unsupported`, and `missing` are fail-closed.

| Canonical object type | Complete | Partial | Unsupported | Missing | Total | Audit interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| document | 1 | 0 | 0 | 0 | 1 | Provenance container |
| section | 100 | 0 | 0 | 0 | 100 | Document body plus 99 detected headings |
| heading | 99 | 0 | 0 | 0 | 99 | Source text and hierarchy retained |
| paragraph | 562 | 0 | 0 | 0 | 562 | Body prose retained |
| text span | 712 | 2 | 0 | 0 | 714 | Two follow unresolved captions |
| caption | 55 | 2 | 0 | 0 | 57 | 55 are linked to their adjacent table; two have no table/figure target |
| table | 28 | 56 | 0 | 0 | 84 | 55 merged/irregular tables and one nested table are partial |
| row | 193 | 786 | 0 | 0 | 979 | Mirrors table status |
| cell | 825 | 4,318 | 0 | 0 | 5,143 | All physical cells retained; partial follows merged/irregular table topology |
| figure | 2 | 3 | 0 | 0 | 5 | Inline drawings complete; VML shapes partial |
| equation | 0 | 17 | 0 | 0 | 17 | OMML surface text only |
| reference | 190 | 352 | 0 | 0 | 542 | 190 bookmarks; 190 cross-reference fields and 162 other fields |
| footnote | 0 | 0 | 1 | 0 | 1 | Definition is unanchored in body |
| endnote | 0 | 0 | 1 | 0 | 1 | Definition is unanchored in body |
| embedded object | 0 | 0 | 3 | 0 | 3 | OLE payloads are intentionally unsupported |
| **Total** | **2,767** | **5,536** | **5** | **0** | **8,308** | |

`missing = 0` above means no emitted Canonical object falsely claims a missing representation.  It does **not** mean every OOXML part was processed: the package has 15 header/footer parts, 10 of them non-empty, and current Canonicalization does not traverse them.  This is recorded below as a source-coverage gap, not counted as complete data.

Reference accounting is intentional and auditable.  Of 192 bookmark starts, 190 meaningful body bookmarks were retained.  The excluded two are an empty body bookmark and a `_GoBack` marker inside a table.  The source has 378 `instrText` XML fragments; 352 non-empty field instructions became partial reference objects, while 26 whitespace-only fragments carry no reference semantics.  Of 190 cross-reference objects, 133 have a verified `reference_to` target; the other 57 remain partial and cannot be used as evidence.

## Structure and locator audit

The formal `CanonicalDocument` validates its manifest, object IDs, document order, relation endpoints, relation shapes, section hierarchy, sibling parents, table topology, and relation digests before artifacts are written.

| Check | Result |
| --- | ---: |
| Canonical objects with a direct source span | 8,308 / 8,308 (100%) |
| Relations with source-span provenance | 29,452 / 29,452 (100%) |
| Non-document objects without a `parent_child` parent | 0 |
| Negative / invalid `body_ordinal` locators | 0 |
| Duplicate Canonical object IDs | 0 |
| Impossible `document_order` edges | 0 |
| Broken relation endpoints or relation-shape violations | 0 |
| `caption_of` relations | 55 |
| `reference_to` relations | 133 |

| Relation type | Count |
| --- | ---: |
| `parent_child` | 8,307 |
| `sibling` | 6,429 |
| `section_hierarchy` | 99 |
| `document_order` | 8,307 |
| `table_contains_row` | 979 |
| `row_contains_cell` | 5,143 |
| `caption_of` | 55 |
| `reference_to` | 133 |

The 84 table records have exactly 979 `table_contains_row` and 5,143 `row_contains_cell` edges, matching the raw physical topology.  Canonical IDs remain distinct even where the document itself repeats labels or values; repeated text is not treated as duplicate objects.

During this audit, three parser defects were corrected and the canonicalizer was versioned to `/2`:

1. Nested-table body locators had used Python proxy identity and could vary between rebuilds.  They now use the XML body's structural index, and a negative body ordinal is rejected by the Canonical contract.
2. `m:oMathPara` wrappers had caused a nested `m:oMath` to be counted twice.  The 17 raw OMML equations now map to exactly 17 partial Canonical equations.
3. This document places most captions immediately before their tables.  The canonicalizer now creates `caption_of` only for adjacent preceding or following tables/figures, yielding 55 verified relations; it leaves the remaining two partial rather than guessing.

Bookmarks in heading paragraphs are now preserved, rather than silently skipped while advancing section state.

## Content accuracy audit

This was a source-side comparison, not merely a schema check.

| Audit slice | Method | Result |
| --- | --- | --- |
| Body text | Re-extracted all 718 canonical heading/paragraph/caption witnesses from `word/document.xml` using each locator | 718 compared, 0 mismatch (100%) |
| Tables | Recomputed normalized table witness text from the raw 83 top-level and one nested table | 84 compared, 0 mismatch (100%) |
| Row/cell topology | Compared physical raw row/cell totals with Canonical topology relations | 979 rows and 5,143 cells, exact match |
| Figures | Compared raw drawing inventory | 2 inline + 3 VML = 5 Canonical figures; VML remains partial |
| Equations | Compared raw OMML inventory after wrapper de-duplication | 17 raw = 17 partial Canonical equations |
| Captions | Checked adjacency in source order | 55 correctly associated; 2 explicitly unresolved |
| Rendered-layout spot check | Rendered 105 pages and inspected pages 1, 5, 20, 40, 60, 80, 100, and 105, including dense merged-table regions | No sampled rendering anomaly; not a substitute for full visual/layout semantics |

The 100% text-witness comparison must not be misread as 100% table semantics.  A merged or nested table's words are retained exactly, but the current logical cell model cannot guarantee a lossless interpretation of all merge semantics.  Those 56 tables, their 786 rows, and their 4,318 cells remain partial by design.

## Findings and impact

| ID | Severity | Finding | Impact / disposition |
| --- | --- | --- | --- |
| CA-001 | MAJOR | Ten non-empty header/footer parts are not traversed into Canonical objects. | Full-document completeness cannot be claimed.  Header/footer content is prohibited as Gold evidence until explicitly modeled and parsed. |
| CA-002 | MAJOR | 56/84 tables are merged, irregular, or nested and therefore partial. | Their values may help human navigation only; they and their descendant rows/cells are prohibited as formal Gold evidence. |
| CA-003 | MAJOR | VML shapes (3), OLE objects (3), and OMML equations (17) lack a lossless semantic representation. | VML and OMML are partial; OLE is unsupported.  None may be formal Gold evidence. |
| CA-004 | MINOR | Two caption-style paragraphs have no adjacent table/figure target. | They remain partial, have no `caption_of` edge, and are prohibited as evidence. |
| CA-005 | MINOR | Fifty-seven field-based cross references do not resolve to a verified bookmark target. | They remain partial; no unsupported reference topology is presented as complete. |
| CA-006 | ACCEPTABLE_LIMITATION | One footnote and one endnote are unanchored; three OLE payloads are opaque. | They are explicitly marked unsupported, with locators/provenance retained. |
| CA-007 | ACCEPTABLE_LIMITATION | Page numbers are supplementary review metadata, not Canonical locators. | No page-based Gold evidence or page-only traceability is permitted. |

There is no current `BLOCKER` for authoring from the verified body subset.  CA-001 is a blocker only for any prospective Case/Gold that relies on header/footer content; it prevents describing this as a complete representation of every source part.

## Gold-evidence eligibility

Eligibility is based on the actual object status and locator, not on object count.  `partial`, `unsupported`, or `missing` objects fail closed even where the text looks plausible.

| Object class | Eligibility in this document |
| --- | --- |
| Complete paragraph / text span | **Allowed** after normal Case/Gold review.  Must retain the Canonical ID and source span. |
| Complete table / row / cell | **Allowed** after review, only within the 28 complete tables (193 rows, 825 cells). |
| Complete heading | **Supporting context by default**; may support a precisely worded claim only after reviewer approval. |
| Complete section / document | **Structural provenance only**, never answer evidence. |
| Complete caption | **Supporting context only**; not standalone factual evidence without the associated complete target. |
| Complete inline figure | **Supporting metadata only**.  The Canonical object describes locator/alt metadata, not image semantics. |
| Complete bookmark reference | **Navigation/topology only**, not answer evidence. |
| Any partial table/row/cell/caption/text span/figure/equation/reference | **Prohibited** as formal Gold evidence. |
| Footnote, endnote, embedded object | **Prohibited**; unsupported. |
| Header/footer material | **Prohibited**; currently absent from Canonical traversal. |

## Verification

The regression tests do not embed any content from the real source document.  They exercise generic DOCX fixtures and cover contract hierarchy/topology, invalid locator fail-closure, repeated-build digest stability, nested-table locator stability, OMML wrapper de-duplication, caption topology, and heading-bookmark preservation.

```text
PYTHONPATH=src .venv/bin/pytest -q tests/rag_eval_platform/test_canonical_contract.py
8 passed
```

The complete Platform suite also passed: `114 passed, 3 skipped`.  The audit itself rebuilt the actual DOCX twice and compared the emitted Canonical object and relation bytes exactly.

## Required conclusions

1. **Was the real DOCX converted into complete Canonical data?** Not completely.  Its body has a reproducible, structurally valid Canonical representation; non-empty headers/footers and several rich structures are not fully represented.
2. **Which types are reliable?** Body sections, headings, paragraphs, text spans, the 28 unmerged tables and their 193 rows/825 cells, 55 caption-to-table relations, inline-drawing metadata, and meaningful bookmarks.
3. **Which are partial/unsupported/missing?** 56 tables and descendants, 17 equations, 3 VML figures, 352 fields/references, two captions/spans are partial; three OLE objects and the unanchored footnote/endnote are unsupported; ten non-empty header/footer parts are outside the Canonical traversal.
4. **Are tables and rich structures accurate enough?** Table text and physical topology match source exactly, but only 28 tables are semantically safe Gold sources.  Rich structures are not sufficiently lossless for Gold.
5. **Are there Gold-polluting parse errors?** No in the allowed complete-body subset.  The identified risky material is marked partial/unsupported or absent and is explicitly prohibited.
6. **Which objects are prohibited as Gold evidence?** All partial, unsupported, missing, header/footer, figure-semantic, equation, reference, note, embedded-object, and merged/nested-table material, as detailed above.
7. **Can Canonical data support Case/Gold generation now?** Yes, conditionally: author only from complete body paragraphs/text spans and the 28 complete tables/rows/cells, with normal review and formal validation.
8. **If not fully complete, what blocks it?** Header/footer traversal is the full-document coverage blocker.  Merge-aware table semantics and rich-object parsing are additional gaps for those specific source regions.
9. **Next step?** Begin restricted Case/Gold Authoring from the eligible subset; schedule Canonical parser work before using header/footer, merged/nested tables, VML/OLE, equations, notes, or unresolved cross references.

No frozen 20-case Bundle, Bundle ID, Gold revision, Release, or historical run reference was modified during this audit.
