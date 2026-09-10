"""Real DeepAgents streaming and credential-free demo research runtimes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any, Protocol

from langchain_core.messages import AIMessage, BaseMessage

from agent.main_agent import create_main_agent
from api.context import get_session_dir
from api.monitor import Monitor
from tools.markdown_tools import generate_markdown
from tools.mysql_tools import DatabaseService
from tools.pdf_tools import convert_md_to_pdf
from tools.ragflow_tools import RagflowService
from tools.tavily_tools import SearchTopic, internet_search
from tools.upload_file_read_tool import read_file_content
from utils.config import Settings
from utils.security import ALLOWED_UPLOAD_EXTENSIONS


class ResearchRunner(Protocol):
    async def run(self, query: str, monitor: Monitor) -> str: ...


def _wants_any(text: str, terms: set[str]) -> bool:
    lowered = text.casefold()
    return any(term in lowered for term in terms)


def _json_summary(value: Any, limit: int = 2_000) -> str:
    rendered = json.dumps(value, ensure_ascii=False, default=str, indent=2)
    return rendered if len(rendered) <= limit else f"{rendered[:limit]}\n…"


EVIDENCE_TOOL_NAMES = {"task", "read_file_content"}
REPORT_TOOL_NAMES = {"generate_markdown", "convert_md_to_pdf"}


def enforce_report_tool_order(
    tool_calls: Sequence[Mapping[str, Any]],
    *,
    evidence_seen: bool,
    markdown_seen: bool,
) -> tuple[bool, bool]:
    """Reject report calls that race evidence collection or PDF prerequisites."""
    names = {str(call.get("name", "")) for call in tool_calls}
    if names.intersection(EVIDENCE_TOOL_NAMES) and names.intersection(REPORT_TOOL_NAMES):
        raise RuntimeError("evidence collection and report generation must be sequential")
    if {"generate_markdown", "convert_md_to_pdf"}.issubset(names):
        raise RuntimeError("Markdown generation must complete before PDF conversion")
    if names.intersection(REPORT_TOOL_NAMES) and not evidence_seen:
        raise RuntimeError("report generation requires completed evidence collection")
    if "convert_md_to_pdf" in names and not markdown_seen:
        raise RuntimeError("PDF conversion requires a completed Markdown generation call")
    return (
        evidence_seen or bool(names.intersection(EVIDENCE_TOOL_NAMES)),
        markdown_seen or "generate_markdown" in names,
    )


class DemoResearchRunner:
    """Offline coordinator that exercises production boundaries without pretending to be an LLM."""

    DATABASE_TERMS = {
        "database",
        "mysql",
        "sql",
        "sales",
        "revenue",
        "product data",
        "数据库",
        "销售",
        "营收",
        "产品数据",
    }
    KNOWLEDGE_TERMS = {
        "ragflow",
        "knowledge base",
        "internal policy",
        "procedure",
        "知识库",
        "内部政策",
        "制度",
        "流程",
    }
    PUBLIC_TERMS = {
        "latest",
        "recent",
        "news",
        "market",
        "public",
        "development",
        "agent",
        "最近",
        "最新",
        "新闻",
        "市场",
        "发展",
        "公开",
    }
    FILE_TERMS = {"file", "document", "upload", "summarize", "文件", "文档", "上传", "总结"}

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = DatabaseService(settings)
        self.knowledge = RagflowService(settings)

    async def _read_uploads(self, query: str, monitor: Monitor) -> list[str]:
        session_dir = get_session_dir()
        files = sorted(
            path
            for path in session_dir.iterdir()
            if path.is_file() and path.suffix.lower() in ALLOWED_UPLOAD_EXTENSIONS
        )
        if not files:
            return []
        if not _wants_any(query, self.FILE_TERMS) and _wants_any(
            query, self.DATABASE_TERMS | self.KNOWLEDGE_TERMS | self.PUBLIC_TERMS
        ):
            return []

        sections = ["## Uploaded file evidence"]
        for path in files:
            await monitor.tool_start("read_file_content", {"file_path": path.name})
            result = await read_file_content(path.name, settings=self.settings)
            if not result.get("ok"):
                sections.append(f"- **{path.name}**: {_json_summary(result.get('error'))}")
                continue
            content = str(result.get("content", ""))
            line_count = len(content.splitlines())
            preview = content[:1_500].strip()
            sections.append(
                f"### {path.name}\n\n"
                f"Extracted {len(content)} characters across {line_count} lines.\n\n"
                f"> {preview.replace(chr(10), chr(10) + '> ')}"
            )
        return sections

    @staticmethod
    def _research_angles(query: str) -> list[str]:
        return [
            f"{query} — primary sources and documented developments",
            f"{query} — adoption, implementation evidence, and measurable impact",
            f"{query} — limitations, safety, governance, and counterevidence",
        ]

    async def _network_research(self, query: str, monitor: Monitor) -> list[str]:
        await monitor.assistant_call(
            "network_search_agent", {"assignment": query, "angles": 3}
        )
        topic: SearchTopic = (
            "news"
            if _wants_any(query, {"recent", "latest", "news", "最近", "最新"})
            else "general"
        )
        findings = []
        for angle in self._research_angles(query):
            await monitor.tool_start("internet_search", {"query": angle, "topic": topic})
            findings.append(
                await internet_search(angle, topic=topic, max_results=3, settings=self.settings)
            )

        lines = [
            "## Public research",
            "",
            "> Demo Mode uses a labelled local evidence corpus; it is not live web data.",
        ]
        source_urls: set[str] = set()
        for index, (angle, finding) in enumerate(
            zip(self._research_angles(query), findings, strict=True), start=1
        ):
            lines.extend(["", f"### Angle {index}", "", f"**Focus:** {angle}"])
            if not finding.get("ok"):
                lines.append(f"- Search unavailable: {_json_summary(finding.get('error'))}")
                continue
            for source in finding.get("results", []):
                if not isinstance(source, dict):
                    continue
                title = str(source.get("title", "Untitled source"))
                url = str(source.get("url", ""))
                content = str(source.get("content", ""))
                lines.append(f"- [{title}]({url}): {content}")
                if url:
                    source_urls.add(url)
        if source_urls:
            lines.extend(["", "### Sources", *[f"- {url}" for url in sorted(source_urls)]])
        return lines

    async def _database_research(self, query: str, monitor: Monitor) -> list[str]:
        await monitor.assistant_call("database_query_agent", {"assignment": query})
        await monitor.tool_start("list_sql_tables", {})
        tables = await self.database.list_tables()
        table = "sales" if _wants_any(query, {"sales", "revenue", "销售", "营收"}) else "products"
        await monitor.tool_start("get_table_data", {"table_name": table, "limit": 5})
        preview = await self.database.get_table(table, 5)
        if table == "sales":
            sql = (
                "SELECT p.name AS product, SUM(s.revenue) AS revenue "
                "FROM sales s JOIN products p ON p.id = s.product_id "
                "GROUP BY p.name ORDER BY revenue DESC"
            )
        else:
            sql = "SELECT name, category, annual_revenue FROM products ORDER BY annual_revenue DESC"
        await monitor.tool_start("execute_sql_query", {"query": sql})
        result = await self.database.execute(sql)
        return [
            "## Structured company data",
            "",
            f"**Available tables:** {_json_summary(tables.get('tables', []), 500)}",
            "",
            f"**Schema and preview for `{table}`:**",
            "",
            f"```json\n{_json_summary(preview)}\n```",
            "",
            f"**Read-only query:** `{sql}`",
            "",
            f"```json\n{_json_summary(result)}\n```",
        ]

    async def _knowledge_research(self, query: str, monitor: Monitor) -> list[str]:
        await monitor.assistant_call("knowledge_base_agent", {"assignment": query})
        await monitor.tool_start("get_assistant_list", {})
        assistants = await self.knowledge.list_assistants()
        if not assistants.get("ok") or not assistants.get("assistants"):
            return ["## Private knowledge", "", _json_summary(assistants)]
        first = assistants["assistants"][0]
        questions = [
            f"What broad internal context applies to: {query}?",
            f"Which specific controls or documented details apply to: {query}?",
            f"What exceptions, limitations, or escalation paths apply to: {query}?",
        ]
        await monitor.tool_start(
            "create_ask_delete", {"assistant_id": first["id"], "questions": questions}
        )
        answers = await self.knowledge.ask_and_cleanup(first["id"], questions)
        return [
            "## Private knowledge",
            "",
            f"**Selected assistant:** {first['name']} — {first['description']}",
            "",
            f"```json\n{_json_summary(answers, 5_000)}\n```",
        ]

    async def run(self, query: str, monitor: Monitor) -> str:
        sections = [
            "# Deep Research Result",
            "",
            f"**Task:** {query}",
            "",
            "**Runtime:** Demo Mode (credential-free local adapters)",
        ]
        sections.extend(await self._read_uploads(query, monitor))

        wants_database = _wants_any(query, self.DATABASE_TERMS)
        wants_knowledge = _wants_any(query, self.KNOWLEDGE_TERMS)
        wants_public = _wants_any(query, self.PUBLIC_TERMS)
        has_file_evidence = "## Uploaded file evidence" in sections
        if not any((wants_database, wants_knowledge, wants_public, has_file_evidence)):
            wants_public = True

        if wants_public:
            sections.extend(await self._network_research(query, monitor))
        if wants_database:
            sections.extend(await self._database_research(query, monitor))
        if wants_knowledge:
            sections.extend(await self._knowledge_research(query, monitor))

        sections.extend(
            [
                "",
                "## Synthesis",
                "",
                "The sections above preserve each selected source boundary. Demo evidence is "
                "labelled and must be replaced by Real Mode provider results for live decisions.",
            ]
        )
        result = "\n".join(sections).strip()

        wants_pdf = _wants_any(query, {"pdf", ".pdf"})
        wants_markdown = wants_pdf or _wants_any(
            query, {"markdown", ".md", "报告", "report"}
        )
        generated: list[str] = []
        if wants_markdown:
            await monitor.tool_start(
                "generate_markdown", {"filename": "deep-research-report.md"}
            )
            markdown = await generate_markdown("deep-research-report.md", result)
            if markdown.get("ok"):
                generated.append(str(markdown["path"]))
                if wants_pdf:
                    await monitor.tool_start(
                        "convert_md_to_pdf",
                        {
                            "markdown_path": markdown["path"],
                            "pdf_filename": "deep-research-report.pdf",
                        },
                    )
                    pdf = await convert_md_to_pdf(
                        str(markdown["path"]), "deep-research-report.pdf"
                    )
                    if pdf.get("ok"):
                        generated.append(str(pdf["path"]))
                    else:
                        result += f"\n\nPDF generation error: {_json_summary(pdf['error'])}"
            else:
                result += f"\n\nMarkdown generation error: {_json_summary(markdown['error'])}"
        if generated:
            result += f"\n\n**Generated files:** {', '.join(generated)}"
        return result


def _walk_messages(value: Any) -> AsyncIterator[BaseMessage]:
    async def walk(item: Any) -> AsyncIterator[BaseMessage]:
        if isinstance(item, BaseMessage):
            yield item
        elif isinstance(item, dict):
            for child in item.values():
                async for message in walk(child):
                    yield message
        elif isinstance(item, (list, tuple)):
            for child in item:
                async for message in walk(child):
                    yield message

    return walk(value)


def _message_text(message: AIMessage) -> str:
    if isinstance(message.content, str):
        return message.content.strip()
    parts = []
    for block in message.content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") in {"text", "output_text"}:
            parts.append(str(block.get("text", "")))
    return "\n".join(part for part in parts if part).strip()


def stream_update_scope(update: Any) -> tuple[bool, Any]:
    """Return whether a LangGraph subgraph stream update belongs to the root graph."""
    if (
        isinstance(update, tuple)
        and len(update) == 2
        and isinstance(update[0], tuple)
    ):
        namespace, payload = update
        return not namespace, payload
    return True, update


class DeepAgentsResearchRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._graph: Any = None
        self._graph_lock = asyncio.Lock()

    async def _get_graph(self) -> Any:
        if self._graph is None:
            async with self._graph_lock:
                if self._graph is None:
                    self._graph = await asyncio.to_thread(create_main_agent, self.settings)
        return self._graph

    async def run(self, query: str, monitor: Monitor) -> str:
        graph = await self._get_graph()
        uploaded = sorted(
            path.name
            for path in get_session_dir().iterdir()
            if path.is_file() and path.suffix.lower() in ALLOWED_UPLOAD_EXTENSIONS
        )
        task = query
        if uploaded:
            task += "\n\nUploaded files available in this session: " + ", ".join(uploaded)

        final_text = ""
        evidence_seen = False
        markdown_seen = False
        stream = graph.astream(
            {"messages": [{"role": "user", "content": task}]},
            config={"recursion_limit": self.settings.max_agent_steps},
            stream_mode="updates",
            subgraphs=True,
        )
        async for update in stream:
            is_root_update, payload = stream_update_scope(update)
            async for message in _walk_messages(payload):
                if not isinstance(message, AIMessage):
                    continue
                if message.tool_calls:
                    if is_root_update:
                        evidence_seen, markdown_seen = enforce_report_tool_order(
                            message.tool_calls,
                            evidence_seen=evidence_seen,
                            markdown_seen=markdown_seen,
                        )
                    await monitor.observe_tool_calls(message.tool_calls)
                elif is_root_update:
                    text = _message_text(message)
                    if text:
                        final_text = text
        if not final_text:
            raise RuntimeError("DeepAgents completed without a final assistant response")
        return final_text


class ModeAwareResearchRunner:
    """Keep API startup provider-independent and select the runtime per settings."""

    def __init__(self, settings: Settings) -> None:
        self.runner: ResearchRunner = (
            DemoResearchRunner(settings)
            if settings.demo_mode
            else DeepAgentsResearchRunner(settings)
        )

    async def run(self, query: str, monitor: Monitor) -> str:
        return await self.runner.run(query, monitor)
