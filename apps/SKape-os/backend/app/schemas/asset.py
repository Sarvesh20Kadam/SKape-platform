from datetime import datetime

from pydantic import BaseModel


class AssetCreate(BaseModel):
    name: str
    asset_type: str
    description: str | None = None
    location: str | None = None
    status: str = "active"
    assigned_to: int | None = None


class AssetUpdate(BaseModel):
    name: str | None = None
    asset_type: str | None = None
    description: str | None = None
    location: str | None = None
    status: str | None = None
    assigned_to: int | None = None
    is_active: bool | None = None


class AssetResponse(BaseModel):
    id: int
    name: str
    asset_type: str
    description: str | None
    location: str | None
    status: str
    organization_id: int
    assigned_to: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True