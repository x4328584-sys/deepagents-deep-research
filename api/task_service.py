"""Asynchronous task lifecycle and per-thread execution service."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

from agent.runtime import ResearchRunner
from api.context import bind_task_context, prepare_session
from api.logger import log_event
from api.monitor import Monitor
from api.websocket_manager import WebSocketManager
from utils.config import Settings
from utils.path_utils import session_name

logger = logging.getLogger(__name__)


class TaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._uploads: set[str] = set()
        self._lock = asyncio.Lock()

    async def start(
        self,
        thread_id: str,
        factory: Callable[[], Coroutine[Any, Any, None]],
    ) -> bool:
        async with self._lock:
            if thread_id in self._uploads:
                return False
            current = self._tasks.get(thread_id)
            if current is not None and not current.done():
                return False
            task: asyncio.Task[None] = asyncio.create_task(
                factory(), name=f"research-{thread_id}"
            )
            task.add_done_callback(self._consume_background_exception)
            self._tasks[thread_id] = task
            return True

    async def begin_upload(self, thread_id: str) -> bool:
        """Reserve one thread for upload so task startup and uploads cannot race."""
        async with self._lock:
            current = self._tasks.get(thread_id)
            if thread_id in self._uploads or (current is not None and not current.done()):
                return False
            self._uploads.add(thread_id)
            return True

    async def finish_upload(self, thread_id: str) -> None:
        async with self._lock:
            self._uploads.discard(thread_id)

    @staticmethod
    def _consume_background_exception(task: asyncio.Task[None]) -> None:
        """Retrieve task failures so the event loop does not log private details."""
        if task.cancelled():
            return
        task.exception()

    async def status(self, thread_id: str) -> str:
        async with self._lock:
            task = self._tasks.get(thread_id)
        if task is None:
            return "not_found"
        if task.cancelled():
            return "cancelled"
        if not task.done():
            return "running"
        return "failed" if task.exception() is not None else "completed"

    async def wait(self, thread_id: str, wait_seconds: float = 10) -> None:
        async with self._lock:
            task = self._tasks.get(thread_id)
        if task is None:
            raise KeyError(thread_id)
        await asyncio.wait_for(asyncio.shield(task), timeout=wait_seconds)

    async def shutdown(self) -> None:
        async with self._lock:
            tasks = [task for task in self._tasks.values() if not task.done()]
            self._uploads.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


class TaskService:
    def __init__(
        self,
        settings: Settings,
        manager: WebSocketManager,
        runner: ResearchRunner,
    ) -> None:
        self.settings = settings
        self.manager = manager
        self.runner = runner

    async def execute(self, thread_id: str, query: str) -> None:
        started = time.monotonic()
        monitor = Monitor(self.manager, thread_id)
        try:
            session_dir = await prepare_session(
                self.settings.output_root, self.settings.upload_root, thread_id
            )
            await monitor.session_created(session_name(thread_id))
            with bind_task_context(thread_id, session_dir):
                result = await self.runner.run(query, monitor)
            await monitor.task_result(result)
            log_event(
                logger,
                "task_completed",
                thread_id=thread_id,
                agent="main_agent",
                duration=round(time.monotonic() - started, 4),
                success=True,
            )
        except asyncio.CancelledError:
            await monitor.error("Research task was cancelled")
            raise
        except Exception as exc:
            public_error = f"Research task failed: {type(exc).__name__}"
            await monitor.error(public_error)
            logger.exception(
                "task_failed",
                extra={
                    "context": {
                        "event": "task_failed",
                        "thread_id": thread_id,
                        "agent": "main_agent",
                        "duration": round(time.monotonic() - started, 4),
                        "success": False,
                        "error": type(exc).__name__,
                    }
                },
            )
            raise
