import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.root import router as root_router
from app.api.health import router as health_router
from app.api.version import router as version_router
from app.api.projects import router as projects_router
from app.api import users
from app.api.organizations import router as organizations_router
from app.api.invitations import router as invitations_router
from app.api.tasks import router as tasks_router
from app.api.dashboard import router as dashboard_router
from app.api.comments import router as comments_router
from app.api.activity import router as activity_router
from app.api.assets import router as assets_router
from app.api.devices import router as devices_router
from app.api.telemetry import router as telemetry_router
from app.api.device_health import router as device_health_router

from app.core.config import settings

from app.exceptions import (
    NotFoundException,
    BadRequestException,
)

from app.exception_handlers import (
    not_found_exception_handler,
    bad_request_exception_handler,
)

from app.services.device_monitor import device_monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor_task = asyncio.create_task(
        device_monitor()
    )

    print("[DEVICE MONITOR] Started")

    try:
        yield

    finally:
        monitor_task.cancel()

        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        print("[DEVICE MONITOR] Stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_exception_handler(
    NotFoundException,
    not_found_exception_handler,
)

app.add_exception_handler(
    BadRequestException,
    bad_request_exception_handler,
)


app.include_router(
    root_router,
)

app.include_router(
    health_router,
    prefix="/api/v1",
)

app.include_router(
    version_router,
    prefix="/api/v1",
)

app.include_router(
    projects_router,
    prefix="/api/v1",
)

app.include_router(
    users.router,
    prefix="/api/v1/users",
    tags=["Users"],
)

app.include_router(
    organizations_router,
    prefix="/api/v1",
)

app.include_router(
    invitations_router,
    prefix="/api/v1",
)

app.include_router(
    tasks_router,
    prefix="/api/v1",
)

app.include_router(
    assets_router,
    prefix="/api/v1",
)

app.include_router(
    dashboard_router,
    prefix="/api/v1",
)

app.include_router(
    comments_router,
    prefix="/api/v1",
)

app.include_router(
    activity_router,
    prefix="/api/v1",
)

app.include_router(
    devices_router,
    prefix="/api/v1",
)

app.include_router(
    telemetry_router,
    prefix="/api/v1",
)

app.include_router(
    device_health_router,
    prefix="/api/v1",
)