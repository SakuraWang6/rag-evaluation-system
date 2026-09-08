# ADR 0002: Architecture Change Envelope

- Status: Accepted
- Date: 2026-09-08
- Scope: Evaluation System architecture changes after signal recovery

## Context

The next phase may reorganize Platform internals and the composition of the
evaluation workflow. Before that work begins, stable cross-component behavior
must be separated from implementation details that are safe to move. Without
that distinction, a directory or module refactor could accidentally change
evaluation semantics while still looking structurally successful.

## Stable boundaries

The following remain authoritative unless a separate versioned decision and
compatibility plan explicitly change them:

- Wire Protocol 1.0 and its lifecycle/error semantics.
- Artifact Contract 1.2, immutable run artifacts, and verification behavior.
- Gold/scorer data never enters a Worker source sandbox.
- Runtime evidence-item cardinality and rank are not expanded by canonical
  provenance mappings (ADR 0001).
- Observable stage meanings, `None` versus `[]`, and metric cutoff behavior.
- LightRAG and RAG-Anything remain independent Git/runtime owners behind the
  Worker process boundary.
- Platform, Adapters, and WebUI remain separately one Evaluation release unit with
  explicit package ownership.

## Changeable internals

The following may be reorganized behind characterization tests without a
contract version change:

- Platform router/module layout and dependency composition.
- Internal service orchestration and repository implementations.
- Adapter implementation helpers that leave Wire output unchanged.
- WebUI feature/component layout and local state organization.
- Build and test composition that preserves the required aggregate signal.

## Critical-path protection map

| Path | Executable authority |
| --- | --- |
| Authoring → formal release | `test_authoring_api_publishes_and_removes_formal_catalog_version_without_erasing_history` |
| Product draft → queued evaluation job | `test_wizard_draft_compiles_to_existing_experiment_and_job_store` |
| Runtime evidence → canonical Gold | ADR 0001's three required Adapter contract nodes |
| Supervisor process lifecycle | `test_supervisor_can_start_stop_and_start_again` and timeout single-writer test |
| Platform routes ↔ WebUI client | `contracts/webui-critical-api.json` tested from both packages |
| Run execution and artifact integrity | real fake-worker executor test plus `verify_artifacts` assertions |
| Third-party Worker boundary | required LightRAG and RAG-Anything model-free lifecycle jobs |
| CI policy implementation | `ci/tests` required job and aggregate `required / engineering-signals` |

This is a risk-weighted map, not a repository-wide coverage percentage. New
architecture work must add or strengthen characterization at the boundary it
changes before moving implementation.

## Change protocol

1. Name the stable boundary and its current executable test.
2. Add characterization if the boundary is not already observable.
3. Move one ownership surface at a time without changing public outputs.
4. Run the aggregate required gate and compare the exact Adapter/Platform
   baselines.
5. If semantics must change, stop the refactor and create a separate ADR,
   schema/version decision, and migration plan.

## Non-goals

This decision does not choose the future Platform module layout, redesign
provenance/lineage/SegmentTrace, alter metrics, or authorize new product
features. It defines the guardrails within which those later design decisions
can be evaluated.
