"""Loads the knowledge files once at startup. It does not call any model.

The English file feeds the system prompt (sections 1 to 8). The quick answers come from
section 9 of each file and are served without a model call. Section 0 is not used as a prompt:
the rules that matter live in code (prompt.py), where they are versioned and tested (LLM-10).
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.core.locale import Locale
from app.schemas.chat import QUICK_QUESTION_IDS, QuickQuestionId

ENGLISH_FILE: Final = "ChatbotKnowledge.en.md"
SPANISH_FILE: Final = "ChatbotKnowledge.es.md"

# The system prompt (rules plus knowledge) must fit the Groq free tier even with a cold cache:
# 8,000 tokens per minute for the prompt, the question, the history and the answer together.
MAX_SYSTEM_PROMPT_TOKENS: Final = 6000
# Rough estimate for English prose. The real count is read from the provider's usage and logged.
CHARS_PER_TOKEN: Final = 4

# Headings of section 9, one per quick question. If a heading is reworded the app refuses to
# start, instead of answering a button with the wrong text.
_HEADINGS: Final[dict[Locale, dict[QuickQuestionId, str]]] = {
    Locale.EN: {
        "projects": "What are your most important projects?",
        "stack": "Which technologies or stack do you know best?",
        "production": "Do you have experience with real or production projects?",
        "availability": "What is your availability, location and preferred work mode?",
        "challenge": "What was your hardest technical challenge?",
        "ai": "Do you use AI when programming?",
    },
    Locale.ES: {
        "projects": "¿Cuáles son tus proyectos más importantes?",
        "stack": "¿Qué tecnologías o stack dominas mejor?",
        "production": "¿Tienes experiencia en proyectos reales o de producción?",
        "availability": "¿Cuál es tu disponibilidad, ubicación y modalidad de trabajo preferida?",
        "challenge": "¿Cuál fue tu reto técnico más difícil?",
        "ai": "¿Usas IA al programar?",
    },
}

_SECTION = re.compile(r"(?m)^## (\d+)\. .*$")
_QUESTION = re.compile(r"(?m)^### Q: (.+)\nA: (.+)$")


class KnowledgeError(Exception):
    """A knowledge file is missing, incomplete or too big. Raised at startup only."""


@dataclass(frozen=True, slots=True)
class Knowledge:
    prompt_text: str
    version: str
    quick_answers: dict[Locale, dict[QuickQuestionId, str]]

    def quick_answer(self, question_id: QuickQuestionId, locale: Locale) -> str:
        return self.quick_answers[locale][question_id]

    @staticmethod
    def quick_question(question_id: QuickQuestionId, locale: Locale) -> str:
        """The text of the button, as it appears in the knowledge file."""
        return _HEADINGS[locale][question_id]


def load_knowledge(directory: Path) -> Knowledge:
    """Read both files and check them.

    Raises:
        KnowledgeError: A file is missing or empty, a quick question has no answer, or the
            knowledge is too big for the model limits.
    """
    texts = {
        Locale.EN: _read(directory / ENGLISH_FILE),
        Locale.ES: _read(directory / SPANISH_FILE),
    }
    quick_answers = {locale: _quick_answers(text, locale) for locale, text in texts.items()}
    prompt_text = _prompt_sections(texts[Locale.EN])

    digest = hashlib.sha256()
    for locale in (Locale.EN, Locale.ES):
        digest.update(texts[locale].encode("utf-8"))
    return Knowledge(
        prompt_text=prompt_text,
        version=digest.hexdigest()[:12],
        quick_answers=quick_answers,
    )


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def _read(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KnowledgeError(f"Cannot read the knowledge file {path.name}.") from exc
    if not text.strip():
        raise KnowledgeError(f"The knowledge file {path.name} is empty.")
    return text


def _prompt_sections(text: str) -> str:
    """Return sections 1 to 8: the facts. Section 0 (rules) and 9 (quick answers) are left out.

    Section 9 repeats facts that are already in sections 1 to 8, and it is served without a
    model call, so sending it would only spend tokens.
    """
    matches = list(_SECTION.finditer(text))
    wanted = [
        (match.start(), matches[index + 1].start() if index + 1 < len(matches) else len(text))
        for index, match in enumerate(matches)
        if 1 <= int(match.group(1)) <= 8
    ]
    if len(wanted) != 8:
        raise KnowledgeError("The English knowledge file must have sections 1 to 8.")
    return "\n\n".join(text[start:end].strip().removesuffix("---").strip() for start, end in wanted)


def _quick_answers(text: str, locale: Locale) -> dict[QuickQuestionId, str]:
    section_nine = text.split("## 9.", maxsplit=1)
    if len(section_nine) != 2:
        raise KnowledgeError(f"The {locale.value} knowledge file has no section 9.")
    by_question = {
        match.group(1).strip(): match.group(2).strip()
        for match in _QUESTION.finditer(section_nine[1])
    }
    answers: dict[QuickQuestionId, str] = {}
    for question_id in QUICK_QUESTION_IDS:
        heading = _HEADINGS[locale][question_id]
        if heading not in by_question:
            raise KnowledgeError(
                f"The {locale.value} file has no quick answer for '{question_id}' ({heading})."
            )
        answers[question_id] = by_question[heading]
    return answers
