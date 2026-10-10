import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.runtime_config import RuntimeConfigError


POSTGRES_URL = (
    "postgresql+psycopg2://migrator:unused@127.0.0.1:9/phase4c_gate"
)
POSTGRES_ALIAS_URL = (
    "postgres://migrator:unused@127.0.0.1:9/phase4c_gate"
)
HTTPS_ORIGIN = "https://app.example"
SECOND_ORIGIN = "https://admin.example"


@pytest.fixture
def quiet_monitor(monkeypatch):
    async def idle():
        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            return

    monkeypatch.setattr("app.main.device_monitor", idle)


def _production(
    monkeypatch,
    *,
    url=POSTGRES_URL,
    origins=HTTPS_ORIGIN,
    docs=None,
):
    monkeypatch.setenv("SKAPE_ENV", "production")
    if url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", url)
    if origins is None:
        monkeypatch.delenv("SKAPE_CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("SKAPE_CORS_ORIGINS", origins)
    if docs is None:
        monkeypatch.delenv("SKAPE_ENABLE_API_DOCS", raising=False)
    else:
        monkeypatch.setenv("SKAPE_ENABLE_API_DOCS", docs)


def _forbid_database(monkeypatch):
    attempts = []

    def forbidden(*_args, **_kwargs):
        attempts.append(True)
        raise AssertionError("database connection attempted")

    monkeypatch.setattr("app.database.create_engine", forbidden)
    monkeypatch.setattr(
        "app.database.create_database_engine",
        forbidden,
    )
    monkeypatch.setattr("app.database.engine.connect", forbidden)
    monkeypatch.setattr("app.database.SessionLocal", forbidden)
    monkeypatch.setattr("sqlalchemy.create_engine", forbidden)
    return attempts


@pytest.mark.parametrize(
    "url",
    ["sqlite://", "sqlite:///phase4c.db"],
)
def test_production_rejects_sqlite(monkeypatch, url):
    _production(monkeypatch, url=url)
    attempts = _forbid_database(monkeypatch)
    with pytest.raises(RuntimeConfigError, match="SQLite") as caught:
        create_app()
    assert attempts == []
    assert "sqlite:" not in str(caught.value)


def test_production_rejects_an_unsupported_driver(monkeypatch):
    _production(
        monkeypatch,
        url="mysql://migrator:gate-secret@127.0.0.1:9/hidden",
    )
    attempts = _forbid_database(monkeypatch)
    with pytest.raises(
        RuntimeConfigError,
        match="PostgreSQL",
    ) as caught:
        create_app()
    message = str(caught.value)
    assert attempts == []
    assert "gate-secret" not in message
    assert "mysql://" not in message


def test_production_rejects_a_postgresql_url_without_a_database(
    monkeypatch,
):
    _production(
        monkeypatch,
        url="postgresql://migrator:unused@127.0.0.1:9",
    )
    attempts = _forbid_database(monkeypatch)
    with pytest.raises(
        RuntimeConfigError,
        match="name a PostgreSQL database",
    ):
        create_app()
    assert attempts == []


@pytest.mark.parametrize("origins", [None, "", "   "])
def test_production_rejects_unset_or_blank_cors(monkeypatch, origins):
    _production(monkeypatch, origins=origins)
    attempts = _forbid_database(monkeypatch)
    with pytest.raises(RuntimeConfigError, match="SKAPE_CORS_ORIGINS"):
        create_app()
    assert attempts == []


@pytest.mark.parametrize(
    "origins",
    ["*", "https://*.example.com", "https://app.example, *"],
)
def test_production_rejects_wildcard_origins(monkeypatch, origins):
    _production(monkeypatch, origins=origins)
    with pytest.raises(RuntimeConfigError, match="wildcard"):
        create_app()


@pytest.mark.parametrize(
    "origins",
    [
        "http://app.example",
        "http://localhost:5173",
        "https://app.example,http://admin.example",
    ],
)
def test_production_rejects_http_origins(monkeypatch, origins):
    _production(monkeypatch, origins=origins)
    with pytest.raises(RuntimeConfigError, match="HTTPS"):
        create_app()


def test_production_accepts_explicit_https_origins(
    quiet_monitor,
    monkeypatch,
):
    _production(
        monkeypatch,
        origins=f"{HTTPS_ORIGIN}, {SECOND_ORIGIN}",
    )
    attempts = _forbid_database(monkeypatch)
    application = create_app()
    assert attempts == []
    assert application.docs_url is None
    assert application.redoc_url is None
    assert application.openapi_url is None
    with TestClient(application) as client:
        first = client.get(
            "/api/v1/health/",
            headers={"Origin": HTTPS_ORIGIN},
        )
        second = client.get(
            "/api/v1/health/",
            headers={"Origin": SECOND_ORIGIN},
        )
        unknown = client.get(
            "/api/v1/health/",
            headers={"Origin": "https://unknown.example"},
        )
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404
    assert first.status_code == 200
    assert (
        first.headers["access-control-allow-origin"]
        == HTTPS_ORIGIN
    )
    assert (
        second.headers["access-control-allow-origin"]
        == SECOND_ORIGIN
    )
    assert unknown.status_code == 200
    assert (
        unknown.headers.get("access-control-allow-origin")
        != "https://unknown.example"
    )


def test_production_accepts_the_postgres_scheme_alias(monkeypatch):
    _production(monkeypatch, url=POSTGRES_ALIAS_URL)
    attempts = _forbid_database(monkeypatch)
    application = create_app()
    assert attempts == []
    assert application.docs_url is None


@pytest.mark.parametrize(
    "docs",
    ["true", "1", "yes", "on", "TRUE", "Yes"],
)
def test_production_rejects_enabled_api_docs(monkeypatch, docs):
    _production(monkeypatch, docs=docs)
    attempts = _forbid_database(monkeypatch)
    with pytest.raises(
        RuntimeConfigError,
        match="API documentation must be disabled",
    ):
        create_app()
    assert attempts == []


@pytest.mark.parametrize("docs", ["false", "0", "no", "off"])
def test_production_accepts_explicitly_disabled_docs(monkeypatch, docs):
    _production(monkeypatch, docs=docs)
    application = create_app()
    assert application.docs_url is None
    assert application.openapi_url is None


def test_development_configuration_still_starts(
    quiet_monitor,
    monkeypatch,
):
    monkeypatch.delenv("SKAPE_ENV", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.delenv("SKAPE_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("SKAPE_ENABLE_API_DOCS", "true")
    application = create_app()
    with TestClient(application) as client:
        health = client.get(
            "/api/v1/health/",
            headers={"Origin": "http://localhost:5173"},
        )
        document = client.get("/openapi.json")
    assert health.status_code == 200
    assert (
        health.headers["access-control-allow-origin"]
        == "http://localhost:5173"
    )
    assert document.status_code == 200


def test_explicit_development_env_keeps_local_defaults(monkeypatch):
    monkeypatch.setenv("SKAPE_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv(
        "SKAPE_CORS_ORIGINS",
        "http://localhost:5173",
    )
    monkeypatch.delenv("SKAPE_ENABLE_API_DOCS", raising=False)
    application = create_app()
    assert application.docs_url is None


def test_unrecognized_environment_is_rejected(monkeypatch):
    monkeypatch.setenv("SKAPE_ENV", "staging")
    with pytest.raises(RuntimeConfigError, match="SKAPE_ENV"):
        create_app()


def test_production_spelling_cannot_skip_the_gate(monkeypatch):
    _production(monkeypatch, url="sqlite://")
    monkeypatch.setenv("SKAPE_ENV", " Production ")
    attempts = _forbid_database(monkeypatch)
    with pytest.raises(RuntimeConfigError, match="SQLite"):
        create_app()
    assert attempts == []
