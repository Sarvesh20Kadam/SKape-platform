from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TelemetryCreate(BaseModel):
    temperature: float | None = Field(
        default=None,
        ge=-50,
        le=150,
        description="Temperature in degrees Celsius",
    )

    sensor_1: float | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="Sensor 1 reading",
    )

    sensor_2: float | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="Sensor 2 reading",
    )

    sensor_3: float | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="Sensor 3 reading",
    )


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