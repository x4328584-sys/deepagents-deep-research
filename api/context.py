"""Task-local thread and filesystem context."""

from __future__ import annotations

import asyncio
import os
import shutil
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from pathlib import Path

from utils.path_utils import output_session_dir, upload_session_dir

current_thread_id: ContextVar[str | None] = ContextVar("current_thread_id", default=None)
current_session_dir: ContextVar[Path | None] = ContextVar("current_session_dir", default=None)


@dataclass
class SearchBudget:
    count: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


current_search_budget: ContextVar[SearchBudget | None] = ContextVar(
    "current_search_budget", default=None
)


class MissingTaskContext(RuntimeError):
    """Raised when a task-bound tool is called outside a research task."""


def get_thread_id() -> str:
    value = current_thread_id.get()
    if value is None:
        raise MissingTaskContext("thread_id is not bound to the current task")
    return value


def get_session_dir() -> Path:
    value = current_session_dir.get()
    if value is None:
        raise MissingTaskContext("session_dir is not bound to the current task")
    return value


def consume_search_call(limit: int) -> int:
    """Increment and return the task-local search count, enforcing its cap."""
    budget = current_search_budget.get()
    if budget is None:
        budget = SearchBudget()
        current_search_budget.set(budget)
    with budget.lock:
        next_count = budget.count + 1
        if next_count > limit:
            raise RuntimeError(f"search call limit exceeded ({limit})")
        budget.count = next_count
        return next_count


@contextmanager
def bind_task_context(thread_id: str, session_dir: Path) -> Iterator[None]:
    thread_token: Token[str | None] = current_thread_id.set(thread_id)
    session_token: Token[Path | None] = current_session_dir.set(session_dir.resolve())
    search_token: Token[SearchBudget | None] = current_search_budget.set(SearchBudget())
    try:
        yield
    finally:
        current_search_budget.reset(search_token)
        current_session_dir.reset(session_token)
        current_thread_id.reset(thread_token)


def _prepare_session_sync(output_root: Path, upload_root: Path, thread_id: str) -> Path:
    session_dir = output_session_dir(output_root, thread_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    source_dir = upload_session_dir(upload_root, thread_id)
    if source_dir.exists():
        for source in source_dir.iterdir():
            if not source.is_file() or source.is_symlink():
                continue
            destination = session_dir / source.name
            if destination.exists():
                if destination.read_bytes() == source.read_bytes():
                    continue
                raise FileExistsError(f"session file already exists: {source.name}")
            temporary = destination.with_name(f".{destination.name}.copying")
            try:
                shutil.copy2(source, temporary)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
    return session_dir


async def prepare_session(output_root: Path, upload_root: Path, thread_id: str) -> Path:
    return await asyncio.to_thread(_prepare_session_sync, output_root, upload_root, thread_id)
