import api from "../../../api/client";

import type {
  Project,
  ProjectCreatePayload,
  ProjectUpdatePayload,
} from "../types/project.types";

export async function getProjects(): Promise<Project[]> {
  const response = await api.get<Project[]>("/projects/");

  return response.data;
}

export async function createProject(
  payload: ProjectCreatePayload,
): Promise<Project> {
  const response = await api.post<Project>(
    "/projects/",
    payload,
  );

  return response.data;
}

export async function updateProject(
  projectId: number,
  payload: ProjectUpdatePayload,
): Promise<Project> {
  const response = await api.put<Project>(
    `/projects/${projectId}`,
    payload,
  );

  return response.data;
}

export async function deleteProject(
  projectId: number,
): Promise<Project> {
  const response = await api.delete<Project>(
    `/projects/${projectId}`,
  );

  return response.data;
}