# RAG Evaluation Adapters

Each Adapter is an isolated implementation of the direct Worker 2.0 contract:

```text
prepare(original_docx, resolved_config) -> PreparedSystemV2
query(prepared_system, NativeQueryV2)    -> AdapterRunResultV2
```

The Platform never imports a RAG implementation. A Worker receives one
Original DOCX, a resolved secret-free configuration and native queries. It
does not receive Gold, scorer configuration or leaderboard policy.

## Contract responsibilities

An Adapter must:

- preserve the RAG's parser, chunker, index, retrieval, ranking, context and
  answer behavior;
- execute one native query for each Platform query;
- report runtime and observation profile identities during `prepare`;
- emit honest stage status and completeness in `UnifiedTrace`;
- content-pin catalog, stage, provenance and transformation records;
- fail closed on ambiguous mapping, identity drift or invalid receipts; and
- make unobservable evidence unavailable instead of fabricating an empty hit
  or miss.

Adapter implementations may use different runtime hooks. Their public output
must pass the shared observation TCK in
`rag_eval.adapters.observation_tck`. The same Unified Evaluation and Artifact
writer consume every conforming result.

## Implementations

- [LightRAG](lightrag/README.md)
- [RAG-Anything](rag-anything/README.md)

Each package has its own dependency environment. Cross-package contract tests
live under `tests/rag_eval_adapters/`; native implementation tests live beside
the corresponding Adapter.

Adding another RAG should change only its Adapter package, system profile,
Worker lifecycle configuration and TCK fixtures. It must not add a Dataset,
scorer, Artifact, API or WebUI branch.
