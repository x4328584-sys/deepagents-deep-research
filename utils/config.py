"""Environment-only application configuration."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import BeforeValidator, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_origins(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "CORS_ORIGINS must be a JSON array or comma-separated list"
                ) from exc
        else:
            value = [item.strip() for item in stripped.split(",") if item.strip()]
    return value


Origins = Annotated[list[str], NoDecode, BeforeValidator(_parse_origins)]


class Settings(BaseSettings):
    """Validated runtime settings with safe Demo Mode defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "DeepAgents Deep Research"
    demo_mode: bool = True

    llm_model: str = "deepseek-v4-flash"
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.deepseek.com"
    llm_temperature: float = Field(default=0.1, ge=0, le=2)

    tavily_api_key: SecretStr | None = None

    mysql_host: str = "localhost"
    mysql_port: int = Field(default=3306, ge=1, le=65535)
    mysql_user: str = "research"
    mysql_password: SecretStr | None = None
    mysql_database: str = "company_data"

    ragflow_api_url: str | None = None
    ragflow_api_key: SecretStr | None = None

    cors_origins: Origins = ["http://localhost:5173"]
    external_timeout_seconds: float = Field(default=20, gt=0, le=120)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    max_extracted_chars: int = Field(default=200_000, ge=1_000, le=2_000_000)
    max_query_chars: int = Field(default=20_000, ge=100, le=100_000)
    max_agent_steps: int = Field(default=100, ge=10, le=500)
    max_search_calls: int = Field(default=5, ge=1, le=5)
    max_database_rows: int = Field(default=500, ge=1, le=5_000)
    max_upload_files: int = Field(default=10, ge=1, le=100)
    log_level: str = "INFO"

    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[1])

    @field_validator("openai_base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.rstrip("/")
        parsed = urlsplit(normalized)
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("OPENAI_BASE_URL must be a safe HTTP(S) URL") from exc
        if (
            parsed.scheme not in {"https", "http"}
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("OPENAI_BASE_URL must be an HTTP(S) URL")
        return normalized

    @field_validator("ragflow_api_url")
    @classmethod
    def normalize_optional_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("RAGFLOW_API_URL must be a safe HTTP(S) URL") from exc
        if (
            parsed.scheme not in {"https", "http"}
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("RAGFLOW_API_URL must be an HTTP(S) URL")
        return normalized

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            origin = value.strip().rstrip("/")
            if origin == "*":
                normalized.append(origin)
                continue
            parsed = urlsplit(origin)
            try:
                port = parsed.port
            except ValueError as exc:
                raise ValueError(f"invalid CORS origin: {origin}") from exc
            if (
                parsed.scheme not in {"http", "https"}
                or parsed.hostname is None
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"invalid CORS origin: {origin}")
            if port is not None and not 1 <= port <= 65535:
                raise ValueError(f"invalid CORS origin: {origin}")
            normalized.append(origin)
        if "*" in normalized and len(normalized) != 1:
            raise ValueError("wildcard CORS origin cannot be combined with other origins")
        return list(dict.fromkeys(normalized))

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("unsupported LOG_LEVEL")
        return normalized

    @property
    def output_root(self) -> Path:
        return self.project_root / "output"

    @property
    def upload_root(self) -> Path:
        return self.project_root / "updated"

    @property
    def log_dir(self) -> Path:
        return self.project_root / "logs"

    def require_real_llm(self) -> tuple[str, str, str]:
        """Return Real Mode LLM values without ever formatting the secret."""
        if self.demo_mode:
            raise RuntimeError("Real LLM configuration is unavailable in Demo Mode")
        if self.openai_api_key is None or not self.openai_api_key.get_secret_value().strip():
            raise RuntimeError("OPENAI_API_KEY is required when DEMO_MODE=false")
        if not self.llm_model.strip():
            raise RuntimeError("LLM_MODEL is required when DEMO_MODE=false")
        return self.llm_model, self.openai_base_url, self.openai_api_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
