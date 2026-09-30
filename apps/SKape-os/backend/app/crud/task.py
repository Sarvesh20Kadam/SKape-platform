from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.project import Project
from app.models.user import User
from app.crud.activity import log_activity


# ============================================================
# LIST TASKS
# ============================================================

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

    # -------------------------------------------------
    # Status filter
    # -------------------------------------------------

    if status is not None:
        query = query.filter(
            Task.status == status
        )

    # -------------------------------------------------
    # Priority filter
    # -------------------------------------------------

    if priority is not None:
        query = query.filter(
            Task.priority == priority
        )

    # -------------------------------------------------
    # Assignee filter
    # -------------------------------------------------

    if assigned_to is not None:
        query = query.filter(
            Task.assigned_to == assigned_to
        )

    # -------------------------------------------------
    # Project filter
    # -------------------------------------------------

    if project_id is not None:
        query = query.filter(
            Task.project_id == project_id
        )

    # -------------------------------------------------
    # Search
    # -------------------------------------------------

    if search:
        search_term = f"%{search.strip()}%"

        query = query.filter(
            (Task.title.ilike(search_term))
            | (Task.description.ilike(search_term))
        )

    # -------------------------------------------------
    # Newest tasks first
    # -------------------------------------------------

    query = query.order_by(
        Task.created_at.desc()
    )

    # -------------------------------------------------
    # Pagination
    # -------------------------------------------------

    query = query.offset(skip).limit(limit)

    return query.all()


# ============================================================
# GET SINGLE TASK
# ============================================================

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


# ============================================================
# CREATE TASK
# ============================================================

def create_task(
    db: Session,
    task,
    organization_id: int,
    user_id: int,
):
    """
    Create a task inside the current organization
    and record the creation in the activity log.
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

    # Get database-generated ID.
    db.flush()

    # -------------------------------------------------
    # Activity log
    # -------------------------------------------------

    log_activity(
        db=db,
        action="created",
        entity="task",
        entity_id=new_task.id,
        user_id=user_id,
        organization_id=organization_id,
    )

    # -------------------------------------------------
    # Commit transaction
    # -------------------------------------------------

    db.commit()
    db.refresh(new_task)

    return new_task


# ============================================================
# UPDATE TASK
# ============================================================

def update_task(
    db: Session,
    task_id: int,
    organization_id: int,
    user_id: int,
    updated_task,
):
    """
    Update a task belonging to the current organization
    and record the update in the activity log.
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
    # Only update supplied fields
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
                    User.organization_id == organization_id,
                )
                .first()
            )

            if assignee is None:
                raise ValueError(
                    "Assigned user not found in this organization."
                )

    # -------------------------------------------------
    # Apply title update
    # -------------------------------------------------

    if "title" in update_data:

        title = update_data["title"]

        if title is None or not title.strip():
            raise ValueError(
                "Task title cannot be empty."
            )

        task.title = title.strip()

    # -------------------------------------------------
    # Apply description update
    # -------------------------------------------------

    if "description" in update_data:

        description = update_data["description"]

        task.description = (
            description.strip()
            if description
            else None
        )

    # -------------------------------------------------
    # Apply status update
    # -------------------------------------------------

    if "status" in update_data:
        task.status = update_data["status"]

    # -------------------------------------------------
    # Apply priority update
    # -------------------------------------------------

    if "priority" in update_data:
        task.priority = update_data["priority"]

    # -------------------------------------------------
    # Apply due date update
    # -------------------------------------------------

    if "due_date" in update_data:
        task.due_date = update_data["due_date"]

    # -------------------------------------------------
    # Apply assignee update
    # -------------------------------------------------

    if "assigned_to" in update_data:
        task.assigned_to = update_data["assigned_to"]

    # -------------------------------------------------
    # Apply project update
    # -------------------------------------------------

    if "project_id" in update_data:
        task.project_id = update_data["project_id"]

    # -------------------------------------------------
    # Activity log
    # -------------------------------------------------

    log_activity(
        db=db,
        action="updated",
        entity="task",
        entity_id=task.id,
        user_id=user_id,
        organization_id=organization_id,
    )

    # -------------------------------------------------
    # Commit transaction
    # -------------------------------------------------

    db.commit()
    db.refresh(task)

    return task


# ============================================================
# DELETE TASK
# ============================================================

def delete_task(
    db: Session,
    task_id: int,
    organization_id: int,
    user_id: int,
):
    """
    Delete a task belonging to the current organization
    and record the deletion in the activity log.
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

    # Keep the ID before deleting the SQLAlchemy object.
    task_id_value = task.id

    # -------------------------------------------------
    # Delete task
    # -------------------------------------------------

    db.delete(task)

    # Flush deletion before recording activity.
    db.flush()

    # -------------------------------------------------
    # Activity log
    # -------------------------------------------------

    log_activity(
        db=db,
        action="deleted",
        entity="task",
        entity_id=task_id_value,
        user_id=user_id,
        organization_id=organization_id,
    )

    # -------------------------------------------------
    # Commit transaction
    # -------------------------------------------------

    db.commit()

    return task