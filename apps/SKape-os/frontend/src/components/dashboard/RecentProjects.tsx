function RecentProjects() {
  return (
    <section
      className="
        overflow-hidden
        rounded-xl
        border
        border-zinc-800/80
        bg-zinc-900/40
      "
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800/70 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-zinc-200">
            Recent projects
          </h2>

          <p className="mt-1 text-xs text-zinc-500">
            Your latest workspace projects.
          </p>
        </div>

        <button
          type="button"
          className="
            text-xs
            font-semibold
            text-zinc-500
            transition-colors
            hover:text-emerald-400
          "
        >
          View all
        </button>
      </div>

      {/* Empty state */}
      <div className="flex min-h-[260px] flex-col items-center justify-center px-6 py-12 text-center">
        <div
          className="
            flex
            h-11
            w-11
            items-center
            justify-center
            rounded-lg
            border
            border-zinc-800
            bg-zinc-950
          "
        >
          <div className="h-2 w-2 rounded-full bg-zinc-700" />
        </div>

        <h3 className="mt-4 text-sm font-semibold text-zinc-300">
          No projects yet
        </h3>

        <p className="mt-1.5 max-w-xs text-xs leading-5 text-zinc-500">
          Create your first project to start organizing
          work across your workspace.
        </p>

        <button
          type="button"
          className="
            mt-5
            rounded-lg
            border
            border-zinc-700
            bg-zinc-800/60
            px-3.5
            py-2
            text-xs
            font-semibold
            text-zinc-300
            transition-all
            hover:border-emerald-500/40
            hover:bg-zinc-800
            hover:text-emerald-400
          "
        >
          Create project
        </button>
      </div>
    </section>
  );
}

export default RecentProjects;