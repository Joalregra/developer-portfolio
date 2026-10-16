"""Command that applies the retention period to the chat log (rule DATA-06).

    python -m app.jobs.purge_chat_log

Run it once a day (cron on the server, see the README). It connects as the retention user
(RETENTION_DATABASE_URL), the only one allowed to delete, and exits with 0 on success and 1 on any
failure, so cron or a monitor can tell. It logs how many rows it deleted, never what they said.
"""

import asyncio
import logging
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import create_engine, create_session_factory
from app.services.retention import purge_expired_messages

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_FAILED = 1


async def run(settings: Settings) -> int:
    """Purge once and return the exit code."""
    if settings.retention_database_url is None:
        logger.error("retention_database_url_not_set")
        return EXIT_FAILED
    engine = create_engine(settings.retention_database_url.get_secret_value())
    try:
        deleted = await purge_expired_messages(
            create_session_factory(engine), retention_days=settings.chat_log_retention_days
        )
    except SQLAlchemyError as exc:
        # Only the error type: the text of the exception can carry the SQL parameters.
        logger.error("chat_log_purge_failed", extra={"error": type(exc).__name__})
        return EXIT_FAILED
    finally:
        await engine.dispose()
    logger.info(
        "chat_log_purged",
        extra={"deleted": deleted, "retention_days": settings.chat_log_retention_days},
    )
    return EXIT_OK


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    # psycopg in async mode needs the selector loop; Windows defaults to another one.
    return asyncio.run(run(settings), loop_factory=asyncio.SelectorEventLoop)


if __name__ == "__main__":
    sys.exit(main())
