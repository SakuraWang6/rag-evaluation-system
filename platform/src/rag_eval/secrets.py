"""Local secret references. Values never become product or run artifacts."""

from __future__ import annotations

import base64
import json
import os
import secrets
import stat
from pathlib import Path
from typing import Protocol

SAFE_ENVIRONMENT_KEYS = {
    "EMBEDDING_BINDING",
    "EMBEDDING_MODEL",
    "LLM_BINDING",
    "LLM_MODEL",
    "QUERY_LLM_BINDING",
    "QUERY_LLM_MODEL",
    "RAG_EVAL_SEED",
}


def safe_environment(values: os._Environ[str] | dict[str, str]) -> dict[str, str]:
    """Return the non-secret environment allowlist safe for diagnostics."""

    return {
        key: str(values[key])
        for key in sorted(SAFE_ENVIRONMENT_KEYS.intersection(values))
    }


class SecretStore(Protocol):
    def set(self, value: str) -> str: ...
    def get(self, reference: str) -> str: ...
    def delete(self, reference: str) -> None: ...


class DeferredSecretStore:
    """Avoid touching a Keychain unless a product system actually uses secrets."""

    def __init__(self, factory) -> None:
        self._factory = factory
        self._store: SecretStore | None = None

    def _get_store(self) -> SecretStore:
        if self._store is None:
            self._store = self._factory()
        return self._store

    def set(self, value: str) -> str:
        return self._get_store().set(value)

    def get(self, reference: str) -> str:
        return self._get_store().get(reference)

    def delete(self, reference: str) -> None:
        self._get_store().delete(reference)


def _identifier(reference: str) -> str:
    prefix = "secret://local/"
    if not reference.startswith(prefix):
        raise ValueError("invalid local secret reference")
    return reference.removeprefix(prefix)


class KeychainSecretStore:
    """Keychain-only store; an insecure keyring backend is rejected."""

    service_name = "rag-eval-platform"

    def _keyring(self):
        try:
            import keyring  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("system Keychain is unavailable; install keyring or explicitly enable encrypted development storage") from exc
        backend = keyring.get_keyring()
        module = type(backend).__module__.lower()
        if "fail" in module or "plaintext" in module:
            raise RuntimeError("no secure system Keychain backend is available")
        return keyring

    def set(self, value: str) -> str:
        identifier = secrets.token_urlsafe(24)
        self._keyring().set_password(self.service_name, identifier, value)
        return f"secret://local/{identifier}"

    def get(self, reference: str) -> str:
        value = self._keyring().get_password(self.service_name, _identifier(reference))
        if value is None:
            raise KeyError("secret reference is not configured")
        return value

    def delete(self, reference: str) -> None:
        try:
            self._keyring().delete_password(self.service_name, _identifier(reference))
        except Exception:
            return


class EncryptedDevFileSecretStore:
    """Explicit AES-GCM development fallback; never selected automatically."""

    def __init__(self, path: Path, encoded_key: str) -> None:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:
            raise RuntimeError("encrypted development storage requires cryptography") from exc
        try:
            key = base64.urlsafe_b64decode(encoded_key.encode("ascii"))
        except Exception as exc:
            raise RuntimeError("RAG_EVAL_SECRET_STORE_KEY must be base64 encoded") from exc
        if len(key) != 32:
            raise RuntimeError("RAG_EVAL_SECRET_STORE_KEY must decode to exactly 32 bytes")
        self.path, self._cipher = path, AESGCM(key)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        if stat.S_IMODE(self.path.stat().st_mode) != 0o600:
            raise RuntimeError("encrypted development secret file must have mode 0600")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("encrypted development secret file is malformed")
        return {str(key): str(value) for key, value in payload.items()}

    def _write(self, values: dict[str, str]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(values, sort_keys=True), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)

    def set(self, value: str) -> str:
        identifier = secrets.token_urlsafe(24)
        nonce = os.urandom(12)
        ciphertext = self._cipher.encrypt(nonce, value.encode("utf-8"), identifier.encode("utf-8"))
        values = self._read()
        values[identifier] = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
        self._write(values)
        return f"secret://local/{identifier}"

    def get(self, reference: str) -> str:
        identifier = _identifier(reference)
        encoded = self._read().get(identifier)
        if encoded is None:
            raise KeyError("secret reference is not configured")
        payload = base64.urlsafe_b64decode(encoded.encode("ascii"))
        return self._cipher.decrypt(payload[:12], payload[12:], identifier.encode("utf-8")).decode("utf-8")

    def delete(self, reference: str) -> None:
        identifier = _identifier(reference)
        values = self._read()
        if values.pop(identifier, None) is not None:
            self._write(values)


def create_secret_store(dev_file: Path) -> SecretStore:
    if os.environ.get("RAG_EVAL_ENABLE_ENCRYPTED_DEV_SECRET_STORE") == "1":
        key = os.environ.get("RAG_EVAL_SECRET_STORE_KEY")
        if not key:
            raise RuntimeError("encrypted development storage is enabled but RAG_EVAL_SECRET_STORE_KEY is missing")
        return EncryptedDevFileSecretStore(dev_file, key)
    return KeychainSecretStore()
