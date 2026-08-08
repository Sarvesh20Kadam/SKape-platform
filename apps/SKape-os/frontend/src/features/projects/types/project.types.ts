export type ProjectStatus =
  | "planned"
  | "active"
  | "completed"
  | "archived";

export type Project = {
  id: number;
  name: string;
  description: string;
  status: ProjectStatus;
};

export type ProjectCreatePayload = {
  name: string;
  description: string;
};

export type ProjectUpdatePayload = {
  name: string;
  description: string;
  status: ProjectStatus;
};