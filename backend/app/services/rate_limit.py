"""Per-visitor request limits, kept in memory for one process (OWASP LLM10, rules PI-12, PI-13).

There is no await between reading and writing the counters, so asyncio needs no lock. A
restart resets everything, and several processes would each keep their own counters; both are
known limits of running one uvicorn process (ARQ-06).

Memory stays bounded: old entries are swept at most once a minute and the number of tracked
keys has a ceiling, so rotating addresses cannot grow the dictionaries forever.
"""

import ipaddress
import logging
import math
import time
from collections import deque
from collections.abc import Callable
from typing import Final

logger = logging.getLogger(__name__)

MINUTE: Final = 60.0
HOUR: Final = 3_600.0
DAY: Final = 86_400.0
SWEEP_EVERY_SECONDS: Final = 60.0
MAX_TRACKED_KEYS: Final = 50_000
IPV6_PREFIX_BITS: Final = 56


class RateLimitExceededError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


class ModelQuotaExceededError(Exception):
    """A visitor used up the questions they may send to a model. `window` is "hour" or "day"."""

    def __init__(self, retry_after_seconds: int, window: str) -> None:
        super().__init__("model quota exceeded")
        self.retry_after_seconds = retry_after_seconds
        self.window = window


def client_key(host: str) -> str:
    """Identify a visitor by address.

    A home or office usually gets a whole IPv6 block (a /56 or /48), not a single address, so
    all addresses of the same /56 count as one visitor: rotating inside it is useless.
    """
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    if isinstance(address, ipaddress.IPv6Address):
        # ::ffff:1.2.3.4 is an IPv4 visitor seen through an IPv6 socket, not an IPv6 network.
        address = address.ipv4_mapped or address
    if isinstance(address, ipaddress.IPv6Address):
        return str(
            ipaddress.ip_network(f"{address}/{IPV6_PREFIX_BITS}", strict=False).network_address
        )
    return str(address)


class RateLimiter:
    def __init__(
        self,
        per_minute: int,
        per_day: int,
        *,
        strike_limit: int = 3,
        strike_window_seconds: float = 600.0,
        block_seconds: float = 900.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.per_minute = per_minute
        self.per_day = per_day
        self.strike_limit = strike_limit
        self.strike_window = strike_window_seconds
        self.block_seconds = block_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._strikes: dict[str, deque[float]] = {}
        self._blocked_until: dict[str, float] = {}
        self._last_sweep = clock()

    def check(self, key: str) -> None:
        """Count one request from `key`.

        Raises:
            RateLimitExceededError: The key is blocked or used up its minute or day allowance.
        """
        now = self._clock()
        self._sweep(now)
        blocked_until = self._blocked_until.get(key)
        if blocked_until is not None and now < blocked_until:
            raise RateLimitExceededError(math.ceil(blocked_until - now))

        hits = self._hits.get(key)
        if hits is None:
            self._make_room()
            hits = self._hits[key] = deque()
        while hits and now - hits[0] >= DAY:
            hits.popleft()
        in_last_minute = [moment for moment in hits if now - moment < MINUTE]
        if len(in_last_minute) >= self.per_minute:
            raise RateLimitExceededError(math.ceil(MINUTE - (now - in_last_minute[0])))
        if len(hits) >= self.per_day:
            raise RateLimitExceededError(math.ceil(DAY - (now - hits[0])))
        hits.append(now)

    def add_strike(self, key: str) -> bool:
        """Note an attack attempt. Returns True if the key just got blocked (PI-13)."""
        now = self._clock()
        strikes = self._strikes.setdefault(key, deque())
        while strikes and now - strikes[0] >= self.strike_window:
            strikes.popleft()
        strikes.append(now)
        if len(strikes) < self.strike_limit:
            return False
        self._blocked_until[key] = now + self.block_seconds
        strikes.clear()
        logger.warning("ip_blocked", extra={"seconds": self.block_seconds, "reason": "strikes"})
        return True

    def stats(self) -> dict[str, int]:
        return {
            "tracked": len(self._hits),
            "strikes": len(self._strikes),
            "blocked": len(self._blocked_until),
        }

    def _make_room(self) -> None:
        if len(self._hits) >= MAX_TRACKED_KEYS:
            # Dicts keep insertion order, so the first key is the one seen longest ago.
            self._hits.pop(next(iter(self._hits)))

    def _sweep(self, now: float) -> None:
        if now - self._last_sweep < SWEEP_EVERY_SECONDS:
            return
        self._last_sweep = now
        self._hits = {k: v for k, v in self._hits.items() if v and now - v[-1] < DAY}
        self._strikes = {
            k: v for k, v in self._strikes.items() if v and now - v[-1] < self.strike_window
        }
        self._blocked_until = {k: t for k, t in self._blocked_until.items() if t > now}
        logger.info("limiter_stats", extra=self.stats())


class ModelQuota:
    """How many questions per hour and per day one visitor may send to a model.

    RateLimiter counts every request; this counts only the ones that would cost model tokens, so
    quick buttons, cached answers and refusals never reach it. Same rules as RateLimiter: sliding
    windows, injected clock, one sweep a minute, a ceiling on tracked keys. The counters stay in
    memory on purpose: no address is ever written to disk, and a restart gives everyone a fresh
    quota.
    """

    def __init__(
        self,
        per_hour: int,
        per_day: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.per_hour = per_hour
        self.per_day = per_day
        self._clock = clock
        self._calls: dict[str, deque[float]] = {}
        self._last_sweep = clock()

    def reserve(self, key: str) -> None:
        """Count one model question for `key`.

        Raises:
            ModelQuotaExceededError: The key used its hour or day allowance.
        """
        now = self._clock()
        self._sweep(now)
        calls = self._calls.get(key)
        if calls is None:
            self._make_room()
            calls = self._calls[key] = deque()
        while calls and now - calls[0] >= DAY:
            calls.popleft()
        in_last_hour = [moment for moment in calls if now - moment < HOUR]
        if len(in_last_hour) >= self.per_hour:
            raise ModelQuotaExceededError(math.ceil(HOUR - (now - in_last_hour[0])), "hour")
        if len(calls) >= self.per_day:
            raise ModelQuotaExceededError(math.ceil(DAY - (now - calls[0])), "day")
        calls.append(now)

    def release(self, key: str) -> None:
        """Give back the last reservation of `key`, for a question that failed through no fault
        of the visitor."""
        calls = self._calls.get(key)
        if calls:
            calls.pop()

    def _make_room(self) -> None:
        if len(self._calls) >= MAX_TRACKED_KEYS:
            self._calls.pop(next(iter(self._calls)))

    def _sweep(self, now: float) -> None:
        if now - self._last_sweep < SWEEP_EVERY_SECONDS:
            return
        self._last_sweep = now
        self._calls = {k: v for k, v in self._calls.items() if v and now - v[-1] < DAY}
