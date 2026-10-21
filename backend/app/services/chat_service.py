"""The whole life of one chat question, from the limits to the logged answer.

Every layer of defence is called from here, in a fixed order (backend brief, section 9):
switch, rate limit, quick answer, cleaning, heuristics, answer cache, classifier, budget, model,
output validation. Routes call this and nothing else. It raises domain errors and never
imports FastAPI.
"""

import asyncio
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from app.core.deadline import Deadline
from app.core.errors import (
    AssistantPausedError,
    AssistantUnavailableError,
    InvalidModelOutputError,
    InvalidRequestError,
    RateLimitedError,
)
from app.core.logging import request_id_var
from app.db.repositories import ChatLogEntry
from app.models.chat import ChatStatus, LlmProvider
from app.schemas.chat import ChatRequest, ChatResponse, ChatSection, ChatTurn, QuickQuestionId
from app.services.answer_cache import AnswerCache, CachedAnswer
from app.services.budget import BudgetExhaustedError
from app.services.chat_log_writer import ChatLogWriter
from app.services.guard import PromptGuard, detect_injection, mask_personal_data, normalize
from app.services.knowledge import Knowledge
from app.services.llm.base import ProviderOutputError, ProviderRequestError, ProviderResult
from app.services.llm.router import LLMRouter, NoProviderAvailableError
from app.services.output_validator import OutputValidator
from app.services.prompt import REFUSALS, build_user_message
from app.services.rate_limit import RateLimiter, RateLimitExceededError

logger = logging.getLogger(__name__)

_LEAK_REASON: Final = "leak"
_EMPTY_REASON: Final = "empty"


@dataclass(slots=True)
class _Exchange:
    """One question while it is being handled: what was asked, and since when."""

    request: ChatRequest
    question: str
    started: float
    guard_result: str = "skipped"


