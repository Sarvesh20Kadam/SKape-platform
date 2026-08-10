import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  CheckSquare,
  ChevronDown,
  Filter,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "lucide-react";

import DashboardLayout from "../components/layout/DashboardLayout";

import CreateTaskModal from "../features/task/components/CreateTaskModal";
import EditTaskModal from "../features/task/components/EditTaskModal";

import { useTask } from "../features/task/hooks/useTask";
import { useProjects } from "../hooks/useProjects";

import type {
  Task,
  TaskPriority,
  TaskStatus,
  UpdateTaskPayload,
} from "../features/task/types/task.types";

function TasksPage() {
  const navigate = useNavigate();

  const {
    tasks,
    loading,
    creating,
    updating,
    deleting,
    error,
    addTask,
    editTask,
    removeTask,
  } = useTask();

  const { projects } = useProjects();

  const [createModalOpen, setCreateModalOpen] =
    useState(false);

  const [editModalOpen, setEditModalOpen] =
    useState(false);

  const [selectedTask, setSelectedTask] =
    useState<Task | null>(null);

  const [openMenuId, setOpenMenuId] =
    useState<number | null>(null);

  const [deleteTaskId, setDeleteTaskId] =
    useState<number | null>(null);

  const [search, setSearch] = useState("");

  const [statusFilter, setStatusFilter] =
    useState<"all" | TaskStatus>("all");

  /*
   * =========================================================
   * FILTER TASKS
   * =========================================================
   */

  const filteredTasks = useMemo(() => {
    const query = search.trim().toLowerCase();

    return tasks.filter((task) => {
      const matchesSearch =
        !query ||
        task.title
          .toLowerCase()
          .includes(query) ||
        task.description
          ?.toLowerCase()
          .includes(query);

      const matchesStatus =
        statusFilter === "all" ||
        task.status === statusFilter;

      return (
        matchesSearch &&
        matchesStatus
      );
    });
  }, [
    tasks,
    search,
    statusFilter,
  ]);

  /*
   * =========================================================
   * CREATE TASK
   * =========================================================
   */

  const handleCreateTask = async (
    data: Parameters<typeof addTask>[0],
  ) => {
    const createdTask =
      await addTask(data);

    if (createdTask) {
      setCreateModalOpen(false);
    }
  };

  /*
   * =========================================================
   * OPEN EDIT MODAL
   * =========================================================
   */

  const handleOpenEdit = (
    task: Task,
  ) => {
    setOpenMenuId(null);

    setSelectedTask(task);

    setEditModalOpen(true);
  };

  /*
   * =========================================================
   * CLOSE EDIT MODAL
   * =========================================================
   */

  const handleCloseEdit = () => {
    if (updating) {
      return;
    }

    setEditModalOpen(false);

    setSelectedTask(null);
  };

  /*
   * =========================================================
   * SAVE EDITED TASK
   * =========================================================
   */

  const handleEditTask = async (
    taskId: number,
    data: UpdateTaskPayload,
  ) => {
    const updatedTask =
      await editTask(
        taskId,
        data,
      );

    if (updatedTask) {
      setEditModalOpen(false);

      setSelectedTask(null);
    }
  };

  /*
   * =========================================================
   * REQUEST DELETE
   * =========================================================
   */

  const handleRequestDelete = (
    task: Task,
  ) => {
    setOpenMenuId(null);

    setDeleteTaskId(task.id);
  };

  /*
   * =========================================================
   * CANCEL DELETE
   * =========================================================
   */

  const handleCancelDelete = () => {
    if (deleting) {
      return;
    }

    setDeleteTaskId(null);
  };

  /*
   * =========================================================
   * CONFIRM DELETE
   * =========================================================
   */

  const handleConfirmDelete = async () => {
    if (deleteTaskId === null) {
      return;
    }

    const success =
      await removeTask(
        deleteTaskId,
      );

    if (success) {
      setDeleteTaskId(null);
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-8">

        {/* =====================================================
            PAGE HEADER
            ===================================================== */}

        <section className="border-b border-zinc-800/80 pb-8">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">

            <div>
              <div className="mb-3 flex items-center gap-2">

                <span className="h-2 w-2 rounded-full bg-emerald-500" />

                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
                  Workspace
                </span>

              </div>

              <h1 className="text-3xl font-semibold tracking-[-0.03em] text-zinc-100">
                Tasks
              </h1>

              <p className="mt-2 text-sm text-zinc-500">
                Manage and organize work
                across your workspace.
              </p>
            </div>

            <button
              type="button"
              onClick={() =>
                setCreateModalOpen(true)
              }
              className="
                inline-flex
                h-11
                shrink-0
                items-center
                justify-center
                gap-2
                rounded-lg
                bg-emerald-500
                px-5
                text-sm
                font-semibold
                text-zinc-950
                transition-colors
                hover:bg-emerald-400
              "
            >
              <Plus
                size={17}
                strokeWidth={2.2}
              />

              New task
            </button>

          </div>
        </section>

        {/* =====================================================
            SEARCH + FILTER
            ===================================================== */}

        <section className="flex flex-col gap-3 sm:flex-row">

          {/* Search */}

          <div className="relative min-w-0 flex-1">

            <Search
              size={17}
              strokeWidth={1.8}
              className="
                pointer-events-none
                absolute
                left-3.5
                top-1/2
                -translate-y-1/2
                text-zinc-600
              "
            />

            <input
              type="search"
              value={search}
              onChange={(event) =>
                setSearch(
                  event.target.value,
                )
              }
              placeholder="Search tasks..."
              aria-label="Search tasks"
              className="
                h-11
                w-full
                rounded-lg
                border
                border-zinc-800
                bg-zinc-900/50
                pl-10
                pr-4
                text-sm
                text-zinc-200
                outline-none
                transition-all
                placeholder:text-zinc-600
                hover:border-zinc-700
                focus:border-emerald-500/40
                focus:bg-zinc-900
                focus:ring-1
                focus:ring-emerald-500/10
              "
            />

          </div>

          {/* Status filter */}

          <div className="relative">

            <Filter
              size={15}
              strokeWidth={1.8}
              className="
                pointer-events-none
                absolute
                left-3
                top-1/2
                -translate-y-1/2
                text-zinc-600
              "
            />

            <select
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(
                  event.target.value as
                    | "all"
                    | TaskStatus,
                )
              }
              className="
                h-11
                w-full
                appearance-none
                rounded-lg
                border
                border-zinc-800
                bg-zinc-900/50
                pl-9
                pr-10
                text-sm
                text-zinc-300
                outline-none
                transition
                hover:border-zinc-700
                focus:border-emerald-500/40
                sm:w-44
              "
              aria-label="Filter tasks by status"
            >
              <option value="all">
                All tasks
              </option>

              <option value="todo">
                To do
              </option>

              <option value="in_progress">
                In progress
              </option>

              <option value="completed">
                Completed
              </option>

              <option value="cancelled">
                Cancelled
              </option>

            </select>

            <ChevronDown
              size={15}
              className="
                pointer-events-none
                absolute
                right-3
                top-1/2
                -translate-y-1/2
                text-zinc-600
              "
            />

          </div>

        </section>

        {/* =====================================================
            SUMMARY
            ===================================================== */}

        <div className="flex items-center justify-between">

          <div>

            <h2 className="text-sm font-semibold text-zinc-200">
              All tasks
            </h2>

            <p className="mt-1 text-xs text-zinc-600">
              {filteredTasks.length}{" "}
              {filteredTasks.length === 1
                ? "task"
                : "tasks"}
            </p>

          </div>

        </div>

        {/* =====================================================
            LOADING
            ===================================================== */}

        {loading && (
          <div className="space-y-3">

            {[1, 2, 3].map(
              (item) => (
                <div
                  key={item}
                  className="
                    h-28
                    animate-pulse
                    rounded-xl
                    border
                    border-zinc-800
                    bg-zinc-900/50
                  "
                />
              ),
            )}

          </div>
        )}

        {/* =====================================================
            ERROR
            ===================================================== */}

        {!loading && error && (
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
            {error}
          </div>
        )}

        {/* =====================================================
            TASK LIST
            ===================================================== */}

        {!loading &&
          !error &&
          filteredTasks.length > 0 && (

            <div className="space-y-2">

              {filteredTasks.map(
                (task) => (

                  <TaskCard
                    key={task.id}
                    task={task}
                    menuOpen={
                      openMenuId ===
                      task.id
                    }

                    onOpen={() =>
                      navigate(
                        `/tasks/${task.id}`,
                      )
                    }

                    onMenuToggle={() =>
                      setOpenMenuId(
                        (current) =>
                          current ===
                          task.id
                            ? null
                            : task.id,
                      )
                    }

                    onEdit={() =>
                      handleOpenEdit(
                        task,
                      )
                    }

                    onDelete={() =>
                      handleRequestDelete(
                        task,
                      )
                    }
                  />

                ),
              )}

            </div>
          )}

        {/* =====================================================
            EMPTY STATE
            ===================================================== */}

        {!loading &&
          !error &&
          filteredTasks.length === 0 && (

            <div
              className="
                rounded-xl
                border
                border-zinc-800
                bg-zinc-950
              "
            >

              <div
                className="
                  flex
                  min-h-[300px]
                  flex-col
                  items-center
                  justify-center
                  px-6
                  text-center
                "
              >

                <div
                  className="
                    mb-4
                    flex
                    h-12
                    w-12
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
                    strokeWidth={1.7}
                    className="text-zinc-500"
                  />
                </div>

                <h2 className="text-base font-semibold text-zinc-200">
                  {tasks.length === 0
                    ? "No tasks yet"
                    : "No tasks found"}
                </h2>

                <p className="mt-2 max-w-sm text-sm leading-6 text-zinc-500">
                  {tasks.length === 0
                    ? "Create your first task and start organizing work."
                    : "Try changing your search or status filter."}
                </p>

                {tasks.length === 0 && (

                  <button
                    type="button"
                    onClick={() =>
                      setCreateModalOpen(
                        true,
                      )
                    }
                    className="
                      mt-5
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

                    Create task
                  </button>

                )}

              </div>

            </div>
          )}

      </div>

      {/* =====================================================
          CREATE TASK MODAL
          ===================================================== */}

      <CreateTaskModal
        open={createModalOpen}
        loading={creating}
        error={error}
        projects={projects.map(
          (project) => ({
            id: project.id,
            name: project.name,
          }),
        )}
        onClose={() =>
          setCreateModalOpen(false)
        }
        onSubmit={handleCreateTask}
      />

      {/* =====================================================
          EDIT TASK MODAL
          ===================================================== */}

      <EditTaskModal
        open={editModalOpen}
        task={selectedTask}
        loading={updating}
        error={error}
        projects={projects.map(
          (project) => ({
            id: project.id,
            name: project.name,
          }),
        )}
        onClose={handleCloseEdit}
        onSubmit={handleEditTask}
      />

      {/* =====================================================
          DELETE CONFIRMATION
          ===================================================== */}

      {deleteTaskId !== null && (

        <DeleteTaskDialog
          loading={deleting}
          onCancel={
            handleCancelDelete
          }
          onConfirm={
            handleConfirmDelete
          }
        />

      )}

    </DashboardLayout>
  );
}

