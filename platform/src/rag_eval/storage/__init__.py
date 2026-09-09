"""Atomic file-backed platform storage.

The package deliberately avoids importing the legacy Run store eagerly.  The
Artifact 2.0 implementation depends on :mod:`rag_eval.storage.atomic`; loading
that small helper must not recursively initialise the legacy Run reader.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rag_eval.storage.layout import PlatformPaths
    from rag_eval.storage.runs import RunStore


def __getattr__(name: str) -> Any:
    if name == "PlatformPaths":
        from rag_eval.storage.layout import PlatformPaths

        return PlatformPaths
    if name == "RunStore":
        from rag_eval.storage.runs import RunStore

        return RunStore
    raise AttributeError(name)


__all__ = ["PlatformPaths", "RunStore"]
