from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TelemetryCreate(BaseModel):
    temperature: float | None = None
    sensor_1: float | None = None
    sensor_2: float | None = None
    sensor_3: float | None = None


class TelemetryResponse(BaseModel):
    id: int
    device_id: int

    temperature: float | None
    sensor_1: float | None
    sensor_2: float | None
    sensor_3: float | None

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )