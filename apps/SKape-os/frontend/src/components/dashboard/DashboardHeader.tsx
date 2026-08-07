function DashboardHeader() {
    const hour = new Date().getHours();
  
    let greeting = "Good Evening";
  
    if (hour < 12) {
      greeting = "Good Morning";
    } else if (hour < 18) {
      greeting = "Good Afternoon";
    }
  
    return (
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-white">
            {greeting} 👋
          </h1>
  
          <p className="mt-2 text-zinc-400">
            Welcome back to SKape.
            Here's your workspace overview.
          </p>
        </div>
  
        <button className="rounded-xl bg-emerald-600 px-6 py-3 font-semibold text-white transition hover:bg-emerald-500">
          + New Project
        </button>
      </div>
    );
  }
  
  export default DashboardHeader;