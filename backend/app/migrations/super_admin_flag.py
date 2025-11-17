from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def apply(engine: Engine) -> None:
    """Ensure the super_admin column exists on the user table."""

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "user" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("user")}
    if "super_admin" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE user ADD COLUMN super_admin INTEGER DEFAULT 0"))
