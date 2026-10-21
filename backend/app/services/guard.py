"""Checks on what the visitor wrote, before any model sees it (OWASP LLM01).

Three layers, from cheapest to most expensive: clean the text (normalize), look for known
attack phrases (detect_injection) and ask a classifier model (PromptGuard). None of them is
enough alone; they only make an attack more expensive. The real defence is that the assistant
has no tools, no secrets in its prompt and an output validator behind it.
"""

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Final, Protocol

from app.services.guard_patterns import (
    ENCODED_BLOCK,
    EXTRACTION_PATTERNS,
    JAILBREAK_PATTERNS,
    OVERRIDE_PATTERNS,
    SCRAMBLE_MIN_LENGTH,
    SCRAMBLE_TARGETS,
    SCRAMBLE_VERBS,
    SQUASHED_PHRASES,
)

logger = logging.getLogger(__name__)

MAX_REPEATED_CHARS: Final = 8
# Prompt Guard reads at most 512 tokens. Long texts are cut into overlapping pieces, so a long
# message cannot make the classifier fail by being too big, and an attack at a cut still shows.
CHUNK_CHARS: Final = 450
CHUNK_OVERLAP: Final = 100

# Letters that are not format characters but draw nothing (Hangul and Khmer fillers, braille
# blank). They split words without being visible.
_INVISIBLE_LETTERS: Final = frozenset({0x115F, 0x1160, 0x17B4, 0x17B5, 0x2800, 0x3164, 0xFFA0})
# Cyrillic and Greek letters that look like Latin ones, for matching the phrase list (code points,
# so the source has no look-alike characters).
_CONFUSABLES: Final = {
    **dict.fromkeys([0x430, 0x3B1], "a"),
    **dict.fromkeys([0x435, 0x3B5], "e"),
    **dict.fromkeys([0x43E, 0x3BF], "o"),
    **dict.fromkeys([0x440, 0x3C1], "p"),
    **dict.fromkeys([0x441], "c"),
    **dict.fromkeys([0x443, 0x3C5], "y"),
    **dict.fromkeys([0x445, 0x3C7], "x"),
    **dict.fromkeys([0x456, 0x3B9], "i"),
    **dict.fromkeys([0x455], "s"),
    **dict.fromkeys([0x458], "j"),
    **dict.fromkeys([0x43A, 0x3BA], "k"),
    **dict.fromkeys([0x43C], "m"),
    **dict.fromkeys([0x43D], "h"),
    **dict.fromkeys([0x442, 0x3C4], "t"),
    **dict.fromkeys([0x3BD], "v"),
}
MIN_PHONE_DIGITS: Final = 9

_REPEATS = re.compile(rf"(.)\1{{{MAX_REPEATED_CHARS},}}")
_SPACES = re.compile(r"\s+")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_WORD = re.compile(r"[a-z]+")
_NOT_LETTERS = re.compile(r"[^a-z]")


@dataclass(frozen=True, slots=True)
class GuardVerdict:
    blocked: bool
    # Short machine name of the rule that matched. Never the visitor's text.
    reason: str | None = None


class InjectionClassifier(Protocol):
    """Anything that scores how likely a text is an attack, from 0 to 1."""

    async def score(self, text: str, time_limit: float) -> float: ...


def strip_invisible(text: str) -> str:
    """NFKC, then remove what hides text from people and filters but not from models.

    Control and format characters (zero width spaces, the Unicode tag block, bidi marks) go.
    The blank filler letters become a space, because they usually stand in for one between
    words. Line breaks stay.
    """
    text = unicodedata.normalize("NFKC", text)
    kept = (
        char
        for char in text
        if char in "\n\t" or unicodedata.category(char) not in {"Cc", "Cf", "Cs", "Co", "Cn"}
    )
    return "".join(" " if ord(char) in _INVISIBLE_LETTERS else char for char in kept)


