from __future__ import annotations

from rag_eval.replay import replay_mismatches

from .test_comparison import manifest


def test_replay_reports_model_and_index_drift() -> None:
    original = manifest("original")
    replayed = manifest(
        "replayed",
        index_fingerprints=["different"],
        model_artifacts={},
    )

    fields = {item["field"] for item in replay_mismatches(original, replayed)}

    assert "model_artifacts" in fields
    assert "index_input_fingerprints" in fields
