import logging
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.locale import Locale
from app.db.repositories import ChatLogEntry, ChatLogRepository
from app.db.session import create_engine, create_session_factory
from app.main import create_app
from app.models.chat import ChatMessage, ChatStatus, Feedback, LlmProvider
from app.services.chat_log import record_chat_message
from tests.conftest import sqlite_url

pytestmark = pytest.mark.anyio

QUESTION = "Which projects has Johan built with FastAPI?"


def make_entry(**changes: Any) -> ChatLogEntry:
    """A valid answered row. Each test changes only the field it is about."""
    entry = ChatLogEntry(
        locale=Locale.EN,
        question=QUESTION,
        answer="He built Gedocs and an AI reporting platform.",
        status=ChatStatus.ANSWERED,
        provider=LlmProvider.GROQ,
        latency_ms=850,
        knowledge_version="abc123",
        prompt_tokens=7000,
        completion_tokens=120,
        cached_tokens=6500,
    )
    return replace(entry, **changes)


async def test_valid_entry_is_stored_and_its_id_returned(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    entry = make_entry()

    saved_id = await record_chat_message(session_factory, entry)

    assert saved_id == entry.id
    async with session_factory() as session:
        row = await session.get(ChatMessage, entry.id)
    assert row is not None
    assert (row.question, row.status, row.provider, row.cached_tokens) == (
        QUESTION,
        "answered",
        "groq",
        6500,
    )


async def test_quick_answer_without_a_model_is_valid(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    entry = make_entry(
        status=ChatStatus.ANSWERED_QUICK,
        provider=LlmProvider.NONE,
        prompt_tokens=None,
        completion_tokens=None,
        cached_tokens=None,
    )

    assert await record_chat_message(session_factory, entry) == entry.id


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"question": ""}, id="empty-question"),
        pytest.param({"question": "x" * 1001}, id="question-too-long"),
        pytest.param({"answer": None}, id="answered-without-answer"),
        pytest.param({"answer": "x" * 2001}, id="answer-too-long"),
        pytest.param({"provider": LlmProvider.NONE}, id="answered-without-a-model"),
        pytest.param(
            {"status": ChatStatus.ANSWERED_QUICK, "provider": LlmProvider.GROQ},
            id="quick-answer-with-a-model",
        ),
        pytest.param(
            {"status": ChatStatus.REFUSED_OFF_TOPIC, "provider": LlmProvider.NONE},
            id="off-topic-refusal-without-a-model",
        ),
        pytest.param(
            {"status": ChatStatus.REFUSED_INJECTION, "provider": LlmProvider.NONE},
            id="tokens-without-a-model",
        ),
        pytest.param({"latency_ms": -1}, id="negative-latency"),
        pytest.param({"prompt_tokens": -1, "cached_tokens": None}, id="negative-tokens"),
        pytest.param({"cached_tokens": 7001}, id="cached-more-than-prompt"),
        pytest.param({"knowledge_version": ""}, id="empty-knowledge-version"),
    ],
)
async def test_database_rejects_invalid_rows(
    session_factory: async_sessionmaker[AsyncSession], changes: dict[str, Any]
) -> None:
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await ChatLogRepository(session).add(make_entry(**changes))


async def test_database_rejects_unknown_status_and_locale(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # The enums stop these in Python, so the test writes the rows directly.
    for bad in ({"status": "banned"}, {"locale": "fr"}, {"provider": "openai"}):
        values = {
            "id": uuid.uuid4(),
            "locale": "en",
            "question": "q",
            "answer": "a",
            "status": "answered",
            "provider": "groq",
            "latency_ms": 1,
            "knowledge_version": "v",
        } | bad
        async with session_factory() as session:
            session.add(ChatMessage(**values))
            with pytest.raises(IntegrityError):
                await session.commit()


async def test_no_database_means_nothing_is_stored() -> None:
    assert await record_chat_message(None, make_entry()) is None


async def test_write_failure_returns_none_and_never_logs_the_question(
    session_factory: async_sessionmaker[AsyncSession], caplog: pytest.LogCaptureFixture
) -> None:
    invalid = make_entry(answer=None)  # rejected by the database

    with caplog.at_level(logging.ERROR):
        assert await record_chat_message(session_factory, invalid) is None

    assert [record.getMessage() for record in caplog.records] == ["chat_log_failed"]
    assert QUESTION not in caplog.text


async def test_unreachable_database_returns_none(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "missing-folder" / "x.db"))
    try:
        assert await record_chat_message(create_session_factory(engine), make_entry()) is None
    finally:
        await engine.dispose()


async def test_feedback_needs_an_existing_message_and_is_one_per_message(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    entry = make_entry()
    await record_chat_message(session_factory, entry)

    async with session_factory() as session:
        session.add(Feedback(id=uuid.uuid4(), message_id=uuid.uuid4(), helpful=True))
        with pytest.raises(IntegrityError):  # message does not exist
            await session.commit()

    async with session_factory() as session:
        session.add(Feedback(id=uuid.uuid4(), message_id=entry.id, helpful=True))
        await session.commit()
    async with session_factory() as session:
        session.add(Feedback(id=uuid.uuid4(), message_id=entry.id, helpful=False))
        with pytest.raises(IntegrityError):  # already rated
            await session.commit()


async def test_deleting_a_message_deletes_its_feedback(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    entry = make_entry()
    await record_chat_message(session_factory, entry)
    async with session_factory() as session:
        session.add(Feedback(id=uuid.uuid4(), message_id=entry.id, helpful=True))
        await session.commit()

    async with session_factory() as session:
        message = await session.get(ChatMessage, entry.id)
        assert message is not None
        await session.delete(message)
        await session.commit()

    async with session_factory() as session:
        assert (await session.scalars(select(Feedback))).all() == []


def test_app_starts_without_a_database(app: FastAPI) -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert app.state.session_factory is None


def test_app_opens_the_database_on_startup(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        chat_enabled=False,
        database_url=sqlite_url(tmp_path / "app.db"),
    )
    app = create_app(settings)

    with TestClient(app):
        assert app.state.session_factory is not None
