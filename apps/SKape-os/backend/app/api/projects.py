from typing import List

from fastapi import APIRouter, HTTPException

from app.schemas.project import ProjectCreate, ProjectResponse
from app.services.project_service import (
    create_project,
    get_projects,
    get_project_by_id,
)

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


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int):
    project = get_project_by_id(project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return project