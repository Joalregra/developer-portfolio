"""Domain errors and their single translation to HTTP.

Services raise these exceptions and never import FastAPI (ARQ-02). `register_exception_handlers`
turns them, and FastAPI's own errors, into one stable JSON shape (ERR-01):
`{"error": {"code", "message", "request_id", "details"}}`.

Visitor-facing messages exist in Spanish and English. The frontend decides what to show from
`code`, which is stable and always English.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ClassVar

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.locale import Locale
from app.core.logging import request_id_var


def _messages(*, en: str, es: str) -> Mapping[Locale, str]:
    """Build an immutable per-language message table, so a subclass cannot change a parent's."""
    return MappingProxyType({Locale.EN: en, Locale.ES: es})


class AppError(Exception):
    """Base class for expected errors. Subclasses set the HTTP status, a code and messages."""

    status_code: ClassVar[int] = 500
    code: ClassVar[str] = "internal_error"
    messages: ClassVar[Mapping[Locale, str]] = _messages(
        en="Unexpected error.", es="Error inesperado."
    )

    def __init__(
        self,
        message: str | None = None,
        *,
        locale: Locale = Locale.EN,
        details: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.message = message or self.messages[locale]
        self.details = details
        self.headers = dict(headers or {})
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    messages = _messages(
        en="Resource not found.",
        es="Recurso no encontrado.",
    )


class MessageNotFoundError(NotFoundError):
    """A rating refers to a message that is not in the log: it never existed, was deleted after
    the retention period, or its row could not be written (the log is best effort)."""

    messages = _messages(
        en="That answer is no longer available to rate.",
        es="Esa respuesta ya no está disponible para valorar.",
    )


class InvalidRequestError(AppError):
    """The request is well formed but has nothing to answer, for example only invisible text."""

    status_code = 422
    code = "invalid_request"
    messages = _messages(
        en="The question is empty.",
        es="La pregunta está vacía.",
    )


class RateLimitedError(AppError):
    """One IP sent too many requests."""

    status_code = 429
    code = "rate_limited"
    messages = _messages(
        en="Too many questions. Please wait a moment and try again.",
        es="Demasiadas preguntas. Espera un momento e inténtalo de nuevo.",
    )

    def __init__(self, retry_after_seconds: int, *, locale: Locale = Locale.EN) -> None:
        super().__init__(locale=locale, headers={"Retry-After": str(retry_after_seconds)})


class AssistantPausedError(AppError):
    """The daily budget is spent or the kill switch is off."""

    status_code = 503
    code = "assistant_paused"
    messages = _messages(
        en="The assistant is paused for today. You can contact Johan by email.",
        es="El asistente está en pausa por hoy. Puedes escribirle a Johan por correo.",
    )


class AssistantUnavailableError(AppError):
    """Every LLM provider failed or timed out."""

    status_code = 503
    code = "assistant_unavailable"
    messages = _messages(
        en="The assistant is unavailable right now. You can contact Johan by email.",
        es="El asistente no está disponible ahora. Puedes escribirle a Johan por correo.",
    )


class FeedbackUnavailableError(AppError):
    """The rating could not be stored: no database, or it failed. The chat is not affected."""

    status_code = 503
    code = "feedback_unavailable"
    messages = _messages(
        en="Your rating could not be saved right now.",
        es="No se pudo guardar tu valoración ahora.",
    )


class InvalidModelOutputError(AppError):
    """The model answered, but twice in a row the answer failed validation."""

    status_code = 502
    code = "invalid_model_output"
    messages = _messages(
        en="The assistant could not produce a valid answer. Please try again.",
        es="El asistente no pudo generar una respuesta válida. Inténtalo de nuevo.",
    )


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: Any = None


class ErrorResponse(BaseModel):
    """Error schema, also used in `responses=` so it appears in /docs (ERR-07)."""

    error: ErrorBody


_HTTP_CODES = {
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build the one error response shape, tagged with the current request id."""
    body = ErrorResponse(
        error=ErrorBody(
            code=code, message=message, request_id=request_id_var.get(), details=details
        )
    )
    return JSONResponse(jsonable_encoder(body), status_code=status_code, headers=headers)


async def _handle_app_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):  # narrows the type; registered only for AppError
        raise exc
    return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def _handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    # Keep location, message and type; drop `input` so visitor text is not echoed back.
    details = [
        {"loc": err.get("loc"), "msg": err.get("msg"), "type": err.get("type")}
        for err in exc.errors()
    ]
    return error_response(422, "invalid_request", "The request is not valid.", details)


async def _handle_http_exception(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    code = _HTTP_CODES.get(exc.status_code, "http_error")
    return error_response(exc.status_code, code, str(exc.detail), headers=exc.headers)


def register_exception_handlers(app: FastAPI) -> None:
    """Install the handlers that give every error the same JSON shape."""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
