function DashboardHeader() {
  return (
    <header className="flex flex-col gap-5 border-b border-zinc-800/80 pb-7 sm:flex-row sm:items-end sm:justify-between">
      {/* =====================================================
          TITLE
          ===================================================== */}

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />

          <span className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
            Workspace
          </span>
        </div>

        <div>
          <h1 className="text-[2rem] font-bold leading-tight tracking-[-0.035em] text-zinc-100 sm:text-[2.25rem]">
            Dashboard
          </h1>

          <p className="mt-1.5 text-sm font-medium text-zinc-500 sm:text-[0.9375rem]">
            A clear view of what&apos;s happening across your workspace.
          </p>
        </div>
      </div>

      {/* =====================================================
          ACTION
          ===================================================== */}

      <button
        type="button"
        className="group inline-flex h-10 items-center justify-center gap-2 self-start rounded-lg bg-emerald-500 px-4 text-sm font-bold text-zinc-950 shadow-sm transition-all duration-200 hover:bg-emerald-400 hover:shadow-[0_0_24px_rgba(16,185,129,0.12)] active:translate-y-px sm:self-auto"
      >
        <span
          aria-hidden="true"
          className="text-base leading-none transition-transform duration-200 group-hover:rotate-90"
        >
          +
        </span>

        <span>Create</span>
      </button>
    </header>
  );
}

export default DashboardHeader;