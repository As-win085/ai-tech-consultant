"""PostgreSQL connection, schema setup, and migration helpers (pg8000).

pg8000's native interface autocommits each statement and supports multi-statement
SQL, which is enough for idempotent DDL migrations. All Task 3 tables live in a
dedicated schema (default ``meeting_to_scope``) so they never collide with the
Knowledge Brain (Task 1) or Inbox Agent (Task 2) schemas.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pg8000.native

from app.config import ConfigError

DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_database_url(url: str) -> dict:
    parts = urlsplit(url)
    if parts.scheme not in {"postgres", "postgresql", "postgresql+pg8000"}:
        raise ConfigError(f"Unsupported DATABASE_URL scheme {parts.scheme!r}; expected postgresql://")
    if not parts.hostname:
        raise ConfigError("DATABASE_URL is missing a host")
    database = (parts.path or "").lstrip("/") or None
    if not parts.username:
        raise ConfigError("DATABASE_URL is missing a user")
    if not database:
        raise ConfigError("DATABASE_URL is missing a database name")
    return {
        "user": unquote(parts.username),
        "password": unquote(parts.password) if parts.password else None,
        "host": parts.hostname,
        "port": parts.port or 5432,
        "database": database,
    }


def connect(database_url: str) -> pg8000.native.Connection:
    return pg8000.native.Connection(**parse_database_url(database_url))


def validate_schema_name(schema: str) -> str:
    if not _SCHEMA_RE.match(schema):
        raise ConfigError(f"invalid schema name: {schema!r}")
    return schema


def apply_migrations(
    connection: pg8000.native.Connection,
    *,
    schema: str = "meeting_to_scope",
    migrations_dir: str | Path | None = None,
) -> list[str]:
    """Apply unapplied ``*.sql`` migrations in order. Returns newly applied files."""
    schema = validate_schema_name(schema)
    directory = Path(migrations_dir) if migrations_dir else DEFAULT_MIGRATIONS_DIR

    connection.run(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    connection.run(f"SET search_path TO {schema}")
    connection.run(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, "
        "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    applied = {row[0] for row in connection.run("SELECT version FROM schema_migrations")}

    newly_applied: list[str] = []
    for path in sorted(directory.glob("*.sql")):
        version = path.name
        if version in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        connection.run(f"SET search_path TO {schema}")
        connection.run(sql)
        connection.run("INSERT INTO schema_migrations (version) VALUES (:version)", version=version)
        newly_applied.append(version)
    return newly_applied
