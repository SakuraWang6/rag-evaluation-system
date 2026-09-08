# Artifact 2.0 Platform API and WebUI

- Status: implemented as the Phase 7 result read path
- Input authority: immutable, verified Artifact 2.0 files
- Presentation contract: `run-artifact-*-view-v1`
- Legacy policy: persisted execution facts only; no request-time scoring

## Boundary

The normal result endpoints now read through `ArtifactPresentationReader`:

```text
artifact-v2/artifact.json
artifact-v2/summary.json
artifact-v2/case-index.json
artifact-v2/cases/*.json
              ↓ integrity + model validation
run-artifact-*-view-v1
              ↓ formatting only
WebUI
```

The reader imports no Adapter, provenance mapper, answer scorer, or evidence
scorer. It may verify hashes and validate persisted models. It never derives a
new evidence mapping, metric, judgment, or failure attribution.

The result endpoints are:

- `GET /api/v1/runs/{run_id}/summary`
- `GET /api/v1/runs/{run_id}/cases`
- `GET /api/v1/runs/{run_id}/cases/index`
- `GET /api/v1/runs/{run_id}/cases/{case_id}`
- `GET /api/v1/runs/{run_id}/artifacts/verify`

Comparison consumes the same persisted aggregate metrics. Artifact 2.0 metrics
are comparable only when their persisted descriptor digests agree.

The Phase 7 shadow test compares the API manifest, summary, and case payloads
with the same verified `ArtifactV2Reader` values. It also freezes the intentional
legacy difference: the former dynamic projection can produce a present-day
score, while the normal API now returns `legacy_unavailable` and no metrics.

## Availability states

`available` means Artifact 2.0 passed checksum, identity, model, summary, and
index verification. The API returns its persisted manifest, summary, cases,
and metric descriptors.

`legacy_unavailable` means the Run predates Artifact 2.0. The API may return
persisted question, execution status, and answer text for historical reading,
but v2 metrics, provenance, and failure attribution remain unavailable. The
current scorer is never used to fill missing fields.

`corrupted` means an Artifact 2.0 directory exists but failed verification.
Diagnostic verification details remain visible; its manifest, summary, and
case result are withheld from presentation and comparison.

## Descriptor-driven WebUI

The WebUI obtains core metric IDs from persisted
`leaderboard_eligibility.required_metric_ids`. It obtains stage, cutoff,
candidate window, ranked window, context budget, aggregation, and scorer
identity from each persisted `MetricDescriptor`; it does not infer semantics
from metric-name prefixes.

Stage cards render `observation_status` and `completeness` independently. In
particular, `observed + truncated + proven_prefix_depth` remains distinct from
`partial`, `unsupported`, `unobserved`, `failed`, and `corrupted`.

System-specific query controls are declared by immutable System Profiles as
`query_modes` and `query_timeout_min_seconds`. No result or configuration
component branches on a concrete RAG name or corpus mode.

## Compatibility and next boundary

Artifact 1.2 files and their internal readers are unchanged for offline
forensics. Their old dynamic product projection is no longer the normal API or
WebUI result authority.

Phase 8 now prevents new public pre-segmented Runs and makes Original DOCX the
only formal creation route. The legacy execution implementations remain in
their documented compatibility window; Artifact presentation remains
persisted-only for both old and new Runs.
