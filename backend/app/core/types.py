"""Custom SQLAlchemy types that work with both PostgreSQL and SQLite."""

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator


class CompatibleJSON(TypeDecorator):
    """JSON type that uses JSONB on PostgreSQL and JSON on SQLite.

    Use this instead of `from sqlalchemy.dialects.postgresql import JSONB`
    to ensure tests work with SQLite while production uses PostgreSQL.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())
