# Evidence Localization and Evaluation Repair

Status: IN PROGRESS — formal benchmark readiness is UNVERIFIED.

## Scope and preservation

The acceptance run is `2ad4ecfc4c9d4d3ba30baf0ad9f276b3`, under
`/Users/sakura/RAG/.rag-eval-real-benchmark-pilot/runs/`.
It contains 8 real cases and 19 Gold Evidence items. Every item must be audited
at Raw Retrieval, Ranked Retrieval, and Final Context (57 item-stage decisions).
Original source, cases, traces, summaries, reports, work artifacts, and run
manifest must not be overwritten. Reconstructed provenance and rescoring are
separate, versioned derivatives whose input hashes remain inspectable.

Implementation work is delegated to `gpt-5.6-luna` with `max` reasoning, interpreting
the user's `luan` request as that available model. The coordinating agent audits
the evidence and independently reviews acceptance. No new user-owned task is
created.

## Current-state audit (2026-09-04)

- The original run executed using a Docker worker. Its image identity is pinned
  in `execution-environment.json`; editing the host checkout alone does not
  update that image or prove a new formal runtime works.
- Logs show 8 queries with 20 raw chunks and 5 final-context chunks per query.
- The original provenance map has zero documents and zero runtime chunks.
- All 19 Gold locators resolve in the retained canonical source graph.
- The retained source DOCX and the parser's retained DOCX have the same SHA256:
  `7d50899d15356000782b292bb84e135e4f1ebe20672ba9799939a6a1e2861755`.
- Canonical records retain `ooxml-structural-v1` source coordinates. Parsed
  LightRAG blocks retain paragraph-ID ranges; table sidecars retain native
  table and block identities. The parser's `document_hash` is not the original
  DOCX byte hash and must not be treated as one.
- The source graph has 84 tables (including nested structure); the historical
  native table sidecar contains 83 tables. Equal numeric ID suffixes are not
  sufficient proof of object correspondence.
- There are 196 persisted runtime chunks. The existing exact-table fallback
  maps 19, fails on absent full-table markup for 94, incompatible grids for 43,
  ambiguous duplicate grids for 4, and missing source spans for 36.
- All 36 spanless chunks retain table sidecar references. Split-table lineage
  must use those references and actual row/cell coverage, not pretend that a
  synthesized table fragment occupies an exact substring of the full source.
- Historical presentation currently changes all evidence metrics for a case
  to unavailable if any stage reports unavailable provenance. Alternative-path
  handling also examines irrelevant unmatched alternatives. Both are defects.
- Current answer rules misjudge Chinese numeric answers and ASCII terms
  adjacent to Chinese text. Semantic review is manual and limited to text and
  formula answers, not the required automatic Rule -> LLM -> Human workflow.
- The run detail renders a bundle hash instead of the release display name.
  This legacy release has no stored business name; its API fallback is
  `real-pilot-1.0.0`, with 8 cases.

These are audit findings, not repaired acceptance results.

### Read-only runtime confirmation and implementation resumption

- The user requested a separate read-only investigation; implementation agents
  were interrupted for that investigation and resumed only when the active
  implementation goal was explicitly continued.
- The original Docker image was inspected with an ephemeral read-only,
  network-disabled container, without mounting the original run. Its installed
  adapter source matches the image's `/opt/rag-eval/adapter` source exactly
  (SHA256 `cb50c90891a7ef83af7ef77565b0d54355f2590d3e8b0701b9eea93f848a74ad`).
  `_load_canonical_provenance` returns `None` for native source-only documents;
  `_build_ingestion_provenance_manifest` consequently emits empty dictionaries.
  The installed adapter has no native-DOCX mapping entry point. This confirms
  the historical empty-map cause in the actual worker, not just host source.
- The live API still returns 19 unavailable evidence metrics with denominator
  0 and coverage 0, and answer accuracy 2/7. The stored original summary remains
  different. All 38 original baseline files still match their pinned hashes.
- The current grid-only host fallback was independently exercised in memory:
  19 full flags, 94 absent runtime tables, 43 unmatched grids, 36 missing spans,
  and 4 duplicate-grid ambiguities. These flags are not accepted formal proofs.
- After implementation resumed, the existing 14-case evidence-contract suite
  independently returned 12 passed / 2 failed. The remaining failures concern
  historical stage masking and cell-scope observability. A test expecting a
  definite miss from a bare table locator needs its observability assumptions
  checked; production checks must not be weakened solely to make it green.
