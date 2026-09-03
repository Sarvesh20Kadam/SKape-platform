from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeviceCredentialResponse(BaseModel):
    id: int
    device_id: int
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None

    model_config = ConfigDict(
        from_attributes=True,
    )


class DeviceCredentialProvisionResponse(BaseModel):
    credential: DeviceCredentialResponse
    device_secret: str