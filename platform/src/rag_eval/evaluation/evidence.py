"""Provenance-first Gold Evidence matching and localization.

The evaluator deliberately keeps three concerns separate:

* matching one returned item to one Gold object;
* localizing every Gold object at one retrieval stage; and
* reducing those localizations through the Gold MSES expression.

The last expression is ``OR(paths) -> AND(clauses) -> OR(evidence)``.  A
returned chunk may project several canonical objects at the same rank.  The
rank is therefore always the rank of the source chunk; a projection never
creates a synthetic rank.

``CorpusEvidenceIndex`` is intentionally a small, read-only bridge.  Existing
callers may construct it with only ``{document_id: text}``.  A formal run can
add a versioned provenance map with ``from_provenance_map`` (or pass it as the
second positional argument).  The map supplies the global
canonical-object-to-runtime-chunk reverse index needed to distinguish a true
retrieval miss from an unlocalized returned chunk.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from rag_eval.contracts.adapter import RAGEvidenceItem
from rag_eval.contracts.dataset import (
    GoldEvidence,
    GoldEvidenceSet,
    ObjectLocator,
    PageRegionLocator,
    TableCellLocator,
    TextSpanLocator,
)
from rag_eval.evaluation.answers import normalize_text


EVIDENCE_SCORER_ID = "provenance-evidence-groups"
EVIDENCE_SCORER_VERSION = "1.2"


def scorer_source_digest() -> str:
    """Digest the source that implements deterministic evidence scoring.

    A hand-maintained label is not a reproducibility boundary: changing the
    localizer or the stage reducer without changing that label would make a
    rescore indistinguishable from the old score.  The evidence digest covers
    both this module and the metric reducer (the latter is imported only for
    its source bytes, so there is no import cycle).
    """

    digest = hashlib.sha256()
    for path in (
        Path(__file__),
        Path(__file__).with_name("metrics.py"),
    ):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            # Keep imports usable in unusual packaged environments.  The
            # module name remains in the digest, but a missing source is not
            # silently presented as the normal source fingerprint.
            digest.update(b"<source-unavailable>")
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


EVIDENCE_SCORER_DIGEST = scorer_source_digest()

PROVENANCE_UNAVAILABLE_REASON = (
    "runtime provenance mapping is unavailable for locator-only Gold Evidence"
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_FORMAL_METADATA_KEYS = frozenset(
    {
        "provenance_schema",
        "source_sha256",
        "source_digest",
        "content_sha256",
        "trace_content_sha256",
        "trace_source_sha256",
        "source_witness_sha256",
        "canonical_witness_sha256",
        "canonical_objects",
        "provenance_edges",
        "edges",
        "formal_provenance",
        "canonical_provenance_map_digest",
        "provenance_map_digest",
        "map_digest",
        "canonical_segment_ids",
        "canonical_segment_batch_id",
        "canonical_segment_manifest_digest",
    }
)

_RANGE_METADATA_KEYS = frozenset(
    {
        "runtime_source_span",
        "source_span",
        "canonical_overlap_span",
        "overlap_span",
        "expected_extent",
        "canonical_object_span",
    }
)


class EvidenceMatchKind(StrEnum):
    """How an item was associated with Gold Evidence."""

    EXACT_PROVENANCE = "exact_provenance"
    SAME_DOCUMENT_UNIQUE_QUOTE = "same_document_unique_quote"
    CORPUS_UNIQUE_QUOTE = "corpus_unique_quote"


class LocalizationStatus(StrEnum):
    """Per-Gold, per-stage localization result."""

    MATCHED = "matched"
    PARTIAL = "partial"
    RETRIEVAL_MISSED = "retrieval_missed"
    PROVENANCE_MISSING = "provenance_missing"


# Names used by early P1 callers.  Keeping aliases avoids making the
# transport contract depend on one spelling while exposing one enum value set.
EvidenceLocalizationStatus = LocalizationStatus
GoldEvidenceLocalizationStatus = LocalizationStatus


@dataclass(frozen=True, slots=True)
class EvidenceMatch:
    evidence_id: str
    item_id: str
    rank: int
    kind: EvidenceMatchKind
    # These fields are optional extensions; old consumers only used the first
    # four fields above.
    coverage: tuple[dict[str, Any], ...] = ()
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class GoldLocalization:
    """One Gold object's state at one stage (and optional cutoff)."""

    evidence_id: str
    status: LocalizationStatus
    rank: int | None = None
    item_ids: tuple[str, ...] = ()
    match_kind: EvidenceMatchKind | None = None
    reason: str | None = None
    coverage: tuple[dict[str, Any], ...] = ()

    @property
    def matched(self) -> bool:
        return self.status == LocalizationStatus.MATCHED

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "status": self.status.value,
            "rank": self.rank,
            "item_ids": list(self.item_ids),
            "match_kind": self.match_kind.value if self.match_kind else None,
            "reason": self.reason,
            "coverage": [dict(value) for value in self.coverage],
        }


@dataclass(frozen=True, slots=True)
class StageLocalization:
    """Per-Gold localization for one raw/ranked/context stage."""

    stage: str
    observable: bool
    gold: Mapping[str, GoldLocalization]
    cutoff: int | None = None
    reason: str | None = None

    @property
    def statuses(self) -> Mapping[str, LocalizationStatus]:
        return {key: value.status for key, value in self.gold.items()}

    @property
    def provenance_missing(self) -> bool:
        return any(
            value.status == LocalizationStatus.PROVENANCE_MISSING
            for value in self.gold.values()
        )

    def complete_path(self, evidence_set: GoldEvidenceSet) -> bool:
        return any(
            all(
                any(
                    self.gold.get(evidence_id, _missing_localization(evidence_id)).status
                    == LocalizationStatus.MATCHED
                    for evidence_id in clause
                )
                for clause in path
            )
            for path in _paths(evidence_set)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "observable": self.observable,
            "cutoff": self.cutoff,
            "reason": self.reason,
            "gold": {
                key: value.as_dict() for key, value in sorted(self.gold.items())
            },
        }


@dataclass(frozen=True, slots=True)
class _PartialPiece:
    evidence_id: str
    item_id: str
    rank: int
    start: int
    end: int
    object_id: str | None
    coverage: dict[str, Any]


