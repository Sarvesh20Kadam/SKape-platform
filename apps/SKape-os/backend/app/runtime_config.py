"""Runtime switches that must be explicit outside local development.

``SKAPE_ENABLE_API_DOCS``
    Unset, blank, or false keeps ``/docs``, ``/redoc``, and
    ``/openapi.json`` disabled. Set it to ``true``, ``1``, ``yes``, or
    ``on`` to enable them for local development. Any other value is
    rejected before the application starts.

``SKAPE_CORS_ORIGINS``
    Comma-separated browser origins, for example
    ``http://localhost:5173,http://127.0.0.1:5173``. When the variable
    is unset, the local Vite origins are used so development keeps
    working. A wildcard is rejected because credentialed browser
    requests are allowed. Blank or invalid entries are rejected before
    the application starts.
"""

import os
from urllib.parse import urlsplit


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


def cors_origins(raw=None):
    if raw is None:
        raw = os.environ.get("SKAPE_CORS_ORIGINS")
    if raw is None:
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
        origins.append(origin.rstrip("/"))
    return origins
