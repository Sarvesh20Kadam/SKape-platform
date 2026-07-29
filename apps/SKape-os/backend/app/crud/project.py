from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


def create_project(
    db: Session,
    project: ProjectCreate,
    organization_id: int
):
    db_project = Project(
        name=project.name,
        description=project.description,
        status="active",
        organization_id=organization_id
    )

    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    return db_project


def get_projects(
    db: Session,
    organization_id: int
):
    return (
        db.query(Project)
        .filter(Project.organization_id == organization_id)
        .all()
    )


def get_project_by_id(
    db: Session,
    project_id: int,
    organization_id: int
):
    return (
        db.query(Project)
        .filter(
            Project.id == project_id,
            Project.organization_id == organization_id
        )
        .first()
    )


def update_project(
    db: Session,
    project_id: int,
    organization_id: int,
    updated_project: ProjectUpdate
):
    project = get_project_by_id(
        db,
        project_id,
        organization_id
    )

    if project is None:
        return None

    project.name = updated_project.name
    project.description = updated_project.description
    project.status = updated_project.status

    db.commit()
    db.refresh(project)

    return project


def delete_project(
    db: Session,
    project_id: int,
    organization_id: int
):
    project = get_project_by_id(
        db,
        project_id,
        organization_id
    )

    if project is None:
        return None

    db.delete(project)
    db.commit()

    return project