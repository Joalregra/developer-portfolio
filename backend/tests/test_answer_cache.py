"""The cache of answers to repeated questions: what makes two questions the same, and when an
entry goes away. How the chat uses it is tested in test_chat_endpoint.py."""

from app.core.locale import Locale
from app.services.answer_cache import (
    AnswerCache,
    CachedAnswer,
    CacheRecord,
    normalize_question,
    question_key,
)
from tests.fakes import FakeClock

ANSWER = CachedAnswer("Johan builds FastAPI backends.", "projects")


def make_cache(clock: FakeClock, *, ttl: float = 60, max_entries: int = 3) -> AnswerCache:
    return AnswerCache(ttl_seconds=ttl, max_entries=max_entries, clock=clock)


def test_questions_that_differ_only_in_case_spacing_or_edge_marks_are_the_same() -> None:
    variants = [
        "¿Qué stack usa Johan?",
        "qué stack usa johan",
        "  QUÉ   stack\tusa Johan??  ",
        "¡Qué stack usa Johan!",
    ]
    assert {normalize_question(text) for text in variants} == {"qué stack usa johan"}


def test_accents_are_kept_so_two_different_words_are_never_merged() -> None:
    assert normalize_question("¿Qué stack usa?") != normalize_question("que stack usa")


def test_marks_and_words_inside_the_question_still_count() -> None:
    assert normalize_question("Has Johan used C++?") != normalize_question("Has Johan used C?")
    assert normalize_question("Does he know Python?") != normalize_question("Does he know Java?")


def test_a_stored_answer_comes_back_for_the_same_question() -> None:
    cache = make_cache(FakeClock())

    cache.put(Locale.EN, "What stack does Johan use?", ANSWER)

    assert cache.get(Locale.EN, "what stack does johan use") == ANSWER


def test_the_language_is_part_of_the_key() -> None:
    cache = make_cache(FakeClock())
    cache.put(Locale.EN, "Python", ANSWER)

    assert cache.get(Locale.ES, "Python") is None


def test_an_entry_expires_after_the_time_limit() -> None:
    clock = FakeClock()
    cache = make_cache(clock, ttl=60)
    cache.put(Locale.EN, "Question", ANSWER)

    clock.advance(59)
    assert cache.get(Locale.EN, "Question") == ANSWER
    clock.advance(1)
    assert cache.get(Locale.EN, "Question") is None
    assert len(cache) == 0


def test_the_least_recently_used_entry_goes_first_when_full() -> None:
    cache = make_cache(FakeClock(), max_entries=2)
    cache.put(Locale.EN, "one", ANSWER)
    cache.put(Locale.EN, "two", ANSWER)
    cache.get(Locale.EN, "one")  # "two" is now the oldest use

    cache.put(Locale.EN, "three", ANSWER)

    assert cache.get(Locale.EN, "two") is None
    assert cache.get(Locale.EN, "one") == ANSWER
    assert cache.get(Locale.EN, "three") == ANSWER


def test_a_ttl_of_zero_switches_the_cache_off() -> None:
    cache = make_cache(FakeClock(), ttl=0)

    cache.put(Locale.EN, "Question", ANSWER)

    assert cache.enabled is False
    assert cache.get(Locale.EN, "Question") is None
    assert len(cache) == 0


def test_a_question_with_nothing_but_marks_is_not_stored() -> None:
    cache = make_cache(FakeClock())

    cache.put(Locale.EN, "¿?!", ANSWER)

    assert len(cache) == 0


def test_the_cache_never_keeps_the_text_of_the_question() -> None:
    cache = make_cache(FakeClock())
    cache.put(Locale.EN, "What is Johan's secret salary?", ANSWER)

    (record,) = cache.export()

    assert record.key == question_key(normalize_question("What is Johan's secret salary?"))
    assert len(record.key) == 64
    assert "salary" not in repr(record).replace(ANSWER.text, "")
    assert all("salary" not in str(key) for key in cache._entries)


def test_an_exported_entry_comes_back_after_loading_into_a_new_cache() -> None:
    clock = FakeClock()
    old = make_cache(clock)
    old.put(Locale.EN, "What stack does Johan use?", ANSWER)
    new = make_cache(clock)

    assert new.load(old.export()) == 1

    assert new.get(Locale.EN, "what stack does johan use") == ANSWER


def test_age_is_counted_with_the_wall_clock_so_downtime_counts() -> None:
    clock = FakeClock()
    old = make_cache(clock, ttl=60)
    old.put(Locale.EN, "Question", ANSWER)
    records = old.export()
    clock.advance(30)  # the process was down for 30 s
    new = make_cache(clock, ttl=60)
    new.load(records)

    assert new.get(Locale.EN, "Question") == ANSWER
    clock.advance(30)
    assert new.get(Locale.EN, "Question") is None


def test_expired_entries_are_dropped_when_loading() -> None:
    clock = FakeClock()
    fresh = CacheRecord(Locale.EN, question_key("fresh"), clock.now - 10, ANSWER)
    stale = CacheRecord(Locale.EN, question_key("stale"), clock.now - 60, ANSWER)
    cache = make_cache(clock, ttl=60)

    assert cache.load([fresh, stale]) == 1

    assert len(cache) == 1
    assert cache.get(Locale.EN, "fresh") == ANSWER
    assert cache.get(Locale.EN, "stale") is None


def test_loading_respects_the_size_limit() -> None:
    clock = FakeClock()
    records = [CacheRecord(Locale.EN, question_key(str(i)), clock.now, ANSWER) for i in range(5)]
    cache = make_cache(clock, max_entries=3)

    cache.load(records)

    assert len(cache) == 3


def test_a_cache_that_is_off_loads_nothing() -> None:
    record = CacheRecord(Locale.EN, question_key("q"), 1000.0, ANSWER)
    cache = make_cache(FakeClock(), ttl=0)

    assert cache.load([record]) == 0
    assert len(cache) == 0


def test_every_change_raises_the_version_and_a_read_does_not() -> None:
    cache = make_cache(FakeClock())
    start = cache.version

    cache.put(Locale.EN, "Question", ANSWER)
    stored = cache.version
    cache.get(Locale.EN, "Question")

    assert stored > start
    assert cache.version == stored


def test_export_leaves_out_what_expired() -> None:
    clock = FakeClock()
    cache = make_cache(clock, ttl=60)
    cache.put(Locale.EN, "Question", ANSWER)

    clock.advance(60)

    assert cache.export() == []
