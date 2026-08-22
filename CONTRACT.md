# RAG Evaluation Contract 1.0

Contract 1.0 was frozen after the Fake, LightRAG, and RAG-Anything adapters
passed the same lifecycle and execution boundary. Public Pydantic models live
under `rag_eval.contracts`; machine-readable JSON Schema is exported with:

```bash
rag-eval export-schemas ./schemas
```

## Compatibility

- Wire requests and responses use `protocol_version = "1.0"`.
- Platform and Worker reject a different major or minor version before an
  operation is dispatched. There is no implicit 0.x compatibility path.
- Additive optional fields require a 1.x contract release. Removing a field,
  changing its meaning, changing `None` versus `[]`, or changing an endpoint
  requires Contract/Wire 2.0.
- Dataset and run artifacts remain `schema_version = 2`; their producer is
  `rag_eval_platform`. Artifact schema and Wire versions are independent.

`schemas/1.0/` is the frozen Adapter/Wire release. `schemas/1.1/` is an
additive artifact-contract release used by Phase 5: it adds repetition identity,
full reproducibility records, replay lineage, and artifact checksums without
changing Wire Protocol 1.0 or the Adapter lifecycle.

## Source-only document boundary

`DocumentInput` contains inline UTF-8 text when available and a checked,
relative `source_path` into the run's source-only sandbox. Binary documents use
the path without embedding base64 in HTTP. A SHA-256 digest binds the request to
the staged bytes. Binary Dataset Bundle documents must provide `canonical_path`
for deterministic evidence matching; neither Gold nor scorer data is staged in
the Worker sandbox.

## Error taxonomy

All operation errors use `{code, message, retryable}`. Stable protocol codes
are:

- `invalid_request` / `invalid_payload`
- `protocol_incompatible`
- `run_mismatch`
- `not_prepared`
- `capability_mismatch`
- `worker_closed`
- `adapter_error`

Only handshake and health may be retried automatically. Prepare, ingest, query,
reset, and close are never retried implicitly because they may have side
effects. Process crashes and transport timeouts remain execution failures in
case/run artifacts rather than disappearing from metric denominators.

## Observable stage semantics

- `None`: the adapter cannot observe the stage.
- `[]`: the stage was observed and returned no items.
- `raw_retrieval`: before filter, dedupe, ranking, top-k, or truncation.
- `ranked_retrieval`: after filter/dedupe/merge/ranking, before final selection.
- `final_context`: exact ordered content actually supplied to generation after
  token-budget selection.

An adapter must not reconstruct an unobservable stage using a second query or
private diagnostic metadata. Evaluation code never reads `native_metadata`.
