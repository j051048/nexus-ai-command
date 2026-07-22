"""Professional, deterministic renderers for reviewed Agent deliverables."""

from __future__ import annotations

import io
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from html import escape
from typing import Any

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.services.artifact_content_sanitizer import sanitize_artifact_content

BRAND_BLUE = "164E63"
ACCENT_BLUE = "0F766E"
LIGHT_BLUE = "E8F2F3"
TEXT_DARK = "182230"
TEXT_MUTED = "667085"


def _set_cell_shading(cell: Any, fill: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    properties.append(shading)


def _add_page_number(paragraph: Any) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("第 ")
    run.font.size = Pt(8)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instruction, end])
    paragraph.add_run(" 页").font.size = Pt(8)


def _configure_styles(document: Document) -> None:
    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor.from_string(TEXT_DARK)
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.45
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")

    for name, size, color in (
        ("Title", 26, BRAND_BLUE),
        ("Heading 1", 18, BRAND_BLUE),
        ("Heading 2", 14, ACCENT_BLUE),
        ("Heading 3", 11.5, TEXT_DARK),
    ):
        style = styles[name]
        style.font.name = "Microsoft YaHei"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.paragraph_format.space_before = Pt(14)
        style.paragraph_format.space_after = Pt(7)

    if "Source Note" not in styles:
        source_style = styles.add_style("Source Note", WD_STYLE_TYPE.PARAGRAPH)
        source_style.base_style = styles["Normal"]
        source_style.font.size = Pt(8.5)
        source_style.font.color.rgb = RGBColor.from_string(TEXT_MUTED)


def _split_markdown_table(
    lines: list[str], start: int
) -> tuple[list[list[str]], int] | None:
    if start + 1 >= len(lines) or "|" not in lines[start]:
        return None
    separator = lines[start + 1].strip()
    if not re.match(r"^\|?\s*:?-{3,}", separator):
        return None
    rows: list[list[str]] = []
    index = start
    while index < len(lines) and "|" in lines[index] and lines[index].strip():
        row = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        if index != start + 1:
            rows.append(row)
        index += 1
    return rows, index


def _render_markdown(document: Document, markdown: str) -> None:
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        table_data = _split_markdown_table(lines, index)
        if table_data:
            rows, next_index = table_data
            if rows:
                width = max(len(row) for row in rows)
                table = document.add_table(rows=len(rows), cols=width)
                table.style = "Table Grid"
                for row_index, row in enumerate(rows):
                    for column_index in range(width):
                        value = row[column_index] if column_index < len(row) else ""
                        cell = table.cell(row_index, column_index)
                        cell.text = value
                        if row_index == 0:
                            _set_cell_shading(cell, BRAND_BLUE)
                            for run in cell.paragraphs[0].runs:
                                run.font.bold = True
                                run.font.color.rgb = RGBColor(255, 255, 255)
                document.add_paragraph()
            index = next_index
            continue
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("### "):
            document.add_heading(stripped[4:], level=3)
        elif stripped.startswith("## "):
            document.add_heading(stripped[3:], level=2)
        elif stripped.startswith("# "):
            document.add_heading(stripped[2:], level=1)
        elif re.match(r"^[-*]\s+", stripped):
            document.add_paragraph(
                re.sub(r"^[-*]\s+", "", stripped), style="List Bullet"
            )
        elif re.match(r"^\d+[.)]\s+", stripped):
            document.add_paragraph(
                re.sub(r"^\d+[.)]\s+", "", stripped), style="List Number"
            )
        elif stripped.startswith("> "):
            paragraph = document.add_paragraph(stripped[2:])
            paragraph.paragraph_format.left_indent = Cm(0.6)
            paragraph.paragraph_format.right_indent = Cm(0.6)
            for run in paragraph.runs:
                run.font.color.rgb = RGBColor.from_string(TEXT_MUTED)
        else:
            document.add_paragraph(stripped)
        index += 1