- Formal-catalog review also requires negative proofs against self-declared
  `verified`/`full` flags, swapped object locators, empty forward edges, and
  absent source/trace/map pins. Schema version or a content hash alone cannot
  prove that returned content belongs to a claimed canonical object.

Baseline test observations (before implementation in this repair):

- Platform `test_evaluation.py`, `test_run_history.py`, `test_case_reviews.py`:
  19 passed (one existing Starlette/httpx deprecation warning).
- Adapter `lightrag/tests`: 4 passed.
- Expanded evidence-contract regressions, independently rerun with bytecode
  and pytest cache disabled: 5 failed, 4 passed. The failures cover stage
  poisoning, an unused alternative, diagnostic evidence, and partial-span
  unions/cutoffs. This is a failing acceptance baseline, not a release pass.
- These green baselines coexist with the demonstrated real-data failures and
  are explicitly not sufficient acceptance coverage.
- The original filename can be recovered without guessing: the existing
  `XXX网站系统（S2A2G2）_V2.0.docx` in the RAG workspace has exactly the pinned
  source SHA256 above. This is a verified source-name fallback, not a claim
  that a historical user-defined dataset name was stored.

## Ordered implementation and acceptance gates

| Gate | Required deliverable | Required proof | State |
|---|---|---|---|
| P0-A | Source/object/parsed/chunk lineage contract and implementation | Source digest and structural identity persist through real parser, chunker, adapter, raw/ranked/context; no Gold or answer used during ingestion | IN PROGRESS |
| P0-B | Historical 8-case localization matrix | 19 item rows x 3 stages, ranks, native IDs, source coordinates, coverage, method and reason; independent expected findings | PENDING |
| P1-A | Stage-aware evidence scoring | Alternatives, unrelated stages, partial unions and cutoff ranks tested; diagnostic evidence does not enter required-group denominator | PENDING |
| P1-B | Immutable versioned reconstruction/rescore | All original file hashes unchanged; versioned inputs/implementation/scorers; before/after metrics and explanations | PENDING |
| P2-A | Rule -> LLM -> Human answer review | Chinese numbers, term boundaries and contradictions tested; real local LLM review; durable state, uncertainty and explicit human override | PENDING |
| P2-B | Result-page integration | Dataset name/version/count; metric sample/coverage/reasons; genuine localization counts; source jump in modal; browser/API verification | PENDING |
| FINAL | Repair report and formal benchmark go/no-go | Requirement-by-requirement evidence, commands/results, matrix, metric deltas, unresolved risks, runnable worker identity | UNVERIFIED |

## Localization contract constraints

- The formal path joins stable source identities and structural lineage.
  Text matching may be used only in explicitly labeled historical recovery.
- A source locator alone does not establish full evidence coverage. Paragraph
  intervals and table row/cell scopes must be retained. A partial chunk is not
  a complete paragraph or complete table.
- Coverage may be combined only with verifiable ranges from the same source
  object. Recall@k combines only chunks within k. MRR uses the first rank at
  which a valid evidence path is fully covered.
- Per-item decisions are `matched`, `partial`, `retrieval_missed`, or
  `provenance_missing`. A missing/unavailable stage is represented separately;
  it must not be fabricated as an empty observed stage.
- A fully verified alternative path is sufficient. Missing unused alternatives
  or near-miss diagnostic evidence must not invalidate that path.
- Keep answer correctness, source-localization observability, required evidence
  recall, and answer grounding distinct in data and presentation.
- Do not inject Gold, answer-dependent search, or evaluator object IDs into
  the retrieval or generation content to make acceptance pass.

## Independent acceptance anchors to verify

These observations come from retained retrieval content and canonical source;
they guide independent verification but do not substitute for lineage proof.

- Access switch: table 10, row 2 columns 2 and 5, rank 2 in all stages.
- Conclusion validity: paragraph 16 has a full-text witness at rank 1 in all
  stages.
- Critical data count: table 17 is at rank 2. The duplicate table 39 at rank 1
  must not be silently substituted for table 17.
  Independent OOXML inspection distinguishes them: table 17 is body ordinal
  420 with paragraph IDs `58D48B54` through `46ACC323`; table 39 is body ordinal
  733 with IDs `1120CB7A` through `5C88F5AA`. Their retained native block ranges
  end at the respective paragraph IDs and have different block IDs. A recovery
  join can therefore use source paragraph lineage rather than guessing which
  identical grid was retrieved.
