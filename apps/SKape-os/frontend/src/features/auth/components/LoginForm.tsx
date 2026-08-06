function LoginForm() {
    return (
      <form className="mt-8 space-y-5">
  
        <div>
          <label className="block mb-2 text-sm text-zinc-400">
            Email
          </label>
  
          <input
            type="email"
            placeholder="john@example.com"
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 outline-none transition focus:border-emerald-500"
          />
        </div>
  
        <div>
          <label className="block mb-2 text-sm text-zinc-400">
            Password
          </label>
  
          <input
            type="password"
            placeholder="••••••••"
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 outline-none transition focus:border-emerald-500"
          />
        </div>
  
        <button
          className="w-full rounded-lg bg-emerald-600 py-3 font-semibold transition hover:bg-emerald-500"
        >
          Sign In
        </button>
  
      </form>
    );
  }
  
  export default LoginForm;