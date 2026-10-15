"""The ORM models and backend/sql/schema.sql must describe the same PostgreSQL tables.

schema.sql is run by hand on the real database, so a change in one place and not in the other
would only show up in production. This test fails first.
"""

import re

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.core.config import BASE_DIR
from app.db.base import Base
from app.models import chat  # noqa: F401 - registers the models in Base.metadata

SCHEMA_SQL = BASE_DIR / "sql" / "schema.sql"


def _normalise(definition: str) -> tuple[str, ...]:
    """Lowercase, collapse spaces and sort the words.

    Sorting ignores the order of clauses that mean the same, such as `NOT NULL DEFAULT now()`
    and `DEFAULT now() NOT NULL`. Any change to a name, a type or a number is still a difference.
    """
    text = re.sub(r"\s+", " ", definition).strip().lower()
    text = text.replace("timestamp with time zone", "timestamptz").replace(
        "foreign key(", "foreign key ("
    )
    return tuple(sorted(text.replace("(", " ( ").replace(")", " ) ").split()))


def _split_top_level(body: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in body:
        depth += char == "("
        depth -= char == ")"
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


def _definitions(sql: str) -> dict[str, tuple[str, ...]]:
    """Map `table.column` and `table.constraint` to their normalised definition."""
    sql = re.sub(r"--[^\n]*", "", sql)
    found: dict[str, tuple[str, ...]] = {}
    for table, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\)", sql, re.S | re.I):
        for part in _split_top_level(body):
            constraint = re.match(r"constraint (\w+)", part, re.I)
            key = constraint.group(1) if constraint else part.split()[0]
            found[f"{table}.{key}"] = _normalise(part)
    for name, rest in re.findall(r"CREATE INDEX (\w+) ON ([^;\n]+)", sql, re.I):
        found[f"index.{name}"] = _normalise(rest)
    return found


def _model_sql() -> str:
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    statements: list[str] = []
    for table in Base.metadata.sorted_tables:
        statements.append(str(CreateTable(table).compile(dialect=dialect)))
        for index in table.indexes:
            statements.append(str(CreateIndex(index).compile(dialect=dialect)))
    return "\n".join(statements)


def test_models_match_schema_sql() -> None:
    from_file = _definitions(SCHEMA_SQL.read_text(encoding="utf-8"))
    from_models = _definitions(_model_sql())

    assert from_models.keys() == from_file.keys()
    different = [key for key in from_file if from_file[key] != from_models[key]]
    assert different == []
