"""How the database engine is built for Neon and for the local SQLite used in tests."""

from app.db.session import (
    POOL_MAX_OVERFLOW,
    POOL_RECYCLE_SECONDS,
    POOL_SIZE,
    create_engine,
)

POSTGRES_URL = "postgresql+psycopg://portfolio_app:secret@db.example.com/portfolio?sslmode=require"


def test_the_postgres_pool_is_small_and_recycles_connections_before_neon_closes_them() -> None:
    engine = create_engine(POSTGRES_URL)

    pool = engine.sync_engine.pool
    assert (pool.size(), pool._max_overflow, pool._recycle) == (  # type: ignore[attr-defined]
        POOL_SIZE,
        POOL_MAX_OVERFLOW,
        POOL_RECYCLE_SECONDS,
    )
    # Neon suspends idle compute after about 5 minutes: recycle before that, not after.
    assert POOL_RECYCLE_SECONDS <= 300


def test_the_sqlite_engine_used_in_tests_gets_no_postgres_pool_options(tmp_path: object) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")

    assert engine.sync_engine.dialect.name == "sqlite"
