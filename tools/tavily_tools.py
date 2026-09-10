"""Bounded Tavily search with an explicit credential-free demo adapter."""

from __future__ import annotations

import asyncio
from typing import Any, Literal, Protocol

from langchain_core.tools import BaseTool, StructuredTool
from tavily import AsyncTavilyClient

from api.context import consume_search_call
from utils.config import Settings

SearchTopic = Literal["general", "news", "finance"]


class SearchClient(Protocol):
    async def search(self, query: str, **kwargs: Any) -> dict[str, Any]: ...


def _error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {"code": code, "message": message, "retryable": retryable},
        "results": [],
    }


def _demo_search(query: str, topic: SearchTopic, max_results: int) -> dict[str, Any]:
    corpus = [
        {
            "title": "Agent architecture and tool-use patterns (demo source)",
            "url": "https://demo.local/research/agent-architecture",
            "content": (
                "A local demonstration record covering planning, specialist delegation, "
                "tool boundaries, reflection, and synthesis for AI agent systems."
            ),
            "raw_content": (
                "Demo corpus: production agent systems benefit from explicit tool ownership, "
                "bounded retries, observable execution metadata, and human-auditable sources."
            ),
            "tags": {"agent", "architecture", "ai", "planning"},
        },
        {
            "title": "Evaluation and reliability practices (demo source)",
            "url": "https://demo.local/research/evaluation",
            "content": (
                "A local demonstration record about task-level evaluation, failure injection, "
                "security tests, and measuring grounded answers."
            ),
            "raw_content": (
                "Demo corpus: evaluation should include end-to-end traces, source quality, "
                "tool errors, concurrency isolation, and deterministic regression cases."
            ),
            "tags": {"evaluation", "reliability", "testing", "security"},
        },
        {
            "title": "Adoption, governance, and operational trade-offs (demo source)",
            "url": "https://demo.local/research/adoption-governance",
            "content": (
                "A local demonstration record covering organizational adoption, data controls, "
                "cost, latency, and governance for agentic applications."
            ),
            "raw_content": (
                "Demo corpus: deployments need least-privilege tools, secret isolation, clear "
                "fallback behavior, and monitoring that does not reveal private reasoning."
            ),
            "tags": {"adoption", "governance", "cost", "risk"},
        },
        {
            "title": "Markets and business metrics (demo finance source)",
            "url": "https://demo.local/research/finance",
            "content": (
                "A local demonstration record showing that financial research should separate "
                "reported facts, time periods, forecasts, and uncertainty."
            ),
            "raw_content": (
                "Demo corpus: finance-oriented queries require dated evidence and should never "
                "present local sample values as live market data."
            ),
            "tags": {"finance", "market", "business", "revenue"},
        },
    ]
    tokens = {token.lower() for token in query.replace("-", " ").split() if len(token) > 1}
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in corpus:
        score = len(tokens.intersection(item["tags"]))
        if topic == "finance" and "finance" in item["tags"]:
            score += 3
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    results = []
    for index, (_, item) in enumerate(scored[:max_results], start=1):
        results.append(
            {
                "title": item["title"],
                "url": item["url"],
                "content": f"Research angle for '{query}': {item['content']}",
                "raw_content": item["raw_content"],
                "score": round(1 - (index - 1) * 0.08, 2),
            }
        )
    return {
        "ok": True,
        "mode": "demo",
        "topic": topic,
        "query": query,
        "answer": "Local demo evidence only; enable Real Mode for current public web results.",
        "results": results,
    }


async def internet_search(
    query: str,
    topic: SearchTopic = "general",
    max_results: int = 5,
    *,
    settings: Settings,
    client: SearchClient | None = None,
) -> dict[str, Any]:
    """Search public information while preserving source fields and structured failures."""
    normalized_query = query.strip()
    if not normalized_query:
        return _error("invalid_query", "search query cannot be empty")
    if topic not in {"general", "news", "finance"}:
        return _error("invalid_topic", "topic must be general, news, or finance")
    bounded_results = min(max(max_results, 1), 10)
    try:
        call_number = consume_search_call(settings.max_search_calls)
    except RuntimeError as exc:
        return _error("search_limit", str(exc))

    if settings.demo_mode:
        response = _demo_search(normalized_query, topic, bounded_results)
        response["call_number"] = call_number
        return response
    if settings.tavily_api_key is None:
        return _error("not_configured", "TAVILY_API_KEY is not configured")

    search_client = client or AsyncTavilyClient(
        api_key=settings.tavily_api_key.get_secret_value()
    )
    try:
        payload = await asyncio.wait_for(
            search_client.search(
                normalized_query,
                topic=topic,
                max_results=bounded_results,
                search_depth="advanced",
                include_answer="basic",
                include_raw_content="markdown",
                timeout=settings.external_timeout_seconds,
            ),
            timeout=settings.external_timeout_seconds + 0.1,
        )
    except TimeoutError:
        return _error("timeout", "Tavily search timed out", retryable=True)
    except Exception as exc:  # provider SDK exceptions are intentionally normalized
        return _error(
            "provider_error",
            f"Tavily search failed: {type(exc).__name__}",
            retryable=True,
        )

    results = []
    for item in payload.get("results", [])[:bounded_results]:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                key: item.get(key)
                for key in ("title", "url", "content", "raw_content", "score", "published_date")
                if item.get(key) is not None
            }
        )
    return {
        "ok": True,
        "mode": "real",
        "topic": topic,
        "query": normalized_query,
        "answer": payload.get("answer"),
        "results": results,
        "call_number": call_number,
    }


def make_internet_search_tool(settings: Settings) -> BaseTool:
    async def search(
        query: str,
        topic: SearchTopic = "general",
        max_results: int = 5,
    ) -> dict[str, Any]:
        """Search the public web for one research angle and return sources."""
        return await internet_search(query, topic, max_results, settings=settings)

    return StructuredTool.from_function(
        coroutine=search,
        name="internet_search",
        description=(
            "Search public internet sources for one focused research angle. Supports general, "
            "news, and finance topics and returns title, URL, content, and raw content."
        ),
    )
