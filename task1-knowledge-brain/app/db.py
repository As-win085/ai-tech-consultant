"""PostgreSQL connection and migration helpers (pg8000, pure Python).

pg8000 is used instead of psycopg because psycopg's binary wheel has no
Python 3.14 build and no host libpq is available. pg8000's native interface
autocommits each statement and supports multi-statement SQL, which is enough
for idempotent DDL migrations.
"""

from pathlib import Path
from urllib.parse import unquote, urlsplit

import pg8000.native

from app.settings import ConfigError

DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def parse_database_url(url: str) -> dict:
    parts = urlsplit(url)
    if parts.scheme not in {"postgres", "postgresql", "postgresql+pg8000"}:
        raise ConfigError(
            f"Unsupported DATABASE_URL scheme {parts.scheme!r}; expected postgresql://"
        )
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


def apply_migrations(
    connection: pg8000.native.Connection,
    migrations_dir: str | Path | None = None,
) -> list[str]:
    """Apply unapplied ``*.sql`` migrations in order. Returns newly applied ones."""
    directory = Path(migrations_dir) if migrations_dir else DEFAULT_MIGRATIONS_DIR
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
        connection.run(path.read_text(encoding="utf-8"))
        connection.run(
            "INSERT INTO schema_migrations (version) VALUES (:version)", version=version
        )
        newly_applied.append(version)
    return newly_applied