class CorpusEvidenceIndex:
    """Source text plus an optional verified provenance catalog.

    Minimal formal-ingestion interface:

    ``CorpusEvidenceIndex.from_provenance_map(payload, documents=...)``
    accepts the map emitted by the provenance bridge.  Consumers then use
    ``runtime_edges_for(document_id, object_id)`` and
    ``has_verified_object(document_id, object_id)``.  ``payload`` may use the
    current ``object_to_runtime_chunks`` reverse map or the equivalent
    ``reverse_index``/``edges`` spelling.  A reverse edge is considered only
    when its forward runtime chunk round-trips to the same object.  A malformed
    map is kept as an unverified catalog and cannot prove a retrieval miss.

    The old ``CorpusEvidenceIndex(documents)`` constructor remains valid.
    It provides deterministic quote counts and source-text span witnesses but
    cannot prove that a locator-only object was absent from retrieval.
    """

    def __init__(
        self,
        documents: Mapping[str, str] | None = None,
        provenance_map: Mapping[str, Any] | None = None,
        *,
        provenance_catalog: Mapping[str, Any] | None = None,
        reverse_index: Mapping[str, Any] | None = None,
        runtime_chunks: Mapping[str, Any] | None = None,
        runtime_documents: Mapping[str, str] | None = None,
        execution_streams: Mapping[str, str] | None = None,
        object_catalog: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
        document_digests: Mapping[str, str] | None = None,
        source_digests: Mapping[str, str] | None = None,
        catalog_verified: bool | None = None,
        expected_map_digest: str | None = None,
        pinned_map_digest: str | None = None,
        expected_map_bytes_digest: str | None = None,
        pinned_map_bytes_digest: str | None = None,
        map_bytes_digest: str | None = None,
        catalog_diagnostics: Iterable[str] | None = None,
    ) -> None:
        self.documents = {
            str(key): str(value)
            for key, value in (documents or {}).items()
            if isinstance(key, str) and isinstance(value, str)
        }
        # ``documents`` is the source/quote view.  Formal runtime spans live
        # in a separate execution coordinate system; callers should provide
        # that view through ``runtime_documents`` (``execution_streams`` is a
        # readable alias).  Keeping both prevents a raw canonical JSONL
        # source from being mistaken for the native retrieval stream.
        self.runtime_documents = {
            str(key): str(value)
            for key, value in (runtime_documents or execution_streams or {}).items()
            if isinstance(key, str) and isinstance(value, str)
        }
        payload: Mapping[str, Any] | None = provenance_map or provenance_catalog
        self.provenance_map = dict(payload) if isinstance(payload, Mapping) else None
        # Adapters/executors can retain a human-readable load failure without
        # weakening the fail-closed formal decision.  This is deliberately
        # diagnostic-only and is not used as a scoring witness.
        self.catalog_diagnostics = tuple(
            str(value)
            for value in (catalog_diagnostics or ())
            if isinstance(value, str) and value.strip()
        )
        # A digest persisted inside the same payload is useful for diagnostics,
        # but is not an external pin.  Callers that want the catalog to prove a
        # retrieval miss must pass the digest obtained from the run manifest.
        requested_map_digest = expected_map_digest or pinned_map_digest
        requested_map_bytes_digest = (
            expected_map_bytes_digest or pinned_map_bytes_digest
        )
        self.map_digest = _mapping_digest(payload) if payload is not None else None
        self.map_bytes_digest = _normalize_digest(map_bytes_digest)
        self.map_digest_verified = bool(
            requested_map_digest
            and self.map_digest is not None
            and _normalize_digest(requested_map_digest) == self.map_digest
        )
        self.map_bytes_digest_verified = bool(
            requested_map_bytes_digest
            and self.map_bytes_digest is not None
            and _normalize_digest(requested_map_bytes_digest)
            == self.map_bytes_digest
        )
        # ``map_digest`` is the canonical logical JSON digest.  A file-backed
        # adapter may instead pin the exact serialized bytes it wrote.  Both
        # are valid external pins, but they are deliberately exposed as
        # separate facts so a pretty-file SHA is never compared as if it were
        # the logical payload digest.
        self.map_pin_verified = (
            self.map_digest_verified or self.map_bytes_digest_verified
        )
        raw_documents: Mapping[str, Any] = {}
        raw_runtime: Mapping[str, Any] = runtime_chunks or {}
        raw_reverse: Mapping[str, Any] = reverse_index or {}
        raw_objects: Mapping[str, Any] | Sequence[Mapping[str, Any]] = (
            object_catalog or {}
        )
        if payload is not None:
            maybe_documents = payload.get("documents")
            normalized_documents = _records_by_id(maybe_documents, "document_id")
            if normalized_documents:
                raw_documents = normalized_documents
            maybe_runtime = payload.get("runtime_chunks")
            normalized_runtime = _records_by_id(maybe_runtime, "runtime_chunk_id")
            if normalized_runtime:
                raw_runtime = normalized_runtime
            maybe_reverse = (
                payload.get("object_to_runtime_chunks")
                or payload.get("object_to_chunks")
                or payload.get("reverse_index")
            )
            if isinstance(maybe_reverse, Mapping):
                raw_reverse = maybe_reverse
            maybe_objects = (
                payload.get("object_catalog")
                or payload.get("canonical_objects")
                or payload.get("objects")
            )
            if isinstance(maybe_objects, (Mapping, list, tuple)):
                raw_objects = maybe_objects
            maybe_streams = payload.get("runtime_documents") or payload.get("execution_streams")
            if not self.runtime_documents and isinstance(maybe_streams, Mapping):
                self.runtime_documents = {
                    str(key): str(value)
                    for key, value in maybe_streams.items()
                    if isinstance(key, str) and isinstance(value, str)
                }

        self._document_digests: dict[str, str] = {}
        self._external_source_digest_ids: set[str] = set()
        for values in (source_digests or {}, document_digests or {}):
            for key, value in values.items():
                normalized = _normalize_digest(value)
                if normalized:
                    document_key = str(key)
                    self._document_digests[document_key] = normalized
                    self._external_source_digest_ids.add(document_key)
        for document_id, record in raw_documents.items():
            if not isinstance(record, Mapping):
                continue
            for key in ("source_sha256", "source_digest", "sha256"):
                digest = _normalize_digest(record.get(key))
                if digest:
                    self._document_digests.setdefault(str(document_id), digest)

        self.runtime_chunks: dict[str, dict[str, Any]] = {
            str(key): dict(value)
            for key, value in raw_runtime.items()
            if isinstance(value, Mapping)
        }
        self.object_catalog: dict[tuple[str | None, str], dict[str, Any]] = {}
        self._valid_catalog_keys: set[tuple[str | None, str]] = set()
        self._invalid_catalog_keys: set[tuple[str | None, str]] = set()
        self._object_ids_by_document: dict[str, set[str]] = defaultdict(set)
        self._catalog_round_trip_ok = True
        self._load_object_catalog(raw_objects)

        self.reverse_index: dict[str, tuple[dict[str, Any], ...]] = {}
        self._load_reverse_index(raw_reverse)
        self._load_top_level_edges(payload)
        self._derive_forward_edges()
        # The catalog is run-scoped and can contain thousands of canonical
        # objects.  Build the typed-locator and runtime reverse lookups once;
        # per-Gold localization must not rescan the whole catalog for every
        # TableCellLocator (or every repeated stage/cutoff).
        self._build_lookup_indexes()
        self.source_pins_verified = self._source_pins_are_verified(raw_documents)

        # Do not infer trust from a schema version or from a boolean embedded
        # in the untrusted map.  ``catalog_verified`` is an explicit caller
        # decision; a pinned digest can establish the same decision when it
        # matches the externally supplied value.
        explicit_verified = catalog_verified if isinstance(catalog_verified, bool) else None
        if explicit_verified is None and self.map_pin_verified:
            explicit_verified = True
        # ``catalog_verified=True`` is not a trust bypass.  A formal
        # run-level map must be pinned by a digest obtained outside the map
        # itself; otherwise a caller could mutate forward/reverse/catalog
        # records and simply assert that the result was verified.
        if (payload is not None or self.runtime_chunks or self.reverse_index or self.object_catalog) and not self.map_pin_verified:
            explicit_verified = False
        if (payload is not None or self.runtime_chunks or self.reverse_index or self.object_catalog) and not self.source_pins_verified:
            explicit_verified = False
        self.catalog_verified = bool(
            explicit_verified is True
            and bool(
                any(self.reverse_index.values())
            )
            and self._catalog_round_trip_ok
        )

    @classmethod
    def from_provenance_map(
        cls,
        payload: Mapping[str, Any],
        *,
        documents: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> "CorpusEvidenceIndex":
        """Build an index from a run-level canonical/runtime map."""

        if not isinstance(payload, Mapping):
            raise TypeError("provenance map must be a mapping")
        return cls(documents, payload, **kwargs)

    # Clear alias used by ingestion callers.
    from_runtime_provenance_map = from_provenance_map

    @classmethod
    def from_reconstruction(
        cls,
        payload: Mapping[str, Any],
        *,
        documents: Mapping[str, str] | None = None,
        runtime_documents: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> "CorpusEvidenceIndex":
        """Consume the historical-recovery serializer's list-shaped map.

        Recovery emits ``documents``/``runtime_chunks`` as lists and stores
        per-chunk projections under ``objects``.  The evaluator normalizes
        that transport into the same forward/reverse catalog contract; it does
        not use recovery's separate scoring implementation.
        """

        if not isinstance(payload, Mapping):
            raise TypeError("reconstruction must be a mapping")
        return cls(
            documents,
            payload,
            runtime_documents=runtime_documents,
            **kwargs,
        )

    @property
    def has_provenance_catalog(self) -> bool:
        """Whether at least one pinned, trusted catalog edge is available.

        ``catalog_verified`` is map-level availability, not a blanket claim
        that every record is sound.  Individual malformed/mismatched edges
        are removed during round-trip validation; callers still resolve only
        the surviving edge/object identities.
        """

        return self.catalog_verified

    @property
    def catalog_round_trip_verified(self) -> bool:
        """Expose the formal forward/reverse/object identity check.

        This is intentionally separate from ``catalog_verified``: an adapter
        can inspect a malformed map and retain it for diagnostics, while only
        a map with external pins *and* a successful round trip may support
        strict localization decisions.
        """

        return self._catalog_round_trip_ok

    def _source_pins_are_verified(self, raw_documents: Mapping[str, Any]) -> bool:
        """Check external source pins against map document identity claims."""

        required: set[str] = set()
        for hinted_id, record in raw_documents.items():
            if isinstance(record, Mapping):
                document_id = record.get("document_id") or hinted_id
                if isinstance(document_id, str) and document_id:
                    required.add(document_id)
        for (document_id, _object_id), _record in self.object_catalog.items():
            if document_id is not None:
                required.add(document_id)
        for edges in self.reverse_index.values():
            for edge in edges:
                document_id = edge.get("document_id")
                if isinstance(document_id, str) and document_id:
                    required.add(document_id)
        if not required or not required.issubset(self._external_source_digest_ids):
            return False
        # The external pin is authoritative, but an embedded source claim
        # that disagrees proves the map was assembled for another source.
        for document_id in required:
            pinned = self._document_digests.get(document_id)
            document_record = raw_documents.get(document_id)
            if not isinstance(document_record, Mapping):
                document_record = next(
                    (
                        value
                        for hinted_id, value in raw_documents.items()
                        if hinted_id == document_id and isinstance(value, Mapping)
                    ),
                    None,
                )
            if isinstance(document_record, Mapping):
                embedded_document = _normalize_digest(
                    document_record.get("source_sha256")
                    or document_record.get("source_digest")
                    or document_record.get("sha256")
                )
                if embedded_document is not None and embedded_document != pinned:
                    return False
            records = [
                value
                for (record_document, _object_id), value in self.object_catalog.items()
                if record_document == document_id and isinstance(value, Mapping)
            ]
            for record in records:
                embedded = _normalize_digest(
                    record.get("source_sha256") or record.get("source_digest")
                )
                if embedded is not None and embedded != pinned:
                    return False
        return True

    def document_digest(self, document_id: str) -> str | None:
        candidates = self.document_digest_candidates(document_id)
        return next(iter(candidates), None)

    def document_digest_candidates(self, document_id: str) -> tuple[str, ...]:
        values: list[str] = []
        explicit = self._document_digests.get(document_id)
        if explicit:
            values.append(explicit)
        text = self.documents.get(document_id)
        if text is not None:
            values.append(_sha256_text(text))
        runtime = self.runtime_documents.get(document_id)
        if runtime is not None:
            values.append(_sha256_text(runtime))
        # Stable uniqueness while allowing a DOCX-byte digest and a canonical
        # execution-text digest to coexist.
        return tuple(dict.fromkeys(values))

    def quote_counts(self, quote: str) -> tuple[dict[str, int], int]:
        normalized_quote = normalize_text(quote)
        if not normalized_quote:
            return {}, 0
        counts = {
            document_id: normalize_text(content).count(normalized_quote)
            for document_id, content in self.documents.items()
        }
        return counts, sum(counts.values())

    def has_verified_object(self, document_id: str, object_id: str) -> bool:
        """Whether the catalog proves the object exists in ``document_id``."""

        if not self.catalog_verified:
            return False
        if self._catalog_record(document_id, object_id) is not None:
            return True
        if object_id in self._object_ids_by_document.get(document_id, set()):
            return True
        # A runtime reverse edge may be the only object-catalog record in the
        # compact map.  It is safe only after forward/reverse round-trip
        # validation has attached an explicit document identity to the edge.
        return any(
            edge.get("document_id") == document_id
            for edge in self.reverse_index.get(object_id, ())
        )

    def catalog_record(
        self, document_id: str, object_id: str
    ) -> Mapping[str, Any] | None:
        """Return one independently validated object-catalog record."""

        return self._catalog_record(document_id, object_id)

    def _catalog_record(
        self, document_id: str, object_id: str
    ) -> dict[str, Any] | None:
        for key in ((document_id, object_id), (None, object_id)):
            if key in self._invalid_catalog_keys:
                continue
            record = self.object_catalog.get(key)
            if record is not None and key in self._valid_catalog_keys:
                return record
        return None

    def runtime_edges_for(
        self, document_id: str, object_id: str
    ) -> tuple[dict[str, Any], ...]:
        """Return verified reverse edges for one source object."""

        if not self.catalog_verified:
            return ()
        values = list(self.reverse_index.get(object_id, ()))
        result: list[dict[str, Any]] = []
        for edge in values:
            edge_document = edge.get("document_id")
            if edge_document not in (None, document_id):
                continue
            enriched = dict(edge)
            # Compact reverse edges may carry only IDs/coverage.  Enriching
            # them from the independently loaded object catalog makes typed
            # table-cell/region checks possible without copying the catalog
            # into every returned item.
            record = self._catalog_record(document_id, object_id)
            if record is not None:
                for key in (
                    "object_type",
                    "locator",
                    "typed_locator",
                    "expected_extent",
                    "source_sha256",
                    "witness_sha256",
                ):
                    if key not in enriched and key in record:
                        enriched[key] = record[key]
            result.append(enriched)
        return tuple(result)

    def runtime_ids_for(self, document_id: str, object_id: str) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                str(edge["runtime_chunk_id"])
                for edge in self.runtime_edges_for(document_id, object_id)
                if isinstance(edge.get("runtime_chunk_id"), str)
            )
        )

    def edge_for_item(
        self, item: RAGEvidenceItem, object_id: str
    ) -> tuple[dict[str, Any], ...]:
        """Resolve an item's native/runtime id through the global catalog."""

        if item.document_id is None:
            return ()
        runtime_id = _item_runtime_id(item)
        if runtime_id is None:
            return ()
        return tuple(
            edge
            for edge in self.runtime_edges_for(item.document_id, object_id)
            if edge.get("runtime_chunk_id") == runtime_id
        )

    def object_ids_for_runtime(self, item: RAGEvidenceItem) -> tuple[str, ...]:
        runtime_id = _item_runtime_id(item)
        if runtime_id is None:
            return ()
        return self._object_ids_by_runtime.get(runtime_id, ())

    def table_cell_objects(
        self, document_id: str, table_id: str
    ) -> tuple[tuple[str, dict[str, Any]], ...]:
        """Return catalogued physical-cell objects for one table.

        The catalog is deliberately queried at run scope.  A cell is accepted
        only when its typed locator identifies the requested table; a matching
        value or a shared document is not enough to establish physical
        identity.  This small method is the table-completeness hook used by
        the evaluator and is also useful to ingestion/executor adapters.
        """

        if not self.catalog_verified:
            return ()
        values: dict[str, dict[str, Any]] = {}
        for key in ((document_id, table_id), (None, table_id)):
            for object_id, record in self._table_cells_by_document_table.get(key, ()):
                if (key[0], object_id) not in self._valid_catalog_keys:
                    continue
                values.setdefault(object_id, dict(record))
        return tuple(sorted(values.items(), key=lambda value: value[0]))

    def has_complete_table_footprint(self, document_id: str, table_id: str) -> bool:
        """Whether every physical cell of a table has a full runtime witness.

        A Word table envelope is often intentionally represented by one
        partial edge per row.  That is enough to navigate the table, but not
        enough to claim that a whole-table Gold object is scoreable.  The
        authoritative proof is its catalogued physical-cell footprint: every
        cell must have a complete typed extent and at least one independently
        verified, full edge to a runtime chunk.

        This is a *run-level* mapping check.  It does not say a particular
        retrieval stage selected every cell; ``_complete_table_union`` and
        ``_partial_table_footprint`` handle that later.
        """

        if not self.catalog_verified or not self.has_verified_object(
            document_id, table_id
        ):
            return False
        cells = self.table_cell_objects(document_id, table_id)
        if not cells:
            return False
        for object_id, record in cells:
            if not self.has_complete_expected_extent(document_id, object_id):
                return False
            locator = _record_locator(record)
            if not any(
                _edge_is_full(edge)
                and (locator is None or _edge_matches_locator(edge, locator))
                for edge in self.runtime_edges_for(document_id, object_id)
            ):
                return False
        return True

    def object_ids_for_locator(
        self, document_id: str, locator: Any
    ) -> tuple[str, ...]:
        """Resolve a typed locator to catalog IDs without value matching."""

        if not self.catalog_verified:
            return ()
        if isinstance(locator, ObjectLocator):
            return (
                (locator.object_id,)
                if self.has_verified_object(document_id, locator.object_id)
                else ()
            )
        key = _locator_key(locator)
        if key is None:
            return ()
        values: set[str] = set()
        for document_key in (document_id, None):
            values.update(self._object_ids_by_locator.get((document_key, key), ()))
        return tuple(sorted(values))

    def has_complete_expected_extent(self, document_id: str, object_id: str) -> bool:
        """Whether the catalog can support a definitive retrieval-miss claim."""

        record = self.object_catalog.get((document_id, object_id))
        if record is None or (document_id, object_id) not in self._valid_catalog_keys:
            record = self._catalog_record(document_id, object_id)
        if record is None:
            return False
        mapping_status = record.get("mapping_status") or record.get("status")
        expected = record.get("expected_extent")
        # The production P0 bridge uses ``mapped/partial/unmapped`` for the
        # object-level status and intentionally omits a second status field in
        # ``expected_extent``.  ``mapped`` is an explicit complete mapping
        # witness only when the extent itself is a non-empty, well-formed
        # structure.  It is not equivalent to a returned edge's
        # ``coverage=full`` claim and cannot be asserted by an item.
        complete_status = mapping_status in {"complete", "verified", "mapped"}
        if not complete_status or not isinstance(expected, Mapping):
            return False
        expected_status = expected.get("status")
        if expected_status is not None and expected_status not in {
            "complete",
            "verified",
            "mapped",
        }:
            return False
        return _extent_mapping_valid(expected)

    def prove_true_miss(
        self,
        document_id: str,
        object_id: str,
        retrieved_chunk_ids: Iterable[str],
    ) -> bool:
        """Prove absence only from a complete object extent and reverse map."""

        if not self.has_complete_expected_extent(document_id, object_id):
            return False
        edges = self.runtime_edges_for(document_id, object_id)
        if not edges or not all(_edge_has_explicit_coverage(edge) for edge in edges):
            return False
        expected = {
            str(edge.get("runtime_chunk_id"))
            for edge in edges
            if isinstance(edge.get("runtime_chunk_id"), str)
        }
        if not expected:
            return False
        return expected.isdisjoint({str(value) for value in retrieved_chunk_ids})

    def _load_object_catalog(
        self, raw: Mapping[str, Any] | Sequence[Mapping[str, Any]]
    ) -> None:
        entries: list[tuple[str | None, Mapping[str, Any]]] = []
        if isinstance(raw, Mapping):
            for key, value in raw.items():
                if isinstance(value, Mapping):
                    entries.append((str(key), value))
                else:
                    self._catalog_round_trip_ok = False
        else:
            for value in raw:
                if isinstance(value, Mapping):
                    entries.append((None, value))
        for hinted_id, value in entries:
            explicit_id = value.get("object_id") or value.get("canonical_object_id")
            entry_invalid = False
            if hinted_id is not None and explicit_id is not None and explicit_id != hinted_id:
                # A mapping key is part of the identity, not a convenient
                # label.  Accepting ``{key: {object_id: other}}`` would let a
                # swapped locator/object ID survive all later hash checks.
                self._catalog_round_trip_ok = False
                entry_invalid = True
            object_id = explicit_id or hinted_id
            if not isinstance(object_id, str) or not object_id:
                self._catalog_round_trip_ok = False
                continue
            document_id = value.get("document_id")
            if not isinstance(document_id, str) or not document_id:
                if document_id is not None:
                    self._catalog_round_trip_ok = False
                    entry_invalid = True
                document_id = None
            record = dict(value)
            record.setdefault("object_id", object_id)
            if document_id is not None:
                record.setdefault("document_id", document_id)
            key = (document_id, object_id)
            self.object_catalog[key] = record
            if not _catalog_record_is_well_formed(record):
                self._catalog_round_trip_ok = False
                entry_invalid = True
            if entry_invalid:
                self._invalid_catalog_keys.add(key)
            else:
                self._valid_catalog_keys.add(key)
            if document_id is not None and not entry_invalid:
                self._object_ids_by_document[document_id].add(object_id)

    def _load_reverse_index(self, raw: Mapping[str, Any]) -> None:
        if not isinstance(raw, Mapping):
            self._catalog_round_trip_ok = False
            return
        for hinted_object_id, values in raw.items():
            object_id = str(hinted_object_id)
            if not isinstance(values, (list, tuple)):
                self._catalog_round_trip_ok = False
                continue
            normalized: list[dict[str, Any]] = []
            for value in values:
                edge = _normalize_edge(value, object_id=object_id)
                if edge is None:
                    self._catalog_round_trip_ok = False
                    continue
                normalized.append(edge)
            self.reverse_index[object_id] = tuple(_unique_edges(normalized))

    def _load_top_level_edges(self, payload: Mapping[str, Any] | None) -> None:
        if payload is None:
            return
        values = payload.get("edges")
        if not isinstance(values, (list, tuple)):
            return
        for value in values:
            edge = _normalize_edge(value)
            if edge is None or not isinstance(edge.get("object_id"), str):
                self._catalog_round_trip_ok = False
                continue
            current = list(self.reverse_index.get(edge["object_id"], ()))
            current.append(edge)
            self.reverse_index[edge["object_id"]] = tuple(_unique_edges(current))

    def _derive_forward_edges(self) -> None:
        """Validate reverse entries against forward runtime records."""

        if not self.runtime_chunks:
            if self.reverse_index:
                self._catalog_round_trip_ok = False
            return
        rewritten: dict[str, tuple[dict[str, Any], ...]] = {}
        for object_id, edges in self.reverse_index.items():
            checked: list[dict[str, Any]] = []
            for edge in edges:
                runtime_id = edge.get("runtime_chunk_id")
                if not isinstance(runtime_id, str):
                    self._catalog_round_trip_ok = False
                    continue
                runtime = self.runtime_chunks.get(runtime_id)
                if not isinstance(runtime, Mapping):
                    self._catalog_round_trip_ok = False
                    continue
                forward_value = runtime.get("canonical_objects")
                forward_edges = runtime.get("edges")
                forward_objects = runtime.get("objects")
                if forward_value is None and forward_edges is None and forward_objects is None:
                    self._catalog_round_trip_ok = False
                    continue
                forward_entries = _forward_entries_for_object(
                    object_id, forward_value, forward_edges, forward_objects
                )
                if not forward_entries:
                    self._catalog_round_trip_ok = False
                    continue
                checked_edge = dict(edge)
                runtime_document = runtime.get("document_id")
                if checked_edge.get("document_id") is None:
                    if not isinstance(runtime_document, str) or not runtime_document:
                        self._catalog_round_trip_ok = False
                        continue
                    checked_edge["document_id"] = runtime_document
                elif isinstance(runtime_document, str) and checked_edge["document_id"] != runtime_document:
                    self._catalog_round_trip_ok = False
                    continue
                if not any(_edge_round_trip_consistent(checked_edge, forward) for forward in forward_entries):
                    self._catalog_round_trip_ok = False
                    continue
                if not any(
                    _catalog_edge_consistent(
                        checked_edge,
                        forward,
                        self._catalog_record(
                            checked_edge.get("document_id"), object_id
                        )
                        if isinstance(checked_edge.get("document_id"), str)
                        else None,
                    )
                    for forward in forward_entries
                ):
                    self._catalog_round_trip_ok = False
                    continue
                checked.append(checked_edge)
            rewritten[object_id] = tuple(_unique_edges(checked))
        self.reverse_index = rewritten

        # The reverse direction above is necessary but not sufficient.  A
        # tampered map can delete a reverse entry while leaving the forward
        # runtime projection intact; iterating only reverse entries would then
        # incorrectly leave the catalog trusted.  Every identity-bearing
        # forward projection must have one exact reverse edge (and the same
        # independently loaded object-catalog record).
        for runtime_id, runtime in self.runtime_chunks.items():
            if not isinstance(runtime, Mapping):
                continue
            forward_entries = _forward_entries_for_all_objects(
                runtime.get("canonical_objects"),
                runtime.get("edges"),
                runtime.get("objects"),
            )
            if not forward_entries:
                continue
            runtime_document = runtime.get("document_id")
            for forward in forward_entries:
                object_id = forward.get("object_id") or forward.get("canonical_object_id")
                if not isinstance(object_id, str) or not object_id:
                    self._catalog_round_trip_ok = False
                    continue
                forward_edge = dict(forward)
                forward_edge["runtime_chunk_id"] = runtime_id
                if forward_edge.get("document_id") is None and isinstance(runtime_document, str):
                    forward_edge["document_id"] = runtime_document
                catalog = (
                    self._catalog_record(
                        forward_edge.get("document_id"), object_id
                    )
                    if isinstance(forward_edge.get("document_id"), str)
                    else None
                )
                candidates = self.reverse_index.get(object_id, ())
                if not any(
                    edge.get("runtime_chunk_id") == runtime_id
                    and edge.get("document_id") in (None, forward_edge.get("document_id"))
                    and _edge_round_trip_consistent(edge, forward_edge)
                    and _catalog_edge_consistent(edge, forward_edge, catalog)
                    for edge in candidates
                ):
                    self._catalog_round_trip_ok = False

    def _build_lookup_indexes(self) -> None:
        """Build immutable-style indexes used by repeated localization calls."""

        by_locator: dict[tuple[str | None, str], set[str]] = defaultdict(set)
        by_table: dict[
            tuple[str | None, str], dict[str, dict[str, Any]]
        ] = defaultdict(dict)
        for (document_id, object_id), record in self.object_catalog.items():
            if (document_id, object_id) not in self._valid_catalog_keys:
                continue
            locator = _record_locator(record)
            locator_key = _locator_key(locator)
            if locator_key is not None:
                by_locator[(document_id, locator_key)].add(object_id)
            table_id = None
            if isinstance(locator, TableCellLocator):
                table_id = locator.table_id
            elif str(record.get("object_type", "")) in {"cell", "table_cell"}:
                candidate = record.get("table_id")
                if isinstance(candidate, str) and candidate:
                    table_id = candidate
            if table_id is not None:
                by_table[(document_id, table_id)][object_id] = dict(record)

        by_runtime: dict[str, set[str]] = defaultdict(set)
        for object_id, edges in self.reverse_index.items():
            for edge in edges:
                runtime_id = edge.get("runtime_chunk_id")
                if isinstance(runtime_id, str) and runtime_id:
                    by_runtime[runtime_id].add(object_id)
        self._object_ids_by_locator = {
            key: tuple(sorted(values)) for key, values in by_locator.items()
        }
        self._table_cells_by_document_table = {
            key: tuple(sorted(values.items(), key=lambda value: value[0]))
            for key, values in by_table.items()
        }
        self._object_ids_by_runtime = {
            key: tuple(sorted(values)) for key, values in by_runtime.items()
        }


