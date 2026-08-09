import { useCallback, useEffect, useState } from "react";

import {
  createTask,
  deleteTask,
  getTasks,
  updateTask,
} from "../services/task.service";

import type {
  CreateTaskPayload,
  Task,
  UpdateTaskPayload,
} from "../types/task.types";

type UseTaskOptions = {
  projectId?: number;
  autoFetch?: boolean;
};

export function useTask({
  projectId,
  autoFetch = true,
}: UseTaskOptions = {}) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(autoFetch);
  const [creating, setCreating] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const data = await getTasks(projectId);

      setTasks(data);
    } catch (err) {
      console.error("Failed to fetch tasks:", err);

      setError(
        "Unable to load tasks. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (!autoFetch) {
      return;
    }

    void fetchTasks();
  }, [autoFetch, fetchTasks]);

  const addTask = useCallback(
    async (
      payload: CreateTaskPayload,
    ): Promise<Task | null> => {
      try {
        setCreating(true);
        setError(null);

        const createdTask = await createTask(payload);

        setTasks((currentTasks) => [
          createdTask,
          ...currentTasks,
        ]);

        return createdTask;
      } catch (err) {
        console.error("Failed to create task:", err);

        setError(
          "Unable to create task. Please try again.",
        );

        return null;
      } finally {
        setCreating(false);
      }
    },
    [],
  );

  const editTask = useCallback(
    async (
      taskId: number,
      payload: UpdateTaskPayload,
    ): Promise<Task | null> => {
      try {
        setUpdating(true);
        setError(null);

        const updatedTask = await updateTask(
          taskId,
          payload,
        );

        setTasks((currentTasks) =>
          currentTasks.map((task) =>
            task.id === taskId
              ? updatedTask
              : task,
          ),
        );

        return updatedTask;
      } catch (err) {
        console.error("Failed to update task:", err);

        setError(
          "Unable to update task. Please try again.",
        );

        return null;
      } finally {
        setUpdating(false);
      }
    },
    [],
  );

  const removeTask = useCallback(
    async (taskId: number): Promise<boolean> => {
      try {
        setDeleting(true);
        setError(null);

        await deleteTask(taskId);

        setTasks((currentTasks) =>
          currentTasks.filter(
            (task) => task.id !== taskId,
          ),
        );

        return true;
      } catch (err) {
        console.error("Failed to delete task:", err);

        setError(
          "Unable to delete task. Please try again.",
        );

        return false;
      } finally {
        setDeleting(false);
      }
    },
    [],
  );

  return {
    tasks,
    loading,
    creating,
    updating,
    deleting,
    error,
    fetchTasks,
    addTask,
    editTask,
    removeTask,
  };
}