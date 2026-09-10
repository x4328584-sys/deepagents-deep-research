import inspect
from pathlib import Path

import pytest
import yaml
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from agent.main_agent import create_main_agent, create_specialist_agents
from agent.prompts import load_prompts
from agent.runtime import enforce_report_tool_order, stream_update_scope
from utils.config import Settings


def _test_model() -> ChatOpenAI:
    return ChatOpenAI(
        model="test-tool-model",
        api_key=SecretStr("test-model-key"),
        base_url="https://model.example.test",
        use_responses_api=False,
    )


def test_yaml_prompts_use_safe_loader_and_have_exact_agents() -> None:
    prompts = load_prompts()
    assert set(prompts["sub_agents"]) == {"tavily", "db", "ragflow"}
    assert {
        prompt["name"] for prompt in prompts["sub_agents"].values()
    } == {
        "network_search_agent",
        "database_query_agent",
        "knowledge_base_agent",
    }
    assert yaml.safe_load is not None


def test_specialists_have_disjoint_required_tool_sets(tmp_path: Path) -> None:
    settings = Settings(project_root=tmp_path, demo_mode=True)
    agents = create_specialist_agents(settings, _test_model())
    by_name = {agent["name"]: agent for agent in agents}
    assert set(by_name) == {
        "network_search_agent",
        "database_query_agent",
        "knowledge_base_agent",
    }
    assert {tool.name for tool in by_name["network_search_agent"]["tools"]} == {
        "internet_search"
    }
    assert {tool.name for tool in by_name["database_query_agent"]["tools"]} == {
        "list_sql_tables",
        "get_table_data",
        "execute_sql_query",
    }
    assert {tool.name for tool in by_name["knowledge_base_agent"]["tools"]} == {
        "get_assistant_list",
        "create_ask_delete",
    }


def test_main_agent_is_a_compiled_deepagents_graph(tmp_path: Path) -> None:
    settings = Settings(project_root=tmp_path, demo_mode=True)
    graph = create_main_agent(settings, model=_test_model())
    assert graph.name == "deep_research_main_agent"
    assert callable(graph.ainvoke)
    assert callable(graph.astream)
    tool_node = graph.builder.nodes["tools"].runnable
    task_tool = tool_node.tools_by_name["task"]
    assert task_tool.coroutine is not None
    compiled_subagents = inspect.getclosurevars(task_tool.coroutine).nonlocals[
        "subagent_graphs"
    ]
    assert set(compiled_subagents) == {
        "network_search_agent",
        "database_query_agent",
        "knowledge_base_agent",
    }
    assert "general-purpose" not in task_tool.description


def test_real_model_requires_key_without_revealing_value(tmp_path: Path) -> None:
    settings = Settings(project_root=tmp_path, demo_mode=False, openai_api_key=None)
    try:
        create_main_agent(settings)
    except RuntimeError as exc:
        assert str(exc) == "OPENAI_API_KEY is required when DEMO_MODE=false"
    else:
        raise AssertionError("missing key must prevent Real Mode graph construction")


def test_report_order_guard_accepts_evidence_then_markdown_then_pdf() -> None:
    evidence, markdown = enforce_report_tool_order(
        [{"name": "task"}], evidence_seen=False, markdown_seen=False
    )
    evidence, markdown = enforce_report_tool_order(
        [{"name": "generate_markdown"}],
        evidence_seen=evidence,
        markdown_seen=markdown,
    )
    evidence, markdown = enforce_report_tool_order(
        [{"name": "convert_md_to_pdf"}],
        evidence_seen=evidence,
        markdown_seen=markdown,
    )
    assert evidence is True
    assert markdown is True


@pytest.mark.parametrize(
    ("calls", "evidence_seen", "markdown_seen"),
    [
        ([{"name": "task"}, {"name": "generate_markdown"}], False, False),
        ([{"name": "read_file_content"}, {"name": "convert_md_to_pdf"}], False, False),
        ([{"name": "generate_markdown"}, {"name": "convert_md_to_pdf"}], True, False),
        ([{"name": "generate_markdown"}], False, False),
        ([{"name": "convert_md_to_pdf"}], True, False),
    ],
)
def test_report_order_guard_rejects_unsafe_sequences(
    calls: list[dict[str, str]], evidence_seen: bool, markdown_seen: bool
) -> None:
    with pytest.raises(RuntimeError):
        enforce_report_tool_order(
            calls,
            evidence_seen=evidence_seen,
            markdown_seen=markdown_seen,
        )


def test_stream_update_scope_distinguishes_main_and_subagent_namespaces() -> None:
    root_payload = {"model": {"messages": []}}
    subagent_payload = {"model": {"messages": ["worker result"]}}
    assert stream_update_scope(((), root_payload)) == (True, root_payload)
    assert stream_update_scope((("task:worker-id",), subagent_payload)) == (
        False,
        subagent_payload,
    )
    assert stream_update_scope(root_payload) == (True, root_payload)