def match_evidence(
    item: RAGEvidenceItem,
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
) -> EvidenceMatch | None:
    """Match one item to Gold, returning only an exact/legacy hit.

    Partial intervals intentionally do not return an ``EvidenceMatch``.  They
    are accumulated by :func:`localize_stage`, where cutoff and gap checks can
    be applied to the entire source object.
    """

    integrity, integrity_reason = _metadata_integrity(item, corpus)
    if integrity == "invalid":
        return None
    if item.document_id != gold.document_id:
        # A corpus-unique quote can still be a legacy diagnostic only when the
        # runtime item did not claim a document.  A wrong explicit document is
        # never rescued by text.
        return _quote_match(item, gold, corpus, integrity, integrity_reason)

    direct = _direct_match(item, gold, corpus, integrity)
    if direct is not None:
        return direct
    return _quote_match(item, gold, corpus, integrity, integrity_reason)


def match_all(
    items: list[RAGEvidenceItem],
    evidence: list[GoldEvidence],
    corpus: CorpusEvidenceIndex,
) -> dict[str, EvidenceMatch]:
    """Return the earliest exact/legacy item per Gold evidence ID."""

    matches: dict[str, EvidenceMatch] = {}
    for gold in evidence:
        candidates = [
            match
            for item in items
            if (match := match_evidence(item, gold, corpus)) is not None
        ]
        if candidates:
            matches[gold.evidence_id] = min(
                candidates, key=lambda value: (value.rank, value.item_id)
            )
    return matches


def localize_gold_evidence(
    items: Sequence[RAGEvidenceItem],
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
    *,
    cutoff: int | None = None,
) -> GoldLocalization:
    """Localize one Gold item, including a verified partial-span union."""

    selected = _items_at_cutoff(items, cutoff)
    exact_candidates: list[EvidenceMatch] = []
    partial_candidates: list[_PartialPiece] = []
    provenance_candidates: list[tuple[int, str, str]] = []
    for item in selected:
        match = match_evidence(item, gold, corpus)
        if match is not None:
            exact_candidates.append(match)
            continue
        piece = _partial_piece(item, gold, corpus)
        if piece is not None:
            partial_candidates.append(piece)
        elif _item_references_gold(item, gold, corpus):
            reason = _provenance_reason(item) or "returned item has no verifiable canonical locator"
            provenance_candidates.append((item.rank, item.item_id, reason))

    if exact_candidates:
        best = min(exact_candidates, key=lambda value: (value.rank, value.item_id))
        return GoldLocalization(
            evidence_id=gold.evidence_id,
            status=LocalizationStatus.MATCHED,
            rank=best.rank,
            item_ids=(best.item_id,),
            match_kind=best.kind,
            reason=best.reason,
            coverage=best.coverage,
        )

    # A table is a logical object whose canonical extent is the set of its
    # physical cells.  A runtime chunk may project those cells without
    # exposing one table-level object edge, so evaluate the table footprint
    # after ordinary exact candidates and before text-span unions.  The
    # catalog, rather than a returned item's ``coverage=full`` claim, is the
    # authority for the required cell identities.
    table_union = _complete_table_union(selected, gold, corpus)
    if table_union is not None:
        rank, item_ids, coverage = table_union
        return GoldLocalization(
            evidence_id=gold.evidence_id,
            status=LocalizationStatus.MATCHED,
            rank=rank,
            item_ids=item_ids,
            match_kind=EvidenceMatchKind.EXACT_PROVENANCE,
            coverage=coverage,
        )

    # A whole table is scoreable when its complete physical-cell footprint is
    # known, even when this query only retrieved one or more rows.  Previously
    # that concrete retrieval outcome could fall through to
    # ``PROVENANCE_MISSING`` merely because the table envelope itself is
    # represented by partial row edges.  Preserve the distinction: incomplete
    # selected cells are a deterministic partial retrieval result, whereas a
    # malformed/unknown table footprint is genuinely unavailable.
    table_partial = _partial_table_footprint(selected, gold, corpus)
    if table_partial is not None:
        rank, item_ids, coverage = table_partial
        return GoldLocalization(
            evidence_id=gold.evidence_id,
            status=LocalizationStatus.PARTIAL,
            rank=rank,
            item_ids=item_ids,
            reason="verified physical table footprint is incomplete at this stage",
            coverage=coverage,
        )

    union = _complete_partial_union(
        partial_candidates,
        gold,
        expected_span=_gold_expected_span(gold, corpus),
    )
    if union is not None:
        rank, pieces = union
        return GoldLocalization(
            evidence_id=gold.evidence_id,
            status=LocalizationStatus.MATCHED,
            rank=rank,
            item_ids=tuple(piece.item_id for piece in pieces),
            match_kind=EvidenceMatchKind.EXACT_PROVENANCE,
            coverage=tuple(piece.coverage for piece in pieces),
        )

    if partial_candidates:
        ordered = sorted(partial_candidates, key=lambda value: (value.rank, value.item_id))
        return GoldLocalization(
            evidence_id=gold.evidence_id,
            status=LocalizationStatus.PARTIAL,
            rank=max(piece.rank for piece in ordered),
            item_ids=tuple(piece.item_id for piece in ordered),
            reason="verified source coverage is partial or has a gap",
            coverage=tuple(piece.coverage for piece in ordered),
        )

    # A content-only diagnostic from another, partially-attributed object
    # must not overwrite a stronger run-level absence proof.  This matters
    # for repeated Word table/paragraph values: the returned item can contain
    # the same rendered text while its verified runtime identity is a
    # different object.  Once the Gold object itself has a complete reverse
    # mapping and none of those runtime chunks were selected, the result is a
    # retrieval miss.  We still retain ``provenance_missing`` when the
    # returned item actually references the Gold object (or when no complete
    # Gold reverse mapping exists), which is the only case in which the
    # diagnostic can affect this Gold decision.
    true_miss_reason = _miss_reason(gold, corpus, selected)
    if true_miss_reason is not None:
        return GoldLocalization(
            evidence_id=gold.evidence_id,
            status=LocalizationStatus.RETRIEVAL_MISSED,
            reason=true_miss_reason,
        )

    if provenance_candidates:
        rank, item_id, reason = min(provenance_candidates, key=lambda value: (value[0], value[1]))
        return GoldLocalization(
            evidence_id=gold.evidence_id,
            status=LocalizationStatus.PROVENANCE_MISSING,
            rank=rank,
            item_ids=(item_id,),
            reason=reason,
        )

    return GoldLocalization(
        evidence_id=gold.evidence_id,
        status=LocalizationStatus.RETRIEVAL_MISSED,
        reason=true_miss_reason,
    )


def localize_stage(
    items: list[RAGEvidenceItem] | Sequence[RAGEvidenceItem] | None,
    evidence_set: GoldEvidenceSet,
    corpus: CorpusEvidenceIndex,
    *,
    stage: str = "stage",
    cutoff: int | None = None,
) -> StageLocalization:
    """Return per-Gold status for one stage.

    ``items is None`` is an unobservable stage and is deliberately represented
    by ``observable=False`` with no fabricated empty list.  ``items == []`` is
    observable and yields retrieval misses.
    """

    if items is None:
        return StageLocalization(
            stage=stage,
            observable=False,
            gold={},
            cutoff=cutoff,
            reason=f"{stage} stage is not observable",
        )
    values = {
        gold.evidence_id: localize_gold_evidence(
            items, gold, corpus, cutoff=cutoff
        )
        for gold in evidence_set.evidence
    }
    return StageLocalization(stage=stage, observable=True, gold=values, cutoff=cutoff)


def localize_retrieval_stages(
    result: Any,
    evidence_set: GoldEvidenceSet,
    corpus: CorpusEvidenceIndex,
    *,
    cutoff: int | None = None,
) -> dict[str, StageLocalization]:
    """Localize Raw, Ranked, and Context independently."""

    return {
        "raw": localize_stage(
            result.raw_retrieval,
            evidence_set,
            corpus,
            stage="raw",
            cutoff=cutoff,
        ),
        "ranked": localize_stage(
            result.ranked_retrieval,
            evidence_set,
            corpus,
            stage="ranked",
            cutoff=cutoff,
        ),
        "context": localize_stage(
            result.final_context,
            evidence_set,
            corpus,
            stage="context",
            cutoff=cutoff,
        ),
    }


# Additional discoverable spellings used in reports and downstream adapters.
localize_evidence = localize_gold_evidence
localize_evidence_stage = localize_stage
localization_matrix = localize_retrieval_stages


def evidence_observability(
    items: list[RAGEvidenceItem] | None,
    evidence_set: GoldEvidenceSet,
    corpus: CorpusEvidenceIndex,
) -> str | None:
    """Return a stage-local provenance reason, if required to score.

    An alternative path that is already complete is sufficient.  We inspect
    only unsatisfied clauses of paths that remain incomplete; unknown chunks in
    an unused alternative or diagnostic near-miss therefore cannot poison an
    independently observed stage.
    """

    if items is None:
        return None
    localized = localize_stage(items, evidence_set, corpus)
    if not localized.observable or localized.complete_path(evidence_set):
        return None
    missing_ids: list[str] = []
    for path in _paths(evidence_set):
        for clause in path:
            if any(
                localized.gold.get(evidence_id, _missing_localization(evidence_id)).status
                == LocalizationStatus.MATCHED
                for evidence_id in clause
            ):
                continue
            if any(
                localized.gold.get(evidence_id, _missing_localization(evidence_id)).status
                == LocalizationStatus.PROVENANCE_MISSING
                for evidence_id in clause
            ):
                missing_ids.extend(clause)
    if not missing_ids:
        return None
    return PROVENANCE_UNAVAILABLE_REASON


def unique_quote_diagnostics(evidence: list[GoldEvidence]) -> dict[str, int]:
    quotes = Counter(normalize_text(item.quote_anchor or "") for item in evidence)
    return {quote: count for quote, count in quotes.items() if quote and count > 1}


# ---------------------------------------------------------------------------
# Matching and formal-witness helpers


def _direct_match(
    item: RAGEvidenceItem,
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
    integrity: str,
) -> EvidenceMatch | None:
    if item.document_id != gold.document_id:
        return None
    expected = gold.locator
    observed = item.locator
    edge = _edge_for_gold(item, gold, corpus)

    if observed is not None and type(observed) is type(expected):
        if not _locator_covers(observed, expected):
            return None
        # A table object locator is not proof that one cell is a full table.
        if isinstance(expected, ObjectLocator) and expected.object_type == "table":
            if not _table_item_is_complete(item, gold, corpus, edge, integrity):
                return None
        if integrity == "invalid":
            return None
        if integrity == "formal" and not _formal_edge_supports_locator(item, gold, corpus, edge):
            return None
        return EvidenceMatch(
            evidence_id=gold.evidence_id,
            item_id=item.item_id,
            rank=item.rank,
            kind=EvidenceMatchKind.EXACT_PROVENANCE,
        )

    # A projection may have no public locator but a typed canonical edge in
    # metadata/catalog.  This is still exact provenance, not quote matching.
    if edge is not None and (
        integrity != "formal" or _formal_edge_supports_locator(item, gold, corpus, edge)
    ) and _edge_covers_gold(edge, gold, item, corpus):
        return EvidenceMatch(
            evidence_id=gold.evidence_id,
            item_id=item.item_id,
            rank=item.rank,
            kind=EvidenceMatchKind.EXACT_PROVENANCE,
        )
    return None


def _quote_match(
    item: RAGEvidenceItem,
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
    integrity: str,
    integrity_reason: str | None,
) -> EvidenceMatch | None:
    # Once a returned item opts into the formal provenance envelope, equal
    # text is only a diagnostic.  In particular, a source/content hash plus a
    # claimed locator must not fall back to a quote hit when its trusted
    # catalog edge is absent.  Quote matching remains the explicit legacy
    # compatibility path only.
    if integrity in {"invalid", "formal"}:
        return None
    quote = (gold.quote_anchor or "").strip()
    if not quote or normalize_text(quote) not in normalize_text(item.content):
        return None
    # A conflicting explicit locator is a distinct physical object.  Text
    # must never substitute duplicate table IDs or cells.
    if item.locator is not None and not _locator_compatible_for_quote(item, gold):
        return None
    if item.metadata.get("provenance_status") in {"missing", "partial", "unavailable"}:
        return None
    counts, corpus_count = corpus.quote_counts(quote)
    if item.document_id == gold.document_id and counts.get(gold.document_id) == 1:
        return EvidenceMatch(
            evidence_id=gold.evidence_id,
            item_id=item.item_id,
            rank=item.rank,
            kind=EvidenceMatchKind.SAME_DOCUMENT_UNIQUE_QUOTE,
            reason=integrity_reason,
        )
    if item.document_id is None and corpus_count == 1:
        return EvidenceMatch(
            evidence_id=gold.evidence_id,
            item_id=item.item_id,
            rank=item.rank,
            kind=EvidenceMatchKind.CORPUS_UNIQUE_QUOTE,
            reason="document identity is unavailable; corpus quote is unique",
        )
    return None


def _locator_compatible_for_quote(item: RAGEvidenceItem, gold: GoldEvidence) -> bool:
    # Quote fallback is safe only for an item without an explicit conflicting
    # physical locator.  A locator of another object is a hard no.
    if item.document_id != gold.document_id:
        return False
    if isinstance(gold.locator, ObjectLocator) and isinstance(item.locator, ObjectLocator):
        return item.locator == gold.locator
    if isinstance(gold.locator, TableCellLocator) and isinstance(item.locator, TableCellLocator):
        return item.locator == gold.locator
    if isinstance(gold.locator, TextSpanLocator) and isinstance(item.locator, TextSpanLocator):
        return _locator_covers(item.locator, gold.locator)
    if isinstance(gold.locator, PageRegionLocator) and isinstance(item.locator, PageRegionLocator):
        return _locator_covers(item.locator, gold.locator)
    return False


def _locator_covers(observed: Any, expected: Any) -> bool:
    if type(observed) is not type(expected):
        return False
    if isinstance(observed, TextSpanLocator) and isinstance(expected, TextSpanLocator):
        return observed.start <= expected.start and observed.end >= expected.end
    if isinstance(observed, ObjectLocator) and isinstance(expected, ObjectLocator):
        return observed == expected
    if isinstance(observed, TableCellLocator) and isinstance(expected, TableCellLocator):
        return observed == expected
    if isinstance(observed, PageRegionLocator) and isinstance(expected, PageRegionLocator):
        return (
            observed.page == expected.page
            and observed.x0 <= expected.x0
            and observed.y0 <= expected.y0
            and observed.x1 >= expected.x1
            and observed.y1 >= expected.y1
        )
    return False


