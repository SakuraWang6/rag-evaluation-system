# LightRAG Structural Context Representation / Evidence Pack

**Status: PASS for the structural metadata bridge and fixed-budget context
organization experiment.** The bridge is provenance-backed and fail-closed;
the organization experiment completed on the full frozen 20-case Bundle. No
production ranking default, Platform contract, Adapter contract, Dataset,
Gold, scorer, metric definition, or evaluation contract was changed.

## Scope and frozen inputs

This phase keeps `final_context_k=5` and the previously accepted Conservative
Segment ordering as the ranking baseline. It does not tune Segment MaxSim,
replacement caps, or deep-tail guards. The structural experiment replays the
already-completed full-benchmark ranking result after validating candidate IDs,
content digests, question digests, and complete rank permutations. It therefore
does not perform a new embedding or LLM run and does not change the frozen
ranking trace.

| Item | Frozen value |
| --- | --- |
| Bundle | `d4961dd43640e087d19a9b7c3a8fc6ab23e88b571e8372a5f5aeccf71378d71e` |
| Source run | `4f9d2df532604bccbad7efdcebb8dd10` |
| Execution source | `documents/doc-7d50899d15356000.md` |
| Execution source SHA-256 | `65f03397ae45ae9e2cfa306c86ca1e3f89f408377f7a8f6bd3aada05d7a1c214` |
| Canonical sidecar | `canonical/evidence.jsonl` |
| Canonical sidecar SHA-256 | `37917f8de1163201abd3d926245e4b4d3ad016059f7ea22f2f8ff2890a5b993b` |
| Candidate pools | frozen BGE-M3 raw `k=20` and `k=50` |
| Final context | fixed five runtime chunks |
| Ranking source config digest | `130a4967838447a534aa4b9a7c1f027a64f46ecd85f8c55b464595b297177ed7` |
| Structural config digest | `de025a855552da4b18a271cb18f518cea066e8d357f3d081e5456b3adcdafc36` |
| Provenance map SHA-256 | `089014fa6a06170a904e2c7f7d7973b2927d054b64b57680022bb58678b52f3b` |
| Structural result SHA-256 | `f3c06ddd9274351a1b2212b1a58ba0c10505e3cba14c572b5b43c48f34577882` |
| Answer generation | disabled |

The result and provenance JSON files are private run artifacts under
`/private/tmp/lightrag-structural-context-20260828/`; this committed report
contains no private document text or question text.

## Structural metadata loss audit

The previous all-empty `heading_path` / `body` representation was traced
through the actual data flow rather than inferred from candidate text.

| Layer | Observed behavior | Finding |
| --- | --- | --- |
| Canonical document | The execution Markdown source is 2,623 lines with 99 exact Markdown heading lines. The canonical sidecar contains 8,241 canonical records; 6,496 align to the execution source, with 100 section records. | Hierarchy and object topology exist in the canonical inputs. |
| Platform bundle API | `bundle.source_documents()` intentionally returns `canonical_path` when present, which is the JSONL evidence view. | This API is correct for evidence matching, but it is not the execution source. |
| Platform execution staging | `source_only_documents()` reads `manifest.documents[0].path` as the execution input and stages `canonical_path` as a sidecar. | LightRAG receives the Markdown execution view and the canonical sidecar separately. |
| Previous structural harness | The old harness called `bundle.source_documents()` and then scanned it for Markdown headings. JSONL has no Markdown heading structure. | The loss occurred in the harness source selection, producing empty heading paths and a `body` fallback; it was not a LightRAG chunk-generation loss. |
| LightRAG chunk generation / persistence | 58 persisted runtime chunks were checked against the execution source: content and source span matched 58/58. | Chunk generation did not lose the source span; it never owned canonical hierarchy metadata. |
| Adapter projection | The earlier bridge carried runtime ID, source span, witness digest, and canonical object references, but not section hierarchy. The new fields are additive metadata on evidence items. | No Adapter contract field was changed. |
| Retrieval trace serialization | The frozen raw trace contains runtime IDs, content, scores, and spans. The formal structural harness joins it to the verified v2 map and rejects ID/span/content mismatches. | Structure is restored by a checked provenance join, not by text heuristics. |

The root cause is therefore **harness representation selection**, followed by a
missing hierarchy projection in the first provenance bridge. It is not an
execution semantic drift between Direct LightRAG and Platform → Adapter →
LightRAG.

## Provenance / metadata bridge implementation

Adapter commit `0b47f866` raises the canonical map to schema v2. Each aligned
canonical object now preserves, when available:

- canonical object ID, object type, exact execution source span, and witness
  digest;
- document order, section ID, heading path, parent section, object role, and
  parent object ID;
- per-parent sibling index/count and preceding/following sibling object IDs;
- table ID, row ID, row index, and column index;
- explicit `metadata_status` (`complete`, `partial`, or `missing`) and
  `missing_fields`.

The map materializes section active intervals from aligned canonical heading
spans. A chunk crossing a heading boundary is marked `partial` and carries all
overlapping section IDs; it is not silently assigned to one section. The bridge
also preserves runtime token counts from the persisted LightRAG chunk record.

LightRAG commit `af46e358` consumes only this verified map in formal structural
runs. `candidates_from_trace(..., provenance=...)` checks the runtime ID,
source span, and content SHA-256 before accepting structure. Missing or partial
metadata remains explicit. The source-only heading scanner remains only for
legacy unit tests and historical diagnostics; it is not used by the formal
structural experiment.

The current bridge exposes reliable per-parent adjacency. A global
preceding/following relation is not invented because canonical table children
share body ordinals and may have overlapping spans; such a relation needs an
explicit canonical ordering contract before it can be promoted from partial
metadata.

## Metadata coverage

### Canonical map

| Quantity | Count |
| --- | ---: |
| Runtime chunks in persisted map | 58 |
| Runtime structure: complete / partial / missing | 34 / 22 / 2 |
| Runtime content/span verified against persisted chunks | 58 / 58 |
| Canonical aligned objects | 6,496 |
| Canonical object structure: complete / partial | 5,614 / 882 |
| Canonical section records | 100 |
| Canonical sections: complete / partial | 99 / 1 |
| Canonical refs with unknown object IDs | 0 |
| Reverse object → runtime mapping gaps | 0 |

Canonical field coverage over the 6,496 aligned objects is:

| Field | Present |
| --- | ---: |
| `document_order` | 6,496 |
| `section_id` | 6,496 |
| `heading_path` | 5,614 |
| `parent_section_id` | 5,614 |
| `object_role` | 6,496 |
| `parent_object_id` | 6,496 |
| `preceding_sibling_object_id` | 5,116 |
| `following_sibling_object_id` | 4,871 |
| `table_id` | 4,605 |
| `row_id` | 4,529 |

### Retrieval candidates

The raw candidate audit covers all 20 cases, not only the prior failure cohort.

| Candidate cutoff | Candidates | Complete | Partial | Missing | Non-empty heading path |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | 400 | 197 | 181 | 22 | 305 |
| 50 | 1,000 | 559 | 401 | 40 | 836 |

Thus formal candidate structural observability is 94.0% at both cutoffs; this
is distinct from complete metadata coverage, because partial provenance is
observable and remains explicitly labeled.

## Integrity and round-trip tests

The new coverage is protected by tests for canonical object → runtime chunk,
runtime chunk → canonical object, exact spans and witness digests, heading and
parent-section projection, document order, table/row/cell topology,
multi-object and overlapping chunks, missing/partial provenance, Adapter
evidence-item serialization round-trip, and trace candidate validation.

Relevant focused tests include:

- Adapter `tests/rag_eval_adapters/test_canonical_provenance.py`: four tests,
  including `test_structure_bridge_preserves_hierarchy_table_topology_and_round_trips`
  and `test_missing_and_partial_provenance_fail_closed`.
- LightRAG `tests/evaluation/test_frozen_ranking_context.py`: eight tests,
  including verified-structure, section-aware organization, and Evidence Pack
  fixed-budget checks.

The full test results are recorded below; the focused structural suites passed
before the formal report was written.

## Evidence Pack design

The experiment has five variants, all with `final_context_k=5`:

1. Baseline BGE-M3 top five.
2. Conservative Segment ranking.
3. Conservative Segment plus structural metadata, with the same order.
4. Conservative Segment plus section-aware organization.
5. Conservative Segment plus Evidence Pack representation.

The section-aware policy is deliberately small and document-only:

- preserve the first two Conservative Segment selections;
- cap complete sections at two selected chunks;
- defer duplicate-section candidates and fill from the deterministic remainder;
- treat partial/missing metadata as ineligible for suppression and fall back to
  the original order when a structural decision is unsafe.

The Evidence Pack variant emits an evidence unit containing runtime chunk ID,
evidence text, heading path, source span, section ID, object types, parent
heading path, and verified preceding/following canonical sibling IDs. Neighbor
expansion is metadata-only in this phase: no extra source text is appended and
the five-chunk context budget is unchanged. Metadata is therefore tested as a
selection/organization signal before any prompt design is attempted.

