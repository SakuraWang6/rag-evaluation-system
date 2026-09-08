"""Cutoff-bound ranking metrics over localized prefix proofs."""

from __future__ import annotations

from rag_eval.contracts.dataset import GoldEvidenceSet
from rag_eval.evaluation.unified.proofs import EPSILON, StageProof, paths


def complete_mrr_bounds(
    prefixes: dict[int, StageProof], cutoff: int
) -> tuple[float, float, str | None]:
    possible_ranks: list[int] = []
    proved_rank: int | None = None
    for rank in range(1, cutoff + 1):
        proof = prefixes[rank].public
        if proof.complete_recall_upper >= 1 - EPSILON:
            possible_ranks.append(rank)
        if proof.complete_recall_lower >= 1 - EPSILON:
            proved_rank = rank
            break
    if proved_rank is not None:
        earliest_possible = min(possible_ranks, default=proved_rank)
        if earliest_possible == proved_rank:
            value = 1 / proved_rank
            return value, value, None
        return (
            1 / proved_rank,
            1 / earliest_possible,
            "an earlier unknown item could complete the Gold path",
        )
    last = prefixes[cutoff].public
    if last.complete_recall_upper < 1 - EPSILON:
        return 0.0, 0.0, None
    earliest_possible = min(possible_ranks, default=1)
    return (
        0.0,
        1 / earliest_possible,
        "unknown provenance could complete the Gold path within the MRR cutoff",
    )


def first_fragment_mrr_bounds(
    gold: GoldEvidenceSet,
    prefixes: dict[int, StageProof],
    cutoff: int,
) -> tuple[float, float, str | None]:
    required = {
        evidence_id
        for path in paths(gold)
        for clause in path
        for evidence_id in clause
    }
    possible_ranks: list[int] = []
    proved_rank: int | None = None
    for rank in range(1, cutoff + 1):
        proofs = tuple(
            value
            for evidence_id, value in prefixes[rank].evidence.items()
            if evidence_id in required
        )
        if any(value.upper > EPSILON for value in proofs):
            possible_ranks.append(rank)
        if any(value.lower > EPSILON for value in proofs):
            proved_rank = rank
            break
    if proved_rank is not None:
        earliest_possible = min(possible_ranks, default=proved_rank)
        if earliest_possible == proved_rank:
            value = 1 / proved_rank
            return value, value, None
        return (
            1 / proved_rank,
            1 / earliest_possible,
            "an earlier unknown item could contain the first Gold fragment",
        )
    if not possible_ranks:
        return 0.0, 0.0, None
    return (
        0.0,
        1 / min(possible_ranks),
        "unknown provenance could contain a Gold fragment within the cutoff",
    )
