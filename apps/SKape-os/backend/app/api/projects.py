from typing import List

from fastapi import APIRouter, HTTPException
from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud.project import (
    create_project as db_create_project,
    get_projects as db_get_projects,
    get_project_by_id as db_get_project_by_id,
    update_project as db_update_project,
    delete_project as db_delete_project,
)

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
def create(
    project: ProjectCreate,
    db: Session = Depends(get_db)
):
    return db_create_project(db, project)


@router.get("/", response_model=List[ProjectResponse])
def get_all_projects(
    db: Session = Depends(get_db)
):
    return db_get_projects(db)

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    project = db_get_project_by_id(db, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return project
    

@router.put("/{project_id}", response_model=ProjectResponse)
def update(
    project_id: int,
    project: ProjectUpdate,
    db: Session = Depends(get_db)
):
    updated = db_update_project(
        db,
        project_id,
        project
    )

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return updated
    
    
@router.delete("/{project_id}", response_model=ProjectResponse)
def delete(
    project_id: int,
    db: Session = Depends(get_db)
):
    deleted = db_delete_project(db, project_id)

    if deleted is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return deleted