class ChatService:
    def __init__(
        self,
        *,
        enabled: bool,
        knowledge: Knowledge,
        system_prompt: str,
        router: LLMRouter,
        guard: PromptGuard | None,
        validator: OutputValidator,
        rate_limiter: RateLimiter,
        writer: ChatLogWriter,
        answer_cache: AnswerCache,
        request_timeout_seconds: float,
    ) -> None:
        self.enabled = enabled
        self.knowledge = knowledge
        self.system_prompt = system_prompt
        self.router = router
        self.guard = guard
        self.validator = validator
        self.rate_limiter = rate_limiter
        self.writer = writer
        self.answer_cache = answer_cache
        self.request_timeout = request_timeout_seconds

    async def answer(
        self, request: ChatRequest, client_key: str, country: str | None
    ) -> ChatResponse:
        """Answer one question.

        Raises:
            AssistantPausedError: The switch is off or today's model budget is spent.
            RateLimitedError: This visitor sent too many requests.
            InvalidRequestError: The question has no text left after cleaning.
            AssistantUnavailableError: No model could answer in time.
            InvalidModelOutputError: The model's answer was not usable, twice.
        """
        started = time.perf_counter()
        self._admit(request, client_key)
        question = mask_personal_data(normalize(request.message))
        if not question:
            raise InvalidRequestError(locale=request.locale)
        if request.quick_question_id is not None:
            return self._answer_quick(request, request.quick_question_id, started)

        exchange = _Exchange(request, question, started)
        history = [_clean_turn(turn) for turn in request.history if turn.role == "user"]
        if (refusal := self._screen_locally(exchange, history, client_key)) is not None:
            return refusal
        if (cached := self._from_cache(exchange)) is not None:
            return cached
        deadline = Deadline(self.request_timeout)
        if (refusal := await self._screen_with_classifier(exchange)) is not None:
            return refusal
        result = await self._ask_model(exchange, history, country, deadline)
        return self._respond(exchange, result)

    def _admit(self, request: ChatRequest, client_key: str) -> None:
        if not self.enabled:
            raise AssistantPausedError(locale=request.locale)
        try:
            self.rate_limiter.check(client_key)
        except RateLimitExceededError as exc:
            raise RateLimitedError(exc.retry_after_seconds, locale=request.locale) from exc

    def _answer_quick(
        self, request: ChatRequest, question_id: QuickQuestionId, started: float
    ) -> ChatResponse:
        """Serve a button's fixed answer. The stored question is the button's own text, never
        whatever the client sent next to the id."""
        locale = request.locale
        exchange = _Exchange(request, self.knowledge.quick_question(question_id, locale), started)
        return self._finish(
            exchange,
            ChatStatus.ANSWERED_QUICK,
            LlmProvider.NONE,
            text=self.knowledge.quick_answer(question_id, locale),
        )

    def _screen_locally(
        self, exchange: _Exchange, history: Sequence[ChatTurn], client_key: str
    ) -> ChatResponse | None:
        """Run the phrase list on the question and on what the visitor said before."""
        for text in (exchange.question, *(turn.content for turn in history)):
            verdict = detect_injection(text)
            if verdict.blocked:
                logger.warning("injection_attempt", extra={"reason": verdict.reason})
                self.rate_limiter.add_strike(client_key)
                return self._refuse(exchange, verdict.reason or "blocked")
        return None

    def _from_cache(self, exchange: _Exchange) -> ChatResponse | None:
        """Serve a repeated question without calling a model. A follow-up is never cached.

        This runs after the phrase list, so an attack is still refused and still adds a strike,
        and before the classifier: a question stored here already passed every check.
        """
        if exchange.request.history:
            return None
        hit = self.answer_cache.get(exchange.request.locale, exchange.question)
        if hit is None:
            return None
        return self._finish(
            exchange,
            ChatStatus.ANSWERED_CACHED,
            LlmProvider.NONE,
            text=hit.text,
            section=hit.section,
        )

    async def _screen_with_classifier(self, exchange: _Exchange) -> ChatResponse | None:
        if self.guard is None:
            return None
        verdict, exchange.guard_result = await self.guard.check(exchange.question)
        if verdict.blocked:
            # No strike: the classifier has more false positives than the phrase list.
            return self._refuse(exchange, "classifier")
        return None

    async def _ask_model(
        self,
        exchange: _Exchange,
        history: Sequence[ChatTurn],
        country: str | None,
        deadline: Deadline,
    ) -> ProviderResult:
        locale = exchange.request.locale
        user_message = build_user_message(exchange.question, history, locale)
        try:
            async with asyncio.timeout(deadline.remaining()):
                return await self.router.complete(
                    self.system_prompt, user_message, country=country, deadline=deadline
                )
        except BudgetExhaustedError as exc:
            raise AssistantPausedError(locale=locale) from exc
        except NoProviderAvailableError as exc:
            self._record(exchange, ChatStatus.PROVIDER_ERROR, LlmProvider.NONE)
            retry = exc.retry_after_seconds
            headers = {"Retry-After": str(int(retry))} if retry else None
            raise AssistantUnavailableError(locale=locale, headers=headers) from exc
        except ProviderRequestError as exc:
            # Our request or key is wrong (the router already logged it). The fallback would
            # not help, and it is a bug to fix.
            self._record(exchange, ChatStatus.PROVIDER_ERROR, LlmProvider.NONE)
            raise AssistantUnavailableError(locale=locale) from exc
        except ProviderOutputError as exc:
            self._record(exchange, ChatStatus.INVALID_OUTPUT, exc.provider)
            raise InvalidModelOutputError(locale=locale) from exc
        except TimeoutError as exc:
            logger.error("deadline_exceeded", extra={"stage": "model"})
            self._record(exchange, ChatStatus.PROVIDER_ERROR, LlmProvider.NONE)
            raise AssistantUnavailableError(locale=locale) from exc

    def _respond(self, exchange: _Exchange, result: ProviderResult) -> ChatResponse:
        """Check the model's answer and turn it into the response."""
        locale = exchange.request.locale
        validated = self.validator.validate(result.answer, locale)
        if validated.reason == _EMPTY_REASON:
            self._record(exchange, ChatStatus.INVALID_OUTPUT, result.provider)
            raise InvalidModelOutputError(locale=locale)
        if not validated.refused:
            status = ChatStatus.ANSWERED
        elif validated.reason == _LEAK_REASON:
            status = ChatStatus.REFUSED_INJECTION
        else:
            status = ChatStatus.REFUSED_OFF_TOPIC
        if status is ChatStatus.ANSWERED and not exchange.request.history:
            self.answer_cache.put(
                locale, exchange.question, CachedAnswer(validated.text, validated.section)
            )
        return self._finish(
            exchange,
            status,
            result.provider,
            text=validated.text,
            refused=validated.refused,
            section=validated.section,
            result=result,
        )

    def _refuse(self, exchange: _Exchange, reason: str) -> ChatResponse:
        exchange.guard_result = reason
        return self._finish(
            exchange,
            ChatStatus.REFUSED_INJECTION,
            LlmProvider.NONE,
            refused=True,
            text=REFUSALS[exchange.request.locale],
        )

    def _entry(
        self,
        exchange: _Exchange,
        status: ChatStatus,
        provider: LlmProvider,
        answer: str | None = None,
        result: ProviderResult | None = None,
    ) -> ChatLogEntry:
        return ChatLogEntry(
            locale=exchange.request.locale,
            question=exchange.question,
            answer=answer,
            status=status,
            provider=provider,
            latency_ms=_elapsed_ms(exchange.started),
            knowledge_version=self.knowledge.version,
            prompt_tokens=result.prompt_tokens if result else None,
            completion_tokens=result.completion_tokens if result else None,
            cached_tokens=result.cached_tokens if result else None,
        )

    def _record(self, exchange: _Exchange, status: ChatStatus, provider: LlmProvider) -> None:
        """Log a failed attempt. There is no response to build, so nothing else is done."""
        self.writer.submit(self._entry(exchange, status, provider))

    def _finish(
        self,
        exchange: _Exchange,
        status: ChatStatus,
        provider: LlmProvider,
        *,
        text: str,
        refused: bool = False,
        section: ChatSection | None = None,
        result: ProviderResult | None = None,
    ) -> ChatResponse:
        """Queue the database row, write the one log line and build the response."""
        # A refusal is fixed text, so only real answers are stored (smaller, nothing to review).
        entry = self._entry(exchange, status, provider, None if refused else text, result)
        self.writer.submit(entry)
        logger.info(
            "chat_completed",
            extra={
                "locale": exchange.request.locale.value,
                "status": status.value,
                "provider": provider.value,
                "latency_ms": entry.latency_ms,
                "prompt_tokens": entry.prompt_tokens,
                "cached_tokens": entry.cached_tokens,
                "cache_cold": provider is LlmProvider.GROQ and not entry.cached_tokens,
                "finish_reason": result.finish_reason if result else None,
                "guard_result": exchange.guard_result,
                "message_length": len(exchange.request.message),
            },
        )
        return ChatResponse(
            answer=text,
            refused=refused,
            section=section,
            message_id=entry.id,
            request_id=request_id_var.get(),
        )


def _clean_turn(turn: ChatTurn) -> ChatTurn:
    return ChatTurn(role=turn.role, content=mask_personal_data(normalize(turn.content)) or "-")


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
