"""Groq: the main provider, and the Prompt Guard classifier that runs on the same account.

The SDK is created with `max_retries=0`. By default it retries a 429 by itself and waits
silently, which hid long delays from the router. Retries are decided in one place only: the
router (rule: one retry layer).
"""

import logging
from typing import Any

import groq
from pydantic import ValidationError

from app.models.chat import LlmProvider
from app.schemas.chat import ModelAnswer
from app.services.llm.base import (
    ProviderOutputError,
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderResult,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)

_MODEL_SCHEMA = ModelAnswer.model_json_schema()
# A per-minute limit cannot ask for a longer wait than this.
MAX_MINUTE_WINDOW_SECONDS = 120.0


def create_client(api_key: str) -> groq.AsyncGroq:
    return groq.AsyncGroq(api_key=api_key, max_retries=0)


class GroqProvider:
    name = LlmProvider.GROQ

    def __init__(
        self, client: groq.AsyncGroq, *, model: str, temperature: float, max_output_tokens: int
    ) -> None:
        self.client = client
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    async def complete(self, system: str, user: str, time_limit: float) -> ProviderResult:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=self.temperature,
                max_completion_tokens=self.max_output_tokens,
                # Low effort keeps the answer fast, and the reasoning is never sent to the client.
                reasoning_effort="low",
                include_reasoning=False,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "model_answer",
                        "strict": True,
                        "schema": _MODEL_SCHEMA,
                    },
                },
                timeout=time_limit,
            )
        except groq.APIError as exc:
            raise _translate(exc) from exc

        choice = response.choices[0]
        usage = response.usage
        details = getattr(usage, "prompt_tokens_details", None)
        try:
            answer = ModelAnswer.model_validate_json(choice.message.content or "")
        except ValidationError as exc:
            raise ProviderOutputError(choice.finish_reason, self.name) from exc
        return ProviderResult(
            answer=answer,
            provider=self.name,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            cached_tokens=getattr(details, "cached_tokens", None),
            finish_reason=choice.finish_reason,
        )


class GroqPromptGuard:
    """Llama Prompt Guard 2 answers with one number from 0 to 1: how likely an attack it is."""

    def __init__(self, client: groq.AsyncGroq, *, model: str) -> None:
        self.client = client
        self.model = model

    async def score(self, text: str, time_limit: float) -> float:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": text}],
            timeout=time_limit,
        )
        return float(response.choices[0].message.content or "")


def _translate(exc: groq.APIError) -> Exception:
    """Map an SDK error to ours. Nothing from the request or the body is copied into it."""
    if isinstance(exc, groq.RateLimitError):
        return ProviderRateLimitedError(_retry_after(exc), daily_quota=_is_daily_quota(exc))
    if isinstance(exc, groq.APITimeoutError | groq.APIConnectionError | groq.InternalServerError):
        return ProviderUnavailableError(type(exc).__name__)
    if isinstance(exc, groq.APIStatusError):
        if exc.status_code == 413 or exc.status_code >= 500:
            # 413 means the prompt does not fit the free-tier window right now.
            return ProviderUnavailableError(f"status {exc.status_code}")
        return ProviderRequestError(f"status {exc.status_code}")
    return ProviderUnavailableError(type(exc).__name__)


def _retry_after(exc: groq.RateLimitError) -> float | None:
    value: Any = exc.response.headers.get("retry-after")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_daily_quota(exc: groq.RateLimitError) -> bool:
    """Tell a per-day quota from a per-minute one.

    Groq names the quota in the error text ("... on tokens per day (TPD) ..."). The text can be
    reworded, so a wait of several minutes also counts: no per-minute window lasts that long.
    """
    if "per day" in str(exc.message).lower():
        return True
    wait = _retry_after(exc)
    return wait is not None and wait > MAX_MINUTE_WINDOW_SECONDS
