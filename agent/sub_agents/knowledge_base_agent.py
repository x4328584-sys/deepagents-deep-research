"""RAGFlow Knowledge Base Agent specification."""

from __future__ import annotations

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from agent.prompts import load_prompts
from tools.ragflow_tools import make_ragflow_tools
from utils.config import Settings


def create_knowledge_base_agent(settings: Settings, model: BaseChatModel) -> SubAgent:
    prompt = load_prompts()["sub_agents"]["ragflow"]
    return {
        "name": prompt["name"],
        "description": prompt["description"],
        "system_prompt": prompt["system_prompt"],
        "tools": make_ragflow_tools(settings),
        "model": model,
    }

