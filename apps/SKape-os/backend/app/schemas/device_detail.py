from pydantic import BaseModel

from app.schemas.device import DeviceResponse
from app.schemas.device_health import DeviceHealthResponse
from app.schemas.telemetry import TelemetryResponse


class DeviceDetailResponse(BaseModel):
    device: DeviceResponse
    health: DeviceHealthResponse
    latest_telemetry: TelemetryResponse | None