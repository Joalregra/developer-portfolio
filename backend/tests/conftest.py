from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.session import create_engine, create_session_factory
from app.main import create_app
from app.models import chat  # noqa: F401 - registers the models in Base.metadata


@pytest.fixture
def settings() -> Settings:
    # `_env_file=None` keeps a developer's real .env (keys, database) out of the tests.
    return Settings(_env_file=None, environment="test", chat_enabled=False)


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path}"


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """A SQLite database with the real tables. The constraints are the ones PostgreSQL gets."""
    test_engine = create_engine(sqlite_url(tmp_path / "test.db"))

    @event.listens_for(test_engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
        # SQLite ignores foreign keys unless asked, PostgreSQL never does.
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)
