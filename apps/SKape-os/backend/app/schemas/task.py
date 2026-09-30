from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_STATUSES = {
    "todo",
    "in_progress",
    "completed",
    "cancelled",
}

ALLOWED_PRIORITIES = {
    "low",
    "medium",
    "high",
    "urgent",
}


class TaskBase(BaseModel):
    title: str = Field(
        min_length=2,
        max_length=200,
    )

    description: Optional[str] = Field(
        default=None,
        max_length=2000,
    )

    priority: str = "medium"

    due_date: Optional[datetime] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()

        if len(value) < 2:
            raise ValueError(
                "Task title must contain at least 2 characters."
            )

        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        value = value.lower().strip()

        if value not in ALLOWED_PRIORITIES:
            raise ValueError(
                "Invalid task priority."
            )

        return value


class TaskCreate(TaskBase):
    project_id: int

    assigned_to: Optional[int] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=200,
    )

    description: Optional[str] = Field(
        default=None,
        max_length=2000,
    )

    status: Optional[str] = None

    priority: Optional[str] = None

    due_date: Optional[datetime] = None

    assigned_to: Optional[int] = None

    project_id: Optional[int] = None

    @field_validator("title")
    @classmethod
    def validate_title(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        value = value.strip()

        if len(value) < 2:
            raise ValueError(
                "Task title must contain at least 2 characters."
            )

        return value

    @field_validator("status")
    @classmethod
    def validate_status(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        value = value.lower().strip()

        if value not in ALLOWED_STATUSES:
            raise ValueError(
                "Invalid task status."
            )

        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        value = value.lower().strip()

        if value not in ALLOWED_PRIORITIES:
            raise ValueError(
                "Invalid task priority."
            )

        return value


class TaskResponse(BaseModel):
    id: int

    title: str

    description: Optional[str]

    priority: str

    due_date: Optional[datetime]

    status: str

    project_id: int

    assigned_to: Optional[int]

    organization_id: int

    alert_id: Optional[int]

    created_at: datetime

    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