- Good vs excellent: the two criterion cells in table 27 are at rank 1.
  The earlier text-only witness for paragraph 41 at rank 5 is NOT the same
  source object: it is the matching description inside table 3. Fresh source
  lineage places Gold paragraph 41 at body ordinal 80, execution-stream
  offsets 6085..6261; rank 5 is chunk 005 at 1539..2179. Preserve the equivalent
  content as a diagnostic, but do not silently treat it as the Gold paragraph.
- Backed-up data: table 17 is at raw/ranked rank 12 and absent from context.
  The earlier paragraph-34 text witness at rank 14 is a different duplicate:
  paragraph 466 at body ordinal 547, offsets 26297..26391, in chunk 047.
  Gold paragraph 34 is body ordinal 73, offsets 3916..4010. Do not substitute
  the duplicate without an explicitly accepted alternative in the Gold data.
- Authentication confidentiality: table 17 is at raw/ranked rank 7. Table 39
  in final context is a distinct duplicate, not proof of the required identity.
- Server OS: alternative path A is table 12 at rank 3, path B table 34 at rank 5.
- HTTP: correct semantic content occurs in other tables, but this does not
  establish retrieval of Gold paragraph 52. Audit paragraph 52 and diagnostic
  paragraph 24 separately for partial/missed evidence. Never rewrite Gold to
  force a match in this historical evaluation.
  Independent retained-stream inspection places paragraph 52 at execution
  offsets 6579..6667 (6588..6676 with the 9-character `{{LRdoc}}` prefix),
  inside native chunk 008 (5513..7312); that chunk is absent
  from this case's raw 20. Chunk 009 starts at 7158 and does not overlap it.
  This is an expected true retrieval miss, subject to the reconstructed
  source-identity proof, not a target to turn green through semantic matching.

## Implementation review findings (not yet accepted)

- A read-only OOXML audit found that 80 of 83 native table sidecars point to
  parsed-block paragraph-ID ranges containing exactly one source direct table.
  This provides a structural historical join without comparing numeric ID
  suffixes. The remaining three share a block whose source tables are at body
  ordinals 677, 684, and 688 and require additional scoped identity witnesses.
- The native-render offset-transform draft expanded an endpoint inside an
  unchanged segment to the segment end. A direct function check demonstrated
  expected 20 versus actual 100 for segment (0,100)->(0,100). This must be
  repaired before any full-coverage claim is accepted.
  The revised functions were independently checked: interior endpoint 20 is
  preserved and out-of-bounds endpoint 101 returns no mapping. The selected
  existing writer/native-extract/IR-title/smart-heading tests now pass 91/91.
  This proves neither new lineage coverage nor the complete P0 runtime path;
  those acceptance gates remain open.
- The initial historical reconstruction draft treated every object in a block
  or table sidecar as fully covered by each related chunk. Sidecar membership
  proves a candidate scope, not actual coverage. It must intersect verified
  object ranges/row-cell extents with the chunk and fail closed on digest or
  content-witness mismatches.
- The initial table join by global native-ID sequence is not accepted.
  Recovery must use source structural scopes and explicit historical fallback
  witnesses where necessary. The whole-table object itself must be retained,
  not only its cells.
- The original 38-file preservation baseline was independently rechecked
  after the resumed audit: all file paths, sizes, and SHA256 values match.
- Historical block contents joined in original order with two newlines
  reproduce the retained runtime stream exactly: 113001 characters after
  removing the explicit `{{LRdoc}}` prefix from the full-document store.
  All 160 chunks with retained source spans match their stream slices exactly;
  the other 36 are split-table chunks requiring row/cell reconstruction.
- Evaluation needs a verified run-level object catalog and reverse chunk
  index to distinguish a real retrieval miss from missing attribution.
  The catalog must be loaded once and reused, not repeated as a large payload
  in every case or inferred from the absence of stage-local edges.
