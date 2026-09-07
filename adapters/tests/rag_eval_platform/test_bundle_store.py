from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from rag_eval.contracts.adapter import AdapterCapabilities
from rag_eval.contracts.run import ExperimentSpec, RunManifest, RunStatus
from rag_eval.datasets.bundle import (
    BundleIntegrityError,
    DatasetBundleStore,
    case_selection_id,
)
from rag_eval.storage.runs import RunStore


def write_bundle(root: Path) -> None:
    document = root / "documents" / "doc-1.txt"
    document.parent.mkdir(parents=True)
    document.write_text("The controlled latency is 42 ms.", encoding="utf-8")
    digest = hashlib.sha256(document.read_bytes()).hexdigest()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "name": "controlled",
                "version": "1",
                "created_at": "2026-08-23T00:00:00Z",
                "documents": [
                    {
                        "document_id": "doc-1",
                        "path": "documents/doc-1.txt",
                        "sha256": digest,
                        "mime_type": "text/plain",
                        "metadata": {},
                    }
                ],
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    (root / "questions.jsonl").write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "question": "What is the controlled latency?",
                "gold_answer_id": "answer-1",
                "gold_evidence_set_id": "evidence-set-1",
                "tags": [],
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "gold_answers.jsonl").write_text(
        json.dumps(
            {
                "gold_answer_id": "answer-1",
                "kind": "numeric",
                "canonical": "42",
                "accepted_values": [],
                "unit": "ms",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "gold_evidence.jsonl").write_text(
        json.dumps(
            {
                "gold_evidence_set_id": "evidence-set-1",
                "evidence": [
                    {
                        "evidence_id": "evidence-1",
                        "document_id": "doc-1",
                        "locator": {
                            "type": "text_span",
                            "start": 0,
                            "end": 32,
                        },
                        "canonical_value": "42 ms",
                        "quote_anchor": "The controlled latency is 42 ms.",
                    }
                ],
                "required_groups": [["evidence-1"]],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_bundle_registration_is_content_addressed_and_immutable(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    write_bundle(source)
    store = DatasetBundleStore(tmp_path / "platform" / "datasets")
    bundle = store.register(source)

    assert len(bundle.bundle_id) == 64
    assert store.get(bundle.bundle_id).questions[0].case_id == "case-1"
    assert (store.root / bundle.bundle_id / "checksums.json").is_file()

    document = store.root / bundle.bundle_id / "documents" / "doc-1.txt"
    document.write_text("tampered", encoding="utf-8")
    with pytest.raises(BundleIntegrityError):
        store.get(bundle.bundle_id)


def test_case_selection_id_is_order_independent_but_seed_sensitive() -> None:
    first = case_selection_id(["b", "a"], policy="all", seed=1)
    assert first == case_selection_id(["a", "b"], policy="all", seed=1)
    assert first != case_selection_id(["a", "b"], policy="all", seed=2)


def test_binary_bundle_requires_and_uses_canonical_text(tmp_path: Path) -> None:
    source = tmp_path / "binary-bundle"
    source.mkdir()
    write_bundle(source)
    (source / "canonical").mkdir()
    pdf = source / "documents" / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 synthetic")
    canonical = source / "canonical" / "report.txt"
    canonical.write_text("The controlled latency is 42 ms.", encoding="utf-8")
    manifest = json.loads((source / "manifest.json").read_text())
    manifest["documents"][0].update(
        {
            "path": "documents/report.pdf",
            "canonical_path": "canonical/report.txt",
            "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "mime_type": "application/pdf",
        }
    )
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    store = DatasetBundleStore(tmp_path / "platform" / "datasets")

    bundle = store.register(source)

    assert bundle.source_documents()["doc-1"] == "The controlled latency is 42 ms."


def test_run_store_ignores_legacy_directories(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs")
    legacy = store.root / "legacy-run"
    legacy.mkdir()
    (legacy / "run.json").write_text(
        json.dumps({"schema": "legacy", "status": "complete"}), encoding="utf-8"
    )
    now = datetime.now(UTC)
    manifest = RunManifest(
        run_id="run-1",
        experiment_id="experiment-1",
        status=RunStatus.COMPLETED,
        bundle_id="bundle",
        case_selection_id="selection",
        platform_version="0.1.0",
        adapter_id="fake",
        adapter_version="0.1.0",
        system_id="fake-rag",
        system_version="1",
        declared_config={},
        effective_config={},
        scorer_id="deterministic-v1",
        scorer_version="1.0",
        scorer_digest="sha256:test",
        declared_capabilities=AdapterCapabilities(),
        observed_capabilities=AdapterCapabilities(),
        seed=0,
        repetitions=1,
        started_at=now,
        completed_at=now,
    )
    experiment = ExperimentSpec(
        experiment_id="experiment-1",
        bundle_id="bundle",
        system_id="fake-rag",
        adapter_id="fake",
        case_selection_id="selection",
    )
    store.create(manifest, experiment)

    assert [item.run_id for item in store.list()] == ["run-1"]
