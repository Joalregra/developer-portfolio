import asyncio
from dataclasses import replace

import pytest

from app.core.deadline import Deadline
from app.models.chat import LlmProvider
from app.services.budget import BudgetExhaustedError, DailyBudget
from app.services.llm.base import (
    ProviderOutputError,
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderResult,
    ProviderUnavailableError,
)
from app.services.llm.router import LLMRouter, NoProviderAvailableError
from tests.fakes import FakeClock, FakeDate, FakeProvider, answer_result

pytestmark = pytest.mark.anyio

GROQ = LlmProvider.GROQ
GEMINI = LlmProvider.GEMINI
DOWN = ProviderUnavailableError("status 503")


# A call to the fake providers reserves about this many tokens: the text is tiny, so the estimate
# is the output limit. A fake result really costs 5100 - 4800 + 120 = 420 (see answer_result).
RESERVATION = 102
MAX_OUTPUT_TOKENS = 100


class Setup:
    def __init__(
        self, primary: FakeProvider, fallback: FakeProvider | None, limit: int = 1_000_000
    ) -> None:
        self.clock = FakeClock()
        self.primary = primary
        self.fallback = fallback
        self.router = LLMRouter(
            primary,
            fallback,
            DailyBudget(limit, clock=FakeDate()),
            primary_timeout=12,
            fallback_timeout=15,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            clock=self.clock,
            sleep=self.clock.sleep,
        )

    async def ask(self, country: str | None = "CO", seconds: float = 25) -> ProviderResult:
        deadline = Deadline(seconds, clock=self.clock)
        return await self.router.complete("system", "user", country=country, deadline=deadline)


def setup(
    primary: list[ProviderResult | Exception],
    fallback: list[ProviderResult | Exception] | None = None,
    limit: int = 1_000_000,
) -> Setup:
    return Setup(
        FakeProvider(GROQ, *primary),
        FakeProvider(GEMINI, *fallback) if fallback is not None else None,
        limit,
    )


async def test_the_main_provider_answers() -> None:
    s = setup([answer_result()], [])

    result = await s.ask()

    assert result.provider is GROQ
    assert s.fallback is not None and s.fallback.calls == 0


@pytest.mark.parametrize(
    "failure",
    [DOWN, ProviderRateLimitedError(30, daily_quota=False)],
    ids=["unavailable", "long-rate-limit"],
)
async def test_the_fallback_answers_when_the_main_provider_cannot(failure: Exception) -> None:
    s = setup([failure], [answer_result(provider=GEMINI)])

    result = await s.ask(country="CO")

    assert result.provider is GEMINI


@pytest.mark.parametrize(
    "country", [None, "DE", "ES", "GB", "CH", "NO", "de", "RE", "GI", "JE", "IM", "AX", "GP"]
)
async def test_gemini_is_not_used_for_unknown_or_excluded_countries(country: str | None) -> None:
    s = setup([DOWN], [answer_result(provider=GEMINI)])

    with pytest.raises(NoProviderAvailableError):
        await s.ask(country=country)

    assert s.fallback is not None and s.fallback.calls == 0


@pytest.mark.parametrize("country", ["CO", "US", "BR", "MX"])
async def test_gemini_is_used_for_known_countries_outside_the_excluded_regions(
    country: str,
) -> None:
    s = setup([DOWN], [answer_result(provider=GEMINI)])

    assert (await s.ask(country=country)).provider is GEMINI


async def test_no_fallback_configured_means_no_provider() -> None:
    s = setup([DOWN], fallback=None)

    with pytest.raises(NoProviderAvailableError):
        await s.ask()


async def test_a_short_rate_limit_is_waited_out_on_the_main_provider() -> None:
    s = setup(
        [ProviderRateLimitedError(2, daily_quota=False), answer_result()],
        [],
    )

    result = await s.ask()

    assert result.provider is GROQ
    assert s.primary.calls == 2
    assert s.clock.now == 1002.0  # it slept the two seconds


async def test_a_short_rate_limit_is_not_waited_when_the_deadline_is_too_close() -> None:
    s = setup(
        [ProviderRateLimitedError(2, daily_quota=False)],
        [answer_result(provider=GEMINI)],
    )

    result = await s.ask(seconds=5)  # 2 s wait + 4 s for another call would not fit

    assert result.provider is GEMINI
    assert s.primary.calls == 1


