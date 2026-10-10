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
        # requires the script heads and does not migrate from here.
        if runtime_environment() == "production":
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
