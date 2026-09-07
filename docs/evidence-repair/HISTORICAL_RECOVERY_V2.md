# Historical recovery v2

This derivative is a read-only reconstruction of run
`2ad4ecfc4c9d4d3ba30baf0ad9f276b3`.  The authoritative generated bundle is
`historical-recovery-v2.4/` at the `v2.4` filenames; `v2.3` and `v2.2` are
immutable prior snapshots.  The earlier `historical-recovery-v2/` and
unqualified `v2` filenames are superseded pre-transport-shape probes.

Run it from the repository root:

```bash
rag-eval-platform/.venv/bin/python \
  rag-eval-platform/scripts/reconstruct_historical_provenance.py \
  --run-dir /Users/sakura/RAG/.rag-eval-real-benchmark-pilot/runs/2ad4ecfc4c9d4d3ba30baf0ad9f276b3 \
  --output-dir /Users/sakura/RAG/rag-eval-platform/docs/evidence-repair/historical-recovery-v2.4 \
  --map-name historical-provenance-v2.4.json \
  --matrix-name historical-localization-matrix-v2.4.json \
  --markdown-name historical-localization-matrix-v2.4.md \
  --acceptance-name historical-recovery-v2.4-acceptance.json \
  --production-audit-name production-localization-audit-v2.4.json \
  --baseline /Users/sakura/RAG/rag-eval-platform/docs/evidence-repair/original-run-baseline.json \
  --strict
```

The output is intentionally append-only and reports `UNVERIFIED` until the
coordinating acceptance review completes.  Use a fresh versioned output
directory (or fresh filenames) for every rerun; the writer refuses to
overwrite an existing derivative or anything inside the source run.  It
contains:

* `historical-provenance-v2.4.json`: one run-level object catalog and reverse
  index.  `documents` and `runtime_chunks` are dictionaries so the scorer can
  load the catalog once.  Each runtime record exposes both
  `canonical_objects` and `edges`; each object records `expected_extent`,
  actual covered ranges, typed locator, stable ID, source coordinates, and
  witness/alignment method.
* `historical-localization-matrix-v2.4.json` and `.md`: 19 exact Gold objects ×
  raw/ranked/context = 57 decisions.  The persisted result is 43 `matched`,
  14 exact-Gold `retrieval_missed`, 0 `partial`, and 0
  `provenance_missing`.  Equivalent text in a duplicate paragraph/table is
  retained only as a diagnostic and is not substituted for the Gold object.
* `production-localization-audit-v2.4.json`: the same 57 decisions through the
  production `CorpusEvidenceIndex.from_provenance_map` and `localize_stage`
  path. It omits `catalog_verified`; the bridge earns `catalog_verified` and
  `map_digest_verified` from the pinned map/source/runtime inputs. Current
  audit counts are 43 `matched`, 14 `retrieval_missed`, 0 other statuses, with
  0 differences from the exact-object matrix.
* `historical-recovery-v2.4-acceptance.json`: source/parsed/canonical hashes,
  original map hash, baseline verification, hashes for the matrix/audit
  artifacts, and hashes for the reconstruction, evidence, metrics, and engine
  source files used to derive them.

The source mapper reads only the source DOCX, canonical JSONL, parsed block
sidecar, retained full-doc store, and retained chunk store.  Gold cases are
opened only in the second matrix pass.  For 160 chunks the retained
`source_span` is checked byte-for-byte against the exact merged execution
stream.  The 36 spanless chunks use their native table sidecar plus a unique
scoped grid witness and report row/cell coverage; they do not receive a
whole-block `full` claim.  An explicit invalid source span fails closed and
cannot fall through to the table-fragment path.

The shared scorer bridge can pin `map_digest` (also emitted as
`canonical_provenance_map_digest`) and supply `source_digests` plus
`runtime_documents`.  The production audit compares status, rank, runtime
chunk IDs, and typed locator for every one of the 57 decisions.  The v2.4
bundle is the pinned locator/rescore input; worker/container rescore and final
acceptance remain `UNVERIFIED`.

## Versioned production re-score

The independent production re-score is in
`historical-rescore-v1.1/` (`historical-rescore-v1/` is an immutable prior
snapshot).  It loads the v2.4 map once, verifies the external
map acceptance pin and source digest, then passes the eight retained
`rag_result` artifacts through production `evaluate_case`.  It does not start
retrieval, generate an answer, call an LLM, or rerun LightRAG.  The JSON keeps
each case's original and new metric records, changed fields, explanation,
Gold-stage localization, input hashes, scorer/source hashes, and the original
38-file baseline verification.  The Markdown is the reviewer-oriented view.

Run a future version into a new directory (never overwrite v2.4 or v1):

```bash
rag-eval-platform/.venv/bin/python \
  rag-eval-platform/scripts/rescore_historical_run.py \
  --run-dir /Users/sakura/RAG/.rag-eval-real-benchmark-pilot/runs/2ad4ecfc4c9d4d3ba30baf0ad9f276b3 \
  --map /Users/sakura/RAG/rag-eval-platform/docs/evidence-repair/historical-recovery-v2.4/historical-provenance-v2.4.json \
  --map-acceptance /Users/sakura/RAG/rag-eval-platform/docs/evidence-repair/historical-recovery-v2.4/historical-recovery-v2.4-acceptance.json \
  --matrix /Users/sakura/RAG/rag-eval-platform/docs/evidence-repair/historical-recovery-v2.4/historical-localization-matrix-v2.4.json \
  --baseline /Users/sakura/RAG/rag-eval-platform/docs/evidence-repair/original-run-baseline.json \
  --output-dir /Users/sakura/RAG/rag-eval-platform/docs/evidence-repair/historical-rescore-vN
```

The v1.1 snapshot is `UNVERIFIED` pending root/runtime review.  Its production
summary is `answer_accuracy=2/7`, `answer_groundedness=4/8`,
`raw_recall@3=7/12`, and `context_recall@3=7/12`; these are selected-path
production metrics, not a 19 × 3 localization-matrix recall denominator.
