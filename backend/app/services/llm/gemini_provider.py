"""Gemini: the fallback provider. Only used for visitors outside the EU, EEA, UK and Switzerland
(the free tier terms do not allow serving those regions; the router enforces it)."""

import asyncio

import httpx
from google import genai
from google.genai import errors, types
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

_MODEL_SCHEMA = ModelAnswer.model_json_schema()
_RATE_LIMITED = 429
_SERVER_ERROR = 500


def create_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


class GeminiProvider:
    name = LlmProvider.GEMINI

    def __init__(
        self, client: genai.Client, *, model: str, temperature: float, max_output_tokens: int
    ) -> None:
        self.client = client
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    async def complete(self, system: str, user: str, time_limit: float) -> ProviderResult:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            response_mime_type="application/json",
            response_json_schema=_MODEL_SCHEMA,
        )
        try:
            # The SDK has its own timeout setting, but this one also covers the connection.
            async with asyncio.timeout(time_limit):
                response = await self.client.aio.models.generate_content(
                    model=self.model, contents=user, config=config
                )
        except TimeoutError as exc:
            raise ProviderUnavailableError("timeout") from exc
        except errors.APIError as exc:
            raise _translate(exc) from exc
        except httpx.HTTPError as exc:
            # The SDK does not wrap network failures (a connection reset, "server disconnected").
            # Only the type is kept: the message can echo the request.
            raise ProviderUnavailableError(type(exc).__name__) from exc

        candidate = response.candidates[0] if response.candidates else None
        finish = candidate.finish_reason.name if candidate and candidate.finish_reason else None
        try:
            answer = ModelAnswer.model_validate_json(response.text or "")
        except ValidationError as exc:
            raise ProviderOutputError(finish, self.name) from exc
        usage = response.usage_metadata
        return ProviderResult(
            answer=answer,
            provider=self.name,
            prompt_tokens=usage.prompt_token_count if usage else None,
            completion_tokens=usage.candidates_token_count if usage else None,
            cached_tokens=usage.cached_content_token_count if usage else None,
            finish_reason=finish,
        )


def _translate(exc: errors.APIError) -> Exception:
    """Map an SDK error to ours, without copying its text (it can echo the request)."""
    code = exc.code or 0
    if code == _RATE_LIMITED:
        # Gemini sends no retry-after and no way to tell minute from day quotas, so the router
        # pauses it for a default time.
        return ProviderRateLimitedError(None, daily_quota=False)
    if code >= _SERVER_ERROR or code == 0:
        return ProviderUnavailableError(f"status {code}")
    return ProviderRequestError(f"status {code}")
