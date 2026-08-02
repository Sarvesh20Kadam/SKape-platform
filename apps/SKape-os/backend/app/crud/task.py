from sqlalchemy.orm import Session

from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate
from app.crud.activity import log_activity


def create_task(
    db: Session,
    task: TaskCreate,
    organization_id: int,
    user_id: int
):
    db_task = Task(
        title=task.title,
        description=task.description,
        priority=task.priority,
        due_date=task.due_date,
        project_id=task.project_id,
        assigned_to=task.assigned_to,
        organization_id=organization_id,
        status="todo",
    )

    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    log_activity(
        db=db,
        action="created",
        entity="task",
        entity_id=db_task.id,
        user_id=user_id,
        organization_id=organization_id
    )

    return db_task


def get_tasks(
    db: Session,
    organization_id: int
):
    return (
        db.query(Task)
        .filter(Task.organization_id == organization_id)
        .all()
    )


def get_task_by_id(
    db: Session,
    task_id: int,
    organization_id: int
):
    return (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.organization_id == organization_id
        )
        .first()
    )


def update_task(
    db: Session,
    task_id: int,
    organization_id: int,
    updated_task: TaskUpdate
):
    task = get_task_by_id(
        db,
        task_id,
        organization_id
    )

    if task is None:
        return None

    update_data = updated_task.model_dump(
        exclude_unset=True
    )

    for key, value in update_data.items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)

    return task


def delete_task(
    db: Session,
    task_id: int,
    organization_id: int
):
    task = get_task_by_id(
        db,
        task_id,
        organization_id
    )

    if task is None:
        return None

    db.delete(task)
    db.commit()

    return task