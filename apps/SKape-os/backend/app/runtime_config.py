"""Runtime switches that must be explicit outside local development.

``SKAPE_ENV``
    Unset, blank, or ``development`` keeps the local workflow.
    ``production`` requires a PostgreSQL ``DATABASE_URL``, an explicit
    HTTPS ``SKAPE_CORS_ORIGINS`` list, and disabled API documentation.
    Any other value is rejected. The production database check parses
    the URL and does not open a connection.

``SKAPE_ENABLE_API_DOCS``
    Unset, blank, or false keeps ``/docs``, ``/redoc``, and
    ``/openapi.json`` disabled. Set it to ``true``, ``1``, ``yes``, or
    ``on`` to enable them for local development. Any other value is
    rejected before the application starts. Production rejects every
    value that would enable documentation.

``SKAPE_CORS_ORIGINS``
    Comma-separated browser origins, for example
    ``http://localhost:5173,http://127.0.0.1:5173``. When the variable
    is unset, the local Vite origins are used so development keeps
    working. A wildcard is rejected because credentialed browser
    requests are allowed. Blank or invalid entries are rejected before
    the application starts. Production requires the variable to be set,
    and every origin must use HTTPS.
"""

import os
from urllib.parse import urlsplit

from sqlalchemy.engine.url import make_url


class RuntimeConfigError(RuntimeError):
    """An environment setting cannot be used safely."""


_DOCS_ENABLED = {"1", "true", "yes", "on"}
_DOCS_DISABLED = {"0", "false", "no", "off"}
_LOCAL_DEV_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
)
_POSTGRES_DRIVERS = {"postgresql", "postgres"}


def runtime_environment(raw=None):
    """Return ``production`` or ``development``.

    Unrecognized names are rejected so a typo cannot skip the
    production checks.
    """

    if raw is None:
        raw = os.environ.get("SKAPE_ENV")
    if raw is None or not str(raw).strip():
        return "development"
    value = str(raw).strip().lower()
    if value == "production":
        return "production"
    if value == "development":
        return "development"
    raise RuntimeConfigError(
        "SKAPE_ENV must be production or development."
    )


def validate_production_database(raw=None):
    """Reject a non-PostgreSQL URL without opening a connection."""

    if raw is None:
        raw = os.environ.get("DATABASE_URL")
    if raw is None or not str(raw).strip():
        raise RuntimeConfigError(
            "DATABASE_URL must be a PostgreSQL URL in production."
        )
    candidate = str(raw).strip()
    try:
        parsed = make_url(candidate)
    except Exception:
        raise RuntimeConfigError(
            "DATABASE_URL must be a PostgreSQL URL in production."
        ) from None
    driver = (parsed.drivername or "").split("+", 1)[0]
    if driver == "sqlite":
        raise RuntimeConfigError(
            "SQLite cannot be used when SKAPE_ENV is production."
        )
    if driver not in _POSTGRES_DRIVERS:
        raise RuntimeConfigError(
            "DATABASE_URL must use PostgreSQL when "
            "SKAPE_ENV is production."
        )
    if not parsed.database:
        raise RuntimeConfigError(
            "DATABASE_URL must name a PostgreSQL database "
            "in production."
        )


def api_docs_enabled(raw=None):
    if raw is None:
        raw = os.environ.get("SKAPE_ENABLE_API_DOCS")
    if raw is None or not str(raw).strip():
        return False
    value = str(raw).strip().lower()
    if value in _DOCS_ENABLED:
        return True
    if value in _DOCS_DISABLED:
        return False
    raise RuntimeConfigError(
        "SKAPE_ENABLE_API_DOCS must be true or false."
    )


def cors_origins(raw=None, *, require_https=False):
    if raw is None:
        raw = os.environ.get("SKAPE_CORS_ORIGINS")
    if raw is None:
        if require_https:
            raise RuntimeConfigError(
                "SKAPE_CORS_ORIGINS must be set in production."
            )
        return list(_LOCAL_DEV_ORIGINS)
    text = str(raw).strip()
    if not text:
        raise RuntimeConfigError(
            "SKAPE_CORS_ORIGINS must list at least one origin."
        )
    origins = []
    for part in text.split(","):
        origin = part.strip()
        if not origin:
            raise RuntimeConfigError(
                "SKAPE_CORS_ORIGINS contains an empty origin."
            )
        if "*" in origin:
            raise RuntimeConfigError(
                "SKAPE_CORS_ORIGINS cannot use a wildcard "
                "with credentials."
            )
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise RuntimeConfigError(
                "SKAPE_CORS_ORIGINS contains an invalid origin."
            )
        if require_https and parsed.scheme != "https":
            raise RuntimeConfigError(
                "SKAPE_CORS_ORIGINS must use HTTPS in production."
            )
        origins.append(origin.rstrip("/"))
    return origins


def resolve_runtime_configuration():
    """Validate startup settings and return docs and CORS choices.

    Production validation parses configuration only. It does not create
    an engine or open a database connection. JWT signing rules stay in
    ``validate_signing_configuration``.
    """

    from app.security import (
        ALGORITHM,
        SECRET_KEY,
        validate_signing_configuration,
    )

    validate_signing_configuration(SECRET_KEY, ALGORITHM)
    if runtime_environment() != "production":
        return api_docs_enabled(), cors_origins()

    validate_production_database()
    if os.environ.get("SKAPE_CORS_ORIGINS") is None:
        raise RuntimeConfigError(
            "SKAPE_CORS_ORIGINS must be set in production."
        )
    origins = cors_origins(require_https=True)
    if api_docs_enabled():
        raise RuntimeConfigError(
            "API documentation must be disabled in production."
        )
    return False, origins
