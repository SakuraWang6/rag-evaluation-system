from __future__ import annotations

import json
import sys

from rag_eval.cli import main


def test_register_system_preserves_virtual_environment_interpreter_symlink(
    tmp_path,
) -> None:
    worker_python = tmp_path / "worker-venv" / "bin" / "python"
    worker_python.parent.mkdir(parents=True)
    worker_python.symlink_to(sys.executable)

    assert main(
        [
            "--home",
            str(tmp_path / "home"),
            "register-system",
            "symlinked-worker",
            "fake",
            "rag_eval.adapters.fake:create_worker_definition",
            "--python",
            str(worker_python),
        ]
    ) == 0

    registration = json.loads(
        (tmp_path / "home" / "systems" / "symlinked-worker.json").read_text()
    )
    assert registration["python_executable"] == str(worker_python.absolute())
