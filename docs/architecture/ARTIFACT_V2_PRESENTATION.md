# Artifact 2.0 API and WebUI Presentation

## Boundary

All result consumers use `ArtifactPresentationReader`:

```text
RunRecordV2 + ResolvedRunPlanV2 + Artifact 2.0
  -> integrity and plan-binding validation
  -> presentation schema 2.0
  -> API / report / comparison / review / WebUI
```

The reader imports no Adapter, provenance mapper or scorer. It may validate
persisted models and hashes, but cannot derive new evidence, metrics,
judgments, failure attribution or leaderboard status.

## Result endpoints

- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/summary`
- `GET /api/v1/runs/{run_id}/cases`
- `GET /api/v1/runs/{run_id}/cases/index`
- `GET /api/v1/runs/{run_id}/cases/{case_id}`
- `GET /api/v1/runs/{run_id}/report`
- `GET /api/v1/runs/{run_id}/artifacts/verify`

The `/api/v1` URI is stable, but the supported result payload is schema `2.0`
only. A missing Run ID returns `404`; there is no alternate-format response,
tombstone, redirect or dynamic conversion.

## Availability

`available` means the RunRecord, plan, Artifact checksum graph, models,
summary and case index all verify. Persisted result content may be returned.

`corrupted` means an expected Artifact is present but fails integrity or plan
binding. Verification details remain diagnostic; result content is withheld
from presentation and comparison.

An unavailable metric inside a valid Artifact retains a null value plus its
status and reason. It is never rendered as numeric zero.

## Reports, comparison and review

Reports are deterministic formatting of Artifact content. Comparison accepts a
metric only when persisted descriptors are identical. Review overlays bind the
target Artifact case digest so a review cannot silently attach to different
case bytes.

These consumers do not rescore or relocalize a Run. A code or model change
requires a new Run and Artifact.

## Descriptor-driven WebUI

The WebUI reads formal metric IDs from persisted leaderboard eligibility and
interprets stage, cutoff, candidate/ranked windows, context budget,
aggregation and scorer identity from `MetricDescriptor`.

Stage cards render `observation_status` and `completeness` independently.
`observed + truncated` stays distinct from `partial`, `unsupported`,
`unobserved`, `failed` and `corrupted`. UI components do not branch on RAG name
or an input-route label.
