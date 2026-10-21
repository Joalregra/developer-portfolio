"""Test doubles shared by the router, service and endpoint tests. No network, no SDKs."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.models.chat import LlmProvider
from app.schemas.chat import ModelAnswer
from app.services.llm.base import ProviderResult


class FakeClock:
    """A clock the test moves by hand. Works as a `time.monotonic` replacement."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    async def sleep(self, seconds: float) -> None:
        self.advance(seconds)


class FakeDate:
    """A UTC clock for DailyBudget."""

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


def answer_result(
    text: str = "Johan builds FastAPI backends.",
    *,
    provider: LlmProvider = LlmProvider.GROQ,
    on_topic: bool = True,
    section: str = "projects",
    cached_tokens: int | None = 4800,
    finish_reason: str = "stop",
) -> ProviderResult:
    return ProviderResult(
        answer=ModelAnswer.model_validate(
            {"on_topic": on_topic, "answer": text, "section": section}
        ),
        provider=provider,
        prompt_tokens=5100,
        completion_tokens=120,
        cached_tokens=cached_tokens,
        finish_reason=finish_reason,
    )


class FakeProvider:
    """Plays a list of outcomes: a ProviderResult is returned, an exception is raised."""

    def __init__(
        self,
        name: LlmProvider,
        *outcomes: ProviderResult | Exception,
        delay: Callable[[], object] | None = None,
    ) -> None:
        self.name = name
        self.outcomes = list(outcomes)
        self.calls = 0
        self.time_limits: list[float] = []
        self.systems: list[str] = []
        self.users: list[str] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def complete(self, system: str, user: str, time_limit: float) -> ProviderResult:
        self.calls += 1
        self.time_limits.append(time_limit)
        self.systems.append(system)
        self.users.append(user)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0)  # lets a second concurrent caller show up
            if not self.outcomes:
                raise AssertionError(f"{self.name} was called more times than the test planned")
            outcome = self.outcomes.pop(0)
        finally:
            self.in_flight -= 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class SlowProvider:
    """Never answers in time. Used to test the total deadline."""

    name = LlmProvider.GROQ

    async def complete(self, system: str, user: str, time_limit: float) -> ProviderResult:
        await asyncio.sleep(30)
        raise AssertionError("the deadline should have cut this call")


class FakeClassifier:
    def __init__(self, score: float | Exception = 0.0) -> None:
        self._score = score
        self.calls = 0

    async def score(self, text: str, time_limit: float) -> float:
        self.calls += 1
        if isinstance(self._score, Exception):
            raise self._score
        return self._score
