"""Select the Alembic database from DATABASE_URL.

The ini file is not a connection source. Resolution happens before an
engine or a connection is created, and errors do not include the URL.
"""

import os

from sqlalchemy.engine.url import make_url


class MigrationUrlError(RuntimeError):
    """DATABASE_URL is missing or cannot be used for a migration."""


def resolve_migration_url(raw=None):
    if raw is None:
        raw = os.environ.get("DATABASE_URL")
    if raw is None or not str(raw).strip():
        raise MigrationUrlError(
            "DATABASE_URL must be set before Alembic runs."
        )
    candidate = str(raw).strip()
    try:
        parsed = make_url(candidate)
    except Exception:
        raise MigrationUrlError(
            "DATABASE_URL is not a valid database URL."
        ) from None
    driver = (parsed.drivername or "").split("+", 1)[0]
    if driver == "sqlite":
        return candidate
    if driver not in {"postgresql", "postgres"}:
        raise MigrationUrlError(
            "DATABASE_URL must use PostgreSQL or SQLite."
        )
    if not parsed.database:
        raise MigrationUrlError(
            "DATABASE_URL must name a database."
        )
    return candidate


def apply_migration_url(config):
    """Point Alembic at DATABASE_URL without opening a connection."""

    url = resolve_migration_url()
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return url


def create_migration_engine(config, engine_factory, *, poolclass):
    """Create a migration engine only after DATABASE_URL is accepted."""

    apply_migration_url(config)
    return engine_factory(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=poolclass,
    )
