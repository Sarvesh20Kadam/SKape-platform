import { useCallback, useEffect, useState } from "react";

import { getTask } from "../services/task.service";
import type { Task } from "../types/task.types";

type UseTaskDetailOptions = {
  taskId: number;
  autoFetch?: boolean;
};

export function useTaskDetail({
  taskId,
  autoFetch = true,
}: UseTaskDetailOptions) {
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(autoFetch);
  const [error, setError] = useState<string | null>(null);

  const fetchTask = useCallback(async () => {
    if (!taskId || Number.isNaN(taskId)) {
      setTask(null);
      setError("Invalid task ID.");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const data = await getTask(taskId);

      setTask(data);
    } catch (err) {
      console.error("Failed to fetch task:", err);

      setTask(null);
      setError(
        "Unable to load this task. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    if (!autoFetch) {
      return;
    }

    void fetchTask();
  }, [autoFetch, fetchTask]);

  return {
    task,
    loading,
    error,
    fetchTask,
  };
}