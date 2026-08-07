function Topbar() {
    return (
      <header className="flex h-20 items-center justify-between border-b border-zinc-800 bg-zinc-950 px-8">
  
        <div>
          <h2 className="text-2xl font-bold text-white">
            Dashboard
          </h2>
  
          <p className="text-zinc-500">
            Welcome back 👋
          </p>
        </div>
  
        <div className="flex items-center gap-4">
  
          <button className="rounded-xl bg-emerald-600 px-5 py-2 font-medium text-white transition hover:bg-emerald-500">
            + Create
          </button>
  
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-zinc-800 font-semibold text-white">
            S
          </div>
  
        </div>
  
      </header>
    );
  }
  
  export default Topbar;