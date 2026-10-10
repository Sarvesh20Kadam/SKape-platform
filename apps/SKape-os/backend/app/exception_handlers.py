# NotFoundException and BadRequestException respond with
# {success, message}. Other HTTP errors keep FastAPI's {detail}
# body so existing clients can keep reading detail.
from fastapi import Request
from fastapi.responses import JSONResponse

from app.exceptions import (
    NotFoundException,
    BadRequestException,
)


async def not_found_exception_handler(
    request: Request,
    exc: NotFoundException
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
        },
    )


async def bad_request_exception_handler(
    request: Request,
    exc: BadRequestException
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
        },
    )