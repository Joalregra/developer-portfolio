"""The file that carries the answer cache and the token budget across a restart."""

import json
import logging
from pathlib import Path

import pytest

from app.core.locale import Locale
from app.services.answer_cache import AnswerCache, CachedAnswer
from app.services.budget import DailyBudget
from app.services.state_store import STATE_VERSION, StatePersister
from tests.fakes import FakeClock, FakeDate

pytestmark = pytest.mark.anyio

ANSWER = CachedAnswer("Johan builds FastAPI backends.", "projects")
FINGERPRINT = "a" * 64


def file_names(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


class Parts:
    """A persister and the cache and budget it carries."""

    def __init__(
        self, path: Path, *, fingerprint: str = FINGERPRINT, clock: FakeClock | None = None
    ) -> None:
        self.clock = clock or FakeClock(1_000_000.0)
        self.date = FakeDate()
        self.cache = AnswerCache(ttl_seconds=3600, max_entries=50, clock=self.clock)
        self.budget = DailyBudget(150_000, clock=self.date)
        self.persister = StatePersister(
            path,
            fingerprint=fingerprint,
            budget=self.budget,
            cache=self.cache,
            save_every_seconds=0.01,
        )


async def test_the_state_makes_a_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    old = Parts(path)
    old.cache.put(Locale.EN, "What stack does Johan use?", ANSWER)
    old.budget.settle(old.budget.reserve(6000), 5180)
    assert await old.persister.save() is True

    new = Parts(path, clock=old.clock)
    new.date = old.date
    new.persister.restore()

    assert new.cache.get(Locale.EN, "what stack does johan use") == ANSWER
    assert new.budget.used == 5180


async def test_no_temporary_file_is_left_after_saving(tmp_path: Path) -> None:
    parts = Parts(tmp_path / "state.json")
    parts.cache.put(Locale.EN, "Question", ANSWER)

    await parts.persister.save()

    assert file_names(tmp_path) == ["state.json"]


async def test_the_file_holds_hashes_and_never_the_question(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    parts = Parts(path)
    parts.cache.put(Locale.EN, "Does Johan know Rust?", ANSWER)

    await parts.persister.save()

    raw = path.read_text("utf-8")
    data = json.loads(raw)
    assert "rust" not in raw.lower()
    assert data["version"] == STATE_VERSION
    assert len(data["answers"][0]["key"]) == 64
    assert set(data["answers"][0]) == {"locale", "key", "stored_at", "text", "section"}
    assert data["budget"]["day"] == "2026-10-15"


async def test_nothing_is_written_when_nothing_changed(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    parts = Parts(path)
    parts.cache.put(Locale.EN, "Question", ANSWER)
    assert await parts.persister.save() is True
    path.unlink()

    assert await parts.persister.save() is False

    assert not path.exists()
    parts.cache.put(Locale.EN, "Another", ANSWER)
    assert await parts.persister.save() is True


async def test_a_corrupt_file_leaves_the_state_empty_and_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "state.json"
    path.write_text("{this is not json", encoding="utf-8")
    parts = Parts(path)

    with caplog.at_level(logging.WARNING):
        parts.persister.restore()

    assert (len(parts.cache), parts.budget.used) == (0, 0)
    assert [r.msg for r in caplog.records] == ["state_load_failed"]
    assert "not json" not in caplog.text


@pytest.mark.parametrize(
    "content",
    [
        {"version": 2, "fingerprint": FINGERPRINT},
        {"version": 1},
        {"version": 1, "fingerprint": FINGERPRINT, "answers": [{"locale": "fr", "key": "x"}]},
        [],
    ],
    ids=["other-version", "no-fingerprint", "bad-entry", "not-an-object"],
)
async def test_a_file_that_does_not_fit_the_format_is_ignored(
    tmp_path: Path, content: object, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    parts = Parts(path)

    with caplog.at_level(logging.WARNING):
        parts.persister.restore()

    assert (len(parts.cache), parts.budget.used) == (0, 0)
    assert "state_load_failed" in [r.msg for r in caplog.records]


async def test_a_missing_file_is_normal_and_silent(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    parts = Parts(tmp_path / "state.json")

    with caplog.at_level(logging.WARNING):
        parts.persister.restore()

    assert not caplog.records


async def test_another_fingerprint_drops_the_cache_but_keeps_the_budget(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "state.json"
    old = Parts(path)
    old.cache.put(Locale.EN, "Question", ANSWER)
    old.budget.reserve(4000)
    await old.persister.save()

    new = Parts(path, fingerprint="b" * 64, clock=old.clock)
    new.date = old.date
    with caplog.at_level(logging.WARNING):
        new.persister.restore()

    assert len(new.cache) == 0
    assert new.budget.used == 4000
    assert "state_cache_discarded" in [r.msg for r in caplog.records]


async def test_yesterdays_budget_is_not_restored(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    old = Parts(path)
    old.budget.reserve(4000)
    await old.persister.save()

    new = Parts(path)
    new.date.advance(days=1)
    new.persister.restore()

    assert new.budget.used == 0


async def test_expired_answers_are_not_restored(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    old = Parts(path)
    old.cache.put(Locale.EN, "Question", ANSWER)
    await old.persister.save()

    new = Parts(path, clock=FakeClock(old.clock.now + 3600))
    new.persister.restore()

    assert len(new.cache) == 0


async def test_a_file_that_cannot_be_written_warns_once_and_the_chat_goes_on(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    parts = Parts(tmp_path / "missing-dir" / "state.json")
    parts.cache.put(Locale.EN, "Question", ANSWER)

    with caplog.at_level(logging.WARNING):
        first = await parts.persister.save()
        second = await parts.persister.save()

    assert (first, second) == (False, False)
    assert [r.msg for r in caplog.records].count("state_save_failed") == 1


async def test_closing_writes_the_final_state(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    parts = Parts(path)
    parts.persister.start()
    parts.cache.put(Locale.EN, "Question", ANSWER)

    await parts.persister.aclose()

    assert json.loads(path.read_text("utf-8"))["answers"][0]["text"] == ANSWER.text


async def test_the_background_task_saves_changes_on_its_own(tmp_path: Path) -> None:
    import asyncio

    path = tmp_path / "state.json"
    parts = Parts(path)
    parts.persister.start()
    parts.cache.put(Locale.EN, "Question", ANSWER)

    for _ in range(100):
        if path.exists():
            break
        await asyncio.sleep(0.02)
    await parts.persister.aclose()

    assert path.exists()
