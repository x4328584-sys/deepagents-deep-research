"""Input and SQL security controls enforced outside prompts."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path, PurePath
from urllib.parse import unquote

import sqlglot
from sqlglot import expressions as exp

THREAD_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
SAFE_STEM_PATTERN = re.compile(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+")
SQL_COMMENT_PATTERN = re.compile(r"(--|#|/\*)")
SQL_FORBIDDEN_PATTERN = re.compile(
    r"\b(INTO\s+(?:OUTFILE|DUMPFILE)|LOAD_FILE|SLEEP|BENCHMARK|GET_LOCK|RELEASE_LOCK)\b",
    re.IGNORECASE,
)
ALLOWED_UPLOAD_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".jsonl",
    ".csv",
    ".docx",
    ".pdf",
    ".xlsx",
    ".xls",
}
ALLOWED_SQL_PREFIXES = {"SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN"}
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
MUTATING_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Merge,
    exp.TruncateTable,
)


class SecurityError(ValueError):
    """Raised for an unsafe user-, model-, or provider-controlled value."""


def validate_thread_id(value: str) -> str:
    candidate = value.strip()
    if not THREAD_ID_PATTERN.fullmatch(candidate):
        raise SecurityError(
            "thread_id must be 1-64 characters using letters, numbers, '_' or '-'"
        )
    return candidate


def repeatedly_unquote(value: str, rounds: int = 3) -> str:
    decoded = value
    for _ in range(rounds):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    return decoded


def sanitize_filename(filename: str, allowed_extensions: set[str] | None = None) -> str:
    """Return a portable basename while rejecting traversal and unsupported types."""
    if not filename or "\x00" in filename:
        raise SecurityError("invalid filename")
    decoded = repeatedly_unquote(unicodedata.normalize("NFKC", filename)).replace("\\", "/")
    if "/" in decoded or decoded in {".", ".."}:
        raise SecurityError("filename must not contain a path")
    basename = PurePath(decoded).name
    if basename in {"", ".", ".."}:
        raise SecurityError("invalid filename")

    cleaned = SAFE_STEM_PATTERN.sub("_", basename).strip(" .")
    cleaned = re.sub(r"_+", "_", cleaned)
    if not cleaned or cleaned.startswith("."):
        raise SecurityError("invalid filename")
    if Path(cleaned).stem.upper() in WINDOWS_RESERVED_NAMES:
        raise SecurityError("reserved filename")
    if len(cleaned) > 120:
        suffix = Path(cleaned).suffix
        cleaned = f"{Path(cleaned).stem[: 120 - len(suffix)]}{suffix}"

    extension_allowlist = allowed_extensions or ALLOWED_UPLOAD_EXTENSIONS
    if Path(cleaned).suffix.lower() not in extension_allowlist:
        raise SecurityError("unsupported file extension")
    return cleaned


def validate_sql_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", value):
        raise SecurityError("invalid SQL identifier")
    return value


def validate_readonly_sql(statement: str) -> str:
    """Validate a single, read-only MySQL statement and return normalized input."""
    sql = statement.strip()
    if not sql:
        raise SecurityError("SQL query cannot be empty")
    if SQL_COMMENT_PATTERN.search(sql):
        raise SecurityError("SQL comments are not allowed")

    without_trailing = sql[:-1].rstrip() if sql.endswith(";") else sql
    if ";" in without_trailing:
        raise SecurityError("multiple SQL statements are not allowed")
    if SQL_FORBIDDEN_PATTERN.search(without_trailing):
        raise SecurityError("unsafe SQL function or file operation")

    first_token = without_trailing.split(None, 1)[0].upper()
    if first_token not in ALLOWED_SQL_PREFIXES:
        raise SecurityError("only SELECT, SHOW, DESCRIBE/DESC, and EXPLAIN are allowed")

    try:
        parsed = sqlglot.parse(without_trailing, read="mysql")
    except sqlglot.errors.ParseError as exc:
        raise SecurityError("invalid SQL syntax") from exc
    if len(parsed) != 1 or parsed[0] is None:
        raise SecurityError("multiple SQL statements are not allowed")
    expression = parsed[0]
    if any(expression.find(node_type) is not None for node_type in MUTATING_EXPRESSIONS):
        raise SecurityError("mutating SQL is not allowed")
    return without_trailing
