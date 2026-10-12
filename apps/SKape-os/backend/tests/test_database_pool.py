import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import QueuePool

from app.database import (
    CONNECT_TIMEOUT_SECONDS,
    DEFAULT_MAX_OVERFLOW,
    DEFAULT_POOL_RECYCLE_SECONDS,
    DEFAULT_POOL_SIZE,
    DEFAULT_POOL_TIMEOUT_SECONDS,
    DEFAULT_STATEMENT_TIMEOUT_SECONDS,
    DatabaseConfigError,
    create_database_engine,
    engine_options,
    postgres_pool_settings,
)


POSTGRES_URL = (
    "postgresql+psycopg2://migrator:unused@127.0.0.1:9/pool_check"
)
POOL_ENV = (
    "SKAPE_DB_POOL_SIZE",
    "SKAPE_DB_MAX_OVERFLOW",
    "SKAPE_DB_POOL_TIMEOUT_SECONDS",
    "SKAPE_DB_POOL_RECYCLE_SECONDS",
    "SKAPE_DB_STATEMENT_TIMEOUT_SECONDS",
)


@pytest.fixture
def cleared_pool_env(monkeypatch):
    for name in POOL_ENV:
        monkeypatch.delenv(name, raising=False)


def test_postgres_engine_uses_bounded_pool_defaults(cleared_pool_env):
    options = engine_options(POSTGRES_URL)
    assert options["pool_pre_ping"] is True
    assert options["pool_size"] == DEFAULT_POOL_SIZE == 5
    assert options["max_overflow"] == DEFAULT_MAX_OVERFLOW == 5
    assert options["pool_timeout"] == DEFAULT_POOL_TIMEOUT_SECONDS == 30
    assert options["pool_recycle"] == DEFAULT_POOL_RECYCLE_SECONDS == 300
    assert options["connect_args"]["connect_timeout"] == (
        CONNECT_TIMEOUT_SECONDS
    )
    assert options["connect_args"]["options"] == (
        "-c statement_timeout="
        f"{DEFAULT_STATEMENT_TIMEOUT_SECONDS * 1000}"
    )

    engine = create_database_engine(POSTGRES_URL)
    try:
        assert engine.dialect.name == "postgresql"
        assert isinstance(engine.pool, QueuePool)
        assert engine.pool.size() == DEFAULT_POOL_SIZE
        assert engine.pool._max_overflow == DEFAULT_MAX_OVERFLOW
        assert engine.pool.timeout() == DEFAULT_POOL_TIMEOUT_SECONDS
        assert engine.pool._recycle == DEFAULT_POOL_RECYCLE_SECONDS
        assert engine.pool._pre_ping is True
        rendered = engine.url.render_as_string(hide_password=False)
        assert "statement_timeout" not in rendered
        assert "statement_timeout" not in repr(engine)
    finally:
        engine.dispose()


def test_postgres_alias_receives_the_same_pool_limits(cleared_pool_env):
    options = engine_options(
        "postgres://migrator:unused@127.0.0.1:9/pool_check"
    )
    assert options["pool_size"] == DEFAULT_POOL_SIZE
    assert options["connect_args"]["options"].startswith(
        "-c statement_timeout="
    )


