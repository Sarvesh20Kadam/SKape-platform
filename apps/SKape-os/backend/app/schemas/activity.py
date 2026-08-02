from datetime import datetime

from pydantic import BaseModel


class ActivityCreate(BaseModel):
    action: str
    entity: str
    entity_id: int


class ActivityResponse(BaseModel):
    id: int
    action: str
    entity: str
    entity_id: int
    user_id: int
    organization_id: int
    created_at: datetime

    class Config:
        from_attributes = True