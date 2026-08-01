from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    due_date: Optional[datetime] = None


class TaskCreate(TaskBase):
    project_id: int
    assigned_to: Optional[int] = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: datetime | None = None
    assigned_to: int | None = None

class TaskResponse(TaskBase):
    id: int
    status: str
    project_id: int
    assigned_to: Optional[int]
    organization_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True