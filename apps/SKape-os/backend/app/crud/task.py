from sqlalchemy.orm import Session

from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate
from app.crud.activity import log_activity

from app.models.user import User
from app.models.project import Project

def create_task(
    db: Session,
    task: TaskCreate,
    organization_id: int,
    user_id: int
):
    project = (
        db.query(Project)
        .filter(
            Project.id == task.project_id,
            Project.organization_id == organization_id
        )
        .first()
    )

    if project is None:
        raise ValueError("Project not found")

    if task.assigned_to is not None:
        user = (
            db.query(User)
            .filter(
                User.id == task.assigned_to,
                User.organization_id == organization_id
            )
            .first()
        )

        if user is None:
            raise ValueError("Assigned user not found")

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
    user_id: int,
    updated_task: TaskUpdate
):
    print("UPDATE TASK VALIDATION EXECUTED")

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
    print(update_data)
    # Validate project if being updated
    if "project_id" in update_data:
        project = (
            db.query(Project)
            .filter(
                Project.id == update_data["project_id"],
                Project.organization_id == organization_id
            )
            .first()
        )

        if project is None:
            raise ValueError("Project not found")

    # Validate assignee if being updated
    if (
        "assigned_to" in update_data
        and update_data["assigned_to"] is not None
    ):
        user = (
            db.query(User)
            .filter(
                User.id == update_data["assigned_to"],
                User.organization_id == organization_id
            )
            .first()
        )

        if user is None:
            raise ValueError("Assigned user not found")

    for key, value in update_data.items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)

    log_activity(
        db=db,
        action="updated",
        entity="task",
        entity_id=task.id,
        user_id=user_id,
        organization_id=organization_id
    )

    return task


def delete_task(
    db: Session,
    task_id: int,
    organization_id: int,
    user_id: int
):
    task = get_task_by_id(
        db,
        task_id,
        organization_id
    )

    if task is None:
        return None

    deleted_task_id = task.id

    db.delete(task)
    db.commit()

    log_activity(
        db=db,
        action="deleted",
        entity="task",
        entity_id=deleted_task_id,
        user_id=user_id,
        organization_id=organization_id
    )

    return task