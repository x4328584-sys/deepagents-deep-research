"""FastAPI REST and thread-scoped WebSocket application."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.websockets import WebSocketDisconnect

from agent.runtime import ModeAwareResearchRunner, ResearchRunner
from api.logger import configure_logging
from api.schemas import FileInfo, TaskRequest, TaskResponse, TaskStatusResponse, UploadResponse
from api.task_service import TaskRegistry, TaskService
from api.websocket_manager import WebSocketManager
from utils.config import Settings, get_settings
from utils.path_utils import (
    ensure_runtime_roots,
    safe_existing_file,
    safe_join,
    upload_session_dir,
)
from utils.security import SecurityError, sanitize_filename, validate_thread_id


def _unique_destination(directory: Path, filename: str) -> Path:
    candidate = safe_join(directory, filename, allow_root=False)
    counter = 1
    while candidate.exists():
        candidate = safe_join(
            directory,
            f"{Path(filename).stem}-{counter}{Path(filename).suffix}",
            allow_root=False,
        )
        counter += 1
    return candidate


def _list_output_files(root: Path, requested: Path) -> list[FileInfo]:
    paths = [requested] if requested.is_file() else list(requested.rglob("*"))
    results = []
    for path in paths:
        if path.is_symlink() or not path.is_file():
            continue
        try:
            canonical = safe_existing_file(root, path.relative_to(root).as_posix())
        except (SecurityError, FileNotFoundError, ValueError):
            continue
        stat = canonical.stat()
        results.append(
            FileInfo(
                name=canonical.name,
                path=canonical.relative_to(root).as_posix(),
                size=stat.st_size,
                mtime=stat.st_mtime,
            )
        )
    return sorted(results, key=lambda item: item.mtime, reverse=True)


def create_app(
    settings: Settings | None = None,
    *,
    runner: ResearchRunner | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    manager = WebSocketManager()
    runtime = runner or ModeAwareResearchRunner(app_settings)
    registry = TaskRegistry()
    task_service = TaskService(app_settings, manager, runtime)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        ensure_runtime_roots(app_settings.output_root, app_settings.upload_root)
        configure_logging(app_settings.log_dir, app_settings.log_level)
        yield
        await registry.shutdown()

    application = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        description="Hierarchical DeepAgents research API",
        lifespan=lifespan,
    )
    allow_credentials = "*" not in app_settings.cors_origins
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
    application.state.settings = app_settings
    application.state.websocket_manager = manager
    application.state.task_registry = registry

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": "demo" if app_settings.demo_mode else "real"}

    @application.post("/api/task", response_model=TaskResponse)
    async def start_task(request: TaskRequest) -> TaskResponse:
        if len(request.query) > app_settings.max_query_chars:
            raise HTTPException(status_code=413, detail="query exceeds configured size limit")
        thread_id = request.thread_id or str(uuid.uuid4())
        started = await registry.start(
            thread_id,
            lambda: task_service.execute(thread_id, request.query),
        )
        if not started:
            raise HTTPException(status_code=409, detail="a task is already running for thread_id")
        return TaskResponse(thread_id=thread_id)

    @application.get("/api/task/{thread_id}", response_model=TaskStatusResponse)
    async def task_status(thread_id: str) -> TaskStatusResponse:
        try:
            valid_id = validate_thread_id(thread_id)
        except SecurityError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        status = await registry.status(valid_id)
        if status == "not_found":
            raise HTTPException(status_code=404, detail="task not found")
        return TaskStatusResponse(thread_id=valid_id, status=status)

    @application.post("/api/upload", response_model=UploadResponse)
    async def upload_files(
        files: Annotated[list[UploadFile], File()],
        thread_id: Annotated[str, Form()],
    ) -> UploadResponse:
        try:
            valid_id = validate_thread_id(thread_id)
        except SecurityError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not files:
            raise HTTPException(status_code=422, detail="at least one file is required")
        if len(files) > app_settings.max_upload_files:
            raise HTTPException(status_code=413, detail="too many files in one upload")
        if not await registry.begin_upload(valid_id):
            raise HTTPException(
                status_code=409,
                detail="cannot upload while this thread is busy",
            )

        try:
            try:
                directory = upload_session_dir(app_settings.upload_root, valid_id)
                directory.mkdir(parents=True, exist_ok=True)
            except SecurityError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            created: list[Path] = []
            names: list[str] = []
            try:
                for upload in files:
                    try:
                        name = sanitize_filename(upload.filename or "")
                    except SecurityError as exc:
                        raise HTTPException(status_code=400, detail=str(exc)) from exc
                    destination = _unique_destination(directory, name)
                    temporary = destination.with_name(f".{destination.name}.uploading")
                    size = 0
                    try:
                        async with aiofiles.open(temporary, "wb") as handle:
                            while chunk := await upload.read(64 * 1024):
                                size += len(chunk)
                                if size > app_settings.max_upload_bytes:
                                    raise HTTPException(
                                        status_code=413,
                                        detail=f"file exceeds size limit: {name}",
                                    )
                                await handle.write(chunk)
                        temporary.replace(destination)
                    finally:
                        temporary.unlink(missing_ok=True)
                        await upload.close()
                    created.append(destination)
                    names.append(destination.name)
            except Exception:
                for path in created:
                    path.unlink(missing_ok=True)
                raise
            return UploadResponse(files=names)
        finally:
            await registry.finish_upload(valid_id)

    @application.get("/api/files", response_model=list[FileInfo])
    async def list_files(path: str = Query(default=".")) -> list[FileInfo]:
        try:
            requested = safe_join(
                app_settings.output_root, path, must_exist=True, allow_root=True
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="output path not found") from exc
        except SecurityError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return _list_output_files(app_settings.output_root.resolve(), requested)

    @application.get("/api/download", response_class=FileResponse)
    async def download_file(path: str = Query(...)) -> FileResponse:
        try:
            requested = safe_existing_file(app_settings.output_root, path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="output file not found") from exc
        except SecurityError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return FileResponse(requested, filename=requested.name)

    @application.websocket("/ws/{thread_id}")
    async def task_websocket(websocket: WebSocket, thread_id: str) -> None:
        try:
            valid_id = validate_thread_id(thread_id)
        except SecurityError:
            await websocket.close(code=1008, reason="invalid thread_id")
            return
        if not await manager.connect(valid_id, websocket):
            return
        try:
            while True:
                message = await websocket.receive_text()
                if message == "ping":
                    sent = await manager.send_json(
                        websocket,
                        {"type": "pong", "message": "服务端已收到: ping"},
                    )
                    if not sent:
                        return
        except WebSocketDisconnect:
            pass
        finally:
            await manager.disconnect(valid_id, websocket)

    return application


app = create_app()
