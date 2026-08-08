function RecentActivity() {
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
            Recent activity
          </h2>

          <p className="mt-1 text-xs text-zinc-500">
            Latest changes across your workspace.
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
          <div className="flex gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-zinc-700" />
            <span className="h-1.5 w-1.5 rounded-full bg-zinc-800" />
            <span className="h-1.5 w-1.5 rounded-full bg-zinc-800" />
          </div>
        </div>

        <h3 className="mt-4 text-sm font-semibold text-zinc-300">
          Nothing happening yet
        </h3>

        <p className="mt-1.5 max-w-xs text-xs leading-5 text-zinc-500">
          Activity from projects, tasks, and team members
          will appear here.
        </p>
      </div>
    </section>
  );
}

export default RecentActivity;