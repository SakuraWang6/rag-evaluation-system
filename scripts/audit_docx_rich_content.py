#!/usr/bin/env python3
"""Read-only OOXML inventory for DOCX figures, captions, references, and OMML.

This deliberately audits source-side structures before Canonicalization.  It
does not invoke a model, render an image, OCR content, or write an Authoring
dataset.  Its JSON report is deterministic for the same DOCX package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
V = "urn:schemas-microsoft-com:vml"
O = "urn:schemas-microsoft-com:office:office"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W, "r": R, "m": M, "a": A, "wp": WP, "v": V, "o": O, "rel": REL}


def _tag(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def _attr(element: etree._Element | None, namespace: str, name: str) -> str | None:
    return element.get(_tag(namespace, name)) if element is not None else None


def _compact(value: str) -> str:
    return re.sub(r"[\s\u00a0]+", " ", value).strip()


def _paragraph_text(paragraph: etree._Element) -> str:
    return _compact("".join(paragraph.xpath(".//w:t/text()", namespaces=NS)))


def _style(paragraph: etree._Element, styles: dict[str, str]) -> tuple[str, str]:
    style = paragraph.find("w:pPr/w:pStyle", NS)
    style_id = _attr(style, W, "val") or ""
    return style_id, styles.get(style_id, style_id or "Normal")


def _styles(package: zipfile.ZipFile) -> dict[str, str]:
    try:
        root = etree.fromstring(package.read("word/styles.xml"))
    except KeyError:
        return {}
    return {
        item.get(_tag(W, "styleId"), ""): _attr(item.find("w:name", NS), W, "val") or ""
        for item in root.findall("w:style", NS)
        if item.get(_tag(W, "styleId"))
    }


def _relationships(package: zipfile.ZipFile) -> dict[str, dict[str, str]]:
    try:
        root = etree.fromstring(package.read("word/_rels/document.xml.rels"))
    except KeyError:
        return {}
    return {
        item.get("Id", ""): {
            "target": item.get("Target", ""),
            "type": item.get("Type", ""),
            "target_mode": item.get("TargetMode", ""),
        }
        for item in root.findall("rel:Relationship", NS)
        if item.get("Id")
    }


def _local_name(element: etree._Element) -> str:
    return etree.QName(element).localname


def _math_tree(element: etree._Element) -> dict[str, Any]:
    """A deterministic, non-semantic OMML tree retaining structure and text."""

    return {
        "tag": _local_name(element),
        "text": _compact(element.text or "") or None,
        "children": [
            _math_tree(child)
            for child in element
            if isinstance(child.tag, str)
        ],
    }


def _body_context(body_children: list[etree._Element], ordinal: int) -> dict[str, Any]:
    paragraph = body_children[ordinal]
    before = next(
        (_paragraph_text(item) for item in reversed(body_children[:ordinal]) if item.tag == _tag(W, "p") and _paragraph_text(item)),
        None,
    )
    after = next(
        (_paragraph_text(item) for item in body_children[ordinal + 1 :] if item.tag == _tag(W, "p") and _paragraph_text(item)),
        None,
    )
    return {
        "body_ordinal": ordinal,
        "paragraph_text": _paragraph_text(paragraph),
        "preceding_paragraph_text": before,
        "following_paragraph_text": after,
    }


def _caption_candidate(paragraph: etree._Element, styles: dict[str, str]) -> dict[str, Any] | None:
    style_id, style_name = _style(paragraph, styles)
    text = _paragraph_text(paragraph)
    figure_number = re.search(r"(?:^|\s)(?:图|Figure)\s*([0-9]+(?:[-.]?[0-9]+)*)", text, re.I)
    if "caption" not in style_name.casefold() and not figure_number:
        return None
    return {
        "style_id": style_id,
        "style_name": style_name,
        "text": text,
        "figure_number": figure_number.group(1) if figure_number else None,
        "caption_signal": "style" if "caption" in style_name.casefold() else "number_pattern",
    }


def audit(source: Path) -> dict[str, Any]:
    with zipfile.ZipFile(source) as package:
        document = etree.fromstring(package.read("word/document.xml"))
        styles = _styles(package)
        relationships = _relationships(package)
        members = {item.filename for item in package.infolist()}
        body = document.find("w:body", NS)
        if body is None:
            raise ValueError("DOCX has no word/document.xml body")
        children = [item for item in body if item.tag != _tag(W, "sectPr")]
        paragraphs = [(index, item) for index, item in enumerate(children) if item.tag == _tag(W, "p")]

        captions = [
            _body_context(children, ordinal) | _caption_candidate(paragraph, styles)
            for ordinal, paragraph in paragraphs
            if _caption_candidate(paragraph, styles) is not None
        ]
        figures: list[dict[str, Any]] = []
        equations: list[dict[str, Any]] = []
        vml: list[dict[str, Any]] = []
        ole: list[dict[str, Any]] = []
        field_references: list[dict[str, Any]] = []
        textual_figure_mentions: list[dict[str, Any]] = []

        for ordinal, paragraph in paragraphs:
            context = _body_context(children, ordinal)
            for sequence, drawing in enumerate(paragraph.findall(".//w:drawing", NS), start=1):
                inline = drawing.find("wp:inline", NS)
                anchor = drawing.find("wp:anchor", NS)
                item = inline if inline is not None else anchor
                if item is None:
                    figures.append(context | {"sequence": sequence, "storage": "drawingml_unresolved", "complete_locator": False})
                    continue
                doc_pr = item.find("wp:docPr", NS)
                extent = item.find("wp:extent", NS)
                blip = item.find(".//a:blip", NS)
                relationship_id = _attr(blip, R, "embed") if blip is not None else None
                relationship = relationships.get(relationship_id or "", {})
                target = relationship.get("target")
                package_target = f"word/{target}" if target and not target.startswith("/") else None
                figures.append(
                    context
                    | {
                        "sequence": sequence,
                        "storage": "drawingml_inline" if inline is not None else "drawingml_anchor",
                        "complete_locator": bool(relationship_id and target and package_target in members),
                        "relationship_id": relationship_id,
                        "relationship_type": relationship.get("type"),
                        "media_target": target,
                        "media_member_exists": package_target in members if package_target else False,
                        "docPr_id": doc_pr.get("id") if doc_pr is not None else None,
                        "name": doc_pr.get("name") if doc_pr is not None else None,
                        "alt_text": doc_pr.get("descr") if doc_pr is not None else None,
                        "title": doc_pr.get("title") if doc_pr is not None else None,
                        "width_emu": int(extent.get("cx")) if extent is not None and extent.get("cx", "").isdigit() else None,
                        "height_emu": int(extent.get("cy")) if extent is not None and extent.get("cy", "").isdigit() else None,
                    }
                )
            for sequence, shape in enumerate(paragraph.findall(".//v:shape", NS), start=1):
                image_data = shape.find("v:imagedata", NS)
                relationship_id = _attr(image_data, R, "id") if image_data is not None else None
                relationship = relationships.get(relationship_id or "", {})
                vml.append(
                    context
                    | {
                        "sequence": sequence,
                        "storage": "vml_shape",
                        "shape_id": shape.get("id"),
                        "shape_type": shape.get("type"),
                        "title": shape.get("title"),
                        "alt": shape.get("alt"),
                        "style": shape.get("style"),
                        "relationship_id": relationship_id,
                        "media_target": relationship.get("target"),
                        "has_imagedata": image_data is not None,
                    }
                )
            for sequence, object_element in enumerate(paragraph.findall(".//o:OLEObject", NS), start=1):
                ole.append(
                    context
                    | {
                        "sequence": sequence,
                        "storage": "ole",
                        "relationship_id": _attr(object_element, R, "id"),
                        "prog_id": object_element.get("ProgID"),
                        "object_type": object_element.get("Type"),
                    }
                )

            math_paragraphs = list(paragraph.findall(".//m:oMathPara", NS))

            def is_wrapped_math(item: etree._Element) -> bool:
                parent = item.getparent()
                while parent is not None and parent is not paragraph:
                    if parent.tag == _tag(M, "oMathPara"):
                        return True
                    parent = parent.getparent()
                return False

            math_elements: list[tuple[str, etree._Element]] = [("block", item) for item in math_paragraphs]
            math_elements.extend(
                ("inline", item)
                for item in paragraph.findall(".//m:oMath", NS)
                if not is_wrapped_math(item)
            )
            for sequence, (placement, math) in enumerate(math_elements, start=1):
                raw = etree.tostring(math, with_tail=False)
                equations.append(
                    context
                    | {
                        "sequence": sequence,
                        "storage": "omml",
                        "placement": placement,
                        "raw_omml_sha256": hashlib.sha256(raw).hexdigest(),
                        "raw_omml": raw.decode("utf-8"),
                        "surface_text": _compact("".join(math.xpath(".//m:t/text()", namespaces=NS))),
                        "tree": _math_tree(math),
                    }
                )

            instructions = [
                _attr(item, W, "instr") or ""
                for item in paragraph.findall(".//w:fldSimple", NS)
            ] + list(paragraph.xpath(".//w:instrText/text()", namespaces=NS))
            for instruction in (_compact(item) for item in instructions):
                if instruction:
                    field_references.append(context | {"instruction": instruction})
            text = context["paragraph_text"]
            if re.search(r"(?:如图|见图|图\s*[0-9]+|Figure\s*[0-9]+)", text, re.I):
                textual_figure_mentions.append(context | {"mention_text": text})

        media = []
        for name in sorted(
            member
            for member in members
            if member.startswith("word/media/") and not member.endswith("/")
        ):
            payload = package.read(name)
            media.append(
                {
                    "part": name,
                    "byte_count": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "extension": Path(name).suffix.casefold(),
                }
            )

    return {
        "source": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_side_counts": {
            "drawingml_inline": sum(item["storage"] == "drawingml_inline" for item in figures),
            "drawingml_anchor": sum(item["storage"] == "drawingml_anchor" for item in figures),
            "vml_shape": len(vml),
            "ole": len(ole),
            "omml_equation": len(equations),
            "caption_candidate": len(captions),
            "field_reference": len(field_references),
            "textual_figure_mention": len(textual_figure_mentions),
            "media_resource": len(media),
        },
        "drawingml_figures": figures,
        "vml_shapes": vml,
        "ole_objects": ole,
        "equations": equations,
        "caption_candidates": captions,
        "field_references": field_references,
        "textual_figure_mentions": textual_figure_mentions,
        "media_resources": media,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-docx", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source_docx.resolve())
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["source_side_counts"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
