import asyncio
import json
import logging
from pathlib import Path

import pytest

from api.context import (
    MissingTaskContext,
    bind_task_context,
    consume_search_call,
    get_session_dir,
    get_thread_id,
)
from api.logger import JsonFormatter
from api.monitor import Monitor
from api.task_service import TaskRegistry
from api.websocket_manager import WebSocketManager


class RecordingManager:
    def __init__(self) -> None:
        self.events: dict[str, list[dict[str, object]]] = {}

    async def broadcast(self, thread_id: str, payload: dict[str, object]) -> None:
        self.events.setdefault(thread_id, []).append(payload)


async def test_contextvars_isolate_concurrent_tasks(tmp_path: Path) -> None:
    ready = asyncio.Event()
    observed: dict[str, tuple[str, Path]] = {}

    async def worker(name: str) -> None:
        with bind_task_context(name, tmp_path / name):
            if name == "thread-a":
                ready.set()
                await asyncio.sleep(0.02)
            else:
                await ready.wait()
            observed[name] = (get_thread_id(), get_session_dir())

    await asyncio.gather(worker("thread-a"), worker("thread-b"))
    assert observed == {
        "thread-a": ("thread-a", (tmp_path / "thread-a").resolve()),
        "thread-b": ("thread-b", (tmp_path / "thread-b").resolve()),
    }
    with pytest.raises(MissingTaskContext):
        get_thread_id()


def test_contextvars_reset_after_exception(tmp_path: Path) -> None:
    with (
        pytest.raises(RuntimeError, match="forced failure"),
        bind_task_context("thread-error", tmp_path),
    ):
        assert get_thread_id() == "thread-error"
        raise RuntimeError("forced failure")
    with pytest.raises(MissingTaskContext):
        get_thread_id()
    with pytest.raises(MissingTaskContext):
        get_session_dir()


async def test_contextvars_reset_after_cancellation(tmp_path: Path) -> None:
    ready = asyncio.Event()
    reset_observed = asyncio.Event()

    async def worker() -> None:
        try:
            with bind_task_context("thread-cancel", tmp_path):
                ready.set()
                await asyncio.Event().wait()
        except asyncio.CancelledError:
            with pytest.raises(MissingTaskContext):
                get_thread_id()
            reset_observed.set()
            raise

    task = asyncio.create_task(worker())
    await ready.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert reset_observed.is_set()


async def test_search_budget_is_shared_by_concurrent_child_contexts(tmp_path: Path) -> None:
    async def consume() -> int | str:
        await asyncio.sleep(0)
        try:
            return consume_search_call(5)
        except RuntimeError:
            return "blocked"

    with bind_task_context("thread-a", tmp_path):
        results = await asyncio.gather(*(consume() for _ in range(7)))
    assert sorted(item for item in results if isinstance(item, int)) == [1, 2, 3, 4, 5]
    assert results.count("blocked") == 2


async def test_monitor_emits_all_public_event_shapes() -> None:
    manager = RecordingManager()
    monitor = Monitor(manager, "thread-a")  # type: ignore[arg-type]
    await monitor.session_created("session_thread-a")
    await monitor.tool_start("internet_search", {"query": "agents", "api_key": "hidden"})
    await monitor.assistant_call("network_search_agent", {"topic": "agents"})
    await monitor.task_result("done")
    await monitor.error("offline")

    events = manager.events["thread-a"]
    assert [event["event"] for event in events] == [
        "session_created",
        "tool_start",
        "assistant_call",
        "task_result",
        "error",
    ]
    tool_data = events[1]["data"]
    assert isinstance(tool_data, dict)
    assert tool_data["args"]["api_key"] == "[REDACTED]"  # type: ignore[index]
    assert all("timestamp" in event for event in events)


async def test_monitor_maps_task_and_regular_tool_calls() -> None:
    manager = RecordingManager()
    monitor = Monitor(manager, "thread-a")  # type: ignore[arg-type]
    await monitor.observe_tool_calls(
        [
            {"id": "1", "name": "task", "args": {"subagent_type": "database_query_agent"}},
            {"id": "2", "name": "generate_markdown", "args": {"filename": "report.md"}},
        ]
    )
    assert [event["event"] for event in manager.events["thread-a"]] == [
        "assistant_call",
        "tool_start",
    ]


async def test_monitor_redacts_secret_like_values_and_keeps_full_result() -> None:
    manager = RecordingManager()
    monitor = Monitor(manager, "thread-a")  # type: ignore[arg-type]
    secret_like = "sk-" + "a" * 24
    result = "x" * 3_000 + secret_like
    await monitor.task_result(result)
    public_result = manager.events["thread-a"][0]["data"]["result"]  # type: ignore[index]
    assert len(public_result) > 3_000
    assert secret_like not in public_result
    assert "[REDACTED_SECRET]" in public_result


def test_json_formatter_redacts_plain_message_and_context_secrets() -> None:
    secret_like = "sk-" + "b" * 24
    record = logging.LogRecord(
        name="provider",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=f"provider failed api_key={secret_like}",
        args=(),
        exc_info=None,
    )
    record.context = {"password": "database-value", "thread_id": "safe-thread"}

    payload = json.loads(JsonFormatter().format(record))
    assert secret_like not in payload["message"]
    assert "[REDACTED_SECRET]" in payload["message"]
    assert payload["password"] == "[REDACTED]"
    assert payload["thread_id"] == "safe-thread"


class BlockingSocket:
    def __init__(self, *, block_first_send: bool = False) -> None:
        self.accepted = False
        self.sent: list[dict[str, object]] = []
        self.block_first_send = block_first_send
        self.first_send_started = asyncio.Event()
        self.release_first_send = asyncio.Event()

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict[str, object]) -> None:
        if self.block_first_send and not self.sent:
            self.first_send_started.set()
            await self.release_first_send.wait()
        self.sent.append(payload)


async def test_websocket_replay_is_ordered_before_live_broadcast() -> None:
    manager = WebSocketManager()
    old_event = {"event": "session_created"}
    new_event = {"event": "tool_start"}
    await manager.broadcast("thread-a", old_event)

    socket = BlockingSocket(block_first_send=True)
    connecting = asyncio.create_task(
        manager.connect("thread-a", socket)  # type: ignore[arg-type]
    )
    await socket.first_send_started.wait()
    broadcasting = asyncio.create_task(manager.broadcast("thread-a", new_event))
    await asyncio.sleep(0)
    assert socket.sent == []
    socket.release_first_send.set()
    assert await connecting is True
    await broadcasting
    assert socket.sent == [old_event, new_event]


async def test_websocket_manager_isolates_threads_and_serializes_sockets() -> None:
    manager = WebSocketManager()
    socket_a = BlockingSocket()
    socket_b = BlockingSocket()
    assert await manager.connect("thread-a", socket_a)  # type: ignore[arg-type]
    assert await manager.connect("thread-b", socket_b)  # type: ignore[arg-type]
    await manager.broadcast("thread-a", {"event": "task_result"})
    assert socket_a.sent == [{"event": "task_result"}]
    assert socket_b.sent == []


async def test_task_registry_prevents_upload_start_races() -> None:
    registry = TaskRegistry()
    assert await registry.begin_upload("thread-a") is True
    assert await registry.begin_upload("thread-a") is False
    assert await registry.start("thread-a", lambda: asyncio.sleep(0)) is False
    await registry.finish_upload("thread-a")

    release = asyncio.Event()

    async def running_task() -> None:
        await release.wait()

    assert await registry.start("thread-a", running_task) is True
    assert await registry.begin_upload("thread-a") is False
    release.set()
    await registry.wait("thread-a")
