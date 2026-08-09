from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.project import Project
from app.models.user import User


def get_tasks(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 10,
    status: str | None = None,
    priority: str | None = None,
    assigned_to: int | None = None,
    project_id: int | None = None,
    search: str | None = None,
):
    """
    Return tasks belonging to the current organization.

    Supports:
    - pagination
    - status filtering
    - priority filtering
    - assignee filtering
    - project filtering
    - title/description search
    """

    query = (
        db.query(Task)
        .filter(
            Task.organization_id == organization_id
        )
    )

    # Status filter
    if status is not None:
        query = query.filter(
            Task.status == status
        )

    # Priority filter
    if priority is not None:
        query = query.filter(
            Task.priority == priority
        )

    # Assignee filter
    if assigned_to is not None:
        query = query.filter(
            Task.assigned_to == assigned_to
        )

    # Project filter
    if project_id is not None:
        query = query.filter(
            Task.project_id == project_id
        )

    # Search
    if search:
        search_term = f"%{search.strip()}%"

        query = query.filter(
            (Task.title.ilike(search_term))
            | (Task.description.ilike(search_term))
        )

    # Newest tasks first
    query = query.order_by(
        Task.created_at.desc()
    )

    # Pagination
    query = query.offset(skip).limit(limit)

    return query.all()


def get_task_by_id(
    db: Session,
    task_id: int,
    organization_id: int,
):
    """
    Return one task only if it belongs
    to the current organization.
    """

    return (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.organization_id == organization_id,
        )
        .first()
    )


def create_task(
    db: Session,
    task,
    organization_id: int,
    user_id: int,
):
    """
    Create a task inside the current organization.
    """

    # -------------------------------------------------
    # Validate project
    # -------------------------------------------------

    project = (
        db.query(Project)
        .filter(
            Project.id == task.project_id,
            Project.organization_id == organization_id,
        )
        .first()
    )

    if project is None:
        raise ValueError(
            "Project not found in this organization."
        )

    # -------------------------------------------------
    # Validate assignee
    # -------------------------------------------------

    if task.assigned_to is not None:

        assignee = (
            db.query(User)
            .filter(
                User.id == task.assigned_to,
                User.organization_id == organization_id,
            )
            .first()
        )

        if assignee is None:
            raise ValueError(
                "Assigned user not found in this organization."
            )

    # -------------------------------------------------
    # Create task
    # -------------------------------------------------

    new_task = Task(
        title=task.title.strip(),
        description=(
            task.description.strip()
            if task.description
            else None
        ),
        status="todo",
        priority=task.priority,
        project_id=task.project_id,
        assigned_to=task.assigned_to,
        due_date=task.due_date,
        organization_id=organization_id,
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return new_task


def update_task(
    db: Session,
    task_id: int,
    organization_id: int,
    user_id: int,
    updated_task,
):
    """
    Update a task belonging to the current organization.
    """

    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.organization_id == organization_id,
        )
        .first()
    )

    if task is None:
        return None

    # -------------------------------------------------
    # Only update fields actually supplied
    # -------------------------------------------------

    update_data = updated_task.model_dump(
        exclude_unset=True
    )

    # -------------------------------------------------
    # Validate project change
    # -------------------------------------------------

    if "project_id" in update_data:

        new_project_id = update_data["project_id"]

        project = (
            db.query(Project)
            .filter(
                Project.id == new_project_id,
                Project.organization_id == organization_id,
            )
            .first()
        )

        if project is None:
            raise ValueError(
                "Project not found in this organization."
            )

    # -------------------------------------------------
    # Validate assignee change
    # -------------------------------------------------

    if "assigned_to" in update_data:

        new_assigned_to = update_data["assigned_to"]

        if new_assigned_to is not None:

            assignee = (
                db.query(User)
                .filter(
                    User.id == new_assigned_to,
                    User.organization_id
                    == organization_id,
                )
                .first()
            )

            if assignee is None:
                raise ValueError(
                    "Assigned user not found in this organization."
                )

    # -------------------------------------------------
    # Apply updates
    # -------------------------------------------------

    if "title" in update_data:

        title = update_data["title"]

        if title is None or not title.strip():
            raise ValueError(
                "Task title cannot be empty."
            )

        task.title = title.strip()

    if "description" in update_data:

        description = update_data["description"]

        task.description = (
            description.strip()
            if description
            else None
        )

    if "status" in update_data:
        task.status = update_data["status"]

    if "priority" in update_data:
        task.priority = update_data["priority"]

    if "due_date" in update_data:
        task.due_date = update_data["due_date"]

    if "assigned_to" in update_data:
        task.assigned_to = update_data["assigned_to"]

    if "project_id" in update_data:
        task.project_id = update_data["project_id"]

    db.commit()
    db.refresh(task)

    return task


def delete_task(
    db: Session,
    task_id: int,
    organization_id: int,
    user_id: int,
):
    """
    Delete a task belonging to the current organization.
    """

    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.organization_id == organization_id,
        )
        .first()
    )

    if task is None:
        return None

    db.delete(task)
    db.commit()

    return task