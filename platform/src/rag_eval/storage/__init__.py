"""Atomic file-backed Platform storage primitives."""

from rag_eval.storage.ids import safe_id
from rag_eval.storage.layout import PlatformPaths

__all__ = ["PlatformPaths", "safe_id"]