/* =========================================================
   TASK CARD
   ========================================================= */

type TaskCardProps = {
  task: Task;
  menuOpen: boolean;
  onOpen: () => void;
  onMenuToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
};

function TaskCard({
  task,
  menuOpen,
  onOpen,
  onMenuToggle,
  onEdit,
  onDelete,
}: TaskCardProps) {
  const statusLabel: Record<
    TaskStatus,
    string
  > = {
    todo: "TO DO",
    in_progress: "IN PROGRESS",
    completed: "COMPLETED",
    cancelled: "CANCELLED",
  };

  const priorityLabel: Record<
    TaskPriority,
    string
  > = {
    low: "LOW",
    medium: "MEDIUM",
    high: "HIGH",
    urgent: "URGENT",
  };

  return (
    <article
      onClick={onOpen}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (
          event.key === "Enter" ||
          event.key === " "
        ) {
          event.preventDefault();
          onOpen();
        }
      }}
      className="
        relative
        cursor-pointer
        rounded-xl
        border
        border-zinc-800
        bg-zinc-950
        px-5
        py-4
        outline-none
        transition-colors
        hover:border-zinc-700
        hover:bg-zinc-900/30
        focus-visible:border-emerald-500/40
        focus-visible:ring-1
        focus-visible:ring-emerald-500/20
      "
    >

      <div className="flex items-start gap-4">

        {/* =================================================
            TASK ICON
            ================================================= */}

        <div
          className="
            mt-0.5
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
            size={17}
            strokeWidth={1.7}
            className={
              task.status ===
              "completed"
                ? "text-emerald-400"
                : "text-zinc-500"
            }
          />
        </div>

        {/* =================================================
            TASK CONTENT
            ================================================= */}

        <div className="min-w-0 flex-1">

          <div className="flex items-center gap-2 pr-10">

            <h3 className="truncate text-sm font-semibold text-zinc-200">
              {task.title}
            </h3>

            <span
              className={`
                shrink-0
                rounded-full
                border
                px-2
                py-0.5
                text-[10px]
                font-semibold
                tracking-[0.08em]
                ${
                  task.status ===
                  "completed"
                    ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-400"
                    : "border-zinc-800 text-zinc-500"
                }
              `}
            >
              {
                statusLabel[
                  task.status
                ]
              }
            </span>

          </div>

          {task.description && (

            <p className="mt-1.5 line-clamp-2 text-sm leading-6 text-zinc-500">
              {task.description}
            </p>

          )}

          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2">

            {/* Priority */}

            <div className="flex items-center gap-2">

              <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-600">
                Priority
              </span>

              <span
                className={
                  task.priority ===
                  "urgent"
                    ? "text-xs font-medium text-red-400"
                    : task.priority ===
                        "high"
                      ? "text-xs font-medium text-orange-400"
                      : task.priority ===
                          "medium"
                        ? "text-xs font-medium text-amber-400"
                        : "text-xs font-medium text-zinc-500"
                }
              >
                {
                  priorityLabel[
                    task.priority
                  ]
                }
              </span>

            </div>

            {/* Project */}

            <span className="text-xs text-zinc-700">
              Project #{task.project_id}
            </span>

            {/* Due date */}

            {task.due_date && (

              <span className="text-xs text-zinc-600">
                Due{" "}
                {new Date(
                  task.due_date,
                ).toLocaleDateString()}
              </span>

            )}

          </div>

        </div>

        {/* =================================================
            TASK ACTIONS
            ================================================= */}

        <div
          className="absolute right-4 top-4"
          onClick={(event) =>
            event.stopPropagation()
          }
        >

          <button
            type="button"
            aria-label={`Actions for ${task.title}`}
            aria-expanded={menuOpen}
            onClick={(event) => {
              event.stopPropagation();

              onMenuToggle();
            }}
            className="
              flex
              h-8
              w-8
              items-center
              justify-center
              rounded-lg
              text-zinc-600
              transition-colors
              hover:bg-zinc-900
              hover:text-zinc-300
            "
          >
            <MoreHorizontal
              size={18}
              strokeWidth={1.8}
            />
          </button>

          {menuOpen && (

            <div
              className="
                absolute
                right-0
                top-9
                z-20
                w-40
                overflow-hidden
                rounded-xl
                border
                border-zinc-800
                bg-zinc-950
                p-1
                shadow-xl
                shadow-black/40
              "
              onClick={(event) =>
                event.stopPropagation()
              }
            >

              {/* Edit */}

              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();

                  onEdit();
                }}
                className="
                  flex
                  w-full
                  items-center
                  gap-2.5
                  rounded-lg
                  px-3
                  py-2.5
                  text-left
                  text-sm
                  text-zinc-400
                  transition-colors
                  hover:bg-zinc-900
                  hover:text-zinc-100
                "
              >
                <Pencil
                  size={15}
                  strokeWidth={1.8}
                />

                Edit task
              </button>

              {/* Delete */}

              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();

                  onDelete();
                }}
                className="
                  flex
                  w-full
                  items-center
                  gap-2.5
                  rounded-lg
                  px-3
                  py-2.5
                  text-left
                  text-sm
                  text-red-400
                  transition-colors
                  hover:bg-red-500/10
                "
              >
                <Trash2
                  size={15}
                  strokeWidth={1.8}
                />

                Delete task
              </button>

            </div>
          )}

        </div>

      </div>

    </article>
  );
}