No variant uses Gold Evidence, Gold locators, reference answers, failure labels,
or scorer output to select candidates. Gold is used only by the unchanged
Platform evaluator after selection to calculate the reported metrics.

## Full frozen 20-case experiment

`Candidate Gold Coverage` is required-evidence coverage at the candidate cutoff.
`Preserved/unchanged correct` is the number of cases already correct at that
cutoff's baseline and still correct. Rescue, regression, and unchanged failure
are defined by the unchanged Context Recall@5 contract.

| k | Variant | Candidate Gold Coverage | MRR | R@1 | R@3 | R@5 | Rescued | Preserved correct | Regression | Unchanged failure |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | Baseline BGE-M3 | 0.80 | 0.347 | 0.20 | 0.40 | 0.50 | 0 | 10 | 0 | 10 |
| 20 | Conservative Segment | 0.80 | 0.459 | 0.30 | 0.55 | 0.75 | 5 | 10 | 0 | 5 |
| 20 | + structural metadata | 0.80 | 0.459 | 0.30 | 0.55 | 0.75 | 5 | 10 | 0 | 5 |
| 20 | + section-aware organization | 0.80 | 0.468 | 0.30 | 0.60 | 0.75 | 5 | 10 | 0 | 5 |
| 20 | + Evidence Pack | 0.80 | 0.459 | 0.30 | 0.55 | 0.75 | 5 | 10 | 0 | 5 |
| 50 | Baseline BGE-M3 | 0.90 | 0.350 | 0.20 | 0.40 | 0.50 | 0 | 10 | 0 | 10 |
| 50 | Conservative Segment | 0.90 | 0.462 | 0.30 | 0.55 | 0.75 | 5 | 10 | 0 | 5 |
| 50 | + structural metadata | 0.90 | 0.462 | 0.30 | 0.55 | 0.75 | 5 | 10 | 0 | 5 |
| 50 | + section-aware organization | 0.90 | 0.472 | 0.30 | 0.60 | 0.75 | 5 | 10 | 0 | 5 |
| 50 | + Evidence Pack | 0.90 | 0.462 | 0.30 | 0.55 | 0.75 | 5 | 10 | 0 | 5 |

The prior fixed-pool Oracle reference is `R@5=0.80`. The best current safe
result is `0.75`, leaving a 0.05 gap. Structural metadata alone does not
change selection. Section-aware organization improves MRR and R@3 without
changing R@5 or causing regression. Evidence Pack currently changes the
representation, not the selected five chunks, so its retrieval metrics remain
identical to Conservative Segment.

### Context organization diagnostics

Means are over the selected five chunks for the full 20-case benchmark.

| k | Variant | Duplicate-section rate | Same-section concentration | Evidence diversity | Span redundancy | Structural coverage | Complete coverage | Mean LightRAG tokens |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | Baseline | 0.230 | 0.450 | 0.200 | 0.00522 | 0.940 | 0.470 | 5,999.5 |
| 20 | Conservative Segment | 0.165 | 0.370 | 0.180 | 0.00633 | 0.940 | 0.380 | 5,999.4 |
| 20 | Section-aware | 0.050 | 0.270 | 0.190 | 0.00585 | 0.900 | 0.290 | 5,999.4 |
| 20 | Evidence Pack | 0.165 | 0.370 | 0.180 | 0.00633 | 0.940 | 0.380 | 5,999.4 |
| 50 | Baseline | 0.230 | 0.450 | 0.200 | 0.00522 | 0.940 | 0.470 | 5,999.5 |
| 50 | Conservative Segment | 0.165 | 0.370 | 0.180 | 0.00633 | 0.940 | 0.380 | 5,999.4 |
| 50 | Section-aware | 0.050 | 0.270 | 0.190 | 0.00585 | 0.900 | 0.290 | 5,999.4 |
| 50 | Evidence Pack | 0.165 | 0.370 | 0.180 | 0.00633 | 0.940 | 0.380 | 5,999.4 |

The section-aware policy reduced duplicate-section rate from 0.23 to 0.05 and
same-section concentration from 0.45 to 0.27, while keeping the five-chunk
budget and R@5 unchanged. The slight decrease in complete structural coverage
is expected from its conservative treatment of partial/missing provenance; it
does not claim structure where the bridge cannot prove it.

## Case-level transition matrix

The status transition is identical at `k=20` and `k=50`: the same frozen raw
prefixes and safe Conservative selections are retained. The table also records
the selected **raw baseline ranks** for Conservative Segment and section-aware
organization. Evidence Pack has the same selected ranks as Conservative Segment.

