from fastapi import APIRouter

from app.core.config import settings
from app.schemas.version import VersionResponse

router = APIRouter(
    prefix="/version",
    tags=["Version"]
)


@router.get("/", response_model=VersionResponse)
def version():
    return VersionResponse(
        application=settings.APP_NAME,
        version=settings.VERSION,
        api="v1"
    )