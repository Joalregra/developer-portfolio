"""Deletes chat log rows older than the retention period (rule DATA-06).

The log keeps visitors' questions, so it must not grow forever. The work is split into small
batches, each in its own transaction, so a long clean-up never blocks the chat from writing. It is
safe to run twice or to stop halfway: the next run continues where this one left off.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.repositories import RetentionRepository

logger = logging.getLogger(__name__)

BATCH_SIZE: Final = 1000
# A daily run deletes about a day of rows. This ceiling (500,000 rows) only stops a bug from
# keeping the job busy for ever; whatever is left is deleted by the next run.
MAX_BATCHES_PER_RUN: Final = 500


async def purge_expired_messages(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    retention_days: int,
    batch_size: int = BATCH_SIZE,
    max_batches: int = MAX_BATCHES_PER_RUN,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    """Delete the messages (and their ratings) created more than `retention_days` ago.

    Args:
        session_factory: Must connect as a user allowed to SELECT and DELETE.
        retention_days: How long a message is kept.
        batch_size: Rows deleted per transaction.
        max_batches: Most transactions in one run.
        clock: Current time in UTC, injectable for tests.

    Returns:
        How many messages were deleted.

    Raises:
        SQLAlchemyError: The database failed. Batches already committed stay deleted.
    """
    cutoff = clock() - timedelta(days=retention_days)
    deleted_total = 0
    for _ in range(max_batches):
        async with session_factory() as session:
            deleted = await RetentionRepository(session).delete_older_than(cutoff, limit=batch_size)
        deleted_total += deleted
        if deleted < batch_size:
            return deleted_total
    logger.warning("chat_log_purge_incomplete", extra={"deleted": deleted_total})
    return deleted_total
