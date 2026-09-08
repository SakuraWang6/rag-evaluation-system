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

from rag_eval.authoring.canonical_adapter import LegacyDocxCanonicalAdapter
from rag_eval.authoring.models import CanonicalView
from rag_eval.canonical.conformance import CanonicalConformanceSuite
from rag_eval.contracts.canonical import CANONICAL_SCHEMA_VERSION, canonical_json
from rag_eval.storage.atomic import atomic_write_bytes, atomic_write_json


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
V = "urn:schemas-microsoft-com:vml"
O = "urn:schemas-microsoft-com:office:office"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W, "r": R, "m": M, "a": A, "wp": WP, "v": V, "o": O, "rel": REL}
CANONICALIZER_VERSION = "rag-eval-authoring-canonicalizer/6"


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
    contract_manifest_path: Path
    contract_objects_path: Path
    contract_relations_path: Path
    canonical_contract_digest: str
    conformance_path: Path
    conformance_digest: str
    conformance_sha256: str
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
            canonical_contract_schema_version=CANONICAL_SCHEMA_VERSION,
            canonical_contract_digest=self.canonical_contract_digest,
            canonical_contract_manifest_path=str(self.contract_manifest_path.relative_to(root)),
            canonical_contract_objects_path=str(self.contract_objects_path.relative_to(root)),
            canonical_contract_relations_path=str(self.contract_relations_path.relative_to(root)),
            canonical_conformance_path=str(self.conformance_path.relative_to(root)),
            canonical_conformance_digest=self.conformance_digest,
            canonical_conformance_sha256=self.conformance_sha256,
        )


