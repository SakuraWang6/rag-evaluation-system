"""Deterministic, chunker-independent OOXML canonicalization for DOCX.

The output is a source-grounded object graph, not an attempt to infer answers
or benchmark cases.  It preserves unsupported material as diagnostics rather
than silently treating it as text evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from lxml import etree

from rag_eval.authoring.models import CanonicalView
from rag_eval.storage.atomic import atomic_write_json


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
V = "urn:schemas-microsoft-com:vml"
O = "urn:schemas-microsoft-com:office:office"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W, "r": R, "m": M, "a": A, "wp": WP, "v": V, "o": O, "rel": REL}
CANONICALIZER_VERSION = "rag-eval-authoring-canonicalizer/1"


def _tag(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def _attr(element: etree._Element, namespace: str, name: str) -> str | None:
    return element.get(_tag(namespace, name))


def _read_xml(package: zipfile.ZipFile, name: str) -> etree._Element | None:
    try:
        return etree.fromstring(package.read(name))
    except KeyError:
        return None
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"invalid OOXML XML part: {name}") from exc


def _compact_text(value: str) -> str:
    return re.sub(r"[ \t\r\n]+", " ", value).strip()


def _json_line(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _digest_records(records: list[dict[str, Any]]) -> str:
    payload = "".join(_json_line(record) for record in records).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class CanonicalizationResult:
    document_id: str
    canonical_digest: str
    execution_markdown: str
    evidence_records_path: Path
    object_records_path: Path
    summary_path: Path
    diagnostics_path: Path
    diagnostics: dict[str, Any]

    def view(self, *, root: Path, source_sha256: str) -> CanonicalView:
        return CanonicalView(
            document_id=self.document_id,
            source_sha256=source_sha256,
            canonical_digest=self.canonical_digest,
            execution_markdown=self.execution_markdown,
            evidence_records_path=str(self.evidence_records_path.relative_to(root)),
            object_records_path=str(self.object_records_path.relative_to(root)),
            summary_path=str(self.summary_path.relative_to(root)),
            diagnostics_path=str(self.diagnostics_path.relative_to(root)),
        )


class DocxCanonicalizer:
    """Extract ordered, observable OOXML records with stable source-derived IDs."""

    def canonicalize(
        self,
        *,
        source_path: Path,
        output_root: Path,
        source_sha256: str,
    ) -> CanonicalizationResult:
        document_id = f"doc-{source_sha256[:16]}"
        canonical_dir = output_root / "canonical"
        diagnostics_dir = output_root / "diagnostics"
        canonical_dir.mkdir(parents=True, exist_ok=True)
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source_path) as package:
            document = _read_xml(package, "word/document.xml")
            if document is None:
                raise ValueError("OOXML package has no word/document.xml")
            styles = self._styles(package)
            relationships = self._relationships(package)
            notes = self._notes(package)
            records, markdown, extraction = self._body_records(
                document=document,
                styles=styles,
                relationships=relationships,
                notes=notes,
                document_id=document_id,
                source_sha256=source_sha256,
            )
            package_diagnostics = self._package_diagnostics(package, document, notes)

        base_records = [self._base_record(record) for record in records]
        canonical_digest = _digest_records(base_records)
        records = [
            record | {"canonical_digest": canonical_digest, "canonicalizer": CANONICALIZER_VERSION}
            for record in base_records
        ]
        record_text = "".join(_json_line(record) for record in records)
        execution_markdown = self._normalize_markdown(markdown)
        evidence_path = canonical_dir / "evidence.jsonl"
        objects_path = canonical_dir / "objects.jsonl"
        markdown_path = canonical_dir / "execution.md"
        summary_path = canonical_dir / "summary.json"
        diagnostics_path = diagnostics_dir / "analysis.json"
        evidence_path.write_text(record_text, encoding="utf-8")
        objects_path.write_text(record_text, encoding="utf-8")
        markdown_path.write_text(execution_markdown, encoding="utf-8")
        diagnostics = self._diagnostics(
            records=records,
            extraction=extraction,
            package_diagnostics=package_diagnostics,
            document_id=document_id,
            source_sha256=source_sha256,
            canonical_digest=canonical_digest,
        )
        atomic_write_json(diagnostics_path, diagnostics)
        atomic_write_json(
            summary_path,
            {
                "document_id": document_id,
                "source_sha256": source_sha256,
                "canonical_digest": canonical_digest,
                "canonicalizer": CANONICALIZER_VERSION,
                "record_count": len(records),
                "execution_markdown_sha256": hashlib.sha256(
                    execution_markdown.encode("utf-8")
                ).hexdigest(),
            },
        )
        return CanonicalizationResult(
            document_id=document_id,
            canonical_digest=canonical_digest,
            execution_markdown=execution_markdown,
            evidence_records_path=evidence_path,
            object_records_path=objects_path,
            summary_path=summary_path,
            diagnostics_path=diagnostics_path,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _base_record(record: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in record.items() if key != "canonical_digest"}

    @staticmethod
    def _styles(package: zipfile.ZipFile) -> dict[str, str]:
        root = _read_xml(package, "word/styles.xml")
        if root is None:
            return {}
        values: dict[str, str] = {}
        for style in root.findall("w:style", NS):
            style_id = _attr(style, W, "styleId")
            name = style.find("w:name", NS)
            if style_id and name is not None:
                values[style_id] = _attr(name, W, "val") or style_id
        return values

    @staticmethod
    def _relationships(package: zipfile.ZipFile) -> dict[str, dict[str, str]]:
        root = _read_xml(package, "word/_rels/document.xml.rels")
        if root is None:
            return {}
        values: dict[str, dict[str, str]] = {}
        for relation in root.findall("rel:Relationship", NS):
            relation_id = relation.get("Id")
            if relation_id:
                values[relation_id] = {
                    "target": relation.get("Target", ""),
                    "type": relation.get("Type", ""),
                    "target_mode": relation.get("TargetMode", ""),
                }
        return values

    @staticmethod
    def _notes(package: zipfile.ZipFile) -> dict[str, dict[str, str]]:
        note_maps: dict[str, dict[str, str]] = {}
        for kind, part, element_name in (
            ("footnote", "word/footnotes.xml", "footnote"),
            ("endnote", "word/endnotes.xml", "endnote"),
        ):
            root = _read_xml(package, part)
            note_maps[kind] = {}
            if root is None:
                continue
            for note in root.findall(f"w:{element_name}", NS):
                note_id = _attr(note, W, "id")
                if note_id is not None and note_id not in {"-1", "0"}:
                    note_maps[kind][note_id] = _compact_text("".join(note.itertext()))
        return note_maps

    def _body_records(
        self,
        *,
        document: etree._Element,
        styles: dict[str, str],
        relationships: dict[str, dict[str, str]],
        notes: dict[str, dict[str, str]],
        document_id: str,
        source_sha256: str,
    ) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
        body = document.find("w:body", NS)
        if body is None:
            raise ValueError("OOXML document has no body")
        records: list[dict[str, Any]] = []
        markdown: list[str] = []
        extraction: dict[str, Any] = {"unanchored_notes": [], "partial_objects": []}
        section_ordinal = 0
        current_section = self._object_id(document_id, "section", section_ordinal)
        records.append(
            self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="document",
                object_id=document_id,
                status="supported",
                structural_locator={"part": "word/document.xml"},
                canonical_value=document_id,
                witness="OOXML WordprocessingML document",
            )
        )
        records.append(
            self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="section",
                object_id=current_section,
                status="supported",
                structural_locator={"part": "word/document.xml", "ordinal": section_ordinal},
                canonical_value="Document body",
                witness="Document body",
            )
        )
        last_associable: dict[str, Any] | None = None
        table_ordinal = 0
        block_ordinal = 0
        figure_ordinal = 0
        equation_ordinal = 0
        reference_ordinal = 0
        for body_ordinal, child in enumerate(body):
            if child.tag == _tag(W, "sectPr"):
                continue
            if child.tag == _tag(W, "p"):
                style_id, style_name = self._paragraph_style(child, styles)
                text = self._paragraph_text(child)
                if not text and not self._paragraph_has_rich_object(child):
                    continue
                heading_level = self._heading_level(style_id, style_name)
                block_ordinal += 1
                block_id = self._object_id(document_id, "block", block_ordinal)
                is_caption = "caption" in style_name.lower()
                is_list = self._is_list(child, style_name)
                block_kind = (
                    "heading" if heading_level is not None else
                    ("caption" if is_caption else ("list_item" if is_list else "paragraph"))
                )
                status = "partial" if is_caption else "supported"
                block_record = self._record(
                    document_id=document_id,
                    source_sha256=source_sha256,
                    object_type="block",
                    object_id=block_id,
                    status=status,
                    structural_locator={
                        "part": "word/document.xml",
                        "body_ordinal": body_ordinal,
                        "section_id": current_section,
                        "style_id": style_id,
                        "style_name": style_name,
                    },
                    canonical_value=text,
                    witness=text,
                )
                block_record["block_kind"] = block_kind
                span_record: dict[str, Any] | None = None
                if text:
                    span_record = self._record(
                        document_id=document_id,
                        source_sha256=source_sha256,
                        object_type="text_span",
                        object_id=self._object_id(document_id, "text_span", block_ordinal),
                        status=status,
                        structural_locator={
                            "part": "word/document.xml",
                            "body_ordinal": body_ordinal,
                            "block_id": block_id,
                            "span_ordinal": 1,
                        },
                        canonical_value=text,
                        witness=text,
                    )
                    span_record["block_id"] = block_id
                if heading_level is not None:
                    section_ordinal += 1
                    current_section = self._object_id(document_id, "section", section_ordinal)
                    records.append(block_record)
                    if span_record is not None:
                        records.append(span_record)
                    section_record = self._record(
                        document_id=document_id,
                        source_sha256=source_sha256,
                        object_type="section",
                        object_id=current_section,
                        status="supported",
                        structural_locator={
                            "part": "word/document.xml",
                            "body_ordinal": body_ordinal,
                            "heading_level": heading_level,
                        },
                        canonical_value=text,
                        witness=text,
                    )
                    records.append(section_record)
                    markdown.append("#" * heading_level + " " + text)
                    last_associable = None
                    continue
                if is_caption and last_associable is not None:
                    block_record["associated_object_id"] = last_associable["object_id"]
                    block_record["association_method"] = "adjacent_body_object"
                elif is_caption:
                    block_record["association_method"] = "unresolved"
                    extraction["partial_objects"].append({"object_id": block_id, "reason": "unresolved_caption_association"})
                records.append(block_record)
                if span_record is not None:
                    records.append(span_record)
                if text:
                    markdown.append(("- " if is_list else "") + text)
                if not is_caption:
                    last_associable = block_record
                rich_records, figure_ordinal, equation_ordinal, reference_ordinal = self._paragraph_rich_records(
                    paragraph=child,
                    document_id=document_id,
                    source_sha256=source_sha256,
                    body_ordinal=body_ordinal,
                    section_id=current_section,
                    relationships=relationships,
                    notes=notes,
                    figure_ordinal=figure_ordinal,
                    equation_ordinal=equation_ordinal,
                    reference_ordinal=reference_ordinal,
                    paragraph_text=text,
                )
                for rich_record in rich_records:
                    records.append(rich_record)
                    if rich_record["object_type"] == "figure":
                        description = rich_record.get("canonical_value") or "inline image"
                        markdown.append(f"Figure: {description}")
                    elif rich_record["object_type"] == "equation":
                        markdown.append(f"Equation: {rich_record.get('canonical_value', '')}")
                    if rich_record["status"] != "supported":
                        extraction["partial_objects"].append(
                            {"object_id": rich_record["object_id"], "reason": rich_record["status"]}
                        )
                continue
            if child.tag == _tag(W, "tbl"):
                table_ordinal += 1
                table_records, table_markdown, table_record = self._table_records(
                    table=child,
                    document_id=document_id,
                    source_sha256=source_sha256,
                    body_ordinal=body_ordinal,
                    section_id=current_section,
                    table_ordinal=table_ordinal,
                )
                records.extend(table_records)
                markdown.extend(table_markdown)
                last_associable = table_record
                if table_record["status"] != "supported":
                    extraction["partial_objects"].append(
                        {"object_id": table_record["object_id"], "reason": "merged_or_irregular_table"}
                    )
        body_ordinals = {id(child): index for index, child in enumerate(body)}
        for nested_table in document.findall(".//w:tc/w:tbl", NS):
            ancestor = nested_table
            while ancestor.getparent() is not None and ancestor.getparent() is not body:
                ancestor = ancestor.getparent()
            parent_ordinal = body_ordinals.get(id(ancestor), -1)
            table_ordinal += 1
            table_records, table_markdown, table_record = self._table_records(
                table=nested_table,
                document_id=document_id,
                source_sha256=source_sha256,
                body_ordinal=parent_ordinal,
                section_id=current_section,
                table_ordinal=table_ordinal,
                nested=True,
            )
            records.extend(table_records)
            markdown.extend(table_markdown)
            extraction["partial_objects"].append(
                {"object_id": table_record["object_id"], "reason": "nested_table"}
            )
        anchored_note_ids = {
            (record.get("note_kind"), record.get("note_id"))
            for record in records
            if record.get("object_type") == "note"
        }
        for note_kind, note_values in notes.items():
            for note_id in sorted(note_values):
                if (note_kind, note_id) not in anchored_note_ids:
                    note_record = self._record(
                        document_id=document_id,
                        source_sha256=source_sha256,
                        object_type="note",
                        object_id=self._object_id(document_id, f"unanchored_{note_kind}", int(note_id) if note_id.isdigit() else len(records)),
                        status="unsupported",
                        structural_locator={"part": f"word/{note_kind}s.xml", "note_id": note_id},
                        canonical_value=note_values[note_id],
                        witness=note_values[note_id],
                    )
                    note_record["note_kind"] = note_kind
                    note_record["note_id"] = note_id
                    note_record["reason"] = "unanchored_note"
                    records.append(note_record)
                    extraction["unanchored_notes"].append({"kind": note_kind, "note_id": note_id})
        return records, markdown, extraction

    def _paragraph_rich_records(
        self,
        *,
        paragraph: etree._Element,
        document_id: str,
        source_sha256: str,
        body_ordinal: int,
        section_id: str,
        relationships: dict[str, dict[str, str]],
        notes: dict[str, dict[str, str]],
        figure_ordinal: int,
        equation_ordinal: int,
        reference_ordinal: int,
        paragraph_text: str,
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        records: list[dict[str, Any]] = []
        base_locator = {"part": "word/document.xml", "body_ordinal": body_ordinal, "section_id": section_id}
        for drawing in paragraph.findall(".//w:drawing", NS):
            inline = drawing.find("wp:inline", NS)
            anchor = drawing.find("wp:anchor", NS)
            drawing_item = inline if inline is not None else anchor
            if drawing_item is None:
                continue
            figure_ordinal += 1
            doc_pr = drawing_item.find("wp:docPr", NS)
            blip = drawing_item.find(".//a:blip", NS)
            relation_id = _attr(blip, R, "embed") if blip is not None else None
            relationship = relationships.get(relation_id or "", {})
            name = doc_pr.get("name") if doc_pr is not None else None
            description = doc_pr.get("descr") if doc_pr is not None else None
            value = _compact_text(description or name or relationship.get("target", "inline image"))
            supported = inline is not None and bool(relationship.get("target"))
            record = self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="figure",
                object_id=self._object_id(document_id, "figure", figure_ordinal),
                status="supported" if supported else "partial",
                structural_locator=base_locator | {"drawing": "inline" if inline is not None else "anchor", "relationship_id": relation_id},
                canonical_value=value,
                witness=value,
            )
            record["media_target"] = relationship.get("target")
            records.append(record)
        for index, shape in enumerate(paragraph.findall(".//v:shape", NS), start=1):
            figure_ordinal += 1
            value = _compact_text(shape.get("alt") or shape.get("title") or shape.get("id") or "VML shape")
            records.append(
                self._record(
                    document_id=document_id,
                    source_sha256=source_sha256,
                    object_type="figure",
                    object_id=self._object_id(document_id, "vml", figure_ordinal),
                    status="partial",
                    structural_locator=base_locator | {"vml_shape_ordinal": index},
                    canonical_value=value,
                    witness=value,
                )
            )
        for index, ole in enumerate(paragraph.findall(".//o:OLEObject", NS), start=1):
            reference_ordinal += 1
            value = _compact_text(ole.get("ProgID") or ole.get("Type") or "OLE embedded object")
            records.append(
                self._record(
                    document_id=document_id,
                    source_sha256=source_sha256,
                    object_type="embedded_object",
                    object_id=self._object_id(document_id, "ole", reference_ordinal),
                    status="unsupported",
                    structural_locator=base_locator | {"ole_ordinal": index, "relationship_id": _attr(ole, R, "id")},
                    canonical_value=value,
                    witness=value,
                )
            )
        equation_elements = list(paragraph.findall(".//m:oMath", NS)) + list(
            paragraph.findall(".//m:oMathPara", NS)
        )
        for index, equation in enumerate(equation_elements, start=1):
            equation_ordinal += 1
            surface = _compact_text("".join(equation.xpath(".//m:t/text()", namespaces=NS)))
            raw_digest = hashlib.sha256(etree.tostring(equation, with_tail=False)).hexdigest()
            record = self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="equation",
                object_id=self._object_id(document_id, "equation", equation_ordinal),
                status="partial",
                structural_locator=base_locator | {"equation_ordinal": index, "raw_xml_sha256": raw_digest},
                canonical_value=surface or "OMML equation",
                witness=surface or "OMML equation",
            )
            record["representation"] = "omml_surface_text"
            records.append(record)
        for bookmark in paragraph.findall(".//w:bookmarkStart", NS):
            reference_ordinal += 1
            value = _compact_text(_attr(bookmark, W, "name") or "bookmark")
            record = self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="reference",
                object_id=self._object_id(document_id, "bookmark", reference_ordinal),
                status="supported",
                structural_locator=base_locator | {"bookmark_id": _attr(bookmark, W, "id")},
                canonical_value=value,
                witness=paragraph_text or value,
            )
            record["reference_kind"] = "bookmark"
            record["bookmark_name"] = value
            records.append(record)
        for hyperlink in paragraph.findall(".//w:hyperlink", NS):
            relation_id = _attr(hyperlink, R, "id")
            target = relationships.get(relation_id or "", {}).get("target")
            if not target:
                continue
            reference_ordinal += 1
            value = _compact_text("".join(hyperlink.itertext())) or target
            record = self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="reference",
                object_id=self._object_id(document_id, "hyperlink", reference_ordinal),
                status="supported",
                structural_locator=base_locator | {"relationship_id": relation_id, "target": target},
                canonical_value=value,
                witness=value,
            )
            record["reference_kind"] = "hyperlink"
            record["target"] = target
            records.append(record)
        instructions = [
            _attr(field, W, "instr") or ""
            for field in paragraph.findall(".//w:fldSimple", NS)
        ] + [value or "" for value in paragraph.xpath(".//w:instrText/text()", namespaces=NS)]
        for index, instruction in enumerate(instructions, start=1):
            instruction = _compact_text(instruction)
            if not instruction:
                continue
            reference_ordinal += 1
            kind = "cross_reference" if re.search(r"\b(?:REF|PAGEREF|SEQ)\b", instruction, re.I) else "field"
            record = self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="reference",
                object_id=self._object_id(document_id, "field", reference_ordinal),
                status="partial",
                structural_locator=base_locator | {"field_ordinal": index, "instruction": instruction},
                canonical_value=paragraph_text or instruction,
                witness=paragraph_text or instruction,
            )
            record["reference_kind"] = kind
            record["field_instruction"] = instruction
            records.append(record)
        for note_kind, element_name in (("footnote", "footnoteReference"), ("endnote", "endnoteReference")):
            for reference in paragraph.findall(f".//w:{element_name}", NS):
                note_id = _attr(reference, W, "id")
                if note_id is None:
                    continue
                reference_ordinal += 1
                value = notes.get(note_kind, {}).get(note_id, "")
                record = self._record(
                    document_id=document_id,
                    source_sha256=source_sha256,
                    object_type="note",
                    object_id=self._object_id(document_id, note_kind, reference_ordinal),
                    status="partial",
                    structural_locator=base_locator | {"note_id": note_id, "note_kind": note_kind},
                    canonical_value=value or paragraph_text,
                    witness=value or paragraph_text,
                )
                record["note_kind"] = note_kind
                record["note_id"] = note_id
                record["body_anchor"] = True
                records.append(record)
        return records, figure_ordinal, equation_ordinal, reference_ordinal

    def _table_records(
        self,
        *,
        table: etree._Element,
        document_id: str,
        source_sha256: str,
        body_ordinal: int,
        section_id: str,
        table_ordinal: int,
        nested: bool = False,
    ) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
        table_id = self._object_id(document_id, "table", table_ordinal)
        rows = table.findall("w:tr", NS)
        table_values: list[list[str]] = []
        cell_specs: list[tuple[int, int, int, str, bool]] = []
        has_merge = False
        max_width = 0
        for row_index, row in enumerate(rows, start=1):
            values: list[str] = []
            logical_column = 1
            for cell in row.findall("w:tc", NS):
                cell_text = _compact_text("\n".join(self._paragraph_text(item) for item in cell.findall(".//w:p", NS)))
                properties = cell.find("w:tcPr", NS)
                grid_span = 1
                vertical_merge = False
                if properties is not None:
                    span = properties.find("w:gridSpan", NS)
                    if span is not None and (_attr(span, W, "val") or "1").isdigit():
                        grid_span = max(1, int(_attr(span, W, "val") or "1"))
                    vertical_merge = properties.find("w:vMerge", NS) is not None
                merged = grid_span > 1 or vertical_merge
                has_merge = has_merge or merged
                cell_specs.append((row_index, logical_column, grid_span, cell_text, merged))
                values.extend([cell_text] + [""] * (grid_span - 1))
                logical_column += grid_span
            table_values.append(values)
            max_width = max(max_width, len(values))
        for values in table_values:
            values.extend([""] * (max_width - len(values)))
        table_record = self._record(
            document_id=document_id,
            source_sha256=source_sha256,
            object_type="table",
            object_id=table_id,
            status="partial" if has_merge or nested else "supported",
            structural_locator={"part": "word/document.xml", "body_ordinal": body_ordinal, "section_id": section_id, "nested": nested},
            canonical_value="\n".join(" | ".join(row) for row in table_values),
            witness="\n".join(" | ".join(row) for row in table_values),
        )
        table_record["row_count"] = len(table_values)
        table_record["column_count"] = max_width
        table_record["has_merged_cells"] = has_merge
        table_record["nested"] = nested
        records = [table_record]
        row_ids: dict[int, str] = {}
        for row_index, values in enumerate(table_values, start=1):
            row_id = self._object_id(document_id, "row", table_ordinal * 100_000 + row_index)
            row_ids[row_index] = row_id
            row_record = self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="row",
                object_id=row_id,
                status=table_record["status"],
                structural_locator={
                    "part": "word/document.xml",
                    "body_ordinal": body_ordinal,
                    "table_id": table_id,
                    "row": row_index,
                },
                canonical_value=" | ".join(values),
                witness=" | ".join(values),
            )
            row_record["table_id"] = table_id
            row_record["row"] = row_index
            records.append(row_record)
        for row_index, column, grid_span, value, merged in cell_specs:
            cell_id = self._object_id(document_id, "cell", table_ordinal * 100_000 + row_index * 1_000 + column)
            record = self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="cell",
                object_id=cell_id,
                status="partial" if merged else table_record["status"],
                structural_locator={
                    "part": "word/document.xml",
                    "body_ordinal": body_ordinal,
                    "table_id": table_id,
                    "row": row_index,
                    "column": column,
                    "grid_span": grid_span,
                },
                canonical_value=value,
                witness=value,
            )
            # Top-level fields intentionally match Bundle 2.0 TableCellLocator.
            record["table_id"] = table_id
            record["row"] = row_index
            record["column"] = column
            record["grid_span"] = grid_span
            record["row_id"] = row_ids[row_index]
            records.append(record)
        return records, self._table_markdown(table_values), table_record

    @staticmethod
    def _table_markdown(rows: list[list[str]]) -> list[str]:
        if not rows:
            return []
        width = max(1, max(len(row) for row in rows))
        normalized = [row + [""] * (width - len(row)) for row in rows]
        def render(row: list[str]) -> str:
            return "| " + " | ".join(value.replace("|", "\\|") for value in row) + " |"
        lines = [render(normalized[0]), "| " + " | ".join("---" for _ in range(width)) + " |"]
        lines.extend(render(row) for row in normalized[1:])
        return lines

    @staticmethod
    def _paragraph_style(paragraph: etree._Element, styles: dict[str, str]) -> tuple[str, str]:
        style = paragraph.find("w:pPr/w:pStyle", NS)
        style_id = _attr(style, W, "val") if style is not None else ""
        return style_id or "", styles.get(style_id or "", style_id or "Normal")

    @staticmethod
    def _heading_level(style_id: str, style_name: str) -> int | None:
        joined = f"{style_id} {style_name}".lower().replace(" ", "")
        match = re.search(r"heading([1-9])", joined)
        return int(match.group(1)) if match else None

    @staticmethod
    def _is_list(paragraph: etree._Element, style_name: str) -> bool:
        return paragraph.find("w:pPr/w:numPr", NS) is not None or "list" in style_name.lower()

    @staticmethod
    def _paragraph_has_rich_object(paragraph: etree._Element) -> bool:
        return bool(
            paragraph.xpath(
                ".//w:drawing | .//v:shape | .//o:OLEObject | .//m:oMath",
                namespaces=NS,
            )
        )

    @staticmethod
    def _paragraph_text(paragraph: etree._Element) -> str:
        pieces: list[str] = []
        for element in paragraph.iter():
            if element.tag == _tag(W, "t"):
                pieces.append(element.text or "")
            elif element.tag == _tag(W, "tab"):
                pieces.append("\t")
            elif element.tag in {_tag(W, "br"), _tag(W, "cr")}:
                pieces.append("\n")
        return _compact_text("".join(pieces))

    @staticmethod
    def _object_id(document_id: str, kind: str, ordinal: int) -> str:
        return f"{document_id}:{kind}:{ordinal:05d}"

    @staticmethod
    def _record(
        *,
        document_id: str,
        source_sha256: str,
        object_type: str,
        object_id: str,
        status: str,
        structural_locator: dict[str, Any],
        canonical_value: str,
        witness: str,
    ) -> dict[str, Any]:
        return {
            "record_type": "canonical_object",
            "document_id": document_id,
            "source_sha256": source_sha256,
            "object_type": object_type,
            "object_id": object_id,
            "status": status,
            "structural_locator": structural_locator,
            "canonical_value": canonical_value,
            "witness": witness,
        }

    @staticmethod
    def _normalize_markdown(lines: Iterable[str]) -> str:
        output: list[str] = []
        for line in lines:
            value = line.rstrip()
            if not value:
                continue
            if value.startswith("|") and output and output[-1].startswith("|"):
                output.append(value)
            else:
                if output and output[-1] != "":
                    output.append("")
                output.append(value)
        return "\n".join(output).strip() + "\n"

    @staticmethod
    def _package_diagnostics(
        package: zipfile.ZipFile,
        document: etree._Element,
        notes: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        names = {item.filename for item in package.infolist()}
        body = document.find("w:body", NS)
        return {
            "parts": {
                "footnotes": "word/footnotes.xml" in names,
                "endnotes": "word/endnotes.xml" in names,
                "comments": "word/comments.xml" in names,
                "styles": "word/styles.xml" in names,
                "document_relationships": "word/_rels/document.xml.rels" in names,
            },
            "body": {
                "tables": len(document.findall(".//w:tbl", NS)),
                "body_tables": len(body.findall("w:tbl", NS)) if body is not None else 0,
                "nested_tables": len(document.findall(".//w:tc/w:tbl", NS)),
                "bookmarks": len(document.findall(".//w:bookmarkStart", NS)),
                "omml_equations": len(document.findall(".//m:oMath", NS)),
                "vml_shapes": len(document.findall(".//v:shape", NS)),
                "ole_objects": len(document.findall(".//o:OLEObject", NS)),
                "inline_drawings": len(document.findall(".//wp:inline", NS)),
                "anchored_drawings": len(document.findall(".//wp:anchor", NS)),
            },
            "note_definitions": {kind: len(values) for kind, values in notes.items()},
            "page_numbers": {
                "policy": "supplementary_review_metadata_only",
                "canonical_locator": False,
            },
        }

    @staticmethod
    def _diagnostics(
        *,
        records: list[dict[str, Any]],
        extraction: dict[str, Any],
        package_diagnostics: dict[str, Any],
        document_id: str,
        source_sha256: str,
        canonical_digest: str,
    ) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for record in records:
            by_status[record["status"]] = by_status.get(record["status"], 0) + 1
            by_type[record["object_type"]] = by_type.get(record["object_type"], 0) + 1
        return {
            "document_id": document_id,
            "source_sha256": source_sha256,
            "canonical_digest": canonical_digest,
            "canonicalizer": CANONICALIZER_VERSION,
            "record_count": len(records),
            "records_by_status": dict(sorted(by_status.items())),
            "records_by_object_type": dict(sorted(by_type.items())),
            "support_policy": {
                "supported": ["body headings", "paragraphs", "lists", "resolved tables", "inline images", "captions", "bookmarks", "hyperlinks"],
                "partial": ["merged tables", "caption association", "OMML surface extraction", "floating/VML shapes", "body-anchored notes", "cross-reference fields"],
                "unsupported": ["OLE embedded objects", "unresolvable drawing/chart/SmartArt semantics", "unanchored notes"],
            },
            "package": package_diagnostics,
            "extraction": extraction,
        }
