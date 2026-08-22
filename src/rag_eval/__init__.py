"""System-neutral RAG evaluation platform."""

from rag_eval.contracts import (
    CONTRACT_VERSION,
    PRODUCER,
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
)

__all__ = ["CONTRACT_VERSION", "PRODUCER", "PROTOCOL_VERSION", "SCHEMA_VERSION"]

__version__ = "0.1.0"
