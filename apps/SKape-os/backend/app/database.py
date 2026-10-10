"""Application database engine.

PostgreSQL pool settings are read when the engine is created. Unset
variables use the defaults below. Only ASCII digits are accepted.
A blank or invalid value is rejected, and the error does not include
the supplied value.

``SKAPE_DB_POOL_SIZE``
    Persistent pooled connections. Default 5. Whole number of
    connections from 1 to 20.

``SKAPE_DB_MAX_OVERFLOW``
    Extra connections allowed above the pool size. Default 5. Whole
    number of connections from 0 to 20. Zero disables overflow.

``SKAPE_DB_POOL_TIMEOUT_SECONDS``
    Seconds to wait for a pooled connection before failing. Default
    30. Whole number of seconds from 1 to 120.

``SKAPE_DB_POOL_RECYCLE_SECONDS``
    Age, in seconds, after which a pooled connection is replaced on
    checkout. Default 300 (five minutes), which is inside common
    network idle limits. Whole number of seconds from 1 to 86400.

``SKAPE_DB_STATEMENT_TIMEOUT_SECONDS``
    Maximum run time of one PostgreSQL statement. Default 30. Whole
    number of seconds from 1 to 120. Passed to libpq as
    ``-c statement_timeout=<milliseconds>`` in the connection options,
    not in the database URL. Zero is rejected because PostgreSQL treats
    it as disabling the timeout.

SQLite keeps ``pool_pre_ping`` and its ``timeout`` connect argument.
It does not receive PostgreSQL pool or statement-timeout arguments.
Alembic uses its own engine and is not given this statement timeout.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from app.env_config import DATABASE_URL


SQLALCHEMY_DATABASE_URL = DATABASE_URL
CONNECT_TIMEOUT_SECONDS = 5
DEFAULT_POOL_SIZE = 5
DEFAULT_MAX_OVERFLOW = 5
DEFAULT_POOL_TIMEOUT_SECONDS = 30
DEFAULT_POOL_RECYCLE_SECONDS = 300
DEFAULT_STATEMENT_TIMEOUT_SECONDS = 30

_POOL_SIZE = (1, 20)
_MAX_OVERFLOW = (0, 20)
_POOL_TIMEOUT_SECONDS = (1, 120)
_POOL_RECYCLE_SECONDS = (1, 86400)
_STATEMENT_TIMEOUT_SECONDS = (1, 120)
_POSTGRES_DRIVERS = {"postgresql", "postgres"}


class DatabaseConfigError(RuntimeError):
    """A database pool setting cannot be used safely."""


class PostgresPoolSettings:
    """Validated PostgreSQL pool limits. Durations are seconds."""

    def __init__(
        self,
        pool_size,
        max_overflow,
        pool_timeout_seconds,
        pool_recycle_seconds,
        statement_timeout_seconds,
    ):
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout_seconds = pool_timeout_seconds
        self.pool_recycle_seconds = pool_recycle_seconds
        self.statement_timeout_seconds = statement_timeout_seconds

    @property
    def statement_timeout_ms(self):
        return self.statement_timeout_seconds * 1000

    def libpq_options(self):
        return f"-c statement_timeout={self.statement_timeout_ms}"


def _configured_int(name, default, bounds, unit):
    raw = os.environ.get(name)
    if raw is None:
        return default
    text = str(raw).strip()
    minimum, maximum = bounds
    message = (
        f"{name} must be a whole number of {unit} "
        f"from {minimum} to {maximum}."
    )
    if (
        not text
        or len(text) > len(str(maximum))
        or not text.isascii()
        or not text.isdigit()
    ):
        raise DatabaseConfigError(message)
    try:
        value = int(text)
    except ValueError:
        raise DatabaseConfigError(message) from None
    if value < minimum or value > maximum:
        raise DatabaseConfigError(message)
    return value


def postgres_pool_settings():
    """Return PostgreSQL pool settings from the environment."""

    return PostgresPoolSettings(
        pool_size=_configured_int(
            "SKAPE_DB_POOL_SIZE",
            DEFAULT_POOL_SIZE,
            _POOL_SIZE,
            "connections",
        ),
        max_overflow=_configured_int(
            "SKAPE_DB_MAX_OVERFLOW",
            DEFAULT_MAX_OVERFLOW,
            _MAX_OVERFLOW,
            "connections",
        ),
        pool_timeout_seconds=_configured_int(
            "SKAPE_DB_POOL_TIMEOUT_SECONDS",
            DEFAULT_POOL_TIMEOUT_SECONDS,
            _POOL_TIMEOUT_SECONDS,
            "seconds",
        ),
        pool_recycle_seconds=_configured_int(
            "SKAPE_DB_POOL_RECYCLE_SECONDS",
            DEFAULT_POOL_RECYCLE_SECONDS,
            _POOL_RECYCLE_SECONDS,
            "seconds",
        ),
        statement_timeout_seconds=_configured_int(
            "SKAPE_DB_STATEMENT_TIMEOUT_SECONDS",
            DEFAULT_STATEMENT_TIMEOUT_SECONDS,
            _STATEMENT_TIMEOUT_SECONDS,
            "seconds",
        ),
    )


def engine_options(url, timeout=CONNECT_TIMEOUT_SECONDS):
    """Pre-ping every dialect. Limit and time out only PostgreSQL."""

    parsed = make_url(url)
    driver = (parsed.drivername or "").split("+", 1)[0]
    options = {"pool_pre_ping": True}
    if driver == "sqlite":
        options["connect_args"] = {"timeout": timeout}
        return options
    if driver not in _POSTGRES_DRIVERS:
        return options
    pool = postgres_pool_settings()
    options.update(
        pool_size=pool.pool_size,
        max_overflow=pool.max_overflow,
        pool_timeout=pool.pool_timeout_seconds,
        pool_recycle=pool.pool_recycle_seconds,
    )
    options["connect_args"] = {
        "connect_timeout": timeout,
        "options": pool.libpq_options(),
    }
    return options


def create_database_engine(url, timeout=CONNECT_TIMEOUT_SECONDS):
    if url is None or not str(url).strip():
        raise RuntimeError("DATABASE_URL must be set.")
    selected = str(url).strip()
    return create_engine(
        selected,
        **engine_options(selected, timeout=timeout),
    )


engine = create_database_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
