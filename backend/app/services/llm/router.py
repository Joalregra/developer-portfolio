"""Chooses which model answers: Groq first, Gemini if Groq cannot (LLM-06).

Policy, in short:
- One call to Groq at a time. The free tier lets about one question through per 40 seconds
  (8,000 tokens per minute against a 5,100-token prompt), so parallel calls would only collect
  429 errors. The lock is never held while waiting.
- 429: remember until when Groq asked us to wait, and wait for it if that fits the deadline
  (a few seconds when the fallback is ready, up to 20 without it). A visitor who arrives
  during that window does not call Groq at all. A spent daily quota pauses Groq instead.
- 5xx, timeout, connection error, or a prompt too large for the window: use the fallback.
- 400, 401, 403, 404: our bug or key. The fallback would not help, so stop.
- Invalid output: one more try with the same provider, except when the answer was cut short.
- The fallback is only used for visitors whose country is known and allowed (LLM-08).
This is the only place that retries (one retry layer).
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Final

from app.core.deadline import Deadline
from app.models.chat import LlmProvider
from app.services.budget import DailyBudget
from app.services.llm.base import (
    LLMProvider,
    ProviderError,
    ProviderOutputError,
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderResult,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)

# EU members, the other EEA countries, Switzerland and the United Kingdom, plus the territories
# that belong to them (Gibraltar, the Crown dependencies, Aland and the French overseas
# departments). Google's terms do not allow the free Gemini tier for apps that serve them.
RESTRICTED_COUNTRIES: Final = frozenset(
    [
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
        "IS",
        "LI",
        "NO",
        "CH",
        "GB",
        "GI",
        "GG",
        "JE",
        "IM",
        "AX",
        "RE",
        "GP",
        "MQ",
        "GF",
        "YT",
        "MF",
        "BL",
    ]
)
# How long a rate-limited call is worth waiting for. With a fallback ready, anything longer is
# faster to send there. Without one, waiting beats an error: the free Groq tier asks to retry in
# 13 to 16 seconds after each question.
MAX_WAIT_WITH_FALLBACK_SECONDS: Final = 5.0
MAX_WAIT_WITHOUT_FALLBACK_SECONDS: Final = 20.0
# Time that must remain to be worth starting another call.
MIN_TIME_FOR_ANOTHER_CALL: Final = 4.0
# Used when a 429 does not say how long to wait.
DEFAULT_RATE_WINDOW_SECONDS: Final = 15.0
DEFAULT_PAUSE_SECONDS: Final = 60.0
DEFAULT_DAILY_PAUSE_SECONDS: Final = 900.0
# Waiting for the lock longer than this is worth a log line.
QUEUE_WAIT_LOG_SECONDS: Final = 1.0
# Finish reasons that mean the answer was cut short (Groq says "length", Gemini "MAX_TOKENS").
CUT_OFF_REASONS: Final = frozenset({"length", "MAX_TOKENS"})


class NoProviderAvailableError(Exception):
    """Every allowed provider failed or none could be used."""

    def __init__(self, retry_after_seconds: float | None = None) -> None:
        super().__init__("no provider available")
        self.retry_after_seconds = retry_after_seconds


class LLMRouter:
    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider | None,
        budget: DailyBudget,
        *,
        primary_timeout: float,
        fallback_timeout: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.budget = budget
        self.primary_timeout = primary_timeout
        self.fallback_timeout = fallback_timeout
        self._clock = clock
        self._sleep = sleep
        self._paused_until: dict[LlmProvider, float] = {}
        self._rate_window_until = 0.0
        self._primary_gate = asyncio.Lock()

    async def complete(
        self, system: str, user: str, *, country: str | None, deadline: Deadline
    ) -> ProviderResult:
        """Return the model's answer.

        Raises:
            NoProviderAvailableError: No allowed provider answered in time.
            ProviderRequestError: Our request or key is wrong (do not retry).
            ProviderOutputError: The model gave an invalid answer twice, or was cut short.
            BudgetExhaustedError: Today's model calls are all used.
        """
        retry_hint: float | None = None
        if not self._is_paused(self.primary):
            try:
                return await self._use_primary(system, user, country, deadline)
            except ProviderRateLimitedError as exc:
                retry_hint = exc.retry_after_seconds
            except ProviderUnavailableError:
                pass
        return await self._use_fallback(system, user, country, deadline, retry_hint)

    async def _use_primary(
        self, system: str, user: str, country: str | None, deadline: Deadline
    ) -> ProviderResult:
        max_wait = (
            MAX_WAIT_WITH_FALLBACK_SECONDS
            if self._fallback_usable(country)
            else MAX_WAIT_WITHOUT_FALLBACK_SECONDS
        )
        while True:
            await self._wait_for_rate_window(deadline, max_wait)
            if (result := await self._try_primary(system, user, deadline)) is not None:
                return result
            # Groq asked us to wait: the loop checks whether that still fits the deadline.

    async def _try_primary(
        self, system: str, user: str, deadline: Deadline
    ) -> ProviderResult | None:
        """One call to the main provider, or None if it answered 429 for a short while."""
        queued_at = self._clock()
        async with self._primary_gate:
            self._log_queue_wait(self._clock() - queued_at)
            if deadline.remaining() < MIN_TIME_FOR_ANOTHER_CALL:
                raise ProviderUnavailableError("no time left after queueing")
            try:
                return await self._call(self.primary, system, user, deadline, self.primary_timeout)
            except ProviderRateLimitedError as exc:
                if exc.daily_quota:
                    raise
                window = exc.retry_after_seconds or DEFAULT_RATE_WINDOW_SECONDS
                self._rate_window_until = self._clock() + window
                return None

    async def _wait_for_rate_window(self, deadline: Deadline, max_wait: float) -> None:
        """Sleep until Groq's last 429 window ends, or raise if that is not worth the time."""
        wait = self._rate_window_until - self._clock()
        if wait <= 0:
            return
        if wait > max_wait or deadline.remaining() <= wait + MIN_TIME_FOR_ANOTHER_CALL:
            raise ProviderRateLimitedError(wait, daily_quota=False)
        await self._sleep(wait)

    async def _use_fallback(
        self,
        system: str,
        user: str,
        country: str | None,
        deadline: Deadline,
        retry_hint: float | None,
    ) -> ProviderResult:
        if self.fallback is None or not self._country_allowed(country):
            logger.warning("fallback_ineligible", extra={"country_known": country is not None})
            raise NoProviderAvailableError(retry_hint)
        if self._is_paused(self.fallback) or deadline.remaining() < MIN_TIME_FOR_ANOTHER_CALL:
            raise NoProviderAvailableError(retry_hint)
        try:
            return await self._call(self.fallback, system, user, deadline, self.fallback_timeout)
        except (ProviderRateLimitedError, ProviderUnavailableError) as exc:
            raise NoProviderAvailableError(retry_hint) from exc

    async def _call(
        self,
        provider: LLMProvider,
        system: str,
        user: str,
        deadline: Deadline,
        step_limit: float,
    ) -> ProviderResult:
        """One provider call, plus a single retry when the output was invalid."""
        attempts = 2
        for attempt in range(1, attempts + 1):
            self.budget.consume()
            try:
                return await provider.complete(system, user, deadline.cap(step_limit))
            except ProviderOutputError as exc:
                # A cut-off answer would be cut off again; any other invalid answer may not be.
                last_try = attempt == attempts or exc.finish_reason in CUT_OFF_REASONS
                self._log_failure(provider, exc)
                if last_try or deadline.remaining() < MIN_TIME_FOR_ANOTHER_CALL:
                    raise
            except ProviderRateLimitedError as exc:
                # A call refused for rate limit did no work and used no quota.
                self.budget.refund()
                self._log_failure(provider, exc)
                self._maybe_pause(provider, exc)
                raise
            except ProviderError as exc:
                self._log_failure(provider, exc)
                raise
        raise AssertionError("unreachable: the loop returns or raises")  # pragma: no cover

    def _maybe_pause(self, provider: LLMProvider, exc: ProviderRateLimitedError) -> None:
        """Cut a provider for everyone only when waiting a little would not help."""
        if exc.daily_quota:
            seconds = exc.retry_after_seconds or DEFAULT_DAILY_PAUSE_SECONDS
            self._pause(provider, seconds, "daily_quota")
        elif provider is self.fallback and exc.retry_after_seconds is None:
            # Gemini never says when to retry, so give it a rest instead of asking every time.
            self._pause(provider, DEFAULT_PAUSE_SECONDS, "no_retry_after")

    def _pause(self, provider: LLMProvider, seconds: float, reason: str) -> None:
        self._paused_until[provider.name] = self._clock() + seconds
        logger.warning(
            "provider_paused",
            extra={"provider": provider.name.value, "seconds": round(seconds), "reason": reason},
        )

    def _fallback_usable(self, country: str | None) -> bool:
        return (
            self.fallback is not None
            and self._country_allowed(country)
            and not self._is_paused(self.fallback)
        )

    def _is_paused(self, provider: LLMProvider) -> bool:
        until = self._paused_until.get(provider.name)
        return until is not None and self._clock() < until

    @staticmethod
    def _country_allowed(country: str | None) -> bool:
        # Unknown country: fail closed, because serving an excluded region breaks the terms.
        return country is not None and country.upper() not in RESTRICTED_COUNTRIES

    @staticmethod
    def _log_queue_wait(seconds: float) -> None:
        if seconds >= QUEUE_WAIT_LOG_SECONDS:
            logger.info("provider_queue_wait", extra={"wait_ms": round(seconds * 1000)})

    @staticmethod
    def _log_failure(provider: LLMProvider, exc: ProviderError) -> None:
        extra: dict[str, object] = {
            "provider": provider.name.value,
            "error": type(exc).__name__,
            "detail": str(exc),
        }
        if isinstance(exc, ProviderRateLimitedError):
            extra["retry_after"] = exc.retry_after_seconds
            extra["daily_quota"] = exc.daily_quota
        if isinstance(exc, ProviderRequestError):
            logger.error("provider_request_failed", extra=extra)
        else:
            logger.warning("provider_failed", extra=extra)
