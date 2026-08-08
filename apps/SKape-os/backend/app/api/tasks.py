from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.permissions import require_role

from app.crud.task import (
    create_task as db_create_task,
    get_tasks as db_get_tasks,
    get_task_by_id as db_get_task_by_id,
    update_task as db_update_task,
    delete_task as db_delete_task,
)

from app.schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
)

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"]
)


@router.post("/", response_model=TaskResponse)
def create(
    task: TaskCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager"
        )
    )
):
    try:
        return db_create_task(
            db=db,
            task=task,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.get("/", response_model=List[TaskResponse])
def get_all(
    skip: int = 0,
    limit: int = 10,
    status: str | None = None,
    priority: str | None = None,
    assigned_to: int | None = None,
    project_id: int | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
            "employee"
        )
    )
):

    return db_get_tasks(
        db=db,
        organization_id=current_user.organization_id,
        skip=skip,
        limit=limit,
        status=status,
        priority=priority,
        assigned_to=assigned_to,
        project_id=project_id,
        search=search,
    )


@router.get("/{task_id}", response_model=TaskResponse)
def get_one(
    task_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
            "employee"
        )
    )
):
    task = db_get_task_by_id(
        db,
        task_id,
        current_user.organization_id
    )

    if task is None:
        raise NotFoundException("Task")

    return task


@router.put("/{task_id}", response_model=TaskResponse)
def update(
    task_id: int,
    task: TaskUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager"
        )
    )
):
    try:
        updated = db_update_task(
            db=db,
            task_id=task_id,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            updated_task=task,
        )

        if updated is None:
            raise HTTPException(
                status_code=404,
                detail="Task not found"
            )

        return updated

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.delete("/{task_id}", response_model=TaskResponse)
def delete(
    task_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager"
        )
    )
):
    deleted = db_delete_task(
        db=db,
        task_id=task_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )

    if deleted is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    return deleted