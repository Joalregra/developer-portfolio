"""Daily cap on the tokens spent on the language models, shared by every visitor (OWASP LLM10).

Groq's free tier is measured in tokens (about 200,000 a day), not in calls, so the budget counts
tokens. A call reserves an estimate before it starts and settles to the real usage afterwards.
The count resets at midnight UTC. It is kept in memory, and `export` / `restore` let the state
file carry it across a restart (services/state_store.py). There is no await between reading and
writing it, so asyncio needs no lock here.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Final

logger = logging.getLogger(__name__)

# Share of the limit at which a warning is logged, once per day each.
WARNING_PERCENTS: Final = (50, 80, 100)


class BudgetExhaustedError(Exception):
    """The tokens allowed for today are spent."""


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    day: date
    used_tokens: int
    warned: frozenset[int]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DailyBudget:
    def __init__(self, limit: int, clock: Callable[[], datetime] = _utc_now) -> None:
        self.limit = limit
        self._clock = clock
        self._day: date = clock().date()
        self._used = 0
        self._warned: set[int] = set()
        # Goes up on every change, so the state file knows whether there is something new to save.
        self.version = 0

    @property
    def used(self) -> int:
        self._roll_over()
        return self._used

    def reserve(self, estimate: int) -> int:
        """Set aside `estimate` tokens for a call about to start. Returns what was reserved.

        Raises:
            BudgetExhaustedError: The estimate does not fit in what is left of today.
        """
        self._roll_over()
        if self._used + estimate > self.limit:
            raise BudgetExhaustedError
        self._used += estimate
        self._changed()
        return estimate

    def settle(self, reserved: int, actual: int) -> None:
        """Replace a reservation with the tokens the call really used."""
        self._roll_over()
        self._used = max(0, self._used - reserved + actual)
        self._changed()

    def refund(self, reserved: int) -> None:
        """Give back a reservation for a call that did no work, such as one refused with a 429."""
        self._roll_over()
        self._used = max(0, self._used - reserved)
        self._changed()

    def export(self) -> BudgetSnapshot:
        self._roll_over()
        return BudgetSnapshot(self._day, self._used, frozenset(self._warned))

    def restore(self, snapshot: BudgetSnapshot) -> bool:
        """Load a saved count. Only today's is taken: yesterday's quota is already over."""
        self._roll_over()
        if snapshot.day != self._day:
            return False
        self._used = max(0, snapshot.used_tokens)
        self._warned = {p for p in snapshot.warned if p in WARNING_PERCENTS}
        self._changed()
        return True

    def _roll_over(self) -> None:
        today = self._clock().date()
        if today != self._day:
            self._day = today
            self._used = 0
            self._warned.clear()
            self.version += 1

    def _changed(self) -> None:
        self.version += 1
        percent = self._used * 100 // self.limit
        for threshold in WARNING_PERCENTS:
            if percent >= threshold and threshold not in self._warned:
                self._warned.add(threshold)
                logger.warning(
                    "budget_used",
                    extra={"percent": threshold, "used": self._used, "limit": self.limit},
                )