async def test_a_minute_level_rate_limit_is_remembered_and_then_forgotten() -> None:
    s = setup(
        [ProviderRateLimitedError(30, daily_quota=False), answer_result()],
        [answer_result(provider=GEMINI), answer_result(provider=GEMINI)],
    )

    first = await s.ask()
    during = await s.ask()  # Groq said 30 s ago-ish: no point in asking again yet
    s.clock.advance(31)
    after = await s.ask()

    assert (first.provider, during.provider, after.provider) == (GEMINI, GEMINI, GROQ)
    assert s.primary.calls == 2  # the visitor in the middle never called Groq


async def test_a_spent_daily_quota_pauses_the_main_provider_until_it_resets() -> None:
    s = setup(
        [ProviderRateLimitedError(3600, daily_quota=True), answer_result()],
        [answer_result(provider=GEMINI), answer_result(provider=GEMINI)],
    )

    await s.ask()
    during_pause = await s.ask()
    s.clock.advance(3601)
    after_pause = await s.ask()

    assert during_pause.provider is GEMINI
    assert after_pause.provider is GROQ
    assert s.primary.calls == 2  # the second request never called Groq


async def test_a_request_error_stops_without_using_the_fallback() -> None:
    s = setup([ProviderRequestError("status 401")], [answer_result(provider=GEMINI)])

    with pytest.raises(ProviderRequestError):
        await s.ask()

    assert s.fallback is not None and s.fallback.calls == 0


async def test_invalid_output_is_retried_once_on_the_same_provider() -> None:
    s = setup([ProviderOutputError("stop", GROQ), answer_result()], [])

    result = await s.ask()

    assert result.provider is GROQ
    assert s.primary.calls == 2


async def test_invalid_output_twice_gives_up_without_the_fallback() -> None:
    s = setup(
        [ProviderOutputError("stop", GROQ), ProviderOutputError("stop", GROQ)],
        [answer_result(provider=GEMINI)],
    )

    with pytest.raises(ProviderOutputError):
        await s.ask()

    assert s.primary.calls == 2
    assert s.fallback is not None and s.fallback.calls == 0


@pytest.mark.parametrize("reason", ["length", "MAX_TOKENS"])
async def test_a_cut_off_answer_is_not_retried(reason: str) -> None:
    s = setup([ProviderOutputError(reason, GROQ)], [])

    with pytest.raises(ProviderOutputError):
        await s.ask()

    assert s.primary.calls == 1


async def test_both_providers_down_gives_no_provider() -> None:
    s = setup([DOWN], [DOWN])

    with pytest.raises(NoProviderAvailableError):
        await s.ask()


async def test_the_retry_hint_reaches_the_caller_when_nothing_can_answer() -> None:
    s = setup([ProviderRateLimitedError(30, daily_quota=False)], fallback=None)

    with pytest.raises(NoProviderAvailableError) as caught:
        await s.ask()

    assert caught.value.retry_after_seconds == 30


async def test_every_provider_call_spends_budget_and_an_empty_budget_stops_it() -> None:
    s = setup([DOWN], [answer_result(provider=GEMINI)], limit=RESERVATION + 50)

    with pytest.raises(BudgetExhaustedError):
        await s.ask()  # a failed Groq call keeps its reservation; Gemini no longer fits


async def test_each_call_gets_the_smaller_of_its_limit_and_the_time_left() -> None:
    s = setup([answer_result()], [])

    await s.ask(seconds=7)

    assert s.primary.time_limits == [7.0]  # the main limit is 12 s, but only 7 s remain


async def test_no_fallback_is_started_with_too_little_time_left() -> None:
    s = setup([DOWN], [answer_result(provider=GEMINI)])
    deadline = Deadline(25, clock=s.clock)
    s.clock.advance(22)  # 3 s left, under the 4 s needed to start another call

    with pytest.raises(NoProviderAvailableError):
        await s.router.complete("system", "user", country="CO", deadline=deadline)

    assert s.fallback is not None and s.fallback.calls == 0


async def test_only_one_call_to_the_main_provider_runs_at_a_time() -> None:
    s = setup([answer_result()] * 6, [])

    await asyncio.gather(s.ask(), s.ask(), s.ask())

    assert s.primary.calls == 3
    assert s.primary.max_in_flight == 1


async def test_two_visitors_at_once_both_get_an_answer_through_a_rate_limit() -> None:
    s = setup(
        [ProviderRateLimitedError(2, daily_quota=False), answer_result(), answer_result()], []
    )

    first, second = await asyncio.gather(s.ask(), s.ask())

    assert (first.provider, second.provider) == (GROQ, GROQ)
    assert s.primary.max_in_flight == 1


