"""Path-safe identifiers shared by Platform stores."""

from __future__ import annotations


def safe_id(value: str) -> str:
    if not value or any(
        character
        not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for character in value
    ):
        raise ValueError(f"unsafe identifier: {value!r}")
    return value


__all__ = ["safe_id"]
