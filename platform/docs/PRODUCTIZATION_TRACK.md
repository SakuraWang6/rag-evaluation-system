# Productization Track

This track is independent of the research `Phase` sequence. It provides a
WebUI-first path without changing Artifact Contract 1.2, Worker Protocol 1.0,
Bundle integrity, metric semantics, replay, or comparison rules.

## Product flow

```text
Basic / Advanced → EvaluationDraft → canonical ExperimentSpec → RunExecutor
                 → ExecutionProvider → authenticated Adapter Worker → RAG
```

`EvaluationDraft`, System Connections, temporary manual-text staging records,
and development secret storage live under `RAG_EVAL_HOME/product/`. They are
product state, not Run Artifacts. The WebUI uses the manual-text staging record
only to create one sealed dataset; it does not expose a separate draft list or
draft editor. A generated `ExperimentSpec` expands every versioned profile
default before a run is queued.

## Basic and Advanced

Basic exposes only LightRAG and RAG-Anything, Dataset/System/Model/Embedding/
Query Mode, and Local or Docker execution. The profile owns versioned defaults
such as `candidate_k=20` and `context_k=5`; they are shown in the canonical
Spec preview and never looked up again at run time.

Advanced contains legacy/custom adapter registration through the existing CLI,
runtime/factory/environment settings, formal artifacts, and direct
ExperimentSpec authoring. Local-path Bundle registration remains a CLI/CI
operation rather than a browser action. Custom RAG is not a Basic option.

## Dataset lifecycle

The primary lifecycle is **Private DOCX → Authoring → reviewer-approved
Dataset → RAG Evaluation**. The Authoring workspace is the only current
product path for private documents. `memory_data_service` and synthetic
generation are legacy/diagnostic assets outside this flow; they are not
invoked by the Platform.

- **Upload Bundle** accepts one Bundle ZIP over the browser API. Platform
  rejects unsafe ZIP paths and validates it in a staging directory before
  copying it into the immutable Bundle Store.
- **Create from Document** accepts a private DOCX and runs the Authoring flow:
  deterministic canonicalization, structure-first targets, separate
  question/answer/evidence resolution, validation gates, reviewer decisions,
  and export/register of an immutable Bundle ID.
- **Create Dataset** supports UTF-8 TXT/Markdown as a small manual flow:
  select source text, enter one Question and Gold Answer, then create the
  sealed dataset. It is not the private-document Authoring mainline.

Gold generation, automatic amendment, PDF, OCR, and non-DOCX Office-document
import are not part of this track. Native-DOCX execution is diagnostic only;
the normal evaluation view is canonical-text.

## Credentials and endpoints

System Connections persist only secret references. The default
`KeychainSecretStore` requires a secure system Keychain. It never silently
falls back. For explicit development-only use, set both:

```bash
RAG_EVAL_ENABLE_ENCRYPTED_DEV_SECRET_STORE=1
RAG_EVAL_SECRET_STORE_KEY='<base64-encoded 32-byte key>'
```

This enables `EncryptedDevFileSecretStore`, an AES-GCM `0600` file. The key is
never written to that file. Values never appear in API reads, logs,
ExperimentSpec, Run Manifest, or reproducibility snapshots.

Saving a new value for an existing credential key rotates its local secret
reference and removes the superseded value only after the connection is saved.
The incremental delete endpoint removes a configured key and its referenced
value; list/save/remove responses expose keys and configured state only.

Model service endpoints use three layers: a stored logical reference (for
example `ollama.local`), Provider resolution, then an effective runtime
endpoint injected only while the Worker starts. `host.docker.internal` is a
DockerProvider detail and is never written into a canonical ExperimentSpec.

## Execution providers

`LocalProcessProvider` is the default and preserves the existing fresh Worker
per repetition behavior. `DockerProvider` uses the same Wire Protocol and each
repetition receives a fresh container and work index. It mounts only the
source-only dataset read-only; Gold/scorers never enter the container. Docker
uses a loopback-only port, short-lived Worker token, non-root user, dropped
capabilities, read-only root filesystem, temporary `/tmp`, and explicit cleanup.

Build standard images from the workspace root:

```bash
docker build -f evaluation-system/adapters/lightrag/Dockerfile \
  -t rag-eval-adapter-lightrag:0.1.0 .
docker build -f evaluation-system/adapters/rag-anything/Dockerfile \
  -t rag-eval-adapter-rag-anything:0.1.0 .
```

The RAG-Anything image includes the MinerU CLI and the minimal native OpenCV
libraries needed by its runtime health check; a Worker handshake alone is not
considered a successful evaluation.

The provider records image identity and an endpoint identity digest in the
checksummed `execution-environment.json` sidecar, never raw private endpoint
values or secrets.

## Compatibility gate

Set `RAG_EVAL_PRODUCT_LAYER_ENABLED=0` to disable product endpoints and the
product UI entrypoints. Existing CLI commands, SystemRegistration records,
ExperimentSpec files, schema-v2 artifacts, checksum verification, and replay
continue unchanged. This mode is part of the Product Track regression suite.
