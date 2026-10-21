"""Add the answered_cached status.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-20

A repeated question can be answered from the in-memory answer cache, without calling a model.
That row has its answer, no provider and no tokens, so it gets its own status. The status list and
the "answered rows have an answer" rule change, and one rule is new. backend/sql/schema.sql
describes the result, so a database built from that file only needs `alembic stamp head`.

It is a frozen snapshot: it must not import the models, which change over time. The table is the
anonymous log, which is small, so checking the new constraints is instant.
"""

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None

_TABLE = "chat_messages"

_STATUS_NEW = (
    "status IN ('answered', 'answered_quick', 'answered_cached', 'refused_off_topic', "
    "'refused_injection', 'rate_limited', 'provider_error', 'invalid_output')"
)
_STATUS_OLD = (
    "status IN ('answered', 'answered_quick', 'refused_off_topic', 'refused_injection', "
    "'rate_limited', 'provider_error', 'invalid_output')"
)
_HAS_ANSWER_NEW = "status NOT IN ('answered', 'answered_quick', 'answered_cached') OR answer IS NOT NULL"
_HAS_ANSWER_OLD = "status NOT IN ('answered', 'answered_quick') OR answer IS NOT NULL"


def _replace(name: str, condition: str) -> None:
    op.drop_constraint(op.f(name), _TABLE, type_="check")
    op.create_check_constraint(op.f(name), _TABLE, condition)


def upgrade() -> None:
    _replace("ck_chat_messages_status_valid", _STATUS_NEW)
    _replace("ck_chat_messages_answered_has_answer", _HAS_ANSWER_NEW)
    op.create_check_constraint(
        op.f("ck_chat_messages_cached_without_llm"),
        _TABLE,
        "status <> 'answered_cached' OR provider = 'none'",
    )


def downgrade() -> None:
    # The old rules do not know the new status. The rows keep their answer and have no model, which
    # is what a quick answer is, so they are relabelled instead of deleted.
    op.execute("UPDATE chat_messages SET status = 'answered_quick' WHERE status = 'answered_cached'")
    op.drop_constraint(op.f("ck_chat_messages_cached_without_llm"), _TABLE, type_="check")
    _replace("ck_chat_messages_answered_has_answer", _HAS_ANSWER_OLD)
    _replace("ck_chat_messages_status_valid", _STATUS_OLD)
