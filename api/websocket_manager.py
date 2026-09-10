"""Thread-scoped WebSocket connections and bounded replay history."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self, history_size: int = 100) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._send_locks: dict[WebSocket, asyncio.Lock] = {}
        self._history: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=history_size)
        )
        self._lock = asyncio.Lock()

    async def connect(self, thread_id: str, websocket: WebSocket) -> bool:
        await websocket.accept()
        send_lock = asyncio.Lock()
        await send_lock.acquire()
        async with self._lock:
            self._send_locks[websocket] = send_lock
            self._connections[thread_id].add(websocket)
            history = list(self._history.get(thread_id, ()))
        replay_succeeded = True
        try:
            for event in history:
                if not await self._send_json_unlocked(websocket, event):
                    replay_succeeded = False
                    break
        finally:
            send_lock.release()
        if not replay_succeeded:
            await self.disconnect(thread_id, websocket)
        return replay_succeeded

    async def disconnect(self, thread_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(thread_id)
            if sockets is None:
                return
            sockets.discard(websocket)
            self._send_locks.pop(websocket, None)
            if not sockets:
                self._connections.pop(thread_id, None)

    async def send_json(self, websocket: WebSocket, payload: dict[str, Any]) -> bool:
        async with self._lock:
            send_lock = self._send_locks.get(websocket)
        if send_lock is None:
            return False
        async with send_lock:
            return await self._send_json_unlocked(websocket, payload)

    @staticmethod
    async def _send_json_unlocked(
        websocket: WebSocket, payload: dict[str, Any]
    ) -> bool:
        try:
            await websocket.send_json(payload)
            return True
        except (RuntimeError, OSError):
            return False

    async def broadcast(self, thread_id: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            self._history[thread_id].append(payload.copy())
            sockets = list(self._connections.get(thread_id, ()))
        sent = await asyncio.gather(*(self.send_json(socket, payload) for socket in sockets))
        failed = [socket for socket, succeeded in zip(sockets, sent, strict=True) if not succeeded]
        for socket in failed:
            await self.disconnect(thread_id, socket)

    async def connection_count(self, thread_id: str) -> int:
        async with self._lock:
            return len(self._connections.get(thread_id, ()))

    async def clear_history(self, thread_id: str) -> None:
        async with self._lock:
            self._history.pop(thread_id, None)