def test_pool_settings_are_configurable(monkeypatch):
    monkeypatch.setenv("SKAPE_DB_POOL_SIZE", "3")
    monkeypatch.setenv("SKAPE_DB_MAX_OVERFLOW", "0")
    monkeypatch.setenv("SKAPE_DB_POOL_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("SKAPE_DB_POOL_RECYCLE_SECONDS", "90")
    monkeypatch.setenv("SKAPE_DB_STATEMENT_TIMEOUT_SECONDS", "2")
    settings = postgres_pool_settings()
    assert settings.pool_size == 3
    assert settings.max_overflow == 0
    assert settings.pool_timeout_seconds == 7
    assert settings.pool_recycle_seconds == 90
    assert settings.statement_timeout_seconds == 2
    assert settings.statement_timeout_ms == 2000
    options = engine_options(POSTGRES_URL)
    assert options["pool_size"] == 3
    assert options["max_overflow"] == 0
    assert options["pool_timeout"] == 7
    assert options["pool_recycle"] == 90
    assert options["connect_args"]["options"] == (
        "-c statement_timeout=2000"
    )
    assert options["connect_args"]["connect_timeout"] == (
        CONNECT_TIMEOUT_SECONDS
    )


def test_statement_timeout_is_passed_to_psycopg2(monkeypatch, cleared_pool_env):
    captured = []

    def refuse_connection(*_args, **kwargs):
        captured.append(kwargs)
        raise OperationalError(
            "connect",
            {},
            Exception("connection refused"),
        )

    monkeypatch.setattr("psycopg2.connect", refuse_connection)
    engine = create_database_engine(POSTGRES_URL)
    try:
        assert captured == []
        with pytest.raises(OperationalError):
            with engine.connect():
                pass
    finally:
        engine.dispose()
    assert captured
    for kwargs in captured:
        assert kwargs["connect_timeout"] == CONNECT_TIMEOUT_SECONDS
        assert kwargs["options"] == "-c statement_timeout=30000"
        assert "://" not in kwargs["options"]
        assert "unused" not in kwargs["options"]


def test_url_options_cannot_replace_the_statement_timeout(
    monkeypatch,
    cleared_pool_env,
):
    captured = []

    def refuse_connection(*_args, **kwargs):
        captured.append(kwargs)
        raise OperationalError("connect", {}, Exception("refused"))

    monkeypatch.setattr("psycopg2.connect", refuse_connection)
    engine = create_database_engine(
        POSTGRES_URL + "?options=-c%20statement_timeout%3D0"
    )
    try:
        with pytest.raises(OperationalError):
            with engine.connect():
                pass
    finally:
        engine.dispose()
    assert captured
    assert captured[0]["options"] == "-c statement_timeout=30000"
    assert "statement_timeout=0" not in captured[0]["options"]


_REJECTED = {
    "SKAPE_DB_POOL_SIZE": (
        "SKAPE_DB_POOL_SIZE must be a whole number of connections "
        "from 1 to 20."
    ),
    "SKAPE_DB_MAX_OVERFLOW": (
        "SKAPE_DB_MAX_OVERFLOW must be a whole number of connections "
        "from 0 to 20."
    ),
    "SKAPE_DB_POOL_TIMEOUT_SECONDS": (
        "SKAPE_DB_POOL_TIMEOUT_SECONDS must be a whole number of "
        "seconds from 1 to 120."
    ),
    "SKAPE_DB_POOL_RECYCLE_SECONDS": (
        "SKAPE_DB_POOL_RECYCLE_SECONDS must be a whole number of "
        "seconds from 1 to 86400."
    ),
    "SKAPE_DB_STATEMENT_TIMEOUT_SECONDS": (
        "SKAPE_DB_STATEMENT_TIMEOUT_SECONDS must be a whole number "
        "of seconds from 1 to 120."
    ),
}


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SKAPE_DB_POOL_SIZE", "0"),
        ("SKAPE_DB_POOL_SIZE", "21"),
        ("SKAPE_DB_POOL_SIZE", "-1"),
        ("SKAPE_DB_POOL_SIZE", "1.5"),
        ("SKAPE_DB_POOL_SIZE", "five"),
        ("SKAPE_DB_POOL_SIZE", ""),
        ("SKAPE_DB_MAX_OVERFLOW", "-1"),
        ("SKAPE_DB_MAX_OVERFLOW", "21"),
        ("SKAPE_DB_POOL_TIMEOUT_SECONDS", "0"),
        ("SKAPE_DB_POOL_TIMEOUT_SECONDS", "121"),
        ("SKAPE_DB_POOL_RECYCLE_SECONDS", "0"),
        ("SKAPE_DB_POOL_RECYCLE_SECONDS", "86401"),
        ("SKAPE_DB_STATEMENT_TIMEOUT_SECONDS", "0"),
        ("SKAPE_DB_STATEMENT_TIMEOUT_SECONDS", "-5"),
        ("SKAPE_DB_STATEMENT_TIMEOUT_SECONDS", "121"),
    ],
)
def test_invalid_pool_values_are_rejected(monkeypatch, name, value):
    for setting in POOL_ENV:
        monkeypatch.delenv(setting, raising=False)
    monkeypatch.setenv(name, value)
    with pytest.raises(DatabaseConfigError) as caught:
        postgres_pool_settings()
    assert str(caught.value) == _REJECTED[name]


@pytest.mark.parametrize(
    "value",
    ["\u00b2", "\u0967", "\uff11\uff10"],
)
def test_non_ascii_digits_are_rejected(monkeypatch, value):
    for setting in POOL_ENV:
        monkeypatch.delenv(setting, raising=False)
    monkeypatch.setenv("SKAPE_DB_POOL_SIZE", value)
    with pytest.raises(DatabaseConfigError) as caught:
        postgres_pool_settings()
    message = str(caught.value)
    assert message == _REJECTED["SKAPE_DB_POOL_SIZE"]
    assert value not in message
    assert caught.value.__cause__ is None


def test_sqlite_engine_ignores_postgres_pool_settings(monkeypatch):
    monkeypatch.setenv("SKAPE_DB_POOL_SIZE", "3")
    monkeypatch.setenv("SKAPE_DB_STATEMENT_TIMEOUT_SECONDS", "2")
    options = engine_options("sqlite://")
    assert options == {
        "pool_pre_ping": True,
        "connect_args": {"timeout": CONNECT_TIMEOUT_SECONDS},
    }
    engine = create_database_engine("sqlite://")
    try:
        assert engine.dialect.name == "sqlite"
        assert not isinstance(engine.pool, QueuePool)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT 1").scalar() == 1
    finally:
        engine.dispose()
