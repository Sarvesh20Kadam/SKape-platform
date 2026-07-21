from app.schemas.project import ProjectCreate, ProjectResponse

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