from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CommentCreate(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )
    task_id: int

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "Comment content cannot be empty."
            )

        return value


class CommentUpdate(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "Comment content cannot be empty."
            )

        return value


class CommentResponse(BaseModel):
    id: int
    content: str
    task_id: int
    user_id: int
    organization_id: int
    created_at: datetime

    class Config:
        from_attributes = True