"""Fail-closed replay identity comparison."""

from __future__ import annotations

from typing import Any

from rag_eval.contracts.run import RunManifest


def replay_mismatches(original: RunManifest, replayed: RunManifest) -> list[dict[str, Any]]:
    """Return machine-readable identity drift; no category silently falls back."""

    checks = {
        "bundle_id": (original.bundle_id, replayed.bundle_id),
        "case_selection_id": (original.case_selection_id, replayed.case_selection_id),
        "declared_config": (original.declared_config, replayed.declared_config),
        "effective_config": (original.effective_config, replayed.effective_config),
        "metric_scorers": (original.metric_scorers, replayed.metric_scorers),
        "model_artifacts": (
            model_identity_map(original),
            model_identity_map(replayed),
        ),
        "index_input_fingerprints": (
            original.index_fingerprints,
            replayed.index_fingerprints,
        ),
        "index_artifact_digests": (
            original.index_artifact_digests,
            replayed.index_artifact_digests,
        ),
        "source_identities": (
            original.reproducibility.source_identities if original.reproducibility else None,
            replayed.reproducibility.source_identities if replayed.reproducibility else None,
        ),
    }
    return [
        {"field": field, "expected": expected, "observed": observed}
        for field, (expected, observed) in checks.items()
        if expected != observed
    ]


def model_identity_map(manifest: RunManifest) -> dict[str, str | None]:
    return {
        name: artifact.identity
        for name, artifact in sorted(manifest.model_artifacts.items())
    }
