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

## Product workflow

With Product Layer enabled (the default), use **Overview → New Evaluation**:

1. Upload a validated Dataset Bundle ZIP, or create a TXT/Markdown draft with
   a manually selected Gold TextSpan and seal it.
2. Add a standard LightRAG or RAG-Anything system and test its Worker handshake.
3. Select Dataset, System, Model, Embedding, and Query Mode.
4. Review the fully expanded canonical ExperimentSpec, then queue the run.

Basic mode does not expose adapter factories, Python paths, environment files,
or Worker lifecycle. Advanced retains ExperimentSpec and legacy/custom-adapter
workflows. All visible product text is supplied by the shared zh-CN/en-US i18n
layer.
