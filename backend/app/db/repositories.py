"""Reads and writes of the assistant log. Only SQL lives here; it knows no HTTP and no rules.

The feedback repository arrives with the feedback endpoint.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.locale import Locale
from app.models.chat import ChatMessage, ChatStatus, LlmProvider


@dataclass(frozen=True, slots=True)
class ChatLogEntry:
    """One question and what happened to it. A plain value, so this layer needs no API schema.

    The `id` is created with the entry, before anything is written. The chat can then return it
    to the browser and write the row after the answer was sent.
    """

    locale: Locale
    question: str
    answer: str | None
    status: ChatStatus
    provider: LlmProvider
    latency_ms: int
    knowledge_version: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)


class ChatLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, entry: ChatLogEntry) -> None:
        """Insert one row and commit. The database constraints decide if the row is valid."""
        self.session.add(
            ChatMessage(
                id=entry.id,
                locale=entry.locale.value,
                question=entry.question,
                answer=entry.answer,
                status=entry.status.value,
                provider=entry.provider.value,
                latency_ms=entry.latency_ms,
                prompt_tokens=entry.prompt_tokens,
                completion_tokens=entry.completion_tokens,
                cached_tokens=entry.cached_tokens,
                knowledge_version=entry.knowledge_version,
            )
        )
        await self.session.commit()
