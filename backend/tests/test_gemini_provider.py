"""The Gemini adapter, with a fake client."""

import asyncio
import json
from types import SimpleNamespace
from typing import Any, cast

import pytest
from google import genai
from google.genai import errors

from app.models.chat import LlmProvider
from app.services.llm.base import (
    ProviderOutputError,
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderUnavailableError,
)
from app.services.llm.gemini_provider import GeminiProvider

pytestmark = pytest.mark.anyio

ANSWER = {"on_topic": True, "answer": "Johan uses PostgreSQL.", "section": "skills"}


def reply(text: str, finish: str = "STOP") -> Any:
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish))],
        usage_metadata=SimpleNamespace(
            prompt_token_count=5170, candidates_token_count=60, cached_content_token_count=1931
        ),
    )


class FakeGemini:
    def __init__(self, outcome: Any = None, delay: float = 0) -> None:
        self.configs: list[Any] = []
        self._outcome = outcome
        self._delay = delay
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, **kwargs: Any) -> Any:
        self.configs.append(kwargs["config"])
        await asyncio.sleep(self._delay)
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def provider(fake: FakeGemini) -> GeminiProvider:
    return GeminiProvider(
        cast("genai.Client", fake), model="gemini-test", temperature=0.3, max_output_tokens=800
    )


async def test_a_valid_answer_comes_back_with_token_counts() -> None:
    fake = FakeGemini(reply(json.dumps(ANSWER)))

    result = await provider(fake).complete("system text", "user text", 15)

    assert result.answer.answer == "Johan uses PostgreSQL."
    assert result.provider is LlmProvider.GEMINI
    assert (result.prompt_tokens, result.completion_tokens, result.cached_tokens) == (
        5170,
        60,
        1931,
    )
    assert result.finish_reason == "STOP"
    config = fake.configs[0]
    assert config.system_instruction == "system text"
    assert config.response_mime_type == "application/json"
    assert config.max_output_tokens == 800


@pytest.mark.parametrize("finish", ["STOP", "MAX_TOKENS"])
async def test_text_that_is_not_the_expected_json_is_an_output_error(finish: str) -> None:
    fake = FakeGemini(reply("not json at all", finish=finish))

    with pytest.raises(ProviderOutputError) as caught:
        await provider(fake).complete("s", "u", 15)

    assert caught.value.finish_reason == finish
    assert caught.value.provider is LlmProvider.GEMINI


async def test_a_429_has_no_retry_time_and_is_not_assumed_to_be_daily() -> None:
    fake = FakeGemini(errors.ClientError(429, {"error": {"message": "quota"}}, None))

    with pytest.raises(ProviderRateLimitedError) as caught:
        await provider(fake).complete("s", "u", 15)

    assert (caught.value.retry_after_seconds, caught.value.daily_quota) == (None, False)


async def test_a_server_error_is_unavailable() -> None:
    fake = FakeGemini(errors.ServerError(503, {"error": {"message": "overloaded"}}, None))

    with pytest.raises(ProviderUnavailableError):
        await provider(fake).complete("s", "u", 15)


async def test_a_bad_request_or_key_is_our_mistake_and_leaks_nothing() -> None:
    fake = FakeGemini(
        errors.ClientError(403, {"error": {"message": "key AIzaSecret blocked"}}, None)
    )

    with pytest.raises(ProviderRequestError) as caught:
        await provider(fake).complete("s", "u", 15)

    assert "AIzaSecret" not in str(caught.value)


async def test_a_call_that_takes_too_long_is_unavailable() -> None:
    fake = FakeGemini(reply(json.dumps(ANSWER)), delay=5)

    with pytest.raises(ProviderUnavailableError, match="timeout"):
        await provider(fake).complete("s", "u", 0.05)
