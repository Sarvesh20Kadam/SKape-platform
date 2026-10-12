import asyncio
import importlib.util
import json
import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.api.health import readiness
from app.core.config import settings
from app.main import app
from app.schema_revision import (
    SchemaRevisionError,
    expected_schema_revisions,
    schema_revisions_match,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_HEAD = "f6b1c0a84e22"
SECRET_URL = (
    "postgresql://migrator:secret-value@127.0.0.1:9/hidden"
)
_URL = os.environ.get("SKAPE_TEST_DATABASE_URL", "").strip()
_REQUIRE = os.environ.get("SKAPE_REQUIRE_POSTGRES") == "1"
needs_postgres = pytest.mark.skipif(
    not _URL and not _REQUIRE,
    reason="SKAPE_TEST_DATABASE_URL is not set",
)


@pytest.fixture
def quiet_monitor(monkeypatch):
    async def idle():
        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            return

    monkeypatch.setattr("app.main.device_monitor", idle)


def _postgres_lab():
    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.fail(
            "schema readiness tests must run serially"
        )
    if not _URL:
        pytest.fail("SKAPE_TEST_DATABASE_URL is required")
    path = Path(__file__).with_name(
        "test_device_monitor_postgres.py"
    )
    spec = importlib.util.spec_from_file_location(
        "skape_postgres_disposable",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _head_parent():
    heads = expected_schema_revisions()
    assert heads == frozenset({REPOSITORY_HEAD})
    script = ScriptDirectory.from_config(
        Config(str(BACKEND_ROOT / "alembic.ini"))
    )
    parent = script.get_revision(REPOSITORY_HEAD).down_revision
    assert isinstance(parent, str) and parent
    return parent


def _write_revision(directory, revision, down_revision):
    down = "None" if down_revision is None else repr(down_revision)
    (directory / f"{revision}.py").write_text(
        f'revision = "{revision}"\n'
        f"down_revision = {down}\n",
        encoding="utf-8",
    )


def _script_directory(tmp_path, revisions):
    versions = tmp_path / "alembic" / "versions"
    versions.mkdir(parents=True)
    for revision, down in revisions:
        _write_revision(versions, revision, down)
    ini = tmp_path / "alembic.ini"
    ini.write_text(
        "[alembic]\n"
        "script_location = %(here)s/alembic\n"
        "sqlalchemy.url =\n",
        encoding="utf-8",
    )
    return ini


class _TrackingSession:
    def __init__(self, session):
        self.session = session
        self.closed = False

    def execute(self, statement, *args, **kwargs):
        return self.session.execute(statement, *args, **kwargs)

    def close(self):
        self.closed = True
        self.session.close()


def _bind_health(monkeypatch, engine):
    factory = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )
    opened = []

    def open_session():
        tracked = _TrackingSession(factory())
        opened.append(tracked)
        return tracked

    monkeypatch.setenv("SKAPE_ENV", "production")
    monkeypatch.setattr("app.api.health.SessionLocal", open_session)
    return opened


@contextmanager
def _health_errors():
    """Capture health errors after Alembic replaces the root handlers."""

    records = []
    handler = logging.Handler()
    handler.setLevel(logging.ERROR)

    def _emit(record):
        records.append(record)

    handler.emit = _emit
    logger = logging.getLogger("skape.health")
    logger.addHandler(handler)
    try:
        yield records
    finally:
        logger.removeHandler(handler)


def _request(client, request_id):
    live = client.get("/api/v1/health/")
    ready = client.get(
        "/api/v1/health/ready",
        headers={"X-Request-ID": request_id},
    )
    return live, ready


def test_repository_has_one_alembic_head():
    assert expected_schema_revisions() == frozenset(
        {REPOSITORY_HEAD}
    )


def test_revision_discovery_does_not_change_sys_path(tmp_path):
    original = Path.cwd()
    assert tmp_path.resolve() != BACKEND_ROOT.resolve()
    try:
        os.chdir(tmp_path)
        before = list(sys.path)
        first = expected_schema_revisions()
        after_first = list(sys.path)
        second = expected_schema_revisions()
        after_second = list(sys.path)
    finally:
        os.chdir(original)
    assert after_first == before
    assert after_second == before
    assert first == frozenset({REPOSITORY_HEAD})
    assert second == first


def test_revision_comparison_requires_every_head():
    head = REPOSITORY_HEAD
    parent = "e3a91c7b2d44"
    assert schema_revisions_match([head], [head])
    assert schema_revisions_match([head, head], {head})
    assert not schema_revisions_match([parent], [head])
    assert not schema_revisions_match([], [head])
    assert not schema_revisions_match([head, parent], [head])
    assert schema_revisions_match(
        ["left00000001", "right0000001"],
        ["right0000001", "left00000001"],
    )
    assert not schema_revisions_match(
        ["left00000001"],
        ["left00000001", "right0000001"],
    )
    assert not schema_revisions_match([], [])


def test_multiple_script_heads_are_all_required(tmp_path):
    ini = _script_directory(
        tmp_path,
        [
            ("base00000001", None),
            ("left00000001", "base00000001"),
            ("right0000001", "base00000001"),
        ],
    )
    expected = expected_schema_revisions(ini)
    assert expected == frozenset(
        {"left00000001", "right0000001"}
    )
    assert schema_revisions_match(expected, expected)
    assert not schema_revisions_match(
        ["left00000001"],
        expected,
    )


def test_script_directory_without_a_head_is_rejected(tmp_path):
    versions = tmp_path / "alembic" / "versions"
    versions.mkdir(parents=True)
    ini = tmp_path / "alembic.ini"
    ini.write_text(
        "[alembic]\n"
        "script_location = %(here)s/alembic\n",
        encoding="utf-8",
    )
    with pytest.raises(SchemaRevisionError, match="no head"):
        expected_schema_revisions(ini)


def test_missing_alembic_configuration_is_rejected(tmp_path):
    with pytest.raises(
        SchemaRevisionError,
        match="unavailable",
    ):
        expected_schema_revisions(tmp_path / "missing.ini")


def test_development_readiness_checks_connectivity_only(
    monkeypatch,
):
    statements = []

    class OneQuery:
        def __init__(self):
            self.closed = False

        def execute(self, statement):
            statements.append(str(statement))
            if len(statements) > 1:
                raise AssertionError(
                    "development readiness queried the schema"
                )

        def close(self):
            self.closed = True

    session = OneQuery()
    monkeypatch.delenv("SKAPE_ENV", raising=False)
    monkeypatch.setattr(
        "app.api.health.SessionLocal",
        lambda: session,
    )
    body = readiness(
        SimpleNamespace(state=SimpleNamespace(request_id="dev-1"))
    )
    assert body["status"] == "ready"
    assert body["service"] == settings.APP_NAME
    assert body["version"] == settings.VERSION
    assert set(body) == {"status", "service", "version"}
    assert statements == ["SELECT 1"]
    assert session.closed


def test_production_connection_failure_is_generic(
    quiet_monitor,
    monkeypatch,
    caplog,
):
    class Broken:
        def __init__(self):
            self.closed = False

        def execute(self, *_args, **_kwargs):
            raise OperationalError(
                "SELECT 1",
                {},
                Exception(f"connection to {SECRET_URL} failed"),
            )

        def close(self):
            self.closed = True

    broken = Broken()
    monkeypatch.setenv("SKAPE_ENV", "production")
    monkeypatch.setattr(
        "app.api.health.SessionLocal",
        lambda: broken,
    )
    with caplog.at_level("ERROR", logger="skape"):
        with TestClient(app) as client:
            live, ready = _request(client, "ready-down")
    assert live.status_code == 200
    assert live.json()["status"] == "healthy"
    assert ready.status_code == 503
    assert ready.json() == {"status": "unavailable"}
    assert ready.headers["x-request-id"] == "ready-down"
    assert broken.closed
    assert "secret-value" not in ready.text
    assert "postgresql://" not in ready.text
    assert "secret-value" not in caplog.text
    assert "postgresql://" not in caplog.text
    assert "[redacted-url]" in caplog.text


@needs_postgres
def test_production_readiness_rejects_a_missing_version_table(
    quiet_monitor,
    monkeypatch,
    caplog,
):
    _postgres_ready = _postgres_lab()
    with _postgres_ready.disposable_database(None) as lab:
        with lab.engine.connect() as connection:
            assert connection.execute(
                text("SELECT current_database()")
            ).scalar() == lab.name
            assert connection.execute(
                text(
                    "SELECT to_regclass('public.alembic_version')"
                )
            ).scalar() is None
        opened = _bind_health(monkeypatch, lab.engine)
        caplog.clear()
        with caplog.at_level("ERROR", logger="skape"):
            with TestClient(app) as client:
                live, ready = _request(client, "ready-missing")
    assert live.status_code == 200
    assert ready.status_code == 503
    assert ready.json() == {"status": "unavailable"}
    assert ready.headers["x-request-id"] == "ready-missing"
    assert opened[0].closed
    assert "schema version table is missing" in caplog.text
    assert "alembic_version" not in ready.text
    assert "postgresql://" not in ready.text
    assert "postgresql://" not in caplog.text


@needs_postgres
def test_production_readiness_rejects_an_outdated_revision(
    quiet_monitor,
    monkeypatch,
):
    parent = _head_parent()
    _postgres_ready = _postgres_lab()
    with _postgres_ready.disposable_database(parent) as lab:
        with lab.engine.connect() as connection:
            assert connection.execute(
                text("SELECT current_database()")
            ).scalar() == lab.name
            stored = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars().all()
        assert stored == [parent]
        opened = _bind_health(monkeypatch, lab.engine)
        with _health_errors() as records:
            with TestClient(app) as client:
                _live, ready = _request(client, "ready-old")
    messages = " ".join(record.getMessage() for record in records)
    assert ready.status_code == 503
    assert ready.json() == {"status": "unavailable"}
    assert ready.headers["x-request-id"] == "ready-old"
    assert opened[0].closed
    assert "schema revision does not match" in messages
    assert parent not in ready.text
    assert REPOSITORY_HEAD not in ready.text
    assert parent not in messages
    assert REPOSITORY_HEAD not in messages
    assert "postgresql://" not in ready.text
    assert "postgresql://" not in messages


@needs_postgres
def test_production_readiness_accepts_the_head_revision(
    quiet_monitor,
    monkeypatch,
):
    _postgres_ready = _postgres_lab()
    with _postgres_ready.disposable_database("head") as lab:
        with lab.engine.connect() as connection:
            assert connection.execute(
                text("SELECT current_database()")
            ).scalar() == lab.name
            stored = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars().all()
        assert stored == [REPOSITORY_HEAD]
        opened = _bind_health(monkeypatch, lab.engine)
        with TestClient(app) as client:
            live, ready = _request(client, "ready-head")
    assert live.status_code == 200
    assert live.json()["status"] == "healthy"
    assert ready.status_code == 200
    body = ready.json()
    assert body == {
        "status": "ready",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
    }
    assert REPOSITORY_HEAD not in ready.text
    assert opened[0].closed
    assert ready.headers["x-request-id"] == "ready-head"


class _Rows:
    def __init__(self, value=None, rows=None):
        self._value = value
        self._rows = [] if rows is None else rows

    def scalar(self):
        return self._value

    def scalars(self):
        rows = self._rows
        return SimpleNamespace(all=lambda: rows)


class _ScriptedSession:
    def __init__(self, steps):
        self.closed = False
        self.statements = []
        self._steps = list(steps)

    def execute(self, statement, *args, **kwargs):
        self.statements.append(str(statement))
        if not self._steps:
            raise AssertionError(str(statement))
        step = self._steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def close(self):
        self.closed = True


def _production_ready(monkeypatch, session, request_id):
    monkeypatch.setenv("SKAPE_ENV", "production")
    monkeypatch.setattr(
        "app.api.health.SessionLocal",
        lambda: session,
    )
    return readiness(
        SimpleNamespace(
            state=SimpleNamespace(request_id=request_id)
        )
    )


def _assert_unavailable(response):
    assert response.status_code == 503
    text = response.body.decode()
    assert json.loads(text) == {"status": "unavailable"}
    assert "postgresql://" not in text
    assert "secret-value" not in text
    assert "server_version_num" not in text


def _head_steps(version):
    return [
        _Rows(1),
        _Rows(version),
        _Rows("alembic_version"),
        _Rows(rows=[REPOSITORY_HEAD]),
    ]


@pytest.mark.parametrize(
    "version",
    [150000, "150004", "159999"],
)
def test_postgresql_15_fails_readiness(monkeypatch, version):
    session = _ScriptedSession([_Rows(1), _Rows(version)])
    response = _production_ready(monkeypatch, session, "pg-15")
    _assert_unavailable(response)
    assert response.headers["x-request-id"] == "pg-15"
    assert session.closed
    assert session.statements == [
        "SELECT 1",
        "SHOW server_version_num",
    ]


@pytest.mark.parametrize(
    "version",
    [160000, "160004", "160010", 169999],
)
def test_postgresql_16_passes_when_the_schema_matches(
    monkeypatch,
    version,
):
    session = _ScriptedSession(_head_steps(version))
    body = _production_ready(monkeypatch, session, "pg-16")
    assert body == {
        "status": "ready",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
    }
    assert session.closed
    assert "SHOW server_version_num" in session.statements
    assert "SELECT version_num FROM alembic_version" in (
        session.statements
    )


@pytest.mark.parametrize(
    "version",
    [170000, "170001", "179999"],
)
def test_postgresql_17_fails_readiness(monkeypatch, version):
    session = _ScriptedSession([_Rows(1), _Rows(version)])
    response = _production_ready(monkeypatch, session, "pg-17")
    _assert_unavailable(response)
    assert session.closed
    assert "alembic_version" not in " ".join(session.statements)


@pytest.mark.parametrize(
    "version",
    [None, "", "   ", "16.10", "abc", True, 16, "10000", b"160000"],
)
def test_malformed_postgresql_version_fails_closed(
    monkeypatch,
    version,
):
    session = _ScriptedSession([_Rows(1), _Rows(version)])
    response = _production_ready(monkeypatch, session, "pg-bad")
    _assert_unavailable(response)
    assert session.closed
    assert "alembic_version" not in " ".join(session.statements)


def test_postgresql_version_query_error_is_generic(
    monkeypatch,
    caplog,
):
    session = _ScriptedSession(
        [
            _Rows(1),
            OperationalError(
                "SHOW server_version_num",
                {},
                Exception(f"connection to {SECRET_URL} failed"),
            ),
        ]
    )
    with caplog.at_level("ERROR", logger="skape"):
        response = _production_ready(
            monkeypatch,
            session,
            "pg-version-down",
        )
    _assert_unavailable(response)
    assert response.headers["x-request-id"] == "pg-version-down"
    assert session.closed
    assert "secret-value" not in caplog.text
    assert "postgresql://" not in caplog.text
    assert "[redacted-url]" in caplog.text


def test_liveness_does_not_query_the_database(
    quiet_monitor,
    monkeypatch,
):
    def forbidden():
        raise AssertionError("liveness opened a database session")

    monkeypatch.setattr("app.api.health.SessionLocal", forbidden)
    with TestClient(app) as client:
        live = client.get("/api/v1/health/")
    assert live.status_code == 200
    assert live.json()["status"] == "healthy"
    assert live.json()["version"] == settings.VERSION


def test_postgresql_16_still_fails_when_the_schema_is_old(
    monkeypatch,
    caplog,
):
    parent = _head_parent()
    session = _ScriptedSession(
        [
            _Rows(1),
            _Rows("160004"),
            _Rows("alembic_version"),
            _Rows(rows=[parent]),
        ]
    )
    with caplog.at_level("ERROR", logger="skape"):
        response = _production_ready(
            monkeypatch,
            session,
            "pg-16-old",
        )
    _assert_unavailable(response)
    assert session.closed
    assert "SHOW server_version_num" in session.statements
    assert "schema revision does not match" in caplog.text
    assert parent not in response.body.decode()
    assert parent not in caplog.text
    assert REPOSITORY_HEAD not in response.body.decode()
    assert REPOSITORY_HEAD not in caplog.text
