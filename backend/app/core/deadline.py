"""A time budget shared by every step of one request (ERR-06).

Each step asks how much time is left and uses the smaller of that and its own limit, so the
sum of the steps can never go past the total.
"""

import time
from collections.abc import Callable


class Deadline:
    def __init__(self, seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._end = clock() + seconds

    def remaining(self) -> float:
        return max(0.0, self._end - self._clock())

    def cap(self, step_limit: float) -> float:
        """The time a step may use: its own limit, or what is left if that is smaller."""
        return min(step_limit, self.remaining())
