"""Request correlation ids and completion logs.

Logs include the method, path, status, duration, and request id.
They do not include bodies, query strings, or headers.
"""

import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.log_safety import configure_logging, get_logger, redact_sensitive


logger = get_logger("access")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def request_id_from_header(raw):
    if raw and _REQUEST_ID.fullmatch(raw):
        return raw
    return str(uuid.uuid4())


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        configure_logging()
        request_id = request_id_from_header(
            request.headers.get("x-request-id", "")
        )
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error(
                "request failed request_id=%s method=%s path=%s error=%s",
                request_id,
                request.method,
                request.url.path,
                redact_sensitive(f"{type(exc).__name__}: {exc}"),
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
                headers={"X-Request-ID": request_id},
            )
        duration_ms = int((time.perf_counter() - started) * 1000)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request completed request_id=%s method=%s path=%s "
            "status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
