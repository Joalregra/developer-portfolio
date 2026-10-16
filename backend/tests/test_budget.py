import logging

import pytest

from app.services.budget import BudgetExhaustedError, DailyBudget
from tests.fakes import FakeDate


def test_calls_are_allowed_until_the_limit() -> None:
    budget = DailyBudget(3, clock=FakeDate())

    for _ in range(3):
        budget.consume()

    with pytest.raises(BudgetExhaustedError):
        budget.consume()
    assert budget.used == 3


def test_the_budget_resets_after_midnight_utc() -> None:
    clock = FakeDate()
    budget = DailyBudget(1, clock=clock)
    budget.consume()
    clock.advance(hours=12)

    budget.consume()

    assert budget.used == 1


def test_warnings_are_logged_once_each_at_50_80_and_100_percent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    budget = DailyBudget(10, clock=FakeDate())

    with caplog.at_level(logging.WARNING):
        for _ in range(10):
            budget.consume()

    percents = [record.percent for record in caplog.records if record.msg == "budget_used"]  # type: ignore[attr-defined]
    assert percents == [50, 80, 100]


def test_a_refunded_call_can_be_used_again() -> None:
    budget = DailyBudget(1, clock=FakeDate())
    budget.consume()

    budget.refund()
    budget.consume()

    assert budget.used == 1


def test_refund_never_goes_below_zero() -> None:
    budget = DailyBudget(1, clock=FakeDate())

    budget.refund()

    assert budget.used == 0
