import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  FolderKanban,
  CheckSquare,
  Building2,
  Calendar,
  Settings,
  LogOut,
} from "lucide-react";

const menuItems = [
  {
    name: "Dashboard",
    icon: LayoutDashboard,
    path: "/dashboard",
  },
  {
    name: "Organizations",
    icon: Building2,
    path: "/organizations",
  },
  {
    name: "Projects",
    icon: FolderKanban,
    path: "/projects",
  },
  {
    name: "Tasks",
    icon: CheckSquare,
    path: "/tasks",
  },
  {
    name: "Calendar",
    icon: Calendar,
    path: "/calendar",
  },
  {
    name: "Settings",
    icon: Settings,
    path: "/settings",
  },
];

function Sidebar() {
  const location = useLocation();

  return (
    <aside className="flex h-screen w-72 flex-col border-r border-zinc-800 bg-zinc-950">

      <div className="border-b border-zinc-800 px-8 py-6">
        <h1 className="text-3xl font-bold tracking-tight text-white">
          SKape
        </h1>

        <p className="mt-2 text-sm text-zinc-500">
          Project Management
        </p>
      </div>

      <nav className="flex-1 px-4 py-6">

        {menuItems.map((item) => {
          const Icon = item.icon;

          const active =
            location.pathname === item.path;

          return (
            <Link
              key={item.name}
              to={item.path}
              className={`mb-2 flex items-center gap-3 rounded-xl px-4 py-3 transition ${
                active
                  ? "bg-emerald-600 text-white"
                  : "text-zinc-400 hover:bg-zinc-900 hover:text-white"
              }`}
            >
              <Icon size={20} />

              {item.name}
            </Link>
          );
        })}

      </nav>

      <div className="border-t border-zinc-800 p-4">
        <button className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-zinc-400 transition hover:bg-zinc-900 hover:text-red-400">
          <LogOut size={20} />
          Logout
        </button>
      </div>

    </aside>
  );
}

export default Sidebar;