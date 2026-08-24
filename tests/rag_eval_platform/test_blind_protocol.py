from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_eval.contracts.research import BlindProtocol
from rag_eval.datasets.blind import BlindProtocolError, validate_blind_layout


def protocol_payload(checksums: Path) -> dict[str, object]:
    start = datetime(2026, 8, 24, tzinfo=UTC)
    return {
        "sealed_at": start.isoformat(),
        "sealed_bundle_digest": "sha256:"
        + hashlib.sha256(checksums.read_bytes()).hexdigest(),
        "curator_id": "curator",
        "config_frozen_at": (start + timedelta(minutes=1)).isoformat(),
        "code_commit": "a" * 40,
        "model_lock_digest": "sha256:" + "b" * 64,
        "comparison_spec_digest": "sha256:" + "c" * 64,
        "analysis_contract_digest": "sha256:" + "d" * 64,
        "formal_runs_started_at": (start + timedelta(minutes=2)).isoformat(),
        "formal_runs_completed_at": (start + timedelta(minutes=3)).isoformat(),
        "gold_revealed_at": (start + timedelta(minutes=4)).isoformat(),
        "evaluator_id": "evaluator",
    }


def write_layout(root: Path) -> tuple[Path, Path]:
    public = root / "blind"
    sealed = root / "sealed"
    (public / "source_public").mkdir(parents=True)
    (public / "questions_public").mkdir()
    (public / "public_manifest.json").write_text("{}", encoding="utf-8")
    (sealed / "canonical").mkdir(parents=True)
    (sealed / "gold_answers.jsonl").write_text("{}\n", encoding="utf-8")
    (sealed / "gold_evidence.jsonl").write_text("{}\n", encoding="utf-8")
    checksums = sealed / "checksums.json"
    checksums.write_text('{"bundle_id":"test"}\n', encoding="utf-8")
    protocol = BlindProtocol.model_validate(protocol_payload(checksums))
    (sealed / "blind_protocol.json").write_text(
        protocol.model_dump_json(), encoding="utf-8"
    )
    return public, sealed


def test_blind_layout_requires_separation_and_a_valid_final_timeline(tmp_path: Path) -> None:
    public, sealed = write_layout(tmp_path)

    report = validate_blind_layout(public, sealed)

    assert report.protocol.curator_id == "curator"
    assert report.public_root == public.resolve()


def test_blind_layout_rejects_gold_leakage_in_the_public_tree(tmp_path: Path) -> None:
    public, sealed = write_layout(tmp_path)
    (public / "gold_evidence.jsonl").write_text("leak", encoding="utf-8")

    with pytest.raises(BlindProtocolError, match="Gold-named"):
        validate_blind_layout(public, sealed)


def test_blind_protocol_rejects_gold_reveal_before_completion(tmp_path: Path) -> None:
    _, sealed = write_layout(tmp_path)
    payload = protocol_payload(sealed / "checksums.json")
    payload["gold_revealed_at"] = payload["formal_runs_started_at"]

    with pytest.raises(ValidationError, match="blind timeline"):
        BlindProtocol.model_validate(payload)
