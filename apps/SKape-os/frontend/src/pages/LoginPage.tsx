import AuthBranding from "../features/auth/components/AuthBranding";
import LoginForm from "../features/auth/components/LoginForm";

function LoginPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-white flex">

      <AuthBranding />

      <div className="flex flex-1 items-center justify-center px-8">

        <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900 p-10 shadow-2xl">

          <h2 className="text-3xl font-bold">
            Welcome Back
          </h2>

          <p className="mt-2 text-zinc-400">
            Sign in to continue
          </p>

          <LoginForm />

        </div>

      </div>

    </div>
  );
}

export default LoginPage;