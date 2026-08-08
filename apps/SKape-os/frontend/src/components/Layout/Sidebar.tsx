import {
  Building2,
  CheckSquare,
  FolderKanban,
  LayoutDashboard,
  Settings,
  X,
  type LucideIcon,
} from "lucide-react";
import { NavLink } from "react-router-dom";

type NavigationItem = {
  label: string;
  path: string;
  icon: LucideIcon;
};

type SidebarProps = {
  open: boolean;
  onClose: () => void;
};

const workspaceNavigation: NavigationItem[] = [
  {
    label: "Dashboard",
    path: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    label: "Projects",
    path: "/projects",
    icon: FolderKanban,
  },
  {
    label: "Tasks",
    path: "/tasks",
    icon: CheckSquare,
  },
];

const managementNavigation: NavigationItem[] = [
  {
    label: "Organization",
    path: "/organizations",
    icon: Building2,
  },
  {
    label: "Settings",
    path: "/settings",
    icon: Settings,
  },
];

function Sidebar({
  open,
  onClose,
}: SidebarProps) {
  return (
    <>
      {/* Mobile backdrop */}
      <button
        type="button"
        aria-label="Close navigation"
        onClick={onClose}
        className={`
          fixed
          inset-0
          z-40
          bg-black/60
          backdrop-blur-[2px]
          transition-opacity
          duration-200
          lg:hidden
          ${
            open
              ? "pointer-events-auto opacity-100"
              : "pointer-events-none opacity-0"
          }
        `}
      />

      {/* Navigation drawer */}
      <aside
        aria-label="Primary navigation"
        className={`
          fixed
          inset-y-0
          left-0
          z-50
          flex
          w-[280px]
          shrink-0
          flex-col
          border-r
          border-zinc-800/80
          bg-zinc-950
          shadow-2xl
          transition-transform
          duration-200
          ease-out
          lg:static
          lg:z-auto
          lg:w-[248px]
          lg:translate-x-0
          lg:shadow-none
          ${
            open
              ? "translate-x-0"
              : "-translate-x-full"
          }
        `}
      >
        {/* Brand */}
        <div className="flex h-[72px] shrink-0 items-center justify-between border-b border-zinc-800/70 px-5 lg:px-6">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-emerald-500 text-sm font-extrabold tracking-[-0.05em] text-zinc-950">
              S
            </span>

            <span className="text-[17px] font-bold tracking-[-0.045em] text-zinc-100">
              SKape
            </span>
          </div>

          {/* Mobile close */}
          <button
            type="button"
            aria-label="Close navigation"
            onClick={onClose}
            className="
              flex
              h-9
              w-9
              items-center
              justify-center
              rounded-lg
              text-zinc-500
              transition-colors
              hover:bg-zinc-900
              hover:text-zinc-200
              lg:hidden
            "
          >
            <X
              size={18}
              strokeWidth={1.8}
            />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-6">
          <NavigationSection
            label="Workspace"
            items={workspaceNavigation}
            onNavigate={onClose}
          />

          <div className="mt-8">
            <NavigationSection
              label="Management"
              items={managementNavigation}
              onNavigate={onClose}
            />
          </div>
        </nav>

        {/* Workspace status */}
        <div className="shrink-0 border-t border-zinc-800/70 p-4">
          <div className="flex items-center gap-3 rounded-lg px-2 py-2">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-40" />

              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>

            <div className="min-w-0">
              <p className="truncate text-xs font-semibold text-zinc-400">
                Workspace online
              </p>

              <p className="mt-0.5 truncate text-[11px] text-zinc-600">
                All systems operational
              </p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}

type NavigationSectionProps = {
  label: string;
  items: NavigationItem[];
  onNavigate: () => void;
};

function NavigationSection({
  label,
  items,
  onNavigate,
}: NavigationSectionProps) {
  return (
    <div>
      <p className="px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-zinc-600">
        {label}
      </p>

      <div className="mt-3 space-y-1">
        {items.map((item) => {
          const Icon = item.icon;

          return (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={onNavigate}
              className={({ isActive }) =>
                [
                  "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-150",
                  isActive
                    ? "bg-zinc-800/80 font-semibold text-zinc-100"
                    : "font-medium text-zinc-500 hover:bg-zinc-900 hover:text-zinc-200",
                ].join(" ")
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    size={17}
                    strokeWidth={isActive ? 2 : 1.7}
                    className={
                      isActive
                        ? "text-emerald-400"
                        : "text-zinc-600 transition-colors group-hover:text-zinc-400"
                    }
                    aria-hidden="true"
                  />

                  <span>{item.label}</span>

                  {isActive && (
                    <span
                      aria-hidden="true"
                      className="ml-auto h-1.5 w-1.5 rounded-full bg-emerald-400"
                    />
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </div>
    </div>
  );
}

export default Sidebar;