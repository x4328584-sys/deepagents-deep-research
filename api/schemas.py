"""Pydantic API contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from utils.security import validate_thread_id


class TaskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=100_000)
    thread_id: str | None = None

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query cannot be blank")
        return normalized

    @field_validator("thread_id")
    @classmethod
    def valid_optional_thread_id(cls, value: str | None) -> str | None:
        return validate_thread_id(value) if value is not None else None


class TaskResponse(BaseModel):
    status: str = "started"
    thread_id: str


class UploadResponse(BaseModel):
    status: str = "uploaded"
    files: list[str]


class FileInfo(BaseModel):
    name: str
    type: str = "file"
    path: str
    size: int
    mtime: float


class TaskStatusResponse(BaseModel):
    thread_id: str
    status: str

