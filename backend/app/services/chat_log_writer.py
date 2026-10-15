"""Writes chat log rows in the background, so the visitor never waits for the database.

If the database is down, writes would pile up in memory (each holds a question and an answer).
So the number of pending writes has a ceiling, and rows over it are dropped and counted. The
drops are logged at most once a minute, or a slow database would also flood the logs.
"""

import asyncio
import logging
import time
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.repositories import ChatLogEntry
from app.services.chat_log import record_chat_message

logger = logging.getLogger(__name__)

MAX_PENDING_WRITES: Final = 100
DROP_LOG_EVERY_SECONDS: Final = 60.0


class ChatLogWriter:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None,
        *,
        max_pending: int = MAX_PENDING_WRITES,
    ) -> None:
        self._session_factory = session_factory
        self._max_pending = max_pending
        # Tasks are kept in a set: the event loop only holds weak references to them.
        self._pending: set[asyncio.Task[object]] = set()
        self.dropped = 0
        self._last_drop_log = float("-inf")

    def submit(self, entry: ChatLogEntry) -> None:
        """Start writing `entry` and return at once. Must be called from a running event loop."""
        if self._session_factory is None:
            return
        if len(self._pending) >= self._max_pending:
            self._note_drop()
            return
        task = asyncio.create_task(record_chat_message(self._session_factory, entry))
        self._pending.add(task)
        task.add_done_callback(self._finished)

    async def drain(self, timeout_seconds: float) -> None:
        """Wait for pending writes at shutdown, up to `timeout_seconds`."""
        if not self._pending:
            return
        _, still_pending = await asyncio.wait(self._pending, timeout=timeout_seconds)
        if still_pending:
            logger.error("shutdown_dropped", extra={"count": len(still_pending)})

    def _note_drop(self) -> None:
        self.dropped += 1
        now = time.monotonic()
        if now - self._last_drop_log >= DROP_LOG_EVERY_SECONDS:
            self._last_drop_log = now
            logger.error(
                "chat_log_dropped",
                extra={"pending": len(self._pending), "dropped_total": self.dropped},
            )

    def _finished(self, task: asyncio.Task[object]) -> None:
        self._pending.discard(task)
        if not task.cancelled() and task.exception() is not None:
            # record_chat_message handles database errors; this is any other bug.
            logger.error("chat_log_task_failed", extra={"error": type(task.exception()).__name__})
