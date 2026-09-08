"""Verified canonical-extent union and set-difference operations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from rag_eval.contracts.canonical import canonical_json
from rag_eval.contracts.observation import (
    CanonicalExtent,
    ExtentUnit,
    PhysicalCellFootprint,
    ProvenanceEdge,
)

UnitKey = tuple[str, str, str]


def _key(unit: ExtentUnit) -> UnitKey:
    return (unit.unit_id, unit.coordinate_system, canonical_json(unit.coordinates))


def _merge(intervals: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    result: list[list[int]] = []
    for start, end in sorted(intervals):
        if not result or start > result[-1][1]:
            result.append([start, end])
        else:
            result[-1][1] = max(result[-1][1], end)
    return tuple((start, end) for start, end in result)


def _interval_measure(intervals: Iterable[tuple[int, int]]) -> int:
    return sum(end - start for start, end in _merge(intervals))


def _interval_difference_measure(
    left: Iterable[tuple[int, int]], right: Iterable[tuple[int, int]]
) -> int:
    remaining = list(_merge(left))
    for cut_start, cut_end in _merge(right):
        next_remaining: list[tuple[int, int]] = []
        for start, end in remaining:
            if cut_end <= start or cut_start >= end:
                next_remaining.append((start, end))
                continue
            if start < cut_start:
                next_remaining.append((start, cut_start))
            if cut_end < end:
                next_remaining.append((cut_end, end))
        remaining = next_remaining
    return _interval_measure(remaining)


@dataclass(frozen=True, slots=True)
class ExtentCoverage:
    """A normalized union over one expected Canonical extent."""

    expected: CanonicalExtent
    mode: str
    intervals: dict[UnitKey, tuple[tuple[int, int], ...]]
    expected_intervals: dict[UnitKey, tuple[int, int]]
    covered_atoms: frozenset[str]
    expected_atoms: frozenset[str]

    @property
    def fraction(self) -> float:
        if self.mode == "range":
            denominator = sum(
                end - start for start, end in self.expected_intervals.values()
            )
            numerator = sum(_interval_measure(value) for value in self.intervals.values())
            return numerator / denominator if denominator else 0.0
        denominator = len(self.expected_atoms)
        return len(self.covered_atoms) / denominator if denominator else 0.0

    def difference_fraction(self, other: ExtentCoverage) -> float:
        self._require_compatible(other)
        if self.mode == "range":
            denominator = sum(
                end - start for start, end in self.expected_intervals.values()
            )
            lost = sum(
                _interval_difference_measure(
                    self.intervals.get(key, ()), other.intervals.get(key, ())
                )
                for key in self.expected_intervals
            )
            return lost / denominator if denominator else 0.0
        denominator = len(self.expected_atoms)
        return (
            len(self.covered_atoms - other.covered_atoms) / denominator
            if denominator
            else 0.0
        )

    def _require_compatible(self, other: ExtentCoverage) -> None:
        if self.expected.extent_digest != other.expected.extent_digest:
            raise ValueError("canonical extent deltas require the same expected extent")


def extent_coverage(
    expected: CanonicalExtent,
    edges: Iterable[ProvenanceEdge],
    *,
    all_object_edges: Iterable[ProvenanceEdge],
) -> ExtentCoverage:
    """Union verified edges; merged table cells remain one logical atom."""

    selected = tuple(edges)
    all_edges = tuple(all_object_edges)
    if all(unit.start is not None for unit in expected.units):
        expected_intervals = {
            _key(unit): (int(unit.start), int(unit.end))
            for unit in expected.units
            if unit.start is not None and unit.end is not None
        }
        intervals: dict[UnitKey, list[tuple[int, int]]] = {
            key: [] for key in expected_intervals
        }
        for edge in selected:
            for unit in edge.covered_extent.units:
                key = _key(unit)
                if key not in intervals or unit.start is None or unit.end is None:
                    continue
                start, end = expected_intervals[key]
                intervals[key].append((max(start, unit.start), min(end, unit.end)))
        return ExtentCoverage(
            expected=expected,
            mode="range",
            intervals={key: _merge(value) for key, value in intervals.items()},
            expected_intervals=expected_intervals,
            covered_atoms=frozenset(),
            expected_atoms=frozenset(),
        )

    expected_units = {unit.unit_id for unit in expected.units}
    group_by_unit = {unit_id: unit_id for unit_id in expected_units}
    footprint_by_unit: dict[str, PhysicalCellFootprint] = {}
    for edge in all_edges:
        for footprint in edge.physical_cell_footprint:
            previous = footprint_by_unit.get(footprint.physical_cell_id)
            if previous is not None and previous != footprint:
                raise ValueError("physical cell footprint is inconsistent across receipts")
            footprint_by_unit[footprint.physical_cell_id] = footprint
    if expected.extent_kind == "physical_cell_union":
        for unit_id in expected_units:
            footprint = footprint_by_unit.get(unit_id)
            if footprint is not None and footprint.merge_origin_physical_cell_id:
                group_by_unit[unit_id] = footprint.merge_origin_physical_cell_id

    units_by_group: dict[str, set[str]] = {}
    for unit_id, group_id in group_by_unit.items():
        units_by_group.setdefault(group_id, set()).add(unit_id)
    covered_units = {
        unit.unit_id
        for edge in selected
        for unit in edge.covered_extent.units
        if unit.unit_id in expected_units and unit.start is None
    }
    covered_atoms = {
        group_id
        for group_id, unit_ids in units_by_group.items()
        if unit_ids.issubset(covered_units)
    }
    return ExtentCoverage(
        expected=expected,
        mode="atom",
        intervals={},
        expected_intervals={},
        covered_atoms=frozenset(covered_atoms),
        expected_atoms=frozenset(units_by_group),
    )
