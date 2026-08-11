import { useEffect, useRef, useState } from "react";
import {
  FolderPlus,
  Loader2,
  X,
} from "lucide-react";

import type { ProjectStatus } from "../../features/projects/types/project.types";

type CreateProjectModalProps = {
  open: boolean;
  loading?: boolean;
  error?: string | null;

  mode?: "create" | "edit";

  initialName?: string;
  initialDescription?: string;
  initialStatus?: ProjectStatus;

  onClose: () => void;

  onSubmit: (data: {
    name: string;
    description: string;
    status?: ProjectStatus;
  }) => Promise<void> | void;
};

function CreateProjectModal({
  open,
  loading = false,
  error = null,
  mode = "create",
  initialName = "",
  initialDescription = "",
  initialStatus = "planned",
  onClose,
  onSubmit,
}: CreateProjectModalProps) {
  const nameRef =
    useRef<HTMLInputElement>(null);

  const [name, setName] =
    useState(initialName);

  const [description, setDescription] =
    useState(initialDescription);

  const [status, setStatus] =
    useState<ProjectStatus>(
      initialStatus,
    );

  const [validationError, setValidationError] =
    useState<string | null>(null);

  const isEdit = mode === "edit";

  useEffect(() => {
    if (!open) {
      return;
    }

    setName(initialName);
    setDescription(initialDescription);
    setStatus(initialStatus);
    setValidationError(null);

    const timer = window.setTimeout(() => {
      nameRef.current?.focus();
    }, 50);

    return () => {
      window.clearTimeout(timer);
    };
  }, [
    open,
    initialName,
    initialDescription,
    initialStatus,
  ]);

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
  }, [
    open,
    loading,
    onClose,
  ]);

  if (!open) {
    return null;
  }

  const handleSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    const trimmedName =
      name.trim();

    const trimmedDescription =
      description.trim();

    if (!trimmedName) {
      setValidationError(
        "Project name is required.",
      );

      nameRef.current?.focus();

      return;
    }

    if (trimmedName.length < 2) {
      setValidationError(
        "Project name must contain at least 2 characters.",
      );

      nameRef.current?.focus();

      return;
    }

    if (trimmedName.length > 100) {
      setValidationError(
        "Project name cannot exceed 100 characters.",
      );

      nameRef.current?.focus();

      return;
    }

    if (
      trimmedDescription.length >
      1000
    ) {
      setValidationError(
        "Description cannot exceed 1000 characters.",
      );

      return;
    }

    setValidationError(null);

    await onSubmit({
      name: trimmedName,
      description:
        trimmedDescription,
      status: isEdit
        ? status
        : undefined,
    });
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
        px-4
        py-6
      "
      role="dialog"
      aria-modal="true"
      aria-labelledby="project-modal-title"
    >
      {/* Backdrop */}
      <button
        type="button"
        aria-label="Close modal"
        disabled={loading}
        onClick={onClose}
        className="
          absolute
          inset-0
          cursor-default
          bg-black/70
          backdrop-blur-[3px]
        "
      />

      {/* Modal */}
      <div
        className="
          relative
          z-10
          w-full
          max-w-lg
          overflow-hidden
          rounded-2xl
          border
          border-zinc-800
          bg-zinc-950
          shadow-2xl
          shadow-black/50
        "
      >
        {/* Accent */}
        <div className="h-px w-full bg-gradient-to-r from-transparent via-emerald-500/70 to-transparent" />

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
              <FolderPlus
                size={18}
                strokeWidth={1.8}
                className="text-emerald-400"
              />
            </div>

            <div>
              <h2
                id="project-modal-title"
                className="
                  text-base
                  font-semibold
                  tracking-[-0.01em]
                  text-zinc-100
                "
              >
                {isEdit
                  ? "Edit project"
                  : "Create project"}
              </h2>

              <p className="mt-1 text-sm text-zinc-500">
                {isEdit
                  ? "Update your project details."
                  : "Start a new project in your workspace."}
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

            {/* Name */}
            <div>
              <label
                htmlFor="project-name"
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
                Project name
              </label>

              <input
                ref={nameRef}
                id="project-name"
                type="text"
                value={name}
                disabled={loading}
                maxLength={100}
                onChange={(event) => {
                  setName(
                    event.target.value,
                  );

                  setValidationError(
                    null,
                  );
                }}
                placeholder="e.g. Website redesign"
                autoComplete="off"
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
                  {name.length}/100
                </span>
              </div>
            </div>

            {/* Description */}
            <div>
              <label
                htmlFor="project-description"
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

                <span
                  className="
                    ml-2
                    font-normal
                    normal-case
                    tracking-normal
                    text-zinc-700
                  "
                >
                  Optional
                </span>
              </label>

              <textarea
                id="project-description"
                value={description}
                disabled={loading}
                maxLength={1000}
                rows={4}
                onChange={(event) => {
                  setDescription(
                    event.target.value,
                  );

                  setValidationError(
                    null,
                  );
                }}
                placeholder="What are you building?"
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
                  {description.length}/1000
                </span>
              </div>
            </div>

            {/* Status */}
            {isEdit && (
              <div>
                <label
                  htmlFor="project-status"
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
                  id="project-status"
                  value={status}
                  disabled={loading}
                  onChange={(event) => {
                    setStatus(
                      event.target
                        .value as ProjectStatus,
                    );

                    setValidationError(
                      null,
                    );
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
                  <option value="planned">
                    Planned
                  </option>

                  <option value="active">
                    Active
                  </option>

                  <option value="completed">
                    Completed
                  </option>

                  <option value="archived">
                    Archived
                  </option>
                </select>
              </div>
            )}

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

                  {isEdit
                    ? "Saving..."
                    : "Creating..."}
                </>
              ) : isEdit ? (
                "Save changes"
              ) : (
                "Create project"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default CreateProjectModal;