import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  CheckSquare,
  ChevronDown,
  Pencil,
} from "lucide-react";

import DashboardLayout from "../components/layout/DashboardLayout";

import EditTaskModal from "../features/task/components/EditTaskModal";
import { useTaskDetail } from "../features/task/hooks/useTaskDetail";
import { updateTask } from "../features/task/services/task.service";

import { useProjects } from "../hooks/useProjects";

import type {
  TaskStatus,
  UpdateTaskPayload,
} from "../features/task/types/task.types";

function TaskDetailPage() {
  const navigate = useNavigate();

  const { taskId } = useParams<{
    taskId: string;
  }>();

  const numericTaskId = Number(taskId);

  const {
    task,
    loading,
    error,
    fetchTask,
  } = useTaskDetail({
    taskId: numericTaskId,
  });

  const {
    projects,
  } = useProjects();

  const [editOpen, setEditOpen] =
    useState(false);

  const [saving, setSaving] =
    useState(false);

  const [editError, setEditError] =
    useState<string | null>(null);

  const [statusOpen, setStatusOpen] =
    useState(false);

  const [statusUpdating, setStatusUpdating] =
    useState(false);

  /*
   * =========================================================
   * EDIT TASK
   * =========================================================
   */

  const handleEditSubmit = async (
    taskId: number,
    data: UpdateTaskPayload,
  ) => {
    try {
      setSaving(true);
      setEditError(null);

      await updateTask(
        taskId,
        data,
      );

      /*
       * Refresh the task from the backend
       * so the page always shows the actual
       * saved state.
       */
      await fetchTask();

      setEditOpen(false);
    } catch (err) {
      console.error(
        "Failed to update task:",
        err,
      );

      setEditError(
        "Unable to update this task. Please try again.",
      );
    } finally {
      setSaving(false);
    }
  };

  /*
   * =========================================================
   * STATUS UPDATE
   * =========================================================
   */

  const handleStatusChange = async (
    status: TaskStatus,
  ) => {
    if (!task) {
      return;
    }

    if (status === task.status) {
      setStatusOpen(false);
      return;
    }

    try {
      setStatusUpdating(true);
      setStatusOpen(false);
      setEditError(null);

      await updateTask(
        task.id,
        {
          status,
        },
      );

      await fetchTask();
    } catch (err) {
      console.error(
        "Failed to update task status:",
        err,
      );

      setEditError(
        "Unable to update task status. Please try again.",
      );
    } finally {
      setStatusUpdating(false);
    }
  };

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

          <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950">

            <div className="border-b border-zinc-800/80 px-6 py-8 sm:px-8">
              <div className="flex items-start gap-4">

                <div className="h-14 w-14 animate-pulse rounded-xl bg-zinc-900" />

                <div className="flex-1 space-y-4">

                  <div className="h-5 w-32 animate-pulse rounded bg-zinc-900" />

                  <div className="h-9 w-2/3 animate-pulse rounded bg-zinc-900" />

                  <div className="h-4 w-20 animate-pulse rounded bg-zinc-900" />

                </div>

              </div>
            </div>

            <div className="space-y-4 px-6 py-8 sm:px-8">

              <div className="h-4 w-24 animate-pulse rounded bg-zinc-900" />

              <div className="h-20 w-full animate-pulse rounded bg-zinc-900" />

            </div>

            <div className="grid border-t border-zinc-800/80 sm:grid-cols-2 lg:grid-cols-4">

              {Array.from({
                length: 4,
              }).map((_, index) => (
                <div
                  key={index}
                  className="h-24 animate-pulse border-zinc-800/80 bg-zinc-950 px-6 py-5 sm:border-r"
                />
              ))}

            </div>

          </div>

        </div>
      </DashboardLayout>
    );
  }

  /*
   * =========================================================
   * ERROR
   * =========================================================
   */

  if (error) {
    return (
      <DashboardLayout>
        <div className="mx-auto w-full max-w-[1480px]">

          <button
            type="button"
            onClick={() =>
              navigate("/tasks")
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

            Back to tasks
          </button>

          <div className="mt-8 rounded-xl border border-red-500/20 bg-red-500/5 p-5 text-sm text-red-400">
            {error}
          </div>

        </div>
      </DashboardLayout>
    );
  }

  /*
   * =========================================================
   * TASK NOT FOUND
   * =========================================================
   */

  if (!task) {
    return (
      <DashboardLayout>
        <div className="mx-auto w-full max-w-[1480px]">

          <button
            type="button"
            onClick={() =>
              navigate("/tasks")
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

            Back to tasks
          </button>

          <div className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-950 p-8">

            <h1 className="text-lg font-semibold text-zinc-200">
              Task not found
            </h1>

            <p className="mt-2 text-sm text-zinc-500">
              This task may have been deleted
              or you may not have access to it.
            </p>

            <button
              type="button"
              onClick={() =>
                navigate("/tasks")
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
              <ArrowLeft size={16} />

              Back to tasks
            </button>

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
              navigate("/tasks")
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

            Back to tasks
          </button>

          <button
            type="button"
            disabled={statusUpdating || saving}
            onClick={() => {
              setEditError(null);
              setEditOpen(true);
            }}
            className="
              inline-flex
              h-10
              items-center
              gap-2
              rounded-lg
              border
              border-zinc-800
              bg-zinc-950
              px-4
              text-sm
              font-medium
              text-zinc-400
              transition-all
              hover:border-zinc-700
              hover:bg-zinc-900
              hover:text-zinc-200
              disabled:cursor-not-allowed
              disabled:opacity-50
            "
          >
            <Pencil size={15} />

            Edit
          </button>

        </div>

        {/* =====================================================
            ERROR FROM UPDATE
            ===================================================== */}

        {editError && (
          <div
            role="alert"
            className="
              rounded-xl
              border
              border-red-500/20
              bg-red-500/5
              px-5
              py-4
              text-sm
              text-red-400
            "
          >
            {editError}
          </div>
        )}

        {/* =====================================================
            MAIN TASK
            ===================================================== */}

        <section className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950">

          {/* ===================================================
              TASK HEADER
              =================================================== */}

          <div className="border-b border-zinc-800/80 px-6 py-8 sm:px-8">

            <div className="flex items-start gap-4">

              {/* Task icon */}

              <div
                className="
                  mt-1
                  flex
                  h-14
                  w-14
                  shrink-0
                  items-center
                  justify-center
                  rounded-xl
                  border
                  border-zinc-800
                  bg-zinc-900
                "
              >
                <CheckSquare
                  size={21}
                  strokeWidth={1.8}
                  className={
                    task.status ===
                    "completed"
                      ? "text-emerald-400"
                      : "text-zinc-500"
                  }
                />
              </div>

              {/* Task heading */}

              <div className="min-w-0 flex-1">

                {/* Status + Priority */}

                <div className="flex flex-wrap items-center gap-2">

                  {/* Status dropdown */}

                  <div className="relative">

                    <button
                      type="button"
                      disabled={
                        statusUpdating
                      }
                      aria-haspopup="menu"
                      aria-expanded={
                        statusOpen
                      }
                      onClick={() =>
                        setStatusOpen(
                          (current) =>
                            !current,
                        )
                      }
                      className={`
                        inline-flex
                        items-center
                        gap-2
                        rounded-full
                        border
                        px-2.5
                        py-1
                        text-[10px]
                        font-semibold
                        uppercase
                        tracking-[0.1em]
                        transition-colors
                        disabled:cursor-not-allowed
                        disabled:opacity-60
                        ${
                          task.status ===
                          "completed"
                            ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-400"
                            : task.status ===
                                "cancelled"
                              ? "border-red-500/20 bg-red-500/5 text-red-400"
                              : "border-zinc-800 text-zinc-500 hover:border-zinc-700 hover:bg-zinc-900 hover:text-zinc-300"
                        }
                      `}
                    >
                      {statusUpdating
                        ? "Updating..."
                        : formatStatus(
                            task.status,
                          )}

                      <ChevronDown
                        size={11}
                        strokeWidth={2}
                      />
                    </button>

                    {/* Status menu */}

                    {statusOpen && (
                      <div
                        role="menu"
                        className="
                          absolute
                          left-0
                          top-8
                          z-30
                          w-44
                          overflow-hidden
                          rounded-xl
                          border
                          border-zinc-800
                          bg-zinc-950
                          p-1
                          shadow-xl
                          shadow-black/40
                        "
                      >

                        <StatusOption
                          label="To do"
                          value="todo"
                          current={
                            task.status
                          }
                          onSelect={
                            handleStatusChange
                          }
                        />

                        <StatusOption
                          label="In progress"
                          value="in_progress"
                          current={
                            task.status
                          }
                          onSelect={
                            handleStatusChange
                          }
                        />

                        <StatusOption
                          label="Completed"
                          value="completed"
                          current={
                            task.status
                          }
                          onSelect={
                            handleStatusChange
                          }
                        />

                        <StatusOption
                          label="Cancelled"
                          value="cancelled"
                          current={
                            task.status
                          }
                          onSelect={
                            handleStatusChange
                          }
                        />

                      </div>
                    )}

                  </div>

                  {/* Priority */}

                  <span className="rounded-full border border-zinc-800 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-zinc-500">
                    {task.priority}
                  </span>

                </div>

                {/* Title */}

                <h1 className="mt-4 break-words text-2xl font-semibold tracking-[-0.025em] text-zinc-100 sm:text-3xl">
                  {task.title}
                </h1>

                {/* ID */}

                <p className="mt-2 text-xs text-zinc-600">
                  Task #{task.id}
                </p>

              </div>

            </div>

          </div>

          {/* ===================================================
              DESCRIPTION
              =================================================== */}

          <div className="px-6 py-8 sm:px-8">

            <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-zinc-600">
              Description
            </h2>

            <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-zinc-400">
              {task.description ||
                "No description provided."}
            </p>

          </div>

          {/* ===================================================
              METADATA
              =================================================== */}

          <div className="grid border-t border-zinc-800/80 sm:grid-cols-2 lg:grid-cols-4">

            <InfoItem
              label="Project"
              value={`Project #${task.project_id}`}
            />

            <InfoItem
              label="Priority"
              value={task.priority}
            />

            <InfoItem
              label="Due date"
              value={
                task.due_date
                  ? new Date(
                      task.due_date,
                    ).toLocaleDateString()
                  : "No due date"
              }
            />

            <InfoItem
              label="Assigned to"
              value={
                task.assigned_to
                  ? `User #${task.assigned_to}`
                  : "Unassigned"
              }
            />

          </div>

        </section>

        {/* =====================================================
            ACTIVITY
            ===================================================== */}

        <section className="rounded-2xl border border-zinc-800 bg-zinc-950 p-6 sm:p-8">

          <h2 className="text-sm font-semibold text-zinc-200">
            Activity
          </h2>

          <p className="mt-2 text-sm text-zinc-600">
            Task activity will appear here.
          </p>

        </section>

      </div>

      {/* =====================================================
          EDIT TASK MODAL
          ===================================================== */}

      <EditTaskModal
        open={editOpen}
        task={task}
        loading={saving}
        error={editError}
        projects={projects}
        onClose={() => {
          if (!saving) {
            setEditOpen(false);
            setEditError(null);
          }
        }}
        onSubmit={handleEditSubmit}
      />

    </DashboardLayout>
  );
}

/* =========================================================
   STATUS OPTION
   ========================================================= */

type StatusOptionProps = {
  label: string;
  value: TaskStatus;
  current: TaskStatus;
  onSelect: (
    status: TaskStatus,
  ) => void;
};

function StatusOption({
  label,
  value,
  current,
  onSelect,
}: StatusOptionProps) {
  const isActive =
    current === value;

  return (
    <button
      type="button"
      role="menuitem"
      onClick={() =>
        onSelect(value)
      }
      className={`
        flex
        w-full
        items-center
        justify-between
        rounded-lg
        px-3
        py-2.5
        text-left
        text-sm
        transition-colors
        ${
          isActive
            ? "bg-zinc-900 text-zinc-200"
            : "text-zinc-500 hover:bg-zinc-900 hover:text-zinc-200"
        }
      `}
    >
      <span>{label}</span>

      {isActive && (
        <Check
          size={15}
          strokeWidth={2}
          className="text-emerald-400"
        />
      )}
    </button>
  );
}

/* =========================================================
   STATUS FORMATTER
   ========================================================= */

function formatStatus(
  status: TaskStatus,
) {
  switch (status) {
    case "todo":
      return "To do";

    case "in_progress":
      return "In progress";

    case "completed":
      return "Completed";

    case "cancelled":
      return "Cancelled";

    default:
      return status;
  }
}

/* =========================================================
   INFO ITEM
   ========================================================= */

type InfoItemProps = {
  label: string;
  value: string;
};

function InfoItem({
  label,
  value,
}: InfoItemProps) {
  return (
    <div className="border-zinc-800/80 px-6 py-5 sm:border-r lg:last:border-r-0">

      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-600">
        {label}
      </p>

      <p className="mt-2 truncate text-sm font-medium capitalize text-zinc-300">
        {value}
      </p>

    </div>
  );
}

export default TaskDetailPage;