"""Database Query Agent specification."""

from __future__ import annotations

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from agent.prompts import load_prompts
from tools.mysql_tools import make_mysql_tools
from utils.config import Settings


def create_database_query_agent(settings: Settings, model: BaseChatModel) -> SubAgent:
    prompt = load_prompts()["sub_agents"]["db"]
    return {
        "name": prompt["name"],
        "description": prompt["description"],
        "system_prompt": prompt["system_prompt"],
        "tools": make_mysql_tools(settings),
        "model": model,
    }