| Case | Baseline → Conservative | Baseline → Section-aware | Conservative raw ranks | Section-aware raw ranks |
| --- | --- | --- | --- | --- |
| `case-09a8ceb2fd234fa792053c48363f488b` | failure → failure | failure → failure | 1,9,3,4,5 | 1,9,3,4,2 |
| `case-0dd707b2ed894a959706d58dda84625d` | failure → failure | failure → failure | 1,19,3,7,4 | 1,19,3,7,4 |
| `case-37308a726ef441d08f085367ac2a6c70` | correct → preserved | correct → preserved | 2,6,1,4,3 | 2,6,1,4,3 |
| `case-6f4c41dbfd8649c1a42f789b82204736` | failure → failure | failure → failure | 2,3,1,4,5 | 2,3,4,6,9 |
| `case-6f8984c0b5d8431d9c591dc7a8e8bf0a` | correct → preserved | correct → preserved | 1,16,2,12,3 | 1,16,2,12,3 |
| `case-874745d934d24e3c85e6d2acf7d17fec` | failure → rescue | failure → rescue | 7,1,5,2,4 | 7,1,5,2,4 |
| `case-99c5a254df1a4b73a29a098368acf527` | failure → rescue | failure → rescue | 5,2,1,4,6 | 5,2,6,8,9 |
| `case-a68460e6f98542e7be69f243d234c3a6` | failure → rescue | failure → rescue | 20,5,2,8,1 | 20,5,2,8,1 |
| `case-b72d79202f5b41de9b345fa75c1375a9` | correct → preserved | correct → preserved | 1,2,12,5,3 | 1,2,12,5,7 |
| `case-bcfdc5a86d53445297cff3aed59e05fc` | correct → preserved | correct → preserved | 1,3,2,5,4 | 1,3,2,5,4 |
| `case-c191d27a84ca42a684a72f2ea84fe0a3` | failure → rescue | failure → rescue | 1,10,11,3,4 | 1,10,11,3,4 |
| `case-cc787fe6dab24d0d958270c977b76f3d` | correct → preserved | correct → preserved | 1,3,7,5,2 | 1,3,7,4,6 |
| `case-ccd246a577734bb1986e1b43c1fce62a` | correct → preserved | correct → preserved | 1,5,3,2,4 | 1,5,3,2,8 |
| `case-db0c0c9312414a1584a8c4d6df0a83ec` | correct → preserved | correct → preserved | 6,1,2,4,5 | 6,1,2,4,5 |
| `case-decc05076bc84b95acbdea784dbdb4f9` | failure → rescue | failure → rescue | 13,14,4,1,3 | 13,14,4,1,3 |
| `case-e59e310bde1e456fa047ff1d997b7581` | correct → preserved | correct → preserved | 6,1,3,2,4 | 6,1,2,4,12 |
| `case-e81b1553b4d64bbfbd872f95fab83dad` | failure → failure | failure → failure | 1,3,6,5,4 | 1,3,6,5,4 |
| `case-e95211e1e6d24d74b40ecdf9533a82fa` | failure → failure | failure → failure | 5,2,6,4,1 | 5,2,6,4,1 |
| `case-e9a763b99ca5407294c57158d995bbbb` | correct → preserved | correct → preserved | 1,2,3,5,12 | 1,2,3,5,12 |
| `case-f5d5c8e7ec554295b34aa010a6947d4b` | correct → preserved | correct → preserved | 2,1,3,4,5 | 2,1,3,4,5 |

The transition counts for every non-baseline variant at both cutoffs are:

| Transition | Count |
| --- | ---: |
| Rescue | 5 |
| Preserved correct | 10 |
| Regression | 0 |
| Unchanged failure | 5 |

## `case-0dd...` structural analysis

`case-0dd707b2ed894a959706d58dda84625d` remains the primary
candidate-present context-organization gap.

- The Gold-matched runtime chunk is present at raw baseline rank 8 and is rank
  9 after Conservative Segment. It is not in the final five for any structural
  variant at either candidate cutoff.
- Its metadata is **partial but informative**: it has a non-empty verified
  heading path, document-order range, section IDs, table IDs, and canonical
  object types spanning block, cell, reference, row, section, table, and
  text-span records. It is marked partial because its verified source span
  crosses section intervals; the bridge does not collapse that into a false
  single-section claim.
- The main competing candidate in the Conservative final context is in the
  same verified section family. It has complete section metadata, while the
  Gold chunk is a multi-object, cross-boundary representation. Section-aware
  organization therefore correctly identifies the local section relation but
  cannot distinguish the intra-section semantic near-match from the
  provenance-correct evidence.
