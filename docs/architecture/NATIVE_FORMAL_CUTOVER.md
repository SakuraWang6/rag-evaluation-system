# Native Formal Run Cutover

- Status: implemented as the Phase 8 public creation boundary
- Formal execution contract: `native-document/v2`
- Public input authority: immutable Benchmark Release
- RAG ingestion input: exactly one release-pinned Original DOCX

## Normal creation path

```text
Benchmark Release
  -> System Profile + query/runtime overrides
  -> NativeEvaluationDraftRequest
  -> content-addressed runtime projection
  -> public Run admission
  -> ExperimentSpec
  -> queued native-document/v2 Run
```

`NativeEvaluationDraftRequest` intentionally has no `bundle_id`, `formal`, or
corpus-mode field. The selected Release supplies the immutable source,
Canonical Catalog, Questions, Gold Answers, and Gold Evidence. System Profile
and explicit query/runtime settings supply the system configuration.

The runtime projection contains the pinned DOCX plus an adjacent Canonical
Catalog. `source_only_documents()` submits one DOCX `DocumentInput` to the
Adapter. The Canonical Catalog is an out-of-band observer input used to prove
runtime-to-canonical provenance; it is not submitted to the RAG as replacement
content.

## Admission ownership

`rag_eval.runtime_admission` is the sole policy boundary for new public
Experiment creation and queueing. It rejects:

- caller-supplied `evaluation_corpus` configuration, including an explicit
  native value;
- a pre-segmented Benchmark Contract;
- Bundle metadata selecting a pre-segmented corpus;
- a Bundle whose content-addressed identity differs from the deterministic
  runtime projection rebuilt from the selected immutable Release;
- release-bound inputs that are not a verified `native-document/v2`
  projection;
- formal inputs that are not exactly one pinned DOCX.

Before applying the policy, the Platform composition root deterministically
materializes the selected immutable Release and supplies its content-addressed
runtime `bundle_id`. Admission requires an exact ID match, so changing the
DOCX, Canonical Catalog, Questions, Gold Answers, Gold Evidence, or projection
metadata cannot inherit the Release pin.

The product System and Evaluation Draft write contracts reject corpus
selectors before persistence. The lower-level public Experiment and queue APIs
apply the same admission policy. CLI create/run commands apply it as well.

This policy does not inspect Adapter names or capabilities and does not inspect
or filter Gold. Canonical Conformance remains the only Gold Eligibility owner.

## Compatibility window

Phase 8 closes new public creation; it does not delete historical machinery:

- persisted ExperimentSpecs and Run Artifacts remain readable;
- Artifact 1.2 and Artifact 2.0 readers are unchanged;
- canonical-segment and benchmark-segment materializers remain available to
  direct characterization tests and migration shadow comparisons;
- the Executor and Adapters retain their legacy branches for the compatibility
  window;
- already queued work can still be recovered by the Supervisor;
- a separately initiated historical replay remains explicit provenance work,
  rather than a new normal evaluation.

Removing the legacy live branches is a later retirement change after a stable
compatibility version. It is not part of this cutover commit.

## Eligibility

`native-document/v2` is no longer disqualified by a legacy
`diagnostic_only`/`native-docx` label when a verified Artifact 2.0 summary is
the authority. Artifact 2.0 leaderboard eligibility continues to be derived
only from persisted availability and descriptor consistency for every formal
core metric across every Case. Adapter identity, system identity, execution
view, and global stage completeness are not eligibility inputs.

Legacy artifacts without Artifact 2.0 retain their historical diagnostic
comparison restriction.

## Validation and rollback

The Phase 8 suite proves:

- a release preview and finalization carry no public corpus selector;
- the runtime projection and actual `DocumentInput` contain the original DOCX
  as the only ingestion item;
- public product, Experiment, queue, and CLI boundaries cannot create a new
  pre-segmented Run;
- a caller cannot pair a Release ID with a modified DOCX, Catalog, Questions,
  Answers, or Gold because any such change produces the wrong runtime Bundle
  identity;
- native/pre-segmented shadow comparison proves the Benchmark is unchanged and
  records an expected legacy admission failure when that oracle cannot
  represent an otherwise Canonical-conformant Gold subtype;
- legacy pre-segmented materializers and characterization tests still run;
- Artifact 2.0 comparison does not apply legacy route-label disqualification;
- the WebUI has no raw Experiment editor/queue path and selects only runnable
  Benchmark Releases.

Rollback is one revert of the Phase 8 commit. Because historical artifacts and
legacy execution implementations are not rewritten or deleted, rollback does
not require artifact migration.
