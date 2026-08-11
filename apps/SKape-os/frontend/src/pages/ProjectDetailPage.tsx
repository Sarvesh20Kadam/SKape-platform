import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CheckSquare,
  FolderKanban,
  Plus,
} from "lucide-react";
import {
  useNavigate,
  useParams,
} from "react-router-dom";

import DashboardLayout from "../components/layout/DashboardLayout";

import { getProjects } from "../features/projects/services/project.service";
import { getTasks } from "../features/task/services/task.service";

import type { Project } from "../features/projects/types/project.types";
import type { Task } from "../features/task/types/task.types";

function ProjectDetailPage() {
  const navigate = useNavigate();

  const { projectId } = useParams<{
    projectId: string;
  }>();

  const numericProjectId = Number(projectId);

  const [project, setProject] =
    useState<Project | null>(null);

  const [tasks, setTasks] =
    useState<Task[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  /*
   * =========================================================
   * LOAD PROJECT + TASKS
   * =========================================================
   */

  useEffect(() => {
    async function loadProject() {
      if (
        !numericProjectId ||
        Number.isNaN(numericProjectId)
      ) {
        setError("Invalid project ID.");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        /*
         * We currently have getProjects()
         * rather than getProject(id), so we
         * find the project from the existing
         * project collection.
         */
        const projects =
          await getProjects();

        const selectedProject =
          projects.find(
            (item) =>
              item.id ===
              numericProjectId,
          );

        if (!selectedProject) {
          setProject(null);
          setTasks([]);
          setError(
            "Project not found.",
          );
          return;
        }

        setProject(
          selectedProject,
        );

        /*
         * Load only tasks belonging to
         * this project.
         */
        const projectTasks =
          await getTasks(
            numericProjectId,
          );

        setTasks(projectTasks);
      } catch (err) {
        console.error(
          "Failed to load project:",
          err,
        );

        setError(
          "Unable to load this project. Please try again.",
        );
      } finally {
        setLoading(false);
      }
    }

    void loadProject();
  }, [numericProjectId]);

  /*
   * =========================================================
   * TASK SUMMARY
   * =========================================================
   */

  const taskSummary = useMemo(() => {
    const completed =
      tasks.filter(
        (task) =>
          task.status ===
          "completed",
      ).length;

    const inProgress =
      tasks.filter(
        (task) =>
          task.status ===
          "in_progress",
      ).length;

    const remaining =
      tasks.length - completed;

    return {
      total: tasks.length,
      completed,
      inProgress,
      remaining,
    };
  }, [tasks]);

  /*
   * =========================================================
   * LOADING
   * =========================================================
   */

  if (loading) {
    return (
      <DashboardLayout>
        <div className="mx-auto w-full max-w-[1480px] space-y-6">

          <div className="h-5 w-32 animate-pulse rounded bg-zinc-900" />

          <div className="h-52 animate-pulse rounded-2xl border border-zinc-800 bg-zinc-900/40" />

          <div className="h-80 animate-pulse rounded-2xl border border-zinc-800 bg-zinc-900/40" />

        </div>
      </DashboardLayout>
    );
  }

  /*
   * =========================================================
   * ERROR
   * =========================================================
   */

  if (error || !project) {
    return (
      <DashboardLayout>
        <div className="mx-auto w-full max-w-[1480px]">

          <button
            type="button"
            onClick={() =>
              navigate("/projects")
            }
            className="
              inline-flex
              items-center
              gap-2
              text-sm
              text-zinc-500
              transition-colors
              hover:text-zinc-200
            "
          >
            <ArrowLeft size={16} />
            Back to projects
          </button>

          <div
            className="
              mt-8
              rounded-2xl
              border
              border-red-500/20
              bg-red-500/5
              p-6
            "
          >
            <h1 className="text-lg font-semibold text-zinc-200">
              {error ||
                "Project not found"}
            </h1>

            <p className="mt-2 text-sm leading-6 text-zinc-500">
              This project may have been
              deleted or you may not have
              access to it.
            </p>
          </div>

        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="mx-auto w-full max-w-[1480px] space-y-7">

        {/* =====================================================
            HEADER
            ===================================================== */}

        <div className="flex items-center justify-between gap-4">

          <button
            type="button"
            onClick={() =>
              navigate("/projects")
            }
            className="
              inline-flex
              items-center
              gap-2
              text-sm
              text-zinc-500
              transition-colors
              hover:text-zinc-200
            "
          >
            <ArrowLeft size={16} />

            Back to projects
          </button>

          <button
            type="button"
            onClick={() =>
              navigate(
                `/tasks?project_id=${project.id}`,
              )
            }
            className="
              inline-flex
              h-10
              items-center
              gap-2
              rounded-lg
              bg-emerald-500
              px-4
              text-sm
              font-semibold
              text-zinc-950
              transition-colors
              hover:bg-emerald-400
            "
          >
            <Plus size={16} />

            New task
          </button>

        </div>

        {/* =====================================================
            PROJECT HEADER
            ===================================================== */}

        <section
          className="
            overflow-hidden
            rounded-2xl
            border
            border-zinc-800
            bg-zinc-950
          "
        >

          <div className="px-6 py-8 sm:px-8">

            <div className="flex items-start gap-4">

              <div
                className="
                  flex
                  h-12
                  w-12
                  shrink-0
                  items-center
                  justify-center
                  rounded-xl
                  border
                  border-zinc-800
                  bg-zinc-900
                "
              >
                <FolderKanban
                  size={21}
                  strokeWidth={1.7}
                  className="text-emerald-400"
                />
              </div>

              <div className="min-w-0 flex-1">

                <div className="flex flex-wrap items-center gap-2">

                  <span className="rounded-full border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-zinc-500">
                    {project.status}
                  </span>

                  <span className="text-xs text-zinc-700">
                    Project #{project.id}
                  </span>

                </div>

                <h1 className="mt-4 break-words text-2xl font-semibold tracking-[-0.025em] text-zinc-100 sm:text-3xl">
                  {project.name}
                </h1>

                <p className="mt-3 max-w-3xl text-sm leading-7 text-zinc-500">
                  {project.description ||
                    "No description provided."}
                </p>

              </div>

            </div>

          </div>

          {/* Project summary */}

          <div className="grid border-t border-zinc-800/80 sm:grid-cols-3">

            <SummaryItem
              label="Tasks"
              value={taskSummary.total}
            />

            <SummaryItem
              label="In progress"
              value={
                taskSummary.inProgress
              }
            />

            <SummaryItem
              label="Completed"
              value={
                taskSummary.completed
              }
            />

          </div>

        </section>

        {/* =====================================================
            TASKS
            ===================================================== */}

        <section
          className="
            overflow-hidden
            rounded-2xl
            border
            border-zinc-800
            bg-zinc-950
          "
        >

          <div
            className="
              flex
              items-center
              justify-between
              border-b
              border-zinc-800/80
              px-6
              py-5
              sm:px-8
            "
          >

            <div>

              <h2 className="text-sm font-semibold text-zinc-200">
                Project tasks
              </h2>

              <p className="mt-1 text-xs text-zinc-600">
                {tasks.length}{" "}
                {tasks.length === 1
                  ? "task"
                  : "tasks"}{" "}
                in this project
              </p>

            </div>

            <button
              type="button"
              onClick={() =>
                navigate(
                  `/tasks?project_id=${project.id}`,
                )
              }
              className="
                hidden
                items-center
                gap-2
                rounded-lg
                border
                border-zinc-800
                px-3
                py-2
                text-xs
                font-medium
                text-zinc-500
                transition-colors
                hover:border-zinc-700
                hover:bg-zinc-900
                hover:text-zinc-200
                sm:inline-flex
              "
            >
              <Plus size={14} />

              Add task
            </button>

          </div>

          {tasks.length === 0 ? (

            <div className="flex min-h-[260px] flex-col items-center justify-center px-6 text-center">

              <div
                className="
                  flex
                  h-11
                  w-11
                  items-center
                  justify-center
                  rounded-xl
                  border
                  border-zinc-800
                  bg-zinc-900
                "
              >
                <CheckSquare
                  size={19}
                  className="text-zinc-600"
                />
              </div>

              <h3 className="mt-4 text-sm font-semibold text-zinc-200">
                No tasks in this project
              </h3>

              <p className="mt-2 max-w-sm text-sm leading-6 text-zinc-600">
                Create a task to start
                tracking work for this
                project.
              </p>

              <button
                type="button"
                onClick={() =>
                  navigate(
                    `/tasks?project_id=${project.id}`,
                  )
                }
                className="
                  mt-5
                  inline-flex
                  items-center
                  gap-2
                  rounded-lg
                  bg-emerald-500
                  px-4
                  py-2.5
                  text-sm
                  font-semibold
                  text-zinc-950
                  transition-colors
                  hover:bg-emerald-400
                "
              >
                <Plus size={16} />

                Create task
              </button>

            </div>

          ) : (

            <div className="divide-y divide-zinc-800/70">

              {tasks.map((task) => (
                <ProjectTaskRow
                  key={task.id}
                  task={task}
                  onOpen={() =>
                    navigate(
                      `/tasks/${task.id}`,
                    )
                  }
                />
              ))}

            </div>

          )}

        </section>

      </div>
    </DashboardLayout>
  );
}

/* =========================================================
   PROJECT TASK ROW
   ========================================================= */

type ProjectTaskRowProps = {
  task: Task;
  onOpen: () => void;
};

function ProjectTaskRow({
  task,
  onOpen,
}: ProjectTaskRowProps) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="
        flex
        w-full
        items-center
        gap-4
        px-6
        py-4
        text-left
        transition-colors
        hover:bg-zinc-900/40
        sm:px-8
      "
    >

      <div
        className="
          flex
          h-9
          w-9
          shrink-0
          items-center
          justify-center
          rounded-lg
          border
          border-zinc-800
          bg-zinc-900
        "
      >
        <CheckSquare
          size={16}
          strokeWidth={1.7}
          className={
            task.status ===
            "completed"
              ? "text-emerald-400"
              : "text-zinc-500"
          }
        />
      </div>

      <div className="min-w-0 flex-1">

        <p className="truncate text-sm font-medium text-zinc-200">
          {task.title}
        </p>

        <p className="mt-1 truncate text-xs text-zinc-600">
          {task.description ||
            "No description"}
        </p>

      </div>

      <span
        className={`
          hidden
          shrink-0
          rounded-full
          border
          px-2.5
          py-1
          text-[10px]
          font-semibold
          uppercase
          tracking-[0.08em]
          sm:inline-flex
          ${
            task.status ===
            "completed"
              ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-400"
              : "border-zinc-800 text-zinc-500"
          }
        `}
      >
        {task.status.replace(
          "_",
          " ",
        )}
      </span>

      <span className="shrink-0 text-xs text-zinc-700">
        →
      </span>

    </button>
  );
}

/* =========================================================
   SUMMARY ITEM
   ========================================================= */

type SummaryItemProps = {
  label: string;
  value: number;
};

function SummaryItem({
  label,
  value,
}: SummaryItemProps) {
  return (
    <div className="border-zinc-800/80 px-6 py-5 sm:border-r lg:last:border-r-0">

      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-600">
        {label}
      </p>

      <p className="mt-2 text-lg font-semibold text-zinc-200">
        {value}
      </p>

    </div>
  );
}

export default ProjectDetailPage;