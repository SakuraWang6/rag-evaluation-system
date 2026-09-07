"""Small, dependency-free DOCX-to-HTML renderer for the local reader.

The browser cannot open an OOXML package by itself.  This renderer keeps the
source package as the authority and projects the parts that matter for a
reading view (styles, headings, TOC fields, lists, tables, images, page
breaks, and headers/footers) into a self-contained HTML document.  Pagination
is performed in that document with the browser's real font metrics rather
than a character-count estimate.
"""

from __future__ import annotations

import base64
import html
import mimetypes
import posixpath
import re
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W, "r": R, "m": M}


def _q(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def _attr(node: etree._Element | None, namespace: str, name: str, default: str = "") -> str:
    return (node.get(_q(namespace, name)) if node is not None else None) or default


def _safe_class(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-") or "normal"


def _int_value(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _text(node: etree._Element) -> str:
    pieces: list[str] = []
    for child in node.iter():
        if child.tag == _q(W, "t"):
            pieces.append(child.text or "")
        elif child.tag == _q(W, "tab"):
            pieces.append("\t")
        elif child.tag in {_q(W, "br"), _q(W, "cr")}:
            pieces.append("\n")
        elif child.tag in {_q(W, "noBreakHyphen"), _q(W, "softHyphen")}:
            pieces.append("-")
        elif child.tag == _q(M, "t"):
            pieces.append(child.text or "")
    return "".join(pieces)


def _relationship_map(package: zipfile.ZipFile) -> dict[str, str]:
    try:
        root = etree.fromstring(package.read("word/_rels/document.xml.rels"))
    except (KeyError, etree.XMLSyntaxError):
        return {}
    return {
        item.get("Id", ""): item.get("Target", "")
        for item in root
        if item.get("Id") and item.get("Target")
    }


def _part_path(target: str) -> str:
    return posixpath.normpath(posixpath.join("word", target)).lstrip("/")


def _style_map(package: zipfile.ZipFile) -> dict[str, str]:
    try:
        root = etree.fromstring(package.read("word/styles.xml"))
    except (KeyError, etree.XMLSyntaxError):
        return {}
    values: dict[str, str] = {}
    for style in root.findall("w:style", NS):
        style_id = _attr(style, W, "styleId")
        name = _attr(style.find("w:name", NS), W, "val", style_id)
        if style_id:
            values[style_id] = name
    return values


def _heading_level(style_id: str, style_name: str) -> int | None:
    joined = f"{style_id} {style_name}".lower().replace(" ", "")
    match = re.search(r"heading([1-9])", joined)
    if match:
        return int(match.group(1))
    # Chinese Word installations often localize the built-in style name.
    match = re.search(r"标题([1-9])", style_name)
    return int(match.group(1)) if match else None


def _numbering_map(package: zipfile.ZipFile) -> dict[tuple[str, int], tuple[str, str]]:
    try:
        root = etree.fromstring(package.read("word/numbering.xml"))
    except (KeyError, etree.XMLSyntaxError):
        return {}
    abstract: dict[tuple[str, int], tuple[str, str]] = {}
    for item in root.findall("w:abstractNum", NS):
        abstract_id = _attr(item, W, "abstractNumId")
        for level in item.findall("w:lvl", NS):
            ilvl = max(0, min(9, _int_value(_attr(level, W, "ilvl", "0"), 0)))
            abstract[(abstract_id, ilvl)] = (
                _attr(level.find("w:numFmt", NS), W, "val", "decimal"),
                _attr(level.find("w:lvlText", NS), W, "val", "%1."),
            )
    result: dict[tuple[str, int], tuple[str, str]] = {}
    for item in root.findall("w:num", NS):
        num_id = _attr(item, W, "numId")
        abstract_id = _attr(item.find("w:abstractNumId", NS), W, "val")
        for (candidate, level), value in abstract.items():
            if candidate == abstract_id:
                result[(num_id, level)] = value
    return result


def _page_settings(body: etree._Element) -> tuple[int, int, int, int, int, int]:
    """Return page width/height and margins in twentieths of a point."""

    section = body.find("w:sectPr", NS)
    if section is None:
        section = body.xpath(".//w:pPr/w:sectPr", namespaces=NS)[-1] if body.xpath(".//w:pPr/w:sectPr", namespaces=NS) else None
    size = section.find("w:pgSz", NS) if section is not None else None
    margins = section.find("w:pgMar", NS) if section is not None else None
    return (
        max(3600, _int_value(_attr(size, W, "w", "11906"), 11906)),
        max(3600, _int_value(_attr(size, W, "h", "16838"), 16838)),
        max(0, _int_value(_attr(margins, W, "top", "1440"), 1440)),
        max(0, _int_value(_attr(margins, W, "right", "1440"), 1440)),
        max(0, _int_value(_attr(margins, W, "bottom", "1440"), 1440)),
        max(0, _int_value(_attr(margins, W, "left", "1440"), 1440)),
    )


def _inline_html(
    node: etree._Element,
    *,
    relationships: dict[str, str],
    package: zipfile.ZipFile,
) -> str:
    output: list[str] = []
    for child in node:
        if child.tag == _q(W, "r"):
            properties = child.find("w:rPr", NS)
            styles: list[str] = []
            if properties is not None:
                if properties.find("w:b", NS) is not None:
                    styles.append("font-weight:700")
                if properties.find("w:i", NS) is not None:
                    styles.append("font-style:italic")
                if properties.find("w:u", NS) is not None:
                    styles.append("text-decoration:underline")
                if properties.find("w:strike", NS) is not None:
                    styles.append("text-decoration:line-through")
                color = _attr(properties.find("w:color", NS), W, "val")
                if color and color.lower() != "auto":
                    styles.append(f"color:#{re.sub(r'[^0-9a-fA-F]', '', color)[:6]}")
                size = _attr(properties.find("w:sz", NS), W, "val")
                if size.isdigit():
                    styles.append(f"font-size:{max(6, int(size) / 2):g}pt")
            inner: list[str] = []
            for part in child:
                if part.tag == _q(W, "t"):
                    inner.append(html.escape(part.text or ""))
                elif part.tag == _q(W, "tab"):
                    inner.append("<span class=\"docx-tab\">\t</span>")
                elif part.tag in {_q(W, "br"), _q(W, "cr")}:
                    if part.tag == _q(W, "br") and _attr(part, W, "type") == "page":
                        inner.append("<span class=\"docx-inline-page-break\"></span>")
                    else:
                        inner.append("<br>")
                elif part.tag == _q(W, "drawing"):
                    blip = part.find(".//a:blip", {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"})
                    embed = _attr(blip, R, "embed")
                    target = relationships.get(embed, "")
                    path = _part_path(target) if target else ""
                    if path and path in package.namelist():
                        raw = package.read(path)
                        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
                        data = base64.b64encode(raw).decode("ascii")
                        doc_pr = part.find(".//wp:docPr", {"wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"})
                        alt = html.escape((doc_pr.get("descr") or "图像")) if doc_pr is not None else "图像"
                        inner.append(f'<img class="docx-image" src="data:{mime};base64,{data}" alt="{alt}">')
                    else:
                        inner.append('<span class="docx-object-placeholder">[图像]</span>')
                elif part.tag == _q(W, "footnoteReference"):
                    inner.append(f'<sup class="docx-footnote">{html.escape(_attr(part, W, "id"))}</sup>')
            value = "".join(inner)
            output.append(f'<span class="docx-run" style="{";".join(styles)}">{value}</span>' if styles else value)
        elif child.tag == _q(W, "hyperlink"):
            value = _inline_html(child, relationships=relationships, package=package)
            target = relationships.get(_attr(child, R, "id"), "")
            anchor = _attr(child, W, "anchor")
            if anchor and re.fullmatch(r"[A-Za-z0-9_.:-]+", anchor):
                output.append(f'<a href="#{html.escape(anchor, quote=True)}">{value}</a>')
            elif target.startswith(("http://", "https://", "mailto:")):
                output.append(f'<a href="{html.escape(target, quote=True)}" target="_blank" rel="noreferrer">{value}</a>')
            else:
                output.append(value)
        elif child.tag in {_q(W, "fldSimple"), _q(W, "smartTag"), _q(W, "ins"), _q(W, "del")}:
            output.append(_inline_html(child, relationships=relationships, package=package))
    return "".join(output)


def _paragraph_html(
    paragraph: etree._Element,
    *,
    styles: dict[str, str],
    relationships: dict[str, str],
    numbering: dict[tuple[str, int], tuple[str, str]],
    package: zipfile.ZipFile,
    counters: dict[tuple[str, int], int],
    ordinal: int,
) -> str:
    ppr = paragraph.find("w:pPr", NS)
    style_id = _attr(ppr.find("w:pStyle", NS) if ppr is not None else None, W, "val", "Normal")
    style_name = styles.get(style_id, style_id)
    level = _heading_level(style_id, style_name)
    instructions = " ".join(
        [_attr(item, W, "instr") for item in paragraph.findall(".//w:fldSimple", NS)]
        + [item.text or "" for item in paragraph.findall(".//w:instrText", NS)]
    )
    is_toc = bool(re.search(r"\bTOC\b", instructions, re.I)) or style_id.lower().startswith("toc") or style_name.lower().startswith("toc")
    alignment = _attr(ppr.find("w:jc", NS) if ppr is not None else None, W, "val")
    indent = ppr.find("w:ind", NS) if ppr is not None else None
    spacing = ppr.find("w:spacing", NS) if ppr is not None else None
    css: list[str] = []
    if alignment in {"center", "right", "both", "left"}:
        css.append(f"text-align:{'justify' if alignment == 'both' else alignment}")
    if indent is not None:
        for attr, prop in (("left", "margin-left"), ("right", "margin-right"), ("firstLine", "text-indent"), ("hanging", "text-indent")):
            raw = _attr(indent, W, attr)
            if raw.lstrip("-").isdigit():
                value = int(raw) / 20
                if attr == "hanging":
                    value = -value
                css.append(f"{prop}:{value:g}pt")
    if spacing is not None:
        for attr, prop in (("before", "margin-top"), ("after", "margin-bottom")):
            raw = _attr(spacing, W, attr)
            if raw.isdigit():
                css.append(f"{prop}:{int(raw) / 20:g}pt")
    num_pr = ppr.find("w:numPr", NS) if ppr is not None else None
    num_id = _attr(num_pr.find("w:numId", NS) if num_pr is not None else None, W, "val")
    raw_level = _attr(num_pr.find("w:ilvl", NS) if num_pr is not None else None, W, "val", "0")
    list_level = int(raw_level) if raw_level.isdigit() else 0
    marker = ""
    if num_id:
        fmt, template = numbering.get((num_id, list_level), ("bullet", "•"))
        key = (num_id, list_level)
        counters[key] = counters.get(key, 0) + 1
        for deeper in [key for key in counters if key[0] == num_id and key[1] > list_level]:
            counters.pop(deeper, None)
        if fmt == "bullet":
            marker = template if template not in {"%1", ""} else "•"
        else:
            marker = template.replace(f"%{list_level + 1}", str(counters[key]))
            marker = marker.replace("%1", str(counters[key]))
    classes = ["docx-block", f"docx-style-{_safe_class(style_id)}"]
    if is_toc:
        classes.append("docx-toc-entry")
    if num_id:
        classes.append("docx-list-item")
    if level is not None:
        classes.append(f"docx-heading-{level}")
    before = ppr is not None and ppr.find("w:pageBreakBefore", NS) is not None
    after = bool(paragraph.find(".//w:br[@w:type='page']", NS)) or paragraph.find(".//w:sectPr", NS) is not None
    tag = f"h{min(level, 6)}" if level is not None else "p"
    body = _inline_html(paragraph, relationships=relationships, package=package)
    bookmark = paragraph.find(".//w:bookmarkStart", NS)
    bookmark_name = _attr(bookmark, W, "name")
    if bookmark_name and re.fullmatch(r"[A-Za-z0-9_.:-]+", bookmark_name):
        body = f'<span id="{html.escape(bookmark_name, quote=True)}"></span>{body}'
    if num_id:
        body = f'<span class="docx-marker">{html.escape(marker)}</span><span class="docx-list-content">{body}</span>'
    attributes = [f'id="docx-block-{ordinal}"', 'data-docx-block="true"']
    if before:
        attributes.append('data-page-break-before="true"')
    if after:
        attributes.append('data-page-break-after="true"')
    if level is not None:
        attributes.append(f'data-heading-level="{level}"')
    if is_toc:
        attributes.append('data-docx-toc="true"')
    return f'<{tag} class="{" ".join(classes)}" {" ".join(attributes)} style="{";".join(css)}">{body}</{tag}>'


def _table_html(
    table: etree._Element,
    *,
    styles: dict[str, str],
    relationships: dict[str, str],
    numbering: dict[tuple[str, int], tuple[str, str]],
    package: zipfile.ZipFile,
    counters: dict[tuple[str, int], int],
    ordinal: int,
) -> str:
    rows = table.findall("w:tr", NS)
    rendered: list[str] = []
    for row_index, row in enumerate(rows):
        cells: list[str] = []
        for cell in row.findall("w:tc", NS):
            span = _attr(cell.find("w:tcPr/w:gridSpan", NS), W, "val", "1")
            paragraphs = [
                _paragraph_html(p, styles=styles, relationships=relationships, numbering=numbering, package=package, counters=counters, ordinal=ordinal)
                for p in cell.findall("w:p", NS)
            ]
            cell_tag = "th" if row.find("w:trPr/w:tblHeader", NS) is not None else "td"
            cells.append(f'<{cell_tag} colspan="{max(1, int(span) if span.isdigit() else 1)}">{"".join(paragraphs)}</{cell_tag}>')
        rendered.append(f'<tr>{"".join(cells)}</tr>')
    if not rendered:
        return ""
    header_rows = 1 if rows and rows[0].find("w:trPr/w:tblHeader", NS) is not None else 0
    head = f"<thead>{rendered[0]}</thead>" if header_rows else ""
    body = "".join(rendered[header_rows:])
    return f'<table class="docx-table docx-block" data-docx-block="true" id="docx-table-{ordinal}">{head}<tbody>{body}</tbody></table>'


def _render_part(
    root: etree._Element,
    *,
    styles: dict[str, str],
    relationships: dict[str, str],
    numbering: dict[tuple[str, int], tuple[str, str]],
    package: zipfile.ZipFile,
) -> str:
    counters: dict[tuple[str, int], int] = {}
    output: list[str] = []
    ordinal = 0
    for child in root.iterchildren():
        if child.tag == _q(W, "p"):
            ordinal += 1
            output.append(_paragraph_html(child, styles=styles, relationships=relationships, numbering=numbering, package=package, counters=counters, ordinal=ordinal))
        elif child.tag == _q(W, "tbl"):
            ordinal += 1
            output.append(_table_html(child, styles=styles, relationships=relationships, numbering=numbering, package=package, counters=counters, ordinal=ordinal))
        elif child.tag == _q(W, "sdt"):
            content = child.find("w:sdtContent", NS)
            if content is not None:
                for nested in content:
                    if nested.tag in {_q(W, "p"), _q(W, "tbl")}:
                        ordinal += 1
                        output.append(_paragraph_html(nested, styles=styles, relationships=relationships, numbering=numbering, package=package, counters=counters, ordinal=ordinal) if nested.tag == _q(W, "p") else _table_html(nested, styles=styles, relationships=relationships, numbering=numbering, package=package, counters=counters, ordinal=ordinal))
    return "".join(output)


PAGINATION_SCRIPT = r"""
(function () {
  const canvas = document.querySelector('.docx-canvas');
  const flow = document.querySelector('.docx-flow');
  if (!canvas || !flow) return;
  const blocks = Array.from(flow.children);
  flow.remove();
  const host = document.createElement('div');
  host.className = 'docx-pages';
  canvas.appendChild(host);
  const header = document.querySelector('.docx-header-template');
  const footer = document.querySelector('.docx-footer-template');
  const pageHeight = Number.parseFloat(getComputedStyle(canvas).getPropertyValue('--page-height')) || 1122;
  const marginTop = Number.parseFloat(getComputedStyle(canvas).getPropertyValue('--margin-top')) || 96;
  const marginBottom = Number.parseFloat(getComputedStyle(canvas).getPropertyValue('--margin-bottom')) || 96;
  // CSS layout reports scrollHeight as an integer.  DOCX margins commonly
  // convert to fractional pixels (for example 67.2px); comparing that value
  // directly makes an empty min-height body look one pixel too tall and
  // incorrectly starts a new page for every following block.
  const innerHeight = Math.max(160, Math.floor(pageHeight - marginTop - marginBottom));
  function newPage() {
    const page = document.createElement('section');
    page.className = 'docx-page';
    const body = document.createElement('div');
    body.className = 'docx-page-body';
    body.style.minHeight = innerHeight + 'px';
    page.appendChild(body);
    if (header) {
      const value = document.createElement('div');
      value.className = 'docx-header';
      value.innerHTML = header.innerHTML;
      page.prepend(value);
    }
    if (footer) {
      const value = document.createElement('div');
      value.className = 'docx-footer';
      value.innerHTML = footer.innerHTML;
      page.appendChild(value);
    }
    host.appendChild(page);
    return { page, body };
  }
  function paginate() {
    host.replaceChildren();
    let current = newPage();
    blocks.forEach((block, index) => {
      if (index > 0 && block.dataset.pageBreakBefore === 'true' && current.body.children.length) current = newPage();
      current.body.appendChild(block);
      if (current.body.scrollHeight > innerHeight && current.body.children.length > 1) {
        current.body.removeChild(block);
        current = newPage();
        current.body.appendChild(block);
      }
      if (block.dataset.pageBreakAfter === 'true' && index < blocks.length - 1) current = newPage();
    });
    Array.from(host.children).forEach((page, index) => {
      page.dataset.page = String(index + 1);
      page.querySelectorAll('.docx-page-number').forEach((item) => { item.textContent = String(index + 1); });
      page.querySelectorAll('.docx-page-count').forEach((item) => { item.textContent = String(host.children.length); });
    });
  }
  paginate();
  let resizeTimer;
  window.addEventListener('resize', () => { window.clearTimeout(resizeTimer); resizeTimer = window.setTimeout(paginate, 120); });
})();
"""


DOC_CSS = r"""
:root { color-scheme: light; }
* { box-sizing: border-box; }
html, body { margin: 0; min-height: 100%; background: #e9edf2; color: #202a35; }
body { font-family: "Times New Roman", "Songti SC", "STSong", serif; }
.docx-canvas { --page-width: 794px; --page-height: 1122px; --margin-top: 96px; --margin-right: 96px; --margin-bottom: 96px; --margin-left: 96px; padding: 28px 16px 50px; }
.docx-pages { display: grid; gap: 22px; justify-items: center; }
.docx-page { position: relative; width: min(var(--page-width), calc(100vw - 32px)); min-height: var(--page-height); padding: var(--margin-top) var(--margin-right) var(--margin-bottom) var(--margin-left); overflow: visible; background: #fff; box-shadow: 0 8px 26px rgba(35, 47, 61, .16); }
.docx-page-body { min-width: 0; overflow: visible; }
.docx-block { max-width: 100%; margin: 0 0 8pt; white-space: pre-wrap; overflow-wrap: anywhere; }
.docx-block p, p.docx-block { font-size: 11pt; line-height: 1.55; }
.docx-heading-1, .docx-heading-2, .docx-heading-3, .docx-heading-4, .docx-heading-5, .docx-heading-6 { color: #182838; font-weight: 700; page-break-after: avoid; }
.docx-heading-1 { margin-top: 10pt; margin-bottom: 16pt; font-size: 20pt; }
.docx-heading-2 { margin-top: 14pt; margin-bottom: 10pt; font-size: 16pt; }
.docx-heading-3 { margin-top: 12pt; margin-bottom: 8pt; font-size: 13pt; }
.docx-heading-4, .docx-heading-5, .docx-heading-6 { margin-top: 10pt; margin-bottom: 6pt; font-size: 11.5pt; }
.docx-toc-entry { margin: 0; padding: 2pt 0; color: #31485e; font-size: 10.5pt; line-height: 1.35; }
.docx-list-item { display: flex; gap: 7pt; margin-bottom: 3pt; }
.docx-marker { flex: 0 0 24pt; text-align: right; }
.docx-list-content { flex: 1 1 auto; min-width: 0; }
.docx-table { width: 100%; margin: 10pt 0 14pt; border-collapse: collapse; font-size: 9.5pt; line-height: 1.35; page-break-inside: avoid; }
.docx-table th, .docx-table td { padding: 5pt 6pt; border: .6pt solid #8794a2; vertical-align: top; white-space: pre-wrap; }
.docx-table th { background: #edf2f6; font-weight: 700; }
.docx-run { white-space: pre-wrap; }
.docx-image { display: block; max-width: 100%; max-height: 420px; margin: 8pt auto; object-fit: contain; }
.docx-object-placeholder { color: #6d7884; font-style: italic; }
.docx-inline-page-break { display: block; height: 0; break-after: page; page-break-after: always; }
.docx-header, .docx-footer { position: absolute; left: var(--margin-left); right: var(--margin-right); color: #697684; font-size: 8.5pt; }
.docx-header { top: 22px; }
.docx-footer { bottom: 22px; text-align: center; }
.docx-header-template, .docx-footer-template { display: none; }
.docx-tab { display: inline-block; min-width: 2em; }
.docx-footnote { color: #4a5a68; }
@media (max-width: 640px) { .docx-canvas { padding-right: 8px; padding-left: 8px; }.docx-page { width: calc(100vw - 16px); padding-right: 34px; padding-left: 34px; }.docx-heading-1 { font-size: 17pt; }.docx-table { font-size: 8.5pt; } }
"""


def render_docx_html(source_path: Path, filename: str) -> str:
    """Return a self-contained native-style reading view for one DOCX."""

    try:
        package = zipfile.ZipFile(source_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("source is not a readable DOCX package") from exc
    with package:
        try:
            root = etree.fromstring(package.read("word/document.xml"))
        except (KeyError, etree.XMLSyntaxError) as exc:
            raise ValueError("DOCX document.xml is missing or malformed") from exc
        body = root.find("w:body", NS)
        if body is None:
            raise ValueError("DOCX document body is missing")
        styles = _style_map(package)
        relationships = _relationship_map(package)
        numbering = _numbering_map(package)
        width, height, top, right, bottom, left = _page_settings(body)
        content = _render_part(body, styles=styles, relationships=relationships, numbering=numbering, package=package)
        header_html = ""
        footer_html = ""
        section = body.find("w:sectPr", NS)
        if section is not None:
            for reference in section.findall("w:headerReference", NS):
                target = relationships.get(_attr(reference, R, "id"), "")
                part = _part_path(target) if target else ""
                if part in package.namelist():
                    header_html = _render_part(etree.fromstring(package.read(part)), styles=styles, relationships=relationships, numbering=numbering, package=package)
                    break
            for reference in section.findall("w:footerReference", NS):
                target = relationships.get(_attr(reference, R, "id"), "")
                part = _part_path(target) if target else ""
                if part in package.namelist():
                    footer_html = _render_part(etree.fromstring(package.read(part)), styles=styles, relationships=relationships, numbering=numbering, package=package)
                    break
    page_style = ";".join(
        [
            f"--page-width:{width / 15:g}px",
            f"--page-height:{height / 15:g}px",
            f"--margin-top:{top / 15:g}px",
            f"--margin-right:{right / 15:g}px",
            f"--margin-bottom:{bottom / 15:g}px",
            f"--margin-left:{left / 15:g}px",
        ]
    )
    title = html.escape(filename, quote=True)
    return (
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<title>{title}</title><style>{DOC_CSS}</style></head><body>"
        f"<div class=\"docx-canvas\" style=\"{page_style}\"><div class=\"docx-flow\">{content}</div>"
        f"<div class=\"docx-header-template\">{header_html}</div><div class=\"docx-footer-template\">{footer_html}"
        "<span class=\"docx-page-number\"></span></div></div>"
        f"<script>{PAGINATION_SCRIPT}</script></body></html>"
    )
