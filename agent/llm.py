"""OpenAI-compatible model construction for Real Mode."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from utils.config import Settings


def create_chat_model(settings: Settings) -> ChatOpenAI:
    """Create a lazy network client without performing a provider request."""
    settings.require_real_llm()
    assert settings.openai_api_key is not None
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=settings.llm_temperature,
        timeout=settings.external_timeout_seconds,
        max_retries=2,
        stream_usage=False,
        use_responses_api=False,
    )

