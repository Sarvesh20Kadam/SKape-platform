type StatCardProps = {
    title: string;
    value: number;
  };
  
  function StatCard({
    title,
    value,
  }: StatCardProps) {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 transition hover:border-emerald-600">
        <h3 className="text-zinc-400">
          {title}
        </h3>
  
        <p className="mt-3 text-4xl font-bold text-white">
          {value}
        </p>
      </div>
    );
  }
  
  export default StatCard;