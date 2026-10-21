"""Create the assistant log tables.

Revision ID: 0001
Revises:
Create Date: 2026-10-15

This migration describes exactly what backend/sql/schema.sql creates. On a database that was
built from that file, run `alembic stamp head` instead of `upgrade`. It is a frozen snapshot:
it must not import the models, which change over time.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("locale", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_tokens", sa.Integer(), nullable=True),
        sa.Column("knowledge_version", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
        sa.CheckConstraint("locale IN ('es', 'en')", name=op.f("ck_chat_messages_locale_valid")),
        sa.CheckConstraint(
            "length(question) BETWEEN 1 AND 1000",
            name=op.f("ck_chat_messages_question_length"),
        ),
        sa.CheckConstraint(
            "answer IS NULL OR length(answer) BETWEEN 1 AND 2000",
            name=op.f("ck_chat_messages_answer_length"),
        ),
        sa.CheckConstraint(
            "status IN ('answered', 'answered_quick', 'refused_off_topic', 'refused_injection', "
            "'rate_limited', 'provider_error', 'invalid_output')",
            name=op.f("ck_chat_messages_status_valid"),
        ),
        sa.CheckConstraint(
            "provider IN ('groq', 'gemini', 'none')",
            name=op.f("ck_chat_messages_provider_valid"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('answered', 'answered_quick') OR answer IS NOT NULL",
            name=op.f("ck_chat_messages_answered_has_answer"),
        ),
        sa.CheckConstraint(
            "status <> 'answered' OR provider IN ('groq', 'gemini')",
            name=op.f("ck_chat_messages_answered_by_llm"),
        ),
        sa.CheckConstraint(
            "status <> 'answered_quick' OR provider = 'none'",
            name=op.f("ck_chat_messages_quick_without_llm"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('refused_off_topic', 'invalid_output') OR provider <> 'none'",
            name=op.f("ck_chat_messages_model_result_has_provider"),
        ),
        sa.CheckConstraint(
            "provider <> 'none' OR (prompt_tokens IS NULL AND completion_tokens IS NULL "
            "AND cached_tokens IS NULL)",
            name=op.f("ck_chat_messages_tokens_need_provider"),
        ),
        sa.CheckConstraint("latency_ms >= 0", name=op.f("ck_chat_messages_latency_nonnegative")),
        sa.CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0 AND cached_tokens >= 0",
            name=op.f("ck_chat_messages_tokens_nonnegative"),
        ),
        sa.CheckConstraint(
            "cached_tokens IS NULL OR prompt_tokens IS NULL OR cached_tokens <= prompt_tokens",
            name=op.f("ck_chat_messages_cached_within_prompt"),
        ),
        sa.CheckConstraint(
            "length(knowledge_version) BETWEEN 1 AND 64",
            name=op.f("ck_chat_messages_knowledge_version_length"),
        ),
    )
    op.create_index(
        op.f("ix_chat_messages_created_at"), "chat_messages", ["created_at"], unique=False
    )

    op.create_table(
        "feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("helpful", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback")),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["chat_messages.id"],
            name=op.f("fk_feedback_message_id_chat_messages"),
            ondelete="CASCADE",
        ),
        # This unique index also serves the foreign key lookups.
        sa.UniqueConstraint("message_id", name=op.f("uq_feedback_message_id")),
    )


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_index(op.f("ix_chat_messages_created_at"), table_name="chat_messages")
    op.drop_table("chat_messages")
