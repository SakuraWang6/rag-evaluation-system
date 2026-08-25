# Productization Acceptance Report

Date: 2026-08-25  
Acceptance home: `/private/tmp/rag-eval-product-acceptance-20260825`

## Scope and contract boundary

This acceptance covers the Productization Track only. Dataset Bundle,
ExperimentSpec, Worker Protocol 1.0, Artifact Contract 1.2, scoring,
FailureAssessment, comparison, replay, and legacy CLI registration semantics
remain unchanged. Product Drafts compile to canonical ExperimentSpec and use
the existing RunExecutor.

## Accepted real-model evidence

| Provider | System | Run ID | Execution | Integrity |
| --- | --- | --- | --- | --- |
| LocalProcessProvider | RAG-Anything `1.0.1` text-safe Profile | `1afc6f0ebedc4ecaa1b2b2c4bcbe8d59` | 24 expected / 24 completed / 0 timeout / 0 system error | `verify-run` valid |
| DockerProvider | RAG-Anything `1.0.1` text-safe Profile | `3d412c44459445a5b5f41301a23173f9` | 24 expected / 24 completed / 0 timeout / 0 system error | `verify-run` valid |
| LocalProcessProvider | LightRAG historical Phase-8 evidence | `a22efd06eaeb441582838be81d38bc58` | 24 expected / 24 completed / 0 case error | `verify-run` valid |
| DockerProvider | LightRAG historical Phase-8 evidence | `8bdf9a72ba0e4ece9c3e55c8e5f81399` | 24 expected / 24 completed / 0 case error | `verify-run` valid |

For both accepted current RAG-Anything runs, all 24 `raw_retrieval` values
remain `null`; they are not converted to observed-empty `[]` or numeric zero.

The accepted Docker run records immutable image
`sha256:74f08a708b8fc4af1e8910575322f80b22a0bd9e6a13d5fcb4e32c9731df0971`.
Its checksummed execution sidecar records provider, image identity, resolver
strategy, logical endpoint reference, and endpoint identity digest only.

## Product configuration evidence

- `lightrag@1.0.1` is immutable and explicitly binds
  `qwen3:4b-instruct` and `bge-m3:latest`; historical `lightrag@1.0.0`
  remains readable but fails canonical generation when model identities are
  absent.
- `rag-anything@1.0.1` is immutable and text-safe: source-only text parsing,
  image/table/equation processing disabled, `candidate_k=3`, `context_k=1`.
  The historical multimedia-capable `1.0.0` is retained unchanged.
- Basic and Advanced inputs compile to the same fully expanded canonical Spec.
  Advanced parameters override only explicit fields and the preview is the
  exact Spec delivered to RunExecutor.
- New Product System connections use a 600-second request timeout. Existing
  connections and legacy SystemRegistration records retain their stored values.

## Docker isolation and lifecycle evidence

During the accepted Docker run, the fresh Worker container had only:

- `/rag-eval/source` mounted read-only;
- `/rag-eval/work` mounted read-write;
- read-only rootfs, no capabilities, and `no-new-privileges`;
- no Gold, scorer, or manifest mount.

After handshake, normal completion, and a separately exercised cancellation,
`docker ps -a --filter label=rag-eval.managed=true` was empty. The cancelled
RAG-Anything Local job was `694c8430ccfc413582a2dbc9354c483e`.

## Endpoint and credential boundary

- Persisted effective configuration replaces runtime `host` with a non-
  reversible endpoint digest.
- The accepted Local and Docker reproducibility snapshots contain no raw
  loopback/Docker endpoint value. Their safe environments contain only the
  seed.
- Product secret API tests cover save, rotate, remove, and response redaction.
  Rotation persists the new reference before deleting the superseded value;
  API list/save/remove responses expose keys and configured state only.
- The explicit development secret store encryption/`0600` behavior is covered
  by tests. The system Keychain is deliberately not exercised by automated
  acceptance because it requires an interactive local Keychain context.
- A live system-Keychain probe then completed `save → configured → rotate →
  remove` through the Product API. It used generated values, confirmed that
  neither save nor remove response returned a value, and left no probe key in
  the connection or API listing.

## Closed failures retained as evidence

| Run / issue | Cause | Resolution |
| --- | --- | --- |
| `cc3136f7e0b5474e8d2f64de66dec4f2` | text Bundle ran with multimedia defaults and was cancelled in ingest | added immutable text-safe `rag-anything@1.0.1` |
| `e76c576510ba4e8e8bcfefeafb9617c9` | Docker image lacked MinerU | image now installs pinned MinerU runtime |
| `29b4c6e9d1c140ba8bed7cd3f91341f7` | Docker fresh index exceeded 180-second product default; old external worker snapshot exposed endpoint | new Product default is 600 seconds; current worker venv uses current Platform package and accepted run is redacted |
| LightRAG Adapter integration failures | tests launched a Worker using Platform Python without LightRAG core | integration tests now require the dedicated LightRAG Worker venv |

These runs are not accepted success evidence and are intentionally retained in
the acceptance home for auditability.

## Regression evidence

| Check | Result |
| --- | --- |
| Platform test suite | `75 passed, 2 skipped` |
| Adapter test suite with dedicated real Worker venvs | `30 passed` |
| WebUI Vitest | `5 passed` |
| WebUI TypeScript + production build | passed |
| Project Markdown dead-link check | no missing project-local links |
| Product Layer disabled / legacy compatibility | covered by Platform regression tests |

## Remaining manual acceptance boundary

The in-app browser automation policy blocked reloading the already-open local
WebUI after its API target was changed from the historical `8765` instance to
the acceptance `8766` instance. It must not be bypassed by another browser
surface. Therefore the following is intentionally **not** claimed as complete
in this report:

1. a brand-new `RAG_EVAL_HOME` browser-only walkthrough of Overview → ZIP
   upload → System test → Basic Wizard → Local run → Docker run → Compare;
2. visual 390px/desktop and zh-CN/en-US walkthrough on the final running
   frontend.

All API, canonical-generation, real-model, artifact, Docker lifecycle, and
frontend build/test gates above have passed. Complete these two interactive
checks before declaring the full **PRODUCTIZATION GATE: PASS**.
