from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from rag_eval.reproducibility import capture_reproducibility
from rag_eval.worker.process import WorkerCommand


def test_full_reproducibility_snapshot_has_no_secret_values(tmp_path: Path) -> None:
    platform_src = Path(__file__).resolve().parents[2] / "src"
    command = WorkerCommand(
        adapter_id="fake",
        adapter_factory="rag_eval.adapters.fake:create_worker_definition",
        python_executable=sys.executable,
        environment={
            "PYTHONPATH": os.pathsep.join(
                [str(platform_src), os.environ.get("PYTHONPATH", "")]
            ),
            "LLM_MODEL": "controlled-model",
            "SECRET_TOKEN": "must-not-be-recorded",
        },
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    record = capture_reproducibility(
        command,
        run_dir,
        {
            "adapter": {
                "model_digests": {"llm": "sha256:model"},
                "prompt_digests": {"system": "sha256:prompt"},
            }
        },
    )

    assert len(record.dependency_lock_digest) == 64
    assert record.model_digests == {
        "adapter.model_digests.llm": "sha256:model"
    }
    assert record.prompt_digests == {
        "adapter.prompt_digests.system": "sha256:prompt"
    }
    environment = json.loads(
        (run_dir / record.environment_artifact).read_text(encoding="utf-8")
    )
    assert environment["worker_registration"]["environment_keys"] == [
        "LLM_MODEL",
        "PYTHONPATH",
        "SECRET_TOKEN",
    ]
    assert environment["worker_registration"]["safe_environment"] == {
        "LLM_MODEL": "controlled-model"
    }
    assert "must-not-be-recorded" not in json.dumps(environment)
