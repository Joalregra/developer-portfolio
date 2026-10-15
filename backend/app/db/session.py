"""Async engine and session factory. Created once in the app lifespan, never at import time."""

import asyncio
import logging
from typing import Any

from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

# Neon can sleep when idle and take a few seconds to wake. Logging is best effort and runs
# after the answer, so waiting this long never delays a visitor.
POSTGRES_CONNECT_TIMEOUT_SECONDS = 5
POOL_TIMEOUT_SECONDS = 5


def create_engine(database_url: str) -> AsyncEngine:
    """Create the async engine for `database_url`.

    `pool_pre_ping` drops dead connections, common with serverless PostgreSQL.
    `hide_parameters` keeps the values of a failed query out of the error text: they contain
    the visitor's question, which must never reach the logs (brief, section 9.6).
    """
    connect_args: dict[str, Any] = {}
    if make_url(database_url).get_backend_name() == "postgresql":
        connect_args["connect_timeout"] = POSTGRES_CONNECT_TIMEOUT_SECONDS
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        hide_parameters=True,
        # A write waits at most this long for a free connection; after that it is dropped,
        # instead of queueing behind a database that does not answer.
        pool_timeout=POOL_TIMEOUT_SECONDS,
        connect_args=connect_args,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False lets code read an object after commit without a new query.
    return async_sessionmaker(engine, expire_on_commit=False)


def warn_if_event_loop_unsupported() -> None:
    """Say it out loud when psycopg cannot work, instead of failing silently on every write.

    psycopg in async mode needs a selector event loop. On Windows, asyncio defaults to the
    proactor loop, and uvicorn only switches to the selector one when started with --reload.
    Linux, where the app is deployed, is not affected.
    """
    if type(asyncio.get_running_loop()).__name__ == "ProactorEventLoop":
        logger.warning(
            "psycopg_needs_selector_event_loop",
            extra={"hint": "On Windows start uvicorn with --reload; the chat log will fail"},
        )
