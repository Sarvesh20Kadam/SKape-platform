from fastapi import FastAPI

from app.api.root import router as root_router
from app.api.health import router as health_router
from app.core.config import settings
from app.api.version import router as version_router
from app.api.projects import router as projects_router
from app.api import users
from app.api.organizations import router as organizations_router
from app.api.invitations import router as invitations_router
from app.api.tasks import router as tasks_router
from app.api.dashboard import router as dashboard_router
from app.api.comments import router as comments_router


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION
)
app.include_router(
    health_router,
    prefix="/api/v1"
)

app.include_router(
    version_router,
    prefix="/api/v1"
)
app.include_router(
    projects_router,
    prefix="/api/v1"
)
app.include_router(
    users.router,
    prefix="/api/v1/users",
    tags=["Users"]
)
app.include_router(
    organizations_router,
    prefix="/api/v1"
)
app.include_router(
    invitations_router,
    prefix="/api/v1"
)
app.include_router(
    tasks_router,
    prefix="/api/v1"
)
app.include_router(
    dashboard_router,
    prefix="/api/v1"
)
app.include_router(
    comments_router,
    prefix="/api/v1"
)