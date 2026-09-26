from datetime import datetime

from pydantic import BaseModel


class DeviceHealthResponse(BaseModel):
    status: str
    reason: str

    device_status: str
    last_seen_at: datetime | None

    telemetry_at: datetime | None
    telemetry_age_seconds: float | None

    sensors_available: int
    sensors_total: int
