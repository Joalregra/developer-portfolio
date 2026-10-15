"""Builds the chat service from the settings, once at startup.

This is the one place that knows about the real Groq and Gemini clients. Everything else gets
them through the LLMProvider protocol, which is why the tests can use fakes.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final

import groq
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.services.budget import DailyBudget
from app.services.chat_log_writer import ChatLogWriter
from app.services.chat_service import ChatService
from app.services.guard import PromptGuard
from app.services.knowledge import Knowledge
from app.services.llm import gemini_provider, groq_provider
from app.services.llm.base import LLMProvider
from app.services.llm.router import LLMRouter
from app.services.output_validator import OutputValidator, build_allowed_url_prefixes
from app.services.prompt import RULES, build_system_prompt
from app.services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

LOG_DRAIN_SECONDS: Final = 5.0

Closer = Callable[[], Awaitable[None]]


class ChatConfigurationError(Exception):
    """The chat is switched on but something it needs is not configured."""


@dataclass
class ChatRuntime:
    """The chat service and what must be closed when the app stops."""

    service: ChatService
    writer: ChatLogWriter
    closers: list[Closer] = field(default_factory=list)

    async def aclose(self) -> None:
        await self.writer.drain(LOG_DRAIN_SECONDS)
        for close in self.closers:
            await close()


def build_chat_runtime(
    settings: Settings,
    knowledge: Knowledge,
    session_factory: async_sessionmaker[AsyncSession] | None,
) -> ChatRuntime:
    """Create the service. Call only when `settings.chat_enabled` is true.

    Raises:
        ChatConfigurationError: A setting the chat needs is missing.
        KnowledgeError: The knowledge is too big for the model limits.
    """
    missing = settings.missing_chat_settings()
    if missing:
        raise ChatConfigurationError(f"The chat needs these settings: {', '.join(missing)}.")
    # missing_chat_settings() guarantees these are set; the asserts help the type checker.
    assert settings.groq_api_key and settings.groq_model and settings.guard_model  # noqa: S101
    assert settings.canary_token  # noqa: S101

    groq_client = groq_provider.create_client(settings.groq_api_key.get_secret_value())
    closers: list[Closer] = [groq_client.close]
    fallback = _build_fallback(settings, closers)
    writer = ChatLogWriter(session_factory)
    service = ChatService(
        enabled=settings.chat_enabled,
        knowledge=knowledge,
        system_prompt=build_system_prompt(
            knowledge.prompt_text, settings.canary_token.get_secret_value()
        ),
        router=LLMRouter(
            _build_primary(settings, groq_client),
            fallback,
            DailyBudget(settings.daily_llm_budget),
            primary_timeout=settings.groq_timeout_seconds,
            fallback_timeout=settings.gemini_timeout_seconds,
        ),
        guard=PromptGuard(
            groq_provider.GroqPromptGuard(groq_client, model=settings.guard_model),
            threshold=settings.guard_threshold,
            time_limit=settings.guard_timeout_seconds,
        ),
        validator=OutputValidator(
            canary=settings.canary_token.get_secret_value(),
            rules_text=RULES,
            allowed_url_prefixes=build_allowed_url_prefixes(settings.site_url),
        ),
        rate_limiter=RateLimiter(settings.rate_limit_per_minute, settings.rate_limit_per_day),
        writer=writer,
        request_timeout_seconds=settings.request_timeout_seconds,
    )
    return ChatRuntime(service=service, writer=writer, closers=closers)


def _build_primary(settings: Settings, client: groq.AsyncGroq) -> LLMProvider:
    assert settings.groq_model  # noqa: S101 - checked by missing_chat_settings()
    return groq_provider.GroqProvider(
        client,
        model=settings.groq_model,
        temperature=settings.llm_temperature,
        max_output_tokens=settings.llm_max_output_tokens,
    )


def _build_fallback(settings: Settings, closers: list[Closer]) -> LLMProvider | None:
    """The Gemini fallback, or None when it is not configured (the chat still works)."""
    if not (settings.gemini_api_key and settings.gemini_model):
        logger.warning("fallback_not_configured")
        return None
    client = gemini_provider.create_client(settings.gemini_api_key.get_secret_value())
    closers.append(client.aio.aclose)
    return gemini_provider.GeminiProvider(
        client,
        model=settings.gemini_model,
        temperature=settings.llm_temperature,
        max_output_tokens=settings.llm_max_output_tokens,
    )
