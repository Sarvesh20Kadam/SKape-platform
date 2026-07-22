from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str


class ProjectUpdate(BaseModel):
    name: str
    description: str
    status: str


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    status: str