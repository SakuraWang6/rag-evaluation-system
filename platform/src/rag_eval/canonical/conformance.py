"""Adapter-independent Canonical Snapshot conformance and Gold eligibility."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence

from rag_eval.contracts.canonical import (
    CANONICAL_GOLD_ELIGIBILITY_POLICY_IDENTITY,
    CanonicalConformanceReport,
    CanonicalConformanceStatus,
    CanonicalDocument,
    CanonicalGoldEligibilityRule,
    CanonicalObject,
    CanonicalObjectConformance,
    CanonicalObjectType,
    CanonicalRelationType,
    RepresentationStatus,
    canonical_json,
)


def _rule(
    subtype: str,
    object_type: CanonicalObjectType,
    eligible: bool,
    rationale: str,
) -> CanonicalGoldEligibilityRule:
    return CanonicalGoldEligibilityRule(
        subtype=subtype,
        object_types=(object_type,),
        gold_evidence_eligible=eligible,
        rationale=rationale,
    )


CANONICAL_GOLD_ELIGIBILITY_MATRIX = tuple(
    sorted(
        (
            _rule(
                "paragraph.standard",
                CanonicalObjectType.PARAGRAPH,
                True,
                "A non-empty paragraph has a unique OOXML body locator.",
            ),
            _rule(
                "paragraph.list_item",
                CanonicalObjectType.PARAGRAPH,
                True,
                "A list item is a source paragraph with a stable body locator.",
            ),
            _rule(
                "text_span.standard",
                CanonicalObjectType.TEXT_SPAN,
                True,
                "A non-empty span is bound to one canonical parent block.",
            ),
            *(
                _rule(
                    f"table.{kind}.with_headers",
                    CanonicalObjectType.TABLE,
                    True,
                    "Complete logical topology and headers define stable table evidence.",
                )
                for kind in (
                    "regular",
                    "inferred_regular_grid",
                    "horizontal_merge",
                    "vertical_merge",
                    "mixed_merge",
                )
            ),
            _rule(
                "table.headerless",
                CanonicalObjectType.TABLE,
                False,
                "Headerless tables lack an admitted semantic coordinate path.",
            ),
            _rule(
                "table.table_without_data",
                CanonicalObjectType.TABLE,
                False,
                "A header-only table has no admitted data evidence extent.",
            ),
            _rule(
                "table.irregular_or_partial",
                CanonicalObjectType.TABLE,
                False,
                "Incomplete or ambiguous logical topology fails closed.",
            ),
            _rule(
                "table.nested",
                CanonicalObjectType.TABLE,
                False,
                "Nested-table identity is not admitted in the first conformance wave.",
            ),
            *(
                _rule(
                    f"logical_cell.{kind}.with_headers",
                    CanonicalObjectType.LOGICAL_CELL,
                    True,
                    "The logical cell is the table scoring atom for an admitted topology.",
                )
                for kind in (
                    "regular",
                    "inferred_regular_grid",
                    "horizontal_merge",
                    "vertical_merge",
                    "mixed_merge",
                )
            ),
            _rule(
                "logical_cell.headerless",
                CanonicalObjectType.LOGICAL_CELL,
                False,
                "A cell in a headerless table lacks an admitted semantic path.",
            ),
            _rule(
                "logical_cell.table_without_data",
                CanonicalObjectType.LOGICAL_CELL,
                False,
                "A cell in a header-only table is not admitted as data evidence.",
            ),
            _rule(
                "logical_cell.irregular_or_partial",
                CanonicalObjectType.LOGICAL_CELL,
                False,
                "A cell cannot outlive an incomplete parent-table topology.",
            ),
            _rule(
                "logical_cell.nested",
                CanonicalObjectType.LOGICAL_CELL,
                False,
                "Nested logical cells are not admitted in the first conformance wave.",
            ),
            _rule(
                "logical_cell.missing_table",
                CanonicalObjectType.LOGICAL_CELL,
                False,
                "A logical cell without a canonical parent table fails closed.",
            ),
            _rule(
                "physical_cell.proof_only",
                CanonicalObjectType.CELL,
                False,
                "Physical cells prove topology; logical cells are scoring atoms.",
            ),
        ),
        key=lambda item: item.subtype,
    )
)

_RULE_BY_SUBTYPE = {
    item.subtype: item for item in CANONICAL_GOLD_ELIGIBILITY_MATRIX
}
_FIRST_WAVE_TYPES = {
    CanonicalObjectType.PARAGRAPH,
    CanonicalObjectType.TEXT_SPAN,
    CanonicalObjectType.TABLE,
    CanonicalObjectType.CELL,
    CanonicalObjectType.LOGICAL_CELL,
}


class CanonicalConformanceSuite:
    """Evaluate source identity and Gold admission without runtime knowledge."""

    policy_identity = CANONICAL_GOLD_ELIGIBILITY_POLICY_IDENTITY

    def evaluate(self, document: CanonicalDocument) -> CanonicalConformanceReport:
        objects = {item.object_id: item for item in document.objects}
        relations = {
            (item.relation_type, item.source_object_id, item.target_object_id)
            for item in document.relations
        }
        duplicate_locators = self._duplicate_typed_locators(document.objects)
        results = tuple(
            self._evaluate_object(
                document=document,
                item=item,
                objects=objects,
                relations=relations,
                duplicate_locators=duplicate_locators,
            )
            for item in document.objects
        )
        return CanonicalConformanceReport.build(
            canonical_digest=document.manifest.canonical_digest,
            source_sha256=document.manifest.source_sha256,
            parser_identity=document.manifest.parser_identity,
            canonicalizer_identity=document.manifest.canonicalizer_identity,
            configuration_digest=document.manifest.configuration_digest,
            object_results=results,
            rule_matrix=CANONICAL_GOLD_ELIGIBILITY_MATRIX,
        )

    @staticmethod
    def eligibility_attributes(
        report: CanonicalConformanceReport,
    ) -> dict[str, dict[str, object]]:
        """Return explicit fields for new snapshots; never mutate the input."""

        return {
            item.object_id: {
                "gold_evidence_eligible": item.gold_evidence_eligible,
                "gold_eligibility_policy": report.policy_identity,
                "gold_eligibility_subtype": item.subtype,
                "gold_eligibility_reasons": item.reason_codes,
            }
            for item in report.object_results
        }

    def _evaluate_object(
        self,
        *,
        document: CanonicalDocument,
        item: CanonicalObject,
        objects: Mapping[str, CanonicalObject],
        relations: set[tuple[CanonicalRelationType, str, str]],
        duplicate_locators: set[tuple[CanonicalObjectType, str]],
    ) -> CanonicalObjectConformance:
        locator_digest = self._locator_digest(item)
        witness_sha256 = (
            hashlib.sha256(item.canonical_value.encode("utf-8")).hexdigest()
            if item.canonical_value is not None
            else None
        )
        subtype = self._subtype(item, objects)
        reasons = self._identity_reasons(document, item)
        if (item.object_type, locator_digest) in duplicate_locators:
            reasons.append("duplicate_typed_locator")
        if item.object_type not in _FIRST_WAVE_TYPES:
            status = (
                CanonicalConformanceStatus.NONCONFORMANT
                if reasons
                else CanonicalConformanceStatus.NOT_EVALUATED
            )
            return CanonicalObjectConformance(
                object_id=item.object_id,
                object_type=item.object_type,
                subtype=subtype,
                status=status,
                gold_evidence_eligible=False,
                reason_codes=tuple(
                    sorted(reasons or ["type_not_in_first_wave_candidate_set"])
                ),
                locator_digest=locator_digest,
                witness_sha256=witness_sha256,
            )

        reasons.extend(
            self._structural_reasons(
                item=item,
                objects=objects,
                relations=relations,
            )
        )
        rule = _RULE_BY_SUBTYPE.get(subtype)
        if rule is None:
            reasons.append("gold_eligibility_rule_missing")
        if reasons:
            return CanonicalObjectConformance(
                object_id=item.object_id,
                object_type=item.object_type,
                subtype=subtype,
                status=CanonicalConformanceStatus.NONCONFORMANT,
                gold_evidence_eligible=False,
                reason_codes=tuple(sorted(set(reasons))),
                locator_digest=locator_digest,
                witness_sha256=witness_sha256,
            )
        assert rule is not None
        eligible = rule.gold_evidence_eligible
        return CanonicalObjectConformance(
            object_id=item.object_id,
            object_type=item.object_type,
            subtype=subtype,
            status=CanonicalConformanceStatus.CONFORMANT,
            gold_evidence_eligible=eligible,
            reason_codes=(
                "gold_eligible_by_canonical_conformance"
                if eligible
                else "subtype_not_gold_admitted",
            ),
            locator_digest=locator_digest,
            witness_sha256=witness_sha256,
        )

    @staticmethod
    def _locator_digest(item: CanonicalObject) -> str:
        payload = [
            span.model_dump(mode="json", exclude_none=True)
            for span in item.provenance.source_spans
        ]
        return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()

    def _duplicate_typed_locators(
        self, objects: Sequence[CanonicalObject]
    ) -> set[tuple[CanonicalObjectType, str]]:
        typed: dict[tuple[CanonicalObjectType, str], list[str]] = defaultdict(list)
        for item in objects:
            if not item.provenance.source_spans:
                continue
            digest = self._locator_digest(item)
            typed[(item.object_type, digest)].append(item.object_id)
        return {key for key, object_ids in typed.items() if len(object_ids) > 1}

    @staticmethod
    def _identity_reasons(
        document: CanonicalDocument, item: CanonicalObject
    ) -> list[str]:
        manifest = document.manifest
        provenance = item.provenance
        reasons: list[str] = []
        if provenance.source_sha256 != manifest.source_sha256:
            reasons.append("source_identity_mismatch")
        if provenance.parser_identity != manifest.parser_identity:
            reasons.append("parser_identity_mismatch")
        if provenance.canonicalizer_identity != manifest.canonicalizer_identity:
            reasons.append("canonicalizer_identity_mismatch")
        if provenance.configuration_digest != manifest.configuration_digest:
            reasons.append("configuration_identity_mismatch")
        if item.representation_status != RepresentationStatus.COMPLETE:
            reasons.append(f"representation_{item.representation_status.value}")
        if not provenance.source_spans:
            reasons.append("typed_locator_missing")
        empty_merge_continuation = (
            item.object_type == CanonicalObjectType.CELL
            and item.attributes.get("v_merge") == "continue"
        )
        if not (item.canonical_value or "").strip() and not empty_merge_continuation:
            reasons.append("canonical_witness_empty")
        return reasons

    def _subtype(
        self,
        item: CanonicalObject,
        objects: Mapping[str, CanonicalObject],
    ) -> str:
        if item.object_type == CanonicalObjectType.PARAGRAPH:
            return (
                "paragraph.list_item"
                if item.attributes.get("block_kind") == "list_item"
                else "paragraph.standard"
            )
        if item.object_type == CanonicalObjectType.TEXT_SPAN:
            return "text_span.standard"
        if item.object_type == CanonicalObjectType.TABLE:
            return self._table_subtype(item, objects)
        if item.object_type == CanonicalObjectType.LOGICAL_CELL:
            table = objects.get(str(item.attributes.get("table_id") or ""))
            if table is None or table.object_type != CanonicalObjectType.TABLE:
                return "logical_cell.missing_table"
            return self._table_subtype(table, objects).replace(
                "table.", "logical_cell.", 1
            )
        if item.object_type == CanonicalObjectType.CELL:
            return "physical_cell.proof_only"
        return f"non_candidate.{item.object_type.value}"

    @staticmethod
    def _table_subtype(
        table: CanonicalObject,
        objects: Mapping[str, CanonicalObject],
    ) -> str:
        classes = {
            str(value)
            for value in table.attributes.get("table_structure_classes", ())
        }
        if table.attributes.get("nested") or "nested_table" in classes:
            return "table.nested"
        if (
            table.representation_status != RepresentationStatus.COMPLETE
            or table.attributes.get("topology_status") != "complete"
            or table.attributes.get("topology_errors")
        ):
            return "table.irregular_or_partial"
        header_rows = int(table.attributes.get("header_row_count") or 0)
        header_columns = int(table.attributes.get("header_column_count") or 0)
        if not (header_rows or header_columns):
            return "table.headerless"
        logical_cells = [
            item
            for item in objects.values()
            if item.object_type == CanonicalObjectType.LOGICAL_CELL
            and item.attributes.get("table_id") == table.object_id
        ]
        has_data = any(
            int(item.attributes.get("logical_row_start") or 0) > header_rows
            and (
                not header_columns
                or int(item.attributes.get("logical_column_start") or 0)
                > header_columns
            )
            for item in logical_cells
        )
        if not has_data:
            return "table.table_without_data"
        if "mixed_merge" in classes:
            kind = "mixed_merge"
        elif "vertical_merge" in classes:
            kind = "vertical_merge"
        elif "horizontal_merge" in classes:
            kind = "horizontal_merge"
        elif "inferred_regular_grid" in classes:
            kind = "inferred_regular_grid"
        else:
            kind = "regular"
        return f"table.{kind}.with_headers"

    @staticmethod
    def _structural_reasons(
        *,
        item: CanonicalObject,
        objects: Mapping[str, CanonicalObject],
        relations: set[tuple[CanonicalRelationType, str, str]],
    ) -> list[str]:
        reasons: list[str] = []
        span = item.provenance.source_spans[0] if item.provenance.source_spans else None
        coordinates = span.coordinates if span is not None else {}
        if not isinstance(coordinates.get("body_ordinal"), int):
            reasons.append("body_ordinal_missing")

        parent_edges = {
            (source, target)
            for relation_type, source, target in relations
            if relation_type == CanonicalRelationType.PARENT_CHILD
        }
        if item.object_type == CanonicalObjectType.PARAGRAPH:
            if not any(target == item.object_id for _source, target in parent_edges):
                reasons.append("paragraph_parent_relation_missing")
        elif item.object_type == CanonicalObjectType.TEXT_SPAN:
            block_id = item.attributes.get("block_id")
            if not isinstance(block_id, str) or not block_id:
                reasons.append("text_span_parent_id_missing")
            elif (block_id, item.object_id) not in parent_edges:
                reasons.append("text_span_parent_relation_missing")
            if not isinstance(coordinates.get("span_ordinal"), int):
                reasons.append("text_span_ordinal_missing")
        elif item.object_type == CanonicalObjectType.TABLE:
            if item.attributes.get("topology_status") != "complete":
                reasons.append("table_topology_incomplete")
            expected_rows = int(item.attributes.get("physical_row_count") or 0)
            expected_logical_rows = int(
                item.attributes.get("logical_row_count") or 0
            )
            expected_logical_columns = int(
                item.attributes.get("logical_column_count") or 0
            )
            actual_rows = sum(
                relation_type == CanonicalRelationType.TABLE_CONTAINS_ROW
                and source == item.object_id
                for relation_type, source, _target in relations
            )
            actual_logical_rows = sum(
                relation_type == CanonicalRelationType.TABLE_CONTAINS_LOGICAL_ROW
                and source == item.object_id
                for relation_type, source, _target in relations
            )
            actual_logical_columns = sum(
                relation_type
                == CanonicalRelationType.TABLE_CONTAINS_LOGICAL_COLUMN
                and source == item.object_id
                for relation_type, source, _target in relations
            )
            if actual_rows != expected_rows:
                reasons.append("table_physical_row_relation_count_mismatch")
            if actual_logical_rows != expected_logical_rows:
                reasons.append("table_logical_row_relation_count_mismatch")
            if actual_logical_columns != expected_logical_columns:
                reasons.append("table_logical_column_relation_count_mismatch")
        elif item.object_type == CanonicalObjectType.CELL:
            required = {"table_id", "row", "column", "physical_cell_index"}
            if required.difference(coordinates):
                reasons.append("physical_cell_locator_incomplete")
            logical_cell_id = item.attributes.get("logical_cell_id")
            if not isinstance(logical_cell_id, str) or logical_cell_id not in objects:
                reasons.append("physical_cell_logical_target_missing")
            elif (
                CanonicalRelationType.PHYSICAL_TO_LOGICAL_CELL,
                item.object_id,
                logical_cell_id,
            ) not in relations:
                reasons.append("physical_to_logical_relation_missing")
        elif item.object_type == CanonicalObjectType.LOGICAL_CELL:
            required = {"table_id", "row", "column", "logical"}
            if required.difference(coordinates) or coordinates.get("logical") is not True:
                reasons.append("logical_cell_locator_incomplete")
            table_id = item.attributes.get("table_id")
            if not isinstance(table_id, str) or table_id not in objects:
                reasons.append("logical_cell_table_missing")
            origin_id = item.attributes.get("origin_physical_cell_id")
            if not isinstance(origin_id, str) or origin_id not in objects:
                reasons.append("logical_cell_origin_missing")
            elif (
                CanonicalRelationType.PHYSICAL_TO_LOGICAL_CELL,
                origin_id,
                item.object_id,
            ) not in relations:
                reasons.append("logical_cell_origin_relation_missing")
            if not item.attributes.get("covered_logical_coordinates"):
                reasons.append("logical_cell_footprint_missing")
            logical_row_id = item.attributes.get("logical_row_id")
            if not isinstance(logical_row_id, str) or (
                CanonicalRelationType.LOGICAL_ROW_CONTAINS_CELL,
                logical_row_id,
                item.object_id,
            ) not in relations:
                reasons.append("logical_row_relation_missing")
            logical_column_ids = item.attributes.get("logical_column_ids", ())
            if not logical_column_ids or any(
                (
                    CanonicalRelationType.LOGICAL_COLUMN_CONTAINS_CELL,
                    str(column_id),
                    item.object_id,
                )
                not in relations
                for column_id in logical_column_ids
            ):
                reasons.append("logical_column_relation_missing")
        return reasons