- Selected raw ranks are identical for Conservative Segment, structural
  metadata, section-aware, and Evidence Pack: `1,19,3,7,4`. No structural
  variant rescues this case, and no extra text is injected to manufacture a
  rescue.

Conclusion: reliable heading and section metadata removes the previous
observability blind spot, but it does not by itself solve fine-grained
same-section evidence discrimination. The remaining problem is an evidence
granularity / local semantic selection problem, not evidence that the heading
metadata is wrong.

## Deep-pool cases and retrieval-track classification

| Case | Raw Gold rank at k=50 | Conservative rank | Section-aware selected raw ranks | Result | Classification |
| --- | ---: | ---: | --- | --- | --- |
| `case-09a8ceb2fd234fa792053c48363f488b` | 21 | 21 | 1,9,3,4,2 | Not in top five | Deep-tail ranking/context; current guard intentionally preserved. |
| `case-e81b1553b4d64bbfbd872f95fab83dad` | 46 | 46 | 1,3,6,5,4 | Not in top five | Deep-tail ranking/context; current guard intentionally preserved. |
| `case-e95211e1e6d24d74b40ecdf9533a82fa` | absent | absent | 5,2,6,4,1 | Not in top five | **Retrieval-track**; no context organization can recover an absent candidate. |
| `case-6f4c41dbfd8649c1a42f789b82204736` | separate provenance/observability case | — | 2,3,4,6,9 | Not in top five | Keep separate from a proven retrieval miss until its evidence observability is resolved. |

The k=50 coverage increase from 0.80 to 0.90 does not increase safe final
Context Recall@5 above 0.75. Candidate-pool expansion and context organization
must therefore remain separate workstreams. In particular, the current
conservative deep-tail guard must not be removed merely to force the rank-21 or
rank-46 candidates into context.

## Conclusions and next phase

1. **Structural representation: PASS.** Canonical hierarchy, object types,
   source spans, table topology, sibling relations, and explicit partial/missing
   status now round-trip through the runtime map and Adapter evidence metadata.
   The old all-empty heading/body artifact is eliminated from formal runs.
2. **Context organization: PASS with no R@5 gain.** Section-aware selection
   reduces duplicate and same-section concentration, improves MRR/R@3, holds
   R@5 at 0.75, and produces zero regression across the full frozen benchmark.
   Evidence Pack is a valid fixed-budget representation, but its current
   metadata-only neighbor expansion does not yet change selection.
3. **Current gap to Oracle:** 0.05 (`0.80 - 0.75`). The observable candidate-present
   target is `case-0dd...`; deep-tail cases remain unsafe to force, and
   `case-e952...` is retrieval-track.
4. **Ranking decision:** do not continue pointwise Segment MaxSim parameter
   tuning or change the production default based on this benchmark. The safe
   Conservative Segment remains the ranking baseline.
5. **Answer Generation decision:** the metadata bridge is reliable enough to
   enter a controlled Answer Generation integration test that consumes
   Evidence Pack units, but prompt optimization should wait. The test should
   measure whether structured evidence presentation helps answers without
   changing retrieval selection or scoring contracts.
6. **Remaining tracks:** same-section evidence granularity / parallel-section
   discrimination belongs to context organization and evidence-pack research;
   `case-e952...` belongs to retrieval; the deep-pool rank-21/rank-46 cases need
   a separately justified evidence-preserving policy rather than a larger final
   context.

## Tests and commits

| Repository | Result |
| --- | --- |
| `rag-eval-adapters` | `34 passed, 4 skipped` |
| `LightRAG` focused evaluation / structural suites | `18 passed` |
| `rag-eval-platform` | `89 passed, 3 skipped` |
| Python compilation / diff check | passed |

An additional full LightRAG `pytest -q` collection was attempted. It was
blocked by 26 existing optional-backend/model import errors in the local
environment (`neo4j`, `qdrant-client`, Milvus, OpenSearch, Redis,
Anthropic/Bedrock, and related modules); the environment's dependency helper
could not install them. The structural suites themselves pass, and no failure
in that collection reached the changed bridge or organization code. This is an
environment/test-coverage limitation, not evidence of a structural regression.

Commits created for this phase:

- Adapter: `0b47f866` — `feat: bridge structural provenance metadata`
- LightRAG: `af46e358` — `feat: add structural context organization experiments`
- Platform: the documentation commit containing this report (recorded in the
  final repository status after commit).

No production default was changed.
