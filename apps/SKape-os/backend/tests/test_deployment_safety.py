import time
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import OperationalError

from app.alembic_url import (
    MigrationUrlError,
    create_migration_engine,
    resolve_migration_url,
)
from app.database import (
    CONNECT_TIMEOUT_SECONDS,
    DEFAULT_STATEMENT_TIMEOUT_SECONDS,
    create_database_engine,
    engine_options,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
SELECTED_URL = (
    "postgresql+psycopg2://migrator:unused@127.0.0.1:9/"
    "phase4a_selected"
)


def test_alembic_ini_stores_no_database_url():
    contents = ALEMBIC_INI.read_text(encoding="utf-8")
    configured = Config(str(ALEMBIC_INI)).get_main_option("sqlalchemy.url")
    assert configured is None or not str(configured).strip()
    lowered = contents.lower()
    assert "postgresql://" not in lowered
    assert "postgres://" not in lowered
    assert "sqlite://" not in lowered


def test_missing_migration_url_fails_before_an_engine_is_created(
    monkeypatch,
):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    calls = []

    def forbid_engine(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError("migration engine was created")

    with pytest.raises(
        MigrationUrlError,
        match="DATABASE_URL must be set",
    ):
        create_migration_engine(
            Config(str(ALEMBIC_INI)),
            forbid_engine,
            poolclass=object,
        )
    assert calls == []


def test_invalid_migration_url_fails_before_an_engine_is_created(
    monkeypatch,
):
    monkeypatch.setenv("DATABASE_URL", "not-a-database")
    calls = []

    def forbid_engine(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError("migration engine was created")

    with pytest.raises(
        MigrationUrlError,
        match="not a valid database URL",
    ):
        create_migration_engine(
            Config(str(ALEMBIC_INI)),
            forbid_engine,
            poolclass=object,
        )
    assert calls == []


def test_supplied_migration_url_is_the_one_selected(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", SELECTED_URL)
    seen = {}

    def capture_engine(section, prefix, poolclass):
        seen["section"] = section
        seen["prefix"] = prefix
        seen["poolclass"] = poolclass
        return object()

    poolclass = object()
    create_migration_engine(
        Config(str(ALEMBIC_INI)),
        capture_engine,
        poolclass=poolclass,
    )
    selected = make_url(seen["section"]["sqlalchemy.url"])
    assert seen["prefix"] == "sqlalchemy."
    assert seen["poolclass"] is poolclass
    assert selected.drivername == "postgresql+psycopg2"
    assert selected.username == "migrator"
    assert selected.host == "127.0.0.1"
    assert selected.port == 9
    assert selected.database == "phase4a_selected"
    assert resolve_migration_url() == SELECTED_URL


def test_postgres_migration_url_must_name_a_database(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg2://migrator@127.0.0.1:9/",
    )
    with pytest.raises(
        MigrationUrlError,
        match="must name a database",
    ):
        resolve_migration_url()


def test_sqlite_engine_uses_pre_ping_without_postgres_timeout(monkeypatch):
    monkeypatch.setenv("SKAPE_DB_POOL_SIZE", "nope")
    options = engine_options("sqlite://")
    assert options["pool_pre_ping"] is True
    assert options["connect_args"] == {
        "timeout": CONNECT_TIMEOUT_SECONDS,
    }
    assert "connect_timeout" not in options["connect_args"]
    for name in (
        "pool_size",
        "max_overflow",
        "pool_timeout",
        "pool_recycle",
    ):
        assert name not in options

    engine = create_database_engine("sqlite://")
    try:
        assert engine.dialect.name == "sqlite"
        assert engine.pool._pre_ping is True
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT 1").scalar() == 1
    finally:
        engine.dispose()


def test_postgres_engine_uses_pre_ping_and_connect_timeout(monkeypatch):
    for name in (
        "SKAPE_DB_POOL_SIZE",
        "SKAPE_DB_MAX_OVERFLOW",
        "SKAPE_DB_POOL_TIMEOUT_SECONDS",
        "SKAPE_DB_POOL_RECYCLE_SECONDS",
        "SKAPE_DB_STATEMENT_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    options = engine_options(SELECTED_URL)
    assert options["pool_pre_ping"] is True
    assert options["connect_args"] == {
        "connect_timeout": CONNECT_TIMEOUT_SECONDS,
        "options": (
            "-c statement_timeout="
            f"{DEFAULT_STATEMENT_TIMEOUT_SECONDS * 1000}"
        ),
    }
    assert "timeout" not in options["connect_args"]

    engine = create_database_engine(SELECTED_URL)
    try:
        assert engine.dialect.name == "postgresql"
        assert engine.pool._pre_ping is True
    finally:
        engine.dispose()


def test_unreachable_postgres_fails_within_the_connect_timeout():
    engine = create_database_engine(
        "postgresql+psycopg2://migrator:unused@127.0.0.1:1/"
        "phase4a_absent",
        timeout=1,
    )
    started = time.monotonic()
    try:
        with pytest.raises(OperationalError):
            with engine.connect():
                pass
        assert time.monotonic() - started < 4
    finally:
        engine.dispose()
