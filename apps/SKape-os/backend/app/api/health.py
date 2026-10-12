from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.database import SessionLocal
from app.log_safety import get_logger, redact_sensitive
from app.runtime_config import runtime_environment
from app.schema_revision import (
    expected_schema_revisions,
    schema_revisions_match,
)
from app.schemas.health import HealthResponse


logger = get_logger("health")

router = APIRouter(
    prefix="/health",
    tags=["Health"]
)


class SchemaCheckError(RuntimeError):
    """A safe readiness failure. The message has no connection details."""


def _postgresql_major(raw):
    """Return a PostgreSQL major version from ``server_version_num``.

    ``SHOW server_version_num`` returns the numeric form as text.
    PostgreSQL 10 and later encode the major version in the ten-thousands
    place, so 16.4 is 160004 and 16.10 is 160010. Smaller or non-decimal
    values fail closed. The raw value is omitted from the error.
    """

    if isinstance(raw, bool) or raw is None:
        raise SchemaCheckError("PostgreSQL version is unavailable")
    if isinstance(raw, int):
        number = raw
    elif isinstance(raw, str) and raw.strip().isdecimal():
        number = int(raw.strip())
    else:
        raise SchemaCheckError("PostgreSQL version is unavailable")
    if number < 100000:
        raise SchemaCheckError("PostgreSQL version is unavailable")
    return number // 10000


def _require_postgresql_16(db):
    """Reject a server whose major version is not 16.

    Uses the readiness session. It does not open another connection
    and does not migrate.
    """

    raw = db.execute(text("SHOW server_version_num")).scalar()
    if _postgresql_major(raw) != 16:
        raise SchemaCheckError("PostgreSQL major version is not 16")


def _require_current_schema(db):
    """Reject a database that is not exactly at the script heads.

    Reads the version table only. It does not apply migrations.
    """

    present = db.execute(
        text("SELECT to_regclass('public.alembic_version')")
    ).scalar()
    if present is None:
        raise SchemaCheckError("schema version table is missing")
    rows = db.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalars().all()
    if not schema_revisions_match(rows, expected_schema_revisions()):
        raise SchemaCheckError("schema revision does not match")


def _unavailable(request_id):
    return JSONResponse(
        status_code=503,
        content={"status": "unavailable"},
        headers={"X-Request-ID": request_id},
    )


@router.get("/", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="healthy",
        service=settings.APP_NAME,
        version=settings.VERSION
    )


@router.get("/ready")
def readiness(request: Request):
    request_id = getattr(request.state, "request_id", "-")
    db = None
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        # Local databases are created without Alembic. Production
        # requires PostgreSQL 16 and the script heads. It does not
        # migrate from here.
        if runtime_environment() == "production":
            _require_postgresql_16(db)
            _require_current_schema(db)
    except Exception as exc:
        logger.error(
            "readiness check failed request_id=%s error=%s",
            request_id,
            redact_sensitive(f"{type(exc).__name__}: {exc}"),
        )
        return _unavailable(request_id)
    finally:
        if db is not None:
            db.close()
    return {
        "status": "ready",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
    }