- A fresh real-DOCX extract -> IR -> sidecar audit exposed a tuple/dict
  mismatch in the writer's new span path that the 91 legacy tests missed.
  After its repair, independent re-execution produced 184 blocks with lineage,
  718 paragraph atoms, 83 table atoms, and 5134 physical-cell atoms. Every
  emitted span is in bounds, and all 5134 cell slices decode to their own
  recorded source values. The complete 113001-character retrieval stream is
  byte-for-byte/text-identical to the historical retained stream (after its
  explicit marker); the uploaded DOCX hash is unchanged.
  The temporary verification output is `/private/tmp/rag-eval-lineage-audit.1bCpRa`.
  This is parser/sidecar evidence only, NOT chunk, retrieval, or P0 acceptance.
  A historical-reparse recovery may use it only when regenerated lineage is
  explicitly versioned and original-source/full-stream equality is verified;
  it must not present regenerated metadata as an original run artifact.
- All 19 Gold objects have exactly one source-structural match in the newly
  emitted native lineage. A separate root-only diagnostic that intersects
  these object spans with the original chunk spans finds 43 matched and
  14 exact-Gold misses across the 57 item/stage cells. This is a cross-check
  expectation, not a completed persisted acceptance matrix or scoring gate.
  It supersedes earlier text-presence assumptions about paragraphs 34 and 41.
  Exact-Gold misses must not be conflated with absence of equivalent facts
  from another source position or with answer incorrectness.
- Selected paragraph-semantic merge/table-split/long-block and sidecar tests
  passed 101/101 (two existing dependency deprecation warnings), but a direct
  additional content-preservation probe found a regression: merging blocks
  `A1\nA2` and `B1\nB2` produced `A1\n\nA2\n\nB1\n\nB2` instead of
  `A1\nA2\n\nB1\nB2`. Restoring unchanged retrieval input is required.
  The P chunker's lineage consumer also needs to distinguish the writer's
  template-local `content_span` from final rendered `parsed_span`; using the
  former for table coverage would attribute only the placeholder width.
- The revised P-block merge was independently rechecked and now preserves
  `A1\nA2\n\nB1\nB2` exactly. This is a narrow content-preservation check,
  not complete chunking acceptance.
- The new final-chunk lineage bridge was exercised in memory with the prior
  fresh real sidecar and copies of all 196 original chunks. It emitted 148
  mapped, 12 partially mapped, and 36 unmapped chunks. All 2884 full-cell
  slices JSON-decode to their source values; original chunk contents were
  unchanged. The 36 spanless split-table chunks still need structural row/cell
  recovery. No result of this in-memory audit was written into the old run.
- A negative variant of original chunk 025 inserts one space into its JSON
  table opener but keeps the original source span. The current bridge wrongly
  reports it mapped while all 14 full-cell offsets are invalid. Normalized
  whitespace equality is insufficient when coordinates are not transformed.
- Another independent negative probe supplies a correct source hash and a
  correct returned-content hash, but falsely assigns an unrelated chunk to a
  Gold paragraph without a catalog edge. The current formal matcher returns
  `matched`. Exact object/extent association must be checked, not inferred
  from those independent hashes. Both failures were sent to their owning
  implementation agents and remain open until independently retested.
- The strict unbacked-locator negative probe was rerun after the matcher
  change: it now returns no exact match and `provenance_missing`. This closes
  that one probe only; catalog edge, source pin, whole-table completeness and
  coverage-union acceptance are still pending.
- The rewritten historical mapper was independently run in memory with
  `strict=True`, followed by its matrix builder. It produced 19 Gold rows and
  57 stage decisions: 43 matched, 14 retrieval misses, 0 partial and 0 unknown.
  Every observed Gold rank agrees with the earlier independent native-lineage
  oracle. The map itself reports 159 full, 36 partial and 1 missing runtime
  chunks, with 2 table-grid diagnostics still requiring review. Its recovery
  method label, malformed-span fallback, output-path boundary and shared
  evaluator transport were flagged for repair before publishing derivatives.
  Agreement of the 57 decisions is not an end-to-end P0/P1 acceptance claim.
- The existing evaluation/run-history/review baseline suite was rerun after
  these changes: 19 passed. Real lineage, negative cases, stage-isolation and
  renderer acceptance remain separate gates.
