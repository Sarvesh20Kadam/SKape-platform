import { useMemo, useState } from "react";

import DashboardLayout from "../components/layout/DashboardLayout";
import CreateProjectModal from "../components/projects/CreateProjectModal";
import { useProjects } from "../hooks/useProjects";

import type { ProjectStatus } from "../features/projects/types/project.types";

const statusOptions: Array<{
  label: string;
  value: "all" | ProjectStatus;
}> = [
  {
    label: "All projects",
    value: "all",
  },
  {
    label: "Planned",
    value: "planned",
  },
  {
    label: "Active",
    value: "active",
  },
  {
    label: "Completed",
    value: "completed",
  },
  {
    label: "Archived",
    value: "archived",
  },
];

function ProjectsPage() {
  const {
    projects,
    loading,
    creating,
    error,
    createProject,
  } = useProjects();

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<
    "all" | ProjectStatus
  >("all");

  const [createModalOpen, setCreateModalOpen] =
    useState(false);

  const filteredProjects = useMemo(() => {
    const normalizedSearch =
      search.trim().toLowerCase();

    return projects.filter((project) => {
      const matchesSearch =
        normalizedSearch.length === 0 ||
        project.name
          .toLowerCase()
          .includes(normalizedSearch) ||
        project.description
          .toLowerCase()
          .includes(normalizedSearch);

      const matchesStatus =
        status === "all" ||
        project.status === status;

      return matchesSearch && matchesStatus;
    });
  }, [projects, search, status]);

  const handleCreateProject = async (data: {
    name: string;
    description: string;
  }) => {
    await createProject(data);
    setCreateModalOpen(false);
  };

  return (
    <DashboardLayout>
      <section className="space-y-8">
        {/* Page Header */}
        <div className="flex flex-col gap-5 border-b border-zinc-800/70 pb-8 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="mb-3 flex items-center gap-2">
              <span
                aria-hidden="true"
                className="h-1.5 w-1.5 rounded-full bg-emerald-500"
              />

              <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-600">
                Workspace
              </span>
            </div>

            <h1 className="text-3xl font-bold tracking-[-0.04em] text-zinc-100 sm:text-4xl">
              Projects
            </h1>

            <p className="mt-2 max-w-xl text-sm leading-6 text-zinc-500">
              Manage and organize the work happening
              across your workspace.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setCreateModalOpen(true)}
            className="inline-flex h-11 items-center justify-center rounded-lg bg-emerald-500 px-5 text-sm font-semibold text-zinc-950 transition-all hover:bg-emerald-400 active:scale-[0.98]"
          >
            + New project
          </button>
        </div>

        {/* Toolbar */}
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <input
              type="search"
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="Search projects..."
              aria-label="Search projects"
              className="h-11 w-full rounded-lg border border-zinc-800 bg-zinc-900/50 px-4 text-sm text-zinc-200 outline-none transition placeholder:text-zinc-600 hover:border-zinc-700 focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/10"
            />
          </div>

          <select
            value={status}
            onChange={(event) =>
              setStatus(
                event.target.value as
                  | "all"
                  | ProjectStatus,
              )
            }
            aria-label="Filter projects by status"
            className="h-11 rounded-lg border border-zinc-800 bg-zinc-900/50 px-4 text-sm text-zinc-300 outline-none transition focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/10"
          >
            {statusOptions.map((option) => (
              <option
                key={option.value}
                value={option.value}
              >
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {/* Project Content */}
        <div>
          {/* Loading */}
          {loading && (
            <div className="grid gap-4 xl:grid-cols-2">
              {[1, 2, 3, 4].map((item) => (
                <div
                  key={item}
                  className="h-44 animate-pulse rounded-xl border border-zinc-800/70 bg-zinc-900/40"
                />
              ))}
            </div>
          )}

          {/* Error */}
          {!loading && error && (
            <div
              role="alert"
              className="rounded-xl border border-red-500/20 bg-red-500/5 p-6"
            >
              <p className="text-sm font-medium text-red-400">
                {error}
              </p>
            </div>
          )}

          {/* Empty State */}
          {!loading &&
            !error &&
            filteredProjects.length === 0 && (
              <div className="rounded-xl border border-dashed border-zinc-800 px-6 py-16 text-center">
                <h2 className="text-base font-semibold text-zinc-200">
                  {projects.length === 0
                    ? "No projects yet"
                    : "No projects found"}
                </h2>

                <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-zinc-600">
                  {projects.length === 0
                    ? "Create your first project to start organizing work across your workspace."
                    : "Try changing your search or status filter."}
                </p>

                {projects.length === 0 && (
                  <button
                    type="button"
                    onClick={() =>
                      setCreateModalOpen(true)
                    }
                    className="mt-6 inline-flex h-10 items-center justify-center rounded-lg bg-emerald-500 px-4 text-sm font-semibold text-zinc-950 transition hover:bg-emerald-400 active:scale-[0.98]"
                  >
                    Create your first project
                  </button>
                )}
              </div>
            )}

          {/* Projects */}
          {!loading &&
            !error &&
            filteredProjects.length > 0 && (
              <div className="grid gap-4 xl:grid-cols-2">
                {filteredProjects.map((project) => (
                  <article
                    key={project.id}
                    className="group rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-6 transition-all duration-200 hover:border-zinc-700 hover:bg-zinc-900/60"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <h2 className="truncate text-base font-semibold text-zinc-100">
                          {project.name}
                        </h2>

                        <p className="mt-2 line-clamp-2 text-sm leading-6 text-zinc-500">
                          {project.description ||
                            "No description provided."}
                        </p>
                      </div>

                      <span className="shrink-0 rounded-full border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                        {project.status}
                      </span>
                    </div>

                    <div className="mt-8 flex items-center justify-between border-t border-zinc-800/70 pt-4">
                      <span className="text-xs text-zinc-600">
                        Project #{project.id}
                      </span>

                      <button
                        type="button"
                        className="text-xs font-medium text-zinc-500 transition-colors group-hover:text-emerald-400"
                      >
                        Open project →
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
        </div>
      </section>

      {/* Create Project Modal */}
      <CreateProjectModal
        open={createModalOpen}
        loading={creating}
        error={error}
        onClose={() => setCreateModalOpen(false)}
        onSubmit={handleCreateProject}
      />
    </DashboardLayout>
  );
}

export default ProjectsPage;