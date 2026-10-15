"""The Groq adapter, with a fake client: how SDK errors become our errors decides the failover."""

import json
from types import SimpleNamespace
from typing import Any, cast

import groq
import httpx
import pytest

from app.models.chat import LlmProvider
from app.services.llm.base import (
    ProviderOutputError,
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderUnavailableError,
)
from app.services.llm.groq_provider import GroqPromptGuard, GroqProvider

pytestmark = pytest.mark.anyio

REQUEST = httpx.Request("POST", "https://api.groq.test/v1/chat/completions")
ANSWER = {"on_topic": True, "answer": "Johan builds FastAPI backends.", "section": "projects"}


def response(status: int, retry_after: str | None = None) -> httpx.Response:
    headers = {"retry-after": retry_after} if retry_after else {}
    return httpx.Response(status, headers=headers, request=REQUEST)


def completion(content: str, finish: str = "stop", cached: int | None = 4800) -> Any:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish)],
        usage=SimpleNamespace(
            prompt_tokens=5100,
            completion_tokens=140,
            prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
        ),
    )


class FakeGroq:
    def __init__(self, outcome: Any) -> None:
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._outcome = outcome

    async def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def provider(outcome: Any) -> tuple[GroqProvider, FakeGroq]:
    fake = FakeGroq(outcome)
    return GroqProvider(
        cast("groq.AsyncGroq", fake), model="m", temperature=0.3, max_output_tokens=800
    ), fake


async def test_a_valid_answer_comes_back_with_token_counts() -> None:
    groq_provider, _ = provider(completion(json.dumps(ANSWER)))

    result = await groq_provider.complete("system", "user", 12)

    assert result.answer.answer == "Johan builds FastAPI backends."
    assert result.provider is LlmProvider.GROQ
    assert (result.prompt_tokens, result.completion_tokens, result.cached_tokens) == (
        5100,
        140,
        4800,
    )
    assert result.finish_reason == "stop"


async def test_the_request_asks_for_strict_json_and_hides_the_reasoning() -> None:
    groq_provider, fake = provider(completion(json.dumps(ANSWER)))

    await groq_provider.complete("the system text", "the user text", 7)

    sent = fake.calls[0]
    assert sent["messages"] == [
        {"role": "system", "content": "the system text"},
        {"role": "user", "content": "the user text"},
    ]
    assert sent["response_format"]["json_schema"]["strict"] is True
    assert sent["include_reasoning"] is False
    assert (sent["timeout"], sent["max_completion_tokens"], sent["temperature"]) == (7, 800, 0.3)


@pytest.mark.parametrize("finish", ["stop", "length"])
async def test_text_that_is_not_the_expected_json_is_an_output_error(finish: str) -> None:
    groq_provider, _ = provider(completion("Sure! Here you go: ...", finish=finish))

    with pytest.raises(ProviderOutputError) as caught:
        await groq_provider.complete("s", "u", 12)

    assert caught.value.finish_reason == finish
    assert caught.value.provider is LlmProvider.GROQ


async def test_json_with_the_wrong_shape_is_an_output_error() -> None:
    groq_provider, _ = provider(completion(json.dumps({**ANSWER, "section": "pets"})))

    with pytest.raises(ProviderOutputError):
        await groq_provider.complete("s", "u", 12)


def rate_limit(message: str, retry_after: str | None) -> groq.RateLimitError:
    return groq.RateLimitError(message, response=response(429, retry_after), body=None)


@pytest.mark.parametrize(
    ("message", "retry_after", "expected_wait", "daily"),
    [
        ("on tokens per minute (TPM): Limit 8000, Used 4896", "16", 16.0, False),
        ("on tokens per day (TPD): Limit 200000, Used 199900", "3600", 3600.0, True),
        ("on requests per day (RPD): Limit 1000", "7200", 7200.0, True),
        ("Something Groq reworded completely", "5400", 5400.0, True),
        ("Something Groq reworded completely", "13", 13.0, False),
        ("on tokens per minute (TPM)", None, None, False),
        ("on tokens per minute (TPM)", "soon", None, False),
    ],
)
async def test_a_429_says_how_long_to_wait_and_whether_it_is_the_daily_quota(
    message: str, retry_after: str | None, expected_wait: float | None, daily: bool
) -> None:
    groq_provider, _ = provider(rate_limit(message, retry_after))

    with pytest.raises(ProviderRateLimitedError) as caught:
        await groq_provider.complete("s", "u", 12)

    assert caught.value.retry_after_seconds == expected_wait
    assert caught.value.daily_quota is daily


@pytest.mark.parametrize(
    "failure",
    [
        groq.InternalServerError("boom", response=response(500), body=None),
        groq.APIStatusError("too big", response=response(413), body=None),
        groq.APITimeoutError(request=REQUEST),
        groq.APIConnectionError(request=REQUEST),
    ],
    ids=["500", "413", "timeout", "connection"],
)
async def test_server_problems_and_oversized_prompts_allow_the_fallback(failure: Exception) -> None:
    groq_provider, _ = provider(failure)

    with pytest.raises(ProviderUnavailableError):
        await groq_provider.complete("s", "u", 12)


@pytest.mark.parametrize(
    "failure",
    [
        groq.BadRequestError("bad", response=response(400), body=None),
        groq.AuthenticationError("bad key gsk_secret", response=response(401), body=None),
        groq.PermissionDeniedError("blocked", response=response(403), body=None),
        groq.NotFoundError("model gone", response=response(404), body=None),
    ],
    ids=["400", "401", "403", "404"],
)
async def test_our_own_mistakes_do_not_allow_the_fallback_and_leak_nothing(
    failure: Exception,
) -> None:
    groq_provider, _ = provider(failure)

    with pytest.raises(ProviderRequestError) as caught:
        await groq_provider.complete("s", "u", 12)

    assert "gsk_secret" not in str(caught.value)


@pytest.mark.parametrize(("text", "score"), [("0.9995", 0.9995), ("0.0003", 0.0003)])
async def test_prompt_guard_reads_the_score(text: str, score: float) -> None:
    fake = FakeGroq(completion(text))
    guard = GroqPromptGuard(cast("groq.AsyncGroq", fake), model="guard")

    assert await guard.score("hello", 3) == pytest.approx(score)
    assert fake.calls[0]["timeout"] == 3


async def test_prompt_guard_refuses_to_guess_from_unexpected_text() -> None:
    guard = GroqPromptGuard(cast("groq.AsyncGroq", FakeGroq(completion("malicious"))), model="g")

    with pytest.raises(ValueError, match="could not convert"):
        await guard.score("hello", 3)
