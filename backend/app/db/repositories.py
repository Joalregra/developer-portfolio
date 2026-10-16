"""Reads and writes of the assistant log. Only SQL lives here; it knows no HTTP and no rules."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.locale import Locale
from app.models.chat import ChatMessage, ChatStatus, Feedback, LlmProvider


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


class RetentionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def delete_older_than(self, cutoff: datetime, *, limit: int) -> int:
        """Delete up to `limit` messages created before `cutoff`, oldest first, and commit.

        Their ratings go with them (ON DELETE CASCADE). A small batch keeps each transaction
        short, so the job never holds a long lock on the table the chat writes to.

        Returns:
            How many messages were deleted.
        """
        expired = (
            select(ChatMessage.id)
            .where(ChatMessage.created_at < cutoff)
            .order_by(ChatMessage.created_at)
            .limit(limit)
        )
        result = await self.session.execute(delete(ChatMessage).where(ChatMessage.id.in_(expired)))
        await self.session.commit()
        return cast("CursorResult[Any]", result).rowcount


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def message_exists(self, message_id: uuid.UUID) -> bool:
        query = select(ChatMessage.id).where(ChatMessage.id == message_id).limit(1)
        return (await self.session.scalar(query)) is not None

    async def add_if_absent(self, message_id: uuid.UUID, *, helpful: bool) -> bool:
        """Insert the rating unless the message already has one, and commit.

        The database decides, not a SELECT before the INSERT: two clicks at the same time cannot
        both win. A second rating, with the same value or the other one, is ignored.

        Returns:
            True if a row was stored, False if the message was already rated.

        Raises:
            IntegrityError: The message does not exist (the foreign key refuses the row).
        """
        # The app runs on PostgreSQL; the tests on SQLite, which has the same ON CONFLICT clause.
        on_postgresql = self.session.get_bind().dialect.name == "postgresql"
        insert = postgresql.insert if on_postgresql else sqlite.insert
        statement = (
            insert(Feedback)
            .values(id=uuid.uuid4(), message_id=message_id, helpful=helpful)
            .on_conflict_do_nothing(index_elements=[Feedback.message_id])
        )
        # The union of the two dialects' Insert hides that this is a CursorResult.
        result = cast("CursorResult[Any]", await self.session.execute(statement))
        await self.session.commit()
        return result.rowcount == 1
