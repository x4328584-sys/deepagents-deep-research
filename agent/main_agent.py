"""Construction of the genuine DeepAgents research orchestrator."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from deepagents import (
    FilesystemPermission,
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    SubAgent,
    create_deep_agent,
    register_harness_profile,
)
from langchain_core.language_models import BaseChatModel

from agent.llm import create_chat_model
from agent.prompts import load_prompts
from agent.sub_agents.database_query_agent import create_database_query_agent
from agent.sub_agents.knowledge_base_agent import create_knowledge_base_agent
from agent.sub_agents.network_search_agent import create_network_search_agent
from tools.markdown_tools import make_markdown_tool
from tools.pdf_tools import make_pdf_tool
from tools.upload_file_read_tool import make_file_reader_tool
from utils.config import Settings

DEEPAGENTS_BUILTIN_TOOLS = frozenset(
    {"ls", "read_file", "write_file", "edit_file", "delete", "glob", "grep", "execute"}
)
SPECIALIST_TASK_TOOL_DESCRIPTION = """Delegate a bounded research task to exactly one specialist.

Available specialist types and their tools:
{available_agents}

Set subagent_type to one of the names above. Each call is stateless, so include all
required context and the expected output. Independent specialist calls may run in
parallel; synthesize their returned evidence for the user."""


@lru_cache(maxsize=1)
def configure_deepagents_harness() -> None:
    """Remove default tools that violate this application's least-privilege boundary."""
    register_harness_profile(
        "openai",
        HarnessProfile(
            excluded_tools=DEEPAGENTS_BUILTIN_TOOLS,
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
            tool_description_overrides={"task": SPECIALIST_TASK_TOOL_DESCRIPTION},
        ),
    )


def create_specialist_agents(
    settings: Settings, model: BaseChatModel
) -> list[SubAgent]:
    return [
        create_network_search_agent(settings, model),
        create_database_query_agent(settings, model),
        create_knowledge_base_agent(settings, model),
    ]


def create_main_agent(
    settings: Settings,
    *,
    model: BaseChatModel | None = None,
) -> Any:
    """Return a compiled DeepAgents graph with strict provider-tool separation."""
    configure_deepagents_harness()
    chat_model = model or create_chat_model(settings)
    prompts = load_prompts()
    main_tools = [
        make_file_reader_tool(settings),
        make_markdown_tool(),
        make_pdf_tool(),
    ]
    permissions = [
        FilesystemPermission(operations=["read", "write"], paths=["/**"], mode="deny")
    ]
    return create_deep_agent(
        model=chat_model,
        tools=main_tools,
        system_prompt=prompts["main_agent"]["system_prompt"],
        subagents=create_specialist_agents(settings, chat_model),
        permissions=permissions,
        name="deep_research_main_agent",
    )
