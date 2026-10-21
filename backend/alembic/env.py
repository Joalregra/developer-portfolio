"""Alembic environment. The database URL comes from the app settings, never from alembic.ini.

Migrations run with the owner user (`MIGRATION_DATABASE_URL`). The app user cannot change the
schema, by design (DATA-07).
"""

import asyncio
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.db.base import Base
from app.models import chat  # noqa: F401 - import every model module so autogenerate sees it

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# `alembic upgrade head --sql` only needs the dialect to render PostgreSQL statements.
OFFLINE_DIALECT_URL = "postgresql+psycopg://"


def get_database_url() -> str:
    settings = get_settings()
    url = settings.migration_database_url or settings.database_url
    if url is not None:
        return url.get_secret_value()
    if context.is_offline_mode():
        return OFFLINE_DIALECT_URL
    raise RuntimeError("Set MIGRATION_DATABASE_URL (or DATABASE_URL) to run migrations.")


# `%` is escaped because alembic.ini values go through configparser interpolation.
config.set_main_option("sqlalchemy.url", get_database_url().replace("%", "%%"))


def run_migrations_offline() -> None:
    """Render the migration as SQL without connecting to a database."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # compare_* make `alembic check` notice changed types and server defaults. It still cannot
    # compare CHECK constraints, so the SQL file and migration 0001 are compared by hand.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    # psycopg in async mode cannot use the proactor loop that asyncio picks on Windows.
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(run_async_migrations(), loop_factory=loop_factory)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
