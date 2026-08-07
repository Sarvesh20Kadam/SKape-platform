function RecentActivity() {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6">
        <h2 className="mb-6 text-xl font-bold text-white">
          Activity
        </h2>
  
        <div className="flex h-56 items-center justify-center rounded-xl border border-dashed border-zinc-700">
          <p className="text-zinc-500">
            No activity yet
          </p>
        </div>
      </div>
    );
  }
  
  export default RecentActivity;