"""Provenance-first Gold Evidence matching."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from rag_eval.contracts.adapter import RAGEvidenceItem
from rag_eval.contracts.dataset import (
    GoldEvidence,
    ObjectLocator,
    PageRegionLocator,
    TableCellLocator,
    TextSpanLocator,
)
from rag_eval.evaluation.answers import normalize_text

EVIDENCE_SCORER_ID = "provenance-evidence-groups"
EVIDENCE_SCORER_VERSION = "1.0"
EVIDENCE_SCORER_DIGEST = "sha256:" + hashlib.sha256(
    b"provenance-evidence-v1:locator:document-unique-quote:corpus-unique-quote"
).hexdigest()


class EvidenceMatchKind(StrEnum):
    EXACT_PROVENANCE = "exact_provenance"
    SAME_DOCUMENT_UNIQUE_QUOTE = "same_document_unique_quote"
    CORPUS_UNIQUE_QUOTE = "corpus_unique_quote"


@dataclass(frozen=True, slots=True)
class EvidenceMatch:
    evidence_id: str
    item_id: str
    rank: int
    kind: EvidenceMatchKind


class CorpusEvidenceIndex:
    def __init__(self, documents: dict[str, str]) -> None:
        self.documents = dict(documents)

    def quote_counts(self, quote: str) -> tuple[dict[str, int], int]:
        normalized_quote = normalize_text(quote)
        counts = {
            document_id: normalize_text(content).count(normalized_quote)
            for document_id, content in self.documents.items()
        }
        return counts, sum(counts.values())


def match_evidence(
    item: RAGEvidenceItem,
    gold: GoldEvidence,
    corpus: CorpusEvidenceIndex,
) -> EvidenceMatch | None:
    if item.document_id == gold.document_id and _locator_covers(item, gold):
        return EvidenceMatch(
            evidence_id=gold.evidence_id,
            item_id=item.item_id,
            rank=item.rank,
            kind=EvidenceMatchKind.EXACT_PROVENANCE,
        )

    quote = (gold.quote_anchor or "").strip()
    if not quote or normalize_text(quote) not in normalize_text(item.content):
        return None
    counts, corpus_count = corpus.quote_counts(quote)
    if item.document_id == gold.document_id and counts.get(gold.document_id) == 1:
        return EvidenceMatch(
            evidence_id=gold.evidence_id,
            item_id=item.item_id,
            rank=item.rank,
            kind=EvidenceMatchKind.SAME_DOCUMENT_UNIQUE_QUOTE,
        )
    if item.document_id is None and corpus_count == 1:
        return EvidenceMatch(
            evidence_id=gold.evidence_id,
            item_id=item.item_id,
            rank=item.rank,
            kind=EvidenceMatchKind.CORPUS_UNIQUE_QUOTE,
        )
    return None


def _locator_covers(item: RAGEvidenceItem, gold: GoldEvidence) -> bool:
    observed = item.locator
    expected = gold.locator
    if observed is None or type(observed) is not type(expected):
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


def match_all(
    items: list[RAGEvidenceItem],
    evidence: list[GoldEvidence],
    corpus: CorpusEvidenceIndex,
) -> dict[str, EvidenceMatch]:
    by_id = {item.evidence_id: item for item in evidence}
    matches: dict[str, EvidenceMatch] = {}
    for evidence_id, gold in by_id.items():
        candidates = [
            match
            for item in items
            if (match := match_evidence(item, gold, corpus)) is not None
        ]
        if candidates:
            matches[evidence_id] = min(candidates, key=lambda match: match.rank)
    return matches


def unique_quote_diagnostics(evidence: list[GoldEvidence]) -> dict[str, int]:
    quotes = Counter(normalize_text(item.quote_anchor or "") for item in evidence)
    return {quote: count for quote, count in quotes.items() if quote and count > 1}
