"""Checks and cleans what the model answered, before the visitor sees it.

The model's text is untrusted (OWASP LLM05): it may carry a leaked prompt, a key, a link to a
phishing page or markup. Whatever fails a check is replaced by the fixed refusal written in
code (PI-08 to PI-11); the model never writes the refusal.
"""

import logging
import re
from dataclasses import dataclass
from typing import Final

from app.core.locale import Locale
from app.schemas.chat import ChatSection, ModelAnswer
from app.services.guard import strip_invisible
from app.services.prompt import CONTACT_EMAIL, GITHUB_URL, LINKEDIN_URL, REFUSALS

logger = logging.getLogger(__name__)

MAX_ANSWER_CHARS: Final = 1500
LEAK_WORDS: Final = 12
MAX_NUMBERED_LINES: Final = 2

_KEY_PATTERNS: Final = (
    re.compile(r"\bgsk_[A-Za-z0-9]{10,}"),  # Groq
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"),  # Google
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
_URL = re.compile(r"https?://[^\s<>\"'\]]+", re.IGNORECASE)
_MAILTO = re.compile(r"mailto:[^\s<>\"']+", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_NUMBERED_LINE = re.compile(r"(?m)^\s*\d+[.)]\s")
_WORD = re.compile(r"\w+", re.UNICODE)
_NON_ALNUM = re.compile(r"[^a-z0-9]")
_TRAILING_PUNCTUATION = ".,;:!?)"
# Models like to write non-breaking hyphens and spaces; they look odd and break copy and paste.
# Code points: hyphen, non-breaking hyphen, no-break space and narrow no-break space.
_TYPOGRAPHY = str.maketrans({0x2010: "-", 0x2011: "-", 0x00A0: " ", 0x202F: " "})


@dataclass(frozen=True, slots=True)
class ValidatedAnswer:
    text: str
    refused: bool
    section: ChatSection | None
    # Why the answer was replaced: off_topic, leak or empty. None when it passed.
    reason: str | None = None


class OutputValidator:
    def __init__(
        self, *, canary: str, rules_text: str, allowed_url_prefixes: tuple[str, ...]
    ) -> None:
        self._canary_key = _squash(canary)
        self.allowed_url_prefixes = tuple(prefix.lower() for prefix in allowed_url_prefixes)
        self._rule_fragments = _word_windows(rules_text, LEAK_WORDS)

    def validate(self, answer: ModelAnswer, locale: Locale) -> ValidatedAnswer:
        """Return the answer to show, or the standard refusal in the visitor's language."""
        if not answer.on_topic:
            return self._refuse(locale, "off_topic")
        raw = strip_invisible(answer.answer.translate(_TYPOGRAPHY))
        text = self._clean(raw)
        # Checked both ways: markup removal can hide a split word (CAN<i></i>ARY) from the raw
        # text, and it can also join one. OWASP LLM07: a canary, a key or a copy of the rules
        # means the prompt leaked.
        if self._leaks(raw) or self._leaks(text):
            logger.error("prompt_leak_blocked", extra={"length": len(raw)})
            return self._refuse(locale, "leak")
        if not text:
            return self._refuse(locale, "empty")
        section = None if answer.section == "none" else answer.section
        return ValidatedAnswer(text=text, refused=False, section=section)

    def _leaks(self, text: str) -> bool:
        if self._canary_key and self._canary_key in _squash(text):
            return True
        if any(pattern.search(text) for pattern in _KEY_PATTERNS):
            return True
        if len(text) > MAX_ANSWER_CHARS:
            return True
        if len(_NUMBERED_LINE.findall(text)) > MAX_NUMBERED_LINES:
            return True
        return not self._rule_fragments.isdisjoint(_word_windows(text, LEAK_WORDS))

    def _clean(self, text: str) -> str:
        """Plain text only, and links only to places Johan owns (PI-10, PI-11)."""
        text = _MARKDOWN_IMAGE.sub("", text)
        text = _HTML_TAG.sub("", text)
        text = _MAILTO.sub(self._keep_mailto, text)
        text = _URL.sub(self._keep_url, text)
        text = _EMAIL.sub(self._keep_email, text)
        return re.sub(r"[ \t]{2,}", " ", text).strip()

    def _keep_url(self, match: re.Match[str]) -> str:
        url = match.group()
        bare = url.rstrip(_TRAILING_PUNCTUATION)
        return url if self._is_allowed(bare) else ""

    @staticmethod
    def _keep_mailto(match: re.Match[str]) -> str:
        address = match.group()[len("mailto:") :].rstrip(_TRAILING_PUNCTUATION)
        return match.group() if address.lower() == CONTACT_EMAIL else ""

    @staticmethod
    def _keep_email(match: re.Match[str]) -> str:
        return match.group() if match.group().lower() == CONTACT_EMAIL else ""

    def _is_allowed(self, url: str) -> bool:
        lowered = url.lower()
        for prefix in self.allowed_url_prefixes:
            # The next character must end the host or path part, so a prefix cannot be
            # extended into a different site (github.com/Joalregra-evil).
            if lowered == prefix or (lowered.startswith(prefix) and lowered[len(prefix)] in "/?#"):
                return True
        return False

    @staticmethod
    def _refuse(locale: Locale, reason: str) -> ValidatedAnswer:
        return ValidatedAnswer(text=REFUSALS[locale], refused=True, section=None, reason=reason)


def build_allowed_url_prefixes(site_url: str | None) -> tuple[str, ...]:
    prefixes = [LINKEDIN_URL, GITHUB_URL]
    if site_url:
        prefixes.append(site_url.rstrip("/"))
    return tuple(prefixes)


def _word_windows(text: str, size: int) -> frozenset[tuple[str, ...]]:
    # Links are removed first: the rules list Johan's links, and an honest answer to "how do I
    # contact him?" repeats them. Without this it would look like a copy of the rules.
    text = _EMAIL.sub(" ", _URL.sub(" ", text))
    words = [word.lower() for word in _WORD.findall(text)]
    return frozenset(tuple(words[i : i + size]) for i in range(len(words) - size + 1))


def _squash(text: str) -> str:
    """Letters and digits only, lowercase: a canary written with spaces or dots still matches."""
    return _NON_ALNUM.sub("", text.lower())
