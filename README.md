# RAG Evaluation Web UI

Standalone React UI for `rag_eval_platform`. It reads only schema-v2 runs
produced by `rag_eval_platform`; legacy LightRAG evaluation directories are
never discovered or compared.

```bash
npm ci
npm run dev -- --host 127.0.0.1 --port 4178
```

The API root defaults to `http://127.0.0.1:8765/api/v1` and can be changed at
build time with `VITE_RAG_EVAL_API`. LightRAG's WebUI links here through
`VITE_RAG_EVAL_UI_URL` but does not embed this application.

The interface deliberately distinguishes `unavailable`, `not_applicable`,
`error`, observed-empty output, and an observed numeric zero. Retrieval metrics
always name their stage. V1 exposes deterministic groundedness and unsupported
answer rate; it does not expose a hallucination-rate label.
