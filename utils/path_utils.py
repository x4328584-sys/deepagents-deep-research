"""Canonical path resolution for session and public output scopes."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from utils.security import SecurityError, repeatedly_unquote, validate_thread_id

WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:")


def ensure_runtime_roots(output_root: Path, upload_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    upload_root.mkdir(parents=True, exist_ok=True)


def session_name(thread_id: str) -> str:
    return f"session_{validate_thread_id(thread_id)}"


def output_session_dir(output_root: Path, thread_id: str) -> Path:
    return safe_join(output_root, session_name(thread_id), allow_root=False)


def upload_session_dir(upload_root: Path, thread_id: str) -> Path:
    return safe_join(upload_root, session_name(thread_id), allow_root=False)


def safe_join(
    root: Path,
    supplied_path: str,
    *,
    must_exist: bool = False,
    allow_root: bool = True,
) -> Path:
    """Resolve an untrusted relative path beneath root, including encoded input."""
    if not isinstance(supplied_path, str) or "\x00" in supplied_path:
        raise SecurityError("invalid path")
    decoded = repeatedly_unquote(supplied_path.strip()).replace("\\", "/")
    if WINDOWS_DRIVE_PATTERN.match(decoded) or decoded.startswith(("/", "//")):
        raise SecurityError("absolute paths are not allowed")

    pure = PurePosixPath(decoded or ".")
    if any(part == ".." for part in pure.parts):
        raise SecurityError("path traversal is not allowed")

    root_resolved = root.resolve(strict=False)
    candidate = (root_resolved / Path(*pure.parts)).resolve(strict=False)
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise SecurityError("path escapes the permitted root") from exc
    if not allow_root and candidate == root_resolved:
        raise SecurityError("root path is not allowed")
    if must_exist and not candidate.exists():
        raise FileNotFoundError(candidate)
    return candidate


def safe_existing_file(root: Path, supplied_path: str) -> Path:
    candidate = safe_join(root, supplied_path, must_exist=True, allow_root=False)
    if not candidate.is_file():
        raise SecurityError("path is not a regular file")
    return candidate