/* =========================================================
   DELETE DIALOG
   ========================================================= */

type DeleteTaskDialogProps = {
  loading: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

function DeleteTaskDialog({
  loading,
  onCancel,
  onConfirm,
}: DeleteTaskDialogProps) {
  return (
    <div
      className="
        fixed
        inset-0
        z-[110]
        flex
        items-center
        justify-center
        bg-black/60
        px-4
        backdrop-blur-[2px]
      "
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-task-title"
    >

      <div
        className="
          w-full
          max-w-md
          rounded-2xl
          border
          border-zinc-800
          bg-zinc-950
          p-6
          shadow-2xl
          shadow-black/50
        "
      >

        <div
          className="
            flex
            h-10
            w-10
            items-center
            justify-center
            rounded-xl
            border
            border-red-500/20
            bg-red-500/10
          "
        >
          <Trash2
            size={18}
            className="text-red-400"
          />
        </div>

        <h2
          id="delete-task-title"
          className="mt-5 text-base font-semibold text-zinc-100"
        >
          Delete task?
        </h2>

        <p className="mt-2 text-sm leading-6 text-zinc-500">
          This action permanently removes
          the task from your workspace.
          This cannot be undone.
        </p>

        <div className="mt-6 flex justify-end gap-3">

          <button
            type="button"
            disabled={loading}
            onClick={onCancel}
            className="
              h-10
              rounded-lg
              px-4
              text-sm
              font-medium
              text-zinc-500
              transition-colors
              hover:bg-zinc-900
              hover:text-zinc-200
              disabled:pointer-events-none
              disabled:opacity-40
            "
          >
            Cancel
          </button>

          <button
            type="button"
            disabled={loading}
            onClick={onConfirm}
            className="
              inline-flex
              h-10
              min-w-[110px]
              items-center
              justify-center
              gap-2
              rounded-lg
              bg-red-500
              px-4
              text-sm
              font-semibold
              text-white
              transition-colors
              hover:bg-red-400
              disabled:cursor-not-allowed
              disabled:opacity-50
            "
          >
            {loading
              ? "Deleting..."
              : "Delete task"}
          </button>

        </div>

      </div>

    </div>
  );
}

export default TasksPage;