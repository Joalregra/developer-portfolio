import logging

import pytest

from app.services import rate_limit
from app.services.rate_limit import (
    ModelQuota,
    ModelQuotaExceededError,
    RateLimiter,
    RateLimitExceededError,
    client_key,
)
from tests.fakes import FakeClock


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def make(clock: FakeClock, per_minute: int = 3, per_day: int = 10) -> RateLimiter:
    return RateLimiter(per_minute, per_day, clock=clock)


def test_requests_within_the_limit_pass(clock: FakeClock) -> None:
    limiter = make(clock)

    for _ in range(3):
        limiter.check("a")


def test_the_request_over_the_minute_limit_is_refused_with_a_wait_time(clock: FakeClock) -> None:
    limiter = make(clock)
    for _ in range(3):
        limiter.check("a")
        clock.advance(10)

    with pytest.raises(RateLimitExceededError) as caught:
        limiter.check("a")

    # The oldest request was 30 seconds ago, so it frees a place in 30 more.
    assert caught.value.retry_after_seconds == 30


def test_the_window_slides(clock: FakeClock) -> None:
    limiter = make(clock)
    for _ in range(3):
        limiter.check("a")

    clock.advance(61)

    limiter.check("a")


def test_the_day_limit_is_separate(clock: FakeClock) -> None:
    limiter = make(clock, per_minute=100, per_day=4)
    for _ in range(4):
        limiter.check("a")
        clock.advance(120)

    with pytest.raises(RateLimitExceededError) as caught:
        limiter.check("a")

    assert caught.value.retry_after_seconds > 3600


def test_visitors_do_not_share_a_limit(clock: FakeClock) -> None:
    limiter = make(clock, per_minute=1)
    limiter.check("a")

    limiter.check("b")


def test_refused_requests_do_not_extend_the_wait(clock: FakeClock) -> None:
    limiter = make(clock, per_minute=1)
    limiter.check("a")

    for _ in range(5):
        with pytest.raises(RateLimitExceededError):
            limiter.check("a")
    clock.advance(61)

    limiter.check("a")


def test_three_strikes_block_the_visitor_for_a_while(
    clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    limiter = make(clock)
    with caplog.at_level(logging.WARNING):
        assert [limiter.add_strike("a") for _ in range(3)] == [False, False, True]

    with pytest.raises(RateLimitExceededError) as caught:
        limiter.check("a")
    assert caught.value.retry_after_seconds == 900
    assert "ip_blocked" in caplog.text
    clock.advance(901)
    limiter.check("a")


def test_strikes_expire(clock: FakeClock) -> None:
    limiter = make(clock)
    limiter.add_strike("a")
    limiter.add_strike("a")
    clock.advance(601)

    assert limiter.add_strike("a") is False


def test_old_entries_are_swept(clock: FakeClock) -> None:
    limiter = make(clock)
    for number in range(20):
        limiter.check(f"visitor-{number}")
    limiter.add_strike("x")
    clock.advance(86_401)

    limiter.check("someone-new")

    assert limiter.stats() == {"tracked": 1, "strikes": 0, "blocked": 0}


def test_the_number_of_tracked_visitors_has_a_ceiling(
    clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rate_limit, "MAX_TRACKED_KEYS", 5)
    limiter = make(clock)

    for number in range(50):
        limiter.check(f"visitor-{number}")

    assert limiter.stats()["tracked"] <= 5


def test_ipv6_visitors_in_one_56_block_share_a_key() -> None:
    first = client_key("2001:db8:abcd:1200::1")
    second = client_key("2001:db8:abcd:12ff:ffff:ffff:ffff:ffff")  # same /56, other /64
    other_block = client_key("2001:db8:abcd:1300::1")

    assert first == second
    assert first != other_block


def test_an_ipv4_visitor_seen_through_an_ipv6_socket_keeps_its_own_key() -> None:
    assert client_key("::ffff:203.0.113.7") == "203.0.113.7"
    assert client_key("::ffff:203.0.113.8") != client_key("::ffff:203.0.113.7")


def test_ipv4_and_unknown_hosts_are_kept_as_they_are() -> None:
    assert client_key("203.0.113.7") == "203.0.113.7"
    assert client_key("testclient") == "testclient"


def make_quota(clock: FakeClock, per_hour: int = 3, per_day: int = 6) -> ModelQuota:
    return ModelQuota(per_hour, per_day, clock=clock)


def test_model_questions_within_the_hour_allowance_pass(clock: FakeClock) -> None:
    quota = make_quota(clock)

    for _ in range(3):
        quota.reserve("a")


def test_the_question_over_the_hour_allowance_is_refused_with_a_wait_time(
    clock: FakeClock,
) -> None:
    quota = make_quota(clock)
    for _ in range(3):
        quota.reserve("a")
        clock.advance(60)

    with pytest.raises(ModelQuotaExceededError) as caught:
        quota.reserve("a")

    # the oldest question is 180 s old, so it leaves the hour in 3,420 s
    assert (caught.value.window, caught.value.retry_after_seconds) == ("hour", 3420)


def test_the_allowance_comes_back_as_the_hour_slides(clock: FakeClock) -> None:
    quota = make_quota(clock)
    for _ in range(3):
        quota.reserve("a")

    clock.advance(rate_limit.HOUR)

    quota.reserve("a")


def test_the_day_allowance_holds_even_when_the_hour_is_free(clock: FakeClock) -> None:
    quota = make_quota(clock)
    for _ in range(2):  # 3 + 3 questions, an hour apart
        for _ in range(3):
            quota.reserve("a")
        clock.advance(rate_limit.HOUR)

    with pytest.raises(ModelQuotaExceededError) as caught:
        quota.reserve("a")

    assert caught.value.window == "day"
    assert caught.value.retry_after_seconds == rate_limit.DAY - 2 * rate_limit.HOUR


def test_the_day_allowance_slides_too(clock: FakeClock) -> None:
    quota = make_quota(clock, per_hour=10, per_day=2)
    quota.reserve("a")
    quota.reserve("a")

    clock.advance(rate_limit.DAY)

    quota.reserve("a")


def test_each_visitor_has_their_own_model_allowance(clock: FakeClock) -> None:
    quota = make_quota(clock, per_hour=1, per_day=1)
    quota.reserve("a")

    quota.reserve("b")

    with pytest.raises(ModelQuotaExceededError):
        quota.reserve("a")


def test_a_released_question_can_be_asked_again(clock: FakeClock) -> None:
    quota = make_quota(clock, per_hour=1, per_day=1)
    quota.reserve("a")

    quota.release("a")
    quota.reserve("a")

    with pytest.raises(ModelQuotaExceededError):
        quota.reserve("a")


def test_releasing_an_unknown_key_does_nothing(clock: FakeClock) -> None:
    make_quota(clock).release("nobody")


def test_the_model_quota_stops_tracking_old_keys(clock: FakeClock) -> None:
    quota = make_quota(clock)
    quota.reserve("old")

    clock.advance(rate_limit.DAY + 1)
    quota.reserve("new")  # the sweep runs here

    assert list(quota._calls) == ["new"]


def test_the_model_quota_tracks_a_bounded_number_of_keys(
    clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rate_limit, "MAX_TRACKED_KEYS", 3)
    quota = make_quota(clock)

    for key in "abcd":
        quota.reserve(key)

    assert list(quota._calls) == ["b", "c", "d"]
