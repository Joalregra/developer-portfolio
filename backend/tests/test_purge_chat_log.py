"""Retention: rows older than the period go away with their ratings, in batches, safely."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.jobs.purge_chat_log import EXIT_FAILED, EXIT_OK, run
from app.models.chat import ChatMessage, ChatStatus, Feedback, LlmProvider
from app.services.retention import purge_expired_messages
from tests.conftest import sqlite_url

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 15, 3, 0, tzinfo=UTC)


def clock() -> datetime:
    return NOW


async def add_message(
    factory: async_sessionmaker[AsyncSession], *, age_days: float, rated: bool = False
) -> uuid.UUID:
    message_id = uuid.uuid4()
    async with factory() as session:
        session.add(
            ChatMessage(
                id=message_id,
                created_at=NOW - timedelta(days=age_days),
                locale="en",
                question="Which databases has Johan used?",
                answer=None,
                status=ChatStatus.PROVIDER_ERROR.value,
                provider=LlmProvider.NONE.value,
                latency_ms=10,
                knowledge_version="v1",
            )
        )
        await session.flush()  # the rating refers to the message
        if rated:
            session.add(Feedback(id=uuid.uuid4(), message_id=message_id, helpful=True))
        await session.commit()
    return message_id


async def remaining(factory: async_sessionmaker[AsyncSession]) -> set[uuid.UUID]:
    async with factory() as session:
        return set((await session.scalars(select(ChatMessage.id))).all())


async def ratings(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        return (await session.scalar(select(func.count()).select_from(Feedback))) or 0


async def test_only_messages_older_than_the_period_are_deleted(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    old = await add_message(session_factory, age_days=91)
    almost = await add_message(session_factory, age_days=89)
    exactly = await add_message(session_factory, age_days=90)
    new = await add_message(session_factory, age_days=0)

    deleted = await purge_expired_messages(session_factory, retention_days=90, clock=clock)

    assert deleted == 1
    assert await remaining(session_factory) == {almost, exactly, new}
    assert old not in await remaining(session_factory)


async def test_the_rating_of_a_deleted_message_goes_with_it(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await add_message(session_factory, age_days=200, rated=True)
    await add_message(session_factory, age_days=1, rated=True)

    await purge_expired_messages(session_factory, retention_days=90, clock=clock)

    assert await ratings(session_factory) == 1


async def test_a_big_backlog_is_deleted_in_batches_and_a_second_run_finds_nothing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    for age in range(100, 105):
        await add_message(session_factory, age_days=age)
    kept = await add_message(session_factory, age_days=5)

    first = await purge_expired_messages(
        session_factory, retention_days=90, batch_size=2, clock=clock
    )
    second = await purge_expired_messages(
        session_factory, retention_days=90, batch_size=2, clock=clock
    )

    assert (first, second) == (5, 0)
    assert await remaining(session_factory) == {kept}


async def test_the_oldest_rows_go_first_when_the_run_is_cut_short(
    session_factory: async_sessionmaker[AsyncSession], caplog: pytest.LogCaptureFixture
) -> None:
    oldest = await add_message(session_factory, age_days=300)
    middle = await add_message(session_factory, age_days=200)
    newest_expired = await add_message(session_factory, age_days=100)

    with caplog.at_level(logging.WARNING):
        deleted = await purge_expired_messages(
            session_factory, retention_days=90, batch_size=1, max_batches=2, clock=clock
        )

    assert deleted == 2
    assert await remaining(session_factory) == {newest_expired}
    assert oldest not in await remaining(session_factory)
    assert middle not in await remaining(session_factory)
    assert "chat_log_purge_incomplete" in caplog.text


async def test_an_empty_log_deletes_nothing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    assert await purge_expired_messages(session_factory, retention_days=90, clock=clock) == 0


async def test_the_command_purges_with_the_retention_url(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    # The `engine` fixture created tmp_path/test.db; the command connects to it by URL.
    await add_message(session_factory, age_days=400)
    settings = Settings(
        _env_file=None,
        environment="test",
        retention_database_url=sqlite_url(tmp_path / "test.db"),
    )

    code = await run(settings)

    assert code == EXIT_OK
    assert await remaining(session_factory) == set()


async def test_the_command_fails_loudly_without_the_retention_url(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = Settings(_env_file=None, environment="test", retention_database_url=None)

    code = await run(settings)

    assert code == EXIT_FAILED
    assert "retention_database_url_not_set" in caplog.text


async def test_the_command_fails_when_the_database_does_not_answer(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        retention_database_url=sqlite_url(tmp_path / "missing" / "x.db"),
    )

    code = await run(settings)

    assert code == EXIT_FAILED
    assert "chat_log_purge_failed" in caplog.text
