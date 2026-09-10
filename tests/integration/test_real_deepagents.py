from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, ClassVar

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool

from agent.main_agent import DEEPAGENTS_BUILTIN_TOOLS, create_main_agent
from agent.runtime import DeepAgentsResearchRunner
from api.context import bind_task_context
from api.monitor import Monitor
from utils.config import Settings


class RecordingManager:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def broadcast(self, thread_id: str, payload: dict[str, Any]) -> None:
        assert thread_id == "real-graph"
        self.events.append(payload)


class RoutingToolModel(BaseChatModel):
    """Drive one real DeepAgents delegation without any external provider."""

    tool_names: tuple[str, ...] = ()
    observed_tool_sets: ClassVar[list[frozenset[str]]] = []

    @property
    def _llm_type(self) -> str:
        return "routing-tool-test-model"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        **kwargs: Any,
    ) -> RoutingToolModel:
        names = tuple(
            tool.name if isinstance(tool, BaseTool) else str(tool.get("name", ""))
            for tool in tools
            if isinstance(tool, (BaseTool, dict))
        )
        self.observed_tool_sets.append(frozenset(names))
        return self.model_copy(update={"tool_names": names})

    def _get_ls_params(
        self,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        del stop, kwargs
        return {"ls_provider": "openai", "ls_model_name": "routing-tool-test-model"}

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
        if "task" in self.tool_names:
            if tool_messages:
                message = AIMessage(content="# Verified synthesis\n\nNetwork evidence received.")
            else:
                message = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "delegate-network",
                            "name": "task",
                            "args": {
                                "description": "Research public agent-system evidence",
                                "subagent_type": "network_search_agent",
                            },
                        }
                    ],
                )
        elif "internet_search" in self.tool_names:
            if tool_messages:
                message = AIMessage(content="Network evidence collected from demo sources.")
            else:
                message = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "search-public",
                            "name": "internet_search",
                            "args": {
                                "query": "agent system reliability",
                                "topic": "general",
                                "max_results": 2,
                            },
                        }
                    ],
                )
        else:
            raise AssertionError(f"unexpected model-visible tools: {self.tool_names}")
        return ChatResult(generations=[ChatGeneration(message=message)])


@pytest.mark.integration
async def test_real_deepagents_graph_delegates_and_emits_true_tool_events(
    tmp_path: Path,
) -> None:
    settings = Settings(project_root=tmp_path, demo_mode=True)
    model = RoutingToolModel()
    RoutingToolModel.observed_tool_sets = []
    graph = create_main_agent(settings, model=model)
    runner = DeepAgentsResearchRunner(settings)
    runner._graph = graph
    manager = RecordingManager()
    session_dir = tmp_path / "output" / "session_real-graph"
    session_dir.mkdir(parents=True)

    with bind_task_context("real-graph", session_dir):
        result = await runner.run("Research agent reliability", Monitor(manager, "real-graph"))

    assert result.startswith("# Verified synthesis")
    event_pairs = [
        (event["event"], event["data"].get("assistant_name") or event["data"].get("tool_name"))
        for event in manager.events
    ]
    assert ("assistant_call", "network_search_agent") in event_pairs
    assert ("tool_start", "internet_search") in event_pairs
    assert RoutingToolModel.observed_tool_sets
    assert all(
        not DEEPAGENTS_BUILTIN_TOOLS.intersection(tool_set)
        for tool_set in RoutingToolModel.observed_tool_sets
    )
    assert {
        frozenset({"task", "read_file_content", "generate_markdown", "convert_md_to_pdf"}),
        frozenset({"internet_search"}),
    } <= set(RoutingToolModel.observed_tool_sets)
