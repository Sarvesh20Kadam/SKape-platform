from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse

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