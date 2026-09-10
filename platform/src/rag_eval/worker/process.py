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
import time
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

    def start(self, *, readiness_timeout: float = 10.0) -> WorkerClient:
        with self._lock:
            if any(
                resource is not None
                for resource in (self.process, self.client, self._log_file)
            ):
                raise RuntimeError("worker process already owns resources")
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                self._log_file = self.log_path.open("a", encoding="utf-8")
                environment = os.environ.copy()
                environment.update(self.command.environment)
                executable_bin = str(Path(self.command.python_executable).parent)
                inherited_path = environment.get("PATH", "")
                environment["PATH"] = os.pathsep.join(
                    value for value in (executable_bin, inherited_path) if value
                )
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
                self.client.wait_until_ready(readiness_timeout)
            except BaseException:
                # A worker that never became ready must not receive a graceful
                # HTTP close: that request can wait for the full runtime
                # timeout. Terminate the isolated group first, then release
                # the local Client and log resources without masking the
                # startup error.
                self._cleanup(graceful=False, grace_seconds=3.0)
                raise
            return self.client

    def stop(self, *, grace_seconds: float = 3.0) -> None:
        with self._lock:
            self._cleanup(graceful=True, grace_seconds=grace_seconds)

    def cancel(self, *, grace_seconds: float = 3.0) -> bool:
        """Cancel immediately without waiting on an adapter `/close` request.

        A native parser may be serving a long-running ingest request. Calling
        `/close` in that state waits behind the parser and defeats cancellation,
        so cancellation terminates the isolated process group first.
        """

        with self._lock:
            return self._cleanup(graceful=False, grace_seconds=grace_seconds)

    def _cleanup(self, *, graceful: bool, grace_seconds: float) -> bool:
        """Release every owned resource exactly once, including partial starts."""

        process = self.process
        client = self.client
        log_file = self._log_file

        # Detach first so re-entrant or repeated cleanup cannot close the same
        # resource twice. Local references keep every cleanup action possible.
        self.process = None
        self.client = None
        self._log_file = None

        if graceful and process is not None and client is not None:
            try:
                client.close_adapter()
            except Exception as exc:  # noqa: BLE001
                logger.debug("best-effort worker adapter close failed: %s", exc)

        confirmed = True
        if process is not None:
            try:
                confirmed = terminate_process_group(
                    process.pid,
                    process=process,
                    grace_seconds=grace_seconds,
                )
            except Exception as exc:  # noqa: BLE001
                confirmed = False
                logger.warning("worker process cleanup failed: %s", exc)

        if client is not None:
            try:
                client.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("best-effort worker client close failed: %s", exc)

        if log_file is not None:
            try:
                log_file.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("worker log cleanup failed: %s", exc)
                confirmed = False
        return confirmed

    def __enter__(self) -> WorkerClient:
        return self.start()

    def __exit__(self, *_args: object) -> None:
        self.stop()


def reserve_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def terminate_process_group(
    process_group_id: int,
    *,
    process: subprocess.Popen[str] | None = None,
    grace_seconds: float = 3.0,
) -> bool:
    """Terminate and verify a worker tree, including detached parser groups.

    Some document parsers create their own process group below the Adapter
    Worker.  A signal sent only to the Worker's group does not reach those
    descendants, so snapshot the complete child tree before signalling it.
    """

    process_tree = snapshot_process_tree(process_group_id)
    target_groups = set(process_tree[1])
    target_groups.add(process_group_id)
    target_pids = set(process_tree[0])
    target_pids.add(process_group_id)

    signalled = signal_process_groups(target_groups, signal.SIGTERM)
    if not signalled:
        if process is not None:
            _reap_process(process)
        return True
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline and process_tree_has_live_members(
        target_pids, target_groups
    ):
        time.sleep(0.05)
    if process_tree_has_live_members(target_pids, target_groups):
        signal_process_groups(target_groups, signal.SIGKILL)
        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline and process_tree_has_live_members(
            target_pids, target_groups
        ):
            time.sleep(0.05)
    if process is not None:
        _reap_process(process)
    return not process_tree_has_live_members(target_pids, target_groups)


def snapshot_process_tree(root_pid: int) -> tuple[set[int], set[int]]:
    """Return live descendant PIDs and their process groups from one snapshot."""

    table = process_table()
    if table is None:
        return {root_pid}, {root_pid}
    descendants = {root_pid}
    while True:
        discovered = {
            pid
            for pid, (parent_pid, _pgid, _status) in table.items()
            if parent_pid in descendants
        }
        expanded = descendants | discovered
        if expanded == descendants:
            break
        descendants = expanded
    groups = {
        table[pid][1]
        for pid in descendants
        if pid in table and table[pid][1] > 0
    }
    return descendants, groups


def signal_process_groups(process_group_ids: set[int], sig: signal.Signals) -> bool:
    """Signal isolated groups child-first without touching our own group."""

    own_group = os.getpgrp()
    sent = False
    for group_id in sorted(process_group_ids, reverse=True):
        if group_id <= 0 or group_id == own_group:
            continue
        try:
            os.killpg(group_id, sig)
            sent = True
        except ProcessLookupError:
            continue
    return sent


def process_tree_has_live_members(
    process_ids: set[int], process_group_ids: set[int]
) -> bool:
    table = process_table()
    if table is None:
        return any(process_group_has_live_members(group) for group in process_group_ids)
    return any(
        (pid in process_ids or pgid in process_group_ids) and not status.startswith("Z")
        for pid, (_parent_pid, pgid, status) in table.items()
    )


def process_group_has_live_members(process_group_id: int) -> bool:
    """Treat reaped-or-waiting zombies as ended, not as live parser work."""

    table = process_table()
    if table is None:
        try:
            os.killpg(process_group_id, 0)
        except ProcessLookupError:
            return False
        return True
    return any(
        pgid == process_group_id and not status.startswith("Z")
        for _pid, (_parent_pid, pgid, status) in table.items()
    )


def process_table() -> dict[int, tuple[int, int, str]] | None:
    """Read the minimum process topology needed for bounded cancellation."""

    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,pgid=,stat="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    table: dict[int, tuple[int, int, str]] = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 4:
            continue
        try:
            pid, parent_pid, pgid = map(int, fields[:3])
        except ValueError:
            continue
        table[pid] = (parent_pid, pgid, fields[3])
    return table


def _reap_process(process: subprocess.Popen[str]) -> None:
    try:
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        pass
