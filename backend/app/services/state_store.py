"""The chat state that survives a restart: the answer cache and today's token budget.

Both live in memory and are copied to one JSON file, so a deploy does not throw away the cached
answers or hand the Groq quota back to zero. The chat never depends on this file (the same rule as
the database log): if it is missing, corrupt, from another version or unwritable, a warning is
logged and the chat starts with an empty state.

What the file holds, and what it does not:
- Answers the output validator already accepted, keyed by a hash of the normalized question. The
  visitor's text is never stored, so it cannot reach the disk or a backup.
- The token count of the current UTC day.
- No address, no counter per visitor: those reset with every restart on purpose.

The cache is tied to a fingerprint of the system prompt (knowledge, rules and canary). If it
changed, the saved answers may describe an older Johan and are dropped; the budget is kept, because
the quota does not depend on the knowledge. One process writes the file (ARQ-06).
"""

import asyncio
import contextlib
import hashlib
import logging
import os
from datetime import date
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.locale import Locale
from app.schemas.chat import ChatSection
from app.services.answer_cache import AnswerCache, CachedAnswer, CacheRecord
from app.services.budget import BudgetSnapshot, DailyBudget

logger = logging.getLogger(__name__)

STATE_VERSION: Final = 1
SAVE_EVERY_SECONDS: Final = 30.0
# Entries are small (an answer is under 1,500 characters); this only stops a damaged file.
MAX_STATE_BYTES: Final = 4_000_000


class _StoredBudget(BaseModel):
    model_config = ConfigDict(extra="ignore")

    day: date
    used_tokens: int = Field(ge=0)
    warned: list[int] = []


class _StoredAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    locale: Locale
    key: str = Field(pattern=r"^[0-9a-f]{64}$")
    stored_at: float
    text: str
    section: ChatSection | None = None


class _StateFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: Literal[1]
    fingerprint: str
    budget: _StoredBudget | None = None
    answers: list[_StoredAnswer] = []


def fingerprint_of(system_prompt: str) -> str:
    return hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()


class StatePersister:
    """Loads the state at startup, saves it every 30 seconds when it changed, and once more at
    shutdown."""

    def __init__(
        self,
        path: Path,
        *,
        fingerprint: str,
        budget: DailyBudget,
        cache: AnswerCache,
        save_every_seconds: float = SAVE_EVERY_SECONDS,
    ) -> None:
        self._path = path
        self._tmp_path = path.with_name(path.name + ".tmp")
        self._fingerprint = fingerprint
        self._budget = budget
        self._cache = cache
        self._interval = save_every_seconds
        self._saved_at: tuple[int, int] | None = None
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._failing = False

    def restore(self) -> None:
        """Read the file once at startup. Never raises."""
        try:
            raw = self._path.read_bytes()
        except FileNotFoundError:
            logger.info("state_not_found")
            return
        except OSError as exc:
            logger.warning("state_load_failed", extra={"reason": type(exc).__name__})
            return
        try:
            if len(raw) > MAX_STATE_BYTES:
                raise ValueError("file too big")
            state = _StateFile.model_validate_json(raw)
        except (ValidationError, ValueError) as exc:
            logger.warning("state_load_failed", extra={"reason": type(exc).__name__})
            return

        restored_budget = False
        if state.budget is not None:
            restored_budget = self._budget.restore(
                BudgetSnapshot(
                    state.budget.day, state.budget.used_tokens, frozenset(state.budget.warned)
                )
            )
        kept = 0
        if state.fingerprint != self._fingerprint:
            logger.warning("state_cache_discarded", extra={"reason": "knowledge_changed"})
        else:
            kept = self._cache.load(
                CacheRecord(a.locale, a.key, a.stored_at, CachedAnswer(a.text, a.section))
                for a in state.answers
            )
        logger.info(
            "state_restored",
            extra={"answers": kept, "budget_restored": restored_budget},
        )

    def start(self) -> None:
        """Start the periodic save. Needs a running event loop."""
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="state-persister")

    async def aclose(self) -> None:
        """Stop the periodic save and write the final state."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self.save(force=True)

    async def save(self, *, force: bool = False) -> bool:
        """Write the state if something changed since the last write. Never raises."""
        async with self._lock:
            marks = (self._cache.version, self._budget.version)
            if not force and marks == self._saved_at:
                return False
            payload = self._serialize()
            try:
                await asyncio.to_thread(self._write, payload)
            except OSError as exc:
                if not self._failing:
                    logger.warning("state_save_failed", extra={"reason": type(exc).__name__})
                self._failing = True
                return False
            self._failing = False
            self._saved_at = marks
            return True

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self.save()

    def _serialize(self) -> str:
        snapshot = self._budget.export()
        state = _StateFile(
            version=STATE_VERSION,
            fingerprint=self._fingerprint,
            budget=_StoredBudget(
                day=snapshot.day,
                used_tokens=snapshot.used_tokens,
                warned=sorted(snapshot.warned),
            ),
            answers=[
                _StoredAnswer(
                    locale=r.locale,
                    key=r.key,
                    stored_at=r.stored_at,
                    text=r.answer.text,
                    section=r.answer.section,
                )
                for r in self._cache.export()
            ],
        )
        return state.model_dump_json()

    def _write(self, payload: str) -> None:
        """Write to a temporary file and rename it, so a crash never leaves half a file."""
        try:
            with self._tmp_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            self._tmp_path.replace(self._path)  # atomic on the same volume
        except OSError:
            with contextlib.suppress(OSError):
                self._tmp_path.unlink(missing_ok=True)
            raise
