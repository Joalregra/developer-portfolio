"""The contract every LLM provider fulfils, and the errors they raise (ARQ-03).

The router and the chat service depend on this protocol, never on the Groq or Gemini SDKs.
That is what lets the tests use fake providers instead of patching libraries.
"""

from dataclasses import dataclass
from typing import Protocol

from app.models.chat import LlmProvider
from app.schemas.chat import ModelAnswer


@dataclass(frozen=True, slots=True)
class ProviderResult:
    answer: ModelAnswer
    provider: LlmProvider
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None
    finish_reason: str | None = None


class LLMProvider(Protocol):
    name: LlmProvider

    async def complete(self, system: str, user: str, time_limit: float) -> ProviderResult:
        """Ask the model for a ModelAnswer.

        Raises:
            ProviderRateLimitedError: The provider asked us to slow down.
            ProviderUnavailableError: Down, too slow, or unreachable. Another provider may help.
            ProviderRequestError: Our request or key is wrong. Another provider will not help.
            ProviderOutputError: It answered, but not with a valid ModelAnswer.
        """
        ...


class ProviderError(Exception):
    """Base class. The message never includes the prompt or the visitor's text."""


class ProviderRateLimitedError(ProviderError):
    def __init__(self, retry_after_seconds: float | None, *, daily_quota: bool) -> None:
        super().__init__("provider rate limited")
        self.retry_after_seconds = retry_after_seconds
        # True when a per-day quota is spent. Waiting a few seconds will not help then.
        self.daily_quota = daily_quota


class ProviderUnavailableError(ProviderError):
    """5xx, timeout, connection failure or a request too large for the provider's window."""


class ProviderRequestError(ProviderError):
    """400, 401 or 403: a bug or a bad key on our side. Never retried, never failed over."""


class ProviderOutputError(ProviderError):
    def __init__(self, finish_reason: str | None, provider: LlmProvider) -> None:
        super().__init__("invalid model output")
        self.finish_reason = finish_reason
        self.provider = provider