- Newly added chunk-lineage tests plus the P merge baseline independently
  passed 27 tests (two existing dependency warnings). An integration review
  immediately found another open gap: the pipeline obtains native parse output
  through `ParseResult.to_dict()`, whose current model does not carry the source
  byte SHA256. The new final-chunk bridge requires that pin, so passing a hash
  only in a unit fixture is insufficient. Native parse, persistence/reuse and
  pipeline hand-off must preserve it before formal runtime acceptance.

## Regression and release requirements

### Resumed integration audit (2026-09-05)

- The latest read-only audit was completed before the user explicitly resumed
  implementation. All three implementation agents were paused for that audit
  and are now resumed. Its live API check still returns the original 2/7
  answer projection and 19 evidence metrics with zero eligible samples.
- The persisted `historical-recovery-v2.4` map, matrix, Markdown matrix and
  production-localization audit all match their acceptance-manifest SHA256s.
  The original 38-file baseline also remains unchanged. The derivative records
  43 matched and 14 exact-Gold misses over 57 decisions; it is still explicitly
  UNVERIFIED and is not yet a versioned product rescore consumed by the API.
- Current next gates are: verify the real native parser/chunk/trace/adapter
  transport, publish independently checked per-case metric rescoring, and
  connect an explicit scoring version to the product reader. Offline matrix
  agreement alone does not satisfy those gates.
- A real-data performance profile identified a CPU bottleneck distinct from
  JSON loading: 2068 locator lookups scanned the 8308-object catalog repeatedly
  (about 17.2 million locator parsing calls). The 57-decision audit took about
  32 seconds without profiling. Pre-indexing object locators is assigned to
  the evidence owner; correctness and tamper-negative tests remain required.
- The preceding read-only investigation rechecked the actual original worker
  image, retained artifacts, live API and current presentation source. All 38
  immutable baseline inputs still match. The live API exposes 19 unavailable
  evidence metrics (each with zero eligible samples and 8 excluded cases),
  whereas all 19 Gold locators and preview records remain reachable.
- Implementation resumed using the existing Luna/max agents after account
  limits were independently observed to have reset. No usage-reset credit was
  redeemed. Original-run reconstruction remains separate from new-worker
  provenance and neither is accepted through presentation changes alone.
- The combined evidence-contract, historical-recovery, legacy evaluation,
  run-history and review tests independently returned 40 passed in 13.14s.
  This is a regression observation, not the real-data acceptance gate.
- A production-localizer integration using the reconstructed map, externally
  supplied map/source pins and the native runtime stream (without the
  `catalog_verified=True` bypass) produced 43 matched, 9 retrieval misses and
  5 provenance-missing decisions. The independent historical/source oracle
  expects the last five to be exact-Gold misses: backup paragraph 34 at raw
  and ranked rank 14 is actually duplicate paragraph 466, and Gold paragraph
  41 at rank 5 in all stages is actually text inside table 3. Verified
  attribution to a different object must neither become a Gold hit through
  text equality nor become unknown solely because the same text occurs there.
- The selected native-lineage, parser E2E, native golden and paragraph-merge
  suite returned 20 passed / 8 failed. Independent comparison of all eight
  golden outputs found unchanged body lines and unchanged legacy metadata;
  only `source_sha256` and `lineage_schema_version` were added to meta. Any
  fixture/contract update must explicitly assert these additions and retain
  existing content/assets equivalence. Blind golden regeneration is not an
  acceptance proof.
- `ParseResult.to_dict()` and native persistence now contain source SHA256
  propagation in the worktree, but parse/reuse/chunk/trace/runtime tests are
  still required before closing that finding. The adapter's non-empty-span
  trace condition and split-table coverage handling remain integration work.
- Executor integration is assigned to the evidence-scoring owner: after each
  repetition's ingestion, load and validate the run-level provenance map once,
  keep canonical source text distinct from native execution-stream offsets,
  and reuse the verified index across cases. Do not rely on an unconsumed
  ingestion digest or a corpus constructed before native parsing.

Include specific regressions for paragraphs, complete tables, cells, duplicate
tables, split tables, merged cells, partial unions, alternative paths, irrelevant
evidence, per-stage failures, trace-content tampering, source-digest mismatch,
missing lineage, and non-overwriting rescore persistence. UI-only success or unit
tests alone do not pass any end-to-end gate. Unknown claims remain UNVERIFIED;
genuine external prerequisites are recorded as BLOCKED with exact reasons.

The final decision must also verify that the actual worker runtime contains the
new implementation, rather than only verifying host source files.
