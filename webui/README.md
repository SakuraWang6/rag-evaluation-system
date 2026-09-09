# RAG Evaluation WebUI

This React application is the browser client for `rag_eval_platform`. It
creates DOCX-backed Benchmark workflows and renders persisted Artifact 2.0
results.

```bash
npm ci
npm run dev -- --host 127.0.0.1 --port 4178
```

The API root defaults to `http://127.0.0.1:8765/api/v1`; set it at build time
with `VITE_RAG_EVAL_API`.

## Product workflow

1. Upload an Original DOCX and complete Canonical target, question, answer and
   Gold review.
2. Seal an immutable Benchmark Release.
3. Add and test a LightRAG or RAG-Anything system.
4. Create an evaluation from the Release and a fully resolved system/query
   profile.
5. Inspect the Run, cases, evidence flow, metrics, failure attribution and
   integrity result.

The RAG owns native parsing, chunking, indexing and retrieval. The WebUI never
submits Platform-generated chunks as an evaluation corpus.

## Presentation boundary

Result components consume schema-`2.0` Artifact views. They distinguish an
observed numeric zero from `unavailable`, `not_applicable`, execution error,
observed-empty output and corrupted evidence. Stage status and completeness
are rendered independently.

The WebUI does not import RAG-specific logic, infer provenance, execute a
scorer, reconstruct failure attribution, or calculate leaderboard eligibility.
Missing Run IDs return the Platform's normal `404`; corrupted artifacts remain
diagnostic-only.

```bash
npm test
npm run build
```
