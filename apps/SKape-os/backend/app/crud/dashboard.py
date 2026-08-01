from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.task import Task
from app.models.user import User


def get_dashboard(
    db: Session,
    organization_id: int
):
    total_projects = (
        db.query(Project)
        .filter(
            Project.organization_id == organization_id
        )
        .count()
    )

    active_projects = (
        db.query(Project)
        .filter(
            Project.organization_id == organization_id,
            Project.status == "active"
        )
        .count()
    )

    total_tasks = (
        db.query(Task)
        .filter(
            Task.organization_id == organization_id
        )
        .count()
    )

    completed_tasks = (
        db.query(Task)
        .filter(
            Task.organization_id == organization_id,
            Task.status == "done"
        )
        .count()
    )

    pending_tasks = (
        db.query(Task)
        .filter(
            Task.organization_id == organization_id,
            Task.status != "done"
        )
        .count()
    )

    total_members = (
        db.query(User)
        .filter(
            User.organization_id == organization_id
        )
        .count()
    )

    return {
        "total_projects": total_projects,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "total_members": total_members,
        "active_projects": active_projects,
    }