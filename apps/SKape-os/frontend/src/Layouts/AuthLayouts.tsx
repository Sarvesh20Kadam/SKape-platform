import type { ReactNode } from "react";

type AuthLayoutProps = {
  children: ReactNode;
};

function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen flex bg-zinc-950 text-white">

      {/* Left Branding */}
      <div className="hidden lg:flex w-1/2 items-center justify-center bg-gradient-to-br from-zinc-950 via-zinc-900 to-emerald-950">

        <div className="max-w-lg px-12">

          <h1 className="text-6xl font-bold tracking-tight">
            SKape
          </h1>

          <p className="mt-6 text-2xl text-zinc-300">
            Build.
            <br />
            Manage.
            <br />
            Scale.
          </p>

          <p className="mt-12 text-zinc-500">
            Modern Project & Team Management Platform
          </p>

        </div>

      </div>

      {/* Right */}
      <div className="flex flex-1 items-center justify-center px-8">

        {children}

      </div>

    </div>
  );
}

export default AuthLayout;