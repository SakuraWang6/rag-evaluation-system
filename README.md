# RAG Evaluation Platform

`rag_eval_platform` is a system-neutral evaluation service. It owns dataset
bundles, evaluation semantics, immutable run artifacts, job state, comparison,
and reports. It deliberately has no dependency on LightRAG or RAG-Anything.

RAG systems run behind isolated adapter workers. The platform communicates
with workers through frozen Wire Protocol 1.0 over authenticated loopback HTTP/JSON.

The initial storage backend is an atomic file store rooted at
`RAG_EVAL_HOME` (default: `~/.rag_eval_platform`). Legacy LightRAG evaluation
directories are never scanned.
