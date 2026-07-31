from datetime import datetime

from pydantic import BaseModel, EmailStr


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = "employee"


class InvitationResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    status: str
    organization_id: int
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class InvitationAccept(BaseModel):
    token: str