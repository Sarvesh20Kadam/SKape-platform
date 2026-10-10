from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.database import SessionLocal
from app.log_safety import get_logger, redact_sensitive
from app.schemas.health import HealthResponse


logger = get_logger("health")

router = APIRouter(
    prefix="/health",
    tags=["Health"]
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
    except Exception as exc:
        logger.error(
            "readiness check failed request_id=%s error=%s",
            request_id,
            redact_sensitive(f"{type(exc).__name__}: {exc}"),
        )
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable"},
            headers={"X-Request-ID": request_id},
        )
    finally:
        if db is not None:
            db.close()
    return {
        "status": "ready",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
    }
