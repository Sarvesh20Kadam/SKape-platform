import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  createProject as createProjectRequest,
  getProjects,
  updateProject as updateProjectRequest,
} from "../features/projects/services/project.service";

import type {
  Project,
  ProjectCreatePayload,
  ProjectUpdatePayload,
} from "../features/projects/types/project.types";

type UseProjectsResult = {
  projects: Project[];
  loading: boolean;
  creating: boolean;
  updating: boolean;
  error: string | null;

  createProject: (
    payload: ProjectCreatePayload,
  ) => Promise<Project>;

  updateProject: (
    projectId: number,
    payload: ProjectUpdatePayload,
  ) => Promise<Project>;

  refresh: () => Promise<void>;
};

export function useProjects(): UseProjectsResult {
  const [projects, setProjects] =
    useState<Project[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [creating, setCreating] =
    useState(false);

  const [updating, setUpdating] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  /*
   * =========================================================
   * LOAD PROJECTS
   * =========================================================
   */

  const refresh =
    useCallback(async () => {
      try {
        setLoading(true);
        setError(null);

        const data =
          await getProjects();

        setProjects(data);
      } catch (err) {
        console.error(
          "Failed to load projects:",
          err,
        );

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

  /*
   * =========================================================
   * CREATE PROJECT
   * =========================================================
   */

  const createProject =
    useCallback(
      async (
        payload: ProjectCreatePayload,
      ): Promise<Project> => {
        try {
          setCreating(true);
          setError(null);

          const project =
            await createProjectRequest(
              payload,
            );

          setProjects(
            (current) => [
              project,
              ...current.filter(
                (item) =>
                  item.id !==
                  project.id,
              ),
            ],
          );

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

  /*
   * =========================================================
   * UPDATE PROJECT
   * =========================================================
   */

  const updateProject =
    useCallback(
      async (
        projectId: number,
        payload: ProjectUpdatePayload,
      ): Promise<Project> => {
        try {
          setUpdating(true);
          setError(null);

          const updatedProject =
            await updateProjectRequest(
              projectId,
              payload,
            );

          setProjects(
            (current) =>
              current.map(
                (project) =>
                  project.id ===
                  projectId
                    ? updatedProject
                    : project,
              ),
          );

          return updatedProject;
        } catch (err) {
          console.error(
            "Failed to update project:",
            err,
          );

          setError(
            "Unable to update the project. Please try again.",
          );

          throw err;
        } finally {
          setUpdating(false);
        }
      },
      [],
    );

  return {
    projects,
    loading,
    creating,
    updating,
    error,
    createProject,
    updateProject,
    refresh,
  };
}