"""Daily cap on calls to the language models, shared by every visitor (OWASP LLM10).

It keeps the Groq free-tier quota (1,000 requests per day) from being spent by one person.
The count lives in memory and resets at midnight UTC and on every restart. There is no await
between reading and writing it, so asyncio needs no lock here.
"""

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Final

logger = logging.getLogger(__name__)

# Share of the limit at which a warning is logged, once per day each.
WARNING_PERCENTS: Final = (50, 80, 100)


class BudgetExhaustedError(Exception):
    """The calls allowed for today are spent."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DailyBudget:
    def __init__(self, limit: int, clock: Callable[[], datetime] = _utc_now) -> None:
        self.limit = limit
        self._clock = clock
        self._day: date = clock().date()
        self._used = 0
        self._warned: set[int] = set()

    @property
    def used(self) -> int:
        self._roll_over()
        return self._used

    def consume(self) -> None:
        """Count one call to a provider.

        Raises:
            BudgetExhaustedError: Today's calls are all used.
        """
        self._roll_over()
        if self._used >= self.limit:
            raise BudgetExhaustedError
        self._used += 1
        self._warn()

    def refund(self) -> None:
        """Give back one call that did no work, such as one the provider refused with a 429."""
        self._roll_over()
        if self._used > 0:
            self._used -= 1

    def _roll_over(self) -> None:
        today = self._clock().date()
        if today != self._day:
            self._day = today
            self._used = 0
            self._warned.clear()

    def _warn(self) -> None:
        percent = self._used * 100 // self.limit
        for threshold in WARNING_PERCENTS:
            if percent >= threshold and threshold not in self._warned:
                self._warned.add(threshold)
                logger.warning(
                    "budget_used",
                    extra={"percent": threshold, "used": self._used, "limit": self.limit},
                )
