# WebUI Quick Start

This route does not require the CLI, an adapter factory, a Python path, or a
hand-authored `ExperimentSpec`.

## Start

From the Platform checkout, run `./scripts/start-local.sh`, then open
`http://127.0.0.1:4178`.

The local administrator starts Platform with the standard Adapter runtime
already selected (for example,
`RAG_EVAL_LIGHTRAG_WORKER_PYTHON=/path/to/worker-python`). This is a service
configuration, not a Basic user input: the WebUI neither shows nor stores the
Python path in its canonical ExperimentSpec.

## Complete the first run

1. On **Overview**, choose **Create from document** and upload the private
   DOCX. Inspect analysis and canonical evidence, discover targets, resolve
   candidates, and complete reviewer decisions before exporting/registering the
   approved canonical-text Bundle. The dataset page also accepts an existing
   Bundle ZIP or lets you create a small TXT/Markdown dataset by selecting the
   supporting source text and entering its question and answer.
2. Choose **Add RAG system**. In Basic mode select LightRAG or RAG-Anything,
   give it a friendly name, keep **Local process** selected, save, then choose
   **Test connection**. The Overview runtime check becomes ready only after a
   successful worker handshake.
3. Choose **New evaluation**. Select the Dataset and RAG system, then choose
   both a generation model and an embedding model. Query mode is optional.
   Review the fully expanded canonical configuration and choose **Confirm and
   run**. A missing model identity is rejected before a run can be queued.
4. Open **Runs** and select the run. Inspect integrity, metrics, Cases, and
   the question → retrieval → context → answer → evaluation evidence flow.

Basic mode uses immutable versioned SystemProfile defaults. Even values not
shown in Basic are fully expanded and frozen in the generated
`ExperimentSpec` before the existing RunExecutor starts.

## If something fails

- **Docker service is not running**: select Local process for the first run,
  or start Docker Desktop/OrbStack before testing the Docker connection.
- **Model runtime is unavailable**: start the configured local model service
  and make sure the selected model is installed, then test the system again.
- **RAG-Anything Docker is unavailable**: build the standard
  `rag-eval-adapter-rag-anything:0.1.0` image from the workspace root before
  testing the Docker system. Its image includes the MinerU runtime required by
  RAG-Anything's parser health check.
- **Dataset Bundle cannot be imported**: upload one ZIP containing a valid
  Bundle root and intact checksums. ZIP paths and symlinks that are unsafe are
  rejected.
- **Connection test fails**: use the technical details only for diagnosis;
  correct the local RAG runtime or adapter installation, then retest.

## Advanced

Local filesystem path registration is available through the CLI/CI workflow;
legacy/custom adapters, Replay, and hand-authored `ExperimentSpec` are also
Advanced workflows. They do not change the Dataset Bundle, Wire Protocol 1.0,
Artifact Contract 1.2, replay, metric, or comparison semantics.
