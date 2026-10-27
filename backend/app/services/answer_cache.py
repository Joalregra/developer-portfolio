"""In-memory cache of answers to repeated questions.

A model call costs about 5,400 prompt tokens and a slice of a small free quota, so a question that
was already answered is served again without calling a model. The cache holds only answers the
output validator accepted, and only for questions asked without history: a follow-up depends on
what came before, so it is never stored or served from here.

It lives in the process, and `export` / `load` let the state file (services/state_store.py) carry
it across a restart. The key is a hash of the normalized question, so the visitor's text is never
kept: not in memory and not on disk. Entries age by wall-clock time, so the age also counts while
the process is down. The state file drops the whole cache when the knowledge changes. One API
container is enough for this; with several, each would keep its own copy.
"""

import hashlib
import re
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable
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


@dataclass(frozen=True, slots=True)
class CacheRecord:
    """One entry as the state file stores it: the question appears only as its hash."""

    locale: Locale
    key: str
    stored_at: float
    answer: CachedAnswer


def normalize_question(text: str) -> str:
    """Lowercase, one space between words and no marks at the edges. Inner words stay as written."""
    return _WHITESPACE.sub(" ", text).strip().casefold().strip(_EDGE_MARKS)


def question_key(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class AnswerCache:
    """Least recently used entries with an age limit. A `ttl_seconds` of 0 switches it off."""

    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_entries: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[tuple[Locale, str], tuple[float, CachedAnswer]] = OrderedDict()
        # Goes up on every change, so the state file knows whether there is something new to save.
        self.version = 0

    @property
    def enabled(self) -> bool:
        return self._ttl > 0

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, locale: Locale, question: str) -> CachedAnswer | None:
        if not self.enabled:
            return None
        key = (locale, question_key(normalize_question(question)))
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, answer = entry
        if self._clock() - stored_at >= self._ttl:
            del self._entries[key]
            self.version += 1
            return None
        self._entries.move_to_end(key)
        return answer

    def put(self, locale: Locale, question: str, answer: CachedAnswer) -> None:
        normalized = normalize_question(question)
        if not self.enabled or not normalized:
            return
        key = (locale, question_key(normalized))
        self._entries[key] = (self._clock(), answer)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
        self.version += 1

    def export(self) -> list[CacheRecord]:
        """Every live entry, oldest use first, for the state file."""
        now = self._clock()
        return [
            CacheRecord(locale, key, stored_at, answer)
            for (locale, key), (stored_at, answer) in self._entries.items()
            if now - stored_at < self._ttl
        ]

    def load(self, records: Iterable[CacheRecord]) -> int:
        """Add saved entries, skipping the expired ones. Returns how many were kept."""
        if not self.enabled:
            return 0
        now = self._clock()
        kept = 0
        for record in records:
            if now - record.stored_at >= self._ttl:
                continue
            self._entries[(record.locale, record.key)] = (record.stored_at, record.answer)
            kept += 1
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
        self.version += 1
        return kept
