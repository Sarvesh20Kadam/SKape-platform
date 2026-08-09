import api from "../../../api/client";

import type {
  CreateTaskPayload,
  Task,
  UpdateTaskPayload,
} from "../types/task.types";

export async function getTasks(
  projectId?: number,
): Promise<Task[]> {
  const response = await api.get<Task[]>("/tasks/", {
    params: projectId
      ? {
          project_id: projectId,
        }
      : undefined,
  });

  return response.data;
}

export async function getTask(
  taskId: number,
): Promise<Task> {
  const response = await api.get<Task>(
    `/tasks/${taskId}`,
  );

  return response.data;
}

export async function createTask(
  data: CreateTaskPayload,
): Promise<Task> {
  const response = await api.post<Task>(
    "/tasks/",
    data,
  );

  return response.data;
}

export async function updateTask(
  taskId: number,
  data: UpdateTaskPayload,
): Promise<Task> {
  const response = await api.put<Task>(
    `/tasks/${taskId}`,
    data,
  );

  return response.data;
}

export async function deleteTask(
  taskId: number,
): Promise<void> {
  await api.delete(`/tasks/${taskId}`);
}