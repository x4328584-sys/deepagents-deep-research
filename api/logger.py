"""Structured application logging with secret-field redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

SECRET_FIELD_FRAGMENTS = ("api_key", "authorization", "password", "secret", "token")
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"tvly-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|authorization|password|secret|token)\s*[:=]\s*"
        r"(?:Bearer\s+)?[^\s,;]+",
        re.IGNORECASE,
    ),
)


def redact(value: Any, key: str = "") -> Any:
    if any(fragment in key.lower() for fragment in SECRET_FIELD_FRAGMENTS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(item_key): redact(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        sanitized = value
        for pattern in SECRET_VALUE_PATTERNS:
            sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
        return sanitized
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(redact(context))
        if record.exc_info:
            exception_type = record.exc_info[0]
            payload["exception"] = exception_type.__name__ if exception_type else "Exception"
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(log_dir: Path, level: str = "INFO") -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(level)
    if any(getattr(handler, "_deep_research_handler", False) for handler in root.handlers):
        return

    formatter = JsonFormatter()
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console._deep_research_handler = True  # type: ignore[attr-defined]

    rotating = RotatingFileHandler(
        log_dir / "application.jsonl", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    rotating.setFormatter(formatter)
    rotating._deep_research_handler = True  # type: ignore[attr-defined]
    root.addHandler(console)
    root.addHandler(rotating)


def log_event(logger: logging.Logger, event: str, **context: Any) -> None:
    logger.info(event, extra={"context": {"event": event, **context}})
