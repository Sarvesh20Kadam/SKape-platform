import asyncio
import importlib.util
import os
import re
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault(
    "SECRET_KEY",
    "skape-test-jwt-signing-secret-value",
)
os.environ.setdefault("ALGORITHM", "HS256")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.main import app


_DISPOSABLE_NAME = re.compile(r"^skape_test_[0-9a-f]{16}$")
_TABLE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_DISPOSABLE_MODULE = None


def _postgres_api_requested():
    return os.environ.get("SKAPE_TEST_POSTGRES_API") == "1"


def _postgres_disposable():
    """Load the disposable-database helpers without collecting them twice."""

    global _DISPOSABLE_MODULE
    if _DISPOSABLE_MODULE is None:
        path = Path(__file__).with_name(
            "test_device_monitor_postgres.py"
        )
        spec = importlib.util.spec_from_file_location(
            "skape_postgres_disposable",
            path,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _DISPOSABLE_MODULE = module
    return _DISPOSABLE_MODULE


def _clear_disposable_database(engine, name):
    """Remove application rows from one disposable database."""

    if not _DISPOSABLE_NAME.fullmatch(name or ""):
        raise RuntimeError(
            "refusing to clean a non-disposable database"
        )
    with engine.begin() as connection:
        current = connection.execute(
            text("SELECT current_database()")
        ).scalar()
        if current != name or not _DISPOSABLE_NAME.fullmatch(
            current or ""
        ):
            raise RuntimeError(
                "refusing to clean the connected database"
            )
        tables = connection.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' "
                "AND tablename <> 'alembic_version' "
                "ORDER BY tablename"
            )
        ).scalars().all()
        if not tables:
            raise RuntimeError(
                "disposable database has no application tables"
            )
        for table in tables:
            if not _TABLE_NAME.fullmatch(table):
                raise RuntimeError(
                    "refusing to clean an unexpected table"
                )
        quoted = ", ".join(f'"{table}"' for table in tables)
        connection.execute(
            text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
        )


@pytest.fixture(autouse=True)
def _postgres_api_guard():
    """Fail closed when the PostgreSQL API run has no safe database."""

    if not _postgres_api_requested():
        yield
        return
    if os.environ.get("SKAPE_REQUIRE_POSTGRES") != "1":
        pytest.fail(
            "PostgreSQL API tests require SKAPE_REQUIRE_POSTGRES=1"
        )
    url = os.environ.get("SKAPE_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.fail("SKAPE_TEST_DATABASE_URL is required")
    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.fail("PostgreSQL API tests must run serially")
    _postgres_disposable()._assert_safe_admin_url(url)
    yield


@pytest.fixture(scope="session")
def _postgres_api_lab():
    if not _postgres_api_requested():
        pytest.fail(
            "PostgreSQL API database requested without "
            "SKAPE_TEST_POSTGRES_API=1"
        )
    module = _postgres_disposable()
    with module.disposable_database("head") as lab:
        if lab.engine.dialect.name != "postgresql":
            pytest.fail("API tests were not bound to PostgreSQL")
        yield lab


@pytest.fixture
def session_factory(request):
    if _postgres_api_requested():
        lab = request.getfixturevalue("_postgres_api_lab")
        if lab.engine.dialect.name != "postgresql":
            pytest.fail("API tests were not bound to PostgreSQL")
        _clear_disposable_database(lab.engine, lab.name)
        factory = sessionmaker(
            bind=lab.engine,
            autocommit=False,
            autoflush=False,
        )
        yield factory
        _clear_disposable_database(lab.engine, lab.name)
        return

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )
    yield factory
    engine.dispose()


@pytest.fixture
def db(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def api(session_factory, monkeypatch):
    async def idle_monitor():
        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            return

    monkeypatch.setattr(
        "app.main.device_monitor",
        idle_monitor,
    )

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
