# RAG Evaluation Platform

`rag_eval_platform` is the RAG-neutral owner of Benchmark authoring,
Canonical evidence, native-run admission, Unified Evaluation, immutable Run
artifacts, comparison, review overlays, reports and the Platform API.

## Supported runtime

Every new evaluation starts from one immutable Benchmark Release containing
one Original DOCX. Admission creates a content-addressed
`ResolvedRunPlanV2`; execution sends only the document, query and resolved
runtime configuration to an isolated Adapter Worker.

```text
Benchmark Release + Original DOCX
  -> ResolvedRunPlanV2
  -> Worker prepare / query
  -> validated UnifiedTrace
  -> Unified Evaluation
  -> verified Artifact 2.0
  -> RunRecordV2 completed
```

Gold never enters a Worker request. Adapter capabilities can make a metric
unavailable, but cannot change Gold eligibility or create another Benchmark.
`RunRecordV2` stores orchestration state only; all evaluation facts live in
Artifact 2.0.

Historical run formats, pre-segmented execution, replay/rescore and their
readers are not supported. `/api/v1` remains the URI prefix, while result
payloads use schema version `2.0` only.

The architecture contracts are indexed in
[`docs/architecture`](../docs/architecture/README.md). Benchmark construction
rules are in the [Benchmark Authoring Guide](docs/BENCHMARK_AUTHORING.md).

## Start locally

Install the Platform and WebUI dependencies, then run from this directory:

```bash
./scripts/start-local.sh
```

The default endpoints are:

- API: `http://127.0.0.1:8765/api/v1`
- WebUI: `http://127.0.0.1:4178`

Set `RAG_EVAL_HOME`, `RAG_EVAL_API_PORT`, `RAG_EVAL_WEBUI_PORT` or
`RAG_EVAL_WEBUI_DIR` when the defaults are unsuitable. Adapter Worker
configuration is trusted local service configuration and is not exposed as a
Basic-mode browser input.

The [Quick Start](docs/QUICK_START.md) covers the DOCX-to-result workflow.

## CLI

The CLI exposes the same native admission and Artifact authority as the API:

```bash
rag-eval --home /path/to/platform-home --help
rag-eval --home /path/to/platform-home verify-run RUN_ID
rag-eval --home /path/to/platform-home compare strict_controlled RUN_A RUN_B
rag-eval --home /path/to/platform-home export-schemas /path/to/schema-output
```

`create-experiment` and `run` reject an incomplete evaluation profile, an
unbound Benchmark Release, or any non-native execution declaration before a
Run is queued. `compare` accepts only metrics whose persisted descriptors are
identical.

## Storage and integrity

The default file store is rooted at `RAG_EVAL_HOME`. A successful Run contains
an immutable resolved plan, a strict `run-record.json`, and a verified
`artifact-v2/` tree. Artifact publication uses staging, checksum verification
and atomic rename before the Run may become `completed`.

Result reads, reports, comparison and review consume only persisted Artifact
2.0 data. They do not import a scorer, Adapter or provenance mapper.
