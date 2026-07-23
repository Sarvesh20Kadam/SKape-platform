from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.project import ProjectCreate


def create_project(db: Session, project: ProjectCreate):
    db_project = Project(
        name=project.name,
        description=project.description,
        status="active"
    )

    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    return db_project