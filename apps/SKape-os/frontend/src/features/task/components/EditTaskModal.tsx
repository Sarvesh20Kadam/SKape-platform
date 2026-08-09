import { useEffect, useRef, useState } from "react";
import {
  CalendarDays,
  CheckSquare,
  Loader2,
  X,
} from "lucide-react";

import type {
  Task,
  TaskPriority,
  TaskStatus,
  UpdateTaskPayload,
} from "../types/task.types";

type ProjectOption = {
  id: number;
  name: string;
};

type EditTaskModalProps = {
  open: boolean;
  task: Task | null;
  loading?: boolean;
  error?: string | null;
  projects: ProjectOption[];
  onClose: () => void;
  onSubmit: (
    taskId: number,
    data: UpdateTaskPayload,
  ) => Promise<void> | void;
};

function EditTaskModal({
  open,
  task,
  loading = false,
  error = null,
  projects,
  onClose,
  onSubmit,
}: EditTaskModalProps) {
  const titleRef =
    useRef<HTMLInputElement | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] =
    useState("");
  const [projectId, setProjectId] =
    useState("");
  const [priority, setPriority] =
    useState<TaskPriority>("medium");
  const [status, setStatus] =
    useState<TaskStatus>("todo");
  const [dueDate, setDueDate] =
    useState("");

  const [validationError, setValidationError] =
    useState<string | null>(null);

  /*
   * Populate the form whenever
   * a task is selected.
   */
  useEffect(() => {
    if (!open || !task) {
      return;
    }

    setTitle(task.title);
    setDescription(task.description ?? "");
    setProjectId(String(task.project_id));
    setPriority(task.priority);
    setStatus(task.status);

    if (task.due_date) {
      setDueDate(
        task.due_date.slice(0, 10),
      );
    } else {
      setDueDate("");
    }

    setValidationError(null);

    const timer = window.setTimeout(() => {
      titleRef.current?.focus();
    }, 50);

    return () => {
      window.clearTimeout(timer);
    };
  }, [open, task]);

  /*
   * Escape closes the modal.
   */
  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKeyDown = (
      event: KeyboardEvent,
    ) => {
      if (
        event.key === "Escape" &&
        !loading
      ) {
        onClose();
      }
    };

    window.addEventListener(
      "keydown",
      handleKeyDown,
    );

    return () => {
      window.removeEventListener(
        "keydown",
        handleKeyDown,
      );
    };
  }, [open, loading, onClose]);

  if (!open || !task) {
    return null;
  }

  const handleSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    const trimmedTitle =
      title.trim();

    const trimmedDescription =
      description.trim();

    if (!trimmedTitle) {
      setValidationError(
        "Task title is required.",
      );
      titleRef.current?.focus();
      return;
    }

    if (trimmedTitle.length < 2) {
      setValidationError(
        "Task title must contain at least 2 characters.",
      );
      titleRef.current?.focus();
      return;
    }

    if (trimmedTitle.length > 200) {
      setValidationError(
        "Task title cannot exceed 200 characters.",
      );
      titleRef.current?.focus();
      return;
    }

    if (trimmedDescription.length > 2000) {
      setValidationError(
        "Description cannot exceed 2000 characters.",
      );
      return;
    }

    if (!projectId) {
      setValidationError(
        "Please select a project.",
      );
      return;
    }

    setValidationError(null);

    const payload: UpdateTaskPayload = {
      title: trimmedTitle,
      description:
        trimmedDescription || undefined,
      status,
      priority,
      project_id: Number(projectId),
      due_date: dueDate
        ? new Date(
            `${dueDate}T23:59:59`,
          ).toISOString()
        : null,
    };

    await onSubmit(
      task.id,
      payload,
    );
  };

  const displayError =
    validationError || error;

  return (
    <div
      className="
        fixed
        inset-0
        z-[100]
        flex
        items-center
        justify-center
        bg-black/60
        px-4
        py-6
        backdrop-blur-[2px]
      "
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-task-title"
    >
      <div
        className="
          relative
          w-full
          max-w-xl
          overflow-hidden
          rounded-2xl
          border
          border-zinc-800
          bg-zinc-950
          shadow-2xl
          shadow-black/50
        "
      >
        <div className="h-px w-full bg-emerald-500/70" />

        {/* Header */}
        <div
          className="
            flex
            items-start
            justify-between
            border-b
            border-zinc-800/80
            px-6
            py-5
          "
        >
          <div className="flex items-start gap-4">
            <div
              className="
                flex
                h-10
                w-10
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
                size={18}
                strokeWidth={1.8}
                className="text-emerald-400"
              />
            </div>

            <div>
              <h2
                id="edit-task-title"
                className="
                  text-base
                  font-semibold
                  tracking-[-0.01em]
                  text-zinc-100
                "
              >
                Edit task
              </h2>

              <p className="mt-1 text-sm text-zinc-500">
                Update this task's details.
              </p>
            </div>
          </div>

          <button
            type="button"
            disabled={loading}
            onClick={onClose}
            aria-label="Close"
            className="
              rounded-lg
              p-2
              text-zinc-600
              transition-colors
              hover:bg-zinc-900
              hover:text-zinc-300
              disabled:pointer-events-none
              disabled:opacity-40
            "
          >
            <X size={18} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div className="space-y-5 px-6 py-6">
            {/* Title */}
            <div>
              <label
                htmlFor="edit-task-title-input"
                className="
                  mb-2
                  block
                  text-xs
                  font-semibold
                  uppercase
                  tracking-[0.12em]
                  text-zinc-500
                "
              >
                Task title
              </label>

              <input
                ref={titleRef}
                id="edit-task-title-input"
                type="text"
                value={title}
                disabled={loading}
                maxLength={200}
                onChange={(event) => {
                  setTitle(
                    event.target.value,
                  );
                  setValidationError(null);
                }}
                className="
                  h-11
                  w-full
                  rounded-lg
                  border
                  border-zinc-800
                  bg-zinc-900/60
                  px-3.5
                  text-sm
                  text-zinc-100
                  outline-none
                  transition
                  placeholder:text-zinc-600
                  hover:border-zinc-700
                  focus:border-emerald-500/50
                  focus:ring-2
                  focus:ring-emerald-500/10
                  disabled:cursor-not-allowed
                  disabled:opacity-50
                "
              />

              <div className="mt-1.5 flex justify-end">
                <span className="text-[10px] tabular-nums text-zinc-700">
                  {title.length}/200
                </span>
              </div>
            </div>

            {/* Description */}
            <div>
              <label
                htmlFor="edit-task-description"
                className="
                  mb-2
                  block
                  text-xs
                  font-semibold
                  uppercase
                  tracking-[0.12em]
                  text-zinc-500
                "
              >
                Description
              </label>

              <textarea
                id="edit-task-description"
                value={description}
                disabled={loading}
                maxLength={2000}
                rows={3}
                onChange={(event) => {
                  setDescription(
                    event.target.value,
                  );
                  setValidationError(null);
                }}
                className="
                  w-full
                  resize-none
                  rounded-lg
                  border
                  border-zinc-800
                  bg-zinc-900/60
                  px-3.5
                  py-3
                  text-sm
                  leading-6
                  text-zinc-100
                  outline-none
                  transition
                  placeholder:text-zinc-600
                  hover:border-zinc-700
                  focus:border-emerald-500/50
                  focus:ring-2
                  focus:ring-emerald-500/10
                  disabled:cursor-not-allowed
                  disabled:opacity-50
                "
              />

              <div className="mt-1.5 flex justify-end">
                <span className="text-[10px] tabular-nums text-zinc-700">
                  {description.length}/2000
                </span>
              </div>
            </div>

            {/* Project + Priority */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="edit-task-project"
                  className="
                    mb-2
                    block
                    text-xs
                    font-semibold
                    uppercase
                    tracking-[0.12em]
                    text-zinc-500
                  "
                >
                  Project
                </label>

                <select
                  id="edit-task-project"
                  value={projectId}
                  disabled={loading}
                  onChange={(event) => {
                    setProjectId(
                      event.target.value,
                    );
                    setValidationError(null);
                  }}
                  className="
                    h-11
                    w-full
                    rounded-lg
                    border
                    border-zinc-800
                    bg-zinc-900/60
                    px-3
                    text-sm
                    text-zinc-200
                    outline-none
                    transition
                    hover:border-zinc-700
                    focus:border-emerald-500/50
                    focus:ring-2
                    focus:ring-emerald-500/10
                    disabled:cursor-not-allowed
                    disabled:opacity-50
                  "
                >
                  {projects.map(
                    (project) => (
                      <option
                        key={project.id}
                        value={project.id}
                      >
                        {project.name}
                      </option>
                    ),
                  )}
                </select>
              </div>

              <div>
                <label
                  htmlFor="edit-task-priority"
                  className="
                    mb-2
                    block
                    text-xs
                    font-semibold
                    uppercase
                    tracking-[0.12em]
                    text-zinc-500
                  "
                >
                  Priority
                </label>

                <select
                  id="edit-task-priority"
                  value={priority}
                  disabled={loading}
                  onChange={(event) => {
                    setPriority(
                      event.target
                        .value as TaskPriority,
                    );
                    setValidationError(null);
                  }}
                  className="
                    h-11
                    w-full
                    rounded-lg
                    border
                    border-zinc-800
                    bg-zinc-900/60
                    px-3
                    text-sm
                    text-zinc-200
                    outline-none
                    transition
                    hover:border-zinc-700
                    focus:border-emerald-500/50
                    focus:ring-2
                    focus:ring-emerald-500/10
                    disabled:cursor-not-allowed
                    disabled:opacity-50
                  "
                >
                  <option value="low">
                    Low
                  </option>

                  <option value="medium">
                    Medium
                  </option>

                  <option value="high">
                    High
                  </option>

                  <option value="urgent">
                    Urgent
                  </option>
                </select>
              </div>
            </div>

            {/* Status */}
            <div>
              <label
                htmlFor="edit-task-status"
                className="
                  mb-2
                  block
                  text-xs
                  font-semibold
                  uppercase
                  tracking-[0.12em]
                  text-zinc-500
                "
              >
                Status
              </label>

              <select
                id="edit-task-status"
                value={status}
                disabled={loading}
                onChange={(event) => {
                  setStatus(
                    event.target
                      .value as TaskStatus,
                  );
                  setValidationError(null);
                }}
                className="
                  h-11
                  w-full
                  rounded-lg
                  border
                  border-zinc-800
                  bg-zinc-900/60
                  px-3
                  text-sm
                  text-zinc-200
                  outline-none
                  transition
                  hover:border-zinc-700
                  focus:border-emerald-500/50
                  focus:ring-2
                  focus:ring-emerald-500/10
                  disabled:cursor-not-allowed
                  disabled:opacity-50
                "
              >
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
            </div>

            {/* Due date */}
            <div>
              <label
                htmlFor="edit-task-due-date"
                className="
                  mb-2
                  block
                  text-xs
                  font-semibold
                  uppercase
                  tracking-[0.12em]
                  text-zinc-500
                "
              >
                Due date
              </label>

              <div className="relative">
                <CalendarDays
                  size={16}
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
                  id="edit-task-due-date"
                  type="date"
                  value={dueDate}
                  disabled={loading}
                  onChange={(event) => {
                    setDueDate(
                      event.target.value,
                    );
                    setValidationError(null);
                  }}
                  className="
                    h-11
                    w-full
                    rounded-lg
                    border
                    border-zinc-800
                    bg-zinc-900/60
                    pl-10
                    pr-3
                    text-sm
                    text-zinc-200
                    outline-none
                    transition
                    hover:border-zinc-700
                    focus:border-emerald-500/50
                    focus:ring-2
                    focus:ring-emerald-500/10
                    disabled:cursor-not-allowed
                    disabled:opacity-50
                  "
                />
              </div>
            </div>

            {/* Error */}
            {displayError && (
              <div
                role="alert"
                className="
                  rounded-lg
                  border
                  border-red-500/20
                  bg-red-500/5
                  px-3.5
                  py-3
                  text-sm
                  text-red-400
                "
              >
                {displayError}
              </div>
            )}
          </div>

          {/* Footer */}
          <div
            className="
              flex
              items-center
              justify-end
              gap-3
              border-t
              border-zinc-800/80
              bg-zinc-950/80
              px-6
              py-4
            "
          >
            <button
              type="button"
              disabled={loading}
              onClick={onClose}
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
              type="submit"
              disabled={loading}
              className="
                inline-flex
                h-10
                min-w-[130px]
                items-center
                justify-center
                gap-2
                rounded-lg
                bg-emerald-500
                px-5
                text-sm
                font-semibold
                text-zinc-950
                transition-all
                hover:bg-emerald-400
                active:scale-[0.98]
                disabled:cursor-not-allowed
                disabled:opacity-50
              "
            >
              {loading ? (
                <>
                  <Loader2
                    size={15}
                    className="animate-spin"
                  />
                  Saving...
                </>
              ) : (
                "Save changes"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default EditTaskModal;