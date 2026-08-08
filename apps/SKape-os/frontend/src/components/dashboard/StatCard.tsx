type StatCardProps = {
  title: string;
  value: number | string;
};

function StatCard({
  title,
  value,
}: StatCardProps) {
  return (
    <article
      className="
        group
        relative
        overflow-hidden
        rounded-xl
        border
        border-zinc-800/80
        bg-zinc-900/60
        p-5
        transition-all
        duration-200
        hover:-translate-y-0.5
        hover:border-zinc-700
        hover:bg-zinc-900
      "
    >
      {/* Subtle accent line */}
      <div
        aria-hidden="true"
        className="
          absolute
          left-0
          top-0
          h-px
          w-0
          bg-emerald-500
          transition-all
          duration-300
          group-hover:w-full
        "
      />

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm font-semibold text-zinc-500">
          {title}
        </p>

        <span
          aria-hidden="true"
          className="
            h-1.5
            w-1.5
            shrink-0
            rounded-full
            bg-zinc-700
            transition-colors
            duration-200
            group-hover:bg-emerald-500
          "
        />
      </div>

      {/* Value */}
      <div className="mt-7">
        <p
          className="
            font-mono
            text-3xl
            font-medium
            tracking-[-0.04em]
            text-zinc-100
          "
        >
          {value}
        </p>
      </div>

      {/* Bottom metadata */}
      <div className="mt-4 flex items-center gap-2">
        <span className="h-px w-4 bg-zinc-700" />

        <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-zinc-600">
          Current
        </span>
      </div>
    </article>
  );
}

export default StatCard;