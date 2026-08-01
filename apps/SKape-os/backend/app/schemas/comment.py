from datetime import datetime

from pydantic import BaseModel


class CommentCreate(BaseModel):
    content: str
    task_id: int


class CommentUpdate(BaseModel):
    content: str


class CommentResponse(BaseModel):
    id: int
    content: str
    task_id: int
    user_id: int
    organization_id: int
    created_at: datetime

    class Config:
        from_attributes = True