async def test_without_an_allowed_fallback_a_longer_rate_limit_is_waited_out() -> None:
    # The real Groq free tier answers 429 with retry-after 13 to 16 after each question.
    s = setup([ProviderRateLimitedError(15, daily_quota=False), answer_result()], [])

    result = await s.ask(country=None)

    assert result.provider is GROQ
    assert s.clock.now == 1015.0


async def test_with_a_fallback_ready_a_longer_rate_limit_goes_straight_to_it() -> None:
    s = setup(
        [ProviderRateLimitedError(15, daily_quota=False)],
        [answer_result(provider=GEMINI)],
    )

    result = await s.ask(country="CO")

    assert result.provider is GEMINI
    assert s.clock.now == 1000.0  # no time was spent waiting


async def test_a_rate_limit_longer_than_the_waiting_limit_fails_with_a_hint() -> None:
    s = setup([ProviderRateLimitedError(45, daily_quota=False)], [])

    with pytest.raises(NoProviderAvailableError) as caught:
        await s.ask(country=None)

    assert caught.value.retry_after_seconds == 45
    assert s.primary.calls == 1


async def test_a_rate_limit_is_waited_out_again_if_it_repeats() -> None:
    s = setup(
        [
            ProviderRateLimitedError(2, daily_quota=False),
            ProviderRateLimitedError(3, daily_quota=False),
            answer_result(),
        ],
        [],
    )

    result = await s.ask()

    assert result.provider is GROQ
    assert s.clock.now == 1005.0  # 2 s and then 3 s


async def test_a_rate_limit_without_a_retry_after_waits_a_default_time_and_pauses_nobody() -> None:
    s = setup([ProviderRateLimitedError(None, daily_quota=False), answer_result()], [])

    result = await s.ask(country=None)

    assert result.provider is GROQ
    assert s.clock.now == 1015.0


async def test_the_fallback_is_rested_when_it_never_says_when_to_retry() -> None:
    s = setup([DOWN, DOWN], [ProviderRateLimitedError(None, daily_quota=False)])

    with pytest.raises(NoProviderAvailableError):
        await s.ask(country="CO")
    with pytest.raises(NoProviderAvailableError):
        await s.ask(country="CO")

    assert s.fallback is not None and s.fallback.calls == 1  # the second visitor did not ask


async def test_a_call_refused_for_rate_limit_does_not_spend_budget() -> None:
    s = setup(
        [ProviderRateLimitedError(2, daily_quota=False), answer_result()],
        [],
        limit=RESERVATION + 50,
    )

    result = await s.ask()

    assert result.provider is GROQ  # without the refund the second call would be over budget
    assert s.router.budget.used == 420  # and only the real cost of the answer is counted


async def test_a_successful_call_settles_the_reservation_to_the_real_tokens() -> None:
    s = setup([answer_result()], [])

    await s.ask()

    # prompt 5100 - cached 4800 + completion 120: Groq does not count cached tokens in its quota
    assert s.router.budget.used == 420


async def test_a_cold_cache_call_is_counted_in_full() -> None:
    s = setup([answer_result(cached_tokens=None)], [])

    await s.ask()

    assert s.router.budget.used == 5100 + 120


async def test_a_result_without_usage_keeps_the_reservation() -> None:
    result = replace(answer_result(), prompt_tokens=None, completion_tokens=None)
    s = setup([result], [])

    await s.ask()

    assert s.router.budget.used == RESERVATION


async def test_a_provider_failure_keeps_the_reservation() -> None:
    s = setup([DOWN], fallback=None)

    with pytest.raises(NoProviderAvailableError):
        await s.ask()

    assert s.router.budget.used == RESERVATION


async def test_the_reservation_grows_with_the_size_of_the_prompt() -> None:
    s = setup([DOWN], fallback=None)

    with pytest.raises(NoProviderAvailableError):
        await s.router.complete(
            "s" * 4000, "u" * 400, country=None, deadline=Deadline(25, clock=s.clock)
        )

    assert s.router.budget.used == 1100 + MAX_OUTPUT_TOKENS


async def test_a_visitor_who_waited_in_line_past_the_deadline_is_not_sent_to_the_model() -> None:
    s = setup([answer_result(), answer_result()], [answer_result(provider=GEMINI)])
    deadline = Deadline(25, clock=s.clock)

    async def slow_first() -> None:
        async with s.router._primary_gate:
            s.clock.advance(22)  # someone ahead used almost all of this visitor's time

    await slow_first()

    with pytest.raises(NoProviderAvailableError):
        await s.router.complete("system", "user", country=None, deadline=deadline)

    assert s.primary.calls == 0
