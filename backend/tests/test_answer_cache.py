"""The cache of answers to repeated questions: what makes two questions the same, and when an
entry goes away. How the chat uses it is tested in test_chat_endpoint.py."""

from app.core.locale import Locale
from app.services.answer_cache import AnswerCache, CachedAnswer, normalize_question
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
