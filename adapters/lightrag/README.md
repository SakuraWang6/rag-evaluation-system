# LightRAG Evaluation Adapter

This package runs LightRAG behind the direct Worker 2.0 protocol. Register its
factory as:

```text
rag_eval_lightrag_adapter:create_worker_definition
```

`prepare` uploads the checksum-pinned Original DOCX to a run-scoped LightRAG
runtime, waits for native ingestion, validates the persisted chunk catalog and
returns `PreparedSystemV2`. `query` calls the native query path once and
returns `AdapterRunResultV2` with the answer and `UnifiedTrace`.

The Adapter observes exact native chunk IDs, rank, content, score, source
identity and lineage. It maps runtime content to the adjacent Canonical
Catalog by verified native lineage or deterministic structural crosswalk.
Duplicate witnesses, inconsistent spans, content drift and invalid receipts
fail closed. The Adapter never reads Gold or changes Gold eligibility.

The supported query mode is `naive`. Runtime profiles such as `legacy` and
`structured` are LightRAG configuration variants, not evaluation routes or
result formats. The observation profile declares candidate-to-ranked lineage
as `identity_subset` only when that relation can be proved; profiles with
injected or hidden candidates declare the transition `unobservable`.

One runtime chunk may prove several canonical objects, and several chunks may
union to cover one paragraph, logical cell or table. Physical cells and merge
topology remain proof material rather than separately ranked evidence.

See the [LightRAG observation proof boundary](../../docs/architecture/LIGHTRAG_NATIVE_OBSERVATION.md)
and the [shared Adapter contract](../README.md).
