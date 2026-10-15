"""Request and response bodies of the chat endpoint, and the shape asked from the model.

Visitor-facing text limits live here as constants, so the schema, the prompt builder and the
database constraints (models/chat.py) talk about the same numbers.
"""

from typing import Annotated, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.locale import Locale

MESSAGE_MAX_LENGTH = 1000
HISTORY_MAX_TURNS = 6

QuickQuestionId = Literal["projects", "stack", "production", "availability", "challenge", "ai"]
QUICK_QUESTION_IDS: tuple[QuickQuestionId, ...] = get_args(QuickQuestionId)

# Ids of the sections of the portfolio page, so the frontend can link to the right anchor.
ChatSection = Literal["projects", "experience", "about", "skills", "education", "contact"]
CHAT_SECTIONS: tuple[ChatSection, ...] = get_args(ChatSection)

_Text = Annotated[str, Field(min_length=1, max_length=MESSAGE_MAX_LENGTH)]


class ChatTurn(BaseModel):
    """One earlier message. The client sends it, so it is data from the visitor, not truth."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: _Text


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: _Text = Field(examples=["What kind of projects has Johan built?"])
    locale: Locale
    history: list[ChatTurn] = Field(default_factory=list, max_length=HISTORY_MAX_TURNS)
    quick_question_id: QuickQuestionId | None = Field(
        default=None, description="Set when the visitor tapped one of the quick-question buttons."
    )


class ChatResponse(BaseModel):
    answer: str
    refused: bool = Field(
        description="True when the question was off topic or looked like an attack."
    )
    section: ChatSection | None = Field(
        default=None, description="Section of the page the answer is based on, if any."
    )
    message_id: UUID = Field(description="Id of the logged message, for rating it later.")
    request_id: str


class ModelAnswer(BaseModel):
    """What the model must return. Flat on purpose: no $ref and no unions, so every provider
    accepts the schema (Gemini rejects references; Groq strict mode needs every field required).
    """

    model_config = ConfigDict(extra="forbid")

    on_topic: bool
    answer: str
    section: Literal["projects", "experience", "about", "skills", "education", "contact", "none"]
