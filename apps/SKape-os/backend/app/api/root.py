from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/")
def root():
    return {
        "product": settings.APP_NAME,
        "status": "running",
        "version": settings.VERSION,
    }