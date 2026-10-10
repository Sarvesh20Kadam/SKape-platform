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
from app.api.alerts import router as alerts_router
from app.api.device_detail import router as device_detail_router
# Register all SQLAlchemy models before application startup.
import app.models

from app.core.config import settings

from app.exceptions import (
    NotFoundException,
    BadRequestException,
)

from app.exception_handlers import (
    not_found_exception_handler,
    bad_request_exception_handler,
)

from app.log_safety import configure_logging, get_logger
from app.request_context import RequestContextMiddleware
from app.runtime_config import api_docs_enabled, cors_origins
from app.services.device_monitor import device_monitor


logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor_task = asyncio.create_task(
        device_monitor()
    )

    logger.info("device monitor task starting")

    try:
        yield

    finally:
        monitor_task.cancel()

        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        logger.info("device monitor stopped")


def create_app():
    configure_logging()
    docs_enabled = api_docs_enabled()
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestContextMiddleware)

    application.add_exception_handler(
        NotFoundException,
        not_found_exception_handler,
    )

    application.add_exception_handler(
        BadRequestException,
        bad_request_exception_handler,
    )

    application.include_router(
        root_router,
    )

    application.include_router(
        health_router,
        prefix="/api/v1",
    )

    application.include_router(
        version_router,
        prefix="/api/v1",
    )

    application.include_router(
        projects_router,
        prefix="/api/v1",
    )

    application.include_router(
        users.router,
        prefix="/api/v1/users",
        tags=["Users"],
    )

    application.include_router(
        organizations_router,
        prefix="/api/v1",
    )

    application.include_router(
        invitations_router,
        prefix="/api/v1",
    )

    application.include_router(
        tasks_router,
        prefix="/api/v1",
    )

    application.include_router(
        assets_router,
        prefix="/api/v1",
    )

    application.include_router(
        dashboard_router,
        prefix="/api/v1",
    )

    application.include_router(
        comments_router,
        prefix="/api/v1",
    )

    application.include_router(
        activity_router,
        prefix="/api/v1",
    )

    application.include_router(
        devices_router,
        prefix="/api/v1",
    )

    application.include_router(
        telemetry_router,
        prefix="/api/v1",
    )

    application.include_router(
        device_health_router,
        prefix="/api/v1",
    )

    application.include_router(
        device_detail_router,
        prefix="/api/v1",
    )

    application.include_router(
        alerts_router,
        prefix="/api/v1",
    )
    return application


app = create_app()