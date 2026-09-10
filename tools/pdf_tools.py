"""Cross-platform Markdown-to-PDF conversion using ReportLab."""

from __future__ import annotations

import asyncio
import os
from html import escape
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from api.context import get_session_dir
from utils.path_utils import safe_existing_file, safe_join
from utils.security import SecurityError, sanitize_filename

CJK_FONT = "STSong-Light"


def _register_font() -> None:
    try:
        pdfmetrics.getFont(CJK_FONT)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(CJK_FONT))


def _styles() -> dict[str, ParagraphStyle]:
    _register_font()
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "CJKBody",
            parent=base["BodyText"],
            fontName=CJK_FONT,
            fontSize=10.5,
            leading=16,
            spaceAfter=5,
        ),
        "h1": ParagraphStyle(
            "CJKHeading1",
            parent=base["Heading1"],
            fontName=CJK_FONT,
            fontSize=20,
            leading=26,
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "h2": ParagraphStyle(
            "CJKHeading2",
            parent=base["Heading2"],
            fontName=CJK_FONT,
            fontSize=15,
            leading=21,
            spaceBefore=10,
            spaceAfter=7,
        ),
        "h3": ParagraphStyle(
            "CJKHeading3",
            parent=base["Heading3"],
            fontName=CJK_FONT,
            fontSize=12,
            leading=18,
            spaceBefore=7,
            spaceAfter=5,
        ),
        "code": ParagraphStyle(
            "CJKCode",
            parent=base["Code"],
            fontName=CJK_FONT,
            fontSize=8.5,
            leading=12,
            leftIndent=8,
            backColor="#F3F4F6",
            borderPadding=5,
        ),
    }


def _markdown_story(markdown: str) -> list[Any]:
    styles = _styles()
    story: list[Any] = []
    in_code = False
    code_lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            if in_code:
                code_content = "<br/>".join(escape(item) for item in code_lines)
                story.append(Paragraph(code_content, styles["code"]))
                story.append(Spacer(1, 3 * mm))
                code_lines = []
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line or " ")
            continue
        if not line:
            story.append(Spacer(1, 2 * mm))
        elif line.startswith("### "):
            story.append(Paragraph(escape(line[4:]), styles["h3"]))
        elif line.startswith("## "):
            story.append(Paragraph(escape(line[3:]), styles["h2"]))
        elif line.startswith("# "):
            story.append(Paragraph(escape(line[2:]), styles["h1"]))
        elif line.startswith(("- ", "* ")):
            story.append(Paragraph(f"• {escape(line[2:])}", styles["body"]))
        else:
            story.append(Paragraph(escape(line), styles["body"]))
    if code_lines:
        story.append(Paragraph("<br/>".join(escape(item) for item in code_lines), styles["code"]))
    return story


def _convert_sync(markdown_path: str, pdf_filename: str | None) -> dict[str, Any]:
    session_dir = get_session_dir()
    source = safe_existing_file(session_dir, markdown_path)
    if source.suffix.lower() != ".md":
        raise SecurityError("PDF conversion source must be a Markdown file")
    target_name = pdf_filename or f"{source.stem}.pdf"
    safe_name = sanitize_filename(target_name, allowed_extensions={".pdf"})
    destination = safe_join(session_dir, safe_name, allow_root=False)
    temporary = destination.with_name(f".{destination.name}.tmp")
    markdown = source.read_text(encoding="utf-8")
    if not markdown.strip():
        raise ValueError("cannot convert an empty Markdown document")
    try:
        document = SimpleDocTemplate(
            str(temporary),
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title=source.stem,
            author="DeepAgents Deep Research",
        )
        document.build(_markdown_story(markdown))
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "ok": True,
        "name": destination.name,
        "path": destination.name,
        "size": destination.stat().st_size,
        "source": source.name,
    }


async def convert_md_to_pdf(
    markdown_path: str, pdf_filename: str | None = None
) -> dict[str, Any]:
    """Convert an existing session Markdown report to a session PDF."""
    try:
        return await asyncio.to_thread(_convert_sync, markdown_path, pdf_filename)
    except FileNotFoundError:
        return {"ok": False, "error": {"code": "not_found", "message": "Markdown file not found"}}
    except (SecurityError, ValueError) as exc:
        return {"ok": False, "error": {"code": "invalid_pdf_request", "message": str(exc)}}
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "code": "pdf_error",
                "message": f"PDF conversion failed: {type(exc).__name__}",
            },
        }


def make_pdf_tool() -> BaseTool:
    return StructuredTool.from_function(
        coroutine=convert_md_to_pdf,
        name="convert_md_to_pdf",
        description=(
            "Convert a complete Markdown report in the current session to PDF. The Markdown "
            "file must already exist; use generate_markdown first."
        ),
    )
