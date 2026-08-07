import {
    FolderPlus,
    UserPlus,
    CheckSquare,
    Building2,
  } from "lucide-react";
  
  const actions = [
    {
      title: "New Project",
      icon: FolderPlus,
    },
    {
      title: "Invite Member",
      icon: UserPlus,
    },
    {
      title: "New Task",
      icon: CheckSquare,
    },
    {
      title: "Organization",
      icon: Building2,
    },
  ];
  
  function QuickActions() {
    return (
      <div className="mb-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {actions.map((action) => {
          const Icon = action.icon;
  
          return (
            <button
              key={action.title}
              className="flex items-center gap-4 rounded-2xl border border-zinc-800 bg-zinc-900 p-5 transition hover:border-emerald-500 hover:bg-zinc-800"
            >
              <Icon
                size={24}
                className="text-emerald-500"
              />
  
              <span className="font-medium text-white">
                {action.title}
              </span>
            </button>
          );
        })}
      </div>
    );
  }
  
  export default QuickActions;