def _metadata_integrity(
    item: RAGEvidenceItem, corpus: CorpusEvidenceIndex
) -> tuple[str, str | None]:
    """Validate trace/source witnesses without inventing missing hashes.

    ``legacy`` means no formal witness claims were made; a typed locator is
    trusted under the pre-v2 compatibility contract.  ``formal`` means at
    least one formal witness field was supplied and every supplied field is
    valid.  A ``provenance_schema`` explicitly opts into strict mode and then
    requires both source and trace content digests.
    """

    metadata = item.metadata or {}
    status = metadata.get("provenance_status")
    if status is not None and status not in {
        "full",
        "partial",
        "verified",
        "complete",
        "missing",
        "unavailable",
    }:
        return "invalid", f"provenance status is {status!r}"
    # ``missing``/``unavailable`` are explicit negative claims.  They must
    # never be treated as a legacy typed-locator witness merely because the
    # adapter omitted the rest of the formal envelope.
    if status in {"missing", "unavailable"}:
        return "invalid", f"provenance status is {status!r}"
    formal = bool(_FORMAL_METADATA_KEYS.intersection(metadata))
    strict = metadata.get("provenance_schema") is not None
    if not formal:
        return "legacy", None

    if status is not None and status not in {"full", "partial", "verified", "complete"}:
        return "invalid", f"provenance status is {status!r}"
    schema = metadata.get("provenance_schema")
    if schema is not None and schema not in {
        "canonical-provenance/v1",
        "canonical-provenance/v2",
        "canonical-runtime/v1",
        "canonical-runtime/v2",
        "canonical-segments/v1",
    }:
        return "invalid", "unsupported provenance schema"
    canonical_segments = schema == "canonical-segments/v1"

    source_digest_value = _first_value(
        metadata, "source_sha256", "source_digest", "trace_source_sha256"
    )
    content_digest_value = _first_value(
        metadata, "content_sha256", "trace_content_sha256"
    )
    source_digest = _normalize_digest(source_digest_value) if source_digest_value is not None else None
    content_digest = _normalize_digest(content_digest_value) if content_digest_value is not None else None
    if source_digest_value is not None and source_digest is None:
        return "invalid", "source digest is malformed"
    if content_digest_value is not None and content_digest is None:
        return "invalid", "trace content digest is malformed"
    for key in ("source_witness_sha256", "canonical_witness_sha256"):
        if key in metadata and _normalize_digest(metadata.get(key)) is None:
            return "invalid", f"{key} is malformed"

    for key in (
        "canonical_provenance_map_digest",
        "provenance_map_digest",
        "map_digest",
    ):
        if key not in metadata:
            continue
        map_digest = _normalize_digest(metadata.get(key))
        if map_digest is None:
            return "invalid", f"{key} is malformed"
        known_map_digests = {
            value
            for value in (corpus.map_digest, corpus.map_bytes_digest)
            if isinstance(value, str)
        }
        if known_map_digests and map_digest not in known_map_digests:
            return "invalid", "provenance map digest does not match the loaded catalog"

    if strict and (source_digest is None or content_digest is None):
        return "invalid", "formal provenance requires source and trace digests"
    if content_digest is not None and content_digest != _sha256_text(item.content):
        return "invalid", "trace content digest does not match returned content"
    if source_digest is not None and item.document_id is not None:
        candidates = corpus.document_digest_candidates(item.document_id)
        if candidates and source_digest not in candidates:
            return "invalid", "source digest does not match the indexed source"
        if not candidates and strict:
            return "invalid", "source digest cannot be verified against indexed source"

    if canonical_segments:
        segment_ids = metadata.get("canonical_segment_ids")
        if (
            not isinstance(segment_ids, list)
            or not segment_ids
            or any(not isinstance(value, str) or not value for value in segment_ids)
            or len(segment_ids) != len(set(segment_ids))
        ):
            return "invalid", "canonical segment provenance requires non-empty unique segment IDs"
        batch_id = metadata.get("canonical_segment_batch_id")
        if not isinstance(batch_id, str) or not batch_id:
            return "invalid", "canonical segment provenance requires a batch ID"
        manifest_digest = _normalize_digest(
            metadata.get("canonical_segment_manifest_digest")
        )
        if manifest_digest is None:
            return "invalid", "canonical segment manifest digest is malformed"
        runtime_id = _item_runtime_id(item)
        runtime = corpus.runtime_chunks.get(runtime_id) if runtime_id else None
        if not isinstance(runtime, Mapping):
            return "invalid", "canonical segment runtime chunk is absent from the pinned map"
        if runtime.get("mapping_mode") != "canonical_segment":
            return "invalid", "runtime chunk is not a canonical segment mapping"
        if runtime.get("batch_id") != batch_id:
            return "invalid", "canonical segment batch ID does not match the runtime map"
        if tuple(runtime.get("segment_ids") or ()) != tuple(segment_ids):
            return "invalid", "canonical segment IDs do not match the runtime map"
        if item.document_id != runtime.get("document_id"):
            return "invalid", "canonical segment source document does not match the runtime map"
        if runtime.get("canonical_segment_manifest_digest") != manifest_digest:
            return "invalid", "canonical segment manifest digest does not match the runtime map"
        primary = corpus.provenance_map.get("primary_corpus") if corpus.provenance_map else None
        if (
            not isinstance(primary, Mapping)
            or primary.get("mode") != "canonical-segments/v1"
            or primary.get("manifest_digest") != manifest_digest
        ):
            return "invalid", "canonical segment manifest digest does not match the pinned corpus"

    runtime_span = _span_from_metadata(metadata, "runtime_source_span", "source_span")
    if canonical_segments and runtime_span is not None:
        return "invalid", "canonical segment items must not claim a source-document text span"
    if any(key in metadata for key in ("runtime_source_span", "source_span")) and runtime_span is None:
        return "invalid", "runtime source span is malformed"
    if runtime_span is not None and item.document_id is not None:
        source = _runtime_source(corpus, item.document_id)
        if source is not None:
            start, end = runtime_span
            if end > len(source) or source[start:end] != item.content:
                return "invalid", "runtime source witness does not match returned content"
        elif strict:
            return "invalid", "runtime source span cannot be verified"

    for key in ("canonical_overlap_span", "overlap_span"):
        if key in metadata and _span_from_mapping(metadata.get(key)) is None:
            return "invalid", f"{key} is malformed"
    expected = metadata.get("expected_extent")
    if expected is not None and not _extent_mapping_valid(expected):
        return "invalid", "expected extent is malformed"
    canonical_span = metadata.get("canonical_object_span")
    if canonical_span is not None and _span_from_mapping(canonical_span) is None:
        return "invalid", "canonical object span is malformed"
    for key in ("canonical_objects", "provenance_edges", "edges"):
        if key in metadata and not isinstance(metadata.get(key), list):
            return "invalid", f"{key} is malformed"
    return "formal", None


def _formal_edge_supports_locator(
    item: RAGEvidenceItem,
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
    edge: Mapping[str, Any] | None,
) -> bool:
    # Hashes authenticate bytes, not the claimed canonical identity.  A
    # formal typed locator is therefore accepted only when the item's runtime
    # chunk has a separately verified, forward/reverse catalog edge for that
    # object (or a typed span/region edge that covers the Gold locator).
    if not corpus.has_provenance_catalog:
        return False
    metadata = item.metadata or {}
    metadata_ids = _metadata_object_ids(metadata)
    if isinstance(gold.locator, ObjectLocator):
        target_ids = {gold.locator.object_id}
    else:
        target_ids = set(metadata_ids)
        target_ids.update(corpus.object_ids_for_runtime(item))

    trusted: list[dict[str, Any]] = []
    for object_id in sorted(target_ids):
        trusted.extend(corpus.edge_for_item(item, object_id))
    if not trusted:
        return False

    for trusted_edge in trusted:
        if trusted_edge.get("document_id") not in (None, item.document_id):
            continue
        # A formally trusted edge can still represent only an overlap of the
        # canonical object.  Exact matching must wait for a full edge; partial
        # edges are accumulated by ``_partial_piece`` and may be promoted only
        # after a gap-free same-object union.
        if (trusted_edge.get("coverage") or trusted_edge.get("canonical_object_coverage")) != "full":
            continue
        trusted_object_id = trusted_edge.get("object_id")
        if (
            not isinstance(trusted_object_id, str)
            or not corpus.has_complete_expected_extent(item.document_id, trusted_object_id)
        ):
            continue
        if isinstance(gold.locator, ObjectLocator) and trusted_object_id != gold.locator.object_id:
            continue
        trusted_locator = _edge_locator(trusted_edge)
        if trusted_locator is not None:
            if isinstance(gold.locator, TextSpanLocator) and isinstance(trusted_locator, ObjectLocator):
                if _edge_extent(trusted_edge) != (gold.locator.start, gold.locator.end):
                    continue
            elif not _locator_covers(trusted_locator, gold.locator):
                continue
        elif isinstance(gold.locator, TextSpanLocator):
            if _edge_extent(trusted_edge) != (gold.locator.start, gold.locator.end):
                continue
        elif isinstance(gold.locator, PageRegionLocator):
            continue

        # A flattened item edge is only advisory.  If present, it must agree
        # with the independently resolved catalog edge; otherwise a swapped
        # object ID/locator in item metadata is a tampering attempt.
        if edge is not None:
            edge_object_id = edge.get("object_id")
            if edge_object_id is not None and edge_object_id != trusted_object_id:
                continue
            edge_locator = _edge_locator(edge)
            if edge_locator is not None and trusted_locator is not None and edge_locator != trusted_locator:
                continue
        if metadata_ids and trusted_object_id not in metadata_ids:
            continue
        return True
    return False


