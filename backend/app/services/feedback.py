"""Records a visitor's rating of an answer (helpful or not).

Rating is optional and secondary: a failure here must never touch the chat, and a repeated rating
is not an error. The database holds the rules: one rating per message (UNIQUE) and the message
must exist (foreign key).
"""

import logging
from typing import Final, Self

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import FeedbackUnavailableError, MessageNotFoundError, RateLimitedError
from app.db.repositories import FeedbackRepository
from app.schemas.chat import FeedbackRequest
from app.services.rate_limit import RateLimiter, RateLimitExceededError

logger = logging.getLogger(__name__)

# Looser than the chat: a rating costs no model call. These only stop a script from filling
# the table.
FEEDBACK_PER_MINUTE: Final = 20
FEEDBACK_PER_DAY: Final = 200


class FeedbackService:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession] | None, rate_limiter: RateLimiter
    ) -> None:
        self._session_factory = session_factory
        self._rate_limiter = rate_limiter

    @classmethod
    def with_default_limits(cls, session_factory: async_sessionmaker[AsyncSession] | None) -> Self:
        return cls(session_factory, RateLimiter(FEEDBACK_PER_MINUTE, FEEDBACK_PER_DAY))

    async def record(self, request: FeedbackRequest, client_key: str) -> None:
        """Store the rating of one answer. Rating the same answer again is accepted and ignored.

        Raises:
            RateLimitedError: This visitor sent too many ratings.
            FeedbackUnavailableError: There is no database, or it failed.
            MessageNotFoundError: No message with this id is in the log.
        """
        try:
            self._rate_limiter.check(client_key)
        except RateLimitExceededError as exc:
            raise RateLimitedError(exc.retry_after_seconds, locale=request.locale) from exc
        if self._session_factory is None:
            raise FeedbackUnavailableError(locale=request.locale)

        try:
            async with self._session_factory() as session:
                repository = FeedbackRepository(session)
                if not await repository.message_exists(request.message_id):
                    raise MessageNotFoundError(locale=request.locale)
                stored = await repository.add_if_absent(request.message_id, helpful=request.helpful)
        except IntegrityError as exc:
            # The message was deleted between the check and the insert.
            raise MessageNotFoundError(locale=request.locale) from exc
        except SQLAlchemyError as exc:
            # Only the error type: the text of the exception can carry the SQL parameters.
            logger.error("feedback_failed", extra={"error": type(exc).__name__})
            raise FeedbackUnavailableError(locale=request.locale) from exc
        logger.info(
            "feedback_recorded", extra={"helpful": request.helpful, "duplicate": not stored}
        )
