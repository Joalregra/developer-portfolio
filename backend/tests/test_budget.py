import logging
from datetime import date

import pytest

from app.services.budget import BudgetExhaustedError, BudgetSnapshot, DailyBudget
from tests.fakes import FakeDate


def test_tokens_are_reserved_until_the_limit() -> None:
    budget = DailyBudget(1000, clock=FakeDate())

    assert budget.reserve(400) == 400
    budget.reserve(600)

    with pytest.raises(BudgetExhaustedError):
        budget.reserve(1)
    assert budget.used == 1000


def test_an_estimate_that_does_not_fit_is_refused_and_leaves_the_count_alone() -> None:
    budget = DailyBudget(1000, clock=FakeDate())
    budget.reserve(700)

    with pytest.raises(BudgetExhaustedError):
        budget.reserve(301)

    assert budget.used == 700


def test_settling_replaces_the_reservation_with_the_real_cost() -> None:
    budget = DailyBudget(10_000, clock=FakeDate())
    reserved = budget.reserve(6500)

    budget.settle(reserved, 420)

    assert budget.used == 420


def test_settling_can_cost_more_than_was_reserved() -> None:
    budget = DailyBudget(10_000, clock=FakeDate())
    reserved = budget.reserve(100)

    budget.settle(reserved, 300)

    assert budget.used == 300


def test_the_budget_resets_after_midnight_utc() -> None:
    clock = FakeDate()
    budget = DailyBudget(100, clock=clock)
    budget.reserve(100)
    clock.advance(hours=12)

    budget.reserve(100)

    assert budget.used == 100


def test_warnings_are_logged_once_each_at_50_80_and_100_percent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    budget = DailyBudget(1000, clock=FakeDate())

    with caplog.at_level(logging.WARNING):
        for _ in range(10):
            budget.reserve(100)

    records = [r for r in caplog.records if r.msg == "budget_used"]
    assert [r.percent for r in records] == [50, 80, 100]  # type: ignore[attr-defined]
    assert records[-1].used == 1000  # type: ignore[attr-defined]


def test_a_refunded_reservation_can_be_used_again() -> None:
    budget = DailyBudget(100, clock=FakeDate())
    reserved = budget.reserve(100)

    budget.refund(reserved)
    budget.reserve(100)

    assert budget.used == 100


def test_refund_never_goes_below_zero() -> None:
    budget = DailyBudget(100, clock=FakeDate())

    budget.refund(50)

    assert budget.used == 0


def test_every_change_raises_the_version() -> None:
    budget = DailyBudget(1000, clock=FakeDate())
    versions = [budget.version]

    reserved = budget.reserve(100)
    versions.append(budget.version)
    budget.settle(reserved, 50)
    versions.append(budget.version)
    budget.refund(50)
    versions.append(budget.version)

    assert versions == sorted(set(versions))


def test_the_count_of_today_is_exported_and_restored() -> None:
    clock = FakeDate()
    old = DailyBudget(1000, clock=clock)
    old.reserve(500)  # crosses 50 %
    snapshot = old.export()

    new = DailyBudget(1000, clock=clock)
    assert new.restore(snapshot) is True

    assert new.used == 500
    assert new.export() == snapshot
    assert snapshot.warned == frozenset({50})


def test_a_restored_warning_is_not_logged_again(caplog: pytest.LogCaptureFixture) -> None:
    clock = FakeDate()
    old = DailyBudget(1000, clock=clock)
    old.reserve(500)
    new = DailyBudget(1000, clock=clock)
    caplog.clear()  # the warning from old.reserve is not what this test looks at

    with caplog.at_level(logging.WARNING):
        new.restore(old.export())

    assert not [r for r in caplog.records if r.msg == "budget_used"]


def test_the_count_of_another_day_is_not_restored() -> None:
    budget = DailyBudget(1000, clock=FakeDate())  # 2026-10-15
    yesterday = BudgetSnapshot(date(2026, 10, 14), 900, frozenset({50, 80}))

    assert budget.restore(yesterday) is False

    assert budget.used == 0
    assert budget.export().warned == frozenset()
