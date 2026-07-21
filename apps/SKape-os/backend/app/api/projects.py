from typing import List
from fastapi import APIRouter

from app.schemas.project import ProjectCreate, ProjectResponse
from app.services.project_service import create_project, get_projects

router = APIRouter(
    prefix="/projects",
    tags=["Projects"]
)


@router.post("/", response_model=ProjectResponse)
def create(project: ProjectCreate):
    return create_project(project)


@router.get("/", response_model=List[ProjectResponse])
def get_all_projects():
    return get_projects()