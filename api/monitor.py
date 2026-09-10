"""Translate runtime actions into safe, public WebSocket events."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from api.logger import redact
from api.websocket_manager import WebSocketManager


class MonitorEvent(BaseModel):
    type: str = "monitor_event"
    event: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


def _bounded_public_data(data: dict[str, Any], max_text: int = 2_000) -> dict[str, Any]:
    redacted = redact(data)

    def bound(value: Any) -> Any:
        if isinstance(value, str):
            return value if len(value) <= max_text else f"{value[:max_text]}…"
        if isinstance(value, dict):
            return {str(key): bound(item) for key, item in value.items()}
        if isinstance(value, list):
            return [bound(item) for item in value[:50]]
        return value

    result = bound(redacted)
    return result if isinstance(result, dict) else {}


class Monitor:
    """Emits only explicit execution metadata, never hidden model reasoning."""

    def __init__(self, manager: WebSocketManager, thread_id: str) -> None:
        self.manager = manager
        self.thread_id = thread_id
        self._seen_tool_calls: set[str] = set()

    async def emit(
        self,
        event: str,
        message: str,
        data: dict[str, Any] | None = None,
        *,
        max_text: int = 2_000,
    ) -> None:
        model = MonitorEvent(
            event=event,
            message=message,
            data=_bounded_public_data(data or {}, max_text=max_text),
        )
        await self.manager.broadcast(
            self.thread_id,
            model.model_dump(mode="json"),
        )

    async def session_created(self, path: str) -> None:
        await self.emit("session_created", "Session workspace created", {"path": path})

    async def tool_start(self, tool_name: str, args: dict[str, Any] | None = None) -> None:
        await self.emit(
            "tool_start", f"Running tool: {tool_name}", {"tool_name": tool_name, "args": args or {}}
        )

    async def assistant_call(self, assistant_name: str, args: dict[str, Any] | None = None) -> None:
        await self.emit(
            "assistant_call",
            f"Delegating to assistant: {assistant_name}",
            {"assistant_name": assistant_name, "args": args or {}},
        )

    async def task_result(self, result: str) -> None:
        await self.emit(
            "task_result",
            "Research task completed",
            {"result": result},
            max_text=100_000,
        )

    async def error(self, error: str) -> None:
        await self.emit("error", "Research task failed", {"error": error})

    async def observe_tool_calls(
        self, tool_calls: Sequence[Mapping[str, Any]]
    ) -> None:
        """Map LangChain AIMessage tool calls without emitting message reasoning."""
        for call in tool_calls:
            call_id = str(call.get("id", ""))
            if call_id and call_id in self._seen_tool_calls:
                continue
            if call_id:
                self._seen_tool_calls.add(call_id)
            name = str(call.get("name", "unknown_tool"))
            raw_args = call.get("args")
            args: dict[str, Any] = raw_args if isinstance(raw_args, dict) else {}
            if name == "task":
                assistant_name = str(
                    args.get("subagent_type", args.get("assistant_name", "subagent"))
                )
                await self.assistant_call(assistant_name, args)
            else:
                await self.tool_start(name, args)
