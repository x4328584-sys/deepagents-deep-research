"""RAGFlow chat-assistant tools with timeout-safe SDK calls and demo behavior."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import requests
from langchain_core.tools import BaseTool, StructuredTool
from ragflow_sdk import RAGFlow

from utils.config import Settings

ASSISTANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class TimeoutRAGFlow(RAGFlow):  # type: ignore[misc]
    """RAGFlow SDK client whose transport always has an explicit timeout."""

    def __init__(self, api_key: str, base_url: str, timeout: float) -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        self.timeout = timeout

    def post(
        self,
        path: str,
        json: Any = None,
        stream: bool = False,
        files: Any = None,
    ) -> requests.Response:
        return requests.post(
            url=self.api_url + path,
            json=json,
            headers=self.authorization_header,
            stream=stream,
            files=files,
            timeout=self.timeout,
        )

    def get(self, path: str, params: Any = None, json: Any = None) -> requests.Response:
        return requests.get(
            url=self.api_url + path,
            params=params,
            headers=self.authorization_header,
            json=json,
            timeout=self.timeout,
        )

    def delete(self, path: str, json: Any) -> requests.Response:
        return requests.delete(
            url=self.api_url + path,
            json=json,
            headers=self.authorization_header,
            timeout=self.timeout,
        )

    def put(self, path: str, json: Any) -> requests.Response:
        return requests.put(
            url=self.api_url + path,
            json=json,
            headers=self.authorization_header,
            timeout=self.timeout,
        )

    def patch(self, path: str, json: Any) -> requests.Response:
        return requests.patch(
            url=self.api_url + path,
            json=json,
            headers=self.authorization_header,
            timeout=self.timeout,
        )


def _ragflow_error(code: str, message: str, *, retryable: bool = False) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {"code": code, "message": message, "retryable": retryable},
    }


class RagflowService:
    def __init__(
        self,
        settings: Settings,
        sdk_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.settings = settings
        self.sdk_factory = sdk_factory

    def _sdk(self) -> Any:
        if self.sdk_factory is not None:
            return self.sdk_factory()
        if self.settings.ragflow_api_url is None or self.settings.ragflow_api_key is None:
            raise RuntimeError("RAGFlow is not configured")
        return TimeoutRAGFlow(
            api_key=self.settings.ragflow_api_key.get_secret_value(),
            base_url=self.settings.ragflow_api_url,
            timeout=self.settings.external_timeout_seconds,
        )

    @staticmethod
    def _demo_assistants() -> list[dict[str, str]]:
        return [
            {
                "id": "demo-policy",
                "name": "Policy Library",
                "description": "Internal policy, security, and operating procedure examples.",
            },
            {
                "id": "demo-product",
                "name": "Product Knowledge",
                "description": "Product capabilities, support guidance, and release-note examples.",
            },
        ]

    def _list_sync(self) -> list[dict[str, Any]]:
        chats = self._sdk().list_chats(page=1, page_size=100)
        assistants = []
        for chat in chats:
            prompt_config = getattr(chat, "prompt_config", {})
            description = getattr(chat, "description", "")
            if not description and isinstance(prompt_config, dict):
                description = prompt_config.get("prologue", "")
            assistants.append(
                {
                    "id": str(getattr(chat, "id", "")),
                    "name": str(getattr(chat, "name", "assistant")),
                    "description": str(description),
                }
            )
        return assistants

    async def list_assistants(self) -> dict[str, Any]:
        if self.settings.demo_mode:
            return {"ok": True, "mode": "demo", "assistants": self._demo_assistants()}
        if self.settings.ragflow_api_url is None or self.settings.ragflow_api_key is None:
            return _ragflow_error(
                "not_configured", "RAGFLOW_API_URL and RAGFLOW_API_KEY are required"
            )
        try:
            assistants = await asyncio.wait_for(
                asyncio.to_thread(self._list_sync),
                timeout=self.settings.external_timeout_seconds + 0.1,
            )
            return {"ok": True, "mode": "real", "assistants": assistants}
        except TimeoutError:
            return _ragflow_error("timeout", "RAGFlow assistant listing timed out", retryable=True)
        except Exception as exc:
            return _ragflow_error(
                "provider_error",
                f"RAGFlow assistant listing failed: {type(exc).__name__}",
                retryable=True,
            )

    def _ask_sync(
        self, assistant_id: str, questions: list[str]
    ) -> tuple[list[dict[str, Any]], str | None]:
        chat = self._sdk().get_chat(assistant_id)
        session = chat.create_session(
            name=f"deep-research-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
        )
        answers: list[dict[str, Any]] = []
        cleanup_warning: str | None = None
        try:
            for question in questions:
                messages = list(session.ask(question=question, stream=False))
                for message in messages:
                    answers.append(
                        {
                            "question": question,
                            "content": str(getattr(message, "content", "")),
                            "reference": getattr(message, "reference", None),
                        }
                    )
        finally:
            try:
                chat.delete_sessions(ids=[str(session.id)])
            except Exception as exc:
                cleanup_warning = f"session cleanup failed: {type(exc).__name__}"
        return answers, cleanup_warning

    @staticmethod
    def _demo_ask(assistant_id: str, questions: list[str]) -> list[dict[str, Any]]:
        corpus = {
            "demo-policy": (
                "Demo policy knowledge: sensitive values remain environment-only; access is "
                "least-privilege; execution logs are separated from user-facing monitoring."
            ),
            "demo-product": (
                "Demo product knowledge: research tasks use specialist source adapters, retain "
                "source metadata, and generate Markdown before optional PDF conversion."
            ),
        }
        knowledge = corpus[assistant_id]
        return [
            {
                "question": question,
                "content": f"{knowledge} Retrieval angle: {question}",
                "reference": [{"document": "local-demo-knowledge", "chunk": index + 1}],
            }
            for index, question in enumerate(questions)
        ]

    async def ask_and_cleanup(
        self, assistant_id: str, questions: list[str]
    ) -> dict[str, Any]:
        if not ASSISTANT_ID_PATTERN.fullmatch(assistant_id):
            return _ragflow_error("invalid_assistant", "invalid RAGFlow assistant id")
        normalized_questions = [question.strip() for question in questions if question.strip()]
        if not 1 <= len(normalized_questions) <= 5:
            return _ragflow_error("invalid_questions", "provide between one and five questions")
        if any(len(question) > 4_000 for question in normalized_questions):
            return _ragflow_error("invalid_questions", "a RAGFlow question is too long")

        if self.settings.demo_mode:
            assistant_ids = {item["id"] for item in self._demo_assistants()}
            if assistant_id not in assistant_ids:
                return _ragflow_error("not_found", "demo assistant does not exist")
            return {
                "ok": True,
                "mode": "demo",
                "assistant_id": assistant_id,
                "answers": self._demo_ask(assistant_id, normalized_questions),
                "cleanup_warning": None,
            }
        if self.settings.ragflow_api_url is None or self.settings.ragflow_api_key is None:
            return _ragflow_error(
                "not_configured", "RAGFLOW_API_URL and RAGFLOW_API_KEY are required"
            )
        try:
            answers, cleanup_warning = await asyncio.wait_for(
                asyncio.to_thread(self._ask_sync, assistant_id, normalized_questions),
                timeout=(self.settings.external_timeout_seconds + 0.1)
                * len(normalized_questions),
            )
            return {
                "ok": True,
                "mode": "real",
                "assistant_id": assistant_id,
                "answers": answers,
                "cleanup_warning": cleanup_warning,
            }
        except TimeoutError:
            return _ragflow_error("timeout", "RAGFlow query timed out", retryable=True)
        except Exception as exc:
            return _ragflow_error(
                "provider_error", f"RAGFlow query failed: {type(exc).__name__}", retryable=True
            )


async def get_assistant_list(*, service: RagflowService) -> dict[str, Any]:
    """List selectable RAGFlow chat assistants."""
    return await service.list_assistants()


async def create_ask_delete(
    assistant_id: str,
    questions: list[str],
    *,
    service: RagflowService,
) -> dict[str, Any]:
    """Create an isolated session, ask bounded questions, and delete the session."""
    return await service.ask_and_cleanup(assistant_id, questions)


def make_ragflow_tools(settings: Settings) -> list[BaseTool]:
    service = RagflowService(settings)

    async def list_tool() -> dict[str, Any]:
        """List RAGFlow assistants with their names and descriptions."""
        return await get_assistant_list(service=service)

    async def ask_tool(assistant_id: str, questions: list[str]) -> dict[str, Any]:
        """Ask one selected RAGFlow assistant up to five questions in a temporary session."""
        return await create_ask_delete(assistant_id, questions, service=service)

    return [
        StructuredTool.from_function(
            coroutine=list_tool,
            name="get_assistant_list",
            description="List available RAGFlow knowledge-base assistants before selecting one.",
        ),
        StructuredTool.from_function(
            coroutine=ask_tool,
            name="create_ask_delete",
            description=(
                "Create a temporary RAGFlow session, ask one to five progressively focused "
                "questions, retain answers and references, then delete the session."
            ),
        ),
    ]
