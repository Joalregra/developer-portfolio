"""Chat endpoint. Thin: it hands the question to ChatService and returns the answer."""

from fastapi import APIRouter

from app.api.deps import ChatServiceDep, ClientKeyDep, CountryDep
from app.core.errors import AssistantPausedError, ErrorResponse
from app.schemas.chat import ChatRequest, ChatResponse

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
