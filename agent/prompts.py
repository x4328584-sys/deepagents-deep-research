"""Validated YAML prompt loading."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict, cast

import yaml


class PromptEntry(TypedDict):
    name: str
    description: str
    system_prompt: str


class MainPromptEntry(TypedDict):
    description: str
    system_prompt: str


class PromptConfig(TypedDict):
    main_agent: MainPromptEntry
    sub_agents: dict[str, PromptEntry]


def _default_prompt_path() -> Path:
    return Path(__file__).resolve().parents[1] / "prompt" / "prompts.yml"


def _validate_entry(entry: Any, *, require_name: bool) -> None:
    if not isinstance(entry, dict):
        raise ValueError("prompt entry must be a mapping")
    required = {"description", "system_prompt"}
    if require_name:
        required.add("name")
    missing = required.difference(entry)
    if missing:
        raise ValueError(f"prompt entry is missing keys: {sorted(missing)}")
    if any(not isinstance(entry[key], str) or not entry[key].strip() for key in required):
        raise ValueError("prompt values must be non-empty strings")


@lru_cache(maxsize=4)
def load_prompts(path: Path | None = None) -> PromptConfig:
    prompt_path = (path or _default_prompt_path()).resolve()
    with prompt_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError("prompt configuration must be a mapping")
    main = raw.get("main_agent")
    sub_agents = raw.get("sub_agents")
    _validate_entry(main, require_name=False)
    if not isinstance(sub_agents, dict):
        raise ValueError("sub_agents prompt configuration must be a mapping")
    if set(sub_agents) != {"tavily", "db", "ragflow"}:
        raise ValueError("sub_agents must contain exactly tavily, db, and ragflow")
    for entry in sub_agents.values():
        _validate_entry(entry, require_name=True)
    return cast(PromptConfig, raw)

