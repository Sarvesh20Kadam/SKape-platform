from pydantic import BaseModel, EmailStr
from typing import Optional


class OrganizationBase(BaseModel):
    name: str
    slug: str
    email: EmailStr
    phone: Optional[str] = None
    website: Optional[str] = None
    logo: Optional[str] = None
    industry: Optional[str] = None
    address: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    logo: Optional[str] = None
    industry: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


class OrganizationResponse(OrganizationBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True