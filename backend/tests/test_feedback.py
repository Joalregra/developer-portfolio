"""POST /api/chat/feedback: one rating per answer, idempotent, 404 for an unknown message."""

import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.locale import Locale
from app.db.repositories import ChatLogEntry, ChatLogRepository, FeedbackRepository
from app.db.session import create_engine, create_session_factory
from app.main import create_app
from app.models.chat import ChatStatus, Feedback, LlmProvider
from app.services.feedback import FeedbackService
from app.services.rate_limit import RateLimiter
from tests.conftest import sqlite_url

pytestmark = pytest.mark.anyio


@dataclass
class Rating:
    app: FastAPI
    client: httpx.AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    message_id: uuid.UUID

    async def send(self, body: dict[str, Any] | None = None) -> httpx.Response:
        payload = body or {"message_id": str(self.message_id), "helpful": True, "locale": "en"}
        return await self.client.post("/api/chat/feedback", json=payload)

    async def ratings(self) -> list[Feedback]:
        async with self.session_factory() as session:
            return list((await session.scalars(select(Feedback))).all())


async def store_message(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    entry = ChatLogEntry(
        locale=Locale.EN,
        question="Which databases has Johan used?",
        answer="PostgreSQL.",
        status=ChatStatus.ANSWERED,
        provider=LlmProvider.GROQ,
        latency_ms=800,
        knowledge_version="v1",
    )
    async with session_factory() as session:
        await ChatLogRepository(session).add(entry)
    return entry.id


@pytest.fixture
async def rating(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[Rating]:
    app = create_app(Settings(_env_file=None, environment="test", chat_enabled=False))
    app.state.feedback_service = FeedbackService.with_default_limits(session_factory)
    message_id = await store_message(session_factory)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield Rating(app, client, session_factory, message_id)


async def test_the_first_rating_is_stored(rating: Rating) -> None:
    response = await rating.send()

    assert response.status_code == 204
    assert response.content == b""
    (stored,) = await rating.ratings()
    assert (stored.message_id, stored.helpful) == (rating.message_id, True)


async def test_rating_again_with_the_same_value_changes_nothing(rating: Rating) -> None:
    await rating.send()

    response = await rating.send()

    assert response.status_code == 204
    assert len(await rating.ratings()) == 1


async def test_rating_again_with_the_other_value_keeps_the_first_one(rating: Rating) -> None:
    await rating.send()

    response = await rating.send(
        {"message_id": str(rating.message_id), "helpful": False, "locale": "en"}
    )

    assert response.status_code == 204
    (stored,) = await rating.ratings()
    assert stored.helpful is True


async def test_a_repeated_rating_is_logged_as_a_duplicate(
    rating: Rating, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        await rating.send()
        await rating.send()

    recorded = [r for r in caplog.records if r.getMessage() == "feedback_recorded"]
    assert [r.__dict__["duplicate"] for r in recorded] == [False, True]


async def test_a_message_deleted_between_the_check_and_the_insert_is_a_404(
    rating: Rating, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def claims_it_exists(self: FeedbackRepository, message_id: uuid.UUID) -> bool:
        return True  # the check passed; the foreign key then refuses the insert

    monkeypatch.setattr(FeedbackRepository, "message_exists", claims_it_exists)

    response = await rating.send({"message_id": str(uuid.uuid4()), "helpful": True, "locale": "en"})

    assert response.status_code == 404
    assert await rating.ratings() == []


@pytest.mark.parametrize(("locale", "text"), [("en", "no longer available"), ("es", "ya no está")])
async def test_an_unknown_message_is_a_404_in_the_visitors_language(
    rating: Rating, locale: str, text: str
) -> None:
    response = await rating.send(
        {"message_id": str(uuid.uuid4()), "helpful": True, "locale": locale}
    )

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert text in error["message"]
    assert await rating.ratings() == []


@pytest.mark.parametrize(
    "body",
    [
        {"message_id": "not-a-uuid", "helpful": True, "locale": "en"},
        {"message_id": str(uuid.uuid4()), "helpful": "maybe", "locale": "en"},
        {"message_id": str(uuid.uuid4()), "helpful": True},
        {"message_id": str(uuid.uuid4()), "helpful": True, "locale": "fr"},
        {"message_id": str(uuid.uuid4()), "helpful": True, "locale": "en", "comment": "hi"},
    ],
    ids=["bad-uuid", "bad-bool", "no-locale", "bad-locale", "extra-field"],
)
async def test_a_malformed_rating_is_a_422(rating: Rating, body: dict[str, Any]) -> None:
    response = await rating.send(body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


async def test_too_many_ratings_from_one_visitor_are_a_429(rating: Rating) -> None:
    rating.app.state.feedback_service = FeedbackService(
        rating.session_factory, RateLimiter(per_minute=2, per_day=50)
    )

    statuses = [(await rating.send()).status_code for _ in range(3)]

    assert statuses == [204, 204, 429]


async def test_without_a_database_the_answer_is_a_503() -> None:
    app = create_app(Settings(_env_file=None, environment="test", chat_enabled=False))
    app.state.feedback_service = FeedbackService.with_default_limits(None)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat/feedback",
            json={"message_id": str(uuid.uuid4()), "helpful": True, "locale": "en"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "feedback_unavailable"


async def test_an_app_started_without_the_service_answers_503(rating: Rating) -> None:
    rating.app.state.feedback_service = None

    response = await rating.send()

    assert response.status_code == 503


async def test_a_database_failure_is_a_503_and_leaks_nothing(
    rating: Rating, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    broken = create_session_factory(create_engine(sqlite_url(tmp_path / "gone" / "x.db")))
    rating.app.state.feedback_service = FeedbackService.with_default_limits(broken)

    response = await rating.send()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "feedback_unavailable"
    assert "feedback_failed" in caplog.text
    assert str(rating.message_id) not in caplog.text
