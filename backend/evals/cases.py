"""The evaluation cases (rule PI-15) and how they are read.

Each case is one visitor message. `attack` cases try to make the assistant break its rules;
`legit` cases are what a recruiter really asks. The cases file is plain JSON so it can be read
and extended without touching code.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.locale import Locale
from app.schemas.chat import ChatRequest, ChatTurn

CASES_FILE = Path(__file__).resolve().parent / "cases.json"


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["attack", "legit"]
    category: str
    locale: Locale
    message: str
    history: list[ChatTurn] = Field(default_factory=list)
    # Attacks only. "refuse": the assistant should refuse. "any": the message also holds a real
    # question, so answering it on topic is fine and only the checks below apply.
    expect: Literal["refuse", "any"] = "refuse"
    # Words that prove the assistant went along with the attack (case insensitive).
    must_not_contain: list[str] = Field(default_factory=list)
    # Legit only: a good answer holds at least one of these (case insensitive).
    expect_any: list[str] = Field(default_factory=list)

    def to_request(self) -> ChatRequest:
        return ChatRequest(message=self.message, locale=self.locale, history=self.history)


def load_cases(path: Path = CASES_FILE) -> list[EvalCase]:
    """Read the cases file. Ids must be unique, because results and resuming refer to them."""
    cases = [EvalCase.model_validate(item) for item in json.loads(path.read_text("utf-8"))]
    ids = [case.id for case in cases]
    duplicated = sorted({id_ for id_ in ids if ids.count(id_) > 1})
    if duplicated:
        raise ValueError(f"Duplicated case ids: {', '.join(duplicated)}")
    return cases
