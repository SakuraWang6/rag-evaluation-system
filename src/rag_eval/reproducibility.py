"""Full replay metadata capture without importing any RAG implementation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError

from rag_eval.contracts.research import ModelArtifactIdentity, SourceIdentity
from rag_eval.contracts.run import ReproducibilityRecord
from rag_eval.storage.atomic import atomic_write_json
from rag_eval.worker.process import WorkerCommand

SAFE_ENVIRONMENT_KEYS = {
    "EMBEDDING_BINDING",
    "EMBEDDING_MODEL",
    "LLM_BINDING",
    "LLM_MODEL",
    "QUERY_LLM_BINDING",
    "QUERY_LLM_MODEL",
    "RAG_EVAL_SEED",
}


def capture_reproducibility(
    command: WorkerCommand,
    run_dir: Path,
    effective_config: dict[str, Any],
) -> ReproducibilityRecord:
    target = run_dir / "reproducibility"
    target.mkdir(parents=True, exist_ok=True)
    platform_snapshot = local_environment_snapshot()
    worker_snapshot = worker_environment_snapshot(command)
    environment = {
        "platform": platform_snapshot,
        "worker": worker_snapshot,
        "worker_registration": {
            "adapter_id": command.adapter_id,
            "python_executable": str(Path(command.python_executable).resolve()),
            "environment_keys": sorted(command.environment),
            "safe_environment": safe_environment(command.environment),
        },
    }
    dependency_lock = dependency_lock_text(platform_snapshot, worker_snapshot)
    dependency_path = target / "dependency-lock.txt"
    dependency_path.write_text(dependency_lock, encoding="utf-8")
    environment_path = target / "environment.json"
    atomic_write_json(environment_path, environment)
    git = git_identity(find_git_root(Path(__file__).resolve()))
    source_identities = find_source_identities(effective_config, git)
    return ReproducibilityRecord(
        platform_git_commit=git["commit"],
        platform_dirty=git["dirty"],
        dirty_patch_digest=git["dirty_patch_digest"],
        dependency_lock_digest=sha256_text(dependency_lock),
        environment_digest=sha256_bytes(environment_path.read_bytes()),
        model_digests=find_named_digests(effective_config, "model"),
        prompt_digests=find_named_digests(effective_config, "prompt"),
        model_artifacts=find_model_artifacts(effective_config),
        source_identities=source_identities,
        hardware_digest=sha256_text(
            json.dumps(hardware_identity(platform_snapshot), sort_keys=True)
        ),
        dependency_lock_artifact=dependency_path.relative_to(run_dir).as_posix(),
        environment_artifact=environment_path.relative_to(run_dir).as_posix(),
    )


def local_environment_snapshot() -> dict[str, Any]:
    return {
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "executable": str(Path(sys.executable).resolve()),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "distributions": installed_distributions(),
        "safe_environment": safe_environment(os.environ),
        "direct_urls": installed_direct_urls(),
    }


def worker_environment_snapshot(command: WorkerCommand) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update(command.environment)
    executable_bin = str(Path(command.python_executable).parent)
    environment["PATH"] = os.pathsep.join(
        value for value in (executable_bin, environment.get("PATH", "")) if value
    )
    result = subprocess.run(
        [command.python_executable, "-m", "rag_eval.reproducibility", "--snapshot"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "failed to capture worker environment: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("worker environment snapshot is malformed") from exc
    if not isinstance(payload, dict):
        raise TypeError("worker environment snapshot is not an object")
    return payload


def installed_distributions() -> list[str]:
    rows = {
        f"{distribution.metadata.get('Name', distribution.name)}=={distribution.version}"
        for distribution in importlib.metadata.distributions()
    }
    return sorted(rows, key=str.casefold)


def installed_direct_urls() -> dict[str, str]:
    """Return PEP 610 origins without reading or serialising secrets."""

    values: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        raw = distribution.read_text("direct_url.json")
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        url = payload.get("url")
        if isinstance(url, str) and url:
            name = distribution.metadata.get("Name", distribution.name)
            values[name] = safe_direct_url(url)
    return dict(sorted(values.items(), key=lambda item: item[0].casefold()))


def dependency_lock_text(
    platform_snapshot: dict[str, Any], worker_snapshot: dict[str, Any]
) -> str:
    lines = ["[platform]"]
    lines.extend(str(item) for item in platform_snapshot["distributions"])
    lines.append("")
    lines.append("[worker]")
    lines.extend(str(item) for item in worker_snapshot["distributions"])
    for name, url in worker_snapshot.get("direct_urls", {}).items():
        lines.append(f"direct-url {name} {url}")
    return "\n".join(lines) + "\n"


def safe_environment(values: os._Environ[str] | dict[str, str]) -> dict[str, str]:
    return {
        key: str(values[key])
        for key in sorted(SAFE_ENVIRONMENT_KEYS.intersection(values))
    }


def find_git_root(start: Path) -> Path | None:
    for path in (start, *start.parents):
        if (path / ".git").exists():
            return path
    return None


def git_identity(root: Path | None) -> dict[str, Any]:
    if root is None:
        return {"commit": None, "dirty": False, "dirty_patch_digest": None}
    commit = git_output(root, ["rev-parse", "HEAD"]).strip() or None
    status = git_output(root, ["status", "--porcelain=v1", "--untracked-files=all"])
    if not status:
        return {"commit": commit, "dirty": False, "dirty_patch_digest": None}
    patch = git_output(root, ["diff", "--binary", "HEAD", "--"])
    digest = sha256_text(status + "\0" + patch)
    return {"commit": commit, "dirty": True, "dirty_patch_digest": digest}


def git_output(root: Path, arguments: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout if result.returncode == 0 else ""


def find_named_digests(value: Any, category: str) -> dict[str, str]:
    results: dict[str, str] = {}

    def visit(item: Any, path: tuple[str, ...]) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                child_path = (*path, str(key))
                section = ".".join(child_path).lower()
                if (
                    isinstance(child, str)
                    and category in section
                    and "digest" in section
                ):
                    results[".".join(child_path)] = child
                else:
                    visit(child, child_path)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, (*path, str(index)))

    visit(value, ())
    return dict(sorted(results.items()))


def find_model_artifacts(value: Any) -> dict[str, ModelArtifactIdentity]:
    results: dict[str, ModelArtifactIdentity] = {}

    def visit(item: Any) -> None:
        if not isinstance(item, dict):
            return
        raw = item.get("model_artifacts")
        if isinstance(raw, dict):
            for name, identity in raw.items():
                try:
                    results[str(name)] = ModelArtifactIdentity.model_validate(identity)
                except (TypeError, ValidationError):
                    # Invalid adapter metadata must not be transformed into a
                    # plausible identity.  Worker validation rejects it for a
                    # formal run; the snapshot remains readable for diagnosis.
                    continue
        for child in item.values():
            if isinstance(child, dict):
                visit(child)

    visit(value)
    return dict(sorted(results.items()))


def find_source_identities(
    effective_config: dict[str, Any], platform_git: dict[str, Any]
) -> dict[str, SourceIdentity]:
    identities: dict[str, SourceIdentity] = {
        "platform": SourceIdentity(
            package_version=package_version("rag-eval-platform"),
            git_commit=platform_git["commit"],
            dirty_patch_digest=platform_git["dirty_patch_digest"],
        )
    }
    for section in _walk_dicts(effective_config):
        raw = section.get("code_identity")
        if not isinstance(raw, dict):
            continue
        for name, identity in raw.items():
            try:
                identities[str(name)] = SourceIdentity.model_validate(identity)
            except (TypeError, ValidationError):
                continue
    return dict(sorted(identities.items()))


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def hardware_identity(snapshot: dict[str, Any]) -> dict[str, str]:
    return {
        key: str(snapshot[key])
        for key in ("platform", "machine", "implementation")
        if key in snapshot
    }


def safe_direct_url(value: str) -> str:
    """Drop credentials and query fragments from a PEP 610 URL."""

    parsed = urlsplit(value)
    if not parsed.scheme:
        return value
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit((parsed.scheme, hostname + port, parsed.path, "", ""))


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args(argv)
    if not args.snapshot:
        parser.error("--snapshot is required")
    print(json.dumps(local_environment_snapshot(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
