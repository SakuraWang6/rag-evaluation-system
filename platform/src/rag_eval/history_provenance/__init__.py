"""Read-only reconstruction and acceptance helpers for historical RAG runs.

The package deliberately keeps historical artifacts separate from the normal
run/evaluation modules.  In particular, baseline capture never writes inside
the run directory and refuses to replace an existing derived directory.
"""

from .baseline import (
    BaselineManifest,
    BaselineVerification,
    capture_immutable_baseline,
    verify_immutable_baseline,
)
from .reconstruction import (
    CORPUS_INDEX_SCHEMA_VERSION,
    MAP_SCHEMA_VERSION,
    MATRIX_SCHEMA_VERSION,
    RECONSTRUCTION_SCHEMA_VERSION,
    CorpusEvidenceIndex,
    build_historical_localization_matrix,
    build_production_localization_audit,
    attach_runtime_provenance,
    load_corpus_evidence_index,
    matrix_markdown,
    reconstruct_historical_provenance,
    runtime_provenance_metadata,
    write_derived_json,
    write_derived_text,
    write_reconstructed_provenance,
)
from .rescore import (
    RESCORE_ACCEPTANCE_SCHEMA_VERSION,
    RESCORE_SCHEMA_VERSION,
    rescore_historical_run,
    rescore_markdown,
    write_historical_rescore,
)
from .acceptance import (
    PROJECTION_ACCEPTANCE_SCHEMA_VERSION,
    PROJECTION_ACCEPTANCE_STATUS,
    accept_historical_rescore_projection,
    accepted_projection_receipt,
    write_historical_rescore_projection_acceptance,
)

__all__ = [
    "BaselineManifest",
    "BaselineVerification",
    "capture_immutable_baseline",
    "verify_immutable_baseline",
    "MAP_SCHEMA_VERSION",
    "RECONSTRUCTION_SCHEMA_VERSION",
    "CORPUS_INDEX_SCHEMA_VERSION",
    "MATRIX_SCHEMA_VERSION",
    "CorpusEvidenceIndex",
    "load_corpus_evidence_index",
    "reconstruct_historical_provenance",
    "build_historical_localization_matrix",
    "build_production_localization_audit",
    "runtime_provenance_metadata",
    "attach_runtime_provenance",
    "matrix_markdown",
    "write_reconstructed_provenance",
    "write_derived_json",
    "write_derived_text",
    "RESCORE_SCHEMA_VERSION",
    "RESCORE_ACCEPTANCE_SCHEMA_VERSION",
    "rescore_historical_run",
    "rescore_markdown",
    "write_historical_rescore",
    "PROJECTION_ACCEPTANCE_SCHEMA_VERSION",
    "PROJECTION_ACCEPTANCE_STATUS",
    "accept_historical_rescore_projection",
    "accepted_projection_receipt",
    "write_historical_rescore_projection_acceptance",
]
