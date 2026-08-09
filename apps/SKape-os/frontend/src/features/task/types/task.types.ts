export type TaskStatus =
  | "todo"
  | "in_progress"
  | "completed"
  | "cancelled";

export type TaskPriority =
  | "low"
  | "medium"
  | "high"
  | "urgent";

export type Task = {
  id: number;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  project_id: number;
  assigned_to: number | null;
  organization_id: number;
  due_date: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateTaskPayload = {
  title: string;
  description?: string;
  priority?: TaskPriority;
  project_id: number;
  assigned_to?: number | null;
  due_date?: string | null;
};

export type UpdateTaskPayload = {
  title?: string;
  description?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  project_id?: number;
  assigned_to?: number | null;
  due_date?: string | null;
};