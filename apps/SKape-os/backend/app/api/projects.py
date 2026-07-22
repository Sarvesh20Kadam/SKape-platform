from typing import List

from fastapi import APIRouter, HTTPException

from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
)
from app.services.project_service import (
    create_project,
    get_projects,
    get_project_by_id,
    update_project,
    delete_project,
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
            detail="Project not found",
        )

    return project
    

@router.put("/{project_id}", response_model=ProjectResponse)
def update(project_id: int, project: ProjectUpdate):
    updated = update_project(project_id, project)

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return updated
    
    
@router.delete("/{project_id}")
def delete(project_id: int):
    deleted = delete_project(project_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    return {
        "message": "Project deleted successfully"
    }