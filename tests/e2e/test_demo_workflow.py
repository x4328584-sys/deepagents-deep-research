from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from utils.config import Settings


@pytest.mark.e2e
def test_demo_multi_source_pdf_workflow(tmp_path: Path) -> None:
    app = create_app(Settings(project_root=tmp_path, demo_mode=True))
    thread_id = "complete-demo-flow"
    query = "查询最近 Agent 发展、数据库产品营收和知识库内部制度，并生成 PDF 报告"

    with TestClient(app) as client, client.websocket_connect(f"/ws/{thread_id}") as socket:
        response = client.post(
            "/api/task",
            json={"query": query, "thread_id": thread_id},
        )
        assert response.json() == {"status": "started", "thread_id": thread_id}

        events: list[dict[str, Any]] = []
        for _ in range(30):
            event = socket.receive_json()
            if event.get("type") != "monitor_event":
                continue
            events.append(event)
            if event["event"] == "task_result":
                break
        else:
            raise AssertionError("Demo workflow did not produce task_result")

        assistants = {
            event["data"]["assistant_name"]
            for event in events
            if event["event"] == "assistant_call"
        }
        assert assistants == {
            "network_search_agent",
            "database_query_agent",
            "knowledge_base_agent",
        }

        tools = {
            event["data"]["tool_name"]
            for event in events
            if event["event"] == "tool_start"
        }
        assert {
            "internet_search",
            "list_sql_tables",
            "get_table_data",
            "execute_sql_query",
            "get_assistant_list",
            "create_ask_delete",
            "generate_markdown",
            "convert_md_to_pdf",
        } <= tools

        session_path = events[0]["data"]["path"]
        files = client.get("/api/files", params={"path": session_path}).json()
        assert {item["name"] for item in files} == {
            "deep-research-report.md",
            "deep-research-report.pdf",
        }
        pdf = next(item for item in files if item["name"].endswith(".pdf"))
        download = client.get("/api/download", params={"path": pdf["path"]})
        assert download.status_code == 200
        assert download.content.startswith(b"%PDF-")
