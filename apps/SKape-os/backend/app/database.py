from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from app.env_config import DATABASE_URL

SQLALCHEMY_DATABASE_URL = DATABASE_URL
CONNECT_TIMEOUT_SECONDS = 5


def engine_options(url, timeout=CONNECT_TIMEOUT_SECONDS):
    """Pre-ping every dialect. Apply only that dialect's timeout option."""

    parsed = make_url(url)
    driver = (parsed.drivername or "").split("+", 1)[0]
    options = {"pool_pre_ping": True}
    if driver == "sqlite":
        options["connect_args"] = {"timeout": timeout}
    elif driver in {"postgresql", "postgres"}:
        options["connect_args"] = {"connect_timeout": timeout}
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
