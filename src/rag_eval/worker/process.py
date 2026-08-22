"""Lifecycle management for one isolated adapter worker process."""

from __future__ import annotations

import logging
import os
import secrets
import signal
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from rag_eval.worker.client import WorkerClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WorkerCommand:
    adapter_id: str
    adapter_factory: str
    python_executable: str = sys.executable
    environment: dict[str, str] = field(default_factory=dict)
    request_timeout_seconds: float = 180.0


class WorkerProcess:
    def __init__(
        self,
        command: WorkerCommand,
        *,
        run_id: str,
        log_path: Path,
    ) -> None:
        self.command = command
        self.run_id = run_id
        self.log_path = log_path
        self.token = secrets.token_urlsafe(32)
        self.port = reserve_loopback_port()
        self.process: subprocess.Popen[str] | None = None
        self.client: WorkerClient | None = None
        self._log_file: TextIO | None = None
        self._lock = threading.RLock()

    def start(self, *, handshake_timeout: float = 10.0) -> WorkerClient:
        with self._lock:
            if self.process is not None:
                raise RuntimeError("worker process already started")
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = self.log_path.open("a", encoding="utf-8")
            environment = os.environ.copy()
            environment.update(self.command.environment)
            environment["RAG_EVAL_WORKER_TOKEN"] = self.token
            argv = [
                self.command.python_executable,
                "-m",
                "rag_eval.worker.main",
                "--adapter-factory",
                self.command.adapter_factory,
                "--run-id",
                self.run_id,
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
            ]
            self.process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
                env=environment,
                text=True,
                start_new_session=True,
            )
            self.client = WorkerClient(
                f"http://127.0.0.1:{self.port}",
                token=self.token,
                run_id=self.run_id,
                timeout=self.command.request_timeout_seconds,
            )
            try:
                self.client.wait_for_handshake(handshake_timeout)
            except Exception:
                self.stop()
                raise
            return self.client

    def stop(self, *, grace_seconds: float = 3.0) -> None:
        with self._lock:
            process = self.process
            if process is None:
                return
            if self.client is not None:
                try:
                    self.client.close_adapter()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("best-effort worker close failed: %s", exc)
                self.client.close()
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=grace_seconds)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    if process.poll() is None:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait(timeout=grace_seconds)
            if self._log_file is not None:
                self._log_file.close()
            self.process = None
            self.client = None
            self._log_file = None

    def __enter__(self) -> WorkerClient:
        return self.start()

    def __exit__(self, *_args: object) -> None:
        self.stop()


def reserve_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
