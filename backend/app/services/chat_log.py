"""Best-effort recording of chat questions (DATA-05).

The chat must never depend on the database: if Neon is down, the visitor still gets an answer.
This module writes the log row and swallows only database errors, after logging them.
"""

import logging
import uuid

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.repositories import ChatLogEntry, ChatLogRepository

logger = logging.getLogger(__name__)


async def record_chat_message(
    session_factory: async_sessionmaker[AsyncSession] | None, entry: ChatLogEntry
) -> uuid.UUID | None:
    """Store `entry` and return its id, or return None if it could not be stored.

    Args:
        session_factory: Where to open a session, or None when no database is configured.
        entry: The question and its outcome.

    Returns:
        The id of the stored row, or None when there is no database or the write failed.
    """
    if session_factory is None:
        return None
    try:
        async with session_factory() as session:
            await ChatLogRepository(session).add(entry)
    except SQLAlchemyError as exc:
        # The visitor already has the answer. Log the error type only: the exception text can
        # contain the SQL parameters, which include the visitor's question.
        logger.error(
            "chat_log_failed",
            extra={"error": type(exc).__name__, "message_id": str(entry.id)},
        )
        return None
    return entry.id