def render_artifact_docx(
    artifact: dict[str, Any],
    evidence_packet: dict[str, Any] | None = None,
    brand: dict[str, Any] | None = None,
) -> bytes:
    """Render a customer-ready Word document from the canonical artifact version."""

    brand = brand or {}
    sanitized = sanitize_artifact_content(
        str(artifact.get("content_markdown") or ""), evidence_packet
    )
    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(2.1)
    section.bottom_margin = Cm(1.9)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.0)
    _configure_styles(document)

    company = str(brand.get("company_name") or brand.get("name") or "Nexus AI")
    title = str(artifact.get("title") or "AI 成果")
    cover_label = str(artifact.get("artifact_label") or "科学仪器专业成果")
    paragraph = document.add_paragraph(company.upper())
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in paragraph.runs:
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = RGBColor.from_string(ACCENT_BLUE)
    document.add_paragraph()
    title_paragraph = document.add_paragraph(title, style="Title")
    title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle = document.add_paragraph(cover_label)
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in subtitle.runs:
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor.from_string(TEXT_MUTED)
    document.add_paragraph()
    meta_table = document.add_table(rows=4, cols=2)
    meta_table.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta_rows = (
        ("成果编号", str(artifact.get("artifact_code") or "-")),
        ("版本", f"v{artifact.get('version_number') or 1}"),
        (
            "状态",
            (
                "经人工确认"
                if artifact.get("approval_status") == "approved"
                else "审核草稿"
            ),
        ),
        ("生成日期", datetime.now(UTC).strftime("%Y-%m-%d")),
    )
    for row_index, (label, value) in enumerate(meta_rows):
        meta_table.cell(row_index, 0).text = label
        meta_table.cell(row_index, 1).text = value
        _set_cell_shading(meta_table.cell(row_index, 0), LIGHT_BLUE)
        meta_table.cell(row_index, 0).paragraphs[0].runs[0].font.bold = True
    document.add_paragraph()
    notice = document.add_paragraph(
        "本成果由 AI 基于企业已授权资料辅助生成。参数、价格、交期、案例和对外承诺以最终人工审核版本为准。"
    )
    notice.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in notice.runs:
        run.font.size = Pt(8.5)
        run.font.color.rgb = RGBColor.from_string(TEXT_MUTED)
    document.add_page_break()

    headings = [
        re.sub(r"^#{1,3}\s+", "", line).strip()
        for line in sanitized.content.splitlines()
        if re.match(r"^#{1,3}\s+", line)
    ]
    if headings:
        document.add_heading("目录", level=1)
        for position, heading in enumerate(headings[:24], 1):
            document.add_paragraph(f"{position:02d}  {heading}")
        document.add_page_break()

    _render_markdown(document, sanitized.content)
    if sanitized.source_notes:
        document.add_page_break()
        document.add_heading("资料来源", level=1)
        for note in sanitized.source_notes:
            document.add_paragraph(
                f"[{note['number']}] {note['title']} · 版本 {note['version']}",
                style="Source Note",
            )

    for doc_section in document.sections:
        header = doc_section.header.paragraphs[0]
        header.text = f"{company}  |  {title}"
        header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for run in header.runs:
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor.from_string(TEXT_MUTED)
        _add_page_number(doc_section.footer.paragraphs[0])

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _pdf_rows(markdown: str) -> Iterable[tuple[str, str]]:
    for line in markdown.splitlines():
        value = line.strip()
        if not value or re.match(r"^\|?\s*:?-{3,}", value):
            continue
        if value.startswith("### "):
            yield "Heading3", value[4:]
        elif value.startswith("## "):
            yield "Heading2", value[3:]
        elif value.startswith("# "):
            yield "Heading1", value[2:]
        else:
            yield "BodyText", value.lstrip("-*>").strip()


def render_artifact_pdf(
    artifact: dict[str, Any],
    evidence_packet: dict[str, Any] | None = None,
    brand: dict[str, Any] | None = None,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    sanitized = sanitize_artifact_content(
        str(artifact.get("content_markdown") or ""), evidence_packet
    )
    buffer = io.BytesIO()
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "STSong-Light"
    styles.add(
        ParagraphStyle(
            name="NexusNotice",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=8.5,
            leading=14,
            textColor=colors.HexColor("#667085"),
        )
    )
    title = str(artifact.get("title") or "AI 成果")
    company = str((brand or {}).get("company_name") or "Nexus AI")
    story = [
        Spacer(1, 38 * mm),
        Paragraph(escape(company), styles["Heading3"]),
        Spacer(1, 8 * mm),
        Paragraph(escape(title), styles["Title"]),
        Spacer(1, 8 * mm),
        Paragraph("科学仪器专业成果", styles["Heading2"]),
        Spacer(1, 24 * mm),
        Paragraph(
            "本成果由 AI 基于企业已授权资料辅助生成，外发前须完成事实与承诺复核。",
            styles["NexusNotice"],
        ),
        PageBreak(),
    ]
    for style_name, value in _pdf_rows(sanitized.content):
        story.append(Paragraph(escape(value), styles[style_name]))
        story.append(Spacer(1, 2.5 * mm))
    if sanitized.source_notes:
        story.extend([PageBreak(), Paragraph("资料来源", styles["Heading1"])])
        for note in sanitized.source_notes:
            story.append(
                Paragraph(
                    escape(
                        f"[{note['number']}] {note['title']} · 版本 {note['version']}"
                    ),
                    styles["NexusNotice"],
                )
            )
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
        author=company,
    )
    document.build(story)
    return buffer.getvalue()


def render_artifact_xlsx(
    artifact: dict[str, Any], evidence_packet: dict[str, Any] | None = None
) -> bytes:
    sanitized = sanitize_artifact_content(
        str(artifact.get("content_markdown") or ""), evidence_packet
    )
    workbook = Workbook()
    summary = workbook.active
    summary.title = "成果摘要"
    summary.append(["成果名称", artifact.get("title")])
    summary.append(["版本", artifact.get("version_number") or 1])
    summary.append(["质量评分", artifact.get("quality_score")])
    summary.append(["审批状态", artifact.get("approval_status")])
    summary.append([])
    summary.append(["正文"])
    for line in sanitized.content.splitlines():
        if line.strip():
            summary.append([line.strip()])

    evidence = workbook.create_sheet("证据清单")
    evidence.append(["序号", "资料", "版本", "文档 ID", "片段 ID"])
    for note in sanitized.source_notes:
        evidence.append(
            [
                note["number"],
                note["title"],
                note["version"],
                note["document_id"],
                note["chunk_id"],
            ]
        )
    verification = workbook.create_sheet("待核验项")
    verification.append(["序号", "待核验内容", "处理状态"])
    for index, line in enumerate(
        [item for item in sanitized.content.splitlines() if "待核验" in item], 1
    ):
        verification.append([index, line.strip(), "待确认"])

    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=BRAND_BLUE)
        for row in sheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        for column in sheet.columns:
            letter = column[0].column_letter
            sheet.column_dimensions[letter].width = min(
                72, max(14, max(len(str(cell.value or "")) for cell in column) + 2)
            )
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
