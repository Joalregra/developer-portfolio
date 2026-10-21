"""In-memory cache of answers to repeated questions.

A model call costs about 5,400 prompt tokens and a slice of a small free quota, so a question that
was already answered is served again without calling a model. The cache holds only answers the
output validator accepted, and only for questions asked without history: a follow-up depends on
what came before, so it is never stored or served from here.

It lives in the process: it is empty after a restart, which also drops it whenever the knowledge
changes, because the knowledge is only read at startup. One API container is enough for this; with
several, each would keep its own copy.
"""

import re
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from app.core.locale import Locale
from app.schemas.chat import ChatSection

_WHITESPACE: Final = re.compile(r"\s+")
# Marks around a question that do not change what it asks: "¿Qué stack usa?" and "que stack usa".
_EDGE_MARKS: Final = " ¿?¡!.,;:\"'()"


@dataclass(frozen=True, slots=True)
class CachedAnswer:
    text: str
    section: ChatSection | None


def normalize_question(text: str) -> str:
    """Lowercase, one space between words and no marks at the edges. Inner words stay as written."""
    return _WHITESPACE.sub(" ", text).strip().casefold().strip(_EDGE_MARKS)


class AnswerCache:
    """Least recently used entries with an age limit. A `ttl_seconds` of 0 switches it off."""

    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[tuple[Locale, str], tuple[float, CachedAnswer]] = OrderedDict()

    @property
    def enabled(self) -> bool:
        return self._ttl > 0

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, locale: Locale, question: str) -> CachedAnswer | None:
        if not self.enabled:
            return None
        key = (locale, normalize_question(question))
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, answer = entry
        if self._clock() - stored_at >= self._ttl:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return answer

    def put(self, locale: Locale, question: str, answer: CachedAnswer) -> None:
        normalized = normalize_question(question)
        if not self.enabled or not normalized:
            return
        key = (locale, normalized)
        self._entries[key] = (self._clock(), answer)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