class DocxCanonicalizer:
    """Extract ordered, observable OOXML records with stable source-derived IDs."""

    def canonicalize(
        self,
        *,
        source_path: Path,
        output_root: Path,
        source_sha256: str,
        configuration_digest: str,
        parser_identity: str = "rag-eval-authoring-ooxml/1",
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
            media_resources = self._media_resources(package)
            notes = self._notes(package)
            records, markdown, extraction = self._body_records(
                document=document,
                styles=styles,
                relationships=relationships,
                media_resources=media_resources,
                notes=notes,
                document_id=document_id,
                source_sha256=source_sha256,
            )
            package_diagnostics = self._package_diagnostics(package, document, notes)

        base_records = [self._base_record(record) for record in records]
        provisional_contract = LegacyDocxCanonicalAdapter().adapt(
            document_id=document_id,
            source_sha256=source_sha256,
            records=base_records,
            parser_identity=parser_identity,
            canonicalizer_identity=CANONICALIZER_VERSION,
            configuration_digest=configuration_digest,
        )
        legacy_gold_eligibility = {
            item.object_id: item.gold_evidence_eligible
            for item in provisional_contract.objects
        }
        suite = CanonicalConformanceSuite()
        provisional_conformance = suite.evaluate(provisional_contract)
        eligibility = suite.eligibility_attributes(provisional_conformance)
        base_records = [
            record | eligibility[str(record["object_id"])] for record in base_records
        ]
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
        contract = LegacyDocxCanonicalAdapter().adapt(
            document_id=document_id,
            source_sha256=source_sha256,
            records=records,
            parser_identity=parser_identity,
            canonicalizer_identity=CANONICALIZER_VERSION,
            configuration_digest=configuration_digest,
        )
        conformance = suite.evaluate(contract)
        if any(
            item.attributes.get("gold_evidence_eligible")
            != conformance.result_for(item.object_id).gold_evidence_eligible
            or item.attributes.get("gold_eligibility_policy")
            != conformance.policy_identity
            for item in contract.objects
        ):
            raise ValueError("canonical Gold eligibility projection is inconsistent")
        snapshot_dir = canonical_dir / "snapshots" / contract.manifest.canonical_digest
        contract_manifest_path = snapshot_dir / "manifest.json"
        contract_objects_path = snapshot_dir / "objects.jsonl"
        contract_relations_path = snapshot_dir / "relations.jsonl"
        conformance_path = snapshot_dir / "conformance.json"
        manifest_payload = (canonical_json(contract.manifest) + "\n").encode("utf-8")
        objects_payload = "".join(
            canonical_json(item) + "\n" for item in contract.objects
        ).encode("utf-8")
        relations_payload = "".join(
            canonical_json(item) + "\n" for item in contract.relations
        ).encode("utf-8")
        conformance_payload = (canonical_json(conformance) + "\n").encode("utf-8")
        conformance_sha256 = hashlib.sha256(conformance_payload).hexdigest()
        for path, payload in (
            (contract_manifest_path, manifest_payload),
            (contract_objects_path, objects_payload),
            (contract_relations_path, relations_payload),
            (conformance_path, conformance_payload),
        ):
            self._write_immutable_snapshot_file(path, payload)
        diagnostics = self._diagnostics(
            records=records,
            extraction=extraction,
            package_diagnostics=package_diagnostics,
            document_id=document_id,
            source_sha256=source_sha256,
            canonical_digest=canonical_digest,
        )
        diagnostics["canonical_contract"] = {
            "schema_version": CANONICAL_SCHEMA_VERSION,
            "canonical_digest": contract.manifest.canonical_digest,
            "objects_digest": contract.manifest.objects_digest,
            "relations_digest": contract.manifest.relations_digest,
            "object_count": contract.manifest.object_count,
            "relation_count": contract.manifest.relation_count,
        }
        diagnostics["canonical_conformance"] = {
            "schema_version": conformance.schema_version,
            "policy_identity": conformance.policy_identity,
            "report_digest": conformance.report_digest,
            "report_sha256": conformance_sha256,
            "gold_eligible_object_count": sum(
                item.gold_evidence_eligible for item in conformance.object_results
            ),
            "status_counts": {
                status: sum(
                    item.status == status for item in conformance.object_results
                )
                for status in ("conformant", "nonconformant", "not_evaluated")
            },
            "legacy_shadow": {
                "changed_object_count": sum(
                    legacy_gold_eligibility[item.object_id]
                    != item.gold_evidence_eligible
                    for item in conformance.object_results
                ),
                "changed_by_object_type": {
                    object_type: sum(
                        result.object_type.value == object_type
                        and legacy_gold_eligibility[result.object_id]
                        != result.gold_evidence_eligible
                        for result in conformance.object_results
                    )
                    for object_type in sorted(
                        {
                            result.object_type.value
                            for result in conformance.object_results
                            if legacy_gold_eligibility[result.object_id]
                            != result.gold_evidence_eligible
                        }
                    )
                },
            },
        }
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
                "canonical_contract": contract.manifest.model_dump(mode="json"),
                "canonical_conformance": diagnostics["canonical_conformance"],
                # Retain the conservative rich-content inventory alongside
                # the contract manifest.  It is diagnostic provenance, not a
                # claim that visual/OLE semantics have been interpreted.
                "rich_content": diagnostics.get("rich_content", {}),
                "package_rich_content": diagnostics.get("package", {}),
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
            contract_manifest_path=contract_manifest_path,
            contract_objects_path=contract_objects_path,
            contract_relations_path=contract_relations_path,
            canonical_contract_digest=contract.manifest.canonical_digest,
            conformance_path=conformance_path,
            conformance_digest=conformance.report_digest,
            conformance_sha256=conformance_sha256,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _base_record(record: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in record.items() if key != "canonical_digest"}

    @staticmethod
    def _write_immutable_snapshot_file(path: Path, payload: bytes) -> None:
        if path.exists():
            if path.read_bytes() != payload:
                raise ValueError(
                    f"immutable canonical Snapshot collision at {path.name}"
                )
            return
        atomic_write_bytes(path, payload)

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
    def _media_resources(package: zipfile.ZipFile) -> dict[str, dict[str, Any]]:
        """Index actual package media without inferring visual semantics.

        Relationship targets are relative to ``word/document.xml`` and are
        retained verbatim as map keys. The package member digest proves that a
        figure's referenced bytes were present in the source DOCX.
        """

        values: dict[str, dict[str, Any]] = {}
        for info in sorted(package.infolist(), key=lambda item: item.filename):
            if not info.filename.startswith("word/media/") or info.is_dir():
                continue
            payload = package.read(info.filename)
            target = info.filename.removeprefix("word/")
            values[target] = {
                "part": info.filename,
                "byte_count": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "format": Path(info.filename).suffix.casefold().removeprefix(".") or "unknown",
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
        media_resources: dict[str, dict[str, Any]],
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
        # Preserve top-level table IDs across this additive topology upgrade.
        # Nested tables retain the historical allocator range after all direct
        # body tables, while their parent-cell relation is now explicit.
        nested_table_ordinal = len(body.findall("w:tbl", NS))
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
        pending_caption: tuple[dict[str, Any], dict[str, Any] | None] | None = None
        media_object_ids: dict[str, str] = {}
        emitted_media_object_ids: set[str] = set()

        def mark_pending_caption_unresolved() -> None:
            """Downgrade an unresolvable caption and its text span together."""

            nonlocal pending_caption
            if pending_caption is None:
                return
            caption, caption_span = pending_caption
            caption["status"] = "partial"
            caption["association_method"] = "unresolved"
            if caption_span is not None:
                caption_span["status"] = "partial"
            extraction["partial_objects"].append(
                {
                    "object_id": caption["object_id"],
                    "reason": "unresolved_caption_association",
                }
            )
            pending_caption = None

        def associate_pending_caption(target: dict[str, Any]) -> None:
            """Attach a preposed caption only to the immediately next rich object."""

            nonlocal pending_caption
            if pending_caption is None:
                return
            caption, _caption_span = pending_caption
            expected = caption.get("caption_target_kind")
            if (
                (expected is not None and expected != target.get("object_type"))
                or target.get("paragraph_figure_count", 1) != 1
            ):
                mark_pending_caption_unresolved()
                return
            caption["associated_object_id"] = target["object_id"]
            caption["association_method"] = "adjacent_following_body_object"
            self._record_caption_association(caption, target)
            pending_caption = None

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
                caption_info = self._caption_info(text, style_name)
                is_caption = caption_info is not None
                is_list = self._is_list(child, style_name)
                block_kind = (
                    "heading" if heading_level is not None else
                    ("caption" if is_caption else ("list_item" if is_list else "paragraph"))
                )
                # A caption becomes partial only if neither adjacent direction
                # yields a table or figure target.  Starting it as supported
                # permits the common DOCX "caption before table" layout.
                status = "supported"
                if pending_caption is not None and (
                    is_caption or not self._paragraph_has_rich_object(child)
                ):
                    # Empty paragraphs are skipped above and therefore do not
                    # break adjacency.  Any other caption or prose does.
                    mark_pending_caption_unresolved()
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
                if caption_info is not None:
                    block_record.update(caption_info)
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
                    # Heading paragraphs can carry bookmarks and field-based
                    # cross references.  Preserve those source objects before
                    # moving to the next section; otherwise they silently
                    # disappear from the Canonical graph.
                    rich_records, figure_ordinal, equation_ordinal, reference_ordinal = self._paragraph_rich_records(
                        paragraph=child,
                        document_id=document_id,
                        source_sha256=source_sha256,
                        body_ordinal=body_ordinal,
                        section_id=current_section,
                        relationships=relationships,
                        media_resources=media_resources,
                        media_object_ids=media_object_ids,
                        emitted_media_object_ids=emitted_media_object_ids,
                        notes=notes,
                        paragraph_id=block_id,
                        figure_ordinal=figure_ordinal,
                        equation_ordinal=equation_ordinal,
                        reference_ordinal=reference_ordinal,
                        paragraph_text=text,
                    )
                    for rich_record in rich_records:
                        records.append(rich_record)
                        if rich_record["status"] != "supported":
                            extraction["partial_objects"].append(
                                {"object_id": rich_record["object_id"], "reason": rich_record["status"]}
                            )
                    last_associable = None
                    continue
                if (
                    is_caption
                    and last_associable is not None
                    and (
                        block_record.get("caption_target_kind") is None
                        or block_record.get("caption_target_kind") == last_associable.get("object_type")
                    )
                    and last_associable.get("paragraph_figure_count", 1) == 1
                ):
                    block_record["associated_object_id"] = last_associable["object_id"]
                    block_record["association_method"] = "adjacent_body_object"
                    self._record_caption_association(block_record, last_associable)
                records.append(block_record)
                if span_record is not None:
                    records.append(span_record)
                if text:
                    markdown.append(("- " if is_list else "") + text)
                rich_records, figure_ordinal, equation_ordinal, reference_ordinal = self._paragraph_rich_records(
                    paragraph=child,
                    document_id=document_id,
                    source_sha256=source_sha256,
                    body_ordinal=body_ordinal,
                    section_id=current_section,
                    relationships=relationships,
                    media_resources=media_resources,
                    media_object_ids=media_object_ids,
                    emitted_media_object_ids=emitted_media_object_ids,
                    notes=notes,
                    paragraph_id=block_id,
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
                # A caption may only be attached to a direct, immediately
                # preceding or following table/figure.  Paragraphs are never
                # valid ``caption_of`` targets, and no association is inferred
                # across prose or a second caption.
                if is_caption:
                    if "associated_object_id" not in block_record:
                        pending_caption = (block_record, span_record)
                    last_associable = None
                else:
                    figures = [
                        item for item in rich_records if item["object_type"] == "figure"
                    ]
                    for figure in figures:
                        figure["paragraph_figure_count"] = len(figures)
                    if pending_caption is not None:
                        if len(figures) == 1:
                            associate_pending_caption(figures[-1])
                        else:
                            mark_pending_caption_unresolved()
                    last_associable = figures[-1] if figures else None
                continue
            if child.tag == _tag(W, "tbl"):
                table_ordinal += 1
                table_records, table_markdown, table_record, nested_table_ordinal = self._table_records(
                    table=child,
                    document_id=document_id,
                    source_sha256=source_sha256,
                    body_ordinal=body_ordinal,
                    section_id=current_section,
                    table_ordinal=table_ordinal,
                    next_nested_table_ordinal=nested_table_ordinal,
                )
                records.extend(table_records)
                markdown.extend(table_markdown)
                associate_pending_caption(table_record)
                last_associable = table_record
                if table_record["status"] != "supported":
                    extraction["partial_objects"].append(
                        {
                            "object_id": table_record["object_id"],
                            "reason": table_record.get("topology_reason", "irregular_table_topology"),
                        }
                    )
        mark_pending_caption_unresolved()
        self._resolve_rich_content_context(records, extraction)
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
        media_resources: dict[str, dict[str, Any]],
        media_object_ids: dict[str, str],
        emitted_media_object_ids: set[str],
        notes: dict[str, dict[str, str]],
        paragraph_id: str,
        figure_ordinal: int,
        equation_ordinal: int,
        reference_ordinal: int,
        paragraph_text: str,
    ) -> tuple[list[dict[str, Any]], int, int, int]:
        records: list[dict[str, Any]] = []
        base_locator = {"part": "word/document.xml", "body_ordinal": body_ordinal, "section_id": section_id}
        for drawing_index, drawing in enumerate(paragraph.findall(".//w:drawing", NS), start=1):
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
            media_target = relationship.get("target")
            media = media_resources.get(media_target or "")
            resource_id: str | None = None
            if media_target and media is not None:
                resource_id = media_object_ids.setdefault(
                    media_target,
                    f"{document_id}:media:{media['sha256'][:16]}",
                )
                if resource_id not in emitted_media_object_ids:
                    resource = self._record(
                        document_id=document_id,
                        source_sha256=source_sha256,
                        object_type="media_resource",
                        object_id=resource_id,
                        status="supported",
                        structural_locator={
                            "part": str(media["part"]),
                            "relationship_id": relation_id or "",
                        },
                        canonical_value=str(media_target),
                        witness=str(media_target),
                    )
                    resource.update(
                        {
                            "resource_digest": media["sha256"],
                            "resource_format": media["format"],
                            "resource_byte_count": media["byte_count"],
                            "semantic_status": "structural_only",
                            "visual_semantic_status": "unverified",
                            "gold_evidence_eligible": False,
                            "additional_structural_locators": (
                                {
                                    "part": "word/_rels/document.xml.rels",
                                    "relationship_id": relation_id or "",
                                },
                            ),
                        }
                    )
                    records.append(resource)
                    emitted_media_object_ids.add(resource_id)
            name = doc_pr.get("name") if doc_pr is not None else None
            description = doc_pr.get("descr") if doc_pr is not None else None
            title = doc_pr.get("title") if doc_pr is not None else None
            extent = drawing_item.find("wp:extent", NS)
            value = _compact_text(description or title or name or media_target or "image resource")
            supported = resource_id is not None
            record = self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="figure",
                object_id=self._object_id(document_id, "figure", figure_ordinal),
                status="supported" if supported else "partial",
                structural_locator=base_locator
                | {
                    "drawing": "inline" if inline is not None else "anchor",
                    "drawing_ordinal": drawing_index,
                    "relationship_id": relation_id or "",
                },
                canonical_value=value,
                witness=value,
            )
            record.update(
                {
                    "paragraph_object_id": paragraph_id,
                    "resource_object_id": resource_id,
                    "resource_relationship_id": relation_id,
                    "media_target": media_target,
                    "anchor_kind": "inline" if inline is not None else "anchor",
                    "docpr_id": doc_pr.get("id") if doc_pr is not None else None,
                    "docpr_name": name,
                    "alt_text": description,
                    "title": title,
                    "width_emu": int(extent.get("cx")) if extent is not None and (extent.get("cx") or "").isdigit() else None,
                    "height_emu": int(extent.get("cy")) if extent is not None and (extent.get("cy") or "").isdigit() else None,
                    "semantic_status": "structural_only",
                    "visual_semantic_status": "unverified",
                    "caption_relation_status": "unresolved",
                    "reference_relation_status": "unresolved",
                    "gold_evidence_eligible": False,
                }
            )
            records.append(record)
        for index, shape in enumerate(paragraph.findall(".//v:shape", NS), start=1):
            figure_ordinal += 1
            value = _compact_text(shape.get("alt") or shape.get("title") or shape.get("id") or "VML shape")
            image_data = shape.find("v:imagedata", NS)
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
                | {
                    "paragraph_object_id": paragraph_id,
                    "storage": "vml_shape",
                    "vml_shape_id": shape.get("id"),
                    "vml_shape_type": shape.get("type"),
                    "vml_title": shape.get("title"),
                    "vml_alt": shape.get("alt"),
                    "vml_relationship_id": _attr(image_data, R, "id") if image_data is not None else None,
                    "semantic_status": "unverified",
                    "visual_semantic_status": "unverified",
                    "gold_evidence_eligible": False,
                    "reason": "vml_visual_or_equation_semantics_not_canonicalized",
                }
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
                | {
                    "paragraph_object_id": paragraph_id,
                    "reason": "embedded_object_not_interpreted",
                    "gold_evidence_eligible": False,
                }
            )
        # ``m:oMathPara`` normally contains ``m:oMath`` children.  Treat the
        # paragraph wrapper as one displayed equation and exclude its nested
        # math children, otherwise a single OMML expression is emitted twice.
        equation_paragraphs = list(paragraph.findall(".//m:oMathPara", NS))

        def is_wrapped_math(item: etree._Element) -> bool:
            parent = item.getparent()
            while parent is not None and parent is not paragraph:
                if parent.tag == _tag(M, "oMathPara"):
                    return True
                parent = parent.getparent()
            return False

        equation_elements = equation_paragraphs + [
            item
            for item in paragraph.findall(".//m:oMath", NS)
            if not is_wrapped_math(item)
        ]
        for index, equation in enumerate(equation_elements, start=1):
            equation_ordinal += 1
            surface = _compact_text("".join(equation.xpath(".//m:t/text()", namespaces=NS)))
            raw_omml = etree.tostring(equation, with_tail=False, encoding="unicode")
            raw_digest = hashlib.sha256(raw_omml.encode("utf-8")).hexdigest()
            record = self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="equation",
                object_id=self._object_id(document_id, "equation", equation_ordinal),
                status="supported",
                structural_locator=base_locator | {"equation_ordinal": index, "raw_xml_sha256": raw_digest},
                canonical_value=surface or "OMML equation",
                witness=surface or "OMML equation",
            )
            record.update(
                {
                    "paragraph_object_id": paragraph_id,
                    "placement": "block" if equation.tag == _tag(M, "oMathPara") else "inline",
                    "raw_omml": raw_omml,
                    "raw_omml_sha256": raw_digest,
                    "omml_tree": self._omml_tree(equation),
                    "presentation_text": surface or "OMML equation",
                    "representation": "omml_structural_tree_and_surface_text",
                    "semantic_status": "textual_context_available",
                    "gold_evidence_eligible": False,
                }
            )
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
            record["paragraph_object_id"] = paragraph_id
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
        figure_mentions = list(
            re.finditer(
                r"(?:如图|见图)\s*([0-9]+(?:\s*[-.]\s*[0-9]+)*)|图\s*([0-9]+(?:\s*[-.]\s*[0-9]+)*)\s*所示",
                paragraph_text,
                re.IGNORECASE,
            )
        )
        seen_figure_numbers: set[str] = set()
        for index, match in enumerate(figure_mentions, start=1):
            figure_number = re.sub(r"\s+", "", match.group(1) or match.group(2) or "")
            if not figure_number or figure_number in seen_figure_numbers:
                continue
            seen_figure_numbers.add(figure_number)
            reference_ordinal += 1
            record = self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="reference",
                object_id=self._object_id(document_id, "figure_reference", reference_ordinal),
                status="partial",
                structural_locator=base_locator
                | {
                    "textual_figure_reference_ordinal": index,
                    "figure_number": figure_number,
                },
                canonical_value=paragraph_text,
                witness=paragraph_text,
            )
            record.update(
                {
                    "reference_kind": "figure_textual_reference",
                    "figure_number": figure_number,
                    "referencing_paragraph_id": paragraph_id,
                    "resolution_status": "unresolved",
                }
            )
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
        next_nested_table_ordinal: int,
        nested: bool = False,
        parent_cell_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[str], dict[str, Any], int]:
        """Preserve physical OOXML cells and recover a safe logical grid.

        A physical ``w:tc`` is never discarded when it participates in a
        merge.  It maps to one logical cell instead.  The mapping is emitted
        only when the ``tblGrid`` and the ``gridSpan``/``vMerge`` sequence make
        the grid unique; otherwise the observed physical cells remain partial.
        """

        table_id = self._object_id(document_id, "table", table_ordinal)
        rows = table.findall("w:tr", NS)
        table_grid = table.find("w:tblGrid", NS)
        grid_width = len(table_grid.findall("w:gridCol", NS)) if table_grid is not None else 0
        errors: list[str] = []
        classifications: set[str] = set()
        if not rows:
            errors.append("missing_rows")

        physical_cells: list[dict[str, Any]] = []
        logical_cells: list[dict[str, Any]] = []
        active_vertical: dict[int, dict[str, Any]] = {}
        header_rows: list[int] = []
        saw_horizontal = False
        saw_vertical = False
        observed_widths: list[int] = []

        for row_index, row in enumerate(rows, start=1):
            row_properties = row.find("w:trPr", NS)
            grid_before = self._table_grid_offset(row_properties, "gridBefore")
            grid_after = self._table_grid_offset(row_properties, "gridAfter")
            if grid_before is None or grid_after is None:
                errors.append(f"invalid_row_grid_offset:{row_index}")
                grid_before, grid_after = 0, 0
            if grid_before or grid_after:
                classifications.add("irregular_grid")
                errors.append(f"grid_offset:{row_index}")
            if row_properties is not None and row_properties.find("w:tblHeader", NS) is not None:
                header_rows.append(row_index)
            cursor = 1 + grid_before
            next_active: dict[int, dict[str, Any]] = {}
            row_cells = row.findall("w:tc", NS)
            if not row_cells:
                errors.append(f"empty_physical_row:{row_index}")
            for physical_index, cell in enumerate(row_cells, start=1):
                properties = cell.find("w:tcPr", NS)
                raw_span, span_is_valid, span_was_explicit = self._table_grid_span(properties)
                if not span_is_valid:
                    errors.append(f"invalid_grid_span:{row_index}:{physical_index}")
                merge_kind = self._vertical_merge_kind(properties)
                if merge_kind == "invalid":
                    errors.append(f"invalid_vMerge:{row_index}:{physical_index}")
                    merge_kind = "none"
                if merge_kind == "continue" and not span_was_explicit and cursor in active_vertical:
                    raw_span = int(active_vertical[cursor]["column_span"])
                if raw_span < 1:
                    errors.append(f"invalid_effective_span:{row_index}:{physical_index}")
                    raw_span = 1
                end_column = cursor + raw_span - 1
                if grid_width and end_column > grid_width:
                    errors.append(f"grid_overflow:{row_index}:{physical_index}")
                if raw_span > 1:
                    saw_horizontal = True
                if merge_kind != "none":
                    saw_vertical = True
                cell_id = self._object_id(
                    document_id,
                    "cell",
                    table_ordinal * 100_000 + row_index * 1_000 + physical_index,
                )
                direct_text = _compact_text(
                    "\n".join(self._paragraph_text(item) for item in cell.findall("w:p", NS))
                )
                physical = {
                    "element": cell,
                    "cell_id": cell_id,
                    "row": row_index,
                    "physical_index": physical_index,
                    "column": cursor,
                    "column_span": raw_span,
                    "end_column": end_column,
                    "merge_kind": merge_kind,
                    "text": direct_text,
                    "logical": None,
                }
                if merge_kind == "continue":
                    origins = {
                        id(active_vertical[column]): active_vertical[column]
                        for column in range(cursor, end_column + 1)
                        if column in active_vertical
                    }
                    if len(origins) != 1 or any(
                        column not in active_vertical
                        for column in range(cursor, end_column + 1)
                    ):
                        errors.append(f"orphan_or_ambiguous_vMerge_continue:{row_index}:{physical_index}")
                    else:
                        logical = next(iter(origins.values()))
                        if logical["column_span"] != raw_span:
                            errors.append(f"vMerge_span_mismatch:{row_index}:{physical_index}")
                        else:
                            logical["row_end"] = row_index
                            logical["physical"].append(physical)
                            physical["logical"] = logical
                            for column in range(cursor, end_column + 1):
                                next_active[column] = logical
                else:
                    logical = {
                        "row_start": row_index,
                        "row_end": row_index,
                        "column": cursor,
                        "column_span": raw_span,
                        "text": direct_text,
                        "physical": [physical],
                    }
                    physical["logical"] = logical
                    logical_cells.append(logical)
                    if merge_kind == "restart":
                        for column in range(cursor, end_column + 1):
                            next_active[column] = logical
                physical_cells.append(physical)
                cursor = end_column + 1
            effective_width = cursor - 1 + grid_after
            observed_widths.append(effective_width)
            if grid_width and effective_width != grid_width:
                classifications.add("irregular_grid")
                errors.append(f"grid_width_mismatch:{row_index}:{effective_width}:{grid_width}")
            active_vertical = next_active

        if saw_horizontal:
            classifications.add("horizontal_merge")
        if saw_vertical:
            classifications.add("vertical_merge")
        if saw_horizontal and saw_vertical:
            classifications.add("mixed_merge")
        if header_rows:
            expected_headers = list(range(1, len(header_rows) + 1))
            if header_rows != expected_headers:
                errors.append("non_contiguous_explicit_header_rows")
            elif len(header_rows) > 1:
                classifications.add("multi_level_header")
            else:
                classifications.add("header_row")
        header_column_count = 1 if self._table_has_explicit_first_column_header(table) else 0
        if header_column_count:
            classifications.add("header_column")
        if not classifications:
            classifications.add("regular")

        # A missing ``tblGrid`` is not sufficient to claim a complete logical
        # topology, but the directly observed physical columns can still be
        # represented for diagnostics and fail-closed partial objects.
        logical_width = grid_width or max(
            (item["end_column"] for item in physical_cells), default=0
        )
        if logical_width <= 0:
            errors.append("no_observed_columns")
        if grid_width <= 0:
            # Older DOCX producers sometimes omit ``tblGrid`` for a simple
            # rectangular table.  Its topology is still uniquely observable
            # when every physical row has the same width and there are no
            # merge semantics.  Complex/unequal shapes remain fail-closed.
            if saw_horizontal or saw_vertical or len(set(observed_widths)) != 1:
                errors.append("missing_tblGrid_for_complex_or_irregular_topology")
            else:
                classifications.add("inferred_regular_grid")
        topology_complete = not errors
        table_status = "supported" if topology_complete else "partial"
        table_values = self._logical_table_values(logical_cells, len(rows), logical_width)
        locator = {
            "part": "word/document.xml",
            "body_ordinal": body_ordinal,
            "section_id": section_id,
            "nested": nested,
        }
        if parent_cell_id:
            locator["parent_cell_id"] = parent_cell_id
        table_record = self._record(
            document_id=document_id,
            source_sha256=source_sha256,
            object_type="table",
            object_id=table_id,
            status=table_status,
            structural_locator=locator,
            canonical_value="\n".join(" | ".join(row) for row in table_values),
            witness="\n".join(" | ".join(row) for row in table_values),
        )
        table_record.update(
            {
                "row_count": len(rows),
                "column_count": logical_width,
                "table_grid_column_count": grid_width,
                "physical_row_count": len(rows),
                "physical_cell_count": len(physical_cells),
                "logical_row_count": len(rows),
                "logical_column_count": logical_width,
                "logical_cell_count": len(logical_cells),
                "has_merged_cells": saw_horizontal or saw_vertical,
                "nested": nested,
                "topology_status": "complete" if topology_complete else "partial",
                "topology_errors": tuple(sorted(set(errors))),
                "table_structure_classes": tuple(sorted(classifications)),
                "header_row_count": len(header_rows) if header_rows == list(range(1, len(header_rows) + 1)) else 0,
                "header_column_count": header_column_count,
                "parent_cell_id": parent_cell_id,
                "nested_table_ids": (),
            }
        )
        header_count = int(table_record["header_row_count"])
        table_gold_eligible = bool(
            table_status == "supported"
            and (header_count or header_column_count)
            and any(
                item["row_start"] > header_count
                and (not header_column_count or item["column"] > header_column_count)
                for item in logical_cells
            )
        )
        table_record["gold_evidence_eligible"] = table_gold_eligible
        records: list[dict[str, Any]] = [table_record]
        row_ids: dict[int, str] = {}
        logical_row_ids: dict[int, str] = {}
        logical_column_ids: dict[int, str] = {}
        for row_index, values in enumerate(table_values, start=1):
            row_id = self._object_id(document_id, "row", table_ordinal * 100_000 + row_index)
            logical_row_id = self._object_id(document_id, "logical_row", table_ordinal * 100_000 + row_index)
            row_ids[row_index] = row_id
            logical_row_ids[row_index] = logical_row_id
            for kind, object_id, object_type in (
                ("physical", row_id, "row"),
                ("logical", logical_row_id, "logical_row"),
            ):
                row_record = self._record(
                    document_id=document_id,
                    source_sha256=source_sha256,
                    object_type=object_type,
                    object_id=object_id,
                    status=table_status,
                    structural_locator={
                        "part": "word/document.xml",
                        "body_ordinal": body_ordinal,
                        "table_id": table_id,
                        "row": row_index,
                        "row_kind": kind,
                    },
                    canonical_value=" | ".join(values),
                    witness=" | ".join(values),
                )
                row_record.update(
                    {
                        "table_id": table_id,
                        "row": row_index,
                        "row_kind": kind,
                        "gold_evidence_eligible": table_gold_eligible,
                    }
                )
                records.append(row_record)
        for column in range(1, logical_width + 1):
            column_id = self._object_id(document_id, "logical_column", table_ordinal * 100_000 + column)
            logical_column_ids[column] = column_id
            column_record = self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="logical_column",
                object_id=column_id,
                status=table_status,
                structural_locator={
                    "part": "word/document.xml",
                    "body_ordinal": body_ordinal,
                    "table_id": table_id,
                    "column": column,
                },
                canonical_value=f"column {column}",
                witness=f"logical column {column}",
            )
            column_record.update(
                {
                    "table_id": table_id,
                    "column": column,
                    "gold_evidence_eligible": table_gold_eligible,
                }
            )
            records.append(column_record)

        for logical in logical_cells:
            logical_cell_id = self._object_id(
                document_id,
                "logical_cell",
                table_ordinal * 100_000_000 + logical["row_start"] * 1_000 + logical["column"],
            )
            logical["logical_cell_id"] = logical_cell_id
        for logical in logical_cells:
            covered = tuple(
                {"row": row, "column": column}
                for row in range(logical["row_start"], logical["row_end"] + 1)
                for column in range(logical["column"], logical["column"] + logical["column_span"])
            )
            is_header = bool(
                (header_count and logical["row_end"] <= header_count)
                or (header_column_count and logical["column"] <= header_column_count)
            )
            effective_headers: list[dict[str, Any]] = []
            if header_count and logical["row_start"] > header_count:
                for header_row in range(1, header_count + 1):
                    header = next(
                        (
                            candidate
                            for candidate in logical_cells
                            if candidate["row_start"] <= header_row <= candidate["row_end"]
                            and candidate["column"] <= logical["column"] < candidate["column"] + candidate["column_span"]
                        ),
                        None,
                    )
                    if header is not None and header.get("logical_cell_id"):
                        effective_headers.append(header)
            if header_column_count and logical["column"] > header_column_count:
                row_header = next(
                    (
                        candidate
                        for candidate in logical_cells
                        if candidate["row_start"] <= logical["row_start"] <= candidate["row_end"]
                        and candidate["column"] <= header_column_count < candidate["column"] + candidate["column_span"]
                    ),
                    None,
                )
                if row_header is not None and row_header not in effective_headers and row_header.get("logical_cell_id"):
                    effective_headers.append(row_header)
            origin = logical["physical"][0]
            logical_locator = {
                "part": "word/document.xml",
                "body_ordinal": body_ordinal,
                "table_id": table_id,
                "row": logical["row_start"],
                "column": logical["column"],
                "logical": True,
            }
            logical_record = self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="logical_cell",
                object_id=logical["logical_cell_id"],
                status=table_status,
                structural_locator=logical_locator,
                canonical_value=logical["text"],
                witness=logical["text"],
            )
            logical_record.update(
                {
                    "table_id": table_id,
                    "logical_row_id": logical_row_ids[logical["row_start"]],
                    "logical_column_ids": tuple(
                        logical_column_ids[column]
                        for column in range(logical["column"], logical["column"] + logical["column_span"])
                        if column in logical_column_ids
                    ),
                    "logical_row_start": logical["row_start"],
                    "logical_row_end": logical["row_end"],
                    "logical_column_start": logical["column"],
                    "logical_column_end": logical["column"] + logical["column_span"] - 1,
                    "row_span": logical["row_end"] - logical["row_start"] + 1,
                    "column_span": logical["column_span"],
                    "origin_physical_cell_id": origin["cell_id"],
                    "covered_logical_coordinates": covered,
                    "is_header": is_header,
                    "effective_header_ids": tuple(item["logical_cell_id"] for item in effective_headers),
                    "effective_header_path": tuple(item["text"] for item in effective_headers),
                    "gold_evidence_eligible": table_gold_eligible,
                    "derived_from_object_ids": tuple(item["cell_id"] for item in logical["physical"]),
                    "additional_structural_locators": tuple(
                        {
                            "part": "word/document.xml",
                            "body_ordinal": body_ordinal,
                            "table_id": table_id,
                            "row": item["row"],
                            "column": item["column"],
                            "physical_cell_index": item["physical_index"],
                        }
                        for item in logical["physical"][1:]
                    ),
                }
            )
            records.append(logical_record)

        cell_records: dict[str, dict[str, Any]] = {}
        for physical in physical_cells:
            logical = physical["logical"]
            logical_cell_id = logical.get("logical_cell_id") if logical else None
            origin_id = logical["physical"][0]["cell_id"] if logical else None
            covered = (
                tuple(
                    {"row": row, "column": column}
                    for row in range(logical["row_start"], logical["row_end"] + 1)
                    for column in range(logical["column"], logical["column"] + logical["column_span"])
                )
                if logical
                else ()
            )
            record = self._record(
                document_id=document_id,
                source_sha256=source_sha256,
                object_type="cell",
                object_id=physical["cell_id"],
                status=table_status if logical else "partial",
                structural_locator={
                    "part": "word/document.xml",
                    "body_ordinal": body_ordinal,
                    "table_id": table_id,
                    "row": physical["row"],
                    "column": physical["column"],
                    "grid_span": physical["column_span"],
                    "physical_cell_index": physical["physical_index"],
                    "v_merge": physical["merge_kind"],
                },
                canonical_value=physical["text"],
                witness=physical["text"],
            )
            record.update(
                {
                    # Top-level fields intentionally retain Bundle 2.0's
                    # table/cell locator projection.
                    "table_id": table_id,
                    "row": physical["row"],
                    "column": physical["column"],
                    "grid_span": physical["column_span"],
                    "row_id": row_ids[physical["row"]],
                    "physical_cell_index": physical["physical_index"],
                    "v_merge": physical["merge_kind"],
                    "logical_cell_id": logical_cell_id,
                    "merged_cell_origin_physical_id": origin_id,
                    "covered_logical_coordinates": covered,
                    "row_span": (logical["row_end"] - logical["row_start"] + 1) if logical else None,
                    "column_span": logical["column_span"] if logical else None,
                    "nested_table_ids": (),
                    "gold_evidence_eligible": table_gold_eligible,
                }
            )
            cell_records[physical["cell_id"]] = record
            records.append(record)

        nested_ids: list[str] = []
        for physical in physical_cells:
            direct_nested = physical["element"].findall("w:tbl", NS)
            for nested_table in direct_nested:
                next_nested_table_ordinal += 1
                nested_records, _nested_markdown, nested_record, next_nested_table_ordinal = self._table_records(
                    table=nested_table,
                    document_id=document_id,
                    source_sha256=source_sha256,
                    body_ordinal=body_ordinal,
                    section_id=section_id,
                    table_ordinal=next_nested_table_ordinal,
                    next_nested_table_ordinal=next_nested_table_ordinal,
                    nested=True,
                    parent_cell_id=physical["cell_id"],
                )
                records.extend(nested_records)
                nested_ids.append(nested_record["object_id"])
                cell_records[physical["cell_id"]]["nested_table_ids"] = tuple(
                    (*cell_records[physical["cell_id"]]["nested_table_ids"], nested_record["object_id"])
                )
        if nested_ids:
            classifications.add("nested_table")
            table_record["nested_table_ids"] = tuple(nested_ids)
            table_record["table_structure_classes"] = tuple(sorted(classifications))
            table_record["status"] = "partial"
            table_record["topology_status"] = "partial"
            table_record["topology_reason"] = "nested_table_content_is_separate"
            table_record["gold_evidence_eligible"] = False
            for record in records:
                if record.get("object_id") in {table_id, *row_ids.values(), *logical_row_ids.values(), *logical_column_ids.values()}:
                    record["status"] = "partial"
                if record.get("table_id") == table_id and record.get("object_type") in {"cell", "logical_cell"}:
                    record["status"] = "partial"
                if record.get("object_id") in {table_id, *row_ids.values(), *logical_row_ids.values(), *logical_column_ids.values()} or record.get("table_id") == table_id:
                    record["gold_evidence_eligible"] = False
        if table_record["status"] != "supported" and "topology_reason" not in table_record:
            table_record["topology_reason"] = ";".join(table_record["topology_errors"]) or "partial_table_topology"
        return records, self._table_markdown(table_values), table_record, next_nested_table_ordinal

    @staticmethod
    def _table_grid_offset(properties: etree._Element | None, name: str) -> int | None:
        if properties is None:
            return 0
        element = properties.find(f"w:{name}", NS)
        if element is None:
            return 0
        value = _attr(element, W, "val") or "0"
        return int(value) if value.isdigit() else None

    @staticmethod
    def _table_grid_span(properties: etree._Element | None) -> tuple[int, bool, bool]:
        if properties is None:
            return 1, True, False
        element = properties.find("w:gridSpan", NS)
        if element is None:
            return 1, True, False
        value = _attr(element, W, "val") or "1"
        if not value.isdigit() or int(value) < 1:
            return 1, False, True
        return int(value), True, True

    @staticmethod
    def _vertical_merge_kind(properties: etree._Element | None) -> str:
        if properties is None:
            return "none"
        element = properties.find("w:vMerge", NS)
        if element is None:
            return "none"
        value = _attr(element, W, "val")
        if value in (None, "", "continue"):
            return "continue"
        if value == "restart":
            return "restart"
        return "invalid"

    @staticmethod
    def _table_has_explicit_first_column_header(table: etree._Element) -> bool:
        look = table.find("w:tblPr/w:tblLook", NS)
        if look is None:
            return False
        return (_attr(look, W, "firstColumn") or "").lower() in {"1", "true", "on"}

    @staticmethod
    def _logical_table_values(
        logical_cells: list[dict[str, Any]], row_count: int, column_count: int
    ) -> list[list[str]]:
        values = [["" for _ in range(column_count)] for _ in range(row_count)]
        for logical in logical_cells:
            if 1 <= logical["row_start"] <= row_count and 1 <= logical["column"] <= column_count:
                values[logical["row_start"] - 1][logical["column"] - 1] = logical["text"]
        return values

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
    def _caption_info(text: str, style_name: str) -> dict[str, Any] | None:
        """Classify an explicit caption label without using rendered position."""

        figure = re.match(
            r"^\s*(?:图|Figure)\s*([0-9]+(?:\s*[-.]\s*[0-9]+)*)\b",
            text,
            re.IGNORECASE,
        )
        table = re.match(
            r"^\s*(?:表|Table)\s*([0-9]+(?:\s*[-.]\s*[0-9]+)*)\b",
            text,
            re.IGNORECASE,
        )
        is_style_caption = "caption" in style_name.casefold()
        if not is_style_caption and figure is None and table is None:
            return None
        if figure is not None:
            return {
                "caption_target_kind": "figure",
                "caption_figure_number": re.sub(r"\s+", "", figure.group(1)),
                "caption_label_kind": "figure",
                "caption_association_status": "unresolved",
            }
        if table is not None:
            return {
                "caption_target_kind": "table",
                "caption_table_number": re.sub(r"\s+", "", table.group(1)),
                "caption_label_kind": "table",
                "caption_association_status": "unresolved",
            }
        return {
            "caption_target_kind": None,
            "caption_label_kind": "style_only",
            "caption_association_status": "unresolved",
        }

    @staticmethod
    def _record_caption_association(caption: dict[str, Any], target: dict[str, Any]) -> None:
        """Record a direct adjacency association on both endpoints."""

        caption["caption_association_status"] = "reliable"
        if target.get("object_type") != "figure":
            return
        target["caption_object_id"] = caption["object_id"]
        target["caption_relation_status"] = "reliable"
        if (number := caption.get("caption_figure_number")):
            target["figure_number"] = number

    @staticmethod
    def _omml_tree(element: etree._Element) -> dict[str, Any]:
        """Preserve observed OMML structure without claiming mathematical meaning."""

        return {
            "tag": etree.QName(element).localname,
            "text": _compact_text(element.text or "") or None,
            "attributes": dict(sorted(element.attrib.items())),
            "children": [
                DocxCanonicalizer._omml_tree(child)
                for child in element
                if isinstance(child.tag, str)
            ],
        }

    def _resolve_rich_content_context(
        self,
        records: list[dict[str, Any]],
        extraction: dict[str, Any],
    ) -> None:
        """Resolve only explicit caption/number/context topology after body scan.

        This is deliberately not visual inference: a figure reference resolves
        only when a direct textual figure-number mention maps to exactly one
        caption that is itself attached by direct body adjacency.
        """

        by_id = {str(item["object_id"]): item for item in records}
        paragraphs = [
            item
            for item in records
            if item.get("object_type") == "block" and item.get("block_kind") in {"paragraph", "list_item", "caption", "heading"}
        ]
        paragraph_by_id = {str(item["object_id"]): item for item in paragraphs}
        by_section: dict[str, list[dict[str, Any]]] = {}
        for item in paragraphs:
            section = str(item.get("structural_locator", {}).get("section_id", ""))
            by_section.setdefault(section, []).append(item)
        for values in by_section.values():
            values.sort(key=lambda item: int(item.get("structural_locator", {}).get("body_ordinal", -1)))

        figures_by_number: dict[str, list[dict[str, Any]]] = {}
        for item in records:
            if item.get("object_type") != "figure" or item.get("status") != "supported":
                continue
            number = item.get("figure_number")
            if isinstance(number, str) and number:
                figures_by_number.setdefault(number, []).append(item)

        for bookmark in records:
            if bookmark.get("reference_kind") != "bookmark":
                continue
            parent_id = bookmark.get("paragraph_object_id")
            parent = paragraph_by_id.get(str(parent_id)) if parent_id is not None else None
            target_id = parent.get("associated_object_id") if parent is not None else None
            if (
                isinstance(target_id, str)
                and target_id in by_id
                and by_id[target_id].get("object_type") == "figure"
            ):
                bookmark["reference_target_object_id"] = target_id
                bookmark["resolution_status"] = "reliable"

        resolved_reference_count = 0
        unresolved_reference_count = 0
        for reference in records:
            if reference.get("reference_kind") != "figure_textual_reference":
                continue
            number = reference.get("figure_number")
            targets = figures_by_number.get(number, []) if isinstance(number, str) else []
            if len(targets) != 1:
                reference["resolution_status"] = "unresolved"
                reference["reason"] = "missing_or_ambiguous_figure_number_target"
                unresolved_reference_count += 1
                continue
            target = targets[0]
            reference["reference_target_object_id"] = target["object_id"]
            reference["resolution_status"] = "reliable"
            reference["status"] = "supported"
            target["reference_relation_status"] = "reliable"
            target.setdefault("referencing_paragraph_ids", []).append(reference["referencing_paragraph_id"])
            resolved_reference_count += 1

        eligible_equation_count = 0
        eligible_figure_count = 0
        for item in records:
            if item.get("object_type") not in {"figure", "equation"}:
                continue
            locator = item.get("structural_locator", {})
            section = str(locator.get("section_id", ""))
            ordinal = locator.get("body_ordinal")
            candidates = by_section.get(section, [])
            previous = next(
                (
                    candidate
                    for candidate in reversed(candidates)
                    if isinstance(ordinal, int)
                    and int(candidate.get("structural_locator", {}).get("body_ordinal", -1)) < ordinal
                    and str(candidate.get("canonical_value") or "").strip()
                ),
                None,
            )
            following = next(
                (
                    candidate
                    for candidate in candidates
                    if isinstance(ordinal, int)
                    and int(candidate.get("structural_locator", {}).get("body_ordinal", -1)) > ordinal
                    and str(candidate.get("canonical_value") or "").strip()
                ),
                None,
            )
            if previous is not None:
                item["context_before_paragraph_id"] = previous["object_id"]
            if following is not None:
                item["context_after_paragraph_id"] = following["object_id"]
            if item.get("object_type") == "equation":
                context = " ".join(
                    str(value)
                    for value in (
                        item.get("canonical_value"),
                        previous.get("canonical_value") if previous else None,
                        following.get("canonical_value") if following else None,
                    )
                    if value
                )
                explained = bool(re.search(r"(?:公式|计算|其中|取值|得分|where|formula)", context, re.IGNORECASE))
                eligible = (
                    item.get("status") == "supported"
                    and item.get("placement") == "block"
                    and len(str(item.get("presentation_text") or "")) > 3
                    and previous is not None
                    and following is not None
                    and explained
                )
                item["semantic_status"] = "textually_supported" if eligible else "textual_context_available"
                item["gold_evidence_eligible"] = eligible
                if eligible:
                    eligible_equation_count += 1
            else:
                reliable = (
                    item.get("status") == "supported"
                    and item.get("resource_object_id") in by_id
                    and item.get("caption_relation_status") == "reliable"
                    and item.get("reference_relation_status") == "reliable"
                    and bool(item.get("figure_number"))
                )
                item["semantic_status"] = "textually_supported" if reliable else "structural_only"
                item["gold_evidence_eligible"] = reliable
                if reliable:
                    item["gold_evidence_scope"] = "caption_and_text_only"
                    item["referencing_paragraph_ids"] = tuple(sorted(set(item.get("referencing_paragraph_ids", ()))))
                    eligible_figure_count += 1

        extraction["rich_content"] = {
            "gold_eligible_figures": eligible_figure_count,
            "gold_eligible_equations": eligible_equation_count,
            "resolved_figure_references": resolved_reference_count,
            "unresolved_figure_references": unresolved_reference_count,
            "figure_caption_associations": sum(
                item.get("object_type") == "block"
                and item.get("block_kind") == "caption"
                and item.get("caption_target_kind") == "figure"
                and item.get("caption_association_status") == "reliable"
                for item in records
            ),
        }

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
            elif element.tag == _tag(W, "noBreakHyphen"):
                # Word stores the separator in captions such as ``表 2-7`` as
                # an OOXML element rather than a text node.  Dropping it turns
                # a meaningful source label into the misleading ``表 27``.
                pieces.append("-")
            elif element.tag == _tag(W, "softHyphen"):
                pieces.append("-")
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
                "media_resources": sum(
                    item.startswith("word/media/") and not item.endswith("/")
                    for item in names
                ),
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
        tables = [record for record in records if record["object_type"] == "table"]
        rich = [
            record
            for record in records
            if record["object_type"] in {"figure", "equation", "media_resource", "embedded_object"}
        ]
        table_classes: dict[str, int] = {}
        for table in tables:
            for classification in table.get("table_structure_classes", ()):
                table_classes[str(classification)] = table_classes.get(str(classification), 0) + 1
        return {
            "document_id": document_id,
            "source_sha256": source_sha256,
            "canonical_digest": canonical_digest,
            "canonicalizer": CANONICALIZER_VERSION,
            "record_count": len(records),
            "records_by_status": dict(sorted(by_status.items())),
            "records_by_object_type": dict(sorted(by_type.items())),
            "table_topology": {
                "table_count": len(tables),
                "complete_table_count": sum(item["status"] == "supported" for item in tables),
                "partial_table_count": sum(item["status"] == "partial" for item in tables),
                "classes": dict(sorted(table_classes.items())),
            },
            "rich_content": {
                "by_object_type": {
                    kind: sum(item["object_type"] == kind for item in rich)
                    for kind in ("figure", "equation", "media_resource", "embedded_object")
                },
                "by_status": {
                    status: sum(item["status"] == status for item in rich)
                    for status in ("supported", "partial", "unsupported", "missing")
                },
                "gold_eligible": {
                    "figures": sum(
                        item["object_type"] == "figure"
                        and item.get("gold_evidence_eligible") is True
                        for item in rich
                    ),
                    "equations": sum(
                        item["object_type"] == "equation"
                        and item.get("gold_evidence_eligible") is True
                        for item in rich
                    ),
                },
                "relations": extraction.get("rich_content", {}),
            },
            "support_policy": {
                "supported": ["body headings", "paragraphs", "lists", "OOXML-grid-resolved logical tables", "resource-backed DrawingML images", "adjacency-backed captions", "raw OMML with structural tree", "bookmarks", "hyperlinks"],
                "partial": ["unrecoverable table topology", "nested parent-table content", "unresolved caption/reference association", "VML shapes", "body-anchored notes", "unresolved cross-reference fields"],
                "unsupported": ["OLE embedded objects", "unresolvable drawing/chart/SmartArt semantics", "unanchored notes"],
            },
            "package": package_diagnostics,
            "extraction": extraction,
        }
