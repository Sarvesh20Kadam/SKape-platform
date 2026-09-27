from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.task import Task
from app.models.project import Project


def create_maintenance_task_from_alert(
    db: Session,
    alert: Alert,
    project_id: int,
) -> Task:
    """
    Create a maintenance task for an alert.

    The project must belong to the same organization
    as the alert.
    """

    # -------------------------------------------------
    # Validate project
    # -------------------------------------------------

    project = (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.organization_id == alert.organization_id,
        )
        .first()
    )

    if project is None:
        raise ValueError(
            "Project not found in this organization."
        )

    # -------------------------------------------------
    # Determine maintenance task title
    # -------------------------------------------------

    maintenance_title = (
        f"Maintenance: {alert.title}"
    )

    # -------------------------------------------------
    # Prevent duplicate active maintenance tasks
    # -------------------------------------------------

    existing_task = (
        db.query(Task)
        .filter(
            Task.organization_id == alert.organization_id,
            Task.project_id == project_id,
            Task.status.in_(
                ["todo", "in_progress"]
            ),
            Task.title == maintenance_title,
        )
        .first()
    )

    if existing_task is not None:
        return existing_task

    # -------------------------------------------------
    # Map alert severity → task priority
    # -------------------------------------------------

    priority_map = {
        "critical": "urgent",
        "warning": "high",
        "info": "medium",
    }

    priority = priority_map.get(
        alert.severity,
        "medium",
    )

    # -------------------------------------------------
    # Create maintenance task
    # -------------------------------------------------

    task = Task(
        title=maintenance_title,
        description=(
            f"{alert.message}\n\n"
            f"Device ID: {alert.device_id}\n"
            f"Alert ID: {alert.id}"
        ),
        status="todo",
        priority=priority,
        project_id=project_id,
        assigned_to=None,
        organization_id=alert.organization_id,
    )

    db.add(task)
    db.flush()

    return task