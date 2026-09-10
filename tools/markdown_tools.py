"""Session-confined Markdown report generation."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from api.context import get_session_dir
from utils.path_utils import safe_join
from utils.security import SecurityError, sanitize_filename

PLACEHOLDER_ONLY = {
    "todo",
    "[todo]",
    "等待搜索结果",
    "稍后补充",
    "waiting for search results",
}


def _validate_content(content: str) -> str:
    normalized = content.strip()
    if len(normalized) < 20:
        raise ValueError("report content is too short to be a completed document")
    if normalized.casefold() in PLACEHOLDER_ONLY:
        raise ValueError("placeholder reports are not allowed")
    return f"{normalized}\n"


def _generate_markdown_sync(filename: str, content: str) -> dict[str, Any]:
    safe_name = sanitize_filename(filename, allowed_extensions={".md"})
    session_dir = get_session_dir()
    destination = safe_join(session_dir, safe_name, allow_root=False)
    validated = _validate_content(content)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        temporary.write_text(validated, encoding="utf-8", newline="\n")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "ok": True,
        "name": destination.name,
        "path": destination.name,
        "size": destination.stat().st_size,
    }


async def generate_markdown(filename: str, content: str) -> dict[str, Any]:
    """Atomically write a complete Markdown report in the active session."""
    try:
        return await asyncio.to_thread(_generate_markdown_sync, filename, content)
    except (SecurityError, ValueError) as exc:
        return {"ok": False, "error": {"code": "invalid_report", "message": str(exc)}}
    except OSError as exc:
        return {
            "ok": False,
            "error": {
                "code": "write_error",
                "message": f"Markdown write failed: {type(exc).__name__}",
            },
        }


def make_markdown_tool() -> BaseTool:
    return StructuredTool.from_function(
        coroutine=generate_markdown,
        name="generate_markdown",
        description=(
            "Write a complete Markdown report into the current session. Call only after all "
            "required research has returned. Placeholder content is rejected."
        ),
    )
