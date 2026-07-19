from fastapi import FastAPI

from app.api.root import router as root_router
from app.api.health import router as health_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION
)

app.include_router(root_router)
app.include_router(health_router)