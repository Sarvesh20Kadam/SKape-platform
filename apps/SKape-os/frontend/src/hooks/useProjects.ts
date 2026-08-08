import { useCallback, useEffect, useState } from "react";

import {
  createProject as createProjectRequest,
  getProjects,
} from "../features/projects/services/project.service";

import type {
  Project,
  ProjectCreatePayload,
} from "../features/projects/types/project.types";

type UseProjectsResult = {
  projects: Project[];
  loading: boolean;
  creating: boolean;
  error: string | null;
  createProject: (
    payload: ProjectCreatePayload,
  ) => Promise<Project>;
  refresh: () => Promise<void>;
};

export function useProjects(): UseProjectsResult {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const data = await getProjects();

      setProjects(data);
    } catch (err) {
      console.error("Failed to load projects:", err);

      setError(
        "Unable to load projects. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const createProject = useCallback(
    async (
      payload: ProjectCreatePayload,
    ): Promise<Project> => {
      try {
        setCreating(true);
        setError(null);

        const project =
          await createProjectRequest(payload);

        /*
         * Add the newly created project immediately.
         * This avoids forcing the entire page to wait for
         * another GET request before displaying it.
         */
        setProjects((current) => [
          project,
          ...current.filter(
            (item) => item.id !== project.id,
          ),
        ]);

        return project;
      } catch (err) {
        console.error(
          "Failed to create project:",
          err,
        );

        setError(
          "Unable to create the project. Please try again.",
        );

        throw err;
      } finally {
        setCreating(false);
      }
    },
    [],
  );

  return {
    projects,
    loading,
    creating,
    error,
    createProject,
    refresh,
  };
}