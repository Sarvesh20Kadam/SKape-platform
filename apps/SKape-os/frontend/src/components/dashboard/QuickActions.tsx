import {
  FolderPlus,
  ListPlus,
  UserPlus,
  Building2,
  ArrowUpRight,
} from "lucide-react";

type QuickAction = {
  title: string;
  description: string;
  icon: typeof FolderPlus;
};

const actions: QuickAction[] = [
  {
    title: "New project",
    description: "Start something new",
    icon: FolderPlus,
  },
  {
    title: "Create task",
    description: "Add work to your queue",
    icon: ListPlus,
  },
  {
    title: "Invite member",
    description: "Grow your workspace",
    icon: UserPlus,
  },
  {
    title: "Organization",
    description: "Manage your workspace",
    icon: Building2,
  },
];

function QuickActions() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold tracking-tight text-zinc-200">
            Quick actions
          </h2>

          <p className="mt-1 text-sm text-zinc-500">
            Common actions for your workspace.
          </p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {actions.map((action) => {
          const Icon = action.icon;

          return (
            <button
              key={action.title}
              type="button"
              className="
                group
                flex
                min-h-[92px]
                items-center
                gap-4
                rounded-xl
                border
                border-zinc-800/80
                bg-zinc-900/40
                p-4
                text-left
                transition-all
                duration-200
                hover:border-zinc-700
                hover:bg-zinc-900
                active:scale-[0.99]
              "
            >
              <span
                className="
                  flex
                  h-10
                  w-10
                  shrink-0
                  items-center
                  justify-center
                  rounded-lg
                  border
                  border-zinc-800
                  bg-zinc-950
                  text-zinc-400
                  transition-colors
                  duration-200
                  group-hover:border-emerald-500/30
                  group-hover:text-emerald-400
                "
              >
                <Icon
                  size={18}
                  strokeWidth={1.8}
                  aria-hidden="true"
                />
              </span>

              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold text-zinc-200">
                  {action.title}
                </span>

                <span className="mt-1 block truncate text-xs text-zinc-500">
                  {action.description}
                </span>
              </span>

              <ArrowUpRight
                size={15}
                strokeWidth={1.8}
                aria-hidden="true"
                className="
                  shrink-0
                  text-zinc-700
                  transition-all
                  duration-200
                  group-hover:-translate-y-0.5
                  group-hover:translate-x-0.5
                  group-hover:text-zinc-400
                "
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default QuickActions;