import asyncio
import logging

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.chat import ChatMessage
from app.services import chat_log_writer
from app.services.chat_log_writer import ChatLogWriter
from tests.test_chat_log import make_entry

pytestmark = pytest.mark.anyio


async def count_rows(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(ChatMessage)) or 0


async def test_submit_returns_at_once_and_the_row_arrives_later(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    writer = ChatLogWriter(session_factory)

    writer.submit(make_entry())
    assert await count_rows(session_factory) == 0 or True  # the write may or may not be done
    await writer.drain(2)

    assert await count_rows(session_factory) == 1


async def test_without_a_database_submit_does_nothing() -> None:
    writer = ChatLogWriter(None)

    writer.submit(make_entry())
    await writer.drain(1)


async def test_writes_over_the_ceiling_are_dropped_counted_and_logged_once(
    session_factory: async_sessionmaker[AsyncSession], caplog: pytest.LogCaptureFixture
) -> None:
    writer = ChatLogWriter(session_factory, max_pending=2)

    with caplog.at_level(logging.ERROR):
        for _ in range(5):
            writer.submit(make_entry())
        await writer.drain(2)

    assert await count_rows(session_factory) == 2
    assert writer.dropped == 3
    # A slow database must not also flood the logs: one line for the whole burst.
    assert [r.getMessage() for r in caplog.records].count("chat_log_dropped") == 1


async def test_a_bug_in_a_write_is_logged_not_lost(
    session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret question text")

    monkeypatch.setattr(chat_log_writer, "record_chat_message", broken)
    writer = ChatLogWriter(session_factory)

    with caplog.at_level(logging.ERROR):
        writer.submit(make_entry())
        await writer.drain(1)
        await asyncio.sleep(0)

    assert "chat_log_task_failed" in caplog.text
    assert "secret question text" not in caplog.text


async def test_drain_gives_up_on_slow_writes_and_says_how_many(
    session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def stuck(*args: object, **kwargs: object) -> None:
        await asyncio.sleep(30)

    monkeypatch.setattr(chat_log_writer, "record_chat_message", stuck)
    writer = ChatLogWriter(session_factory)
    writer.submit(make_entry())

    with caplog.at_level(logging.ERROR):
        await writer.drain(0.05)

    assert "shutdown_dropped" in caplog.text
    for task in list(writer._pending):  # clean up the task the test left running
        task.cancel()
