from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.crud.activity import log_activity
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


def create_project(
    db: Session,
    project: ProjectCreate,
    organization_id: int,
    user_id: int,
):
    db_project = Project(
        name=project.name,
        description=project.description,
        status="active",
        organization_id=organization_id,
    )

    db.add(db_project)

    try:
        # Get the generated project ID without committing yet.
        db.flush()

        log_activity(
            db=db,
            action="created",
            entity="project",
            entity_id=db_project.id,
            user_id=user_id,
            organization_id=organization_id,
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    db.refresh(db_project)

    return db_project


def get_projects(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 10,
):
    return (
        db.query(Project)
        .filter(
            Project.organization_id == organization_id
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_project_by_id(
    db: Session,
    project_id: int,
    organization_id: int,
):
    return (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.organization_id == organization_id,
        )
        .first()
    )


def update_project(
    db: Session,
    project_id: int,
    organization_id: int,
    user_id: int,
    updated_project: ProjectUpdate,
):
    project = get_project_by_id(
        db=db,
        project_id=project_id,
        organization_id=organization_id,
    )

    if project is None:
        return None

    update_data = updated_project.model_dump(
        exclude_unset=True
    )

    for key, value in update_data.items():
        setattr(project, key, value)

    try:
        # Flush project changes before creating audit record.
        db.flush()

        log_activity(
            db=db,
            action="updated",
            entity="project",
            entity_id=project.id,
            user_id=user_id,
            organization_id=organization_id,
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    db.refresh(project)

    return project


def delete_project(
    db: Session,
    project_id: int,
    organization_id: int,
    user_id: int,
):
    project = get_project_by_id(
        db=db,
        project_id=project_id,
        organization_id=organization_id,
    )

    if project is None:
        return None

    deleted_project_id = project.id
    snapshot = SimpleNamespace(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
    )

    try:
        # Delete the project inside the current transaction.
        db.delete(project)

        # Flush the DELETE but do NOT commit yet.
        db.flush()

        # Create the audit record in the SAME transaction.
        log_activity(
            db=db,
            action="deleted",
            entity="project",
            entity_id=deleted_project_id,
            user_id=user_id,
            organization_id=organization_id,
        )

        # Project deletion + audit record commit together.
        db.commit()

    except Exception:
        db.rollback()
        raise

    return snapshot