def _edge_for_gold(
    item: RAGEvidenceItem,
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    metadata = item.metadata or {}
    for key in ("canonical_objects", "provenance_edges", "edges"):
        values = metadata.get(key)
        if isinstance(values, list):
            candidates.extend(
                value for value in values if isinstance(value, Mapping)
            )
    # Adapter projections flatten one edge into these fields.
    flat_object_id = _metadata_object_id(metadata)
    if flat_object_id is not None:
        candidates.append(
            {
                "object_id": flat_object_id,
                "object_type": metadata.get("canonical_object_type"),
                "locator": metadata.get("canonical_locator"),
                "source_span": metadata.get("canonical_object_span"),
                "overlap_span": metadata.get("canonical_overlap_span"),
                "coverage": metadata.get("canonical_object_coverage")
                or metadata.get("coverage")
                or ("partial" if flat_object_id in metadata.get("canonical_partial_object_ids", []) else "full"),
                "expected_extent": metadata.get("expected_extent"),
            }
        )
    if isinstance(gold.locator, ObjectLocator):
        target_id = gold.locator.object_id
        for value in candidates:
            if value.get("object_id") == target_id:
                return dict(value)
        for value in corpus.edge_for_item(item, target_id):
            return dict(value)
    else:
        for value in candidates:
            locator = _edge_locator(value)
            if locator is not None and _locator_covers(locator, gold.locator):
                return dict(value)
        for object_id in corpus.object_ids_for_locator(gold.document_id, gold.locator):
            for value in corpus.edge_for_item(item, object_id):
                locator = _edge_locator(value)
                if locator is None or _locator_covers(locator, gold.locator):
                    return dict(value)
        # Text spans can be matched by expected extent even without a typed
        # public locator.
        if isinstance(gold.locator, TextSpanLocator):
            for value in candidates:
                extent = _edge_extent(value)
                if extent == (gold.locator.start, gold.locator.end):
                    return dict(value)
    return None


def _edge_covers_gold(
    edge: Mapping[str, Any],
    gold: GoldEvidence,
    item: RAGEvidenceItem,
    corpus: CorpusEvidenceIndex,
) -> bool:
    coverage_value = edge.get("coverage")
    if coverage_value is None:
        coverage_value = edge.get("canonical_object_coverage")
    # Full coverage is an explicit witness, never a default for a malformed
    # or truncated edge.
    coverage = str(coverage_value) if coverage_value is not None else ""
    if coverage != "full":
        return False
    locator = _edge_locator(edge)
    if locator is not None:
        if isinstance(gold.locator, ObjectLocator) and gold.locator.object_type == "table":
            return _table_item_is_complete(item, gold, corpus, edge, "formal")
        if isinstance(gold.locator, TextSpanLocator) and isinstance(locator, ObjectLocator):
            return _edge_extent(edge) == (gold.locator.start, gold.locator.end)
        return _locator_covers(locator, gold.locator)
    if isinstance(gold.locator, ObjectLocator):
        return edge.get("object_id") == gold.locator.object_id
    extent = _edge_extent(edge)
    return isinstance(gold.locator, TextSpanLocator) and extent == (
        gold.locator.start,
        gold.locator.end,
    )


def _table_item_is_complete(
    item: RAGEvidenceItem,
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
    edge: Mapping[str, Any] | None,
    integrity: str,
) -> bool:
    if edge is not None:
        coverage_value = edge.get("coverage")
        if coverage_value is None:
            coverage_value = edge.get("canonical_object_coverage")
        coverage = str(coverage_value) if coverage_value is not None else ""
        if coverage != "full":
            return False
        object_type = edge.get("object_type")
        if object_type is not None and str(object_type) not in {"table", "logical_table"}:
            return False
        # A full table edge is not enough: every required physical cell scope
        # must be present on the same runtime item.  This avoids treating one
        # cell (or a self-asserted ``coverage=full`` flag) as the whole table.
        target = gold.locator.object_id if isinstance(gold.locator, ObjectLocator) else None
        return bool(
            target
            and _table_scope_is_verified(item, gold.document_id, target, corpus, edge)
        )
    # Legacy direct locators have no hash proof.  Requiring the authored table
    # value/quote to be present prevents a one-cell item from standing in for a
    # whole table while keeping old complete-table fixtures working.
    expected = gold.quote_anchor or gold.canonical_value or ""
    if not expected.strip():
        return False
    return normalize_text(expected) in normalize_text(item.content)


def _gold_target_object_ids(
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
) -> set[str]:
    locator = gold.locator
    if isinstance(locator, ObjectLocator):
        return {locator.object_id}
    if isinstance(locator, TableCellLocator):
        return set(corpus.object_ids_for_locator(gold.document_id, locator))
    return set()


def _gold_expected_span(
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
) -> tuple[int, int] | None:
    """Resolve a single contiguous execution extent for a Gold locator."""

    locator = gold.locator
    if isinstance(locator, TextSpanLocator):
        return locator.start, locator.end
    target_ids = _gold_target_object_ids(gold, corpus)
    if len(target_ids) != 1:
        return None
    object_id = next(iter(target_ids))
    record = corpus.catalog_record(gold.document_id, object_id)
    if not isinstance(record, Mapping):
        return None
    ranges = _merge_ranges(_extent_ranges(record.get("expected_extent")))
    return ranges[0] if len(ranges) == 1 else None


def _partial_piece(
    item: RAGEvidenceItem,
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
) -> _PartialPiece | None:
    if item.document_id != gold.document_id:
        return None
    expected = _gold_expected_span(gold, corpus)
    if expected is None:
        return None
    expected_start, expected_end = expected
    observed = item.locator
    edge = _edge_for_gold(item, gold, corpus)
    if not isinstance(observed, TextSpanLocator):
        observed_span = _edge_overlap(edge)
    else:
        observed_span = (observed.start, observed.end)
    if observed_span is None:
        return None
    start, end = observed_span
    # Do not clip a malformed item into the Gold range.  The caller may only
    # union a piece wholly inside the expected object extent.
    if start < expected_start or end > expected_end or end <= start:
        return None
    integrity, _ = _metadata_integrity(item, corpus)
    if integrity != "formal":
        return None
    # Object and physical-cell partials need an independently trusted catalog
    # edge.  TextSpan Golds retain their authored coordinate as the source
    # identity, so the small legacy span fixture can still provide its own
    # explicit object ID/extent witness.
    if not isinstance(gold.locator, TextSpanLocator) and not corpus.has_provenance_catalog:
        return None
    if edge is None:
        return None
    coverage_value = edge.get("coverage") or edge.get("canonical_object_coverage")
    if coverage_value != "partial":
        return None
    target_ids = _gold_target_object_ids(gold, corpus)
    if not isinstance(gold.locator, TextSpanLocator):
        if len(target_ids) != 1:
            return None
        target_id = next(iter(target_ids))
        trusted_edges = tuple(
            value
            for value in corpus.edge_for_item(item, target_id)
            if (value.get("coverage") or value.get("canonical_object_coverage")) == "partial"
        )
        if not trusted_edges:
            return None
        # Do not let a flattened metadata edge override the independent
        # reverse edge's geometry or identity.
        if not any(
            _partial_edges_agree(edge, trusted)
            for trusted in trusted_edges
        ):
            return None
        edge = next(
            trusted
            for trusted in trusted_edges
            if _edge_overlap(trusted) in {None, (start, end)}
        ) if any(
            _edge_overlap(trusted) in {None, (start, end)}
            for trusted in trusted_edges
        ) else edge
    metadata = item.metadata or {}
    schema = metadata.get("provenance_schema")
    overlap = _span_from_metadata(metadata, "canonical_overlap_span", "overlap_span")
    if overlap is None:
        overlap = _edge_overlap(edge)
    if schema is not None:
        required = (
            _normalize_digest(_first_value(metadata, "source_sha256", "source_digest")),
            _normalize_digest(_first_value(metadata, "content_sha256", "trace_content_sha256")),
            overlap,
        )
        if required[0] is None or required[1] is None or required[2] != (start, end):
            return None
    else:
        # Range unions are never inferred from a naked typed locator.  A
        # runtime/source witness and explicit overlap are the minimum bridge.
        if overlap is not None and overlap != (start, end):
            return None
        if _span_from_metadata(metadata, "runtime_source_span", "source_span") is None:
            return None

    object_id = _metadata_object_id(metadata)
    if isinstance(edge.get("object_id"), str):
        edge_object_id = str(edge["object_id"])
        if target_ids and edge_object_id not in target_ids:
            return None
        object_id = edge_object_id
    if target_ids and object_id not in target_ids:
        return None
    if not isinstance(object_id, str) or not object_id:
        return None

    source = _runtime_source(corpus, gold.document_id)
    runtime_span = _span_from_metadata(metadata, "runtime_source_span", "source_span")
    if runtime_span is None:
        return None
    if not (runtime_span[0] <= start and end <= runtime_span[1]):
        return None
    if source is not None:
        if source[runtime_span[0] : runtime_span[1]] != item.content:
            return None
        offset_start = start - runtime_span[0]
        offset_end = end - runtime_span[0]
        if item.content[offset_start:offset_end] != source[start:end]:
            return None
    extent = _edge_extent(edge)
    if extent is not None and extent != (expected_start, expected_end):
        return None
    # A range has meaning only relative to one canonical source object.  Do
    # not infer that identity from the Gold coordinates or from equal text:
    # two objects can legitimately contain the same span/value.
    if not isinstance(object_id, str) or not object_id:
        return None
    coverage = {
        "start": start,
        "end": end,
        "object_id": object_id,
        "method": item.metadata.get("canonical_alignment_method")
        or (edge.get("alignment_method") if edge else None)
        or "verified_runtime_source_overlap",
    }
    return _PartialPiece(
        evidence_id=gold.evidence_id,
        item_id=item.item_id,
        rank=item.rank,
        start=start,
        end=end,
        object_id=object_id,
        coverage=coverage,
    )


def _table_scope_is_verified(
    item: RAGEvidenceItem,
    document_id: str,
    table_id: str,
    corpus: CorpusEvidenceIndex,
    table_edge: Mapping[str, Any] | None = None,
) -> bool:
    """Check a whole-table edge against the catalogued physical cells.

    The table object's own ``coverage`` flag is intentionally not used as a
    completeness proof.  The run-level catalog must enumerate the table's
    physical cells, and every one of those cell identities must round-trip to
    this same runtime chunk with an explicit full edge.  This also works for
    one runtime chunk projecting the table plus all of its cells.
    """

    if not corpus.has_provenance_catalog:
        return False
    # A table edge in metadata is not an independently trusted association;
    # require the catalog's table edge as well.  This rejects a swapped table
    # ID even when a caller supplies matching source/content hashes.
    if not any(
        _edge_is_full(edge)
        for edge in corpus.edge_for_item(item, table_id)
        if edge.get("object_id") == table_id
    ):
        return False
    if not corpus.has_complete_expected_extent(document_id, table_id):
        return False

    catalog_cells = list(corpus.table_cell_objects(document_id, table_id))
    if not catalog_cells:
        return False

    for object_id, record in catalog_cells:
        locator = _record_locator(record)
        if not corpus.has_complete_expected_extent(document_id, object_id):
            return False
        candidates = corpus.edge_for_item(item, object_id)
        if not candidates:
            return False
        if not any(
            _edge_is_full(candidate)
            and (
                locator is None
                or _edge_matches_locator(candidate, locator)
            )
            for candidate in candidates
        ):
            return False
    return True


def _complete_table_union(
    items: Sequence[RAGEvidenceItem],
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
) -> tuple[int, tuple[str, ...], tuple[dict[str, Any], ...]] | None:
    """Prove a whole-table Gold object from all physical-cell projections.

    This is deliberately stricter than accepting a table edge marked
    ``coverage=full``.  Every catalogued cell of the target table must have a
    verified full edge to one of the selected runtime items, with the typed
    cell locator agreeing on table/row/column.  The returned rank is the
    latest rank needed to complete the footprint, which is the same cutoff
    semantics used by a multi-piece text union.
    """

    locator = gold.locator
    if not isinstance(locator, ObjectLocator) or locator.object_type != "table":
        return None
    if not corpus.has_provenance_catalog:
        return None
    table_id = locator.object_id
    # A DOCX table envelope can legitimately be partial even though every
    # physical cell is independently and fully mapped (for example python-
    # docx's rendering of a vertically merged continuation).  The footprint
    # below is the authoritative whole-table proof, so require the table's
    # stable catalog identity here rather than its summary-envelope status.
    # This does *not* let a table edge alone prove completeness: every
    # catalogued physical cell still has to round-trip to a selected item.
    if not corpus.has_complete_table_footprint(gold.document_id, table_id):
        return None
    cells = corpus.table_cell_objects(gold.document_id, table_id)
    if not cells:
        return None

    selected_by_runtime: dict[str, list[RAGEvidenceItem]] = defaultdict(list)
    for item in items:
        # The reverse map authenticates a runtime identity, but the returned
        # trace must still authenticate the bytes it claims for that identity.
        # Without this check a caller could spoof a native chunk ID and borrow
        # its cell footprint.
        integrity, _ = _metadata_integrity(item, corpus)
        if integrity != "formal":
            continue
        runtime_id = _item_runtime_id(item)
        if runtime_id is not None:
            selected_by_runtime[runtime_id].append(item)

    used: dict[str, RAGEvidenceItem] = {}
    coverage: list[dict[str, Any]] = []
    for object_id, record in cells:
        if not corpus.has_complete_expected_extent(gold.document_id, object_id):
            return None
        cell_locator = _record_locator(record)
        candidates: list[RAGEvidenceItem] = []
        for item_values in selected_by_runtime.values():
            for item in item_values:
                if not corpus.edge_for_item(item, object_id):
                    continue
                if any(
                    _edge_is_full(edge)
                    and (cell_locator is None or _edge_matches_locator(edge, cell_locator))
                    for edge in corpus.edge_for_item(item, object_id)
                ):
                    candidates.append(item)
        if not candidates:
            return None
        chosen = min(candidates, key=lambda value: (value.rank, value.item_id))
        used[chosen.item_id] = chosen
        coverage.append(
            {
                "object_id": object_id,
                "locator": cell_locator.model_dump(mode="json")
                if cell_locator is not None
                else None,
                "method": "verified_physical_cell_scope",
            }
        )
    ordered = tuple(sorted(used.values(), key=lambda value: (value.rank, value.item_id)))
    return max(item.rank for item in ordered), tuple(item.item_id for item in ordered), tuple(coverage)


def _partial_table_footprint(
    items: Sequence[RAGEvidenceItem],
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
) -> tuple[int, tuple[str, ...], tuple[dict[str, Any], ...]] | None:
    """Return the verified subset of a whole-table physical-cell footprint.

    This intentionally shares the same global mapping prerequisite as a full
    table union.  A selected row can be called *partial* only after the system
    has proved which physical cells make up the complete table.  Otherwise it
    remains an unavailable provenance condition rather than a fabricated
    retrieval score.
    """

    locator = gold.locator
    if not isinstance(locator, ObjectLocator) or locator.object_type != "table":
        return None
    if not corpus.has_complete_table_footprint(gold.document_id, locator.object_id):
        return None

    selected_by_runtime: dict[str, list[RAGEvidenceItem]] = defaultdict(list)
    for item in items:
        integrity, _ = _metadata_integrity(item, corpus)
        if integrity != "formal":
            continue
        runtime_id = _item_runtime_id(item)
        if runtime_id is not None:
            selected_by_runtime[runtime_id].append(item)

    used: dict[str, RAGEvidenceItem] = {}
    coverage: list[dict[str, Any]] = []
    for object_id, record in corpus.table_cell_objects(
        gold.document_id, locator.object_id
    ):
        cell_locator = _record_locator(record)
        candidates: list[RAGEvidenceItem] = []
        for item_values in selected_by_runtime.values():
            for item in item_values:
                if any(
                    _edge_is_full(edge)
                    and (
                        cell_locator is None
                        or _edge_matches_locator(edge, cell_locator)
                    )
                    for edge in corpus.edge_for_item(item, object_id)
                ):
                    candidates.append(item)
        if not candidates:
            continue
        chosen = min(candidates, key=lambda value: (value.rank, value.item_id))
        used[chosen.item_id] = chosen
        coverage.append(
            {
                "object_id": object_id,
                "locator": cell_locator.model_dump(mode="json")
                if cell_locator is not None
                else None,
                "method": "verified_physical_cell_scope",
            }
        )

    if not used:
        return None
    ordered = tuple(sorted(used.values(), key=lambda value: (value.rank, value.item_id)))
    return max(item.rank for item in ordered), tuple(item.item_id for item in ordered), tuple(coverage)


def _edge_is_full(edge: Mapping[str, Any]) -> bool:
    value = edge.get("coverage")
    if value is None:
        value = edge.get("canonical_object_coverage")
    return value == "full"


def _edge_has_explicit_coverage(edge: Mapping[str, Any]) -> bool:
    value = edge.get("coverage")
    if value is None:
        value = edge.get("canonical_object_coverage")
    return value in {"full", "partial"}


def _edge_matches_locator(edge: Mapping[str, Any], locator: Any) -> bool:
    observed = _edge_locator(edge)
    if observed is not None:
        return observed == locator
    if isinstance(locator, TableCellLocator):
        return (
            edge.get("table_id") == locator.table_id
            and edge.get("row") == locator.row
            and edge.get("column") == locator.column
        )
    return False


def _partial_edges_agree(
    metadata_edge: Mapping[str, Any],
    trusted_edge: Mapping[str, Any],
) -> bool:
    """Compare the geometry a returned item claims with the catalog edge."""

    for key in ("object_id", "runtime_chunk_id", "coverage"):
        left, right = metadata_edge.get(key), trusted_edge.get(key)
        if left is not None and right is not None and left != right:
            return False
    left_locator, right_locator = _edge_locator(metadata_edge), _edge_locator(trusted_edge)
    if left_locator is not None and right_locator is not None and left_locator != right_locator:
        return False
    left_overlap, right_overlap = _edge_overlap(metadata_edge), _edge_overlap(trusted_edge)
    if left_overlap is not None and right_overlap is not None and left_overlap != right_overlap:
        return False
    return True


def _complete_partial_union(
    pieces: Sequence[_PartialPiece],
    gold: GoldEvidence,
    *,
    expected_span: tuple[int, int] | None = None,
) -> tuple[int, tuple[_PartialPiece, ...]] | None:
    if not pieces:
        return None
    if expected_span is None:
        if not isinstance(gold.locator, TextSpanLocator):
            return None
        expected_span = (gold.locator.start, gold.locator.end)
    # Every piece must refer to one source object.  Missing IDs are not
    # recoverable from equal coordinates or equal text; accepting them would
    # let two duplicate canonical objects form a fabricated union.
    object_ids = {piece.object_id for piece in pieces}
    if None in object_ids or len(object_ids) != 1:
        return None
    ordered = sorted(pieces, key=lambda value: (value.start, value.end, value.rank, value.item_id))
    expected_start, expected_end = expected_span
    cursor = expected_start
    used: list[_PartialPiece] = []
    for piece in ordered:
        if piece.start > cursor:
            return None
        if piece.end <= cursor:
            continue
        # A piece can overlap the previous one, but the union must be verified
        # as contiguous and every byte outside Gold was rejected earlier.
        if piece.start < cursor:
            if piece.end > cursor:
                used.append(piece)
                cursor = piece.end
            continue
        used.append(piece)
        cursor = piece.end
        if cursor >= expected_end:
            break
    if cursor < expected_end:
        return None
    if not used:
        return None
    return max(piece.rank for piece in used), tuple(
        sorted(used, key=lambda value: (value.rank, value.item_id))
    )


def _item_references_gold(
    item: RAGEvidenceItem,
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
) -> bool:
    if item.document_id != gold.document_id:
        return False
    expected = gold.locator
    # When a trusted run-level catalog knows which canonical objects a native
    # runtime chunk actually contains, a content-only item that names none of
    # the Gold object's identities is a determinate retrieval miss.  It is not
    # a provenance-unknown near miss merely because its rendered text happens
    # to equal the Gold value.  Keep the fallback below for an item whose
    # runtime identity is genuinely unmapped.
    known_runtime_objects = (
        set(corpus.object_ids_for_runtime(item))
        if corpus.has_provenance_catalog
        else set()
    )
    if known_runtime_objects:
        target_objects: set[str] = set()
        if isinstance(expected, ObjectLocator):
            target_objects.add(expected.object_id)
        elif isinstance(expected, TableCellLocator):
            target_objects.update(
                corpus.object_ids_for_locator(gold.document_id, expected)
            )
        else:
            # Text/page locators are resolved by their typed edge or expected
            # extent below.  A chunk with known objects but no target edge is
            # still a concrete non-Gold object, not an unknown item.
            if _edge_for_gold(item, gold, corpus) is None:
                return False
        if (
            target_objects
            and not target_objects.intersection(known_runtime_objects)
            and any(
                _runtime_chunk_excludes_object(item, object_id, corpus)
                for object_id in target_objects
            )
        ):
            return False
    if isinstance(expected, ObjectLocator):
        if item.locator is not None:
            return (
                isinstance(item.locator, ObjectLocator)
                and item.locator.object_type == expected.object_type
                and item.locator.object_id == expected.object_id
            )
        if corpus.edge_for_item(item, expected.object_id):
            return True
        metadata_ids = _metadata_object_ids(item.metadata)
        if expected.object_id in metadata_ids:
            return True
    elif isinstance(expected, TableCellLocator):
        if item.locator is not None:
            return isinstance(item.locator, TableCellLocator) and item.locator == expected
        edge = _edge_for_gold(item, gold, corpus)
        if edge is not None:
            return True
    else:
        if item.locator is not None and not isinstance(item.locator, type(expected)):
            return False
        edge = _edge_for_gold(item, gold, corpus)
        if edge is not None:
            return True
        if isinstance(item.locator, TextSpanLocator) and isinstance(expected, TextSpanLocator):
            return bool(
                item.locator.start < expected.end and expected.start < item.locator.end
            )
    # An explicit missing-provenance item often retains only the rendered
    # value.  Use Gold's own witness for diagnostics, never as an exact hit.
    if item.locator is not None:
        return False
    needles = [gold.quote_anchor, gold.canonical_value]
    normalized_content = normalize_text(item.content)
    return any(
        isinstance(needle, str)
        and needle.strip()
        and normalize_text(needle) in normalized_content
        for needle in needles
    )


def _runtime_chunk_excludes_object(
    item: RAGEvidenceItem,
    object_id: str,
    corpus: CorpusEvidenceIndex,
) -> bool:
    """Prove a mapped chunk is outside one object's source extent.

    Merely observing another canonical object on a chunk is not enough: a
    partial attribution may leave the target region unmapped.  Exclusion is
    therefore allowed only when the run-level runtime record has an explicit,
    verified source span that exactly agrees with the item and that span is
    disjoint from the target object's complete expected extent.
    """

    if not corpus.has_provenance_catalog:
        return False
    runtime_id = _item_runtime_id(item)
    if runtime_id is None:
        return False
    runtime = corpus.runtime_chunks.get(runtime_id)
    if not isinstance(runtime, Mapping):
        return False
    runtime_span = _span_from_metadata(item.metadata, "runtime_source_span", "source_span")
    map_span = _span_from_mapping(runtime.get("source_span"))
    if runtime_span is None:
        runtime_span = map_span
    # If a caller supplies a span, it must agree with the pinned runtime
    # record.  A self-claimed, alternate coordinate is not exclusion proof.
    if map_span is None or runtime_span != map_span:
        return False
    span_status = runtime.get("source_span_status") or runtime.get("source_span_verification")
    if span_status not in {"verified", "complete", "full"}:
        return False
    # A verified envelope span says where the returned chunk came from; it
    # does not by itself say that every part of that chunk was attributed to
    # canonical objects.  A partial B-object projection must therefore remain
    # unknown for an absent A object when the chunk has an unattributed
    # region.  Production bridges publish ``provenance_status=full`` (or the
    # more explicit ``attribution_status``); missing/partial status is not an
    # absence proof.
    attribution_status = runtime.get("attribution_status") or runtime.get(
        "provenance_status"
    )
    if attribution_status not in {"verified", "complete", "full"}:
        return False
    expected = corpus.catalog_record(item.document_id, object_id)
    if not isinstance(expected, Mapping):
        return False
    if not corpus.has_complete_expected_extent(item.document_id, object_id):
        return False
    ranges = _extent_ranges(expected.get("expected_extent"))
    if not ranges:
        return False
    return all(not _ranges_overlap(runtime_span, value) for value in ranges)


def _provenance_reason(item: RAGEvidenceItem) -> str | None:
    metadata = item.metadata or {}
    reason = metadata.get("provenance_reason") or metadata.get("reason")
    return reason if isinstance(reason, str) and reason.strip() else None


def _miss_reason(
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
    items: Sequence[RAGEvidenceItem],
) -> str | None:
    object_ids: tuple[str, ...] = ()
    if isinstance(gold.locator, ObjectLocator):
        if corpus.has_verified_object(gold.document_id, gold.locator.object_id):
            object_ids = (gold.locator.object_id,)
    else:
        # TableCellLocator has no canonical object_id.  Resolve it through the
        # global object catalog, then apply the same reverse-index proof.
        object_ids = corpus.object_ids_for_locator(gold.document_id, gold.locator)
    returned = {_item_runtime_id(item) for item in items}
    for object_id in object_ids:
        if corpus.prove_true_miss(gold.document_id, object_id, returned):
            return "verified canonical object runtime chunks are absent from this stage"
    return None


def _paths(evidence_set: GoldEvidenceSet) -> list[list[list[str]]]:
    return evidence_set.mses_paths or [evidence_set.required_groups]


def _items_at_cutoff(
    items: Sequence[RAGEvidenceItem], cutoff: int | None
) -> list[RAGEvidenceItem]:
    if cutoff is None:
        return sorted(items, key=lambda value: (value.rank, value.item_id))
    return sorted(
        (item for item in items if item.rank <= cutoff),
        key=lambda value: (value.rank, value.item_id),
    )


def _missing_localization(evidence_id: str) -> GoldLocalization:
    return GoldLocalization(evidence_id=evidence_id, status=LocalizationStatus.RETRIEVAL_MISSED)


def _metadata_object_id(metadata: Mapping[str, Any]) -> str | None:
    value = metadata.get("canonical_object_id")
    if isinstance(value, str) and value:
        return value
    values = metadata.get("canonical_object_ids")
    if isinstance(values, list) and len(values) == 1 and isinstance(values[0], str):
        return values[0]
    return None


def _metadata_object_ids(metadata: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    one = metadata.get("canonical_object_id")
    if isinstance(one, str) and one:
        values.add(one)
    many = metadata.get("canonical_object_ids")
    if isinstance(many, list):
        values.update(str(value) for value in many if isinstance(value, str) and value)
    return values


def _item_runtime_id(item: RAGEvidenceItem) -> str | None:
    if isinstance(item.native_id, str) and item.native_id:
        return item.native_id
    value = item.metadata.get("runtime_chunk_id")
    return value if isinstance(value, str) and value else None


def _object_ids_from_entries(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        result: list[str] = []
        for hinted_id, item in value.items():
            if isinstance(hinted_id, str) and hinted_id:
                result.append(hinted_id)
            if isinstance(item, Mapping):
                object_id = item.get("object_id") or item.get("canonical_object_id")
                if isinstance(object_id, str) and object_id:
                    result.append(object_id)
        return list(dict.fromkeys(result))
    if not isinstance(value, (list, tuple)):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            object_id = item.get("object_id") or item.get("canonical_object_id")
            if isinstance(object_id, str) and object_id:
                result.append(object_id)
        elif isinstance(item, str) and item:
            result.append(item)
    return result


def _forward_entries_for_object(
    object_id: str, *values: Any
) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    for value in values:
        if isinstance(value, Mapping):
            for hinted_id, entry in value.items():
                if isinstance(entry, Mapping):
                    candidate = entry
                    candidate_id = candidate.get("object_id") or candidate.get("canonical_object_id") or hinted_id
                    if candidate_id == object_id:
                        result.append(candidate)
                elif hinted_id == object_id:
                    result.append({"object_id": object_id})
        elif isinstance(value, (list, tuple)):
            for entry in value:
                if isinstance(entry, Mapping):
                    candidate_id = entry.get("object_id") or entry.get("canonical_object_id")
                    if candidate_id == object_id:
                        result.append(entry)
                elif entry == object_id:
                    result.append({"object_id": object_id})
    return result


def _forward_entries_for_all_objects(*values: Any) -> list[Mapping[str, Any]]:
    """Normalize every runtime projection entry for round-trip validation."""

    result: list[Mapping[str, Any]] = []
    for value in values:
        if isinstance(value, Mapping):
            explicit = value.get("object_id") or value.get("canonical_object_id")
            if isinstance(explicit, str) and explicit:
                result.append(value)
                continue
            for hinted_id, entry in value.items():
                if isinstance(entry, Mapping):
                    candidate = dict(entry)
                    object_id = candidate.get("object_id") or candidate.get(
                        "canonical_object_id"
                    ) or (hinted_id if isinstance(hinted_id, str) else None)
                    if isinstance(object_id, str) and object_id:
                        candidate.setdefault("object_id", object_id)
                        result.append(candidate)
                elif isinstance(hinted_id, str) and hinted_id:
                    result.append({"object_id": hinted_id})
        elif isinstance(value, (list, tuple)):
            for entry in value:
                if isinstance(entry, Mapping):
                    object_id = entry.get("object_id") or entry.get(
                        "canonical_object_id"
                    )
                    if isinstance(object_id, str) and object_id:
                        result.append(entry)
                elif isinstance(entry, str) and entry:
                    result.append({"object_id": entry})
    return result


def _edge_round_trip_consistent(
    reverse: Mapping[str, Any], forward: Mapping[str, Any]
) -> bool:
    """Compare identity-bearing forward/reverse edge fields exactly."""

    if reverse.get("object_id") != forward.get("object_id"):
        return False
    for key in ("coverage", "object_type", "source_sha256", "witness_sha256"):
        left, right = reverse.get(key), forward.get(key)
        if left is not None and right is not None and left != right:
            return False
    for key in ("overlap_span", "overlap", "ranges", "expected_extent"):
        left, right = _edge_range_value(reverse, key), _edge_range_value(forward, key)
        if left is not None and right is not None and left != right:
            return False
    left_locator, right_locator = _edge_locator(reverse), _edge_locator(forward)
    if left_locator is not None and right_locator is not None and left_locator != right_locator:
        return False
    return True


def _catalog_edge_consistent(
    reverse: Mapping[str, Any],
    forward: Mapping[str, Any],
    catalog: Mapping[str, Any] | None,
) -> bool:
    """Ensure an edge agrees with the independently pinned object catalog.

    Forward and reverse copies can be tampered together, so their agreement
    alone is insufficient.  When a catalog record is present, its stable ID,
    document, type, typed locator and expected extent are the third identity
    witness.  Compact maps without a catalog record remain loadable for
    diagnostics but cannot become a trusted formal catalog (the extent check
    later fails closed).
    """

    if not isinstance(catalog, Mapping):
        return False
    object_id = catalog.get("object_id") or catalog.get("canonical_object_id")
    if object_id is not None and object_id != reverse.get("object_id"):
        return False
    for value in (reverse, forward):
        value_id = value.get("object_id") or value.get("canonical_object_id")
        if value_id is not None and object_id is not None and value_id != object_id:
            return False
    catalog_document = catalog.get("document_id")
    if isinstance(catalog_document, str) and catalog_document:
        for value in (reverse, forward):
            edge_document = value.get("document_id")
            if edge_document is not None and edge_document != catalog_document:
                return False
    catalog_type = catalog.get("object_type")
    if catalog_type is not None:
        for value in (reverse, forward):
            edge_type = value.get("object_type")
            if edge_type is not None and edge_type != catalog_type:
                return False
    catalog_locator = _record_locator(catalog)
    if catalog_locator is not None:
        for value in (reverse, forward):
            edge_locator = _edge_locator(value)
            if edge_locator is not None and edge_locator != catalog_locator:
                return False
    catalog_extent = _edge_range_value(catalog, "expected_extent")
    if catalog_extent is not None:
        for value in (reverse, forward):
            edge_extent = _edge_range_value(value, "expected_extent")
            if edge_extent is not None and edge_extent != catalog_extent:
                return False
    for key in ("source_sha256", "witness_sha256"):
        expected = _normalize_digest(catalog.get(key))
        if expected is None:
            # The historical serializer stores source/witness hashes nested in
            # the expected extent or structure record; these are still used
            # when present, but absence is not itself a mismatch.
            continue
        for value in (reverse, forward):
            observed = _normalize_digest(value.get(key))
            if observed is not None and observed != expected:
                return False
    return True


def _edge_range_value(edge: Mapping[str, Any], key: str) -> Any:
    value = edge.get(key)
    if value is None:
        return None
    span = _span_from_mapping(value)
    if span is not None:
        return span
    if isinstance(value, Mapping) and isinstance(value.get("ranges"), list):
        ranges = tuple(
            parsed
            for parsed in (_span_from_mapping(item) for item in value["ranges"])
            if parsed is not None
        )
        return ranges if len(ranges) == len(value["ranges"]) else None
    if isinstance(value, (list, tuple)):
        ranges = tuple(
            parsed
            for parsed in (_span_from_mapping(item) for item in value)
            if parsed is not None
        )
        return ranges if len(ranges) == len(value) else None
    return value


def _normalize_edge(value: Any, *, object_id: str | None = None) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    runtime = value.get("runtime_chunk_id") or value.get("chunk_id") or value.get("runtime_id")
    if not isinstance(runtime, str) or not runtime:
        return None
    resolved_object = value.get("object_id") or value.get("canonical_object_id") or object_id
    if not isinstance(resolved_object, str) or not resolved_object:
        return None
    result = dict(value)
    result["runtime_chunk_id"] = runtime
    result["object_id"] = resolved_object
    coverage = value.get("coverage") or value.get("canonical_object_coverage")
    if coverage is not None:
        if coverage not in {"full", "partial"}:
            return None
        result["coverage"] = coverage
    mapping_status = value.get("mapping_status")
    if mapping_status is not None:
        if mapping_status not in {
            "mapped",
            "partial",
            "unmapped",
            "complete",
            "verified",
            "missing",
        }:
            return None
        # An unmapped reverse edge is a diagnostic record, not a source
        # object-to-runtime witness.  Retaining it as an evidence edge would
        # let a malformed map prove a false retrieval miss.
        if mapping_status in {"unmapped", "missing"}:
            return None
    for key in ("overlap_span", "overlap", "ranges"):
        if key in value:
            raw_span = value.get(key)
            span = _span_from_mapping(raw_span)
            if span is not None:
                result["overlap_span"] = {"start": span[0], "end": span[1]}
                break
            ranges = _range_list(raw_span)
            if ranges is None and raw_span is not None:
                return None
            if ranges:
                result["ranges"] = [
                    {"start": start, "end": end} for start, end in ranges
                ]
                if len(ranges) == 1:
                    result["overlap_span"] = {
                        "start": ranges[0][0],
                        "end": ranges[0][1],
                    }
                break
    document = value.get("document_id")
    if document is not None and not isinstance(document, str):
        return None
    for key in ("source_sha256", "source_digest", "witness_sha256", "canonical_witness_sha256"):
        if key in value and value.get(key) is not None and _normalize_digest(value.get(key)) is None:
            return None
    if "expected_extent" in value and value.get("expected_extent") is not None:
        if not _extent_mapping_valid(value.get("expected_extent")):
            return None
    return result


def _unique_edges(values: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for value in values:
        key = (
            value.get("object_id"),
            value.get("runtime_chunk_id"),
            value.get("coverage"),
            str(value.get("overlap_span")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(value))
    return result


def _edge_locator(edge: Mapping[str, Any] | None) -> Any | None:
    if not isinstance(edge, Mapping):
        return None
    value = edge.get("locator") or edge.get("typed_locator")
    if not isinstance(value, Mapping):
        return None
    try:
        kind = value.get("type")
        if kind == "object":
            return ObjectLocator.model_validate(value)
        if kind == "table_cell":
            return TableCellLocator.model_validate(value)
        if kind == "text_span":
            return TextSpanLocator.model_validate(value)
        if kind == "page_region":
            return PageRegionLocator.model_validate(value)
    except (TypeError, ValueError):
        return None
    return None


def _record_locator(record: Mapping[str, Any]) -> Any | None:
    """Parse a catalog object record's typed locator when available."""

    value = record.get("locator") or record.get("typed_locator")
    if isinstance(value, Mapping):
        parsed = _edge_locator({"locator": value})
        if parsed is not None:
            return parsed
    if str(record.get("object_type", "")) in {"cell", "table_cell"}:
        table_id = record.get("table_id")
        row = record.get("row")
        column = record.get("column")
        if (
            isinstance(table_id, str)
            and isinstance(row, (int, str))
            and not isinstance(row, bool)
            and isinstance(column, (int, str))
            and not isinstance(column, bool)
        ):
            try:
                return TableCellLocator(table_id=table_id, row=row, column=column)
            except (TypeError, ValueError):
                return None
    return None


def _catalog_record_is_well_formed(record: Mapping[str, Any]) -> bool:
    """Validate identity-bearing catalog fields without inferring coverage."""

    object_id = record.get("object_id") or record.get("canonical_object_id")
    if not isinstance(object_id, str) or not object_id:
        return False
    document_id = record.get("document_id")
    if document_id is not None and (
        not isinstance(document_id, str) or not document_id
    ):
        return False
    locator_value = record.get("locator") or record.get("typed_locator")
    if locator_value is not None and _record_locator(record) is None:
        return False
    expected = record.get("expected_extent")
    if expected is not None and not _catalog_extent_is_well_formed(expected):
        return False
    status = record.get("mapping_status") or record.get("status")
    if status is not None and status not in {
        "mapped",
        "partial",
        "unmapped",
        "complete",
        "verified",
        "missing",
        "ambiguous",
    }:
        return False
    object_type = record.get("object_type")
    return object_type is None or isinstance(object_type, str)


def _catalog_extent_is_well_formed(value: Any) -> bool:
    """Validate complete *and* explicitly unresolved structural extents.

    The object catalog is a corpus inventory, so an object whose extent is
    known to be unresolved must remain present for diagnostics and whole-table
    completeness checks.  It is not a complete witness: ``has_complete...``
    below still requires a complete/mapped status and a non-empty extent.
    """

    if _extent_mapping_valid(value):
        return True
    if not isinstance(value, Mapping):
        return False
    status = value.get("status")
    if status not in {"missing", "partial", "unmapped", "ambiguous", "unavailable"}:
        return False
    if "ranges" in value:
        return _range_list(value.get("ranges")) is not None
    body_ordinal = value.get("body_ordinal")
    if isinstance(body_ordinal, int) and not isinstance(body_ordinal, bool):
        return body_ordinal >= 0
    table_id = value.get("table_id")
    if isinstance(table_id, str) and table_id:
        return True
    return bool(value.get("reason") or value.get("object_id") or value.get("locator"))


def _locator_key(locator: Any | None) -> str | None:
    """Stable key for the construction-time typed-locator index."""

    if locator is None or not hasattr(locator, "model_dump"):
        return None
    try:
        return json.dumps(
            locator.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        return None


def _edge_overlap(edge: Mapping[str, Any] | None) -> tuple[int, int] | None:
    if not isinstance(edge, Mapping):
        return None
    value = edge.get("overlap_span") or edge.get("overlap") or edge.get("ranges")
    span = _span_from_mapping(value)
    if span is not None:
        return span
    ranges = _range_list(value)
    if not ranges:
        return None
    merged = _merge_ranges(ranges)
    return merged[0] if len(merged) == 1 else None


def _edge_extent(edge: Mapping[str, Any] | None) -> tuple[int, int] | None:
    if not isinstance(edge, Mapping):
        return None
    for key in ("expected_extent", "canonical_object_span", "source_span", "object_span"):
        value = edge.get(key)
        if isinstance(value, Mapping) and isinstance(value.get("start"), int) and isinstance(value.get("end"), int):
            return int(value["start"]), int(value["end"])
        span = _span_from_mapping(value)
        if span is not None:
            return span
        if isinstance(value, Mapping):
            ranges = _range_list(value.get("ranges"))
            if ranges:
                merged = _merge_ranges(ranges)
                if len(merged) == 1:
                    return merged[0]
    return None


def _extent_ranges(value: Any) -> tuple[tuple[int, int], ...]:
    """Read a complete expected extent's execution-stream ranges."""

    if not isinstance(value, Mapping):
        return ()
    ranges = _range_list(value.get("ranges"))
    if ranges:
        return tuple(ranges)
    span = _span_from_mapping(value)
    return (span,) if span is not None else ()


def _ranges_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def _span_from_metadata(metadata: Mapping[str, Any], *keys: str) -> tuple[int, int] | None:
    for key in keys:
        if key in metadata:
            return _span_from_mapping(metadata.get(key))
    return None


def _span_from_mapping(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, Mapping):
        return None
    start, end = value.get("start"), value.get("end")
    if isinstance(start, bool) or isinstance(end, bool):
        return None
    if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
        return None
    return start, end


def _extent_mapping_valid(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    span = _span_from_mapping(value)
    if span is not None:
        return True
    ranges = _range_list(value.get("ranges"))
    if ranges is not None and bool(ranges):
        return True
    # Some production bridges preserve structural source coordinates instead
    # of a rendered execution interval.  These are identity/whole-object
    # witnesses only; partial text unions still require explicit ranges.
    status = value.get("status")
    status_valid = status in {"complete", "verified", "mapped"}
    body_ordinal = value.get("body_ordinal")
    if isinstance(body_ordinal, int) and not isinstance(body_ordinal, bool):
        return body_ordinal >= 0 and status_valid
    table_id = value.get("table_id")
    if isinstance(table_id, str) and table_id:
        row, column = value.get("row"), value.get("column")
        if (
            (isinstance(row, (int, str)) and not isinstance(row, bool))
            and (isinstance(column, (int, str)) and not isinstance(column, bool))
        ):
            return status_valid
        physical = (
            value.get("physical_cell_ids")
            or value.get("cell_ids")
            or value.get("cells")
        )
        # A table-level extent is meaningful only when it identifies a
        # physical-cell footprint (the scorer still checks those cells one by
        # one before declaring a whole-table match).
        if isinstance(physical, (list, tuple, set)) and bool(physical):
            return status_valid
        # A table object may be checked through its separately catalogued
        # physical cells; retaining its typed table identity is enough for
        # the catalog record, but not for a match by itself.
        return status_valid
    # Object extents may be row/cell scopes rather than text intervals.  They
    # still need a non-empty, typed structure; no text union is inferred from
    # them.
    if value.get("object_id") or value.get("locator"):
        return status_valid
    return False


def _range_list(value: Any) -> list[tuple[int, int]] | None:
    if not isinstance(value, (list, tuple)):
        return None
    result: list[tuple[int, int]] = []
    for item in value:
        span = _span_from_mapping(item)
        if span is None:
            return None
        result.append(span)
    return result


def _merge_ranges(values: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or directly adjacent half-open ranges."""

    ordered = sorted(
        (int(start), int(end))
        for start, end in values
        if isinstance(start, int)
        and isinstance(end, int)
        and not isinstance(start, bool)
        and not isinstance(end, bool)
        and start >= 0
        and end > start
    )
    if not ordered:
        return []
    merged: list[list[int]] = [[ordered[0][0], ordered[0][1]]]
    for start, end in ordered[1:]:
        previous = merged[-1]
        if start <= previous[1]:
            previous[1] = max(previous[1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _normalize_digest(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.removeprefix("sha256:")
    return value if _HEX64.fullmatch(value) else None


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mapping_digest(value: Mapping[str, Any]) -> str:
    """Return the canonical digest used for an externally pinned map."""

    # Digest fields are metadata about the payload, not part of its content;
    # excluding them avoids a self-referential hash and makes the pin stable
    # across transport wrappers.
    filtered = {
        key: item
        for key, item in value.items()
        if key
        not in {
            "map_digest",
            "provenance_map_digest",
            "canonical_provenance_map_digest",
        }
    }
    encoded = json.dumps(
        filtered,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _runtime_source(corpus: CorpusEvidenceIndex, document_id: str) -> str | None:
    """Resolve formal span coordinates without mixing source coordinate views."""

    if corpus.runtime_documents:
        return corpus.runtime_documents.get(document_id)
    # Legacy/unit fixtures predate the explicit runtime-stream argument and
    # use their only corpus text as the execution view.  Formal ingestion with
    # a canonical JSONL source should always pass ``runtime_documents``.
    return corpus.documents.get(document_id)


def _first_value(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _records_by_id(value: Any, id_key: str) -> dict[str, Mapping[str, Any]]:
    """Normalize list and mapping transport forms without guessing IDs."""

    if isinstance(value, Mapping):
        return {
            str(key): item
            for key, item in value.items()
            if isinstance(item, Mapping)
        }
    if isinstance(value, (list, tuple)):
        result: dict[str, Mapping[str, Any]] = {}
        for item in value:
            if not isinstance(item, Mapping):
                continue
            identifier = item.get(id_key)
            if isinstance(identifier, str) and identifier:
                result[identifier] = item
        return result
    return {}
