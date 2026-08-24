# Artifact Contract 1.2

Wire Protocol remains **1.0**. This contract hardens artifacts used to make a
controlled research claim.

The checked-in JSON Schemas for this contract live in `schemas/1.2/`; prior
schema directories remain immutable compatibility records.

## Model identity

`display_name` and `requested_ref` are descriptive only. A formal experiment
must reference a frozen `model-lock.json`, and every model in it must expose a
verified `resolved_digest` or immutable `revision`. A tag such as `latest` is
allowed only as the resolver input. Worker `prepare` resolves the model again;
the Platform fails before ingestion if its identity differs from the frozen
lock. A run with `verified=false` is Exploratory only.

## Comparison

`ComparisonSpec` declares every controlled factor and treatment factor. The
Platform evaluates compatibility per metric. A missing retrieval stage can
make a retrieval metric unavailable without turning answer accuracy into zero.
No generic winner is emitted; strict winner eligibility is attached to the
pre-registered primary metric only.

## Failure and latency

`FailureAssessment` is multi-label. It distinguishes retrieval missing,
ranking failure, context selection loss, generation failure, unsupported
answer, timeout, adapter error, and review-required states.

`end_to_end_query_latency` is measured by the Platform from `/query` dispatch
through response parsing and contract validation. Native, retrieval, and
generation timings are optional Adapter diagnostics. Cross-system latency is
only Task Comparable if the frozen latency protocol matches exactly.

## Formal-run minimum

The `ExperimentSpec` has `formal=true`, a model-lock digest, verified model
artifacts, and frozen Comparison / analysis / latency contract digests. The
RunManifest records namespace-specific scorers, model identities, code source
identities, index input fingerprints, index artifact digests, and status
coverage. Replay must reject identity drift unless explicitly run as an
Exploratory replay.
