# Native DOCX Compatibility Contract

> Historical scope: this contract governs pre-v2 authoring runs labeled
> `native-docx`. It does not govern the release-pinned `native-document/v2`
> formal route introduced by Phase 8. See
> `../../docs/architecture/NATIVE_FORMAL_CUTOVER.md` for current admission and
> eligibility rules.

## Scope

Native DOCX execution is a bounded parser-compatibility diagnostic. It is not
part of the `rag-benchmark-contract/1` Retrieval leaderboard and cannot
declare a cross-system winner.

The comparable path is always the frozen canonical leaf-segment corpus:

```text
Dataset Contract → canonical leaf segment_id → typed Adapter trace → strict Retrieval metrics
```

The native path is intentionally separate:

```text
Original DOCX → system parser → diagnostic parser/trace report
```

## Required native diagnostic record

Every native DOCX attempt must freeze all of the following in its Run
manifest/effective configuration:

- `execution_view: "native-docx"` and `diagnostic_only: true`;
- source DOCX checksum and parser/model identities;
- bounded parse/ingest/query timeout and terminal state;
- typed stage trace if the adapter can export it, otherwise explicit
  `unsupported_stage` rather than an empty trace or a zero Retrieval score;
- any parse errors, dropped object categories, and source-to-canonical mapping
  receipts as diagnostics.

The platform records new authoring native DOCX runs with this identity. The
comparison gate rejects them for `task_comparable` and `strict_controlled`
winner claims; exploratory inspection remains available with the diagnostic
reason shown.

## Acceptance rule

A native DOCX diagnostic is **PASS** only for its narrow parser objective when
it reaches a declared terminal state inside its budget and emits the promised
diagnostic/trace capability. It does **not** prove the system's strict
segment-native Recall, MRR, evidence coverage, or answer quality.

If native parsing times out, cannot map returned chunks deterministically, or
does not expose a trace, report `runtime_error`, `mapping_corrupted`, or
`unsupported_stage` respectively. Do not convert any of those states into a
zero score or `unverifiable` Retrieval result.

## Current P2 status

The gate and manifest identity are implemented and unit-tested. A new external
native parser run is intentionally not launched by P2: it remains blocked from
leaderboard admission until the RAG-Anything adapter can return auditable typed
segment traces and mapping receipts. This does not block the canonical
benchmark-contract/1 main chain.
