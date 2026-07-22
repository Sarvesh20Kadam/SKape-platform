from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)

projects = []


def create_project(project: ProjectCreate) -> ProjectResponse:
    new_project = ProjectResponse(
        id=len(projects) + 1,
        name=project.name,
        description=project.description,
        status="active"
    )

    projects.append(new_project)

    return new_project


def get_projects():
    return projects


def get_project_by_id(project_id: int):
    for project in projects:
        if project.id == project_id:
            return project

    return None


def update_project(project_id: int, updated_project: ProjectUpdate):
    project = get_project_by_id(project_id)

    if project is None:
        return None

    project.name = updated_project.name
    project.description = updated_project.description
    project.status = updated_project.status

    return project

def delete_project(project_id: int):
    project = get_project_by_id(project_id)

    if project is None:
        return False

    projects.remove(project)

    return True