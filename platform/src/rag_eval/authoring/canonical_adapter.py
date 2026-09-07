"""Adapter from the legacy DOCX extraction records to Canonical Data Model 1.0.

This is a source-structure adapter.  It derives hierarchy only from the
extractor's direct OOXML structural locators and record ordering; it never
consults a runtime retrieval trace.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

from rag_eval.contracts.canonical import (
    CanonicalDocument,
    CanonicalObject,
    CanonicalObjectProvenance,
    CanonicalObjectType,
    CanonicalRelation,
    CanonicalRelationProvenance,
    CanonicalRelationType,
    RepresentationStatus,
    SourceSpan,
)


ADAPTER_IDENTITY = "rag-eval-docx-canonical-contract-adapter/1"


class LegacyDocxCanonicalAdapter:
    """Map existing DOCX extraction records without changing their Bundle v2 view."""

    def adapt(
        self,
        *,
        document_id: str,
        source_sha256: str,
        records: list[dict[str, Any]],
        parser_identity: str,
        canonicalizer_identity: str,
        configuration_digest: str,
    ) -> CanonicalDocument:
        objects = tuple(
            self._object(
                document_id=document_id,
                source_sha256=source_sha256,
                record=record,
                document_order=order,
                parser_identity=parser_identity,
                canonicalizer_identity=canonicalizer_identity,
                configuration_digest=configuration_digest,
            )
            for order, record in enumerate(records)
        )
        by_id = {item.object_id: item for item in objects}
        raw_by_id = {str(record["object_id"]): record for record in records}
        relations = self._relations(document_id, objects, by_id, raw_by_id)
        return CanonicalDocument.build(
            document_id=document_id,
            source_sha256=source_sha256,
            parser_identity=parser_identity,
            canonicalizer_identity=canonicalizer_identity,
            configuration_digest=configuration_digest,
            objects=objects,
            relations=tuple(relations),
        )

    @staticmethod
    def _object_type(record: dict[str, Any]) -> CanonicalObjectType:
        legacy = str(record.get("object_type", ""))
        if legacy == "block":
            kind = str(record.get("block_kind", "paragraph"))
            if kind == "heading":
                return CanonicalObjectType.HEADING
            if kind == "caption":
                return CanonicalObjectType.CAPTION
            return CanonicalObjectType.PARAGRAPH
        if legacy == "note":
            return (
                CanonicalObjectType.FOOTNOTE
                if record.get("note_kind") == "footnote"
                else CanonicalObjectType.ENDNOTE
            )
        try:
            return CanonicalObjectType(legacy)
        except ValueError:
            return CanonicalObjectType.EMBEDDED_OBJECT

    @staticmethod
    def _status(record: dict[str, Any]) -> RepresentationStatus:
        return {
            "supported": RepresentationStatus.COMPLETE,
            "partial": RepresentationStatus.PARTIAL,
            "unsupported": RepresentationStatus.UNSUPPORTED,
            "missing": RepresentationStatus.MISSING,
        }.get(str(record.get("status")), RepresentationStatus.MISSING)

    def _object(
        self,
        *,
        document_id: str,
        source_sha256: str,
        record: dict[str, Any],
        document_order: int,
        parser_identity: str,
        canonicalizer_identity: str,
        configuration_digest: str,
    ) -> CanonicalObject:
        status = self._status(record)
        locator = dict(record.get("structural_locator") or {})
        part = str(locator.pop("part", "word/document.xml"))
        if not locator:
            locator = {"record_ordinal": document_order}
        value = record.get("canonical_value")
        canonical_value = str(value) if value is not None else None
        text_start, text_end = (0, len(canonical_value)) if canonical_value else (None, None)
        span = SourceSpan(
            part=part,
            coordinates=locator,
            text_start=text_start,
            text_end=text_end,
        )
        additional_spans = tuple(
            SourceSpan(
                part=str(dict(raw).pop("part", "word/document.xml")),
                coordinates={
                    key: value
                    for key, value in dict(raw).items()
                    if key != "part"
                },
            )
            for raw in record.get("additional_structural_locators", ())
            if isinstance(raw, dict) and raw
        )
        attributes = {
            key: value
            for key, value in record.items()
            if key
            not in {
                "record_type",
                "document_id",
                "source_sha256",
                "object_type",
                "object_id",
                "status",
                "structural_locator",
                "canonical_value",
                "witness",
                "canonical_digest",
                "canonicalizer",
                "additional_structural_locators",
                "derived_from_object_ids",
            }
        }
        return CanonicalObject(
            object_id=str(record["object_id"]),
            document_id=document_id,
            object_type=self._object_type(record),
            representation_status=status,
            document_order=document_order,
            canonical_value=None if status == RepresentationStatus.MISSING else canonical_value,
            provenance=CanonicalObjectProvenance(
                source_sha256=source_sha256,
                parser_identity=parser_identity,
                canonicalizer_identity=canonicalizer_identity,
                configuration_digest=configuration_digest,
                extraction_method=ADAPTER_IDENTITY,
                source_spans=() if status == RepresentationStatus.MISSING else (span, *additional_spans),
                derived_from_object_ids=tuple(
                    str(item) for item in record.get("derived_from_object_ids", ())
                ),
            ),
            attributes=attributes,
        )

    def _relations(
        self,
        document_id: str,
        objects: tuple[CanonicalObject, ...],
        by_id: dict[str, CanonicalObject],
        raw_by_id: dict[str, dict[str, Any]],
    ) -> list[CanonicalRelation]:
        relations: dict[tuple[CanonicalRelationType, str, str], CanonicalRelation] = {}

        def add(kind: CanonicalRelationType, source_id: str, target_id: str, **attributes: Any) -> None:
            if source_id == target_id or source_id not in by_id or target_id not in by_id:
                return
            key = (kind, source_id, target_id)
            if key in relations:
                return
            spans = tuple(
                span
                for object_id in (source_id, target_id)
                for span in by_id[object_id].provenance.source_spans
            )
            relation_id = "rel-" + hashlib.sha256(
                f"{kind}:{source_id}:{target_id}".encode("utf-8")
            ).hexdigest()[:24]
            relations[key] = CanonicalRelation(
                relation_id=relation_id,
                document_id=document_id,
                relation_type=kind,
                source_object_id=source_id,
                target_object_id=target_id,
                provenance=CanonicalRelationProvenance(
                    extraction_method=ADAPTER_IDENTITY,
                    source_object_ids=(source_id, target_id),
                    source_spans=spans,
                ),
                attributes=attributes,
            )

        document = next(item for item in objects if item.object_type == CanonicalObjectType.DOCUMENT)
        raw_locator = {
            object_id: dict(record.get("structural_locator") or {})
            for object_id, record in raw_by_id.items()
        }

        sections = [item for item in objects if item.object_type == CanonicalObjectType.SECTION]
        headings_by_body: dict[int, CanonicalObject] = {}
        for item in objects:
            if item.object_type == CanonicalObjectType.HEADING:
                body = raw_locator[item.object_id].get("body_ordinal")
                if isinstance(body, int):
                    headings_by_body[body] = item
        stack: list[tuple[int, CanonicalObject]] = []
        for section in sorted(sections, key=lambda item: item.document_order):
            locator = raw_locator[section.object_id]
            level = locator.get("heading_level")
            if not isinstance(level, int):
                add(CanonicalRelationType.PARENT_CHILD, document.object_id, section.object_id)
                continue
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else next(
                (item for item in sections if item.object_id != section.object_id and raw_locator[item.object_id].get("heading_level") is None),
                document,
            )
            add(CanonicalRelationType.PARENT_CHILD, parent.object_id, section.object_id)
            if parent.object_type == CanonicalObjectType.SECTION:
                add(CanonicalRelationType.SECTION_HIERARCHY, parent.object_id, section.object_id, heading_level=level)
            body = locator.get("body_ordinal")
            if isinstance(body, int) and body in headings_by_body:
                add(CanonicalRelationType.PARENT_CHILD, section.object_id, headings_by_body[body].object_id)
            stack.append((level, section))

        paragraph_by_body: dict[int, CanonicalObject] = {}
        for item in objects:
            locator = raw_locator[item.object_id]
            body = locator.get("body_ordinal")
            if item.object_type in {CanonicalObjectType.PARAGRAPH, CanonicalObjectType.CAPTION, CanonicalObjectType.HEADING} and isinstance(body, int):
                paragraph_by_body.setdefault(body, item)

        for item in objects:
            record = raw_by_id[item.object_id]
            locator = raw_locator[item.object_id]
            if item.object_type in {CanonicalObjectType.DOCUMENT, CanonicalObjectType.SECTION, CanonicalObjectType.HEADING}:
                continue
            if item.object_type == CanonicalObjectType.TEXT_SPAN:
                block_id = locator.get("block_id")
                add(CanonicalRelationType.PARENT_CHILD, str(block_id), item.object_id)
                continue
            if item.object_type == CanonicalObjectType.ROW:
                table_id = str(record.get("table_id", ""))
                add(CanonicalRelationType.PARENT_CHILD, table_id, item.object_id)
                add(CanonicalRelationType.TABLE_CONTAINS_ROW, table_id, item.object_id)
                continue
            if item.object_type == CanonicalObjectType.CELL:
                row_id = record.get("row_id")
                add(CanonicalRelationType.PARENT_CHILD, str(row_id), item.object_id)
                add(CanonicalRelationType.ROW_CONTAINS_CELL, str(row_id), item.object_id)
                logical_cell_id = record.get("logical_cell_id")
                if isinstance(logical_cell_id, str):
                    add(CanonicalRelationType.PHYSICAL_TO_LOGICAL_CELL, item.object_id, logical_cell_id)
                for nested_table_id in record.get("nested_table_ids", ()):
                    add(CanonicalRelationType.NESTED_TABLE_IN_CELL, item.object_id, str(nested_table_id))
                continue
            if item.object_type == CanonicalObjectType.LOGICAL_ROW:
                table_id = str(record.get("table_id", ""))
                add(CanonicalRelationType.PARENT_CHILD, table_id, item.object_id)
                add(CanonicalRelationType.TABLE_CONTAINS_LOGICAL_ROW, table_id, item.object_id)
                continue
            if item.object_type == CanonicalObjectType.LOGICAL_COLUMN:
                table_id = str(record.get("table_id", ""))
                add(CanonicalRelationType.PARENT_CHILD, table_id, item.object_id)
                add(CanonicalRelationType.TABLE_CONTAINS_LOGICAL_COLUMN, table_id, item.object_id)
                continue
            if item.object_type == CanonicalObjectType.LOGICAL_CELL:
                logical_row_id = record.get("logical_row_id")
                logical_column_ids = record.get("logical_column_ids", ())
                add(CanonicalRelationType.PARENT_CHILD, str(logical_row_id), item.object_id)
                add(CanonicalRelationType.LOGICAL_ROW_CONTAINS_CELL, str(logical_row_id), item.object_id)
                for logical_column_id in logical_column_ids:
                    add(CanonicalRelationType.LOGICAL_COLUMN_CONTAINS_CELL, str(logical_column_id), item.object_id)
                continue
            if item.object_type in {CanonicalObjectType.FIGURE, CanonicalObjectType.EQUATION}:
                paragraph_id = record.get("paragraph_object_id") or record.get("paragraph_id")
                if isinstance(paragraph_id, str) and paragraph_id in by_id:
                    add(CanonicalRelationType.PARENT_CHILD, paragraph_id, item.object_id)
                    if (
                        item.object_type == CanonicalObjectType.EQUATION
                        and by_id[paragraph_id].object_type == CanonicalObjectType.PARAGRAPH
                    ):
                        add(CanonicalRelationType.EQUATION_IN_PARAGRAPH, item.object_id, paragraph_id)
                section_id = locator.get("section_id")
                if isinstance(section_id, str) and section_id in by_id:
                    if item.object_type == CanonicalObjectType.FIGURE:
                        add(CanonicalRelationType.SECTION_CONTAINS_FIGURE, section_id, item.object_id)
                    else:
                        add(CanonicalRelationType.SECTION_CONTAINS_EQUATION, section_id, item.object_id)
                if item.object_type == CanonicalObjectType.FIGURE:
                    resource_id = record.get("resource_object_id")
                    if isinstance(resource_id, str):
                        add(CanonicalRelationType.FIGURE_HAS_RESOURCE, item.object_id, resource_id)
                continue
            if item.object_type == CanonicalObjectType.CAPTION:
                associated = record.get("associated_object_id")
                if (
                    isinstance(associated, str)
                    and associated in by_id
                    and by_id[associated].object_type
                    in {CanonicalObjectType.FIGURE, CanonicalObjectType.TABLE}
                ):
                    add(CanonicalRelationType.CAPTION_OF, item.object_id, associated)
            if item.object_type == CanonicalObjectType.REFERENCE and record.get("reference_kind") == "figure_textual_reference":
                paragraph_id = record.get("referencing_paragraph_id")
                target_id = record.get("reference_target_object_id")
                if (
                    isinstance(paragraph_id, str)
                    and isinstance(target_id, str)
                    and paragraph_id in by_id
                    and target_id in by_id
                    and by_id[paragraph_id].object_type == CanonicalObjectType.PARAGRAPH
                    and by_id[target_id].object_type == CanonicalObjectType.FIGURE
                ):
                    add(CanonicalRelationType.PARAGRAPH_REFERENCES_FIGURE, paragraph_id, target_id)
                    add(CanonicalRelationType.REFERENCE_TO, item.object_id, target_id)
            section_id = locator.get("section_id")
            if isinstance(section_id, str) and section_id in by_id:
                add(CanonicalRelationType.PARENT_CHILD, section_id, item.object_id)
                continue
            body = locator.get("body_ordinal")
            parent = paragraph_by_body.get(body) if isinstance(body, int) else None
            if parent is not None and parent.object_id != item.object_id:
                add(CanonicalRelationType.PARENT_CHILD, parent.object_id, item.object_id)
            else:
                add(CanonicalRelationType.PARENT_CHILD, document.object_id, item.object_id)

        for item in objects:
            if item.object_type != CanonicalObjectType.LOGICAL_CELL:
                continue
            for header_id in item.attributes.get("effective_header_ids", ()):
                add(CanonicalRelationType.HEADER_FOR, str(header_id), item.object_id)

        bookmarks = {
            str(item.attributes.get("bookmark_name")): item.object_id
            for item in objects
            if item.object_type == CanonicalObjectType.REFERENCE and item.attributes.get("reference_kind") == "bookmark"
        }
        for item in objects:
            if item.object_type != CanonicalObjectType.REFERENCE:
                continue
            target_id = item.attributes.get("reference_target_object_id")
            if isinstance(target_id, str):
                add(CanonicalRelationType.REFERENCE_TO, item.object_id, target_id)
            if item.attributes.get("reference_kind") == "figure_textual_reference":
                continue
            instruction = str(item.attributes.get("field_instruction", ""))
            if item.attributes.get("reference_kind") == "cross_reference":
                match = re.search(r"\b(?:REF|PAGEREF)\s+([^\\\s]+)", instruction, re.I)
                if match and match.group(1) in bookmarks:
                    add(CanonicalRelationType.REFERENCE_TO, item.object_id, bookmarks[match.group(1)])

        children: dict[str, list[CanonicalObject]] = defaultdict(list)
        for relation in relations.values():
            if relation.relation_type == CanonicalRelationType.PARENT_CHILD:
                children[relation.source_object_id].append(by_id[relation.target_object_id])
        for siblings in children.values():
            ordered = sorted(siblings, key=lambda item: item.document_order)
            for first, second in zip(ordered, ordered[1:]):
                add(CanonicalRelationType.SIBLING, first.object_id, second.object_id)

        ordered_objects = sorted(objects, key=lambda item: item.document_order)
        for first, second in zip(ordered_objects, ordered_objects[1:]):
            add(CanonicalRelationType.DOCUMENT_ORDER, first.object_id, second.object_id, adjacent=True)
        return sorted(relations.values(), key=lambda item: item.relation_id)
