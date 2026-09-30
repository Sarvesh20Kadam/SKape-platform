from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.task import Task
from app.models.project import Project


def create_maintenance_task_from_alert(
    db: Session,
    alert: Alert,
    project_id: int,
) -> tuple[Task, bool]:
    """
    Create a maintenance task for an alert.

    The project must belong to the same organization
    as the alert.

    Returns:
        (task, created)
        created=True when a new task was created.
        created=False when an existing active task was reused.
    """

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

    maintenance_title = (
        f"Maintenance: {alert.title}"
    )

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
        if existing_task.alert_id is None:
            existing_task.alert_id = alert.id
            db.flush()

        return existing_task, False

    priority_map = {
        "critical": "urgent",
        "warning": "high",
        "info": "medium",
    }

    priority = priority_map.get(
        alert.severity,
        "medium",
    )

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
        alert_id=alert.id,
    )

    db.add(task)
    db.flush()

    return task, True