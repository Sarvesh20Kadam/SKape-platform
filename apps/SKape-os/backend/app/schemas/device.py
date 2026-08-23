from datetime import datetime

from pydantic import BaseModel


class DeviceCreate(BaseModel):
    device_id: str
    name: str
    device_type: str
    status: str = "offline"
    asset_id: int | None = None


class DeviceUpdate(BaseModel):
    name: str | None = None
    device_type: str | None = None
    status: str | None = None
    asset_id: int | None = None
    last_seen_at: datetime | None = None
    is_active: bool | None = None


class DeviceResponse(BaseModel):
    id: int
    device_id: str
    name: str
    device_type: str
    status: str
    organization_id: int
    asset_id: int | None
    last_seen_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True