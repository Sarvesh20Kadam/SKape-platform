from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertResponse(BaseModel):
    id: int
    device_id: int
    organization_id: int

    severity: str
    alert_type: str
    title: str
    message: str

    is_resolved: bool
    resolved_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )