"""Network Search Agent specification."""

from __future__ import annotations

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from agent.prompts import load_prompts
from tools.tavily_tools import make_internet_search_tool
from utils.config import Settings


def create_network_search_agent(settings: Settings, model: BaseChatModel) -> SubAgent:
    prompt = load_prompts()["sub_agents"]["tavily"]
    return {
        "name": prompt["name"],
        "description": prompt["description"],
        "system_prompt": prompt["system_prompt"],
        "tools": [make_internet_search_tool(settings)],
        "model": model,
    }

