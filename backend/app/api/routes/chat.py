"""Chat endpoints. Thin: they hand the request to a service and return its result."""

from fastapi import APIRouter, status

from app.api.deps import ChatServiceDep, ClientKeyDep, CountryDep, FeedbackServiceDep
from app.core.errors import AssistantPausedError, ErrorResponse, FeedbackUnavailableError
from app.schemas.chat import ChatRequest, ChatResponse, FeedbackRequest

router = APIRouter(prefix="/api", tags=["chat"])


@router.post(
    "/chat",
    summary="Ask the assistant a question about Johan",
    description=(
        "Answers questions about Johan's professional profile, and nothing else. Off-topic "
        "questions and attempts to manipulate the assistant get a fixed refusal with "
        "`refused: true` (still HTTP 200). Quick-question ids are answered without a model."
    ),
    responses={
        422: {"model": ErrorResponse, "description": "Invalid request body."},
        429: {"model": ErrorResponse, "description": "Too many requests. See `Retry-After`."},
        502: {"model": ErrorResponse, "description": "The model gave an unusable answer."},
        503: {"model": ErrorResponse, "description": "Paused, or no model is available."},
    },
)
async def ask(
    body: ChatRequest, service: ChatServiceDep, client_key: ClientKeyDep, country: CountryDep
) -> ChatResponse:
    if service is None:
        raise AssistantPausedError(locale=body.locale)
    return await service.answer(body, client_key, country)


@router.post(
    "/chat/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Rate an answer as helpful or not",
    description=(
        "One rating per answer. Sending it again, with the same value or the other one, answers "
        "204 and changes nothing. The `message_id` is the one the chat returned with the answer."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "No such message in the log."},
        422: {"model": ErrorResponse, "description": "Invalid request body."},
        429: {"model": ErrorResponse, "description": "Too many requests. See `Retry-After`."},
        503: {"model": ErrorResponse, "description": "The rating could not be stored."},
    },
)
async def rate_answer(
    body: FeedbackRequest, service: FeedbackServiceDep, client_key: ClientKeyDep
) -> None:
    if service is None:
        raise FeedbackUnavailableError(locale=body.locale)
    await service.record(body, client_key)