def normalize(text: str) -> str:
    """Make the text plain before it is checked or sent (PI-02)."""
    text = strip_invisible(text)
    text = _REPEATS.sub(lambda match: match.group(1) * MAX_REPEATED_CHARS, text)
    return _SPACES.sub(" ", text).strip()


def mask_personal_data(text: str) -> str:
    """Replace emails and phone numbers, so they are not sent to an outside provider (DATA-06)."""

    def phone(match: re.Match[str]) -> str:
        digits = sum(char.isdigit() for char in match.group())
        return "[phone]" if digits >= MIN_PHONE_DIGITS else match.group()

    return _PHONE.sub(phone, _EMAIL.sub("[email]", text))


def fold(text: str) -> str:
    """Lowercase, remove accents and swap look-alike Cyrillic or Greek letters for Latin ones."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    plain = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return plain.translate(_CONFUSABLES)


def detect_injection(text: str) -> GuardVerdict:
    """Look for known attack phrases. Cheap and local: no model, no network (PI-03)."""
    if ENCODED_BLOCK.search(text):
        return GuardVerdict(True, "encoded_block")
    folded = fold(text)
    for group in (OVERRIDE_PATTERNS, EXTRACTION_PATTERNS, JAILBREAK_PATTERNS):
        for name, pattern in group.items():
            if pattern.search(folded):
                return GuardVerdict(True, name)
    squashed = _NOT_LETTERS.sub("", folded)
    if any(phrase in squashed for phrase in SQUASHED_PHRASES):
        return GuardVerdict(True, "squashed_phrase")
    if _scrambled_attack(folded):
        return GuardVerdict(True, "scrambled_words")
    return GuardVerdict(False)


def _scrambled_attack(folded: str) -> bool:
    words = [word for word in _WORD.findall(folded) if len(word) >= SCRAMBLE_MIN_LENGTH]
    verbs = [_match_kind(word, SCRAMBLE_VERBS) for word in words]
    targets = [_match_kind(word, SCRAMBLE_TARGETS) for word in words]
    has_verb = any(kind is not None for kind in verbs)
    has_target = any(kind is not None for kind in targets)
    scrambled = any(kind == "scrambled" for kind in verbs + targets)
    return has_verb and has_target and scrambled


def _match_kind(word: str, candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if word == candidate:
            return "exact"
        if (
            len(word) == len(candidate)
            and word[0] == candidate[0]
            and word[-1] == candidate[-1]
            and sorted(word[1:-1]) == sorted(candidate[1:-1])
        ):
            return "scrambled"
    return None


class PromptGuard:
    """Asks a classifier model if a text is an attack. It fails open if the model is down.

    Failing open is a decision: a broken classifier must not take the whole assistant down,
    and the other layers (heuristics, output validator) still run. Each failure is logged.
    """

    def __init__(
        self, classifier: InjectionClassifier, threshold: float, time_limit: float
    ) -> None:
        self.classifier = classifier
        self.threshold = threshold
        self.time_limit = time_limit

    async def check(self, text: str) -> tuple[GuardVerdict, str]:
        """Return the verdict and a result label for the logs: ok, blocked or unavailable."""
        try:
            # One timeout for all pieces together: the SDK's own timeout is per phase.
            async with asyncio.timeout(self.time_limit):
                scores = await asyncio.gather(
                    *(self.classifier.score(piece, self.time_limit) for piece in _pieces(text))
                )
            score = max(scores)
        except Exception as exc:  # any failure here must fail open, never raise
            logger.warning("guard_unavailable", extra={"error": type(exc).__name__})
            return GuardVerdict(False), "unavailable"
        if score >= self.threshold:
            return GuardVerdict(True, "classifier"), "blocked"
        return GuardVerdict(False), "ok"


def _pieces(text: str) -> list[str]:
    if len(text) <= CHUNK_CHARS:
        return [text]
    step = CHUNK_CHARS - CHUNK_OVERLAP
    return [
        text[start : start + CHUNK_CHARS] for start in range(0, len(text) - CHUNK_OVERLAP, step)
    ]
