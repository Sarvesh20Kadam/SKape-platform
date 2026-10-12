import asyncio
import logging
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.health import readiness
from app.core.config import settings
from app.log_safety import redact_sensitive
from app.main import app, create_app
from app.runtime_config import RuntimeConfigError
from app.services.device_monitor import device_monitor


SECRET_URL = (
    "postgresql://migrator:secret-value@127.0.0.1:9/hidden"
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


def _client(application):
    return TestClient(application)


def test_liveness_stays_healthy_when_the_database_is_down(
    quiet_monitor,
    monkeypatch,
):
    def broken():
        raise RuntimeError(SECRET_URL)

    monkeypatch.setattr("app.api.health.SessionLocal", broken)
    with _client(app) as client:
        liveness = client.get("/api/v1/health/")
        readiness_response = client.get("/api/v1/health/ready")
    assert liveness.status_code == 200
    assert liveness.json()["status"] == "healthy"
    assert liveness.json()["version"] == settings.VERSION
    assert readiness_response.status_code == 503
    assert readiness_response.json() == {"status": "unavailable"}
    assert "secret-value" not in readiness_response.text


def test_readiness_reports_a_live_database(api):
    response = api.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["service"] == settings.APP_NAME
    assert body["version"] == settings.VERSION


def test_readiness_failure_is_logged_without_the_database_url(
    quiet_monitor,
    monkeypatch,
    caplog,
):
    class BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise OperationalError(
                "SELECT 1",
                {},
                Exception(f"connection to {SECRET_URL} failed"),
            )

        def close(self):
            return None

    monkeypatch.setattr(
        "app.api.health.SessionLocal",
        lambda: BrokenSession(),
    )
    with caplog.at_level(logging.INFO, logger="skape"):
        with _client(app) as client:
            response = client.get(
                "/api/v1/health/ready",
                headers={"X-Request-ID": "ready-fail-1"},
            )
    assert response.status_code == 503
    assert response.headers["x-request-id"] == "ready-fail-1"
    assert "ready-fail-1" in caplog.text
    assert "status=503" in caplog.text
    assert "secret-value" not in caplog.text
    assert "postgresql://" not in caplog.text
    assert SECRET_URL not in caplog.text


def test_api_docs_are_disabled_unless_explicitly_enabled(
    quiet_monitor,
    monkeypatch,
):
    monkeypatch.delenv("SKAPE_ENABLE_API_DOCS", raising=False)
    application = create_app()
    assert application.docs_url is None
    assert application.redoc_url is None
    assert application.openapi_url is None
    with _client(application) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404

    monkeypatch.setenv("SKAPE_ENABLE_API_DOCS", "true")
    enabled = create_app()
    with _client(enabled) as client:
        document = client.get("/openapi.json")
        assert document.status_code == 200
        assert document.json()["info"]["title"] == settings.APP_NAME
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200


def test_malformed_api_docs_setting_is_rejected(monkeypatch):
    monkeypatch.setenv("SKAPE_ENABLE_API_DOCS", "maybe")
    with pytest.raises(RuntimeConfigError, match="true or false"):
        create_app()


def test_configured_cors_origin_is_allowed_and_unknown_is_not(
    quiet_monitor,
    monkeypatch,
):
    monkeypatch.setenv(
        "SKAPE_CORS_ORIGINS",
        "http://allowed.example",
    )
    application = create_app()
    with _client(application) as client:
        allowed = client.get(
            "/api/v1/health/",
            headers={"Origin": "http://allowed.example"},
        )
        unknown = client.get(
            "/api/v1/health/",
            headers={"Origin": "http://unknown.example"},
        )
    assert allowed.status_code == 200
    assert (
        allowed.headers["access-control-allow-origin"]
        == "http://allowed.example"
    )
    assert unknown.status_code == 200
    assert (
        unknown.headers.get("access-control-allow-origin")
        != "http://unknown.example"
    )
    assert unknown.headers.get("access-control-allow-origin") != "*"


@pytest.mark.parametrize(
    "value",
    ["*", "http://allowed.example, *", "not-an-origin", "   "],
)
def test_malformed_cors_configuration_is_rejected(monkeypatch, value):
    monkeypatch.setenv("SKAPE_CORS_ORIGINS", value)
    with pytest.raises(RuntimeConfigError):
        create_app()


def test_local_development_origins_remain_available(
    quiet_monitor,
    monkeypatch,
):
    monkeypatch.delenv("SKAPE_CORS_ORIGINS", raising=False)
    application = create_app()
    with _client(application) as client:
        response = client.get(
            "/api/v1/health/",
            headers={"Origin": "http://localhost:5173"},
        )
    assert (
        response.headers["access-control-allow-origin"]
        == "http://localhost:5173"
    )


def test_root_version_comes_from_the_application_settings(api):
    body = api.get("/").json()
    assert body["product"] == settings.APP_NAME
    assert body["version"] == settings.VERSION
    version = api.get("/api/v1/version/")
    assert version.status_code == 200
    assert version.json()["version"] == settings.VERSION


def test_request_id_is_propagated_and_sensitive_headers_are_not_logged(
    api,
    caplog,
):
    with caplog.at_level(logging.INFO, logger="skape"):
        response = api.get(
            "/api/v1/health/",
            headers={
                "X-Request-ID": "req-123",
                "Authorization": "Bearer device-secret",
                "X-Device-Secret": "device-secret",
            },
        )
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-123"
    assert "request_id=req-123" in caplog.text
    assert "path=/api/v1/health/" in caplog.text
    assert "status=200" in caplog.text
    assert "device-secret" not in caplog.text
    assert "Bearer" not in caplog.text


def test_generated_request_id_replaces_an_unsafe_header(api, caplog):
    with caplog.at_level(logging.INFO, logger="skape"):
        response = api.get(
            "/api/v1/health/",
            headers={"X-Request-ID": "bad id"},
        )
    request_id = response.headers["x-request-id"]
    uuid.UUID(request_id)
    assert request_id != "bad id"
    assert "bad id" not in caplog.text
    assert f"request_id={request_id}" in caplog.text


def test_unhandled_error_log_keeps_the_request_id_and_hides_secrets(
    quiet_monitor,
    caplog,
):
    application = create_app()

    @application.get("/api/v1/observability-boom")
    def explode():
        raise RuntimeError(
            f"connection to {SECRET_URL} failed "
            "token=invite-token"
        )

    with caplog.at_level(logging.ERROR, logger="skape"):
        with _client(application) as client:
            response = client.get(
                "/api/v1/observability-boom",
                headers={
                    "X-Request-ID": "err-req-1",
                    "Authorization": "Bearer device-secret",
                    "X-Device-Secret": "device-secret",
                },
            )
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["x-request-id"] == "err-req-1"
    assert "secret-value" not in response.text
    assert "request_id=err-req-1" in caplog.text
    assert "path=/api/v1/observability-boom" in caplog.text
    assert "secret-value" not in caplog.text
    assert "postgresql://" not in caplog.text
    assert "invite-token" not in caplog.text
    assert "device-secret" not in caplog.text


def test_monitor_failure_log_redacts_the_database_url(
    monkeypatch,
    caplog,
):
    def fail(_db):
        raise RuntimeError(
            f"cycle failed for {SECRET_URL} password=db-password"
        )

    async def stop(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(
        "app.services.device_monitor.run_monitor_cycle",
        fail,
    )
    monkeypatch.setattr(
        "app.services.device_monitor.asyncio.sleep",
        stop,
    )
    closed = []

    class RecordingSession:
        def close(self):
            closed.append(True)

    monkeypatch.setattr(
        "app.services.device_monitor.SessionLocal",
        lambda: RecordingSession(),
    )
    with caplog.at_level(logging.ERROR, logger="skape"):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(device_monitor())
    assert closed == [True]
    assert "secret-value" not in caplog.text
    assert "db-password" not in caplog.text
    assert "postgresql://" not in caplog.text
    assert "[redacted-url]" in caplog.text
    assert redact_sensitive(SECRET_URL) == "[redacted-url]"


def test_readiness_function_uses_select(monkeypatch):
    statements = []

    class RecordingSession:
        def execute(self, statement):
            statements.append(str(statement))
            return None

        def close(self):
            return None

    monkeypatch.setattr(
        "app.api.health.SessionLocal",
        lambda: RecordingSession(),
    )
    body = readiness(
        SimpleNamespace(state=SimpleNamespace(request_id="select-1"))
    )
    assert body["status"] == "ready"
    assert statements == ["SELECT 1"]
